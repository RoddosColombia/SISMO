"""Mercately WhatsApp webhook + notification service for RODDOS.

Webhook URL: POST /api/mercately/webhook  (public — no JWT)
Sender types: CLIENTE | INTERNO | DESCONOCIDO
Flows: comprobante de pago (cliente), factura proveedor (interno), confirmación SI/NO,
       mensajes libres con detección de intención, templates automáticos (5 tipos)
"""
import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, Query, Request

from dependencies import get_current_user
from ai_chat import execute_chat_action, process_document_chat, process_chat
from database import db

router = APIRouter(prefix="/mercately", tags=["mercately"])

MERCATELY_API = "https://api.mercately.com/api/v1"
SESSION_TTL_MINUTES = 5

_CONFIRMATION_WORDS = {"si", "sí", "yes", "confirmar", "confirm", "ok", "listo", "dale"}
_CANCEL_WORDS = {"no", "cancelar", "cancel"}

# ── Intent detection para mensajes libres de CLIENTES ─────────────────────────
_SALDO_WORDS = ["cuanto debo", "cuánto debo", "mi saldo", "cuantas cuotas", "cuántas cuotas",
                "cuanto me falta", "mi deuda", "saldo", "cuanto queda", "cuánto queda",
                "cuotas me quedan", "que debo"]
_PAGO_WORDS = ["ya pagué", "ya pague", "hice la transferencia", "te mando el comprobante",
               "pague", "pagué", "transferi", "transferí", "consigne", "consigné",
               "ya abonė", "ya abonе", "realicé el pago", "realice el pago"]
_DIFICULTAD_WORDS = ["no puedo pagar", "no puedo", "estoy complicado", "dame más tiempo",
                     "mas tiempo", "más tiempo", "acuerdo de pago", "no tengo", "plazo",
                     "difícil", "dificil", "problema con el pago", "no hay"]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_config() -> dict:
    return await db.mercately_config.find_one({}, {"_id": 0}) or {}


def _fmt(n) -> str:
    """Format number as Colombian peso string: $1.200.000"""
    try:
        return f"${int(n or 0):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


def _normalize_phone(phone: str) -> str:
    """Normalize Colombian phone numbers to +57XXXXXXXXXX format."""
    from services.crm_service import normalizar_telefono
    return normalizar_telefono(phone)


async def _get_telefono_roddos() -> str:
    """Return RODDOS contact number from config."""
    cfg = await _get_config()
    return cfg.get("phone_number") or "3001234567"


async def _get_loan_by_cliente(cliente: dict) -> dict | None:
    """Find active loanbook entry for a CRM client."""
    if not cliente:
        return None
    cedula = cliente.get("cedula") or ""
    telefono = cliente.get("telefono_principal") or ""
    query = {"estado": "activo"}
    if cedula:
        query["cliente_nit"] = cedula
    elif telefono:
        query["cliente_telefono"] = {"$regex": telefono[-10:]}
    return await db.loanbook.find_one(query, {"_id": 0}) if (cedula or telefono) else None


async def _get_proxima_cuota(loan: dict) -> dict | None:
    """Return next pending cuota from loanbook."""
    if not loan:
        return None
    cuotas = loan.get("cuotas") or []
    for c in cuotas:
        if c.get("estado") in ("pendiente", "vencido"):
            return c
    return None


async def _log_gestion_whatsapp(
    cliente: dict | None,
    tipo: str,
    template: str,
    mensaje: str,
    mercately_id: str = "",
    estado: str = "enviado",
    intencion: str = "",
):
    """Log WA message to cartera_gestiones collection."""
    try:
        nombre = ""
        cliente_id = ""
        if cliente:
            nombre = cliente.get("nombre_completo") or cliente.get("nombre") or ""
            cliente_id = cliente.get("cedula") or cliente.get("id") or ""
        await db.cartera_gestiones.insert_one({
            "cliente_id": cliente_id,
            "cliente_nombre": nombre,
            "fecha": datetime.now(timezone.utc).isoformat(),
            "canal": "whatsapp_mercately",
            "tipo": tipo,
            "template": template,
            "intencion": intencion,
            "mensaje": mensaje[:500],
            "estado": estado,
            "mercately_message_id": mercately_id,
        })
    except Exception as e:
        logger.warning("[Mercately] log_gestion error: %s", e)


async def _crear_alerta_cartera(cliente: dict | None, tipo: str, mensaje: str):
    """Create a priority alert in cartera for the given client."""
    try:
        nombre = (cliente or {}).get("nombre_completo") or (cliente or {}).get("nombre") or "Desconocido"
        await db.roddos_events.insert_one({
            "tipo": tipo,
            "canal": "whatsapp",
            "cliente_nombre": nombre,
            "cedula": (cliente or {}).get("cedula", ""),
            "mensaje": mensaje,
            "fecha": datetime.now(timezone.utc).isoformat(),
            "resuelto": False,
        })
    except Exception as e:
        logger.warning("[Mercately] alerta_cartera error: %s", e)


