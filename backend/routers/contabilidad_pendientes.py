"""contabilidad_pendientes.py — Gestión de movimientos contables ambigua/pendientes.

Endpoints:
  GET  /api/contabilidad_pendientes/listado          — Obtener movimientos pendientes
  GET  /api/contabilidad_pendientes/{movimiento_id}  — Detalles de un movimiento
  POST /api/contabilidad_pendientes/{movimiento_id}/confirmar — Confirmar clasificación
  POST /api/contabilidad_pendientes/{movimiento_id}/resolver — Marcar como resuelto
  POST /api/contabilidad_pendientes/webhook/mercately — Webhook de Mercately (público)
  GET  /api/contabilidad_pendientes/estadisticas     — Resumen de pendientes
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from database import db
from dependencies import get_current_user, log_action
from services.accounting_engine import AmbiguousMovementHandler, EstadoResolucion

router = APIRouter(prefix="/contabilidad_pendientes", tags=["contabilidad_pendientes"])
logger = logging.getLogger(__name__)

handler = AmbiguousMovementHandler(db)


# ── Pydantic Models ────────────────────────────────────────────────────────────

class ConfirmarMovimientoRequest(BaseModel):
    cuenta_debito_final: int
    cuenta_credito_final: Optional[int] = None
    notas: str = ""


class ResolverMovimientoRequest(BaseModel):
    cuenta_debito_final: int
    cuenta_credito_final: Optional[int] = None
    notas: str = ""


class WebhookMercatelyRequest(BaseModel):
    movimiento_id: str
    respuesta_usuario: str
    telefono_usuario: str
    conversation_id: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/listado")
async def listar_pendientes(
    estado: Optional[str] = Query(None),
    limite: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    """Obtiene lista de movimientos pendientes con filtros opcionales."""
    filtro_estado = None
    if estado:
        try:
            filtro_estado = EstadoResolucion[estado.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {estado}")

    movimientos = await handler.obtener_pendientes(estado=filtro_estado)
    movimientos_paginated = movimientos[:limite]

    return {
        "total": len(movimientos),
        "mostrados": len(movimientos_paginated),
        "movimientos": movimientos_paginated,
    }


@router.get("/{movimiento_id}")
async def obtener_movimiento(
    movimiento_id: str,
    current_user=Depends(get_current_user),
):
    """Obtiene detalles completos de un movimiento pendiente."""
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return movimiento


@router.post("/{movimiento_id}/confirmar")
async def confirmar_movimiento(
    movimiento_id: str,
    req: ConfirmarMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Confirma la clasificación de un movimiento (por usuario)."""
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    success = await handler.marcar_resuelto(
        movimiento_id=movimiento_id,
        cuenta_debito_final=req.cuenta_debito_final,
        cuenta_credito_final=req.cuenta_credito_final,
        notas=f"Confirmado manualmente por usuario {current_user}: {req.notas}",
    )

    if not success:
        raise HTTPException(status_code=500, detail="No se pudo marcar como resuelto")

    await log_action(
        current_user,
        f"/contabilidad_pendientes/{movimiento_id}/confirmar",
        "POST",
        {"cuenta_debito": req.cuenta_debito_final, "cuenta_credito": req.cuenta_credito_final},
    )

    return {
        "ok": True,
        "mensaje": f"Movimiento {movimiento_id} confirmado y resuelto",
        "movimiento_id": movimiento_id,
    }


