"""
SYNC MANUAL — Sincronización manual de motos facturadas en Alegra
Endpoint para sincronizar motos que se facturaron directamente en Alegra
"""

import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import db
from dependencies import get_current_user

router = APIRouter(prefix="/sync", tags=["sync_manual"])
logger = logging.getLogger(__name__)


class SyncMotoRequest(BaseModel):
    """Request para sincronizar una moto."""
    chasis: str
    factura_id: str
    cliente: str


class SyncMotoResponse(BaseModel):
    """Response de sincronización."""
    ok: bool
    moto_id: str
    estado_antes: dict
    estado_despues: dict
    loanbook_id: str
    loanbook_codigo: str
    timestamp: str


@router.post("/moto/urgente", response_model=SyncMotoResponse)
async def sincronizar_moto_urgente(
    req: SyncMotoRequest,
    current_user=Depends(get_current_user),
):
    """
    Sincronizar moto que fue facturada directamente en Alegra.

    Pasos:
    1. Buscar moto por chasis
    2. Actualizar estado a "Vendida"
    3. Crear/verificar loanbook
    4. Publicar evento
    5. Invalidar caché
    """
    try:
        fecha_hoy = datetime.now(timezone.utc).isoformat()

        logger.info(f"[SYNC] Iniciando sincronización de moto: {req.chasis}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 1: Buscar moto
        # ════════════════════════════════════════════════════════════════════════════════
        moto = await db.inventario_motos.find_one({"chasis": req.chasis})

        if not moto:
            logger.warning(f"[SYNC] Moto no encontrada: {req.chasis}")
            raise HTTPException(
                status_code=404,
                detail=f"Moto con chasis {req.chasis} no encontrada"
            )

        estado_antes = {
            "id": moto.get("id"),
            "estado": moto.get("estado"),
            "factura_alegra_id": moto.get("factura_alegra_id"),
            "propietario": moto.get("propietario"),
        }

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 2: Actualizar estado
        # ════════════════════════════════════════════════════════════════════════════════
        update_result = await db.inventario_motos.update_one(
            {"chasis": req.chasis},
            {
                "$set": {
                    "estado": "Vendida",
                    "factura_alegra_id": req.factura_id,
                    "fecha_venta": fecha_hoy,
                    "propietario": req.cliente,
                    "updated_at": fecha_hoy,
                    "updated_by": f"sync_manual_by_{current_user}",
                }
            }
        )

        moto_updated = await db.inventario_motos.find_one({"chasis": req.chasis})

        estado_despues = {
            "id": moto_updated.get("id"),
            "estado": moto_updated.get("estado"),
            "factura_alegra_id": moto_updated.get("factura_alegra_id"),
            "propietario": moto_updated.get("propietario"),
            "fecha_venta": moto_updated.get("fecha_venta"),
        }

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 3: Crear/Verificar loanbook
        # ════════════════════════════════════════════════════════════════════════════════
        loanbook = await db.loanbook.find_one({"moto_chasis": req.chasis})
        loanbook_id = None
        codigo_lb = None

        if loanbook:
            loanbook_id = loanbook.get("id")
            codigo_lb = loanbook.get("codigo")
            logger.info(f"[SYNC] Loanbook ya existe: {codigo_lb}")
        else:
            # Generar código LB-2026-XXXX
            ultimo = await db.loanbook.find_one(
                {"codigo": {"$regex": "^LB-2026-"}},
                sort=[("codigo", -1)]
            )

            if ultimo and ultimo.get("codigo"):
                codigo_str = ultimo["codigo"].split("-")[-1]
                try:
                    num = int(codigo_str)
                    nuevo_num = num + 1
                except:
                    nuevo_num = 1
            else:
                nuevo_num = 1

            codigo_lb = f"LB-2026-{nuevo_num:04d}"
            loanbook_id = str(uuid.uuid4())

            nuevo_loanbook = {
                "id": loanbook_id,
                "codigo": codigo_lb,
                "estado": "pendiente_entrega",
                "moto_chasis": req.chasis,
                "factura_alegra_id": req.factura_id,
                "cliente_nombre": req.cliente,
                "created_at": fecha_hoy,
                "updated_at": fecha_hoy,
                "created_by": f"sync_manual_by_{current_user}",
            }

            await db.loanbook.insert_one(nuevo_loanbook)
            logger.info(f"[SYNC] Loanbook creado: {codigo_lb}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 4: Publicar evento
        # ════════════════════════════════════════════════════════════════════════════════
        evento = {
            "id": str(uuid.uuid4()),
            "event_type": "factura.venta.creada",
            "source": "sync_manual",
            "chasis": req.chasis,
            "factura_id": req.factura_id,
            "cliente": req.cliente,
            "loanbook_id": loanbook_id,
            "timestamp": fecha_hoy,
            "processed": True,
            "usuario": current_user,
        }

        await db.roddos_events.insert_one(evento)
        logger.info(f"[SYNC] Evento publicado: factura.venta.creada")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 5: Invalidar caché
        # ════════════════════════════════════════════════════════════════════════════════
        await db.cfo_cache.update_many(
            {},
            {"$set": {"invalidated_at": fecha_hoy, "is_valid": False}}
        )
        logger.info(f"[SYNC] CFO cache invalidado")

        logger.info(f"[SYNC] Sincronización completada: {req.chasis} → {req.factura_id}")

        return SyncMotoResponse(
            ok=True,
            moto_id=moto.get("id"),
            estado_antes=estado_antes,
            estado_despues=estado_despues,
            loanbook_id=loanbook_id,
            loanbook_codigo=codigo_lb,
            timestamp=fecha_hoy,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SYNC] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
