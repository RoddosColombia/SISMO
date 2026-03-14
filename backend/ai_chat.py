import os
import uuid
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContent

AGENT_SYSTEM_PROMPT = """Eres el Agente Contable IA de RODDOS Colombia — actúas como un contador experto en NIIF Colombia.
Tienes acceso DIRECTO a Alegra ERP y EJECUTAS acciones reales, no solo sugieres.

DATOS DE CONTEXTO ALEGRA (actualizados al inicio de cada mensaje):
{context}

═══════════════════════════════════════════════════
PLAN DE CUENTAS REAL DE ALEGRA — RODDOS:
═══════════════════════════════════════════════════
{accounts_context}

═══════════════════════════════════════════════════
PATRONES APRENDIDOS DE RODDOS (registros anteriores confirmados):
═══════════════════════════════════════════════════
{patterns_context}

═══════════════════════════════════════════════════
ROL: ASESOR CONTABLE INTELIGENTE
═══════════════════════════════════════════════════
ANTES de ejecutar CUALQUIER asiento contable o causación, SIEMPRE:
1. Identifica la naturaleza de la transacción (qué es, para qué sirve)
2. Sugiere las cuentas específicas del plan de RODDOS en Alegra:
   • Cuenta DÉBITO: [ID — Nombre de la cuenta] → por qué se debita
   • Cuenta CRÉDITO: [ID — Nombre de la cuenta] → por qué se acredita
3. Confirma montos, retenciones e IVA aplicable
4. Presenta la propuesta completa ANTES de mostrar el bloque <action>

Si existe un PATRÓN APRENDIDO para el mismo tipo de transacción (3+ veces):
→ Usa el patrón directamente indicando: "Usando patrón aprendido de RODDOS"
→ Después de 5+ usos, procede automáticamente sin preguntar cuentas

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
TIPOS DE ACCIÓN DISPONIBLES:
═══════════════════════════════════════════════════
• crear_factura_venta   → POST /invoices
• registrar_factura_compra → POST /bills
• crear_causacion       → POST /journal-entries  ⚠ Requiere plan Alegra con módulo Contabilidad
• registrar_pago        → POST /payments
• crear_contacto        → POST /contacts
• registrar_entrega     → ACCIÓN INTERNA (activa plan de cuotas)
• calcular_retencion    → cálculo local (sin ejecutar en Alegra)
• consultar_facturas    → información de facturas existentes

FORMATO EXACTO PARA CREAR_CONTACTO (Alegra Colombia):
{
  "name": "[nombre para mostrar]",
  "nameObject": {"firstName": "[razón social o nombre]", "lastName": "[apellido si es persona natural]"},
  "identificationObject": {"type": "NIT", "number": "[número sin guiones ni DV]"},
  "kindOfPerson": "PERSON_ENTITY",
  "regime": "SIMPLIFIED_REGIME",
  "type": ["provider"],             ← ["client"], ["provider"], o ["client","provider"]
  "phonePrimary": "[teléfono]",
  "email": "[email]"
}
Identificación: usar "identificationObject" (NO "identification" ni "identificationType")
Tipos id: "NIT" (empresa), "CC" (persona natural), "CE", "PP"
Para personas naturales: nameObject.lastName es el apellido. nameObject.firstName es el nombre.
Para empresas con NIT: nameObject.firstName = razón social, nameObject.lastName = ""

═══════════════════════════════════════════════════
FLUJO — DETECCIÓN DE NUEVO TERCERO (PROVEEDOR / CLIENTE)
═══════════════════════════════════════════════════
Si el proveedor o cliente mencionado NO aparece en CONTACTOS_DISPONIBLES del contexto:
→ SIEMPRE propón PRIMERO una acción crear_contacto con _next_action = la acción original
→ Incluye accounting_account_suggested y accounting_account_name según el tipo de tercero

CUENTAS SUGERIDAS POR TIPO DE TERCERO:
• Proveedor de servicios/honorarios    → "2205" "Cuentas por pagar nacionales"
• Proveedor de motos / inventario      → "2205" "Cuentas por pagar nacionales"
• Proveedor de arrendamiento           → "2335" "Arrendamientos por pagar"
• Cliente (comprador moto)             → "1305" "Clientes nacionales"
• Empleado / contratista               → "2335" "Nómina y prestaciones por pagar"
• Entidad financiera / banco           → "2105" "Obligaciones financieras"

FORMATO crear_contacto CON ACCIÓN SIGUIENTE:
<action>
{
  "type": "crear_contacto",
  "title": "Nuevo tercero: [nombre]",
  "summary": [
    {"label": "Nombre", "value": "[nombre]"},
    {"label": "NIT / Identificación", "value": "[nit]"},
    {"label": "Tipo", "value": "Proveedor"},
    {"label": "Cuenta sugerida", "value": "[id_cuenta] — [nombre_cuenta]"}
  ],
  "payload": {
    "name": "[nombre]",
    "nameObject": {"firstName": "[nombre]", "lastName": ""},
    "identificationObject": {"type": "NIT", "number": "[nit_sin_guiones_ni_DV]"},
    "identification": "[nit_sin_guiones_ni_DV]",    ← duplicar aquí para pre-poblar el formulario
    "kindOfPerson": "PERSON_ENTITY",
    "regime": "SIMPLIFIED_REGIME",
    "type": ["provider"],
    "accounting_account_suggested": "[id_cuenta]",
    "accounting_account_name": "[nombre_cuenta]",
    "_next_action": {
      "type": "[accion_original]",
      "title": "[titulo_accion_original]",
      "summary": [...],
      "payload": {
        "provider": {"id": "__NEW_CONTACT_ID__"},
        ...resto_del_payload_original_SIN_CAMBIOS
      }
    }
  }
}
</action>

REGLA: Usa "__NEW_CONTACT_ID__" como placeholder para el ID del proveedor/cliente recién creado.
El sistema reemplazará automáticamente este placeholder con el ID real de Alegra tras la creación.

═══════════════════════════════════════════════════
FLUJO OBLIGATORIO — VENTA DE MOTO A CRÉDITO
═══════════════════════════════════════════════════
Cuando el usuario quiera vender una moto:

PASO 1 — Verificar disponibilidad:
Si el contexto incluye INVENTARIO_DISPONIBLE, verifica que la moto esté listada.
Si su estado ≠ "Disponible", RECHAZA la operación:
  "La moto [descripción] no está disponible (estado: [X]). No se puede facturar."

PASO 2 — Confirmar plan y cuota:
Si el usuario no indicó el plan, PREGUNTA:
  "¿Cuál es el plan de pago? P39S (39 semanas), P52S (52 semanas), P78S (78 semanas), o Contado."
  "¿Cuál es el valor de la cuota semanal?"
  "¿Cuál es la cuota inicial?"

PASO 3 — Mostrar resumen y crear la acción:
El campo _metadata es OBLIGATORIO para crear el Loanbook automáticamente.

FORMATO DE PAYLOAD EXACTO PARA CREAR_FACTURA_VENTA (Alegra API v1):
{
  "date": "YYYY-MM-DD",
  "dueDate": "YYYY-MM-DD",          ← OBLIGATORIO: mismo que date para crédito
  "paymentForm": "CREDIT",          ← OBLIGATORIO: "CREDIT" para crédito, "CASH" para contado
  "client": {"id": "[id_alegra]"},
  "items": [
    {
      "id": "[item_id_alegra]",
      "quantity": 1,
      "price": [precio_sin_iva],
      "tax": [{"id": "4"}]          ← IVA 19% id=4
    }
  ],
  "observations": "Venta [marca modelo] Chasis [XXX]",
  "anotation": "[chasis]\n[motor]",
  "_metadata": { ... }
}

REGLA: dueDate = date para crédito (Alegra gestiona los plazos internamente).
NUNCA omitas dueDate ni paymentForm — la API los rechaza sin ellos.

Incluye dentro del payload el campo "_metadata" con todos estos datos:
{
  "_metadata": {
    "moto_id": "[id interno del inventario]",
    "moto_chasis": "[número de chasis]",
    "moto_descripcion": "[marca modelo color]",
    "cliente_id": "[id_alegra del cliente]",
    "cliente_nombre": "[nombre completo]",
    "cliente_nit": "[nit]",
    "cliente_telefono": "[celular]",
    "plan": "P39S",
    "num_cuotas": 39,
    "cuota_valor": 190000,
    "cuota_inicial": 500000,
    "precio_venta": 8000000
  }
}

PLANES DISPONIBLES:
• P39S = 39 cuotas semanales | P52S = 52 cuotas | P78S = 78 cuotas | Contado = sin Loanbook

El sistema creará automáticamente el Loanbook con estado "PENDIENTE ENTREGA".
Las fechas de cuotas se asignan SOLO cuando se registre la entrega física.
NUNCA aparecerá en Cartera hasta que se registre la entrega.

═══════════════════════════════════════════════════
FLUJO OBLIGATORIO — REGISTRO DE ENTREGA DE MOTO
═══════════════════════════════════════════════════
Cuando el usuario diga "entrega de moto", "entregué la moto", o similar:

1. Pide el código de Loanbook (LB-XXXX-YYYY) y la fecha de entrega.
2. Crea la acción tipo "registrar_entrega":
<action>
{
  "type": "registrar_entrega",
  "title": "Entrega moto — [código loanbook]",
  "summary": [
    {"label": "Loanbook", "value": "[código]"},
    {"label": "Cliente", "value": "[nombre]"},
    {"label": "Fecha entrega", "value": "[fecha]"},
    {"label": "Efecto", "value": "Se calculan fechas de cuota (miércoles), Loanbook → ACTIVO, cliente aparece en Cola de Gestión"}
  ],
  "payload": {
    "loanbook_id": "[id o código del loanbook]",
    "loanbook_codigo": "[código LB-...]",
    "fecha_entrega": "YYYY-MM-DD",
    "notas": "Entrega conforme al cliente"
  }
}
</action>

El sistema calculará automáticamente:
• Primera cuota = primer miércoles >= (fecha_entrega + 7 días)
• Todas las cuotas siguientes serán miércoles consecutivos
• RODDOS: TODOS los cobros vencen el miércoles sin excepción

═══════════════════════════════════════════════════
FLUJO — FACTURA DE COMPRA (PROVEEDOR)
═══════════════════════════════════════════════════
⚠️ REGLA CRÍTICA — DOS TIPOS DE "FACTURA DE COMPRA":

1. COMPRA DE PRODUCTOS FÍSICOS (motos, inventario, mercancía):
   → Usa: registrar_factura_compra → POST /bills
   → REQUIERE: el item DEBE existir en el catálogo de Alegra (ver ITEMS_CATALOGO_ALEGRA en el contexto)
   → Si no hay items del catálogo disponibles, NO puedes usar esta acción

2. FACTURAS DE SERVICIOS (arrendamiento, honorarios, servicios públicos, asesorías):
   → USA SIEMPRE: crear_causacion → POST /journals (NO registrar_factura_compra)
   → Razón: Alegra no acepta servicios en bills — solo productos físicos del catálogo
   → Registra el gasto con asiento contable: Débito Gasto + Crédito Proveedor + Retenciones

FORMATO EXACTO PARA REGISTRAR_FACTURA_COMPRA (solo productos del catálogo):
{
  "date": "YYYY-MM-DD",
  "dueDate": "YYYY-MM-DD",
  "paymentForm": "CREDIT",          ← "CREDIT" o "CASH"
  "provider": {"id": "[id_alegra_proveedor]"},
  "purchases": {
    "items": [
      {
        "id": "[id_item_catalogo]",  ← OBLIGATORIO: ID numérico del catálogo de Alegra
        "quantity": [cant],
        "price": [precio_unitario_sin_iva],
        "tax": [{"id": "4"}]
      }
    ]
  }
}

NUNCA uses "items" en el nivel raíz para bills — SIEMPRE usa "purchases.items".
NUNCA uses un item de servicio (type=service) en bills — solo type=product.
NUNCA omitas dueDate ni paymentForm.

Solo para compras de motos/inventario, incluye _metadata para auto-registro en inventario:
{
  "_metadata": {
    "proveedor_nombre": "[nombre]",
    "plazo_dias": 90,
    "motos_a_agregar": [
      {"marca": "Honda", "version": "CB190R", "cantidad": 3, "precio_unitario": 8400000}
    ]
  }
}
Esto agrega las motos automáticamente al inventario con estado "Disponible".

═══════════════════════════════════════════════════
MAPA DE CUENTAS CONTABLES — RODDOS SAS (IDs reales Alegra)
═══════════════════════════════════════════════════
REGLA: SIEMPRE usa estas cuentas HOJA (leaf) — las cuentas padre dan error.

GASTOS (debito en causaciones):
  5200 → Asesoría jurídica
  5201 → Asesoría financiera
  5202 → Otros honorarios
  5204 → Arrendamiento de equipos
  5205 → Arrendamiento de Oficinas            ← usar para arrendamientos locales
  5207 → Gas
  5208 → Aseo
  5209 → Agua
  5210 → Asistencia técnica
  5211 → Alcantarillado/Acueducto
  5212 → Energía eléctrica
  5213 → Teléfono / Internet
  5214 → Transporte y acarreo
  5215 → Otros servicios                      ← usar para servicios generales
  5230 → Software contables
  5252 → Gastos por Intereses financieros
  5253 → Gastos por Intereses de mora
  5263 → Retención en la fuente asumida

RETENCIONES EN LA FUENTE (crédito en causaciones — pasivos):
  5110 → ReteFuente Salarios por pagar
  5112 → ReteFuente Honorarios y comisiones 10% por pagar
  5113 → ReteFuente Honorarios y comisiones 11% por pagar
  5115 → ReteFuente Servicios 4% por pagar
  5116 → ReteFuente Servicios 6% por pagar
  5118 → ReteFuente Arriendo 3.5% por pagar
  5120 → ReteFuente Compra 2.5% por pagar
  5121 → Retención de IVA por pagar
  5122 → Retención de ICA por pagar
  5123 → Otro tipo de retención por pagar

PASIVOS — PROVEEDORES Y TERCEROS (crédito en causaciones):
  5070 → Cuentas por pagar a proveedores nacionales   ← proveedor neto a pagar
  5071 → Cuentas por pagar a proveedores del exterior

INGRESOS (crédito en asientos de ingreso):
  5154 → Ingresos por Intereses financieros
  5155 → Utilidad en venta de Activos
  5157 → Ganancia por diferencia en cambio
  5158 → Ajustes por aproximaciones
  5299 → Alquiler Oficina
  5151 → Devoluciones en ventas

NÓMINA — PASIVOS (crédito):
  5081 → Intereses sobre cesantías por pagar
  5082 → Prima de servicios por pagar
  5089 → Aportes EPS por pagar
  5090 → Aportes ARP por pagar
  5091 → Aportes ICBF/SENA/Cajas por pagar
  5092 → Fondos cesantías/pensiones por pagar

═══════════════════════════════════════════════════
FLUJO — CAUSACIÓN CONTABLE (EGRESO / INGRESO)
═══════════════════════════════════════════════════
• Endpoint real: POST /journals
• REGLA: débitos totales DEBEN igualar créditos totales

FORMATO EXACTO PARA CREAR_CAUSACION (Alegra API /journals):
{
  "date": "YYYY-MM-DD",
  "observations": "[descripción del comprobante]",
  "entries": [
    {"id": [id_cuenta_debito],  "name": "[nombre cuenta]", "debit": [monto],  "credit": 0},
    {"id": [id_cuenta_credito], "name": "[nombre cuenta]", "debit": 0, "credit": [monto]}
  ]
}

REGLA CRÍTICA: El campo "entries" usa {"id": NÚMERO_ENTERO, "name": NOMBRE_TEXTO, "debit": N, "credit": N}
El campo "name" es solo informativo para el usuario — NO lo envíes a Alegra (el sistema lo elimina automáticamente).
NUNCA uses {"account": {"id": ...}} — ese formato es INCORRECTO y da error 403/400.
El id en entries es el ID numérico de la cuenta del plan de cuentas NIIF de Alegra.
Para Debitos y Créditos que NO aplican, usa 0 (no omitir el campo).

RETENCIONES Colombia (calcular antes de mostrar el asiento):
• ReteFuente Arrendamiento inmuebles:   3.5% del valor bruto
• ReteFuente Servicios generales:       4% (si monto > $199.196)
• ReteFuente Honorarios PN:             10%
• ReteFuente Honorarios PJ:             11%
• ReteFuente Servicios técnicos:        6%
• ReteICA Bogotá servicios generales:   0.414% (11.04 por mil)
• IVA Descontable:                      19% del valor (solo si aplica)

═══════════════════════════════════════════════════
FORMATO DE RESPUESTA PARA ACCIONES:
═══════════════════════════════════════════════════
1. Análisis contable (qué cuentas y por qué — SIEMPRE)
2. Tabla resumen:
   | Concepto | Valor |
   |----------|-------|
   | Débito   | [ID] Nombre cuenta |
   | Crédito  | [ID] Nombre cuenta |
   ...
3. Bloque <action> con JSON completo (OBLIGATORIO para acciones ejecutables)

Ejemplo de <action> para causación arrendamiento con retenciones:
<action>
{
  "type": "crear_causacion",
  "title": "Causación arrendamiento oct-2025",
  "summary": [
    {"label": "Concepto", "value": "Arrendamiento local comercial"},
    {"label": "Débito", "value": "[ID_GASTO] Arrendamiento $3.000.000"},
    {"label": "Crédito", "value": "[ID_RETEFUENTE] ReteFuente 3.5% $105.000"},
    {"label": "Crédito", "value": "[ID_PROVEEDOR] Proveedor neto $2.895.000"}
  ],
  "payload": {
    "date": "2025-10-31",
    "observations": "Causación arrendamiento octubre 2025",
    "entries": [
      {"id": ID_CUENTA_GASTO_ARRENDAMIENTO, "debit": 3000000, "credit": 0},
      {"id": ID_CUENTA_RETEFUENTE_PASIVO,   "debit": 0, "credit": 105000},
      {"id": ID_CUENTA_PROVEEDORES,          "debit": 0, "credit": 2895000}
    ]
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

# Keywords that indicate the user wants to register or ask about accounts
REGISTER_KEYWORDS = [
    "causar", "registrar", "crear", "factura", "asiento", "cuenta",
    "débito", "crédito", "débito", "credito", "pagar", "cobrar",
    "proveedor", "gasto", "ingreso", "nomina", "nómina", "arrendamiento",
    "honorario", "servicio", "compra", "venta", "retención", "iva",
    "que cuenta", "qué cuenta", "cuál cuenta", "cual cuenta",
]


# ─── Similitud de patrones aprendidos ────────────────────────────────────────

async def find_similar_pattern(db, concepto: str, threshold: float = 0.80) -> dict | None:
    """Busca en agent_memory el patrón con mayor similitud Jaccard al concepto dado.
    Retorna el patrón si similitud >= threshold, sino None.
    """
    try:
        patterns = await db.agent_memory.find(
            {"tipo": {"$in": ["crear_causacion", "crear_factura_venta", "registrar_factura_compra"]}},
            {"_id": 0},
        ).sort("frecuencia_count", -1).to_list(50)

        if not patterns:
            return None

        concepto_words = set(concepto.lower().split())
        if not concepto_words:
            return None

        best_match = None
        best_sim   = 0.0

        for p in patterns:
            desc_words = set(p.get("descripcion", "").lower().split())
            if not desc_words:
                continue
            intersection = len(concepto_words & desc_words)
            union        = len(concepto_words | desc_words)
            sim          = intersection / union if union > 0 else 0.0
            if sim > best_sim:
                best_sim   = sim
                best_match = p

        if best_sim >= threshold and best_match:
            best_match = dict(best_match)
            best_match["_similitud"] = round(best_sim, 3)
            return best_match
        return None
    except Exception:
        return None


# ─── Guardar patrón confirmado ────────────────────────────────────────────────

async def save_action_pattern(db, user: dict, action_type: str, payload: dict) -> None:
    """Guarda o actualiza el patrón de acción en agent_memory (agent_memory.save_pattern)."""
    if action_type not in ("crear_causacion", "crear_factura_venta", "registrar_factura_compra"):
        return

    description = (
        payload.get("description")
        or payload.get("observations")
        or f"Acción {action_type}"
    )
    amount = 0.0
    if isinstance(payload.get("items"), list) and payload["items"]:
        amount = sum(float(i.get("price") or i.get("debit") or 0) for i in payload["items"])
    elif payload.get("total"):
        amount = float(payload["total"])

    cuentas_usadas: list[dict] = []
    if action_type == "crear_causacion":
        for entry in (payload.get("entries") or []):
            acc_id = str(entry.get("id", ""))
            if float(entry.get("debit", 0) or 0) > 0:
                cuentas_usadas.append({"id": acc_id, "rol": "debito",  "name": ""})
            elif float(entry.get("credit", 0) or 0) > 0:
                cuentas_usadas.append({"id": acc_id, "rol": "credito", "name": ""})

    await db.agent_memory.update_one(
        {"user_id": user.get("id"), "tipo": action_type, "descripcion": description},
        {"$set": {
            "id":               str(uuid.uuid4()),
            "user_id":          user.get("id"),
            "user_email":       user.get("email"),
            "tipo":             action_type,
            "descripcion":      description,
            "payload_alegra":   payload,
            "monto":            amount,
            "cuentas_usadas":   cuentas_usadas,
            "ultima_ejecucion": datetime.now(timezone.utc).isoformat(),
            "frecuencia":       "mensual",
        }, "$inc": {"frecuencia_count": 1}},
        upsert=True,
    )


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

    # ── Inject catalog items for compra/bill scenarios ──────────────────────
    compra_kws = ["compra", "factura compra", "factura de compra", "bill", "proveedor",
                  "moto", "inventario", "comprar", "adquisición", "adquisicion"]
    if any(kw in msg_lower for kw in compra_kws):
        try:
            catalog_items = await alegra_service.request("items")
            if isinstance(catalog_items, list):
                context["items_catalogo"] = [
                    {"id": it["id"], "name": it["name"], "type": it.get("type", ""),
                     "status": it.get("status", "active")}
                    for it in catalog_items
                    if it.get("status") == "active" and it.get("type") == "product"
                ]
        except Exception:
            pass

    # ── Inject available inventory context for moto sale scenarios ─────────
    sale_kws = ["vende", "venta", "moto", "cb", "fz", "tvs", "kawas", "akt", "chasis",
                "vin", "plan", "p39", "p52", "p78", "financ", "cuota", "entrega", "entregó"]
    if any(kw in msg_lower for kw in sale_kws):
        try:
            motos = await db.inventario_motos.find(
                {"estado": "Disponible"},
                {"_id": 0, "id": 1, "marca": 1, "version": 1, "color": 1, "chasis": 1,
                 "motor": 1, "estado": 1, "total": 1},
            ).sort("created_at", -1).to_list(30)
            if motos:
                context["inventario_disponible"] = motos
        except Exception:
            pass

    # ── Inject active loanbook context for payment/delivery scenarios ───────
    pay_kws = ["pago", "cuota", "cobr", "cancelar", "pagó", "cancel", "loanbook", "lb-", "entrega"]
    if any(kw in msg_lower for kw in pay_kws):
        try:
            loans = await db.loanbook.find(
                {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}},
                {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1,
                 "factura_alegra_id": 1, "plan": 1, "num_cuotas": 1,
                 "saldo_pendiente": 1, "estado": 1, "fecha_entrega": 1,
                 "cuotas": 1},
            ).sort("updated_at", -1).to_list(15)
            context["loanbook_activos"] = [
                {
                    "id": l["id"],
                    "codigo": l["codigo"],
                    "cliente": l["cliente_nombre"],
                    "factura_alegra_id": l.get("factura_alegra_id", ""),
                    "plan": l.get("plan", ""),
                    "saldo_pendiente": l.get("saldo_pendiente", 0),
                    "estado": l.get("estado", ""),
                    "fecha_entrega": l.get("fecha_entrega"),
                    "proximas_cuotas": [
                        c for c in l.get("cuotas", [])
                        if c.get("estado") in ("pendiente", "vencida", "sin_fecha")
                    ][:4],
                }
                for l in loans
            ]
        except Exception:
            pass

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


async def gather_accounts_context(user_message: str, alegra_service, db) -> tuple:
    """Gather chart of accounts and RODDOS learned patterns for AI context.
    Returns (accounts_context_str, patterns_context_str)."""
    msg_lower = user_message.lower()
    needs_accounts = any(w in msg_lower for w in REGISTER_KEYWORDS)

    accounts_str = "No se requiere plan de cuentas para esta consulta."
    patterns_str = "Sin patrones aprendidos aún."

    if not needs_accounts:
        return accounts_str, patterns_str

    # Load leaf accounts from Alegra categories
    try:
        accounts_tree = await alegra_service.get_accounts_from_categories()
        leaves = alegra_service.get_leaf_accounts(accounts_tree)
        if leaves:
            # Group by type for compact representation
            by_type = {}
            for acc in leaves:
                t = acc.get('type', 'asset')
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(f"  [{acc['id']}] {acc['name']}")

            TYPE_LABELS = {
                "asset": "ACTIVOS", "liability": "PASIVOS", "equity": "PATRIMONIO",
                "income": "INGRESOS", "expense": "GASTOS", "cost": "COSTOS",
            }
            lines = []
            for t, accs in by_type.items():
                lines.append(f"{TYPE_LABELS.get(t, t.upper())}:")
                lines.extend(accs[:20])  # max 20 per type to avoid huge context
            accounts_str = "\n".join(lines) or "Sin cuentas disponibles."
    except Exception:
        accounts_str = "Error cargando plan de cuentas (usar cuentas NIIF estándar Colombia)."

    # Load RODDOS learned patterns — primero buscar similitud al mensaje actual
    try:
        # agent_memory.find_similar(concepto) — ANTES de generar cada propuesta
        similar = await find_similar_pattern(db, user_message)

        patterns = await db.agent_memory.find(
            {"tipo": {"$in": ["crear_causacion", "crear_factura_venta", "registrar_factura_compra"]}},
            {"_id": 0}
        ).sort("frecuencia_count", -1).limit(8).to_list(8)

        if patterns:
            plines = []
            TIPO_LABELS = {
                "crear_causacion":         "Causación",
                "crear_factura_venta":     "Factura venta",
                "registrar_factura_compra": "Factura compra",
            }

            # Si hay similitud >= 80% → incluir al TOPE como sugerencia destacada
            if similar:
                sim_pct    = round(similar.get("_similitud", 0) * 100)
                freq_sim   = similar.get("frecuencia_count", 1)
                tipo_sim   = TIPO_LABELS.get(similar["tipo"], similar["tipo"])
                cuentas_sim = similar.get("cuentas_usadas", [])
                cuentas_sim_str = " | ".join([
                    f"{c.get('rol','?')}: [{c.get('id','')}] {c.get('name','')}"
                    for c in cuentas_sim[:2]
                ])
                plines.append(
                    f"[PATRÓN SIMILAR DETECTADO — {sim_pct}% similitud]\n"
                    f"• {tipo_sim} — \"{similar['descripcion']}\" ({freq_sim}x) {cuentas_sim_str}\n"
                    f"→ Puedes sugerir este patrón directamente al usuario\n"
                )

            for p in patterns:
                # Evitar duplicar el patrón ya incluido como similar
                if similar and p.get("descripcion") == similar.get("descripcion"):
                    continue
                freq = p.get("frecuencia_count", 1)
                cuentas = p.get("cuentas_usadas", [])
                cuentas_str = " | ".join([
                    f"{c.get('rol','?')}: [{c.get('id','')}] {c.get('name','')}"
                    for c in cuentas[:2]
                ])
                plines.append(
                    f"• {TIPO_LABELS.get(p['tipo'], p['tipo'])} — \"{p['descripcion']}\" "
                    f"({freq}x) {cuentas_str}"
                )
            patterns_str = "\n".join(plines)
            if any(p.get("frecuencia_count", 1) >= 5 for p in patterns):
                patterns_str += "\n\n[MODO AUTOMÁTICO ACTIVO: patrones con 5+ usos se ejecutan sin preguntar cuentas]"
        else:
            patterns_str = "Sin patrones aprendidos aún. Después de registrar 3+ transacciones similares, comenzaré a sugerirlas automáticamente."
    except Exception:
        patterns_str = "Sin patrones disponibles."

    return accounts_str, patterns_str


DOCUMENT_ANALYSIS_SYSTEM_PROMPT = """Eres el Agente Contable IA de RODDOS Colombia, experto en contabilidad NIIF Colombia.
Has recibido un comprobante contable (factura, recibo, comprobante de pago, extracto u otro documento).