@router.post("/{movimiento_id}/resolver")
async def resolver_movimiento(
    movimiento_id: str,
    req: ResolverMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Marca un movimiento como resuelto después de ser enviado a Alegra."""
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    success = await handler.marcar_resuelto(
        movimiento_id=movimiento_id,
        cuenta_debito_final=req.cuenta_debito_final,
        cuenta_credito_final=req.cuenta_credito_final,
        notas=f"Resuelto por {current_user}: {req.notas}",
    )

    if not success:
        raise HTTPException(status_code=500, detail="No se pudo marcar como resuelto")

    await log_action(
        current_user,
        f"/contabilidad_pendientes/{movimiento_id}/resolver",
        "POST",
        {"cuenta_debito": req.cuenta_debito_final},
    )

    return {
        "ok": True,
        "mensaje": f"Movimiento {movimiento_id} resuelto y enviado a Alegra",
        "movimiento_id": movimiento_id,
    }


@router.post("/webhook/mercately")
async def webhook_mercately(req: WebhookMercatelyRequest):
    """
    Webhook público para recibir respuestas de Mercately WhatsApp.
    No requiere autenticación JWT.
    """
    try:
        success = await handler.procesar_respuesta_whatsapp(
            movimiento_id=req.movimiento_id,
            respuesta_usuario=req.respuesta_usuario,
            telefono_usuario=req.telefono_usuario,
        )

        if not success:
            logger.warning(f"Respuesta no procesada para {req.movimiento_id}: {req.respuesta_usuario}")

        return {
            "ok": True,
            "mensaje": f"Respuesta registrada para {req.movimiento_id}",
            "movimiento_id": req.movimiento_id,
        }

    except Exception as e:
        logger.error(f"Error en webhook Mercately: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando respuesta: {str(e)}")


@router.get("/estadisticas")
async def obtener_estadisticas(current_user=Depends(get_current_user)):
    """Obtiene resumen de movimientos pendientes por estado."""
    todos = await handler.obtener_pendientes()

    estadisticas = {
        "total_pendientes": len(todos),
        "pendiente": len([m for m in todos if m.get("estado") == "pendiente"]),
        "confirmada": len([m for m in todos if m.get("estado") == "confirmada"]),
        "rechazada": len([m for m in todos if m.get("estado") == "rechazada"]),
        "resuelta": len([m for m in todos if m.get("estado") == "resuelta"]),
        "abandonada": len([m for m in todos if m.get("estado") == "abandonada"]),
        "monto_total_pendiente": sum(m.get("monto", 0) for m in todos if m.get("estado") == "pendiente"),
        "dias_promedio_pendencia": _calcular_dias_promedio(todos),
    }

    return estadisticas


# ══════════════════════════════════════════════════════════════════════════════
# BACKLOG DE MOVIMIENTOS — Nuevos endpoints (prefijo /backlog/)
# Para movimientos de baja confianza del motor matricial
# ══════════════════════════════════════════════════════════════════════════════

class BacklogMovimientoRequest(BaseModel):
    banco: str                              # "bbva" | "bancolombia" | "nequi" | "davivienda"
    extracto: str                           # "bbva_enero_2026"
    fecha: str                              # "2026-01-15"
    descripcion: str
    monto: float                            # negativo=egreso, positivo=ingreso
    tipo: str                               # "EGRESO" | "INGRESO"
    confianza_motor: float = 0.0
    cuenta_sugerida: Optional[int] = None
    razon_baja_confianza: str = ""


class CausarMovimientoRequest(BaseModel):
    cuenta_debito: int
    cuenta_credito: int
    observaciones: str = ""


class DescartarMovimientoRequest(BaseModel):
    razon: str


@router.post("/backlog/crear")
async def backlog_crear(
    payload: BacklogMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Crea movimiento en backlog con anti-dup por hash(banco+fecha+descripcion+monto)."""
    dup_key = f"{payload.banco}|{payload.fecha}|{payload.descripcion}|{payload.monto}"
    dup_hash = hashlib.md5(dup_key.encode()).hexdigest()

    existing = await db.contabilidad_pendientes.find_one({"backlog_hash": dup_hash})
    if existing:
        raise HTTPException(status_code=409, detail="Movimiento ya existe en backlog (anti-dup)")

    doc = {
        "backlog_hash": dup_hash,
        "banco": payload.banco,
        "extracto": payload.extracto,
        "fecha": payload.fecha,
        "descripcion": payload.descripcion,
        "monto": payload.monto,
        "tipo": payload.tipo,
        "confianza_motor": payload.confianza_motor,
        "cuenta_sugerida": payload.cuenta_sugerida,
        "razon_baja_confianza": payload.razon_baja_confianza,
        "estado": "pendiente",
        "journal_alegra_id": None,
        "resuelto_por": None,
        "creado_at": datetime.now(timezone.utc).isoformat(),
        "resuelto_at": None,
    }
    result = await db.contabilidad_pendientes.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.get("/backlog/listado")
async def backlog_listado(
    banco: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),   # YYYY-MM
    estado: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
):
    """Lista movimientos de backlog con filtros: banco, mes, estado. Paginación 20/página."""
    query: dict = {"backlog_hash": {"$exists": True}}
    if banco:
        query["banco"] = banco.lower()
    if estado:
        query["estado"] = estado
    if mes:
        query["fecha"] = {"$regex": f"^{mes}"}

    skip = (page - 1) * 20
    docs = await db.contabilidad_pendientes.find(
        query, {"_id": 0}
    ).skip(skip).limit(20).to_list(20)

    total = await db.contabilidad_pendientes.count_documents(query)
    return {"total": total, "page": page, "items": docs}


