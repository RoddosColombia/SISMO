"""loanbook_scheduler.py — 9 CRON jobs para DPD, scores, alertas WA y resumen CEO.

Jobs (timezone=America/Bogota):
  06:00 AM diario    → calcular_dpd_todos()         — DPD + bucket + interés mora
  06:05 AM diario    → alertar_buckets_criticos()    — WA clientes DPD 8/15 + CEO DPD 22
  06:10 AM diario    → verificar_alertas_cfo()       — despacha cfo_alertas[estado=nueva]
  06:30 AM diario    → calcular_scores() + PTP followup
  07:00 AM diario    → generar_cola_radar()          — warm-up caché RADAR
  Martes   09:00 AM  → recordatorio_preventivo()     — cuota vence mañana (miércoles)
  Miércoles 09:00 AM → recordatorio_vencimiento()    — cuota vence hoy
  Jueves   09:00 AM  → notificar_mora_nueva()         — DPD == 1 (no pagaron ayer)
  Viernes  17:00 PM  → resumen_semanal_ceo()          — resumen enriquecido al CEO

REGLA GLOBAL: Si mercately_config.api_key está vacío → solo log, sin envío, sin crash.
"""
import logging
from datetime import datetime, timezone, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# Tasa mora: 15% EA. Tasa diaria = (1.15)**(1/365) − 1
TASA_MORA_DIARIA: float = (1.15 ** (1 / 365)) - 1  # ≈ 0.00038426

_loanbook_scheduler = AsyncIOScheduler(timezone="America/Bogota")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_cop(n) -> str:
    """Formato peso colombiano: $100.000"""
    try:
        return f"${int(n or 0):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def _fmtfecha(iso: str) -> str:
    """2026-03-18 → 18/03/2026"""
    if len(iso) >= 10:
        return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"
    return iso


def _nombre_corto(nombre: str) -> str:
    """Primer nombre únicamente."""
    return (nombre or "").split()[0]


def _get_bucket(dpd: int) -> str:
    if dpd == 0:
        return "0"
    if dpd <= 7:
        return "1-7"
    if dpd <= 14:
        return "8-14"
    if dpd <= 21:
        return "15-21"
    return "22+"


async def _get_mercately_config() -> dict:
    from database import db
    return await db.mercately_config.find_one({}, {"_id": 0}) or {}


async def _wa(telefono: str, mensaje: str, config: dict | None = None) -> bool:
    """Envía WA solo si api_key está configurado. Nunca lanza excepción."""
    cfg = config if config is not None else await _get_mercately_config()
    if not cfg.get("api_key"):
        logger.info("[LoanScheduler] WA sin API key — solo log: %.60s", mensaje)
        return False
    from routers.mercately import enviar_whatsapp
    return await enviar_whatsapp(telefono, mensaje)


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

            prev_bucket   = loan.get("dpd_bucket", "0")
            prev_dpd_max  = loan.get("dpd_maximo_historico", 0)
            nuevo_dpd_max = max(prev_dpd_max, dpd_actual)

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


# ─── CRON 2: 06:05 AM — Alertas WA por bucket crítico ────────────────────────

