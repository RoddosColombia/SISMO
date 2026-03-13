"""loanbook_scheduler.py — CRON jobs diarios para DPD, scores y resumen semanal.

Jobs (timezone=America/Bogota):
  06:00 AM diario  → calcular_dpd_todos()    — DPD + bucket + interés mora
  06:30 AM diario  → calcular_scores()        — score A+..E + estrellas
  07:00 AM diario  → generar_cola_radar()     — warm-up caché cola RADAR
  Viernes 17:00    → resumen_semanal()        — log cobrado vs esperado (WhatsApp CEO: BUILD 5)
"""
import logging
from datetime import datetime, timezone, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# Tasa mora: 15% EA. Tasa diaria = (1.15)**(1/365) − 1
TASA_MORA_DIARIA: float = (1.15 ** (1 / 365)) - 1  # ≈ 0.00038426

_loanbook_scheduler = AsyncIOScheduler(timezone="America/Bogota")


def _get_bucket(dpd: int) -> str:
    if dpd == 0:    return "0"
    if dpd <= 7:    return "1-7"
    if dpd <= 14:   return "8-14"
    if dpd <= 21:   return "15-21"
    return "22+"


# ─── CRON 1: 06:00 AM — DPD ──────────────────────────────────────────────────

async def calcular_dpd_todos() -> None:
    """Calcula DPD, bucket e interés mora 15%EA para todos los loanbooks activo/mora."""
    from database import db
    from services.shared_state import emit_state_change

    try:
        hoy     = date.today()
        hoy_str = hoy.isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "id": 1, "codigo": 1, "cuotas": 1, "estado": 1,
             "dpd_actual": 1, "dpd_bucket": 1, "dpd_maximo_historico": 1},
        ).to_list(5000)

        updated = 0
        for loan in loans:
            loan_id = loan["id"]
            cuotas  = loan.get("cuotas", [])

            cuotas_vencidas = [
                c for c in cuotas
                if c.get("fecha_vencimiento", "") < hoy_str
                and c.get("estado") != "pagada"
                and c.get("fecha_vencimiento")
            ]

            if not cuotas_vencidas:
                dpd_actual   = 0
                bucket       = "0"
                interes_mora = 0.0
            else:
                oldest_fv  = min(c["fecha_vencimiento"] for c in cuotas_vencidas)
                dpd_actual = (hoy - date.fromisoformat(oldest_fv)).days
                bucket     = _get_bucket(dpd_actual)
                interes_mora = sum(
                    c.get("valor", 0) * ((1 + TASA_MORA_DIARIA) ** dpd_actual - 1)
                    for c in cuotas_vencidas
                )

            prev_bucket  = loan.get("dpd_bucket", "0")
            prev_dpd_max = loan.get("dpd_maximo_historico", 0)
            nuevo_dpd_max = max(prev_dpd_max, dpd_actual)

            # ── Transición de estado ──────────────────────────────────────────
            estado_actual = loan["estado"]
            if dpd_actual >= 1 and estado_actual == "activo":
                nuevo_estado = "mora"
            elif dpd_actual == 0 and estado_actual == "mora":
                nuevo_estado = "activo"
            else:
                nuevo_estado = estado_actual

            update_fields: dict = {
                "dpd_actual":             dpd_actual,
                "dpd_bucket":             bucket,
                "dpd_maximo_historico":   nuevo_dpd_max,
                "interes_mora_acumulado": round(interes_mora, 2),
                "updated_at":             now_iso,
            }
            if nuevo_estado != estado_actual:
                update_fields["estado"] = nuevo_estado

            await db.loanbook.update_one({"id": loan_id}, {"$set": update_fields})

            # ── Eventos ───────────────────────────────────────────────────────
            if bucket != prev_bucket:
                await emit_state_change(
                    db, "loanbook.bucket_change", loan_id, bucket, "scheduler",
                    {"prev_bucket": prev_bucket, "dpd_actual": dpd_actual,
                     "codigo": loan["codigo"]},
                )

            if dpd_actual >= 22 and estado_actual not in ("recuperacion",):
                await emit_state_change(
                    db, "protocolo_recuperacion", loan_id, "recuperacion", "scheduler",
                    {"dpd_actual": dpd_actual, "codigo": loan["codigo"]},
                )

            updated += 1

        logger.info("[LoanScheduler] calcular_dpd_todos: %d loans procesados", updated)

    except Exception as e:
        logger.error("[LoanScheduler] calcular_dpd_todos error: %s", e)


# ─── CRON 2: 06:30 AM — Scores ────────────────────────────────────────────────

