"""n8n_hooks.py — Capa de integración entre n8n y SISMO.

No contiene lógica de negocio propia — delega a services y routers existentes.
Es la interfaz que convierte SISMO en una autopista orquestable.

Grupos de endpoints:
  GRUPO 1 — Health & Monitoring (sin auth — n8n puede monitorear 24/7)
    GET  /api/n8n/health
    GET  /api/n8n/status/global66
    GET  /api/n8n/status/backlog

  GRUPO 2 — Triggers de agentes (con auth)
    POST /api/n8n/agente/contador
    POST /api/n8n/agente/cfo
    POST /api/n8n/agente/radar
    POST /api/n8n/agente/loanbook

  GRUPO 3 — Triggers de scheduler (con auth)
    POST /api/n8n/scheduler/{job_id}

  GRUPO 4 — Alertas y eventos (con auth)
    POST /api/n8n/evento
    POST /api/n8n/alerta

Autenticación: header X-N8N-Key con valor N8N_API_KEY (variable de entorno).
Si N8N_API_KEY no está configurada → modo desarrollo (sin verificación).
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/n8n", tags=["n8n"])
logger = logging.getLogger(__name__)


# ── Autenticación ─────────────────────────────────────────────────────────────

def _verify_n8n_key(request: Request) -> None:
    """Verifica X-N8N-Key contra N8N_API_KEY. Modo dev si la variable no está."""
    from fastapi import HTTPException
    api_key = os.environ.get("N8N_API_KEY", "")
    if not api_key:
        logger.warning("[N8N] N8N_API_KEY no configurada — modo desarrollo")
        return
    if request.headers.get("X-N8N-Key", "") != api_key:
        raise HTTPException(status_code=401, detail="N8N API key inválida")


# ── Pydantic Models ───────────────────────────────────────────────────────────

class AgenteRequest(BaseModel):
    accion: str
    datos: dict = {}
    session_id: Optional[str] = None
    periodo: Optional[str] = None


class EventoRequest(BaseModel):
    event_type: str
    datos: dict = {}
    source: str = "n8n"


class AlertaRequest(BaseModel):
    tipo: str
    mensaje: str
    severidad: str = "media"  # "alta" | "media" | "baja"


# ── GRUPO 1: HEALTH & MONITORING (sin auth) ───────────────────────────────────

@router.get("/health")
async def n8n_health():
    """Health check ligero para que n8n detecte si SISMO está caído. < 300ms."""
    from database import db
    try:
        loanbooks_activos = await db.loanbook.count_documents({"estado": {"$in": ["activo", "mora"]}})
    except Exception:
        loanbooks_activos = -1

    try:
        backlog_pendientes = await db.contabilidad_pendientes.count_documents(
            {"backlog_hash": {"$exists": True}, "estado": "pendiente"}
        )
    except Exception:
        backlog_pendientes = -1

    try:
        global66_pendientes = await db.global66_eventos_recibidos.count_documents(
            {"procesado": False}
        )
    except Exception:
        global66_pendientes = -1

    try:
        ultimo_evento = await db.global66_eventos_recibidos.find_one(
            {}, sort=[("recibido_at", -1)]
        )
        if ultimo_evento and ultimo_evento.get("recibido_at"):
            ultima_str = ultimo_evento["recibido_at"]
            try:
                ultima_dt = datetime.fromisoformat(ultima_str.replace("Z", "+00:00"))
                diff_horas = (datetime.now(timezone.utc) - ultima_dt).total_seconds() / 3600
            except Exception:
                diff_horas = None
        else:
            diff_horas = None
    except Exception:
        diff_horas = None

    try:
        cfg = await db.alegra_credentials.find_one({}) or {}
        alegra_conectada = bool(cfg.get("token") or cfg.get("api_token"))
    except Exception:
        alegra_conectada = False

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "loanbooks_activos": loanbooks_activos,
        "backlog_pendientes": backlog_pendientes,
        "global66_pendientes": global66_pendientes,
        "global66_ultimo_evento_hace_horas": round(diff_horas, 2) if diff_horas is not None else None,
        "alegra_conectada": alegra_conectada,
        "scheduler_running": True,
    }


@router.get("/status/global66")
async def n8n_status_global66():
    """Estado específico de Global66 para monitoring externo."""
    from database import db
    try:
        hoy_str = datetime.now(timezone.utc).date().isoformat()
        eventos_hoy = await db.global66_eventos_recibidos.count_documents(
            {"recibido_at": {"$regex": f"^{hoy_str}"}}
        )
        procesados_hoy = await db.global66_eventos_recibidos.count_documents(
            {"recibido_at": {"$regex": f"^{hoy_str}"}, "procesado": True}
        )
        pendientes_total = await db.global66_eventos_recibidos.count_documents(
            {"procesado": False}
        )

        ultimo = await db.global66_eventos_recibidos.find_one(
            {}, sort=[("recibido_at", -1)]
        )
        ultimo_at = ultimo.get("recibido_at") if ultimo else None

        alertar = False
        if ultimo_at:
            try:
                ultima_dt = datetime.fromisoformat(ultimo_at.replace("Z", "+00:00"))
                horas_silencio = (datetime.now(timezone.utc) - ultima_dt).total_seconds() / 3600
                alertar = horas_silencio > 24
            except Exception:
                pass
        else:
            alertar = True

        return {
            "eventos_hoy": eventos_hoy,
            "procesados_hoy": procesados_hoy,
            "pendientes_total": pendientes_total,
            "ultimo_evento_at": ultimo_at,
            "alertar": alertar,
        }
    except Exception as e:
        logger.error("[N8N] status/global66 error: %s", e)
        return {"ok": False, "error": str(e)}


@router.get("/status/backlog")
async def n8n_status_backlog():
    """Estado del backlog de movimientos de baja confianza."""
    from database import db
    try:
        base = {"backlog_hash": {"$exists": True}, "estado": "pendiente"}
        total = await db.contabilidad_pendientes.count_documents(base)

        por_banco = {}
        for banco in ["bbva", "bancolombia", "nequi", "global66", "davivienda"]:
            por_banco[banco] = await db.contabilidad_pendientes.count_documents(
                {**base, "banco": banco}
            )

        # Más antiguo
        mas_antiguo = await db.contabilidad_pendientes.find_one(
            base, sort=[("creado_at", 1)]
        )
        mas_antiguo_dias = None
        if mas_antiguo and mas_antiguo.get("creado_at"):
            try:
                dt = datetime.fromisoformat(mas_antiguo["creado_at"].replace("Z", "+00:00"))
                mas_antiguo_dias = round((datetime.now(timezone.utc) - dt).days +
                                         (datetime.now(timezone.utc) - dt).seconds / 86400, 1)
            except Exception:
                pass

        alertar = total > 50 or (mas_antiguo_dias is not None and mas_antiguo_dias > 7)

        return {
            "total": total,
            "por_banco": por_banco,
            "mas_antiguo_hace_dias": mas_antiguo_dias,
            "alertar": alertar,
        }
    except Exception as e:
        logger.error("[N8N] status/backlog error: %s", e)
        return {"ok": False, "error": str(e)}


# ── GRUPO 2: TRIGGERS DE AGENTES (con auth) ───────────────────────────────────

@router.post("/agente/contador")
async def n8n_agente_contador(payload: AgenteRequest, request: Request):
    """Dispara acciones del agente Contador desde n8n."""
    _verify_n8n_key(request)
    from database import db
    accion = payload.accion
    datos = payload.datos

    try:
        result = {}

        if accion == "consultar_backlog":
            estado = datos.get("estado", "pendiente")
            docs = await db.contabilidad_pendientes.find(
                {"backlog_hash": {"$exists": True}, "estado": estado},
                {"_id": 0}
            ).limit(50).to_list(50)
            result = {"items": docs, "total": len(docs)}

        elif accion == "resumen_causaciones":
            hoy = datetime.now(timezone.utc).date().isoformat()
            causados_hoy = await db.contabilidad_pendientes.count_documents(
                {"estado": "causado", "resuelto_at": {"$regex": f"^{hoy}"}}
            )
            pendientes = await db.contabilidad_pendientes.count_documents(
                {"backlog_hash": {"$exists": True}, "estado": "pendiente"}
            )
            result = {
                "causados_hoy": causados_hoy,
                "pendientes_total": pendientes,
                "fecha": hoy,
            }

        elif accion == "consultar_journals":
            result = {"mensaje": "Usar GET /api/alegra/journals directamente", "accion": accion}

        else:
            result = {"mensaje": f"Acción '{accion}' no reconocida en agente contador"}

        await _registrar_evento_n8n(db, "contador", accion, result)
        return {"ok": True, "accion": accion, "resultado": result}

    except Exception as e:
        logger.error("[N8N] agente/contador error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/agente/cfo")
async def n8n_agente_cfo(payload: AgenteRequest, request: Request):
    """Dispara acciones del agente CFO desde n8n."""
    _verify_n8n_key(request)
    from database import db
    accion = payload.accion

    try:
        result = {}

        if accion == "semaforo":
            cache = await db.cfo_cache.find_one({"tipo": "semaforo"}, {"_id": 0}) or {}
            result = cache

        elif accion == "alertas_activas":
            alertas = await db.cfo_alertas.find(
                {"leido": False}, {"_id": 0}
            ).sort("created_at", -1).limit(20).to_list(20)
            result = {"alertas": alertas, "total": len(alertas)}

        elif accion == "resumen_semanal":
            from services.scheduler import _resumen_semanal_cfo
            asyncio.create_task(_resumen_semanal_cfo())
            result = {"mensaje": "Resumen semanal CFO encolado en background"}

        else:
            result = {"mensaje": f"Acción '{accion}' no reconocida en agente CFO"}

        await _registrar_evento_n8n(db, "cfo", accion, result)
        return {"ok": True, "accion": accion, "resultado": result}

    except Exception as e:
        logger.error("[N8N] agente/cfo error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/agente/radar")
async def n8n_agente_radar(payload: AgenteRequest, request: Request):
    """Dispara acciones del agente RADAR desde n8n."""
    _verify_n8n_key(request)
    from database import db
    accion = payload.accion

    try:
        result = {}

        if accion == "cola_cobro":
            cola = await db.radar_queue.find(
                {}, {"_id": 0}
            ).limit(50).to_list(50)
            result = {"cola": cola, "total": len(cola)}

        elif accion == "mora_activa":
            en_mora = await db.loanbook.find(
                {"dpd": {"$gt": 0}, "estado": "activo"}, {"_id": 0, "cliente": 1, "dpd": 1, "bucket": 1}
            ).to_list(100)
            result = {"en_mora": en_mora, "total": len(en_mora)}

        elif accion == "triggerear_recordatorios":
            from services.scheduler import _wa_recordatorios_vencimiento
            asyncio.create_task(_wa_recordatorios_vencimiento())
            result = {"mensaje": "Recordatorios de vencimiento encolados en background"}

        else:
            result = {"mensaje": f"Acción '{accion}' no reconocida en agente RADAR"}

        await _registrar_evento_n8n(db, "radar", accion, result)
        return {"ok": True, "accion": accion, "resultado": result}

    except Exception as e:
        logger.error("[N8N] agente/radar error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/agente/loanbook")
async def n8n_agente_loanbook(payload: AgenteRequest, request: Request):
    """Dispara acciones del agente Loanbook desde n8n."""
    _verify_n8n_key(request)
    from database import db
    accion = payload.accion

    try:
        result = {}

        if accion == "dpd_resumen":
            pipeline = [
                {"$match": {"estado": "activo"}},
                {"$group": {"_id": "$bucket", "count": {"$sum": 1}}},
            ]
            buckets = await db.loanbook.aggregate(pipeline).to_list(20)
            result = {"buckets": buckets}

        elif accion == "scores_resumen":
            pipeline = [
                {"$match": {"estado": "activo"}},
                {"$group": {"_id": "$score", "count": {"$sum": 1}}},
            ]
            scores = await db.loanbook.aggregate(pipeline).to_list(10)
            result = {"scores": scores}

        elif accion == "recalcular_dpd":
            from services.loanbook_scheduler import calcular_dpd_todos
            asyncio.create_task(calcular_dpd_todos())
            result = {"mensaje": "Recálculo DPD encolado en background"}

        else:
            result = {"mensaje": f"Acción '{accion}' no reconocida en agente loanbook"}

        await _registrar_evento_n8n(db, "loanbook", accion, result)
        return {"ok": True, "accion": accion, "resultado": result}

    except Exception as e:
        logger.error("[N8N] agente/loanbook error: %s", e)
        return {"ok": False, "error": str(e)}


# ── GRUPO 3: TRIGGERS DE SCHEDULER (con auth) ─────────────────────────────────

@router.post("/scheduler/{job_id}")
async def n8n_trigger_scheduler(job_id: str, request: Request):
    """Dispara un job del scheduler desde n8n. Mismos job_ids que /api/scheduler/trigger."""
    _verify_n8n_key(request)
    from database import db
    from routers.scheduler import ALLOWED_JOBS

    if job_id not in ALLOWED_JOBS:
        # No lanzar HTTPException — retornar 200 con error para que n8n lo maneje
        return {"ok": False, "error": f"Job '{job_id}' no reconocido", "allowed": ALLOWED_JOBS}

    try:
        from services.loanbook_scheduler import (
            calcular_dpd_todos, alertar_buckets_criticos, verificar_alertas_cfo,
            calcular_scores, generar_cola_radar, recordatorio_preventivo,
            recordatorio_vencimiento, notificar_mora_nueva, resumen_semanal_ceo,
            alertas_predictivas, resolver_outcomes, procesar_patrones,
        )
        _job_map = {
            "calcular_dpd_todos":       calcular_dpd_todos,
            "alertar_buckets_criticos": alertar_buckets_criticos,
            "verificar_alertas_cfo":    verificar_alertas_cfo,
            "calcular_scores":          calcular_scores,
            "generar_cola_radar":       generar_cola_radar,
            "recordatorio_preventivo":  recordatorio_preventivo,
            "recordatorio_vencimiento": recordatorio_vencimiento,
            "notificar_mora_nueva":     notificar_mora_nueva,
            "resumen_semanal_ceo":      resumen_semanal_ceo,
            "alertas_predictivas":      alertas_predictivas,
            "resolver_outcomes":        resolver_outcomes,
            "procesar_patrones":        procesar_patrones,
        }
        asyncio.create_task(_job_map[job_id]())

        triggered_at = datetime.now(timezone.utc).isoformat()
        await db.roddos_events.insert_one({
            "event_id": str(uuid.uuid4()),
            "event_type": "agente_ia.accion.ejecutada",
            "source": "n8n",
            "agent": "scheduler",
            "job_id": job_id,
            "triggered_at": triggered_at,
            "estado": "pending",
        })

        logger.info("[N8N] Scheduler job '%s' triggered", job_id)
        return {"ok": True, "job": job_id, "triggered_at": triggered_at}

    except Exception as e:
        logger.error("[N8N] scheduler trigger error %s: %s", job_id, e)
        return {"ok": False, "error": str(e)}


# ── GRUPO 4: ALERTAS Y EVENTOS (con auth) ─────────────────────────────────────

TIPOS_ALERTA_VALIDOS = {
    "alegra_down", "global66_silencio", "backlog_alto",
    "mora_critica", "cartera_riesgo", "sistema_degradado",
}


@router.post("/evento")
async def n8n_evento(payload: EventoRequest, request: Request):
    """Inserta un evento en el bus de SISMO. Convierte a n8n en publicador."""
    _verify_n8n_key(request)
    from database import db
    try:
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.roddos_events.insert_one({
            "event_id": event_id,
            "event_type": payload.event_type,
            "source": "n8n",
            "datos": payload.datos,
            "created_at": now,
            "estado": "pending",
        })
        logger.info("[N8N] Evento insertado: %s source=%s", payload.event_type, payload.source)
        return {"ok": True, "event_id": event_id}
    except Exception as e:
        logger.error("[N8N] evento error: %s", e)
        return {"ok": False, "error": str(e)}


@router.post("/alerta")
async def n8n_alerta(payload: AlertaRequest, request: Request):
    """Inserta una alerta de n8n en notifications, cfo_alertas y roddos_events."""
    _verify_n8n_key(request)
    from database import db
    try:
        now = datetime.now(timezone.utc).isoformat()

        if payload.tipo not in TIPOS_ALERTA_VALIDOS:
            logger.warning("[N8N] Tipo de alerta desconocido: %s (se acepta igual)", payload.tipo)

        # notifications (frontend)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "type": payload.tipo,
            "event_type": payload.tipo,
            "message": payload.mensaje,
            "severidad": payload.severidad,
            "source": "n8n",
            "read": False,
            "created_at": now,
        })

        # cfo_alertas (agente CFO)
        await db.cfo_alertas.insert_one({
            "tipo": payload.tipo,
            "mensaje": payload.mensaje,
            "severidad": payload.severidad,
            "fuente": "n8n",
            "created_at": now,
            "leido": False,
        })

        # roddos_events (bus)
        await db.roddos_events.insert_one({
            "event_id": str(uuid.uuid4()),
            "event_type": "agente_ia.accion.ejecutada",
            "source": "n8n",
            "tipo_alerta": payload.tipo,
            "mensaje": payload.mensaje,
            "severidad": payload.severidad,
            "created_at": now,
            "estado": "pending",
        })

        logger.info("[N8N] Alerta insertada: tipo=%s severidad=%s", payload.tipo, payload.severidad)
        return {"ok": True}
    except Exception as e:
        logger.error("[N8N] alerta error: %s", e)
        return {"ok": False, "error": str(e)}


# ── Helper ────────────────────────────────────────────────────────────────────

async def _registrar_evento_n8n(db, agente: str, accion: str, resultado: dict) -> None:
    """Registra en roddos_events cada acción ejecutada desde n8n."""
    try:
        await db.roddos_events.insert_one({
            "event_id": str(uuid.uuid4()),
            "event_type": "agente_ia.accion.ejecutada",
            "source": "n8n",
            "agent": agente,
            "accion": accion,
            "resultado_keys": list(resultado.keys()) if isinstance(resultado, dict) else [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "estado": "pending",
        })
    except Exception as e:
        logger.warning("[N8N] No se pudo registrar evento n8n: %s", e)