@router.patch("/backlog/{id}/causar")
async def backlog_causar(
    id: str,
    payload: CausarMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Crea journal en Alegra y marca movimiento como causado.

    Acepta tanto ObjectId de MongoDB como backlog_hash (MD5) para máxima compatibilidad
    con el frontend que puede enviar cualquiera de los dos según lo que tenga disponible.
    """
    from bson import ObjectId
    from services.alegra_service import AlegraService

    # Buscar por ObjectId o por backlog_hash (el frontend envía backlog_hash cuando no tiene _id)
    mov = None
    try:
        oid = ObjectId(id)
        mov = await db.contabilidad_pendientes.find_one({"_id": oid})
    except Exception:
        pass

    if not mov:
        # Intentar por backlog_hash
        mov = await db.contabilidad_pendientes.find_one({"backlog_hash": id})

    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mov.get("estado") != "pendiente":
        raise HTTPException(status_code=400, detail=f"Movimiento en estado '{mov.get('estado')}', no se puede causar")

    service = AlegraService(db)
    monto = abs(mov.get("monto", 0))
    journal_payload = {
        "date": mov.get("fecha", datetime.now(timezone.utc).isoformat()[:10]),
        "observations": payload.observaciones or mov.get("descripcion", ""),
        "entries": [
            {"id": payload.cuenta_debito, "debit": monto, "credit": 0},
            {"id": payload.cuenta_credito, "debit": 0, "credit": monto},
        ],
    }

    try:
        logger.info(f"[backlog_causar] Iniciando causación de movimiento {id}")
        logger.info(f"[backlog_causar] Payload: {journal_payload}")
        
        # ROG-1: POST a Alegra + GET verificación (request_with_verify())
        result = await service.request_with_verify("journals", "POST", journal_payload)
        logger.info(f"[backlog_causar] request_with_verify retornó: {result}")
        
    except Exception as e:
        logger.error(f"[backlog_causar] ERROR en AlegraService.request_with_verify para {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creando journal en Alegra: {str(e)}")

    # Extraer journal_id del resultado
    journal_id = result.get("id") if isinstance(result, dict) else None
    if not journal_id:
        logger.error(f"[backlog_causar] AlegraService.request_with_verify no retornó ID para {id}")
        raise HTTPException(status_code=500, detail="Alegra no retornó ID del journal creado")

    await db.contabilidad_pendientes.update_one(
        {"_id": mov["_id"]},
        {"$set": {
            "estado": "causado",
            "journal_alegra_id": str(journal_id),
            "resuelto_por": current_user.get("email", ""),
            "resuelto_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"success": True, "journal_alegra_id": str(journal_id), "estado": "causado"}


@router.patch("/backlog/{id}/descartar")
async def backlog_descartar(
    id: str,
    payload: DescartarMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Marca movimiento como descartado.

    Acepta tanto ObjectId de MongoDB como backlog_hash (MD5) para máxima compatibilidad.
    El frontend envía backlog_hash cuando el campo _id no está disponible en el item.
    """
    from bson import ObjectId

    # Buscar por ObjectId o por backlog_hash
    mov = None
    try:
        oid = ObjectId(id)
        mov = await db.contabilidad_pendientes.find_one({"_id": oid})
    except Exception:
        pass

    if not mov:
        mov = await db.contabilidad_pendientes.find_one({"backlog_hash": id})

    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    await db.contabilidad_pendientes.update_one(
        {"_id": mov["_id"]},  # Usar el _id real del documento encontrado
        {"$set": {
            "estado": "descartado",
            "razon_descarte": payload.razon,
            "resuelto_por": current_user.get("email", ""),
            "resuelto_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"success": True, "estado": "descartado"}


# Mapa de cuentas RODDOS — IDs verificados contra Alegra (plan_cuentas_roddos + accounting_engine.py)
# FUENTE DE VERDAD: plan_cuentas_roddos MongoDB + CUENTAS_ACTIVOS en accounting_engine.py
# NUNCA inventar IDs — cada uno fue validado contra Alegra real
CUENTAS_RODDOS: dict[int, str] = {
    # ── Personal (cod. PUC 510x / 511x) ──────────────────────────────────────
    5462: "Sueldos y salarios (510506)",
    5466: "Cesantías (510530)",
    5468: "Prima de servicios (510536)",
    5469: "Vacaciones (510539)",
    5470: "Dotación a trabajadores (510551)",
    5472: "Aportes seguridad social (510570)",
    5475: "Honorarios persona natural (511025)",
    5476: "Honorarios persona jurídica (511030)",
    # ── Operaciones (cod. PUC 512x / 513x / 519x) ────────────────────────────
    5480: "Arrendamientos (512010)",
    5482: "Aseo y vigilancia (513505)",
    5483: "Asistencia técnica / Mantenimiento (513515)",
    5485: "Servicios públicos / Acueducto (513525)",
    5487: "Teléfono / Internet / Comunicaciones (513535)",
    5497: "Útiles, papelería y fotocopia (519530)",
    5498: "Combustibles y lubricantes (519535)",
    5499: "Taxis y buses / Transporte (519545)",
    # ── Impuestos y representación (cod. PUC 511x / 519x) ────────────────────
    5478: "Industria y Comercio — ICA (511505)",
    5495: "Gastos de representación / Publicidad (519520)",
    # ── Financiero (cod. PUC 530x / 531x / 615x) ─────────────────────────────
    5507: "Gastos bancarios (530505)",
    5508: "Comisiones bancarias (530515)",
    5509: "Gravamen al movimiento financiero — GMF 4×1000 (531520)",
    5533: "Intereses créditos directos (615020)",
    # ── Gastos generales / Otros ──────────────────────────────────────────────
    5493: "Gastos generales (5195)",
    5501: "Depreciación (5160)",
    # ── Cuentas bancarias — Activos (cod. PUC 111x) ───────────────────────────
    5310: "Caja general / Nequi",
    5311: "Caja Menor RODDOS (cód.PUC 11050502)",
    5314: "Bancolombia 2029",
    5315: "Bancolombia 2540",
    5318: "BBVA 0210",
    5319: "BBVA 0212",
    5321: "Banco de Bogotá 047674460",
    5322: "Davivienda 482",
    11100507: "Global66 Colombia",
    # ── CXC y cartera (cod. PUC 1305x / 1406x) ───────────────────────────────
    5326: "CXC Clientes nacionales",
    5327: "Créditos Directos RODDOS — cartera",
    5329: "CXC Socios y accionistas",
    5331: "Anticipos a proveedores",
    5332: "Anticipos a empleados",
    # ── Retenciones por pagar (pasivo) ───────────────────────────────────────
    236505: "ReteFuente por pagar",
    236560: "ReteICA por pagar",
}

BANCO_CUENTA: dict[str, int] = {
    "bbva": 5318,
    "bancolombia": 5314,
    "davivienda": 5322,
    "nequi": 5310,
    "global66": 11100507,
    "caja_menor": 5311,
}


def _nombre_cuenta(cuenta_id: Optional[int]) -> str:
    if not cuenta_id:
        return "Cuenta desconocida"
    return CUENTAS_RODDOS.get(int(cuenta_id), f"Cuenta {cuenta_id}")


def _generar_sugerencias(mov: dict) -> list[dict]:
    """
    Genera 3 sugerencias de asiento para un movimiento del backlog.
    Usa los campos del motor matricial + reglas de negocio RODDOS.
    """
    banco = mov.get("banco", "bbva")
    tipo = (mov.get("tipo") or "EGRESO").upper()
    descripcion = (mov.get("descripcion") or "").upper()
    monto = abs(mov.get("monto", 0))
    cuenta_banco = BANCO_CUENTA.get(banco, 5318)
    cuenta_debito_motor = mov.get("cuenta_debito_sugerida")
    cuenta_credito_motor = mov.get("cuenta_credito_sugerida")
    es_traslado = mov.get("es_transferencia_interna", False)

    obs_base = f"{descripcion[:60]} ({banco.upper()})"

    sugerencias = []

    # ── Traslado interno ───────────────────────────────────────────────
    if es_traslado:
        return [{
            "id": 1,
            "titulo": "Traslado interno — no contabilizar",
            "cuenta_debito": cuenta_banco,
            "cuenta_debito_nombre": _nombre_cuenta(cuenta_banco),
            "cuenta_credito": cuenta_banco,
            "cuenta_credito_nombre": _nombre_cuenta(cuenta_banco),
            "observaciones": f"Traslado interno RODDOS — {obs_base}",
            "razon": "Movimiento entre cuentas propias — usar Descartar en su lugar",
            "es_traslado": True,
        }]

    # ── Sugerencia 1: La del motor matricial ──────────────────────────
    if tipo == "EGRESO":
        d1 = int(cuenta_debito_motor) if cuenta_debito_motor else 5493
        c1 = cuenta_banco
        r1 = mov.get("razon_baja_confianza") or f"Clasificación del motor — {_nombre_cuenta(d1)}"
    else:
        d1 = cuenta_banco
        c1 = int(cuenta_credito_motor) if cuenta_credito_motor else 5327
        r1 = mov.get("razon_baja_confianza") or f"Clasificación del motor — {_nombre_cuenta(c1)}"

    sugerencias.append({
        "id": 1,
        "titulo": "Sugerencia del motor" if (cuenta_debito_motor or cuenta_credito_motor) else "Gastos generales",
        "cuenta_debito": d1,
        "cuenta_debito_nombre": _nombre_cuenta(d1),
        "cuenta_credito": c1,
        "cuenta_credito_nombre": _nombre_cuenta(c1),
        "observaciones": obs_base,
        "razon": r1,
        "es_traslado": False,
    })

    # ── Sugerencia 2: Alternativa por palabras clave ──────────────────
    d2, c2, titulo2, razon2 = None, None, "", ""

    if tipo == "EGRESO":
        if any(k in descripcion for k in ["NOMINA", "SALARY", "SUELDO"]):
            d2, c2 = 5462, cuenta_banco
            titulo2, razon2 = "Nómina y salarios", "Detectado: pago de nómina"
        elif any(k in descripcion for k in ["HONORARIO", "ABOGADO", "ASESOR", "CONSUL"]):
            d2, c2 = 5475, cuenta_banco  # Honorarios PN (511025) — no 5470 que es Dotación
            titulo2, razon2 = "Honorarios persona natural", "Detectado: pago de honorarios"
        elif any(k in descripcion for k in ["ARRIENDO", "ARRENDAMIENTO", "CANON"]):
            d2, c2 = 5480, cuenta_banco
            titulo2, razon2 = "Arrendamiento", "Detectado: pago de arriendo"
        elif any(k in descripcion for k in ["ALEGRA", "SOFIA", "SOFTWARE", "INTERNET", "TIGO", "CLARO", "ETB"]):
            d2, c2 = 5487, cuenta_banco  # Teléfono/Internet (513535) — no 5484 que no existe
            titulo2, razon2 = "Teléfono / Internet / Tech", "Detectado: servicio tecnológico o internet"
        elif any(k in descripcion for k in ["COMISION", "COMISIÓN"]):
            d2, c2 = 5508, cuenta_banco
            titulo2, razon2 = "Comisión bancaria", "Detectado: comisión bancaria"
        elif any(k in descripcion for k in ["IMPUESTO", "4X1000", "GMF"]):
            d2, c2 = 5509, cuenta_banco
            titulo2, razon2 = "GMF 4×1000", "Detectado: gravamen al movimiento financiero"
        elif any(k in descripcion for k in ["CXC SOCIO", "RETIRO SOCIO", "GASTO PERSONAL", "ANTICIPO SOCIO", "ENVIO A ANDRES", "ENVIO A IVAN", "COMPRA ANDRES", "PAGO LIZBETH"]):
            d2, c2 = 5329, cuenta_banco
            titulo2, razon2 = "CXC Socios", "Detectado: gasto de socio"
        elif any(k in descripcion for k in ["INTERESES", "CANO", "MARTINEZ", "CREDITO"]):
            d2, c2 = 5533, cuenta_banco  # Intereses créditos directos (615020) — no 5534 que no existe
            titulo2, razon2 = "Intereses", "Detectado: pago de intereses"
        else:
            d2, c2 = 5493, cuenta_banco
            titulo2, razon2 = "Gastos generales", "Sin clasificación específica — cuenta comodín"
    else:  # INGRESO
        if any(k in descripcion for k in ["RDX", "LOANBOOK", "CUOTA", "ABONO"]):
            d2, c2 = cuenta_banco, 5327
            titulo2, razon2 = "Ingreso cartera RDX", "Detectado: pago de cuota de crédito"
        elif any(k in descripcion for k in ["MOTOS DEL TROPICO", "RECUPERADA", "TROPICO"]):
            d2, c2 = cuenta_banco, 5327
            titulo2, razon2 = "Ingreso no operacional", "Detectado: venta de moto recuperada"
        elif any(k in descripcion for k in ["INTERESES", "GANADOS"]):
            d2, c2 = cuenta_banco, 5533
            titulo2, razon2 = "Intereses bancarios ganados", "Detectado: rendimientos bancarios"
        else:
            d2, c2 = cuenta_banco, 5327
            titulo2, razon2 = "Ingreso cartera", "Ingreso en cuenta bancaria"

    if d2 and c2 and (d2, c2) != (d1, c1):  # Solo agregar si es diferente a la primera
        sugerencias.append({
            "id": 2,
            "titulo": titulo2,
            "cuenta_debito": d2,
            "cuenta_debito_nombre": _nombre_cuenta(d2),
            "cuenta_credito": c2,
            "cuenta_credito_nombre": _nombre_cuenta(c2),
            "observaciones": obs_base,
            "razon": razon2,
            "es_traslado": False,
        })

    # ── Sugerencia 3: Fallback / comodín ──────────────────────────────
    d3 = 5493 if tipo == "EGRESO" else cuenta_banco
    c3 = cuenta_banco if tipo == "EGRESO" else 5327
    fallback = (d3, c3)
    if fallback != (d1, c1) and fallback != (d2, c2 if d2 else None):
        sugerencias.append({
            "id": 3,
            "titulo": "Gastos generales" if tipo == "EGRESO" else "Ingreso genérico",
            "cuenta_debito": d3,
            "cuenta_debito_nombre": _nombre_cuenta(d3),
            "cuenta_credito": c3,
            "cuenta_credito_nombre": _nombre_cuenta(c3),
            "observaciones": obs_base,
            "razon": "Cuenta comodín para clasificar y revisar después",
            "es_traslado": False,
        })

    return sugerencias[:3]


@router.get("/backlog/sugerencias/{id}")
async def backlog_sugerencias(
    id: str,
    current_user=Depends(get_current_user),
):
    """Retorna 3 sugerencias de asiento para un movimiento de backlog.

    Acepta tanto ObjectId como backlog_hash.
    """
    from bson import ObjectId

    mov = None
    try:
        oid = ObjectId(id)
        mov = await db.contabilidad_pendientes.find_one({"_id": oid})
    except Exception:
        pass

    if not mov:
        mov = await db.contabilidad_pendientes.find_one({"backlog_hash": id})

    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    sugerencias = _generar_sugerencias(mov)
    return {
        "movimiento_id": id,
        "descripcion": mov.get("descripcion", ""),
        "monto": mov.get("monto", 0),
        "tipo": mov.get("tipo", "EGRESO"),
        "es_transferencia_interna": mov.get("es_transferencia_interna", False),
        "sugerencias": sugerencias,
    }


@router.get("/backlog/stats")
async def backlog_stats(current_user=Depends(get_current_user)):
    """Retorna totales por estado y por banco."""
    # Incluye tanto documentos nuevos (backlog_hash) como schema viejo (pendiente_whatsapp)
    base_query = {"$or": [
        {"backlog_hash": {"$exists": True}},
        {"estado": "pendiente_whatsapp"},
    ]}

    total_pendientes = await db.contabilidad_pendientes.count_documents(
        {**{"$or": base_query["$or"]}, "estado": {"$in": ["pendiente", "pendiente_whatsapp"]}}
    )
    total_causados = await db.contabilidad_pendientes.count_documents(
        {**{"$or": base_query["$or"]}, "estado": "causado"}
    )
    total_descartados = await db.contabilidad_pendientes.count_documents(
        {**{"$or": base_query["$or"]}, "estado": "descartado"}
    )

    por_banco: dict = {}
    for banco in ["bbva", "bancolombia", "nequi", "davivienda"]:
        por_banco[banco] = await db.contabilidad_pendientes.count_documents(
            {"banco": banco, "estado": {"$in": ["pendiente", "pendiente_whatsapp"]}}
        )

    return {
        "total_pendientes": total_pendientes,
        "total_causados": total_causados,
        "total_descartados": total_descartados,
        "por_banco": por_banco,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _calcular_dias_promedio(movimientos: list) -> float:
    """Calcula días promedio de pendencia para movimientos aún sin resolver."""
    pendientes = [
        m for m in movimientos
        if m.get("estado") in ["pendiente", "confirmada", "rechazada"]
    ]

    if not pendientes:
        return 0.0

    ahora = datetime.now(timezone.utc)
    dias_totales = 0

    for m in pendientes:
        fecha_creacion_str = m.get("fecha_creacion")
        if fecha_creacion_str:
            try:
                fecha_creacion = datetime.fromisoformat(fecha_creacion_str)
                dias = (ahora - fecha_creacion).days
                dias_totales += dias
            except (ValueError, TypeError):
                continue

    return dias_totales / len(pendientes) if pendientes else 0.0