async def calcular_scores() -> None:
    """Calcula score A+..E y estrella_nivel, append a score_historial."""
    from database import db

    try:
        today_str = date.today().isoformat()
        now_iso   = datetime.now(timezone.utc).isoformat()

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "id": 1, "dpd_actual": 1, "dpd_maximo_historico": 1,
             "cuotas": 1, "gestiones": 1},
        ).to_list(5000)

        updated = 0
        for loan in loans:
            loan_id  = loan["id"]
            dpd      = loan.get("dpd_actual", 0)
            dpd_max  = loan.get("dpd_maximo_historico", 0)
            cuotas   = loan.get("cuotas", [])
            gestiones = loan.get("gestiones", [])

            # historial_vencidas: pagadas con dpd_al_pagar > 0 (tardaron en pagar)
            historial_vencidas = [
                c for c in cuotas
                if c.get("estado") == "pagada" and (c.get("dpd_al_pagar") or 0) > 0
            ]

            total_g           = max(len(gestiones), 1)
            no_contesto       = sum(1 for g in gestiones if g.get("resultado") == "no_contestó")
            no_contesto_ratio = no_contesto / total_g

            ptp_total    = sum(1 for g in gestiones if g.get("resultado") == "prometió_pago")
            ptp_cumplidos = sum(1 for g in gestiones if g.get("ptp_fue_cumplido") is True)
            ptp_ratio    = ptp_cumplidos / max(ptp_total, 1)

            # Lógica de score (exactamente según BUILD 3 spec)
            if dpd >= 22:
                score = "E"; estrellas = 0
            elif dpd >= 15 or dpd_max >= 22:
                score = "D"; estrellas = 1
            elif dpd >= 8 or (len(historial_vencidas) >= 3 and no_contesto_ratio > 0.5):
                score = "C"; estrellas = 2
            elif dpd >= 1:
                if ptp_ratio >= 0.8:
                    score = "B"; estrellas = 3
                else:
                    score = "C"; estrellas = 2
            elif len(historial_vencidas) == 0 and no_contesto_ratio < 0.1:
                score = "A+"; estrellas = 5
            else:
                score = "A"; estrellas = 4

            score_entry = {
                "fecha":        today_str,
                "score":        score,
                "estrellas":    estrellas,
                "dpd_actual":   dpd,
                "calculado_por": "scheduler",
            }

            await db.loanbook.update_one(
                {"id": loan_id},
                {
                    "$set": {
                        "score_pago":    score,
                        "estrella_nivel": estrellas,
                        "updated_at":    now_iso,
                    },
                    "$push": {"score_historial": score_entry},
                },
            )
            updated += 1

        logger.info("[LoanScheduler] calcular_scores: %d loans procesados", updated)

    except Exception as e:
        logger.error("[LoanScheduler] calcular_scores error: %s", e)


# ─── CRON 3: 07:00 AM — Cola RADAR ───────────────────────────────────────────

async def generar_cola_radar() -> None:
    """Invalida el caché diario y regenera la cola de cobro para el día."""
    from database import db
    from services.shared_state import _invalidate_keys, get_daily_collection_queue

    try:
        _invalidate_keys(["daily_queue:"])
        queue = await get_daily_collection_queue(db)
        logger.info("[LoanScheduler] generar_cola_radar: %d ítems generados", len(queue))
    except Exception as e:
        logger.error("[LoanScheduler] generar_cola_radar error: %s", e)


# ─── CRON 4: Viernes 17:00 — Resumen semanal ─────────────────────────────────

async def resumen_semanal() -> None:
    """Calcula cobrado vs esperado de la semana.
    BUILD 5: envío automático al CEO por WhatsApp (Mercately) — pendiente conexión.
    """
    from database import db

    try:
        hoy    = date.today()
        lunes  = hoy - timedelta(days=hoy.weekday())
        viernes = lunes + timedelta(days=4)
        lunes_str   = lunes.isoformat()
        viernes_str = viernes.isoformat()

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "cuotas": 1, "codigo": 1},
        ).to_list(5000)

        cuotas_esperadas = valor_esperado = 0
        cuotas_pagadas   = valor_cobrado  = 0.0

        for loan in loans:
            for cuota in loan.get("cuotas", []):
                fv = cuota.get("fecha_vencimiento", "")
                if lunes_str <= fv <= viernes_str:
                    cuotas_esperadas += 1
                    valor_esperado   += cuota.get("valor", 0)
                    if cuota.get("estado") == "pagada":
                        cuotas_pagadas += 1
                        valor_cobrado  += cuota.get("valor_pagado", cuota.get("valor", 0))

        pct = round(valor_cobrado / valor_esperado * 100, 1) if valor_esperado > 0 else 0.0

        logger.info(
            "[LoanScheduler] RESUMEN SEMANAL %s→%s | "
            "Esperado: %d cuotas $%.0f | Cobrado: %d cuotas $%.0f (%.1f%%) | "
            "[BUILD 5: pendiente envío WhatsApp CEO via Mercately]",
            lunes_str, viernes_str,
            cuotas_esperadas, valor_esperado,
            int(cuotas_pagadas), valor_cobrado, pct,
        )

    except Exception as e:
        logger.error("[LoanScheduler] resumen_semanal error: %s", e)


# ─── Ciclo de vida ────────────────────────────────────────────────────────────

def start_loanbook_scheduler() -> None:
    """Registra los 4 CRON jobs y arranca el scheduler del loanbook."""
    _loanbook_scheduler.add_job(
        calcular_dpd_todos, trigger="cron",
        hour=6, minute=0,
        id="calcular_dpd_todos", replace_existing=True,
        max_instances=1, misfire_grace_time=300,
    )
    _loanbook_scheduler.add_job(
        calcular_scores, trigger="cron",
        hour=6, minute=30,
        id="calcular_scores", replace_existing=True,
        max_instances=1, misfire_grace_time=300,
    )
    _loanbook_scheduler.add_job(
        generar_cola_radar, trigger="cron",
        hour=7, minute=0,
        id="generar_cola_radar", replace_existing=True,
        max_instances=1, misfire_grace_time=300,
    )
    _loanbook_scheduler.add_job(
        resumen_semanal, trigger="cron",
        day_of_week="fri", hour=17, minute=0,
        id="resumen_semanal", replace_existing=True,
        max_instances=1, misfire_grace_time=3600,
    )
    _loanbook_scheduler.start()
    logger.info(
        "[LoanScheduler] Iniciado — 4 jobs: "
        "DPD@06:00 · Scores@06:30 · RADAR@07:00 · Resumen@Vie17:00 (America/Bogota)"
    )


def stop_loanbook_scheduler() -> None:
    """Detiene el scheduler del loanbook limpiamente."""
    if _loanbook_scheduler.running:
        _loanbook_scheduler.shutdown(wait=False)
        logger.info("[LoanScheduler] Detenido")