async def alertar_buckets_criticos() -> None:
    """WA diferenciado cuando un loan alcanza dpd==8 (URGENTE), 15 (CRÍTICO) o 22 (RECUPERACIÓN → CEO)."""
    from database import db

    try:
        config = await _get_mercately_config()
        if not config.get("api_key"):
            logger.info("[LoanScheduler] alertar_buckets_criticos: sin API key — solo log")
            return

        ceo_number = config.get("ceo_number", "")
        hoy        = date.today()
        hoy_str    = hoy.isoformat()
        fecha_limite_str = (hoy + timedelta(days=7)).strftime("%d/%m/%Y")

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]},
             "dpd_actual": {"$in": [8, 15, 22]}},
            {"_id": 0, "id": 1, "cliente_nombre": 1, "cliente_nit": 1,
             "cliente_telefono": 1, "moto_id": 1, "moto_descripcion": 1,
             "dpd_actual": 1, "cuotas": 1, "interes_mora_acumulado": 1,
             "gestiones": 1, "valor_cuota": 1},
        ).to_list(500)

        enviados = 0
        for loan in loans:
            tel    = loan.get("cliente_telefono", "")
            dpd    = loan.get("dpd_actual", 0)
            nombre = _nombre_corto(loan.get("cliente_nombre", ""))
            modelo = (loan.get("moto_descripcion", "") or "la moto").strip()
            mora_int = float(loan.get("interes_mora_acumulado", 0))

            # Cuota vencida más antigua
            cuotas_venc = [
                c for c in loan.get("cuotas", [])
                if c.get("estado") in ("vencida", "pendiente")
                and c.get("fecha_vencimiento", "") < hoy_str
            ]
            if cuotas_venc:
                cuota_obj = min(cuotas_venc, key=lambda c: c.get("fecha_vencimiento", ""))
                num_cuota = cuota_obj.get("numero", "?")
                capital   = float(cuota_obj.get("valor", loan.get("valor_cuota", 0)))
            else:
                num_cuota = "?"
                capital   = float(loan.get("valor_cuota", 0))

            total = capital + mora_int

            if dpd == 8 and tel:
                msg = (
                    f"{nombre}, llevas {dpd} días con tu cuota #{num_cuota} vencida. "
                    f"Debes {_fmt_cop(capital)} + {_fmt_cop(mora_int)} de mora "
                    f"(Total: {_fmt_cop(total)}). Contáctanos hoy para acordar el pago."
                )
                await _wa(tel, msg, config)
                enviados += 1

            elif dpd == 15 and tel:
                msg = (
                    f"{nombre}, este es un aviso formal. Tienes 7 días para regularizar tu crédito. "
                    f"Adeudas {_fmt_cop(total)}. Si no nos contactas antes del {fecha_limite_str} "
                    "iniciaremos el proceso de recuperación de la moto."
                )
                await _wa(tel, msg, config)
                enviados += 1

            elif dpd == 22 and ceo_number:
                cedula    = loan.get("cliente_nit", "N/D")
                loanbook_id = loan.get("id", "")

                # Chasis desde inventario
                chasis = "N/D"
                if loan.get("moto_id"):
                    moto_doc = await db.inventario_motos.find_one(
                        {"id": loan["moto_id"]}, {"_id": 0, "chasis": 1}
                    )
                    if moto_doc:
                        chasis = moto_doc.get("chasis", "N/D")

                # Última gestión
                gestiones = loan.get("gestiones", [])
                if gestiones:
                    last_g        = gestiones[-1]
                    fecha_ult     = _fmtfecha(last_g.get("fecha", "")[:10])
                    resultado_ult = last_g.get("resultado", "sin registro")
                else:
                    fecha_ult = resultado_ult = "sin registro"

                ceo_msg = (
                    f"🚨 PROTOCOLO RECUPERACIÓN\n"
                    f"Cliente: {loan.get('cliente_nombre', 'N/D')} | Cédula: {cedula}\n"
                    f"Moto: {modelo} | Chasis: {chasis}\n"
                    f"Adeuda: {_fmt_cop(total)} ({dpd} días de mora)\n"
                    f"Último contacto: {fecha_ult} ({resultado_ult})\n"
                    f"Loanbook: {loanbook_id}"
                )
                await _wa(ceo_number, ceo_msg, config)
                enviados += 1

        logger.info("[LoanScheduler] alertar_buckets_criticos: %d mensajes enviados", enviados)

    except Exception as e:
        logger.error("[LoanScheduler] alertar_buckets_criticos error: %s", e)


# ─── CRON 3: 06:10 AM — Despachar alertas CFO pendientes ─────────────────────

