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




# ── WhatsApp Template Wrappers ─────────────────────────────────────────────────

async def _wa_recordatorios_preventivos() -> None:
    """Lunes 8am COT — Template 1: recordatorio D-2 a clientes con cuota el miércoles."""
    try:
        from routers.mercately import run_recordatorios_preventivos
        n = await run_recordatorios_preventivos()
        logger.info("[Scheduler] WA T1 preventivos: %d enviados", n)
    except Exception as e:
        logger.error("[Scheduler] WA T1 error: %s", e)


async def _wa_recordatorios_vencimiento() -> None:
    """Miércoles 8am COT — Template 2: día de vencimiento de cuota."""
    try:
        from routers.mercately import run_recordatorios_vencimiento
        n = await run_recordatorios_vencimiento()
        logger.info("[Scheduler] WA T2 vencimiento: %d enviados", n)
    except Exception as e:
        logger.error("[Scheduler] WA T2 error: %s", e)


async def _wa_alertas_mora_d1() -> None:
    """Jueves 9am COT — Template 3: mora D+1 (cuota no pagada el miércoles)."""
    try:
        from routers.mercately import run_alertas_mora_d1
        n = await run_alertas_mora_d1()
        logger.info("[Scheduler] WA T3 mora D+1: %d enviados", n)
    except Exception as e:
        logger.error("[Scheduler] WA T3 error: %s", e)


async def _wa_alertas_mora_severa() -> None:
    """Sábado 9am COT — Template 5: clientes en mora severa (+30 días)."""
    try:
        from routers.mercately import run_alertas_mora_severa
        n = await run_alertas_mora_severa()
        logger.info("[Scheduler] WA T5 mora severa: %d enviados", n)
    except Exception as e:
        logger.error("[Scheduler] WA T5 error: %s", e)


async def _sync_pagos_alegra() -> None:
    """Every 5 min: pull Alegra payments and apply to loanbook."""
    try:
        from routers.alegra_webhooks import sincronizar_pagos_externos
        n = await sincronizar_pagos_externos()
        if n:
            logger.info("[Scheduler] Alegra payment sync: %d nuevos pagos", n)
    except Exception as e:
        logger.error("[Scheduler] Alegra payment sync error: %s", e)


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

    # ── WhatsApp Templates (America/Bogota) ────────────────────────────────────
    _scheduler.add_job(
        _wa_recordatorios_preventivos,
        trigger="cron",
        day_of_week="mon",  # Lunes
        hour=8, minute=0,
        timezone="America/Bogota",
        id="wa_recordatorios_preventivos",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _wa_recordatorios_vencimiento,
        trigger="cron",
        day_of_week="wed",  # Miércoles
        hour=8, minute=0,
        timezone="America/Bogota",
        id="wa_recordatorios_vencimiento",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _wa_alertas_mora_d1,
        trigger="cron",
        day_of_week="thu",  # Jueves
        hour=9, minute=0,
        timezone="America/Bogota",
        id="wa_alertas_mora_d1",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _wa_alertas_mora_severa,
        trigger="cron",
        day_of_week="sat",  # Sábado
        hour=9, minute=0,
        timezone="America/Bogota",
        id="wa_alertas_mora_severa",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )

    # ── Alegra payment sync every 5 min ────────────────────────────────────────
    _scheduler.add_job(
        _sync_pagos_alegra,
        trigger="interval",
        minutes=5,
        id="sync_pagos_alegra",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    _scheduler.start()
    logger.info(
        "[Scheduler] APScheduler iniciado — "
        "process_pending_events@60s | informe_cfo@día1 08:00 | "
        "WA: T1@lun08 T2@mié08 T3@jue09 T5@sab09 (COT)"
    )


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente. Llamar desde shutdown de FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler detenido")
