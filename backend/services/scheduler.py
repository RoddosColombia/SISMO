"""
scheduler.py — APScheduler para RODDOS Contable IA.

Job único (BUILD 2):
  process_pending_events: corre cada 60 s, procesa roddos_events con estado='pending'
  y los marca como 'processed'. Si event_type desconocido o excepción → estado='failed', log.
"""
import logging
from datetime import datetime, timezone, timedelta

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
    "moto.vendida.webhook",
    "moto.vendida.polling",
    "moto.vendida.retroactivo",
    "alegra.invoice.polling",
    "alegra.webhook.new-invoice",
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


async def _sincronizar_facturas_recientes() -> None:
    """Every 5 min: pull recent Alegra invoices and update inventory if VIN detected."""
    try:
        from routers.alegra_webhooks import sincronizar_facturas_recientes
        n = await sincronizar_facturas_recientes()
        if n:
            logger.info("[Scheduler] Alegra invoice sync: %d facturas nuevas procesadas", n)
    except Exception as e:
        logger.error("[Scheduler] Alegra invoice sync error: %s", e)


async def _procesar_reintentos_alegra() -> None:
    """Every 5 min: retry movimientos pendientes causación en Alegra."""
    from database import db
    from services.bank_reconciliation import BankReconciliationEngine, Banco, MovimientoBancario
    import hashlib

    try:
        engine = BankReconciliationEngine(db)

        # Buscar movimientos pendientes reintento que están listos
        ahora = datetime.now(timezone.utc)
        reintentos = await db.conciliacion_reintentos.find(
            {
                "estado": "pendiente_reintento",
                "proximo_intento": {"$lte": ahora}
            }
        ).to_list(50)

        if not reintentos:
            return

        procesados = 0
        fallidos = 0

        for reintento in reintentos:
            movimiento_hash = reintento.get("movimiento_hash")
            try:
                # Reconstruir MovimientoBancario para reintentar
                mov = MovimientoBancario(
                    banco=Banco[reintento["banco"].upper()],
                    fecha=reintento["fecha"],
                    descripcion=reintento["descripcion"],
                    monto=reintento["monto"],
                    cuenta_debito_sugerida=reintento["cuenta_debito"],
                    cuenta_credito_sugerida=reintento["cuenta_credito"],
                    confianza=1.0,  # Ya fue clasificado como causable
                )

                # Reintentar creación
                exitoso, journal_id, error = await engine.crear_journal_alegra(mov)

                if exitoso:
                    # Éxito — guardar como procesado y eliminar de reintentos
                    await db.conciliacion_movimientos_procesados.insert_one({
                        "hash": movimiento_hash,
                        "banco": reintento["banco"],
                        "fecha": reintento["fecha"],
                        "descripcion": reintento["descripcion"],
                        "monto": reintento["monto"],
                        "journal_id": journal_id,
                        "procesado_at": datetime.now(timezone.utc).isoformat(),
                        "reintento_num": reintento.get("intentos", 1),
                    })

                    await db.conciliacion_reintentos.delete_one(
                        {"movimiento_hash": movimiento_hash}
                    )

                    logger.info(
                        f"[Scheduler] Reintento éxito: {reintento['descripcion']} "
                        f"(intento {reintento.get('intentos', 1)}) → journal {journal_id}"
                    )
                    procesados += 1

                else:
                    # Falló de nuevo
                    intentos_actuales = reintento.get("intentos", 1)

                    if intentos_actuales >= 5:
                        # Máximo de intentos — marcar como fallo permanente
                        await db.conciliacion_reintentos.update_one(
                            {"movimiento_hash": movimiento_hash},
                            {
                                "$set": {
                                    "estado": "fallo_permanente",
                                    "timestamp_fallo_permanente": datetime.now(timezone.utc).isoformat(),
                                    "error_final": error,
                                }
                            }
                        )

                        logger.error(
                            f"[Scheduler] Reintento fallo permanente: "
                            f"{reintento['descripcion']} (5 intentos agotados)"
                        )
                    else:
                        # Siguiente intento en 10 minutos
                        proximo = datetime.now(timezone.utc) + timedelta(minutes=10)
                        await db.conciliacion_reintentos.update_one(
                            {"movimiento_hash": movimiento_hash},
                            {
                                "$set": {
                                    "proximo_intento": proximo,
                                    "timestamp_ultimo_intento": datetime.now(timezone.utc).isoformat(),
                                    "error_ultimo": error,
                                }
                            }
                        )

                    fallidos += 1

            except Exception as e:
                logger.error(
                    f"[Scheduler] Error procesando reintento {movimiento_hash}: {e}"
                )
                fallidos += 1

        if procesados or fallidos:
            logger.info(
                f"[Scheduler] procesar_reintentos_alegra — "
                f"{procesados} exitosos, {fallidos} fallidos"
            )

    except Exception as e:
        logger.error(f"[Scheduler] procesar_reintentos_alegra error general: {e}")


