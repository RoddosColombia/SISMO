import os
import uuid
import json
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage

SYSTEM_PROMPT = """Eres el asistente contable IA de RODDOS Colombia. Eres experto en contabilidad colombiana bajo NIIF, normativas DIAN, retenciones (ReteFuente, ReteIVA, ReteICA), IVA, ICA, y el software Alegra ERP.

Tu misión: ayudar al contador/administrador a registrar transacciones de forma RÁPIDA y PRECISA en Alegra, minimizando el esfuerzo manual.

Cuando el usuario te pida realizar una acción contable:
1. Explica BREVEMENTE lo que vas a hacer (máx 2 líneas)
2. Sugiere las cuentas NIIF correctas (con código y nombre)
3. Si necesitas crear algo en Alegra, incluye un bloque JSON con la acción sugerida:

<action>
{
  "type": "invoice" | "bill" | "journal_entry" | "payment",
  "title": "descripción breve de la acción",
  "module": "ruta del módulo ej: /facturacion-venta",
  "prefill": {
    // datos para pre-rellenar el formulario
  }
}
</action>

Tarifas de retención vigentes Colombia 2025:
- ReteFuente servicios generales: 4% (base > 4 UVT = $191.800)
- ReteFuente honorarios y comisiones: 10% (base > 1 UVT)
- ReteFuente arrendamiento bienes inmuebles: 3.5%
- ReteIVA: 15% del IVA (aplica cuando pagador es gran contribuyente o autorretenedor)
- ReteICA Bogotá - Servicios: 0.966‰ | Industria: 0.414‰ | Comercio: 0.345‰
- UVT 2025: $49.799

Cuentas más usadas NIIF Colombia:
- 1110 Bancos | 1305 Clientes | 1355 Anticipos impuestos
- 2205 Proveedores | 2365 ReteFuente por pagar | 2408 IVA por pagar
- 4135 Ingresos por servicios | 4175 Ingresos por comisiones
- 5105 Gastos personal | 5120 Arrendamientos | 5185 Servicios públicos
- 6135 Costos de ventas

Responde siempre en español colombiano, de forma concisa y profesional.
Si el usuario menciona un monto, calcula automáticamente IVA y retenciones aplicables.
"""


async def process_chat(session_id: str, user_message: str, db, user: dict) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")

    # Save user message
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # Get chat history for context
    history_cursor = db.chat_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("timestamp", 1).limit(20)
    history = await history_cursor.to_list(20)

    # Build context from recent history
    context_parts = []
    for msg in history[:-1]:  # exclude the current message
        role = "Usuario" if msg["role"] == "user" else "Asistente"
        context_parts.append(f"{role}: {msg['content']}")
    
    full_message = user_message
    if context_parts:
        context_str = "\n".join(context_parts[-10:])  # last 5 exchanges
        full_message = f"[Contexto previo de la conversación:\n{context_str}\n]\n\nMensaje actual: {user_message}"

    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    msg = UserMessage(text=full_message)
    response_text = await chat.send_message(msg)

    # Parse action block if present
    action = None
    clean_response = response_text
    if "<action>" in response_text and "</action>" in response_text:
        try:
            start = response_text.index("<action>") + 8
            end = response_text.index("</action>")
            action_json = response_text[start:end].strip()
            action = json.loads(action_json)
            # Clean action tags from displayed response
            clean_response = response_text.replace(
                response_text[response_text.index("<action>"):response_text.index("</action>") + 9], ""
            ).strip()
        except Exception:
            pass

    # Save assistant response
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    return {
        "message": clean_response,
        "action": action,
        "session_id": session_id,
    }