async def _handle_cliente_text(phone: str, cliente: dict | None, content: str):
    """Process free text from a CLIENTE with intent detection."""
    content_l = content.lower()
    nombre = ""
    if cliente:
        full = cliente.get("nombre_completo") or cliente.get("nombre") or ""
        nombre = full.split()[0] if full else "Cliente"
    if not nombre:
        nombre = "Cliente"

    loan = await _get_loan_by_cliente(cliente)
    proxima = await _get_proxima_cuota(loan)

    # Detect intent (ordered by priority)
    intencion = "NO_RECONOCIDA"
    for w in _SALDO_WORDS:
        if w in content_l:
            intencion = "SALDO"
            break
    if intencion == "NO_RECONOCIDA":
        for w in _PAGO_WORDS:
            if w in content_l:
                intencion = "PAGO"
                break
    if intencion == "NO_RECONOCIDA":
        for w in _DIFICULTAD_WORDS:
            if w in content_l:
                intencion = "DIFICULTAD"
                break

    telefono_roddos = await _get_telefono_roddos()
    respuesta = ""

    if intencion == "SALDO" and loan:
        pagadas = loan.get("num_cuotas_pagadas", 0)
        total = loan.get("num_cuotas", 0)
        saldo = loan.get("saldo_pendiente", 0)
        cuota_valor = proxima.get("valor", loan.get("cuota_valor", 0)) if proxima else loan.get("cuota_valor", 0)
        fecha_prox = proxima.get("fecha_vencimiento", "próximo miércoles") if proxima else "próximo miércoles"
        respuesta = (
            f"Hola {nombre} 👋\n"
            f"Tu saldo actual es:\n"
            f"• Cuotas pagadas: {pagadas} de {total}\n"
            f"• Saldo pendiente: {_fmt(saldo)}\n"
            f"• Próxima cuota: {fecha_prox} — {_fmt(cuota_valor)}\n"
            f"¡Cualquier duda estamos aquí! — RODDOS 🏍️"
        )
    elif intencion == "SALDO":
        respuesta = (
            f"Hola {nombre} 👋\n"
            f"No encontré tu crédito activo. Por favor comunícate:\n"
            f"📞 {telefono_roddos}\n"
            f"— RODDOS 🏍️"
        )
    elif intencion == "PAGO":
        respuesta = (
            f"Hola {nombre}, recibimos tu mensaje 👋\n"
            f"En breve verificamos tu pago y te confirmamos.\n"
            f"Si tienes el comprobante, puedes enviarlo aquí mismo. — RODDOS 🏍️"
        )
        await _crear_alerta_cartera(
            cliente, "pago_reportado_whatsapp",
            f"📱 {nombre} reportó pago por WhatsApp — pendiente verificación"
        )
    elif intencion == "DIFICULTAD":
        respuesta = (
            f"Hola {nombre}, entendemos que hay momentos difíciles.\n"
            f"Comunícate con nosotros hoy:\n"
            f"📞 {telefono_roddos}\n"
            f"Buscaremos la mejor solución juntos. — RODDOS"
        )
        await _crear_alerta_cartera(
            cliente, "dificultad_pago_whatsapp",
            f"📱 {nombre} reportó dificultad de pago por WhatsApp — gestión prioritaria"
        )
    else:
        respuesta = (
            f"Hola {nombre} 👋 Recibimos tu mensaje.\n"
            f"Un asesor de RODDOS te contactará pronto.\n"
            f"Si es urgente llámanos: 📞 {telefono_roddos} — RODDOS"
        )

    sent = await enviar_whatsapp(phone, respuesta)
    await _log_gestion_whatsapp(
        cliente=cliente,
        tipo="recibido",
        template="libre",
        mensaje=content[:500],
        estado="procesado",
        intencion=intencion,
    )
    if sent:
        await _log_gestion_whatsapp(
            cliente=cliente,
            tipo="enviado",
            template="respuesta_automatica",
            mensaje=respuesta[:500],
            estado="enviado",
            intencion=intencion,
        )


async def _is_template_activo(template_key: str) -> bool:
    """Check if a specific template is enabled in config. Defaults to True."""
    cfg = await _get_config()
    if not cfg.get("global_activo", True):
        return False
    templates = cfg.get("templates_activos", {})
    return templates.get(template_key, True)


# ── Templates automáticos ─────────────────────────────────────────────────────

async def enviar_template_1_preventivo(loan: dict) -> bool:
    """Template 1: Recordatorio D-2 (lunes, 2 días antes del miércoles)."""
    if not await _is_template_activo("T1"):
        return False
    telefono = loan.get("cliente_telefono") or ""
    if not telefono:
        return False
    nombre = (loan.get("cliente_nombre") or "Cliente").split()[0]
    moto = loan.get("moto_descripcion") or "tu moto"
    proxima = await _get_proxima_cuota(loan)
    if not proxima:
        return False
    num = proxima.get("numero", "?")
    fecha = proxima.get("fecha_vencimiento", "el miércoles")
    monto = _fmt(proxima.get("valor", loan.get("cuota_valor", 0)))

    msg = (
        f"Hola {nombre}, te recordamos que tu cuota #{num} "
        f"de {moto} vence el próximo miércoles {fecha} por {monto}.\n"
        f"¡Recuerda tenerla lista! — RODDOS 🏍️"
    )
    sent = await enviar_whatsapp(telefono, msg)
    if sent:
        await _log_gestion_whatsapp(
            cliente={"nombre_completo": loan.get("cliente_nombre"), "cedula": loan.get("cliente_nit")},
            tipo="enviado", template="recordatorio_preventivo",
            mensaje=msg, estado="enviado"
        )
    return sent