async def verificar_alertas_cfo() -> None:
    """Lee cfo_alertas[estado='nueva'] y las envía al CEO si whatsapp_activo=True."""
    from database import db

    try:
        cfo_config = await db.cfo_config.find_one({}, {"_id": 0}) or {}
        if not cfo_config.get("whatsapp_activo"):
            logger.info("[LoanScheduler] verificar_alertas_cfo: whatsapp_activo=False — omitiendo")
            return

        mercately_cfg = await _get_mercately_config()
        if not mercately_cfg.get("api_key"):
            logger.info("[LoanScheduler] verificar_alertas_cfo: sin API key Mercately")
            return

        ceo_number = (
            cfo_config.get("whatsapp_ceo")
            or mercately_cfg.get("ceo_number")
            or ""
        )
        if not ceo_number:
            logger.info("[LoanScheduler] verificar_alertas_cfo: sin número CEO configurado")
            return

        # Alertas pendientes (estado=nueva o sin campo estado = retrocompat)
        alertas = await db.cfo_alertas.find(
            {"resuelta": False,
             "$or": [{"estado": "nueva"}, {"estado": {"$exists": False}}]},
            {"_id": 0, "id": 1, "dimension": 1, "mensaje": 1, "color": 1, "urgencia": 1},
        ).sort("urgencia", -1).to_list(20)

        if not alertas:
            logger.info("[LoanScheduler] verificar_alertas_cfo: sin alertas pendientes")
            return

        from routers.mercately import enviar_whatsapp
        now_iso  = datetime.now(timezone.utc).isoformat()
        enviados = 0

        for alerta in alertas:
            color_emoji = {"ROJO": "🔴", "AMARILLO": "🟡"}.get(alerta.get("color", ""), "⚠️")
            msg = (
                f"{color_emoji} ALERTA CFO — {alerta.get('dimension', '').upper()}\n"
                f"{alerta.get('mensaje', '')}"
            )
            ok = await enviar_whatsapp(ceo_number, msg[:1000])
            if ok:
                enviados += 1
                await db.cfo_alertas.update_one(
                    {"id": alerta["id"]},
                    {"$set": {"estado": "enviada", "enviada_en": now_iso}},
                )

        logger.info("[LoanScheduler] verificar_alertas_cfo: %d alertas enviadas", enviados)

    except Exception as e:
        logger.error("[LoanScheduler] verificar_alertas_cfo error: %s", e)


# ─── CRON 4: 06:30 AM — Scores + PTP follow-up ───────────────────────────────

async def calcular_scores() -> None:
    """Calcula score A+..E, estrella_nivel y envía recordatorio PTP si es fecha de hoy."""
    from database import db

    try:
        today_str = date.today().isoformat()
        now_iso   = datetime.now(timezone.utc).isoformat()

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora", "recuperacion"]}},
            {"_id": 0, "id": 1, "dpd_actual": 1, "dpd_maximo_historico": 1,
             "cuotas": 1, "gestiones": 1,
             "cliente_nombre": 1, "cliente_telefono": 1,
             "ptp_fecha": 1, "ptp_monto": 1},
        ).to_list(5000)

        # Config WA cargado una sola vez para PTP
        ptp_config = await _get_mercately_config()

        updated = 0
        for loan in loans:
            loan_id   = loan["id"]
            dpd       = loan.get("dpd_actual", 0)
            dpd_max   = loan.get("dpd_maximo_historico", 0)
            cuotas    = loan.get("cuotas", [])
            gestiones = loan.get("gestiones", [])

            historial_vencidas = [
                c for c in cuotas
                if c.get("estado") == "pagada" and (c.get("dpd_al_pagar") or 0) > 0
            ]

            total_g           = max(len(gestiones), 1)
            no_contesto       = sum(1 for g in gestiones if g.get("resultado") == "no_contestó")
            no_contesto_ratio = no_contesto / total_g

            ptp_total     = sum(1 for g in gestiones if g.get("resultado") == "prometió_pago")
            ptp_cumplidos = sum(1 for g in gestiones if g.get("ptp_fue_cumplido") is True)
            ptp_ratio     = ptp_cumplidos / max(ptp_total, 1)

            if dpd >= 22:
                score = "E"
                estrellas = 0
            elif dpd >= 15 or dpd_max >= 22:
                score = "D"
                estrellas = 1
            elif dpd >= 8 or (len(historial_vencidas) >= 3 and no_contesto_ratio > 0.5):
                score = "C"
                estrellas = 2
            elif dpd >= 1:
                score = "B" if ptp_ratio >= 0.8 else "C"
                estrellas = 3 if ptp_ratio >= 0.8 else 2
            elif len(historial_vencidas) == 0 and no_contesto_ratio < 0.1:
                score = "A+"
                estrellas = 5
            else:
                score = "A"
                estrellas = 4

            score_entry = {
                "fecha": today_str, "score": score,
                "estrellas": estrellas, "dpd_actual": dpd,
                "calculado_por": "scheduler",
            }

            await db.loanbook.update_one(
                {"id": loan_id},
                {
                    "$set": {"score_pago": score, "estrella_nivel": estrellas,
                              "updated_at": now_iso},
                    "$push": {"score_historial": score_entry},
                },
            )
            updated += 1

            # ── PTP Follow-up ────────────────────────────────────────────────
            ptp_fecha = loan.get("ptp_fecha", "")
            ptp_monto = loan.get("ptp_monto", 0)
            tel       = loan.get("cliente_telefono", "")
            if ptp_fecha == today_str and tel and ptp_monto:
                nombre = _nombre_corto(loan.get("cliente_nombre", ""))
                msg = (
                    f"Hola {nombre}, hoy es la fecha en que acordaste realizar tu pago de "
                    f"{_fmt_cop(ptp_monto)}. Recuerda enviarnos el comprobante. ¡Contamos contigo! 🙏"
                )
                await _wa(tel, msg, ptp_config)

        logger.info("[LoanScheduler] calcular_scores: %d loans procesados", updated)

    except Exception as e:
        logger.error("[LoanScheduler] calcular_scores error: %s", e)


