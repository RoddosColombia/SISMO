"""conciliacion.py — Endpoints para carga de extractos bancarios y conciliación automática.

Endpoints:
  POST   /api/conciliacion/cargar-extracto  — Cargar extracto bancario
  GET    /api/conciliacion/pendientes       — Listar movimientos pendientes
  POST   /api/conciliacion/resolver/{id}    — Resolver movimiento ambiguo
  GET    /api/conciliacion/estado/{fecha}   — Estado de conciliación para una fecha
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from pydantic import BaseModel

from database import db
from dependencies import get_current_user, log_action
from services.bank_reconciliation import BankReconciliationEngine, Banco

router = APIRouter(prefix="/conciliacion", tags=["conciliacion"])
logger = logging.getLogger(__name__)

engine = BankReconciliationEngine(db)


# ── Pydantic Models ────────────────────────────────────────────────────────

class ResolverMovimientoRequest(BaseModel):
    cuenta_debito: str
    cuenta_credito: str
    observacion: str = ""


class ResumenConciliacion(BaseModel):
    fecha: str
    porcentaje_conciliado: float
    total_movimientos: int
    total_causado: float
    total_pendiente: float
    journals_creados: int
    movimientos_pendientes: int
    discrepancias: list


# ── Background Task Handler ────────────────────────────────────────────────

_jobs_estado: dict[str, dict] = {}  # In-memory job tracking


async def _procesar_extracto_background(
    job_id: str,
    banco: str,
    fecha: str,
    archivo_bytes: bytes,
    usuario_id: str,
):
    """Procesa extracto en background para lotes grandes."""
    _jobs_estado[job_id] = {
        "status": "processing",
        "causados": 0,
        "pendientes": 0,
        "errores": 0,
        "timestamp_inicio": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Parsear
        movimientos = await engine.parsear_extracto(banco, archivo_bytes)
        _jobs_estado[job_id]["total_movimientos"] = len(movimientos)

        # Clasificar
        causables, pendientes = await engine.clasificar_movimientos(movimientos)

        # Causar en Alegra
        for mov in causables:
            exitoso, journal_id, error = await engine.crear_journal_alegra(mov)
            if exitoso:
                _jobs_estado[job_id]["causados"] += 1
                # Guardar en roddos_events
                await db.roddos_events.insert_one({
                    "event_type": "extracto_bancario.causado",
                    "banco": banco,
                    "fecha_movimiento": mov.fecha,
                    "descripcion": mov.descripcion,
                    "monto": mov.monto,
                    "journal_id": journal_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                _jobs_estado[job_id]["errores"] += 1
                logger.error(f"[Job {job_id}] Error causando {mov.descripcion}: {error}")

        # Guardar pendientes
        for mov in pendientes:
            mov_id = await engine.guardar_movimiento_pendiente(mov)
            _jobs_estado[job_id]["pendientes"] += 1
            await db.roddos_events.insert_one({
                "event_type": "extracto_bancario.pendiente",
                "banco": banco,
                "fecha_movimiento": mov.fecha,
                "descripcion": mov.descripcion,
                "monto": mov.monto,
                "movimiento_id": mov_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        _jobs_estado[job_id]["status"] = "completed"
        logger.info(f"[Job {job_id}] Completado: {_jobs_estado[job_id]['causados']} causados, "
                   f"{_jobs_estado[job_id]['pendientes']} pendientes")

    except Exception as e:
        logger.error(f"[Job {job_id}] Error: {e}")
        _jobs_estado[job_id]["status"] = "failed"
        _jobs_estado[job_id]["error"] = str(e)


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/cargar-extracto")
async def cargar_extracto(
    banco: str = Form(...),
    fecha: str = Form(...),
    archivo: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user=Depends(get_current_user),
):
    """
    Carga un extracto bancario, parsea movimientos, clasifica y causa en Alegra.

    Para lotes > 10 movimientos, retorna job_id inmediatamente (procesa en background).
    """
    try:
        # Validar banco
        try:
            Banco[banco.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Banco no soportado: {banco}")

        # Leer archivo
        archivo_bytes = await archivo.read()

        # Parsear extracto
        movimientos = await engine.parsear_extracto(banco, archivo_bytes)

        if not movimientos:
            raise HTTPException(status_code=400, detail="No se encontraron movimientos en el extracto")

        # Clasificar
        causables, pendientes = await engine.clasificar_movimientos(movimientos)

        # Si lote > 10, usar background task
        if len(movimientos) > 10:
            import uuid
            job_id = str(uuid.uuid4())
            background_tasks.add_task(
                _procesar_extracto_background,
                job_id, banco, fecha, archivo_bytes, current_user,
            )

            await log_action(
                current_user,
                "/conciliacion/cargar-extracto",
                "POST",
                {"banco": banco, "fecha": fecha, "total_movimientos": len(movimientos), "job_id": job_id},
            )

            return {
                "job_id": job_id,
                "status": "processing",
                "total_movimientos": len(movimientos),
                "mensaje": "Procesando en background...",
            }

        # Lote pequeño: procesar inmediatamente
        causados = 0
        pendientes_count = 0
        monto_causado = 0.0

        for mov in causables:
            exitoso, journal_id, error = await engine.crear_journal_alegra(mov)
            if exitoso:
                causados += 1
                monto_causado += mov.monto
                await db.roddos_events.insert_one({
                    "event_type": "extracto_bancario.causado",
                    "banco": banco,
                    "fecha_movimiento": mov.fecha,
                    "descripcion": mov.descripcion,
                    "monto": mov.monto,
                    "journal_id": journal_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                logger.error(f"Error causando {mov.descripcion}: {error}")

        for mov in pendientes:
            mov_id = await engine.guardar_movimiento_pendiente(mov)
            pendientes_count += 1
            await db.roddos_events.insert_one({
                "event_type": "extracto_bancario.pendiente",
                "banco": banco,
                "fecha_movimiento": mov.fecha,
                "descripcion": mov.descripcion,
                "monto": mov.monto,
                "movimiento_id": mov_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        await log_action(
            current_user,
            "/conciliacion/cargar-extracto",
            "POST",
            {
                "banco": banco,
                "fecha": fecha,
                "total": len(movimientos),
                "causados": causados,
                "pendientes": pendientes_count,
            },
        )

        return {
            "causados": causados,
            "pendientes": pendientes_count,
            "total_movimientos": len(movimientos),
            "monto_causado": monto_causado,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cargando extracto: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/pendientes")
async def listar_pendientes(
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    """Lista movimientos pendientes en contabilidad_pendientes."""
    movimientos = await db.contabilidad_pendientes.find(
        {
            "$or": [
                {"estado": "esperando_contexto"},
                {"estado": "pendiente"},
            ]
        },
        {"_id": 0},
    ).sort("monto", -1).to_list(limit)

    return {
        "total": len(movimientos),
        "movimientos": movimientos,
    }


@router.post("/resolver/{movimiento_id}")
async def resolver_movimiento(
    movimiento_id: str,
    req: ResolverMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Resuelve un movimiento ambiguo creando journal en Alegra."""
    try:
        movimiento = await db.contabilidad_pendientes.find_one(
            {"id": movimiento_id},
            {"_id": 0},
        )

        if not movimiento:
            raise HTTPException(status_code=404, detail="Movimiento no encontrado")

        # Crear journal en Alegra
        from alegra_service import AlegraService
        service = AlegraService(db)

        payload = {
            "date": movimiento["fecha"],
            "observations": f"{movimiento['descripcion']} - {req.observacion}",
            "entries": [
                {"id": req.cuenta_debito, "debit": int(movimiento["monto"]), "credit": 0},
                {"id": req.cuenta_credito, "debit": 0, "credit": int(movimiento["monto"])},
            ],
        }

        response = await service.request("journals", "POST", payload)
        if not response or not response.get("id"):
            raise ValueError(f"Alegra error: {response}")

        journal_id = str(response["id"])

        # Actualizar estado
        await db.contabilidad_pendientes.update_one(
            {"id": movimiento_id},
            {
                "$set": {
                    "estado": "resuelto",
                    "journal_id": journal_id,
                    "cuenta_debito_final": req.cuenta_debito,
                    "cuenta_credito_final": req.cuenta_credito,
                    "observacion_usuario": req.observacion,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        # Guardar en agent_memory para aprendizaje
        await db.agent_memory.insert_one({
            "tipo": "clasificacion_aprendida",
            "descripcion": movimiento["descripcion"],
            "cuenta_debito": req.cuenta_debito,
            "cuenta_credito": req.cuenta_credito,
            "banco": movimiento.get("banco", ""),
            "confianza_original": movimiento.get("confianza", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Evento
        await db.roddos_events.insert_one({
            "event_type": "extracto_bancario.resuelto",
            "movimiento_id": movimiento_id,
            "journal_id": journal_id,
            "usuario": current_user,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        await log_action(
            current_user,
            f"/conciliacion/resolver/{movimiento_id}",
            "POST",
            {"journal_id": journal_id},
        )

        return {
            "ok": True,
            "movimiento_id": movimiento_id,
            "journal_id": journal_id,
            "mensaje": f"Movimiento resuelto y journal {journal_id} creado en Alegra",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolviendo movimiento: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/estado/{fecha}")
async def obtener_estado_conciliacion(
    fecha: str,  # YYYY-MM-DD
    current_user=Depends(get_current_user),
):
    """
    Retorna estado de conciliación para una fecha.
    Incluye: % conciliado, totales, journals creados, discrepancias.
    """
    try:
        # Eventos de ese día
        eventos = await db.roddos_events.find(
            {
                "event_type": {"$in": [
                    "extracto_bancario.causado",
                    "extracto_bancario.pendiente",
                    "extracto_bancario.resuelto",
                ]},
                "fecha_movimiento": {"$gte": fecha, "$lt": f"{fecha}T23:59:59"},
            },
            {"_id": 0},
        ).to_list(None)

        causados = len([e for e in eventos if e.get("event_type") == "extracto_bancario.causado"])
        pendientes = len([e for e in eventos if e.get("event_type") == "extracto_bancario.pendiente"])
        resueltos = len([e for e in eventos if e.get("event_type") == "extracto_bancario.resuelto"])

        total = causados + pendientes + resueltos
        monto_causado = sum(e.get("monto", 0) for e in eventos if e.get("event_type") in [
            "extracto_bancario.causado", "extracto_bancario.resuelto"
        ])
        monto_pendiente = sum(e.get("monto", 0) for e in eventos if e.get("event_type") == "extracto_bancario.pendiente")

        porcentaje = (causados + resueltos) / total * 100 if total > 0 else 0

        # Discrepancias: movimientos con errores
        discrepancias = []
        eventos_error = await db.roddos_events.find(
            {"event_type": "extracto_bancario.error", "fecha_movimiento": {"$gte": fecha}},
            {"_id": 0},
        ).to_list(None)

        for evt in eventos_error:
            discrepancias.append({
                "tipo": "error_alegra",
                "descripcion": evt.get("descripcion", "Unknown"),
                "error": evt.get("error_msg", ""),
            })

        return {
            "fecha": fecha,
            "porcentaje_conciliado": round(porcentaje, 2),
            "total_movimientos": total,
            "total_causado": causados + resueltos,
            "total_pendiente": pendientes,
            "monto_causado": monto_causado,
            "monto_pendiente": monto_pendiente,
            "journals_creados": causados + resueltos,
            "movimientos_pendientes": pendientes,
            "discrepancias": discrepancias,
        }

    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
