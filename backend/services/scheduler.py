"""
scheduler.py — APScheduler para RODDOS Contable IA.

Job único (BUILD 2):
  process_pending_events: corre cada 60 s, procesa roddos_events con estado='pending'
  y los marca como 'processed'. Si event_type desconocido o excepción → estado='failed', log.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger    = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="America/Bogota")

# Tipos de evento conocidos — cualquier otro → estado='failed'
KNOWN_EVENT_TYPES: frozenset[str] = frozenset({
    "factura.venta.creada",
    "factura.venta.anulada",
    "pago.cuota.registrado",
    "cuota_pagada",
    "inventario.moto.entrada",
    "inventario.moto.baja",
    "cliente.mora.detectada",
    "asiento.contable.creado",
    "agente_ia.accion.ejecutada",
    "factura.compra.creada",
    "repuesto.vendido",
    "loanbook.activado",
    "loanbook.bucket_change",
    "protocolo_recuperacion",
    "ptp.registrado",
})


# ─── Job ──────────────────────────────────────────────────────────────────────

async def _process_pending_events() -> None:
    """Procesa todos los roddos_events con estado='pending' y los marca 'processed'."""
    from database import db  # lazy import: evita circular al importar scheduler temprano

    try:
        pending = await db.roddos_events.find(
            {"estado": "pending"},
            {"_id": 0, "event_id": 1, "event_type": 1},
        ).limit(200).to_list(200)

        if not pending:
            return

        processed_count = 0
        failed_count    = 0
        now_iso         = datetime.now(timezone.utc).isoformat()

        for doc in pending:
            event_id   = doc.get("event_id")
            event_type = doc.get("event_type", "")
            if not event_id:
                continue
            try:
                # Validar event_type — desconocido → fallo intencional
                if event_type not in KNOWN_EVENT_TYPES:
                    raise ValueError(f"event_type desconocido: '{event_type}'")

                await db.roddos_events.update_one(
                    {"event_id": event_id},
                    {"$set": {"estado": "processed", "processed_at": now_iso}},
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"[Scheduler] Error procesando evento {event_id} ({event_type}): {e}")
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


async def _generar_informe_cfo_mensual() -> None:
    """Job día 1 de cada mes 08:00 AM (Bogotá): genera informe CFO y opcionalmente envía WhatsApp."""
    from database import db
    try:
        from services.cfo_agent import generar_informe_cfo, generar_semaforo, consolidar_datos_financieros
        logger.info("[Scheduler] Generando informe CFO mensual automático...")
        informe = await generar_informe_cfo(db, triggered_by="scheduler_mensual")

        # Enviar WhatsApp al CEO si está configurado
        cfg = await db.cfo_config.find_one({}, {"_id": 0}) or {}
        if cfg.get("whatsapp_activo") and cfg.get("whatsapp_ceo"):
            semaforo = informe.get("semaforo", {})
            emojis = {"VERDE": "🟢", "AMARILLO": "🟡", "ROJO": "🔴"}

            def sem_emoji(k: str) -> str:
                return emojis.get(semaforo.get(k, "VERDE"), "🟢")

            metricas = semaforo.get("metricas", {})
            cobrado  = metricas.get("cobrado_mes", 0)
            esperado = metricas.get("esperado_mes", 1)
            pct      = round(cobrado / max(esperado, 1) * 100, 1)

            dims = f"Caja {sem_emoji('caja')} Cartera {sem_emoji('cartera')} Ventas {sem_emoji('ventas')} Roll {sem_emoji('roll_rate')} Imp {sem_emoji('impuestos')}"
            resumen_wa = (
                f"📊 Informe CFO RODDOS — {informe.get('periodo','')}\n"
                f"{dims}\n"
                f"Cobrado: ${cobrado:,.0f} / ${esperado:,.0f} ({pct}%)\n"
                f"Alerta: {', '.join(k.upper() for k, v in semaforo.items() if k != 'metricas' and v == 'ROJO') or 'Sin alertas críticas'}"
            )
            try:
                import httpx
                mercately_cfg = await db.mercately_config.find_one({}, {"_id": 0}) or {}
                mercately_key = mercately_cfg.get("api_key") or ""
                if mercately_key:
                    async with httpx.AsyncClient(timeout=15) as client:
                        await client.post(
                            "https://api.mercately.com/api/v1/customers/send_message",
                            headers={"Authorization": f"Bearer {mercately_key}"},
                            json={"phone": cfg["whatsapp_ceo"], "message": resumen_wa[:400]},
                        )
            except Exception as wa_err:
                logger.warning(f"[Scheduler CFO] WhatsApp no enviado: {wa_err}")

        logger.info(f"[Scheduler] Informe CFO mensual generado: {informe.get('id')}")
    except Exception as e:
        logger.error(f"[Scheduler] Error informe CFO mensual: {e}")




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
    _scheduler.add_job(
        _generar_informe_cfo_mensual,
        trigger="cron",
        day=1,
        hour=8,
        minute=0,
        timezone="America/Bogota",
        id="informe_cfo_mensual",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("[Scheduler] APScheduler iniciado — process_pending_events cada 60 s | informe_cfo_mensual día 1 08:00")


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente. Llamar desde shutdown de FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler detenido")