# ─── CRON 5: 07:00 AM — Cola RADAR ───────────────────────────────────────────

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


# ─── CRON 6: Martes 09:00 AM — Recordatorio preventivo ───────────────────────

async def recordatorio_preventivo() -> None:
    """Envía WA a clientes cuya cuota vence MAÑANA (miércoles)."""
    from database import db

    try:
        config = await _get_mercately_config()
        if not config.get("api_key"):
            logger.info("[LoanScheduler] recordatorio_preventivo: sin API key — solo log")
            return

        manana     = (date.today() + timedelta(days=1)).isoformat()
        fecha_fmt  = _fmtfecha(manana)

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "cliente_nombre": 1, "cliente_telefono": 1,
             "moto_descripcion": 1, "cuotas": 1},
        ).to_list(5000)

        enviados = 0
        for loan in loans:
            tel = loan.get("cliente_telefono", "")
            if not tel:
                continue
            for cuota in loan.get("cuotas", []):
                if (cuota.get("fecha_vencimiento") == manana
                        and cuota.get("estado") == "pendiente"):
                    nombre = _nombre_corto(loan.get("cliente_nombre", ""))
                    modelo = (loan.get("moto_descripcion", "") or "la moto").strip()
                    valor  = cuota.get("valor", 0)
                    msg = (
                        f"Hola {nombre} 👋, mañana miércoles {fecha_fmt} vence tu cuota "
                        f"#{cuota['numero']} por {_fmt_cop(valor)} de tu {modelo}. "
                        "Envíanos el comprobante cuando realices el pago. ¡Gracias!"
                    )
                    await _wa(tel, msg, config)
                    enviados += 1
                    break  # un mensaje por cliente

        logger.info("[LoanScheduler] recordatorio_preventivo: %d enviados", enviados)

    except Exception as e:
        logger.error("[LoanScheduler] recordatorio_preventivo error: %s", e)


# ─── CRON 7: Miércoles 09:00 AM — Recordatorio vencimiento ───────────────────

async def recordatorio_vencimiento() -> None:
    """Envía WA a clientes cuya cuota vence HOY."""
    from database import db

    try:
        config = await _get_mercately_config()
        if not config.get("api_key"):
            logger.info("[LoanScheduler] recordatorio_vencimiento: sin API key — solo log")
            return

        hoy       = date.today().isoformat()
        fecha_fmt = _fmtfecha(hoy)

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "cliente_nombre": 1, "cliente_telefono": 1, "cuotas": 1},
        ).to_list(5000)

        enviados = 0
        for loan in loans:
            tel = loan.get("cliente_telefono", "")
            if not tel:
                continue
            for cuota in loan.get("cuotas", []):
                if (cuota.get("fecha_vencimiento") == hoy
                        and cuota.get("estado") == "pendiente"):
                    nombre = _nombre_corto(loan.get("cliente_nombre", ""))
                    valor  = cuota.get("valor", 0)
                    msg = (
                        f"Hola {nombre}, hoy {fecha_fmt} vence tu cuota #{cuota['numero']} "
                        f"por {_fmt_cop(valor)}. Recuerda enviarnos el comprobante 📸. "
                        "¡Contamos contigo!"
                    )
                    await _wa(tel, msg, config)
                    enviados += 1
                    break

        logger.info("[LoanScheduler] recordatorio_vencimiento: %d enviados", enviados)

    except Exception as e:
        logger.error("[LoanScheduler] recordatorio_vencimiento error: %s", e)


# ─── CRON 8: Jueves 09:00 AM — Notificación mora nueva ───────────────────────

