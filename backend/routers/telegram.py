"""Telegram Bot integration for RODDOS Contable IA.
Receives photos/documents → analyzes with Claude → proposes accounting entry → executes in Alegra.
"""
import base64
import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from ai_chat import execute_chat_action, process_chat, process_document_chat
from database import db
from dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])

TELEGRAM_API = "https://api.telegram.org"

TIPO_LABELS = {
    "factura_compra": "Factura de Compra",
    "factura_venta": "Factura de Venta",
    "recibo_pago": "Recibo de Pago",
    "comprobante_egreso": "Comprobante de Egreso",
    "extracto_bancario": "Extracto Bancario",
    "otro": "Documento",
}


# ── internal helpers ─────────────────────────────────────────────────────────

async def _get_config():
    return await db.telegram_config.find_one({}, {"_id": 0})


async def _send(token: str, chat_id: int, text: str):
    """Send a plain HTML message to a Telegram chat."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{TELEGRAM_API}/bot{token}/sendMessage", json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
    except Exception as e:
        logger.error(f"Telegram send error: {e}")


async def _download_file(token: str, file_id: str) -> bytes:
    """Download a file from Telegram servers."""
    async with httpx.AsyncClient(timeout=30) as client:
        info = await client.get(f"{TELEGRAM_API}/bot{token}/getFile", params={"file_id": file_id})
        info.raise_for_status()
        file_path = info.json()["result"]["file_path"]
        dl = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        dl.raise_for_status()
        return dl.content


def _fmt(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


def _safe(text: str) -> str:
    """Escape HTML entities to prevent Telegram parse errors."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_proposal(proposal: dict, intro: str) -> str:
    """Format a document_proposal dict as an HTML Telegram message."""
    tipo = TIPO_LABELS.get(proposal.get("tipo_documento", ""), proposal.get("tipo_documento", "Documento"))
    lines = [f"📄 <b>{tipo} detectado</b>", ""]
    if intro:
        lines += [_safe(intro[:400]), ""]

    if proposal.get("proveedor_cliente"):
        lines.append(f"🏢 <b>Proveedor:</b> {_safe(proposal['proveedor_cliente'])}")
    if proposal.get("nit"):
        lines.append(f"🔢 <b>NIT:</b> {_safe(proposal['nit'])}")
    if proposal.get("fecha"):
        lines.append(f"📅 <b>Fecha:</b> {proposal['fecha']}")
    if proposal.get("numero_documento"):
        lines.append(f"📋 <b>N° Doc:</b> {_safe(proposal['numero_documento'])}")
    if proposal.get("concepto"):
        lines.append(f"📝 <b>Concepto:</b> {_safe(proposal['concepto'])}")

    lines.append("")
    lines.append(f"💰 <b>Subtotal:</b> ${_fmt(proposal.get('subtotal', 0))}")
    if proposal.get("iva_valor", 0) > 0:
        lines.append(f"📊 <b>IVA {proposal.get('iva_porcentaje', '')}%:</b> ${_fmt(proposal.get('iva_valor', 0))}")
    if proposal.get("retefuente_valor", 0) > 0:
        lines.append(f"✂️ <b>ReteFuente:</b> ${_fmt(proposal.get('retefuente_valor', 0))}")
    total = proposal.get("total") or proposal.get("subtotal", 0)
    lines.append(f"💵 <b>TOTAL:</b> ${_fmt(total)}")

    if proposal.get("cuenta_gasto_nombre"):
        lines += ["", f"📒 <b>Cuenta:</b> {_safe(proposal['cuenta_gasto_nombre'])}"]
    if proposal.get("es_pago_loanbook"):
        lines += ["", f"🏍️ <b>Pago Loanbook:</b> {_safe(proposal.get('loanbook_codigo', '') or '')}"]
    if proposal.get("ilegible"):
        lines += ["", "⚠️ <i>Datos incompletos — completa en la app web antes de confirmar.</i>"]

    lines += [
        "", "─────────────────",
        "¿Registrar esto en Alegra?",
        "",
        "✅ Responde <b>/si</b> para confirmar",
        "❌ Responde <b>/no</b> para cancelar",
    ]
    return "\n".join(lines)


# ── process helpers ───────────────────────────────────────────────────────────