async def enviar_template_2_vencimiento(loan: dict) -> bool:
    """Template 2: Recordatorio D-0 (miércoles 8am, día de vencimiento)."""
    if not await _is_template_activo("T2"):
        return False
    telefono = loan.get("cliente_telefono") or ""
    if not telefono:
        return False
    nombre = (loan.get("cliente_nombre") or "Cliente").split()[0]
    proxima = await _get_proxima_cuota(loan)
    if not proxima:
        return False
    num = proxima.get("numero", "?")
    monto = _fmt(proxima.get("valor", loan.get("cuota_valor", 0)))
    cfg = await _get_config()
    datos_bancarios = cfg.get("datos_bancarios") or "Nuestras cuentas bancarias"

    msg = (
        f"Hola {nombre}, hoy vence tu cuota #{num} por {monto}.\n"
        f"Puedes pagar por transferencia a:\n{datos_bancarios}\n"
        f"¡Gracias por tu puntualidad! — RODDOS 🏍️"
    )
    sent = await enviar_whatsapp(telefono, msg)
    if sent:
        await _log_gestion_whatsapp(
            cliente={"nombre_completo": loan.get("cliente_nombre"), "cedula": loan.get("cliente_nit")},
            tipo="enviado", template="vencimiento_hoy",
            mensaje=msg, estado="enviado"
        )
    return sent


async def enviar_template_3_mora_d1(loan: dict) -> bool:
    """Template 3: Alerta mora D+1 (jueves, si el miércoles no pagó)."""
    if not await _is_template_activo("T3"):
        return False
    telefono = loan.get("cliente_telefono") or ""
    if not telefono:
        return False
    nombre = (loan.get("cliente_nombre") or "Cliente").split()[0]
    proxima = await _get_proxima_cuota(loan)
    if not proxima:
        return False
    num = proxima.get("numero", "?")
    monto = _fmt(proxima.get("valor", loan.get("cuota_valor", 0)))
    fecha_venc = proxima.get("fecha_vencimiento", "ayer")

    msg = (
        f"Hola {nombre}, tu cuota #{num} por {monto} "
        f"quedó pendiente desde el miércoles {fecha_venc}.\n"
        f"Para evitar inconvenientes comunícate hoy con nosotros. — RODDOS 🏍️"
    )
    sent = await enviar_whatsapp(telefono, msg)
    if sent:
        await _log_gestion_whatsapp(
            cliente={"nombre_completo": loan.get("cliente_nombre"), "cedula": loan.get("cliente_nit")},
            tipo="enviado", template="mora_d1",
            mensaje=msg, estado="enviado"
        )
    return sent


async def enviar_template_4_confirmacion_pago(
    nombre_cliente: str, telefono: str, monto: float,
    numero_cuota: int, saldo_pendiente: float,
    cedula: str = ""
) -> bool:
    """Template 4: Confirmación de pago (disparado al registrar pago)."""
    if not await _is_template_activo("T4"):
        return False
    if not telefono:
        return False
    nombre = nombre_cliente.split()[0] if nombre_cliente else "Cliente"
    msg = (
        f"✅ Hola {nombre}, recibimos tu pago de {_fmt(monto)} "
        f"para la cuota #{numero_cuota}.\n"
        f"Saldo restante: {_fmt(saldo_pendiente)}.\n"
        f"¡Gracias! — RODDOS 🏍️"
    )
    sent = await enviar_whatsapp(telefono, msg)
    if sent:
        await _log_gestion_whatsapp(
            cliente={"nombre_completo": nombre_cliente, "cedula": cedula},
            tipo="enviado", template="confirmacion_pago",
            mensaje=msg, estado="enviado"
        )
    return sent


async def enviar_template_5_mora_severa(loan: dict) -> bool:
    """Template 5: Mora severa +30 días."""
    if not await _is_template_activo("T5"):
        return False
    telefono = loan.get("cliente_telefono") or ""
    if not telefono:
        return False
    nombre = (loan.get("cliente_nombre") or "Cliente").split()[0]
    dpd = loan.get("dpd_actual", 0)
    vencidas = [c for c in (loan.get("cuotas") or []) if c.get("estado") == "vencido"]
    monto_vencido = _fmt(sum(c.get("valor", 0) for c in vencidas))
    n_vencidas = len(vencidas)
    fecha_primera = vencidas[0].get("fecha_vencimiento", "") if vencidas else ""
    cfg = await _get_config()
    telefono_roddos = cfg.get("phone_number") or "3001234567"

    msg = (
        f"Hola {nombre}, tienes {n_vencidas} cuota{'s' if n_vencidas != 1 else ''} pendiente{'s' if n_vencidas != 1 else ''} "
        f"por un total de {monto_vencido} desde {fecha_primera}.\n"
        f"Es importante que te comuniques con nosotros hoy para buscar una solución.\n"
        f"📞 {telefono_roddos} — RODDOS 🏍️"
    )
    sent = await enviar_whatsapp(telefono, msg)
    if sent:
        await _log_gestion_whatsapp(
            cliente={"nombre_completo": loan.get("cliente_nombre"), "cedula": loan.get("cliente_nit")},
            tipo="enviado", template="mora_severa",
            mensaje=msg, estado="enviado"
        )
    return sent