async def notificar_mora_nueva() -> None:
    """Envía WA a clientes con dpd_actual == 1 (no pagaron ayer)."""
    from database import db

    try:
        config = await _get_mercately_config()
        if not config.get("api_key"):
            logger.info("[LoanScheduler] notificar_mora_nueva: sin API key — solo log")
            return

        hoy_str = date.today().isoformat()

        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}, "dpd_actual": 1},
            {"_id": 0, "cliente_nombre": 1, "cliente_telefono": 1,
             "cuotas": 1, "valor_cuota": 1},
        ).to_list(500)

        enviados = 0
        for loan in loans:
            tel = loan.get("cliente_telefono", "")
            if not tel:
                continue

            cuotas_venc = [
                c for c in loan.get("cuotas", [])
                if c.get("estado") in ("vencida", "pendiente")
                and c.get("fecha_vencimiento", "") < hoy_str
            ]
            if cuotas_venc:
                cuota_obj = min(cuotas_venc, key=lambda c: c.get("fecha_vencimiento", ""))
                num_cuota = cuota_obj.get("numero", "?")
                valor     = float(cuota_obj.get("valor", loan.get("valor_cuota", 0)))
            else:
                num_cuota = "?"
                valor     = float(loan.get("valor_cuota", 0))

            nombre = _nombre_corto(loan.get("cliente_nombre", ""))
            msg = (
                f"Hola {nombre}, notamos que tu cuota #{num_cuota} de {_fmt_cop(valor)} "
                "aún no fue registrada. ¿Tuviste algún inconveniente? 🤔 Cuéntanos para ayudarte."
            )
            await _wa(tel, msg, config)
            enviados += 1

        logger.info("[LoanScheduler] notificar_mora_nueva: %d enviados", enviados)

    except Exception as e:
        logger.error("[LoanScheduler] notificar_mora_nueva error: %s", e)


# ─── CRON 9: Viernes 17:00 PM — Resumen semanal CEO ──────────────────────────

async def resumen_semanal_ceo() -> None:
    """Resumen enriquecido con semáforo 🟢/🟡/🔴, roll rate y top mora → CEO + destinatarios."""
    from database import db

    try:
        hoy   = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        vier  = lunes + timedelta(days=4)
        lunes_str = lunes.isoformat()
        vier_str  = vier.isoformat()

        # ── Cobrado vs esperado ───────────────────────────────────────────────
        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "cuotas": 1},
        ).to_list(5000)

        valor_esperado = valor_cobrado = 0.0
        for loan in loans:
            for c in loan.get("cuotas", []):
                fv = c.get("fecha_vencimiento", "")
                if lunes_str <= fv <= vier_str:
                    valor_esperado += c.get("valor", 0)
                    if c.get("estado") == "pagada":
                        valor_cobrado += c.get("valor_pagado", c.get("valor", 0))

        pct = round(valor_cobrado / valor_esperado * 100, 1) if valor_esperado > 0 else 0.0

        # ── Portfolio health ──────────────────────────────────────────────────
        from services.shared_state import get_portfolio_health
        ph            = await get_portfolio_health(db)
        cartera_total = ph.get("cartera_activa", 0)
        count_mora    = ph.get("en_mora", 0)
        tasa_mora     = ph.get("tasa_mora", 0.0)

        # ── Roll rate (últimos 7 días) ─────────────────────────────────────────
        hace_7 = (hoy - timedelta(days=7)).isoformat()
        BUCKET_ORDER = {"0": 0, "1-7": 1, "8-14": 2, "15-21": 3, "22+": 4}
        eventos_rr = await db.roddos_events.find(
            {"event_type": "loanbook.bucket_change",
             "timestamp": {"$gte": hace_7}},
            {"_id": 0, "entity_id": 1, "new_state": 1},
        ).sort("timestamp", -1).to_list(2000)

        ultimo_bucket: dict[str, str] = {}
        for ev in reversed(eventos_rr):
            eid = ev.get("entity_id", "")
            if eid and eid not in ultimo_bucket:
                ultimo_bucket[eid] = ev.get("new_state", "0")

        worsened  = sum(1 for ns in ultimo_bucket.values() if BUCKET_ORDER.get(ns, 0) >= 2)
        roll_rate = round(worsened / max(len(ultimo_bucket), 1) * 100, 1) if ultimo_bucket else 0.0

        # ── Top 2 clientes en mora ─────────────────────────────────────────────
        top2 = await db.loanbook.find(
            {"estado": "mora"},
            {"_id": 0, "cliente_nombre": 1, "dpd_actual": 1},
        ).sort("dpd_actual", -1).to_list(2)

        if len(top2) >= 2:
            top_mora_str = (
                f"{_nombre_corto(top2[0]['cliente_nombre'])} ({top2[0].get('dpd_actual', 0)}d) | "
                f"{_nombre_corto(top2[1]['cliente_nombre'])} ({top2[1].get('dpd_actual', 0)}d)"
            )
        elif len(top2) == 1:
            top_mora_str = f"{_nombre_corto(top2[0]['cliente_nombre'])} ({top2[0].get('dpd_actual', 0)}d)"
        else:
            top_mora_str = "Sin mora activa"

        # ── Semáforo ──────────────────────────────────────────────────────────
        if tasa_mora < 5 and pct >= 80:
            semaforo = "🟢"
        elif tasa_mora > 15 or pct < 50:
            semaforo = "🔴"
        else:
            semaforo = "🟡"

        resumen_texto = (
            f"{semaforo} Resumen RODDOS — semana {lunes_str}\n"
            f"💰 Cobrado: {_fmt_cop(valor_cobrado)} de {_fmt_cop(valor_esperado)} ({pct:.0f}%)\n"
            f"📊 Cartera activa: {_fmt_cop(cartera_total)}\n"
            f"⚠️ En mora: {count_mora} clientes ({tasa_mora:.1f}%)\n"
            f"🔄 Roll Rate: {roll_rate:.0f}% (meta: <15%)\n"
            f"📋 Top mora: {top_mora_str}"
        )

        logger.info("[LoanScheduler] resumen_semanal_ceo: %s", resumen_texto[:200])

        config = await _get_mercately_config()
        if not config.get("api_key"):
            logger.info("[LoanScheduler] resumen_semanal_ceo: sin API key — solo log")
            return

        from routers.mercately import enviar_whatsapp

        # CEO principal
        ceo_number = config.get("ceo_number", "")
        if ceo_number:
            ok = await enviar_whatsapp(ceo_number, resumen_texto)
            logger.info("[LoanScheduler] Resumen CEO → %s: %s", ceo_number, "OK" if ok else "FAIL")

        # Resto de destinatarios (evitar duplicado si ceo_number también está en la lista)
        for numero in config.get("destinatarios_resumen", []):
            if numero != ceo_number:
                await enviar_whatsapp(numero, resumen_texto)

    except Exception as e:
        logger.error("[LoanScheduler] resumen_semanal_ceo error: %s", e)