PLAN DE CUENTAS DISPONIBLE EN ALEGRA (cuentas hoja):
{accounts_context}

LOANBOOKS ACTIVOS EN RODDOS:
{loanbook_context}

FECHA ACTUAL: {fecha_actual}

TU TAREA:
1. Lee y analiza cuidadosamente el documento
2. Extrae TODOS los datos relevantes con máxima precisión
3. Determina el tipo de transacción contable
4. Detecta si es un pago de cuota de Loanbook RODDOS (busca: "RODDOS", moto, cuota, plan de pagos, o si el monto coincide con algún Loanbook activo)
5. Sugiere la cuenta contable correcta del plan de cuentas disponible
6. Propone la acción a ejecutar en Alegra

REGLAS CONTABLES:
- Facturas de proveedores con IVA → accion_contable = registrar_factura_compra
- Recibos, comprobantes de servicio sin facturas formales → accion_contable = crear_causacion
- Comprobantes de pago/transferencias → accion_contable = registrar_pago
- ReteFuente: calcula según tipo (servicios 4%, honorarios 10%, arrendamiento 3.5%, compras 2.5%)
- Si el documento es ilegible o incompleto → ilegible=true, lista campos en campos_faltantes

DESPUÉS de tu análisis en texto, incluye OBLIGATORIAMENTE este bloque:
<document_proposal>
{
  "es_pago_loanbook": false,
  "loanbook_codigo": null,
  "tipo_documento": "factura_compra",
  "proveedor_cliente": "",
  "nit": "",
  "fecha": "YYYY-MM-DD",
  "numero_documento": "",
  "concepto": "",
  "subtotal": 0,
  "iva_porcentaje": 0,
  "iva_valor": 0,
  "retefuente_valor": 0,
  "retefuente_tipo": "ninguna",
  "total": 0,
  "accion_contable": "crear_causacion",
  "cuenta_gasto_id": null,
  "cuenta_gasto_nombre": "",
  "ilegible": false,
  "campos_faltantes": []
}
</document_proposal>