async def _process_file(token: str, chat_id: int, file_id: str, mime_type: str, file_name: str, user_text: str):
    """Download Telegram file → Claude analysis → send proposal."""
    await _send(token, chat_id, "🔍 Analizando el documento…")
    try:
        file_bytes = await _download_file(token, file_id)
        file_b64 = base64.b64encode(file_bytes).decode()

        admin = await db.users.find_one({"role": "admin"}, {"_id": 0, "id": 1, "email": 1, "name": 1})
        if not admin:
            await _send(token, chat_id, "Error: no hay usuario administrador configurado en RODDOS.")
            return

        session_id = f"telegram-{chat_id}-{uuid.uuid4().hex[:8]}"
        result = await process_document_chat(
            session_id,
            user_text or "Analiza este comprobante contable.",
            file_b64, file_name, mime_type,
            db, admin,
        )

        proposal = result.get("document_proposal")
        text_resp = result.get("message", "")

        if not proposal:
            await _send(token, chat_id, _safe(text_resp) or "No pude extraer datos estructurados del documento.")
            return

        # Store pending proposal keyed by chat_id
        await db.telegram_sessions.update_one(
            {"chat_id": chat_id},
            {"$set": {
                "chat_id": chat_id,
                "pending_proposal": proposal,
                "intro_text": text_resp,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        await _send(token, chat_id, _format_proposal(proposal, text_resp))

    except Exception as e:
        logger.error(f"Telegram file processing error: {e}")
        await _send(token, chat_id, f"Error al analizar el documento: {_safe(str(e))}")


async def _handle_confirm(token: str, chat_id: int):
    """User said /si — execute the pending proposal."""
    session = await db.telegram_sessions.find_one({"chat_id": chat_id}, {"_id": 0})
    if not session or not session.get("pending_proposal"):
        await _send(token, chat_id, "No hay ningún comprobante pendiente. Envía una foto o PDF primero.")
        return

    await _send(token, chat_id, "⚙️ Ejecutando en Alegra…")
    try:
        proposal = session["pending_proposal"]
        fmtv = lambda n: f"${_fmt(n)}"  # noqa: E731

        confirm_lines = list(filter(None, [
            "CONFIRMAR EJECUCIÓN — Comprobante verificado vía Telegram:",
            f"Tipo: {TIPO_LABELS.get(proposal.get('tipo_documento', ''), proposal.get('tipo_documento', ''))}",
            f"Proveedor/Cliente: {proposal.get('proveedor_cliente', '')} (NIT: {proposal.get('nit', '')})" if proposal.get("proveedor_cliente") else None,
            f"Fecha: {proposal.get('fecha', '')}" if proposal.get("fecha") else None,
            f"Concepto: {proposal.get('concepto', '')}",
            f"Subtotal: {fmtv(proposal.get('subtotal', 0))}",
            f"IVA: {fmtv(proposal.get('iva_valor', 0))}" if proposal.get("iva_valor", 0) > 0 else None,
            f"ReteFuente ({proposal.get('retefuente_tipo', '')}): {fmtv(proposal.get('retefuente_valor', 0))}" if proposal.get("retefuente_valor", 0) > 0 else None,
            f"Total: {fmtv(proposal.get('total', proposal.get('subtotal', 0)))}",
            f"Cuenta: [{proposal.get('cuenta_gasto_id')}] {proposal.get('cuenta_gasto_nombre', '')}" if proposal.get("cuenta_gasto_id") else None,
            "",
            f"Acción: {proposal.get('accion_contable', '')}",
            "Genera el bloque <action> completo y correcto para Alegra.",
        ]))

        admin = await db.users.find_one({"role": "admin"}, {"_id": 0, "id": 1, "email": 1, "name": 1})
        session_id = f"telegram-confirm-{chat_id}"
        result = await process_chat(session_id, "\n".join(confirm_lines), db, admin)
        pending_action = result.get("pending_action")

        if pending_action and pending_action.get("type") and pending_action.get("payload"):
            exec_result = await execute_chat_action(pending_action["type"], pending_action["payload"], db, admin)
            doc_id = exec_result.get("id") or exec_result.get("result", {}).get("id") or ""
            sync_msgs = exec_result.get("sync", {}).get("sync_messages", [])
            ok_msg = f"✅ <b>Registrado en Alegra</b>{f' — ID: {doc_id}' if doc_id else ''}"
            if sync_msgs:
                ok_msg += "\n\n" + "\n".join(_safe(m) for m in sync_msgs[:3])
            await _send(token, chat_id, ok_msg)
        else:
            resp_text = result.get("message", "No pude construir la acción. Verifica los datos en la app web.")
            await _send(token, chat_id, _safe(resp_text[:1000]))

        # Clear session
        await db.telegram_sessions.update_one({"chat_id": chat_id}, {"$unset": {"pending_proposal": "", "intro_text": ""}})

    except Exception as e:
        logger.error(f"Telegram confirm error: {e}")
        await _send(token, chat_id, f"Error al ejecutar en Alegra: {_safe(str(e))}")


async def _handle_cancel(token: str, chat_id: int):
    await db.telegram_sessions.update_one({"chat_id": chat_id}, {"$unset": {"pending_proposal": "", "intro_text": ""}})
    await _send(token, chat_id, "Registro cancelado. Envía otro comprobante cuando quieras.")


async def _handle_text(token: str, chat_id: int, text: str):
    """Route plain text message through the main AI agent."""
    admin = await db.users.find_one({"role": "admin"}, {"_id": 0, "id": 1, "email": 1, "name": 1})
    if not admin:
        return
    try:
        session_id = f"telegram-main-{chat_id}"
        result = await process_chat(session_id, text, db, admin)
        response = result.get("message", "")
        if result.get("pending_action"):
            response += "\n\n<i>(Para ejecutar esta acción, usa la app web de RODDOS.)</i>"
        await _send(token, chat_id, _safe(response)[:3000])
    except Exception as e:
        await _send(token, chat_id, f"Error: {_safe(str(e))}")


# ── webhook ───────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Public endpoint called by Telegram servers. No JWT auth."""
    config = await _get_config()
    if not config or not config.get("token"):
        return {"ok": True}  # not configured — silently ignore

    token = config["token"]

    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id: int = message["chat"]["id"]
    from_user = message.get("from", {})
    sender_name = from_user.get("first_name", "Usuario")
    text: str = (message.get("text") or "").strip()

    # ── commands ──
    if text.lower() in ("/si", "si", "sí", "confirmar", "confirm", "yes", "ok"):
        await _handle_confirm(token, chat_id)
        return {"ok": True}

    if text.lower() in ("/no", "no", "cancelar", "cancel"):
        await _handle_cancel(token, chat_id)
        return {"ok": True}

    if text.lower().startswith("/start"):
        await db.telegram_config.update_one({}, {"$set": {"linked_chat_id": chat_id}})
        await _send(token, chat_id,
            f"Hola {_safe(sender_name)}! Soy el <b>Agente Contable IA de RODDOS</b> 🤖\n\n"
            "Envíame una <b>foto de un recibo</b> o <b>PDF de una factura</b> y la registro en Alegra automáticamente.\n\n"
            "También puedo responder preguntas contables:\n<i>\"¿Cuánto IVA debo?\"</i>, <i>\"Calcula ReteFuente de $2M\"</i>\n\n"
            "📎 <b>Formatos aceptados:</b> fotos JPG/PNG, documentos PDF"
        )
        return {"ok": True}

    # ── photo ──
    if "photo" in message:
        photos = message["photo"]
        file_id = photos[-1]["file_id"]  # largest size
        caption = message.get("caption", "")
        await _process_file(token, chat_id, file_id, "image/jpeg", f"recibo_{chat_id}.jpg", caption)
        return {"ok": True}

    # ── document (PDF, image as file) ──
    if "document" in message:
        doc = message["document"]
        mime = doc.get("mime_type", "application/pdf")
        fname = doc.get("file_name", f"doc_{chat_id}.pdf")
        caption = message.get("caption", "")
        allowed_mimes = {"application/pdf", "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
        if mime not in allowed_mimes:
            await _send(token, chat_id, "Solo acepto imágenes (JPG, PNG, WebP) y PDFs. Envía el recibo como foto o PDF.")
            return {"ok": True}
        await _process_file(token, chat_id, doc["file_id"], mime, fname, caption)
        return {"ok": True}

    # ── plain text ──
    if text and not text.startswith("/"):
        await _handle_text(token, chat_id, text)
        return {"ok": True}

    return {"ok": True}


# ── config endpoints (protected) ─────────────────────────────────────────────

@router.get("/config")
async def get_telegram_config(current_user=Depends(get_current_user)):
    config = await _get_config()
    if not config:
        return {"configured": False, "webhook_set": False}
    masked = ("*" * 20 + config["token"][-6:]) if config.get("token") else ""
    return {
        "configured": bool(config.get("token")),
        "token_masked": masked,
        "webhook_set": config.get("webhook_set", False),
        "webhook_url": config.get("webhook_url"),
        "bot_username": config.get("bot_username"),
        "linked_chat_id": config.get("linked_chat_id"),
    }


@router.post("/config")
async def save_telegram_config(request: Request, current_user=Depends(get_current_user)):
    data = await request.json()
    token = data.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token requerido")

    # Validate token via getMe
    bot_username = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TELEGRAM_API}/bot{token}/getMe")
            if resp.status_code == 200:
                bot_username = resp.json().get("result", {}).get("username")
            else:
                raise HTTPException(status_code=400, detail="Token inválido — verifica el token de @BotFather")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo validar el token: {e}")

    # Derive public backend URL from the incoming request
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    scheme = request.headers.get("x-forwarded-proto", "https")
    webhook_url = f"{scheme}://{host}/api/telegram/webhook" if host else None

    webhook_set = False
    if webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{TELEGRAM_API}/bot{token}/setWebhook", json={"url": webhook_url})
                webhook_set = resp.json().get("ok", False)
        except Exception:
            pass

    await db.telegram_config.update_one(
        {},
        {"$set": {
            "token": token,
            "bot_username": bot_username,
            "webhook_set": webhook_set,
            "webhook_url": webhook_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    return {"configured": True, "bot_username": bot_username, "webhook_set": webhook_set, "webhook_url": webhook_url}


@router.delete("/config")
async def remove_telegram_config(current_user=Depends(get_current_user)):
    """Remove the webhook and delete the config."""
    config = await _get_config()
    if config and config.get("token"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{TELEGRAM_API}/bot{config['token']}/deleteWebhook")
        except Exception:
            pass
    await db.telegram_config.delete_many({})
    return {"message": "Configuración de Telegram eliminada"}
