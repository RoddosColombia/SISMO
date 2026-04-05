"""radar.py — RODDOS RADAR: cobranza, cola de gestión, salud de cartera."""
import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends

from database import db
from dependencies import get_current_user
from services.shared_state import get_portfolio_health, get_daily_collection_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/radar", tags=["radar"])


@router.get("/portfolio-health")
async def portfolio_health(current_user=Depends(get_current_user)):
    """KPIs de salud de cartera desde shared_state (caché TTL 30 s)."""
    return await get_portfolio_health(db)


@router.get("/queue")
async def collection_queue(current_user=Depends(get_current_user)):
    """Cola de cobro del día (< 200 ms, desde caché).
    Cada ítem incluye: bucket, dpd_actual, total_a_pagar, dias_para_protocolo, whatsapp_link.
    """
    return await get_daily_collection_queue(db)


@router.get("/semana")
async def semana_stats(current_user=Depends(get_current_user)):
    """Cuotas esperadas esta semana vs pagadas vs pendientes + nuevas moras."""
    hoy      = date.today()
    lunes    = hoy - timedelta(days=hoy.weekday())
    domingo  = lunes + timedelta(days=6)
    lunes_s  = lunes.isoformat()
    domingo_s = domingo.isoformat()

    # Reference point: 7 days ago (to detect new moras)
    hace7 = (hoy - timedelta(days=7)).isoformat()

    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora", "completado"]}},
        {"_id": 0, "cuotas": 1, "codigo": 1, "cliente_nombre": 1, "created_at": 1},
    ).to_list(5000)

    esperadas: list[dict] = []
    pagadas:   list[dict] = []
    pendientes: list[dict] = []
    nuevas_moras = 0

    for loan in loans:
        tiene_mora_nueva = False
        for cuota in loan.get("cuotas", []):
            fv = cuota.get("fecha_vencimiento", "")
            if lunes_s <= fv <= domingo_s:
                item: dict = {
                    "codigo":            loan["codigo"],
                    "cliente_nombre":    loan.get("cliente_nombre", ""),
                    "cuota_numero":      cuota.get("numero"),
                    "fecha_vencimiento": fv,
                    "valor":             cuota.get("valor", 0),
                    "estado":            cuota.get("estado"),
                }
                esperadas.append(item)
                if cuota.get("estado") == "pagada":
                    pagadas.append(item)
                elif cuota.get("estado") == "vencida" and not tiene_mora_nueva:
                    nuevas_moras += 1
                    tiene_mora_nueva = True
                else:
                    pendientes.append(item)

    valor_esperado = sum(i["valor"] for i in esperadas)
    valor_cobrado  = sum(i["valor"] for i in pagadas)
    pct_cobranza   = round(valor_cobrado / valor_esperado * 100, 1) if valor_esperado > 0 else 0.0

    return {
        "semana_inicio":  lunes_s,
        "semana_fin":     domingo_s,
        "esperadas":      len(esperadas),
        "pagadas":        len(pagadas),
        "pendientes":     len(pendientes),
        "nuevas_moras":   nuevas_moras,
        "valor_esperado": valor_esperado,
        "valor_cobrado":  valor_cobrado,
        "pct_cobranza":   pct_cobranza,
        "detalle_pendiente": sorted(pendientes, key=lambda x: x["fecha_vencimiento"]),
    }


# ── Deprecated alias — remove in 30 days ─────────────────────────────────────

@router.get("/cola-remota")
async def cola_remota_deprecated(current_user=Depends(get_current_user)):
    """DEPRECATED — alias for /queue. Will be removed in 30 days. Use /queue instead."""
    return await collection_queue(current_user)


@router.get("/roll-rate")
async def roll_rate(current_user=Depends(get_current_user)):
    """% loanbooks que cambiaron a bucket peor en los últimos 7 días.
    Retorna 0 % (data_disponible=False) si no hay eventos suficientes.
    """
    BUCKET_ORDER = {"0": 0, "1-7": 1, "8-14": 2, "15-21": 3, "22+": 4}

    hace_7_dias = (date.today() - timedelta(days=7)).isoformat()

    eventos = await db.roddos_events.find(
        {
            "event_type": "loanbook.bucket_change",
            "timestamp":  {"$gte": hace_7_dias},
        },
        {"_id": 0, "entity_id": 1, "new_state": 1, "metadata": 1, "timestamp": 1},
    ).sort("timestamp", -1).to_list(2000)

    if not eventos:
        return {
            "roll_rate_pct":    0.0,
            "data_disponible":  False,
            "mensaje":          "Sin datos suficientes. Disponible tras 7 días de operación.",
            "total_changes":    0,
            "empeorados":       0,
            "mejorados":        0,
        }

    # Tomar el cambio más reciente por loanbook_id
    latest: dict = {}
    for evt in eventos:
        eid = evt.get("entity_id", "")
        if eid not in latest:
            latest[eid] = evt

    worsened = improved = 0
    for evt in latest.values():
        new_b  = evt.get("new_state", "0")
        prev_b = (evt.get("metadata") or {}).get("prev_bucket", "0")
        new_o  = BUCKET_ORDER.get(new_b, 0)
        prev_o = BUCKET_ORDER.get(prev_b, 0)
        if new_o > prev_o:
            worsened += 1
        elif new_o < prev_o:
            improved += 1

    total     = len(latest)
    roll_rate = round(worsened / total * 100, 1) if total > 0 else 0.0

    return {
        "roll_rate_pct":          roll_rate,
        "data_disponible":        True,
        "total_loans_con_cambio": total,
        "empeorados":             worsened,
        "mejorados":              improved,
        "periodo_dias":           7,
    }