# ─── Ciclo de vida ────────────────────────────────────────────────────────────

def start_loanbook_scheduler() -> None:
    """Registra los 9 CRON jobs y arranca el scheduler."""
    _jobs = [
        (calcular_dpd_todos,       {"hour": 6, "minute": 0},                        "calcular_dpd_todos"),
        (alertar_buckets_criticos, {"hour": 6, "minute": 5},                        "alertar_buckets_criticos"),
        (verificar_alertas_cfo,    {"hour": 6, "minute": 10},                       "verificar_alertas_cfo"),
        (calcular_scores,          {"hour": 6, "minute": 30},                       "calcular_scores"),
        (generar_cola_radar,       {"hour": 7, "minute": 0},                        "generar_cola_radar"),
        (recordatorio_preventivo,  {"day_of_week": "tue", "hour": 9, "minute": 0},  "recordatorio_preventivo"),
        (recordatorio_vencimiento, {"day_of_week": "wed", "hour": 9, "minute": 0},  "recordatorio_vencimiento"),
        (notificar_mora_nueva,     {"day_of_week": "thu", "hour": 9, "minute": 0},  "notificar_mora_nueva"),
        (resumen_semanal_ceo,      {"day_of_week": "fri", "hour": 17, "minute": 0}, "resumen_semanal_ceo"),
    ]

    for func, kwargs, job_id in _jobs:
        _loanbook_scheduler.add_job(
            func, trigger="cron",
            id=job_id, replace_existing=True,
            max_instances=1, misfire_grace_time=300,
            **kwargs,
        )

    _loanbook_scheduler.start()
    logger.info(
        "[LoanScheduler] Iniciado — 9 jobs: "
        "DPD@06:00 · Buckets@06:05 · CFO@06:10 · "
        "Scores@06:30 · RADAR@07:00 · "
        "Prev@Mar09:00 · Venc@Mié09:00 · Mora@Jue09:00 · Resumen@Vie17:00 (America/Bogota)"
    )


def stop_loanbook_scheduler() -> None:
    """Detiene el scheduler limpiamente."""
    if _loanbook_scheduler.running:
        _loanbook_scheduler.shutdown(wait=False)
        logger.info("[LoanScheduler] Detenido")