# ── Template scheduler trigger functions ─────────────────────────────────────

async def run_recordatorios_preventivos() -> int:
    """Lunes 8am — Template 1: send D-2 reminder to clients with cuota due this Wednesday."""
    from datetime import date
    today = date.today()
    # Wednesday = weekday 2; from Monday (weekday 0), Wednesday is in 2 days
    wed = today + timedelta(days=2)
    wed_str = wed.strftime("%Y-%m-%d")
    sent = 0
    async for loan in db.loanbook.find({"estado": "activo"}, {"_id": 0}):
        for cuota in (loan.get("cuotas") or []):
            if cuota.get("estado") == "pendiente" and cuota.get("fecha_vencimiento") == wed_str:
                if await enviar_template_1_preventivo(loan):
                    sent += 1
                break
    logger.info("[Mercately] T1 preventivo: %d enviados para %s", sent, wed_str)
    return sent


async def run_recordatorios_vencimiento() -> int:
    """Miércoles 8am — Template 2: send D-0 reminder to clients with cuota due today."""
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    sent = 0
    async for loan in db.loanbook.find({"estado": "activo"}, {"_id": 0}):
        for cuota in (loan.get("cuotas") or []):
            if cuota.get("estado") == "pendiente" and cuota.get("fecha_vencimiento") == today:
                if await enviar_template_2_vencimiento(loan):
                    sent += 1
                break
    logger.info("[Mercately] T2 vencimiento: %d enviados para %s", sent, today)
    return sent


async def run_alertas_mora_d1() -> int:
    """Jueves 9am — Template 3: alert for loans where yesterday's cuota wasn't paid."""
    from datetime import date
    ayer = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    sent = 0
    async for loan in db.loanbook.find({"estado": "activo"}, {"_id": 0}):
        for cuota in (loan.get("cuotas") or []):
            if cuota.get("estado") == "vencido" and cuota.get("fecha_vencimiento") == ayer:
                if await enviar_template_3_mora_d1(loan):
                    sent += 1
                break
    logger.info("[Mercately] T3 mora D+1: %d enviados", sent)
    return sent


async def run_alertas_mora_severa() -> int:
    """Weekly — Template 5: alert clients with dpd > 30."""
    sent = 0
    async for loan in db.loanbook.find({"estado": "activo", "dpd_actual": {"$gt": 30}}, {"_id": 0}):
        if await enviar_template_5_mora_severa(loan):
            sent += 1
    logger.info("[Mercately] T5 mora severa: %d enviados", sent)
    return sent




async def enviar_whatsapp(phone: str, mensaje: str) -> bool:
    """Send a WhatsApp message via Mercately. Returns True on success. Never raises."""
    try:
        cfg = await _get_config()
        api_key = cfg.get("api_key", "")
        if not api_key:
            logger.warning("[Mercately] No API key configured — message not sent to %s", phone)
            return False
        # Check global toggle
        if not cfg.get("global_activo", True):
            logger.info("[Mercately] Canal globalmente desactivado — message skipped for %s", phone)
            return False
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{MERCATELY_API}/customers/send_message",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"phone": phone, "message": mensaje},
            )
            if resp.status_code not in (200, 201):
                logger.warning("[Mercately] Send failed %s: %s", resp.status_code, resp.text[:200])
                return False
        return True
    except Exception as exc:
        logger.error("[Mercately] enviar_whatsapp error: %s", exc)
        return False