# ── FASE 8-A: Diagnóstico + Arranque ─────────────────────────────────────────

@router.get("/diagnostico")
async def diagnostico(current_user=Depends(get_current_user)):
    """Estado de salud del CRM: loanbooks con DPD, score_roddos y etapa_cobro calculados.

    También reporta configuración de Mercately y último run de cada scheduler job.
    """
    try:
        total_activos = await db.loanbook.count_documents({"estado": {"$in": ["activo", "mora"]}})

        loanbooks_con_dpd = await db.loanbook.count_documents(
            {"estado": {"$in": ["activo", "mora"]}, "dpd_actual": {"$exists": True}}
        )
        loanbooks_con_score = await db.loanbook.count_documents(
            {"estado": {"$in": ["activo", "mora"]}, "score_roddos": {"$exists": True}}
        )
        loanbooks_con_etapa = await db.loanbook.count_documents(
            {"estado": {"$in": ["activo", "mora"]}, "etapa_cobro": {"$exists": True}}
        )

        # Estado Mercately
        mercately_cfg = await db.mercately_config.find_one({}, {"_id": 0, "api_key": 1}) or {}
        mercately_configurado = bool(mercately_cfg.get("api_key"))

        # Último run de cada job desde roddos_events
        JOBS_INTERES = ["calcular_dpd_todos", "calcular_scores", "generar_cola_radar"]
        ultimo_run_jobs: dict = {}
        for job_name in JOBS_INTERES:
            evento = await db.roddos_events.find_one(
                {"event_type": "scheduler.job_run", "metadata.job": job_name},
                {"_id": 0, "timestamp": 1, "metadata": 1},
                sort=[("timestamp", -1)],
            )
            if evento:
                ultimo_run_jobs[job_name] = evento.get("timestamp")
            else:
                # Fallback: buscar por source=scheduler en events de wa.sent
                evento_alt = await db.roddos_events.find_one(
                    {"source": "scheduler", "metadata.job": job_name},
                    {"_id": 0, "timestamp": 1},
                    sort=[("timestamp", -1)],
                )
                ultimo_run_jobs[job_name] = (evento_alt or {}).get("timestamp")

        return {
            "total_loanbooks_activos": total_activos,
            "loanbooks_con_dpd": loanbooks_con_dpd,
            "loanbooks_con_score_roddos": loanbooks_con_score,
            "loanbooks_con_etapa_cobro": loanbooks_con_etapa,
            "mercately_configurado": mercately_configurado,
            "ultimo_run_jobs": ultimo_run_jobs,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("[RADAR] diagnostico error: %s", e)
        return {
            "error": str(e),
            "total_loanbooks_activos": 0,
            "loanbooks_con_dpd": 0,
            "loanbooks_con_score_roddos": 0,
            "loanbooks_con_etapa_cobro": 0,
            "mercately_configurado": False,
            "ultimo_run_jobs": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/arranque")
async def arranque(background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    """Dispara manualmente los 3 scheduler jobs FASE 8-A via BackgroundTasks.

    No espera a las 06:00 AM. Útil para inicializar datos o forzar recálculo.
    Retorna job_id para tracking.
    """
    from services.loanbook_scheduler import calcular_dpd_todos, calcular_scores, generar_cola_radar

    job_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    background_tasks.add_task(calcular_dpd_todos)
    background_tasks.add_task(calcular_scores)
    background_tasks.add_task(generar_cola_radar)

    logger.info("[RADAR] arranque manual. job_id=%s actor=%s", job_id, current_user.get("email"))

    return {
        "job_id": job_id,
        "status": "dispatched",
        "jobs": ["calcular_dpd_todos", "calcular_scores", "generar_cola_radar"],
        "dispatched_at": now_iso,
        "nota": "Los jobs corren en background. Usa GET /api/radar/diagnostico para verificar el resultado.",
    }
