"""
scheduler.py — APScheduler para RODDOS Contable IA.

Job único (BUILD 2):
  process_pending_events: corre cada 60 s, procesa roddos_events con estado='pending'
  y los marca como 'processed'. Si un evento falla → estado='failed', log, continúa.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger   = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="America/Bogota")


# ─── Job ──────────────────────────────────────────────────────────────────────

async def _process_pending_events() -> None:
    """Procesa todos los roddos_events con estado='pending' y los marca 'processed'."""
    from database import db  # lazy import: evita circular al importar scheduler temprano

    try:
        pending = await db.roddos_events.find(
            {"estado": "pending"},
            {"_id": 0, "event_id": 1},
        ).limit(200).to_list(200)

        if not pending:
            return

        processed_count = 0
        failed_count    = 0
        now_iso         = datetime.now(timezone.utc).isoformat()

        for doc in pending:
            event_id = doc.get("event_id")
            if not event_id:
                continue
            try:
                await db.roddos_events.update_one(
                    {"event_id": event_id},
                    {"$set": {"estado": "processed", "processed_at": now_iso}},
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"[Scheduler] Error procesando evento {event_id}: {e}")
                try:
                    await db.roddos_events.update_one(
                        {"event_id": event_id},
                        {"$set": {"estado": "failed", "error": str(e)}},
                    )
                except Exception:
                    pass
                failed_count += 1

        if processed_count or failed_count:
            logger.info(
                f"[Scheduler] process_pending_events — "
                f"{processed_count} procesados, {failed_count} fallidos"
            )

    except Exception as e:
        logger.error(f"[Scheduler] process_pending_events error general: {e}")


# ─── Ciclo de vida ────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    """Registra el job y arranca el scheduler. Llamar desde startup de FastAPI."""
    _scheduler.add_job(
        _process_pending_events,
        trigger="interval",
        seconds=60,
        id="process_pending_events",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )
    _scheduler.start()
    logger.info("[Scheduler] APScheduler iniciado — job 'process_pending_events' cada 60 s")


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente. Llamar desde shutdown de FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler detenido")