async def _descargar_media(url: str) -> bytes:
    """Download media from URL. Raises httpx errors on failure."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _detect_sender(phone: str, whitelist: list) -> tuple:
    """Returns (tipo, cliente_doc).
    tipo: 'CLIENTE' | 'INTERNO' | 'DESCONOCIDO'
    cliente_doc: crm_clientes document or None.
    """
    norm = _normalize_phone(phone)
    norm_whitelist = [_normalize_phone(w) for w in whitelist]
    if norm in norm_whitelist:
        return "INTERNO", None

    # Direct match (all DB entries should be +57... after migration)
    cliente = await db.crm_clientes.find_one(
        {"telefono_principal": norm}, {"_id": 0}
    )
    if cliente:
        return "CLIENTE", cliente

    # Fallback: match by last 10 digits (handles any remaining legacy formats)
    digits10 = norm[-10:]
    cliente = await db.crm_clientes.find_one(
        {"telefono_principal": {"$regex": digits10}}, {"_id": 0}
    )
    if cliente:
        return "CLIENTE", cliente
    return "DESCONOCIDO", None


async def _get_active_session(phone: str) -> dict | None:
    """Return active non-expired session for phone, or None."""
    session = await db.mercately_sessions.find_one({"phone": phone}, {"_id": 0})
    if not session:
        return None
    expires_at = session.get("expires_at")
    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        if datetime.now(timezone.utc) > exp:
            await db.mercately_sessions.delete_one({"phone": phone})
            return None
    return session


async def _save_session(phone: str, data: dict):
    """Upsert session with 5-minute TTL."""
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)
    ).isoformat()
    await db.mercately_sessions.update_one(
        {"phone": phone},
        {"$set": {"phone": phone, "expires_at": expires_at,
                  "created_at": datetime.now(timezone.utc).isoformat(), **data}},
        upsert=True,
    )


async def _clear_session(phone: str):
    await db.mercately_sessions.delete_one({"phone": phone})


async def _get_admin() -> dict | None:
    return await db.users.find_one({"role": "admin"}, {"_id": 0, "id": 1, "email": 1, "name": 1})


# ── CLIENT flows ──────────────────────────────────────────────────────────────

async def _handle_cliente_media(phone: str, cliente: dict, media_url: str, content: str):
    """Download comprobante → analyze with Claude → propose payment matching."""
    await enviar_whatsapp(phone, "🔍 Analizando tu comprobante de pago...")
    try:
        file_bytes = await _descargar_media(media_url)
        file_b64 = base64.b64encode(file_bytes).decode()
        url_lower = media_url.lower()
        mime = "application/pdf" if ".pdf" in url_lower else "image/jpeg"
        fname = "comprobante.pdf" if ".pdf" in url_lower else "comprobante.jpg"

        admin = await _get_admin()
        if not admin:
            await enviar_whatsapp(phone, "Error interno: no hay administrador configurado.")
            return

        session_id = f"mercately-cli-{phone}-{uuid.uuid4().hex[:8]}"
        result = await process_document_chat(
            session_id, content or "Analiza este comprobante de pago bancario",
            file_b64, fname, mime, db, admin,
        )
        proposal = result.get("document_proposal")
        if not proposal:
            await enviar_whatsapp(phone, "No pude leer el comprobante. ¿Puedes enviarlo más nítido o en PDF?")
            return

        monto_comp = float(proposal.get("total") or proposal.get("subtotal") or 0)
        fecha_comp = proposal.get("fecha") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        referencia = proposal.get("numero_documento") or f"WA-{uuid.uuid4().hex[:6].upper()}"
        banco = proposal.get("proveedor_cliente") or "banco"
        nombre_cliente = (cliente.get("nombre") or cliente.get("cliente_nombre") or "").split()[0]

        # Duplicate check by referencia_wa
        if not referencia.startswith("WA-"):
            existing = await db.cartera_pagos.find_one({"referencia_wa": referencia}, {"_id": 0})
            if existing:
                cuota_info = f"Cuota #{existing.get('cuota_numero', '?')}"
                fecha_pago = existing.get("fecha_pago", "")
                await enviar_whatsapp(
                    phone,
                    f"⚠️ Este comprobante ya fue registrado.\n"
                    f"📋 {cuota_info} pagada el {fecha_pago}.\n"
                    "Si crees que es un error, escríbenos.",
                )
                return

        # Find active loanbook for this client
        cliente_id = cliente.get("id", "")
        loan = await db.loanbook.find_one(
            {
                "$or": [
                    {"cliente_id": cliente_id},
                    {"cliente_telefono": {"$regex": phone[-10:]}},
                ],
                "estado": {"$in": ["activo", "mora"]},
            },
            {"_id": 0},
        )
        if not loan:
            await enviar_whatsapp(
                phone,
                f"Hola {nombre_cliente}, no encontré un crédito activo asociado a tu número.\n"
                "Escríbenos al WhatsApp principal para ayudarte.",
            )
            return

        cuotas = loan.get("cuotas", [])
        cuota_pend = next((c for c in cuotas if c["estado"] in ("pendiente", "vencida")), None)
        if not cuota_pend:
            await enviar_whatsapp(
                phone,
                f"Hola {nombre_cliente}, no tienes cuotas pendientes. ¡Gracias por tu puntualidad! 🎉",
            )
            return

        cuota_num = cuota_pend["numero"]
        cuota_valor = float(cuota_pend.get("valor") or loan.get("cuota_valor") or 0)
        moto_desc = (
            f"{loan.get('moto_marca', '')} {loan.get('moto_version', '')}".strip()
            or loan.get("moto_descripcion", "tu moto")
        )
        fecha_fmt = (
            f"{fecha_comp[8:10]}/{fecha_comp[5:7]}/{fecha_comp[:4]}"
            if len(fecha_comp) >= 10 else fecha_comp
        )

        propuesta = (
            f"Hola {nombre_cliente}, veo un pago de {_fmt(monto_comp)} "
            f"del {fecha_fmt} en {banco}.\n"
            f"¿Corresponde a tu cuota #{cuota_num} de {_fmt(cuota_valor)} "
            f"del {moto_desc}?\n\n"
            "Responde *SI* para confirmar el registro."
        )
        diferencia = abs(monto_comp - cuota_valor)
        if diferencia > 1:
            if monto_comp < cuota_valor:
                propuesta += (
                    f"\n\n⚠️ El monto ({_fmt(monto_comp)}) es menor a la cuota ({_fmt(cuota_valor)}). "
                    "¿Es un pago parcial? Responde *SI* para registrar como abono."
                )
            else:
                propuesta += (
                    f"\n\n💡 El monto ({_fmt(monto_comp)}) supera la cuota ({_fmt(cuota_valor)}). "
                    "El excedente se aplicará a mora o siguiente cuota."
                )

        await _save_session(phone, {
            "tipo_remitente": "CLIENTE",
            "loanbook_id": loan["id"],
            "cuota_num": cuota_num,
            "monto_propuesto": monto_comp,
            "cuota_valor": cuota_valor,
            "factura_alegra_id": loan.get("factura_alegra_id", ""),
            "propuesta_texto": propuesta,
            "referencia": referencia,
            "fecha_pago": fecha_comp,
        })
        await enviar_whatsapp(phone, propuesta)

    except Exception as exc:
        logger.error("[Mercately] _handle_cliente_media error: %s", exc)
        await enviar_whatsapp(phone, "Ocurrió un error al procesar tu comprobante. Por favor intenta de nuevo.")


async def _handle_cliente_confirmacion(phone: str, session: dict):
    """Execute payment registration after client confirms with SI."""
    await enviar_whatsapp(phone, "⚙️ Registrando tu pago en el sistema...")
    try:
        factura_id = session.get("factura_alegra_id", "")
        monto = float(session.get("monto_propuesto", 0))
        fecha_pago = session.get("fecha_pago") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        loanbook_id = session.get("loanbook_id", "")
        referencia = session.get("referencia", "")

        if not factura_id or not monto:
            await enviar_whatsapp(phone, "No hay propuesta de pago activa. Envía el comprobante nuevamente.")
            await _clear_session(phone)
            return

        admin = await _get_admin()
        if not admin:
            await enviar_whatsapp(phone, "Error interno al registrar. Contacta al administrador.")
            return

        payload = {
            "date": fecha_pago,
            "type": "in",
            "invoices": [{"id": factura_id, "amount": monto}],
            "paymentMethod": "transfer",
        }
        exec_result = await execute_chat_action("registrar_pago", payload, db, admin)

        if not exec_result.get("success"):
            await enviar_whatsapp(phone, "No pude registrar el pago. Contacta al administrador.")
            await _clear_session(phone)
            return

        # Store referencia_wa for duplicate prevention
        if referencia and not referencia.startswith("WA-"):
            await db.cartera_pagos.update_one(
                {"loanbook_id": loanbook_id, "cuota_numero": session.get("cuota_num")},
                {"$set": {"referencia_wa": referencia}},
            )

        loan = await db.loanbook.find_one({"id": loanbook_id}, {"_id": 0})
        recibo = _build_recibo(loan, session)
        await enviar_whatsapp(phone, recibo)
        await _clear_session(phone)

    except Exception as exc:
        logger.error("[Mercately] _handle_cliente_confirmacion error: %s", exc)
        await enviar_whatsapp(phone, "Error al confirmar el pago. Contacta al administrador.")
        await _clear_session(phone)


def _build_recibo(loan: dict | None, session: dict) -> str:
    """Build digital receipt for client."""
    if not loan:
        return (
            "✅ Pago registrado correctamente.\n"
            f"💰 Total: {_fmt(session.get('monto_propuesto', 0))}\n"
            "¡Gracias! 🙏"
        )
    cuota_num = session.get("cuota_num", "?")
    monto_pagado = float(session.get("monto_propuesto", 0))
    cuota_valor = float(session.get("cuota_valor", monto_pagado))
    mora = max(0.0, monto_pagado - cuota_valor)
    capital = min(monto_pagado, cuota_valor)
    plan = loan.get("plan", "")
    num_cuotas = loan.get("num_cuotas", 0)
    pagadas = min(loan.get("num_cuotas_pagadas", 0) + 1, num_cuotas)
    nombre = (loan.get("cliente_nombre") or "").split()[0]
    moto_desc = (
        f"{loan.get('moto_marca', '')} {loan.get('moto_version', '')}".strip()
        or loan.get("moto_descripcion", "")
    )
    cuotas = loan.get("cuotas", [])
    proxima_fecha = next(
        (c.get("fecha_vencimiento", "") for c in cuotas
         if c.get("estado") in ("pendiente", "vencida") and c.get("numero", 0) > cuota_num),
        "",
    )
    proxima_fmt = ""
    if proxima_fecha and len(proxima_fecha) >= 10:
        proxima_fmt = f" | Próxima: miércoles {proxima_fecha[8:10]}/{proxima_fecha[5:7]}"

    lines = [
        "✅ Pago registrado correctamente.",
        f"📋 Cuota #{cuota_num} · {moto_desc} · Plan {plan}",
        f"💰 Capital: {_fmt(capital)} | Mora: {_fmt(mora)} | Total: {_fmt(monto_pagado)}",
        f"📅 Cuotas al día: {pagadas} de {num_cuotas}{proxima_fmt}",
        f"¡Gracias {nombre}! 🙏",
    ]
    return "\n".join(lines)


# ── INTERNAL flows ─────────────────────────────────────────────────────────────

async def _handle_interno_media(phone: str, media_url: str, content: str):
    """Download factura/documento → analyze → propose ExecutionCard via WhatsApp."""
    await enviar_whatsapp(phone, "🔍 Analizando el documento contable...")
    try:
        file_bytes = await _descargar_media(media_url)
        file_b64 = base64.b64encode(file_bytes).decode()
        url_lower = media_url.lower()
        mime = "application/pdf" if ".pdf" in url_lower else "image/jpeg"
        fname = "factura.pdf" if ".pdf" in url_lower else "factura.jpg"

        admin = await _get_admin()
        if not admin:
            await enviar_whatsapp(phone, "Error interno: no hay administrador configurado.")
            return

        session_id = f"mercately-int-{phone}-{uuid.uuid4().hex[:8]}"
        result = await process_document_chat(
            session_id,
            content or "Analiza esta factura de proveedor con todas sus retenciones aplicables",
            file_b64, fname, mime, db, admin,
        )
        proposal = result.get("document_proposal")
        pending_action = result.get("pending_action")
        text_resp = result.get("message", "")

        if not proposal:
            msg = (text_resp[:400] if text_resp else "No pude extraer datos del documento.")
            await enviar_whatsapp(phone, msg)
            return

        msg = _format_propuesta_interna(proposal, text_resp)
        await _save_session(phone, {
            "tipo_remitente": "INTERNO",
            "proposal_data": proposal,
            "pending_action": pending_action,
            "propuesta_texto": msg,
        })
        await enviar_whatsapp(phone, msg)

    except Exception as exc:
        logger.error("[Mercately] _handle_interno_media error: %s", exc)
        await enviar_whatsapp(phone, f"Error al analizar el documento: {str(exc)[:200]}")


def _format_propuesta_interna(proposal: dict, intro: str) -> str:
    """Format accounting proposal as WhatsApp ExecutionCard-style message."""
    _TIPO_LABELS = {
        "factura_compra": "Factura de Compra",
        "factura_venta": "Factura de Venta",
        "recibo_pago": "Recibo de Pago",
        "comprobante_egreso": "Comprobante de Egreso",
        "extracto_bancario": "Extracto Bancario",
    }
    tipo = _TIPO_LABELS.get(proposal.get("tipo_documento", ""), "Documento")
    lines = [f"📄 *{tipo} detectado*", ""]
    if intro:
        lines += [intro[:300], ""]
    if proposal.get("proveedor_cliente"):
        lines.append(f"🏢 Proveedor: {proposal['proveedor_cliente']}")
    if proposal.get("nit"):
        lines.append(f"🔢 NIT: {proposal['nit']}")
    if proposal.get("fecha"):
        lines.append(f"📅 Fecha: {proposal['fecha']}")
    if proposal.get("concepto"):
        lines.append(f"📝 {proposal['concepto']}")
    lines.append("")
    lines.append(f"💰 Subtotal: {_fmt(proposal.get('subtotal', 0))}")
    if float(proposal.get("iva_valor") or 0) > 0:
        lines.append(f"📊 IVA {proposal.get('iva_porcentaje', '')}%: {_fmt(proposal.get('iva_valor', 0))}")
    if float(proposal.get("retefuente_valor") or 0) > 0:
        lines.append(f"✂️ ReteFuente: {_fmt(proposal.get('retefuente_valor', 0))}")
    total = proposal.get("total") or proposal.get("subtotal") or 0
    lines.append(f"💵 *TOTAL: {_fmt(total)}*")
    if proposal.get("ilegible"):
        lines += ["", "⚠️ Datos incompletos — verifica en la app web antes de confirmar."]
    lines += [
        "", "─────────────────",
        "¿Registrar esto en Alegra?",
        "Responde *SI* para confirmar o *NO* para cancelar.",
    ]
    return "\n".join(lines)


async def _handle_interno_confirmacion(phone: str, session: dict):
    """Execute accounting action after internal user confirms with SI."""
    await enviar_whatsapp(phone, "⚙️ Ejecutando en Alegra...")
    try:
        pending_action = session.get("pending_action")
        if not pending_action or not pending_action.get("type") or not pending_action.get("payload"):
            await enviar_whatsapp(
                phone,
                "No hay acción ejecutable automáticamente.\n"
                "Usa la app web de RODDOS para completar este registro.",
            )
            await _clear_session(phone)
            return

        admin = await _get_admin()
        if not admin:
            await enviar_whatsapp(phone, "Error interno. Contacta al administrador.")
            await _clear_session(phone)
            return

        exec_result = await execute_chat_action(
            pending_action["type"], pending_action["payload"], db, admin
        )
        doc_id = (
            exec_result.get("id")
            or (exec_result.get("result") or {}).get("id")
            or ""
        )
        sync_msgs = (exec_result.get("sync") or {}).get("sync_messages", [])

        ok_msg = f"✅ *Registrado en Alegra*{f' — ID: {doc_id}' if doc_id else ''}"
        if sync_msgs:
            ok_msg += "\n" + "\n".join(str(m) for m in sync_msgs[:2])
        await enviar_whatsapp(phone, ok_msg)
        await _clear_session(phone)

    except Exception as exc:
        logger.error("[Mercately] _handle_interno_confirmacion error: %s", exc)
        await enviar_whatsapp(phone, "Error al ejecutar en Alegra. Intenta desde la app web.")
        await _clear_session(phone)


# ── Webhook endpoint ───────────────────────────────────────────────────────────

@router.post("/webhook")
async def mercately_webhook(request: Request):
    """Public webhook called by Mercately on incoming WhatsApp messages."""
    cfg = await _get_config()
    if not cfg or not cfg.get("api_key"):
        return {"ok": True}  # not configured — silently ignore

    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    phone = _normalize_phone(data.get("phone") or "")
    message_type = (data.get("message_type") or "text").lower()
    content = (data.get("content") or "").strip()
    media_url = data.get("media_url") or ""

    if not phone:
        return {"ok": True}

    whitelist = cfg.get("whitelist", [])
    tipo_remitente, cliente = await _detect_sender(phone, whitelist)

    # ── DESCONOCIDO ──────────────────────────────────────────────────────────
    if tipo_remitente == "DESCONOCIDO":
        await enviar_whatsapp(
            phone,
            "Hola, soy el asistente de RODDOS Motos.\n"
            "Para registrar un pago, tu número debe estar vinculado a un crédito activo.\n"
            "Escríbenos al número principal para más información.",
        )
        return {"ok": True}

    content_lower = content.lower()

    # ── CONFIRMACIÓN (SI / NO) ────────────────────────────────────────────────
    if message_type == "text":
        if content_lower in _CANCEL_WORDS:
            await _clear_session(phone)
            await enviar_whatsapp(phone, "Registro cancelado. Envía un nuevo documento cuando quieras.")
            return {"ok": True}

        if content_lower in _CONFIRMATION_WORDS:
            session = await _get_active_session(phone)
            if not session:
                hint = (
                    "Envía el comprobante de pago."
                    if tipo_remitente == "CLIENTE"
                    else "Envía la factura o documento a registrar."
                )
                await enviar_whatsapp(phone, f"No hay propuesta pendiente. {hint}")
                return {"ok": True}

            if tipo_remitente == "CLIENTE":
                await _handle_cliente_confirmacion(phone, session)
            else:
                await _handle_interno_confirmacion(phone, session)
            return {"ok": True}

    # ── MEDIA (imagen / PDF) ──────────────────────────────────────────────────
    is_media = message_type in ("image", "document", "audio", "video") or bool(media_url)
    if is_media and media_url:
        if tipo_remitente == "CLIENTE":
            await _handle_cliente_media(phone, cliente, media_url, content)
        else:
            await _handle_interno_media(phone, media_url, content)
        return {"ok": True}

    # ── TEXT query — route INTERNO through accounting agent ──────────────────
    if message_type == "text" and content and tipo_remitente == "INTERNO":
        admin = await _get_admin()
        if admin:
            session_id = f"mercately-int-{phone}"
            try:
                result = await process_chat(session_id, content, db, admin)
                response = result.get("message", "")
                if result.get("pending_action"):
                    response += "\n\n_(Para ejecutar esta acción confirma con *SI* o usa la app web)_"
                if response:
                    await enviar_whatsapp(phone, response[:1000])
                    # If pending_action exists, save it in session so SI confirms
                    if result.get("pending_action"):
                        await _save_session(phone, {
                            "tipo_remitente": "INTERNO",
                            "pending_action": result["pending_action"],
                            "proposal_data": None,
                            "propuesta_texto": response[:400],
                        })
            except Exception as exc:
                logger.error("[Mercately] text-to-AI error: %s", exc)

    return {"ok": True}


# ── Gestiones log endpoints ────────────────────────────────────────────────────

@router.get("/gestiones")
async def get_gestiones_log(limit: int = Query(50, le=200), current_user=Depends(get_current_user)):
    """Returns last N WhatsApp messages logged in cartera_gestiones."""
    docs = await db.cartera_gestiones.find({}, {"_id": 0}).sort("fecha", -1).limit(limit).to_list(limit)
    return {"gestiones": docs, "total": len(docs)}


@router.get("/gestiones/cliente/{cedula}")
async def get_gestiones_cliente(cedula: str, current_user=Depends(get_current_user)):
    """Returns WhatsApp history for a specific client (by cedula)."""
    docs = await db.cartera_gestiones.find(
        {"cliente_id": cedula}, {"_id": 0}
    ).sort("fecha", -1).limit(100).to_list(100)
    return {"gestiones": docs, "total": len(docs)}
