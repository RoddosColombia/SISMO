"""scheduler.py — Trigger manual de CRON jobs (admin only).

POST /api/scheduler/trigger/{job_id}  → lanza el job en background y retorna inmediatamente.
GET  /api/scheduler/jobs              → lista de jobs disponibles con próxima ejecución.
"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_current_user

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

ALLOWED_JOBS: list[str] = [
    # ── Scheduler B (loanbook_scheduler) — 12 jobs ────────────────────────────
    "calcular_dpd_todos",
    "alertar_buckets_criticos",
    "verificar_alertas_cfo",
    "calcular_scores",
    "generar_cola_radar",
    "recordatorio_preventivo",
    "recordatorio_vencimiento",
    "notificar_mora_nueva",
    "resumen_semanal_ceo",
    # BUILD 9 — Learning Engine
    "alertas_predictivas",
    "resolver_outcomes",
    "procesar_patrones",
    # ── Scheduler A (scheduler) — 4 jobs — P-02 ──────────────────────────────
    "sync_pagos_alegra",
    "sync_facturas_alegra",
    "procesar_reintentos_alegra",
    "recuperar_global66_pendientes",
]

JOB_LABELS: dict[str, str] = {
    "calcular_dpd_todos":            "Calcular DPD (06:00)",
    "alertar_buckets_criticos":      "Alertas Buckets (06:05)",
    "verificar_alertas_cfo":         "Verificar Alertas CFO (06:10)",
    "calcular_scores":               "Calcular Scores + PTP (06:30)",
    "generar_cola_radar":            "Generar Cola RADAR (07:00)",
    "recordatorio_preventivo":       "Recordatorio Preventivo (Mar 09:00)",
    "recordatorio_vencimiento":      "Recordatorio Vencimiento (Mié 09:00)",
    "notificar_mora_nueva":          "Notificar Mora Nueva (Jue 09:00)",
    "resumen_semanal_ceo":           "Resumen Semanal CEO (Vie 17:00)",
    # BUILD 9
    "alertas_predictivas":           "Alertas Predictivas ML (06:45)",
    "resolver_outcomes":             "Resolver Outcomes WA (07:30)",
    "procesar_patrones":             "Procesar Patrones ML (Lun 08:00)",
    # P-02 — Scheduler A
    "sync_pagos_alegra":             "Sync Pagos Alegra (cada 5 min)",
    "sync_facturas_alegra":          "Sync Facturas Alegra (cada 5 min)",
    "procesar_reintentos_alegra":    "Procesar Reintentos Alegra (cada 5 min)",
    "recuperar_global66_pendientes": "Recuperar Global66 Pendientes (cada 10 min)",
}


@router.get("/jobs")
async def list_jobs(current_user=Depends(get_current_user)):
    """Lista todos los jobs del scheduler con estado y próxima ejecución."""
    from services.loanbook_scheduler import _loanbook_scheduler
    from services.scheduler import _scheduler

    # Merge ambos schedulers para mostrar estado real de todos los jobs
    running_jobs: dict = {}
    for j in _loanbook_scheduler.get_jobs():
        running_jobs[j.id] = j
    for j in _scheduler.get_jobs():
        running_jobs[j.id] = j

    result = []
    for job_id in ALLOWED_JOBS:
        job = running_jobs.get(job_id)
        result.append({
            "id":      job_id,
            "label":   JOB_LABELS.get(job_id, job_id),
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "running": job is not None,
        })
    return result


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str, current_user=Depends(get_current_user)):
    """Ejecuta un job manualmente en background. Retorna inmediatamente."""
    if job_id not in ALLOWED_JOBS:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' no reconocido")

    # Scheduler B — loanbook_scheduler
    from services.loanbook_scheduler import (
        calcular_dpd_todos, alertar_buckets_criticos, verificar_alertas_cfo,
        calcular_scores, generar_cola_radar, recordatorio_preventivo,
        recordatorio_vencimiento, notificar_mora_nueva, resumen_semanal_ceo,
        alertas_predictivas, resolver_outcomes, procesar_patrones,
    )
    # Scheduler A — scheduler (P-02)
    from services.scheduler import (
        _sync_pagos_alegra,
        _sincronizar_facturas_recientes,
        _procesar_reintentos_alegra,
        _recuperar_global66_pendientes,
    )

    _job_map = {
        # Scheduler B
        "calcular_dpd_todos":            calcular_dpd_todos,
        "alertar_buckets_criticos":      alertar_buckets_criticos,
        "verificar_alertas_cfo":         verificar_alertas_cfo,
        "calcular_scores":               calcular_scores,
        "generar_cola_radar":            generar_cola_radar,
        "recordatorio_preventivo":       recordatorio_preventivo,
        "recordatorio_vencimiento":      recordatorio_vencimiento,
        "notificar_mora_nueva":          notificar_mora_nueva,
        "resumen_semanal_ceo":           resumen_semanal_ceo,
        # BUILD 9
        "alertas_predictivas":           alertas_predictivas,
        "resolver_outcomes":             resolver_outcomes,
        "procesar_patrones":             procesar_patrones,
        # Scheduler A (P-02)
        "sync_pagos_alegra":             _sync_pagos_alegra,
        "sync_facturas_alegra":          _sincronizar_facturas_recientes,
        "procesar_reintentos_alegra":    _procesar_reintentos_alegra,
        "recuperar_global66_pendientes": _recuperar_global66_pendientes,
    }

    asyncio.create_task(_job_map[job_id]())
    return {
        "ok":           True,
        "job":          job_id,
        "label":        JOB_LABELS.get(job_id, job_id),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "message":      f"Job '{job_id}' iniciado en background",
    }
