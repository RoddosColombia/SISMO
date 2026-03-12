import os
import uuid
import json
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage

AGENT_SYSTEM_PROMPT = """Eres el Agente Contable IA de RODDOS Colombia. Tienes acceso DIRECTO a Alegra ERP y EJECUTAS acciones reales, no solo sugieres.

DATOS DE CONTEXTO ALEGRA (actualizados al inicio de cada mensaje):
{context}

═══════════════════════════════════════════════════
COMPORTAMIENTO OBLIGATORIO:
═══════════════════════════════════════════════════
1. EJECUTA todo desde el chat. El usuario NO va a ningún formulario.
2. Con la información disponible, construye el payload completo.
3. Calcula IVA, retenciones y totales AUTOMÁTICAMENTE.
4. Presenta un resumen CLARO antes de ejecutar.
5. Siempre incluye el bloque <action> con payload listo para ejecutar.
6. Si falta un cliente en Alegra, solicita NIT y crea el contacto primero.

═══════════════════════════════════════════════════
TARIFAS VIGENTES Colombia 2025 (UVT = $49.799):
═══════════════════════════════════════════════════
• IVA general: 19% | Bienes básicos: 5% | Excluidos: 0%
• ReteFuente Servicios generales: 4% (si monto > $199.196 = 4 UVT)
• ReteFuente Servicios técnicos/especializados: 6%
• ReteFuente Honorarios PN: 10% | PJ: 11%
• ReteFuente Arrendamiento inmuebles: 3.5% | muebles: 4%
• ReteFuente Compras: 2.5% (si monto > $1.344.573 = 27 UVT)
• ReteFuente Transporte: 3.5%
• ReteIVA: 15% del IVA (cuando aplica)
• ReteICA Bogotá: Servicios 0.966‰ | Industria 0.414‰ | Comercio 0.345‰
• SMLMV 2025: $1.423.500 | Auxilio transporte: $200.000

═══════════════════════════════════════════════════
CUENTAS NIIF COLOMBIA MÁS USADAS:
═══════════════════════════════════════════════════
• 1105 Caja | 1110 Bancos | 1305 Clientes | 1355 Anticipo impuestos
• 2205 Proveedores | 2365 ReteFuente por pagar | 2408 IVA por pagar | 2409 IVA descontable
• 4105 Ventas productos | 4135 Servicios | 4155 Honorarios | 4175 Comisiones
• 5105 Gasto personal | 5110 Honorarios admon | 5120 Arrendamiento | 5185 Servicios públicos
• 6135 Costos de ventas

═══════════════════════════════════════════════════
TIPOS DE ACCIÓN DISPONIBLES:
═══════════════════════════════════════════════════
• crear_factura_venta → POST /invoices
• registrar_factura_compra → POST /bills
• crear_causacion → POST /journal-entries
• registrar_pago → POST /payments
• crear_contacto → POST /contacts
• calcular_retencion → cálculo local (sin ejecutar en Alegra)
• consultar_facturas → información de facturas existentes

═══════════════════════════════════════════════════
FORMATO DE RESPUESTA PARA ACCIONES:
═══════════════════════════════════════════════════
1. Una línea explicando qué vas a hacer
2. Tabla resumen:
   | Concepto | Valor |
   |----------|-------|
   | Cliente  | Xxx   |
   ...
3. Bloque <action> con JSON completo (OBLIGATORIO para acciones ejecutables)

Ejemplo de <action>:
<action>
{
  "type": "crear_factura_venta",
  "title": "Factura para [cliente]",
  "summary": [
    {"label": "Cliente", "value": "Nombre S.A.S."},
    {"label": "Concepto", "value": "Servicio prestado"},
    {"label": "Valor base", "value": "$5.000.000"},
    {"label": "IVA 19%", "value": "$950.000"},
    {"label": "Total", "value": "$5.950.000"},
    {"label": "Cuenta ingreso", "value": "[4135] Ingresos por servicios"}
  ],
  "payload": {
    "date": "2025-10-20",
    "dueDate": "2025-11-19",
    "client": {"id": "ID_DEL_CLIENTE"},
    "items": [{"description": "...", "quantity": 1, "price": 5000000, "account": {"id": "4135"}, "tax": [{"percentage": 19}]}]
  }
}
</action>

IMPORTANTE: Responde siempre en español colombiano. Sé conciso y profesional.
"""


async def gather_context(user_message: str, alegra_service) -> dict:
    """Gather relevant Alegra data to provide context to Claude."""
    context = {
        "fecha_actual": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "contactos": [],
        "cuentas_bancarias": [],
    }
    try:
        contacts = await alegra_service.request("contacts")
        context["contactos"] = [
            {"id": c["id"], "name": c["name"], "nit": c.get("identification", ""), "tipo": c.get("type", "")}
            for c in (contacts if isinstance(contacts, list) else [])
        ]
    except Exception:
        pass

    try:
        banks = await alegra_service.request("bank-accounts")
        context["cuentas_bancarias"] = [
            {"id": b["id"], "name": b["name"], "balance": b.get("balance", 0)}
            for b in (banks if isinstance(banks, list) else [])
        ]
    except Exception:
        pass

    return context


async def process_chat(session_id: str, user_message: str, db, user: dict) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")

    # Import here to avoid circular import
    from alegra_service import AlegraService
    alegra_service = AlegraService(db)

    # Gather context
    context_data = await gather_context(user_message, alegra_service)
    context_str = json.dumps(context_data, ensure_ascii=False)

    # Build system prompt with context
    system_prompt = AGENT_SYSTEM_PROMPT.replace("{context}", context_str)

    # Save user message to MongoDB
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # Call Claude
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_prompt,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    msg = UserMessage(text=user_message)
    response_text = await chat.send_message(msg)

    # Parse action block
    action = None
    clean_response = response_text
    if "<action>" in response_text and "</action>" in response_text:
        try:
            start = response_text.index("<action>") + 8
            end = response_text.index("</action>")
            action_json = response_text[start:end].strip()
            action = json.loads(action_json)
            clean_response = (
                response_text[:response_text.index("<action>")].strip()
                + response_text[end + 9:].strip()
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
        "pending_action": action,
        "session_id": session_id,
    }


async def execute_chat_action(action_type: str, payload: dict, db, user: dict) -> dict:
    """Execute a confirmed action in Alegra."""
    from alegra_service import AlegraService
    service = AlegraService(db)

    ACTION_MAP = {
        "crear_factura_venta": ("invoices", "POST"),
        "registrar_factura_compra": ("bills", "POST"),
        "crear_causacion": ("journal-entries", "POST"),
        "registrar_pago": ("payments", "POST"),
        "crear_contacto": ("contacts", "POST"),
    }

    if action_type not in ACTION_MAP:
        raise ValueError(f"Acción no reconocida: {action_type}")

    endpoint, method = ACTION_MAP[action_type]
    result = await service.request(endpoint, method, payload)

    # Save execution to audit
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "endpoint": f"/chat/execute/{action_type}",
        "method": method,
        "request_body": payload,
        "response_status": 200,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    doc_id = result.get("id") or result.get("number") or ""
    return {
        "success": True,
        "result": result,
        "id": doc_id,
        "message": f"Ejecutado en Alegra exitosamente",
    }