Valores válidos tipo_documento: factura_compra | factura_venta | recibo_pago | comprobante_egreso | extracto_bancario | otro
Valores válidos accion_contable: registrar_factura_compra | crear_causacion | registrar_pago | ninguna
Valores retefuente_tipo: ninguna | servicios_4 | servicios_6 | honorarios_10 | arrendamiento_3.5 | compras_2.5

IMPORTANTE: cuenta_gasto_id debe ser un ID NUMÉRICO real del plan de cuentas listado arriba.
Responde en español colombiano. Sé muy preciso con montos y cuentas."""


async def process_document_chat(
    session_id: str, user_message: str,
    file_content: str, file_name: str, file_type: str,
    db, user: dict
) -> dict:
    """Process a chat message that includes a document (image/PDF) for accounting analysis."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")

    from alegra_service import AlegraService
    alegra_service = AlegraService(db)

    # Always load full accounts context for document analysis
    accounts_str, _ = await gather_accounts_context("causar registrar factura", alegra_service, db)

    # Get active loanbooks for payment detection
    loanbook_str = "Sin loanbooks activos."
    try:
        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}},
            {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "saldo_pendiente": 1, "plan": 1}
        ).to_list(15)
        if loans:
            loanbook_str = "\n".join([
                f"• [{l['codigo']}] {l['cliente_nombre']} — Plan: {l.get('plan', '')} Saldo: ${l.get('saldo_pendiente', 0):,.0f}"
                for l in loans
            ])
    except Exception:
        pass

    fecha_actual = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = (
        DOCUMENT_ANALYSIS_SYSTEM_PROMPT
        .replace("{accounts_context}", accounts_str)
        .replace("{loanbook_context}", loanbook_str)
        .replace("{fecha_actual}", fecha_actual)
    )

    # Save user message to DB
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": f"{user_message or 'Analiza este comprobante'}\n[Archivo adjunto: {file_name}]",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # Call Claude with file content (use separate session to avoid polluting main chat context)
    chat = LlmChat(
        api_key=api_key,
        session_id=f"{session_id}-doc-{uuid.uuid4().hex[:8]}",
        system_message=system_prompt,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    file_obj = FileContent(content_type=file_type, file_content_base64=file_content)
    text = user_message or "Analiza este comprobante contable y extrae todos los datos para su registro en Alegra."
    msg = UserMessage(text=text, file_contents=[file_obj])
    response_text = await chat.send_message(msg)

    # Parse <document_proposal> block
    document_proposal = None
    clean_response = response_text
    if "<document_proposal>" in response_text and "</document_proposal>" in response_text:
        try:
            start = response_text.index("<document_proposal>") + len("<document_proposal>")
            end = response_text.index("</document_proposal>")
            proposal_json = response_text[start:end].strip()
            document_proposal = json.loads(proposal_json)
            clean_response = (
                response_text[:response_text.index("<document_proposal>")].strip()
                + response_text[end + len("</document_proposal>"):].strip()
            ).strip()
        except Exception:
            pass

    # Also parse <action> block if present
    action = None
    if "<action>" in clean_response and "</action>" in clean_response:
        try:
            start = clean_response.index("<action>") + 8
            end = clean_response.index("</action>")
            action = json.loads(clean_response[start:end].strip())
            clean_response = (
                clean_response[:clean_response.index("<action>")].strip()
                + clean_response[end + 9:].strip()
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
        "document_proposal": document_proposal,
        "pending_action": action,
        "session_id": session_id,
    }


async def process_chat(
    session_id: str, user_message: str, db, user: dict,
    file_content: str = None, file_name: str = None, file_type: str = None,
) -> dict:
    # Route to document analysis if a file was attached
    if file_content:
        return await process_document_chat(
            session_id, user_message, file_content,
            file_name or "documento", file_type or "image/jpeg",
            db, user
        )

    # ── CFO intent detection (antes del flujo contable normal) ───────────────
    from services.cfo_agent import is_cfo_query, process_cfo_query
    if is_cfo_query(user_message):
        return await process_cfo_query(user_message, db, user, session_id)
    # ─────────────────────────────────────────────────────────────────────────

    api_key = os.environ.get("EMERGENT_LLM_KEY")

    # Import here to avoid circular import
    from alegra_service import AlegraService
    alegra_service = AlegraService(db)

    # Gather context (parallel where possible)
    context_data = await gather_context(user_message, alegra_service, db)
    accounts_str, patterns_str = await gather_accounts_context(user_message, alegra_service, db)
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

    # Append inventory / loanbook / catalog items context if injected
    extra_context = ""
    if context_data.get("items_catalogo"):
        items_list = context_data["items_catalogo"]
        lines = [f"  • [{it['id']}] {it['name']} (type={it['type']})" for it in items_list]
        extra_context += "\n\nITEMS_CATALOGO_ALEGRA (IDs válidos para registrar_factura_compra → purchases.items):\n" + "\n".join(lines)
    if context_data.get("inventario_disponible"):
        motos_list = context_data["inventario_disponible"]
        lines = [f"  • [{m.get('id','')}] {m.get('marca','')} {m.get('version','')} {m.get('color','')} — Chasis: {m.get('chasis','')} Motor: {m.get('motor','')} Precio: ${m.get('total',0):,.0f}" for m in motos_list[:20]]
        extra_context += "\n\nINVENTARIO_DISPONIBLE (motos en stock para venta):\n" + "\n".join(lines)
    if context_data.get("loanbook_activos"):
        lb_list = context_data["loanbook_activos"]
        lines = [
            f"  • [{l['codigo']}] id={l['id']} — {l['cliente']} | Plan: {l['plan']} | "
            f"Saldo: ${l['saldo_pendiente']:,.0f} | Estado: {l['estado']} | "
            f"Alegra factura: {l.get('factura_alegra_id','?')} | "
            f"Entrega: {l.get('fecha_entrega','pendiente')}"
            for l in lb_list[:10]
        ]
        extra_context += "\n\nLOANBOOK_ACTIVOS:\n" + "\n".join(lines)

    # Build system prompt with all context
    system_prompt = (
        AGENT_SYSTEM_PROMPT
        .replace("{context}", context_str + extra_context)
        .replace("{iva_context}", iva_context_str)
        .replace("{accounts_context}", accounts_str)
        .replace("{patterns_context}", patterns_str)
    )

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

    # ── Extract internal _metadata BEFORE anything else ──────────────────────
    internal_metadata: dict = {}
    if isinstance(payload, dict):
        internal_metadata = payload.pop("_metadata", None) or {}

    # ── Special case: registrar_entrega (internal-only, no Alegra call) ──────
    if action_type == "registrar_entrega":
        loan_id = payload.get("loanbook_id", "") or internal_metadata.get("loanbook_id", "")
        loan_codigo = payload.get("loanbook_codigo", "")
        fecha_entrega = payload.get("fecha_entrega", "")
        if not fecha_entrega:
            raise ValueError("Falta fecha_entrega para registrar la entrega")

        # Look up by id or codigo
        loan = await db.loanbook.find_one({"id": loan_id}, {"_id": 0})
        if not loan and loan_codigo:
            loan = await db.loanbook.find_one({"codigo": loan_codigo}, {"_id": 0})
        if not loan:
            raise ValueError(f"Loanbook '{loan_id or loan_codigo}' no encontrado")

        from routers.loanbook import register_entrega as lb_entrega, EntregaRequest
        req_obj = EntregaRequest(fecha_entrega=fecha_entrega)
        result = await lb_entrega(loan["id"], req_obj, user)
        result_dict = dict(result) if not isinstance(result, dict) else result

        from post_action_sync import post_action_sync
        sync_result = await post_action_sync(
            "registrar_entrega", result_dict, payload, db, user, metadata=internal_metadata
        )
        return {
            "success": True,
            "result": result_dict,
            "id": loan["id"],
            "message": result_dict.get("message", "Entrega registrada y Loanbook activado"),
            "sync": sync_result,
        }

    ACTION_MAP = {
        "crear_factura_venta": ("invoices", "POST"),
        "registrar_factura_compra": ("bills", "POST"),
        "crear_causacion": ("journals", "POST"),
        "registrar_pago": ("payments", "POST"),
        "crear_contacto": ("contacts", "POST"),
    }

    if action_type not in ACTION_MAP:
        raise ValueError(f"Acción no reconocida: {action_type}")

    endpoint, method = ACTION_MAP[action_type]

    # ── CREAR_CONTACTO: handle _next_action and internal fields ──────────────
    if action_type == "crear_contacto":
        import json as _json
        next_action = payload.pop("_next_action", None)
        # Remove internal display-only fields before sending to Alegra
        payload.pop("accounting_account_suggested", None)
        payload.pop("accounting_account_name", None)
        # Ensure nameObject.lastName is never empty (Alegra Colombia requires it)
        name_obj = payload.get("nameObject")
        if isinstance(name_obj, dict) and not name_obj.get("lastName"):
            full_name = name_obj.get("firstName", "") or payload.get("name", "")
            parts = full_name.strip().split(" ", 1)
            name_obj["firstName"] = parts[0]
            name_obj["lastName"] = parts[1] if len(parts) > 1 else "."
        # Note: keep 'name' and 'nameObject' - both are used by Alegra

        result = await service.request(endpoint, method, payload)
        # Check if Alegra returned an error in the body (200 with error code)
        if isinstance(result, dict) and result.get("code") and not result.get("id"):
            err_msg = result.get("message", "Error al crear el contacto en Alegra")
            raise HTTPException(status_code=400, detail=f"Alegra: {err_msg} (código {result.get('code')})")
        new_contact_id = str(result.get("id", "")) if isinstance(result, dict) else ""
        contact_name = ""
        if isinstance(result, dict):
            no = result.get("nameObject") or {}
            contact_name = f"{no.get('firstName','')} {no.get('lastName','')}".strip() or result.get("name", "")

        # Replace placeholder in next_action payload with real ID
        if next_action and new_contact_id:
            next_str = _json.dumps(next_action)
            next_str = next_str.replace('"__NEW_CONTACT_ID__"', new_contact_id)
            next_str = next_str.replace("__NEW_CONTACT_ID__", new_contact_id)
            next_action = _json.loads(next_str)

        return {
            "success": True,
            "result": result,
            "id": new_contact_id,
            "message": f"Tercero '{contact_name}' creado exitosamente en Alegra",
            "sync": {},
            **({"next_pending_action": next_action} if next_action else {}),
        }

    # ── CREAR_CAUSACION: strip display-only 'name' from entries ──────────────
    if action_type == "crear_causacion":
        entries = payload.get("entries", [])
        payload["entries"] = [
            {"id": e["id"], "debit": e.get("debit", 0), "credit": e.get("credit", 0)}
            for e in entries
        ]

    endpoint, method = ACTION_MAP[action_type]

    # ── Guard: prevent double-selling same moto ───────────────────────────────
    if action_type == "crear_factura_venta":
        moto_id   = internal_metadata.get("moto_id", "")
        moto_chas = internal_metadata.get("moto_chasis", "")
        if moto_id or moto_chas:
            query = {"id": moto_id} if moto_id else {"chasis": moto_chas}
            moto = await db.inventario_motos.find_one(query, {"_id": 0, "estado": 1, "chasis": 1})
            if moto and moto.get("estado") not in ("Disponible", None, ""):
                raise ValueError(
                    f"La moto {moto_chas or moto_id} ya fue registrada como '{moto.get('estado')}'. "
                    "No se puede vender una moto que no está disponible."
                )

    result = await service.request(endpoint, method, payload)

    # POST ACTION SYNC — updates internal modules and emits events
    from post_action_sync import post_action_sync
    sync_result = await post_action_sync(
        action_type,
        result if isinstance(result, dict) else {},
        payload,
        db,
        user,
        metadata=internal_metadata,
    )

    if isinstance(result, dict):
        doc_id = result.get("id") or result.get("number") or ""
    elif isinstance(result, list) and result:
        doc_id = result[0].get("id") if isinstance(result[0], dict) else ""
    else:
        doc_id = ""

    # agent_memory.save_pattern() — guarda patrón cuando el usuario confirma
    await save_action_pattern(db, user, action_type, payload)

    return {
        "success": True,
        "result": result,
        "id": doc_id,
        "message": "Ejecutado en Alegra exitosamente",
        "sync": sync_result,
    }
