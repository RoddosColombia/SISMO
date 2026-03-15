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
    "calcular_dpd_todos",
    "alertar_buckets_criticos",
    "verificar_alertas_cfo",
    "calcular_scores",
    "generar_cola_radar",
    "recordatorio_preventivo",
    "recordatorio_vencimiento",
    "notificar_mora_nueva",
    "resumen_semanal_ceo",
]

JOB_LABELS: dict[str, str] = {
    "calcular_dpd_todos":       "Calcular DPD (06:00)",
    "alertar_buckets_criticos": "Alertas Buckets (06:05)",
    "verificar_alertas_cfo":    "Verificar Alertas CFO (06:10)",
    "calcular_scores":          "Calcular Scores + PTP (06:30)",
    "generar_cola_radar":       "Generar Cola RADAR (07:00)",
    "recordatorio_preventivo":  "Recordatorio Preventivo (Mar 09:00)",
    "recordatorio_vencimiento": "Recordatorio Vencimiento (Mié 09:00)",
    "notificar_mora_nueva":     "Notificar Mora Nueva (Jue 09:00)",
    "resumen_semanal_ceo":      "Resumen Semanal CEO (Vie 17:00)",
}


@router.get("/jobs")
async def list_jobs(current_user=Depends(get_current_user)):
    """Lista los 9 jobs del scheduler con estado y próxima ejecución."""
    from services.loanbook_scheduler import _loanbook_scheduler
    running_jobs = {j.id: j for j in _loanbook_scheduler.get_jobs()}
    result = []
    for job_id in ALLOWED_JOBS:
        job = running_jobs.get(job_id)
        result.append({
            "id":              job_id,
            "label":           JOB_LABELS.get(job_id, job_id),
            "next_run":        job.next_run_time.isoformat() if job and job.next_run_time else None,
            "running":         job is not None,
        })
    return result


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str, current_user=Depends(get_current_user)):
    """Ejecuta un job manualmente en background. Retorna inmediatamente."""
    if job_id not in ALLOWED_JOBS:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' no reconocido")

    from services.loanbook_scheduler import (
        calcular_dpd_todos, alertar_buckets_criticos, verificar_alertas_cfo,
        calcular_scores, generar_cola_radar, recordatorio_preventivo,
        recordatorio_vencimiento, notificar_mora_nueva, resumen_semanal_ceo,
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
    }
    asyncio.create_task(_job_map[job_id]())
    return {
        "ok":          True,
        "job":         job_id,
        "label":       JOB_LABELS.get(job_id, job_id),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "message":     f"Job '{job_id}' iniciado en background",
    }
