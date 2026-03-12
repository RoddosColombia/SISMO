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

═══════════════════════════════════════════════════
IVA CUATRIMESTRAL — ESTADO ACTUAL:
═══════════════════════════════════════════════════
{iva_context}

IMPORTANTE: Responde siempre en español colombiano. Sé conciso y profesional.
Cuando el usuario pregunte sobre IVA, SIEMPRE incluye el estado actual del período y 3+ sugerencias concretas para reducirlo.
"""


async def gather_context(user_message: str, alegra_service, db) -> dict:
    """Gather relevant Alegra data to provide context to Claude."""
    context = {
        "fecha_actual": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "contactos": [],
        "cuentas_bancarias": [],
        "iva_status": None,
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

    # Pull IVA status for cuatrimestral context
    msg_lower = user_message.lower()
    if any(w in msg_lower for w in ["iva", "impuesto", "dian", "declaraci", "periodo", "cuatrimest", "cuánto", "cuanto", "pagar"]):
        try:
            from server import db as main_db
        except ImportError:
            main_db = db
        try:
            from datetime import date as _date
            now = datetime.now(timezone.utc)
            cfg = await db.iva_config.find_one({}, {"_id": 0})
            if not cfg:
                cfg = {"tipo_periodo": "cuatrimestral", "periodos": [
                    {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
                    {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
                    {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
                ], "saldo_favor_dian": 0}

            mes = now.month
            ano = now.year
            periodos = cfg.get("periodos", [])
            saldo_favor = float(cfg.get("saldo_favor_dian", 0))
            periodo = next((p for p in periodos if p["inicio_mes"] <= mes <= p["fin_mes"]), periodos[-1] if periodos else None)
            if periodo:
                ds = f"{ano}-{str(periodo['inicio_mes']).zfill(2)}-01"
                de = f"{ano}-{str(periodo['fin_mes']).zfill(2)}-28"
                inv = await alegra_service.request("invoices", params={"date_start": ds, "date_end": de})
                bills = await alegra_service.request("bills", params={"date_start": ds, "date_end": de})
                inv = inv if isinstance(inv, list) else []
                bills = bills if isinstance(bills, list) else []
                tv = sum(float(i.get("total") or 0) for i in inv)
                tc = sum(float(b.get("total") or 0) for b in bills)
                iva_cobrado = round(tv / 1.19 * 0.19)
                iva_desc = round(tc / 1.19 * 0.19)
                iva_bruto = max(0, iva_cobrado - iva_desc)
                iva_pagar = max(0, iva_bruto - saldo_favor)
                meses_trans = max(1, mes - periodo["inicio_mes"] + 1)
                meses_tot = periodo["fin_mes"] - periodo["inicio_mes"] + 1
                mes_lim = periodo["fin_mes"] + periodo.get("mes_limite_offset", 1)
                ano_lim = ano + (1 if mes_lim > 12 else 0)
                mes_lim = mes_lim if mes_lim <= 12 else mes_lim - 12
                fecha_lim = f"{ano_lim}-{str(mes_lim).zfill(2)}-{periodo.get('dia_limite', 30)}"
                dias_rest = (_date.fromisoformat(fecha_lim) - _date.today()).days
                context["iva_status"] = {
                    "periodo": periodo["nombre"],
                    "tipo": cfg.get("tipo_periodo", "cuatrimestral"),
                    "fecha_limite": fecha_lim,
                    "dias_restantes": dias_rest,
                    "meses_transcurridos": meses_trans,
                    "meses_total": meses_tot,
                    "iva_cobrado_acumulado": iva_cobrado,
                    "iva_descontable_acumulado": iva_desc,
                    "iva_bruto_periodo": iva_bruto,
                    "saldo_favor_dian": saldo_favor,
                    "iva_pagar_estimado": iva_pagar,
                    "facturas_venta": len(inv),
                    "facturas_compra": len(bills),
                }
        except Exception:
            pass

    return context


async def process_chat(session_id: str, user_message: str, db, user: dict) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")

    # Import here to avoid circular import
    from alegra_service import AlegraService
    alegra_service = AlegraService(db)

    # Gather context
    context_data = await gather_context(user_message, alegra_service, db)
    context_str = json.dumps(context_data, ensure_ascii=False)

    # Build IVA context string
    iva_ctx = context_data.get("iva_status")
    if iva_ctx:
        iva_context_str = (
            f"Período: {iva_ctx['periodo']} | Tipo: {iva_ctx['tipo']} | "
            f"Mes {iva_ctx['meses_transcurridos']} de {iva_ctx['meses_total']}\n"
            f"Fecha límite: {iva_ctx['fecha_limite']} ({iva_ctx['dias_restantes']} días)\n"
            f"IVA cobrado acumulado: ${iva_ctx['iva_cobrado_acumulado']:,.0f}\n"
            f"IVA descontable acumulado: ${iva_ctx['iva_descontable_acumulado']:,.0f}\n"
            f"IVA bruto del período: ${iva_ctx['iva_bruto_periodo']:,.0f}\n"
            f"Saldo a favor DIAN: ${iva_ctx['saldo_favor_dian']:,.0f}\n"
            f"⚠️ IVA ESTIMADO A PAGAR DIAN: ${iva_ctx['iva_pagar_estimado']:,.0f}\n"
            f"Facturas: {iva_ctx['facturas_venta']} ventas / {iva_ctx['facturas_compra']} compras registradas"
        )
    else:
        iva_context_str = "Pregunta sobre IVA para obtener el estado actualizado del período cuatrimestral."

    # Build system prompt with context
    system_prompt = AGENT_SYSTEM_PROMPT.replace("{context}", context_str).replace("{iva_context}", iva_context_str)

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

    if isinstance(result, dict):
        doc_id = result.get("id") or result.get("number") or ""
    elif isinstance(result, list) and result:
        doc_id = result[0].get("id") if isinstance(result[0], dict) else ""
    else:
        doc_id = ""

    # Save to agent_memory for recurrent suggestion
    if action_type in ("crear_causacion", "crear_factura_venta", "registrar_factura_compra"):
        description = payload.get("description") or payload.get("observations") or f"Acción {action_type}"
        amount = 0
        if isinstance(payload.get("items"), list) and payload["items"]:
            amount = sum(float(i.get("price") or i.get("debit") or 0) for i in payload["items"])
        elif payload.get("total"):
            amount = float(payload["total"])
        await db.agent_memory.update_one(
            {"user_id": user.get("id"), "tipo": action_type, "descripcion": description},
            {"$set": {
                "id": str(uuid.uuid4()),
                "user_id": user.get("id"),
                "user_email": user.get("email"),
                "tipo": action_type,
                "descripcion": description,
                "payload_alegra": payload,
                "monto": amount,
                "ultima_ejecucion": datetime.now(timezone.utc).isoformat(),
                "frecuencia": "mensual",
            }},
            upsert=True,
        )

    return {
        "success": True,
        "result": result,
        "id": doc_id,
        "message": "Ejecutado en Alegra exitosamente",
    }