async def _retry_dlq_events() -> None:
    """Retry failed DLQ events every 5 minutes (per D-07/BUS-04)."""
    from database import db
    from services.event_bus_service import EventBusService
    bus = EventBusService(db)
    try:
        retried = await bus.retry_dlq()
        if retried > 0:
            logger.info("[Scheduler] DLQ retry: %d events re-published", retried)
    except Exception as e:
        logger.error("[Scheduler] DLQ retry failed: %s", e)


async def _compute_portfolio_summary() -> None:
    """Daily 11:30 PM — portfolio snapshot (SCH-01)."""
    from database import db
    from services.portfolio_pipeline import compute_portfolio_summary
    try:
        await compute_portfolio_summary(db)
    except Exception as e:
        logger.error("[Scheduler] Portfolio summary failed: %s", e)


async def _compute_financial_report_mensual() -> None:
    """Monthly day 1 — P&L report (SCH-02)."""
    from database import db
    from services.portfolio_pipeline import compute_financial_report_mensual
    try:
        await compute_financial_report_mensual(db)
    except Exception as e:
        logger.error("[Scheduler] Monthly financial report failed: %s", e)


def start_scheduler() -> None:
    """Registra el job y arranca el scheduler. Llamar desde startup de FastAPI."""
    _scheduler.add_job(
        _retry_dlq_events,
        trigger="interval",
        minutes=5,
        id="dlq_retry",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )
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

    # ── Alegra invoice sync every 5 min (fallback para webhooks rotos) ─────────
    _scheduler.add_job(
        _sincronizar_facturas_recientes,
        trigger="interval",
        minutes=5,
        id="sync_facturas_alegra",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    # ── Reintentos de causación Alegra cada 5 min ──────────────────────────────
    _scheduler.add_job(
        _procesar_reintentos_alegra,
        trigger="interval",
        minutes=5,
        id="procesar_reintentos_alegra",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    # ── Inventario reconciliación cada lunes 7am ────────────────────────────────
    _scheduler.add_job(
        _reconciliar_inventario_lunes,
        trigger="cron",
        day_of_week="mon",
        hour=7, minute=0,
        timezone="America/Bogota",
        id="reconciliar_inventario_lunes",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )

    # ── DIAN sync diario 11pm Bogotá ───────────────────────────────────────────
    _scheduler.add_job(
        _sync_dian_diario,
        trigger="cron",
        hour=23, minute=0,
        timezone="America/Bogota",
        id="dian_sync_diario",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )

    # ── Portfolio summary daily 11:30 PM (SCH-01) ──────────────────────────────
    _scheduler.add_job(
        _compute_portfolio_summary,
        trigger="cron",
        hour=23, minute=30,
        timezone="America/Bogota",
        id="portfolio_summary_diario",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # ── Financial report monthly day 1, 6:00 AM (SCH-02) ──────────────────────
    _scheduler.add_job(
        _compute_financial_report_mensual,
        trigger="cron",
        day=1,
        hour=6, minute=0,
        timezone="America/Bogota",
        id="financial_report_mensual",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    _scheduler.start()
    logger.info(
        "[Scheduler] APScheduler iniciado — "
        "process_pending_events@60s | informe_cfo@día1 08:00 | "
        "WA: T1@lun08 T2@mié08 T3@jue09 T5@sab09 | "
        "inventario@lun07 | sync_pagos@5min | sync_facturas@5min | reintentos_alegra@5min | dian@23:00 | "
        "BUILD24: portfolio_summary@23:30 | financial_report@día1 06:00 | "
        "BUILD21: resumen_semanal_cfo@lun08 | anomalias_diarias@23:30 | "
        "BUILD25: global66_recuperacion@10min (COT)"
    )

    # ── BUILD 21: Resumen semanal CFO (lunes 8:05am) ──────────────────────────
    _scheduler.add_job(
        _resumen_semanal_cfo,
        trigger="cron",
        day_of_week="mon",
        hour=8, minute=5,
        timezone="America/Bogota",
        id="resumen_semanal_cfo",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )

    # ── BUILD 21: Detección de anomalías contables diarias (23:30) ───────────
    _scheduler.add_job(
        _detectar_anomalias_diarias,
        trigger="cron",
        hour=23, minute=30,
        timezone="America/Bogota",
        id="anomalias_contables_diarias",
        replace_existing=True, max_instances=1, misfire_grace_time=3600,
    )

    # ── BUILD 25: Recuperación eventos Global66 no procesados (cada 10 min) ──
    _scheduler.add_job(
        _recuperar_global66_pendientes,
        trigger="interval",
        minutes=10,
        id="recuperar_global66_pendientes",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )


async def _recuperar_global66_pendientes() -> None:
    """Cada 10 min — Reintenta en Alegra los eventos Global66 no procesados."""
    from database import db
    from alegra_service import AlegraService
    from services.accounting_engine import clasificar_movimiento
    GLOBAL66_BANK_ACCOUNT_ID = 11100507
    FALLBACK = 5493
    MAX_INTENTOS = 5

    try:
        pendientes = await db.global66_eventos_recibidos.find({
            "procesado": False,
            "intentos_alegra": {"$lt": MAX_INTENTOS},
            "motivo": {"$exists": False},
        }).to_list(20)

        if not pendientes:
            return

        service = AlegraService(db)
        recuperados = 0

        for evento in pendientes:
            try:
                clasificacion = clasificar_movimiento(
                    descripcion=evento.get("descripcion", ""),
                    proveedor="",
                    monto=float(evento.get("monto", 0)),
                    banco_origen=GLOBAL66_BANK_ACCOUNT_ID,
                )
                monto = abs(float(evento.get("monto", 0)))
                tipo = evento.get("tipo", "INGRESO")

                if tipo == "INGRESO":
                    d = GLOBAL66_BANK_ACCOUNT_ID
                    c = clasificacion.cuenta_credito or FALLBACK
                else:
                    d = clasificacion.cuenta_debito or FALLBACK
                    c = GLOBAL66_BANK_ACCOUNT_ID

                result = await service.request_with_verify("journals", "POST", {
                    "date": evento.get("fecha", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                    "observations": evento.get("descripcion", "Global66 recuperado"),
                    "entries": [
                        {"id": d, "debit": int(monto), "credit": 0},
                        {"id": c, "debit": 0, "credit": int(monto)},
                    ],
                })
                journal_id = result.get("id")

                await db.global66_eventos_recibidos.update_one(
                    {"_id": evento["_id"]},
                    {
                        "$set": {"procesado": True, "alegra_journal_id": str(journal_id)},
                        "$inc": {"intentos_alegra": 1},
                    }
                )
                recuperados += 1

            except Exception as e:
                await db.global66_eventos_recibidos.update_one(
                    {"_id": evento["_id"]},
                    {"$inc": {"intentos_alegra": 1}, "$set": {"ultimo_error": str(e)}}
                )

        if recuperados:
            logger.info("[Scheduler] Global66 recuperados: %d eventos causados", recuperados)

    except Exception as e:
        logger.error("[Scheduler] Error recuperación Global66: %s", e)


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente. Llamar desde shutdown de FastAPI."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler detenido")


async def _sync_dian_diario() -> None:
    """23:00 COT — Sincroniza facturas DIAN del día anterior + hoy (ventana 48h)."""
    from database import db as _db
    from services.dian_service import sync_facturas_dian
    try:
        hoy = datetime.now(timezone.utc).date()
        ayer = (hoy - timedelta(days=1))
        resumen = await sync_facturas_dian(ayer.isoformat(), hoy.isoformat(), _db)
        logger.info(
            "[Scheduler] DIAN sync: consultadas=%d causadas=%d omitidas=%d errores=%d",
            resumen.get("consultadas", 0),
            resumen.get("procesadas", 0),
            resumen.get("omitidas", 0),
            resumen.get("errores", 0),
        )
    except Exception as e:
        logger.error("[Scheduler] DIAN sync error: %s", e)


async def _reconciliar_inventario_lunes() -> None:
    """Lunes 7am COT — Verifica que el conteo de motos cuadre. Genera alerta si no cuadra."""
    from database import db
    try:
        total = await db.inventario_motos.count_documents({})
        disponibles = await db.inventario_motos.count_documents({"estado": "Disponible"})
        vendidas_entregadas = await db.inventario_motos.count_documents(
            {"estado": {"$in": ["Vendida", "Entregada"]}}
        )
        anuladas = await db.inventario_motos.count_documents({"estado": "Anulada"})
        otros = total - disponibles - vendidas_entregadas - anuladas
        now = datetime.now(timezone.utc).isoformat()

        if otros != 0:
            await db.roddos_events.insert_one({
                "event_type": "inventario.descuadre.detectado",
                "total_motos": total,
                "disponibles": disponibles,
                "vendidas_entregadas": vendidas_entregadas,
                "anuladas": anuladas,
                "sin_estado_definido": otros,
                "timestamp": now,
                "nota": f"⚠️ Inventario descuadrado: {otros} motos sin estado definido",
            })
            await db.notifications.insert_one({
                "type": "inventario_descuadrado",
                "message": f"⚠️ Inventario descuadrado: {otros} motos sin estado definido. Total: {total}",
                "data": {"total": total, "disponibles": disponibles, "vendidas_entregadas": vendidas_entregadas},
                "read": False,
                "timestamp": now,
            })
            logger.warning("[Scheduler] Inventario descuadrado: %d motos sin estado definido", otros)
        else:
            await db.roddos_events.insert_one({
                "event_type": "inventario.reconciliacion.ok",
                "total_motos": total,
                "disponibles": disponibles,
                "vendidas_entregadas": vendidas_entregadas,
                "anuladas": anuladas,
                "timestamp": now,
                "nota": f"✅ Inventario cuadrado: {total} motos",
            })
            logger.info("[Scheduler] Inventario cuadrado: %d motos (D=%d VE=%d A=%d)", total, disponibles, vendidas_entregadas, anuladas)

    except Exception as e:
        logger.error("[Scheduler] Error reconciliación inventario: %s", e)


# ── BUILD 21 — Resumen Semanal CFO ───────────────────────────────────────────

async def _resumen_semanal_cfo() -> None:
    """Lunes 8:05am COT — Genera resumen semanal del CFO e inyecta en cfo_alertas.

    El agente lo leerá en la próxima sesión del usuario y lo presentará proactivamente.
    """
    from database import db
    try:
        from services.accounting_engine import generar_resumen_semanal
        resumen = await generar_resumen_semanal(db)
        now = datetime.now(timezone.utc).isoformat()

        # Guardar en cfo_alertas para que el agente lo inyecte en contexto
        await db.cfo_alertas.insert_one({
            "tipo": "resumen_semanal",
            "mensaje": resumen["resumen_texto"],
            "semana": resumen.get("semana", ""),
            "datos": resumen,
            "created_at": now,
            "leido": False,
            "fuente": "scheduler_lunes_cfo",
        })

        # También en notifications para el frontend
        await db.notifications.insert_one({
            "type": "resumen_semanal_cfo",
            "message": resumen["resumen_texto"],
            "data": resumen,
            "read": False,
            "timestamp": now,
        })

        logger.info(
            "[Scheduler] Resumen semanal CFO generado — recaudo=$%s déficit=$%s alertas=%d",
            f"{resumen.get('recaudo_proyectado', 0):,.0f}",
            f"{resumen.get('deficit_superavit', 0):,.0f}",
            len(resumen.get("alertas", [])),
        )
    except Exception as e:
        logger.error("[Scheduler] Error generando resumen semanal CFO: %s", e)


# ── BUILD 21 — Detección de Anomalías Contables ───────────────────────────────

async def _detectar_anomalias_diarias() -> None:
    """23:30 COT — Detecta anomalías contables y financia. Genera alertas en cfo_alertas.

    Las alertas son leídas por el agente en la próxima sesión del usuario.
    """
    from database import db
    try:
        from services.accounting_engine import detectar_anomalias
        anomalias = await detectar_anomalias(db)
        now = datetime.now(timezone.utc).isoformat()

        if not anomalias:
            logger.info("[Scheduler] Anomalías contables diarias: sin anomalías detectadas.")
            return

        for anomalia in anomalias:
            # Evitar duplicar alertas del mismo día
            existe = await db.cfo_alertas.find_one({
                "tipo": anomalia["tipo"],
                "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()},
            })
            if existe:
                continue

            await db.cfo_alertas.insert_one({
                "tipo": anomalia["tipo"],
                "mensaje": anomalia["mensaje"],
                "severidad": anomalia.get("severidad", "media"),
                "accion_sugerida": anomalia.get("accion_sugerida", ""),
                "created_at": now,
                "leido": False,
                "fuente": "scheduler_anomalias_diarias",
            })

            # Notificación frontend para anomalías altas
            if anomalia.get("severidad") == "alta":
                await db.notifications.insert_one({
                    "type": f"anomalia_{anomalia['tipo']}",
                    "message": f"⚠️ [{anomalia['severidad'].upper()}] {anomalia['mensaje']}",
                    "data": anomalia,
                    "read": False,
                    "timestamp": now,
                })

        logger.info(
            "[Scheduler] Anomalías contables: %d anomalías detectadas y guardadas.",
            len(anomalias),
        )
    except Exception as e:
        logger.error("[Scheduler] Error en detección de anomalías: %s", e)
