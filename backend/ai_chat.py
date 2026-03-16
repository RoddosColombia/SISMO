import os
import re
import uuid
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContent


# ── Helpers para context builders (evitar NoneType format errors) ─────────────

def _safe_num(val, default: float = 0) -> float:
    """Safe numeric: returns `default` if val is None or non-numeric."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_str(val, default: str = "") -> str:
    """Safe string: returns `default` if val is None."""
    if val is None:
        return default
    return str(val)


# ── Helpers de detección de tipo de proveedor ────────────────────────────────
_PJ_SUFFIXES = (
    "SAS", "S.A.S", "LTDA", "S.A.", "SA ", "CORP", "INC", "SOCIEDAD",
    "EMPRESA", "CONSULTORÍA", "CONSULTORIA", "COMPAÑÍA", "COMPANIA",
    "GROUP", "SERVICIOS", "SOLUTIONS", "SOLUCIONES", "ASOCIADOS",
    "ASOCIADAS", "CIA ", "CÍA ", "LIMITADA", "INMOBILIARIA", "AGENCIA",
)
_PN_PATTERN = re.compile(
    r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b'
)
# Detecta "CC 1020345678", "cédula: 1020345678", "NIT 900.888.777-1", etc.
_ID_PATTERN = re.compile(
    r'\b(?:cc|cédula|cedula|nit|c\.c\.)\s*[:\#]?\s*([\d.]{6,12}(?:-\d)?)',
    re.IGNORECASE,
)


def _detectar_tipo_proveedor(msg: str) -> str:
    """Detecta si el proveedor en el mensaje es PN (persona natural) o PJ (empresa).

    Returns: 'PN', 'PJ', o 'UNCLEAR'.
    """
    upper = msg.upper()
    if any(suf.upper() in upper for suf in _PJ_SUFFIXES):
        return "PJ"
    if _PN_PATTERN.search(msg):
        return "PN"
    return "UNCLEAR"


def _detectar_identificacion(msg: str) -> str | None:
    """Detecta si hay un número de CC o NIT explícito en el mensaje.

    Returns: número como string, o None si no hay.
    """
    m = _ID_PATTERN.search(msg)
    return m.group(1) if m else None

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
MÓDULO CFO ESTRATÉGICO — REGLAS PERMANENTES
═══════════════════════════════════════════════════
Aplica estas reglas en CADA mensaje que involucre dinero, gastos o decisiones financieras.
Los datos de cartera vienen del contexto {cfo_context}

REGLA 1 — RESERVA MÍNIMA:
Siempre mantener reserva para 2 semanas de gastos fijos.
Si una acción deja la caja por debajo de esa reserva → alerta ANTES de confirmar:
"⚠️ Esta operación deja la caja en $X, por debajo de la reserva mínima de $X (2 semanas de gastos)."

REGLA 2 — DEUDA NO PRODUCTIVA PRIMERO:
Si hay deuda NP vencida >30 días Y el usuario pide comprar inventario → advertir:
"Tienes deuda no productiva vencida por $X. Recomiendo liquidarla antes de comprar motos.
¿Quieres continuar de todas formas?"

REGLA 3 — PISO DE CRÉDITOS:
Monitorear permanentemente. Si créditos activos caen bajo el mínimo calculado → alerta proactiva:
"⚠️ Tienes N créditos activos ($X/sem). El mínimo para cubrir gastos fijos es N.
Prioriza nuevas ventas a crédito esta semana."

REGLA 4 — LÍMITE DE COMPROMISOS:
No comprometer más del 60% del recaudo semanal en gastos fijos + deuda combinados.
Si se supera ese límite → advertir con el porcentaje real.

REGLA 5 — CLASIFICACIÓN AUTOMÁTICA DE GASTOS:
Cada nuevo gasto registrado → clasificarlo como productivo o no productivo automáticamente
e informar al usuario cuál es la clasificación y por qué.

═══════════════════════════════════════════════════
REGLA FUNDAMENTAL DE LIQUIDEZ — MODELO DE NEGOCIO RODDOS
═══════════════════════════════════════════════════
RODDOS vende el 100% de sus motos a CUOTAS (planes P26S, P39S, P52S, P78S).
Esto significa: la FACTURACIÓN NO genera liquidez inmediata.
Una factura de $9.000.000 NO equivale a $9.000.000 en caja.

LA LIQUIDEZ REAL proviene ÚNICAMENTE de:

Fuente 1 — Cuotas iniciales (irregular, no predecible semana a semana):
  • Pago único al momento de la venta. Ejemplo: ~$1.460.000/cliente.
  • Total pendiente cobro marzo 2026: $5.300.000.

Fuente 2 — Cuotas semanales recaudo (predecible, fija cada miércoles):
  • Actualmente: 10 loanbooks × cuota promedio = $1.659.400/semana.
  • Esta es la base del flujo de caja operativo.

DÉFICIT OPERATIVO SEMANAL (estado actual):
  recaudo_semanal: $1.659.400
  gastos_fijos_semanales: $7.500.000
  déficit_semanal: -$5.840.600
  (El -$20.840.600 anterior era incorrecto — incluía reserva × 3 gastos)

SEPARACIÓN CONTABLE vs FINANCIERA:
  • Estado de Resultados P&L → base devengada (útil para contabilidad e impuestos)
  • Plan de Ingresos CFO → base caja / recaudo real (útil para decisiones operativas)
  NUNCA confundir una con la otra al dar recomendaciones de liquidez.

CUANDO EL USUARIO PREGUNTE "¿cuánto dinero entra esta semana?":
  → Respuesta correcta: "$1.659.400 de recaudo de cuotas el miércoles"
  → NUNCA responder con cifras de facturación mensual o P&L.

CUANDO EL USUARIO PREGUNTE "¿cuántas motos necesito vender?":
  → Cada venta aporta cuota_inicial ese día + cuota_semanal adicional al recaudo.
  → Para cubrir el déficit semanal de $5.840.600:
     motos_necesarias ≈ TECHO($5.840.600 / $1.460.000) ≈ 4 ventas con cuota inicial de $1.460.000
     O bien: cada moto nueva agrega ~$167.722/semana al recaudo — necesitas 35 motos adicionales para cerrar el gap solo con recaudo.
  → META 90 días (al 20-jun-2026): 55-60 ventas = ~45 créditos activos = autosostenible.

DATOS CFO EN TIEMPO REAL (para responder consultas — los valores reales vienen de {cfo_context}):
• Recaudo semanal actual: $1.659.400 (10 loanbooks activos)
• Déficit semanal: -$5.840.600 (recaudo - gastos fijos)
• Ticket promedio cuota: $167.722/semana
• Para autosostenibilidad: mínimo 45 créditos activos

TIPOS DE ACCIÓN DISPONIBLES:
• crear_factura_venta      → POST /invoices
• registrar_factura_compra → POST /bills
• anular_factura_compra    → DELETE /bills/{id}
• crear_causacion          → POST /journals
• registrar_pago           → POST /payments
• crear_contacto           → POST /contacts
• registrar_entrega        → ACCIÓN INTERNA (activa plan de cuotas)
• calcular_retencion       → cálculo local (sin ejecutar en Alegra)
• consultar_facturas       → información de facturas existentes
• crear_nota_credito       → POST /credit-notes  (nota crédito sobre factura de venta)
• crear_nota_debito        → POST /debit-notes   (cargo adicional sobre factura)
• crear_comprobante_ingreso → POST /journal-entries tipo ingreso de caja
• crear_comprobante_egreso  → POST /journal-entries tipo egreso de caja

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

Si el usuario especificó chasis o moto_id:
  - Si no existe en inventario → RECHAZA:
    "❌ No encontré la moto con chasis [X] en el inventario. 
     Verifica el chasis o registra primero la entrada de esa unidad."
  - Si existe pero estado ≠ "Disponible" → RECHAZA con detalle:
    "❌ La moto [chasis X] tiene estado '[estado]'. No se puede facturar.
     [Si estado=Vendida]: Vinculada a factura [numero] del [fecha_venta]."

Si el usuario NO especificó chasis (venta genérica por modelo):
  - Cuenta cuántas unidades del modelo tienen estado "Disponible" en INVENTARIO_DISPONIBLE.
  - Si count == 0 → RECHAZA:
    "❌ No hay unidades disponibles de [modelo]. Stock actual: 0.
     Registra una compra primero para agregar unidades."
  - Si count > 0 → muestra las opciones:
    "Hay [N] unidades disponibles de [modelo]:
     • Chasis [A] — [color A]
     • Chasis [B] — [color B]
     ¿Cuál vas a vender? (responde el número de chasis)"
    Espera confirmación antes de continuar.

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

Solo para compras de motos/inventario, incluye _metadata para auto-registro en inventario.
REGLA OBLIGATORIA: Si la compra involucra motos o vehículos, el campo _metadata.motos_a_agregar
es OBLIGATORIO. Nunca omitirlo en compras de motos.

PROTOCOLO DE COMPRA DE MOTOS — sigue este orden:

PASO 1 — Verificar datos mínimos:
Si el usuario NO especificó color y chasis de cada unidad, PREGUNTA ANTES de ejecutar:
  "Para registrar las motos en inventario necesito datos de cada unidad:
   • ¿Cuál es el color?
   • ¿Número de chasis? (recomendado)
   • ¿Número de motor? (opcional)
   Si no tienes los datos ahora, responde 'sin datos' y las motos quedarán pendientes."

PASO 2 — Si el usuario responde "sin datos" o "sin chasis":
   Crea las motos en inventario con estado "Pendiente datos" (no "Disponible").
   Indica al usuario: "Las motos se agregaron con estado 'Pendiente datos'. 
   Completa chasis/color en Módulo Motos antes de venderlas."

PASO 3 — EXTRACCIÓN DE CAMPOS DE MOTOS (aplica cuando el usuario pega texto de una factura):

Las facturas de Auteco/proveedores suelen incluir descripción en bloque. Debes dividirlas así:

  ENTRADA: "MOTOCICLETA HONDA CB 125 TWISTER ROJA VIN: 9C2KC1710RR000123 MOTOR: KC17E0000456"
  SALIDA esperada:
    referencia: "HONDA CB 125 TWISTER"    ← TODO hasta el color, sin el color
    color:      "ROJA"                    ← solo el color (puede ser 2 palabras: "NEGRO MATE")
    chasis:     "9C2KC1710RR000123"       ← después de VIN: / CHASIS: / BASTIDOR: / No. SERIE:
    motor:      "KC17E0000456"            ← después de MOTOR: / No. MOTOR: / MOT:
    marca:      "HONDA"                   ← primera palabra de la referencia
    
  Colores típicos colombianos (1 o 2 palabras):
  ROJA, AZUL RACING, NEGRO MATE, BLANCA PERLA, GRIS OSCURO, VERDE HUNTER,
  NARANJA, AMARILLA SPORT, PLATA, ROJO CANDY

  Si no puedes identificar el color claramente → color: "" y PREGUNTA al usuario.
  Si no hay chasis → chasis: "" y ADVIERTE:
    "⚠️ Chasis no detectado. Sin chasis no se puede prevenir doble venta."

REGLA CRÍTICA: NUNCA cantidad > 1 con un solo chasis.
  Si la factura trae 3 motos distintas → 3 objetos separados, cada uno con cantidad: 1.
  Solo usa cantidad > 1 si el usuario confirma que son unidades sin datos individuales (sin chasis).

PASO 4 — Formato _metadata obligatorio para compra de motos:
{
  "_metadata": {
    "es_compra_motos": true,
    "proveedor_nombre": "[nombre]",
    "plazo_dias": 90,
    "motos_a_agregar": [
      {
        "referencia": "HONDA CB 125 TWISTER",  // modelo sin color
        "marca":      "HONDA",                 // REQUERIDO
        "version":    "CB 125 TWISTER",        // REQUERIDO (= referencia sin marca)
        "color":      "ROJA",                  // opcional pero extraer siempre
        "chasis":     "9C2KC1710RR000123",     // opcional pero recomendado
        "motor":      "KC17E0000456",          // opcional
        "cantidad":   1,                       // SIEMPRE 1 si hay chasis
        "precio_unitario": 7058824,            // REQUERIDO
        "año":        2026                     // si se menciona
      }
    ]
  }
}

PASO 5 — Tarjeta de confirmación ANTES de ejecutar la compra:
Muestra el resumen de unidades a registrar en inventario:
  "📦 **UNIDADES A INGRESAR AL INVENTARIO**
   Unidad 1: [referencia] | Color: [color] | Chasis: [chasis] | Motor: [motor]
   Unidad 2: ...
   ¿Confirmas los datos o necesitas corregir algo?"
Si el usuario dice "corregir X", actualiza ese campo antes de ejecutar.

═══════════════════════════════════════════════════
FLUJO — ANULACIÓN DE FACTURA DE COMPRA
═══════════════════════════════════════════════════
Cuando el usuario pide "anula la factura de compra [número o ID]":

PASO 1 — Buscar la factura:
  Si el usuario da número (ej: "FC-2025-001"), buscarlo en el contexto de facturas.
  Si da ID numérico de Alegra, usarlo directamente.

PASO 2 — Mostrar tarjeta de confirmación OBLIGATORIA:
  Acción: anular_factura_compra
  Tipo: WARNING (destructivo, irreversible en Alegra)
  Campos del summary:
    - Factura: [número]
    - Proveedor: [nombre]
    - Monto: $[X]
    - Motos vinculadas: [N] unidades (si aplica)
    - Advertencia: "Esta acción no se puede revertir"

PASO 3 — Al confirmar, usar este formato:
<action>
{
  "type": "anular_factura_compra",
  "title": "Anular Factura de Compra [número]",
  "summary": [
    {"label": "Factura", "value": "[número]"},
    {"label": "Proveedor", "value": "[nombre]"},
    {"label": "Monto", "value": "$[X]"},
    {"label": "⚠️ Advertencia", "value": "Esta acción no se puede revertir"}
  ],
  "payload": {
    "bill_id": "[id_alegra_de_la_bill]",
    "bill_numero": "[número visible, ej: FC-2025-001]",
    "proveedor_nombre": "[nombre]",
    "total": [monto],
    "_metadata": {
      "bill_numero": "[número visible]",
      "proveedor_nombre": "[nombre]",
      "total": [monto]
    }
  }
}
</action>

BLOQUEO AUTOMÁTICO: Si alguna moto vinculada a esa factura tiene estado "Vendida" o "Entregada",
NO puedes anular. Informa al usuario antes de mostrar la tarjeta de confirmación:
  "❌ No se puede anular la factura [X]. La moto con chasis [Y] vinculada a esta factura
   ya fue vendida. Resuelve primero esa venta antes de anular la compra."

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

REGLA CRÍTICA — IDs DE CUENTAS:
El campo "id" en cada entry DEBE ser el ID numérico interno de Alegra de esa empresa.
En el contexto recibirás "cuentas_contables": lista de {id, code, name} con los IDs reales.
USA SIEMPRE el id de esa lista. NUNCA inventes un ID ni uses el código PUC como ID.
Si no ves la cuenta exacta en la lista, escoge la más cercana por nombre o cuenta padre.
El campo "name" es informativo para el usuario — el sistema lo elimina antes de enviar a Alegra.
NUNCA uses {"account": {"id": ...}} — ese formato da error 400.

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

═══════════════════════════════════════════════════
PLAN DE CUENTAS RODDOS — IDs INTERNOS DE ALEGRA
(Usa SIEMPRE estos IDs en crear_causacion. No inventes IDs.)
═══════════════════════════════════════════════════
BANCOS:
  [5314] 11100501 — Bancolombia 2029
  [5315] 11100502 — Bancolombia 2540
  [5318] 11100505 — BBVA 0210
  [5319] 11100506 — BBVA 0212
  [5321] 11200501 — Banco de Bogotá Ahorros
  [5322] 11200502 — Davivienda Ahorros 482
  [5310] 11050501 — Caja general

CARTERA / ACTIVOS:
  [5326] 13050501 — Cuentas por cobrar clientes nacionales
  [5327] 13050502 — Creditos Directos Roddos (cuotas loanbook)
  [5348] 14350101 — Motos (Inventario)
  [5349] 14350102 — Repuestos (Inventario)

INGRESOS:
  [5442] 41350501 — Motos (Ventas)
  [5445] 41350601 — Repuestos (Ventas)
  [5456] 41502001 — Creditos Directos Roddos (Intereses mora/financiación)
  [5453] 41459507 — Matricula
  [5451] 41459505 — Aval

COSTOS:
  [5520] 61350501 — Motos (Costo ventas)
  [5523] 61350601 — Repuestos (Costo ventas)
  [5531] 61459507 — Matricula (Costo)

PASIVOS — IVA:
  [5404] 24080601 — IVA Generado 19%
  [5406] 24081001 — IVA Descontable en Compras 19%
  [5408] 24081501 — IVA Descontable por Servicios

PASIVOS — RETENCIONES POR PAGAR:
  [5381] 23651501 — Retenciones honorarios 10% (persona natural)
  [5382] 23651502 — Retenciones honorarios 11% (persona jurídica)
  [5383] 23652501 — Retenciones servicios 4%
  [5386] 23653001 — Retenciones arriendo 3.5%
  [5388] 23654001 — Retenciones compra 2.5%
  [5392] 23680501 — RteICA 11.04‰ Bogotá
  [5410] 241205   — ICA por pagar
  [5376] 220505   — Cuentas por pagar a proveedores nacionales

GASTOS FRECUENTES:
  [5480] 512010 — Arrendamientos (arriendo local Calle 127)
  [5462] 510506 — Sueldos y salarios
  [5478] 511505 — Industria y Comercio (ICA gasto)
  [5484] 513520 — Software/Sistemas (Emergent, Alegra, Mercately)
  [5487] 513535 — Teléfono / Internet
  [5507] 530505 — Gastos bancarios
  [5508] 530515 — Comisiones
  [5509] 531520 — Gravamen al movimiento Financiero (4x1000)
  [5497] 519530 — Útiles, papelería y fotocopia

ASIENTOS TÍPICOS DE RODDOS:
• Arriendo Calle 127:    DEB [5480] Arrendamientos | CRED [5386] Ret.arriendo 3.5% | CRED [proveedor] Neto
• Honorarios PN:         DEB [cuenta gasto]         | CRED [5381] Ret.hon. 10%     | CRED banco/proveedor
• Honorarios PJ:         DEB [cuenta gasto]         | CRED [5382] Ret.hon. 11%     | CRED banco/proveedor
• Servicios (mant/aseo): DEB [cuenta gasto]         | CRED [5383] Ret.servicios 4% | CRED proveedor
• Venta moto:            DEB [5326] Cartera         | CRED [5442] Ingresos motos   | CRED [5404] IVA si aplica
• Costo venta moto:      DEB [5520] Costo motos     | CRED [5348] Inventario motos
• Pago cuota loanbook:   DEB banco                  | CRED [5327] Créditos Directos | CRED [5456] Interés mora
• Software/licencia:     DEB [5484] Sistemas        | CRED proveedor

REGLA CRÍTICA — RETENCIONES EN HONORARIOS (3 casos, SEGUIR EN ORDEN):

CASO 1 — Tipo detectado Y número de CC/NIT disponible en el mensaje:
  La sección "CUENTAS REALES DE RODDOS" muestra "PROVEEDOR DETECTADO: PERSONA NATURAL" Y hay CC en el mensaje
  → ACCIÓN: Genera el bloque <action> crear_contacto + crear_causacion DIRECTAMENTE. NO hagas ninguna pregunta.
  → Usa retención 10%: [5381] 23651501 para PN
  La sección muestra "PROVEEDOR DETECTADO: PERSONA JURÍDICA" Y hay NIT en el mensaje
  → ACCIÓN: Genera el bloque <action> crear_contacto + crear_causacion DIRECTAMENTE. NO hagas ninguna pregunta.
  → Usa retención 11%: [5382] 23651502 para PJ

CASO 2 — Tipo detectado pero falta número de CC/NIT:
  La sección muestra "PROVEEDOR DETECTADO: PERSONA NATURAL" pero NO hay CC en el mensaje
  → ACCIÓN: Haz UNA sola pregunta: "¿Cuál es el número de cédula de [nombre]?"
  → NO preguntes el tipo — ya está determinado. NO preguntes nada más.
  La sección muestra "PROVEEDOR DETECTADO: PERSONA JURÍDICA" pero NO hay NIT en el mensaje
  → ACCIÓN: Haz UNA sola pregunta: "¿Cuál es el NIT de [nombre]?"
  → NO preguntes el tipo — ya está determinado. NO preguntes nada más.

CASO 3 — Tipo NO detectado:
  La sección muestra "TIPO DE PROVEEDOR NO DETECTADO"
  → ACCIÓN: Pregunta UNA vez: "¿[nombre] es persona natural (PN) o empresa (persona jurídica)?"
  → Luego pide NIT/CC en la siguiente respuesta.

NUNCA uses ambas retenciones a la vez. Solo una según el tipo de proveedor.
NUNCA inventes ni uses NIT/CC ficticios o placeholders — espera el dato real del usuario.

═══════════════════════════════════════════════════
FUENTES DE DATOS POR PRIORIDAD
═══════════════════════════════════════════════════
Para consultas de inventario (motos disponibles):
  1. INVENTARIO_DISPONIBLE del contexto (MongoDB — más actualizado)
  2. Consulta GET /items en Alegra (product activos)
  3. Inferencia: 10 loanbooks activos = 10 motos entregadas; facturas compra recientes = unidades adquiridas
  4. Último estado conocido desde sesión anterior

Para consultas de cartera/cobros:
  1. LOANBOOK_ACTIVOS del contexto (MongoDB)
  2. GET /invoices en Alegra filtrado por cliente
  3. roddos_events para movimientos recientes

Para consultas contables/fiscales:
  1. GET /journal-entries en Alegra del período
  2. GET /invoices + GET /bills del período
  3. cfo_configuracion para parámetros fiscales

═══════════════════════════════════════════════════
PRINCIPIOS DE BLINDAJE DEL AGENTE (CRÍTICOS)
═══════════════════════════════════════════════════
PRINCIPIO 1 — Nunca fallar en silencio:
  Antes de reportar cualquier error SIEMPRE:
  a) Intenta al menos 2 fuentes alternativas según la guía de prioridad arriba
  b) Si todas fallan, explica exactamente QUÉ falló y POR QUÉ en lenguaje claro
  c) Propón SIEMPRE 2 alternativas concretas que el usuario puede tomar
  NUNCA respondas solo "Hubo un error" — siempre da contexto y opciones

PRINCIPIO 2 — Acción sobre información:
  Cuando no puedas obtener el dato exacto, usa lo que SÍ sabes:
  • Datos de sesiones anteriores (indicarlos como estimaciones)
  • Datos inferibles desde loanbooks (10 activos = 10 motos entregadas a crédito)
  • Dirección al módulo específico: inventario→Motos | cartera→RADAR | impuestos→Impuestos

PRINCIPIO 3 — Completitud contable:
  Para CUALQUIER operación contable:
  a) Débitos = Créditos (verificar balance antes de mostrar el asiento)
  b) Usar IDs reales del plan de cuentas (de CUENTAS_CONTABLES_ALEGRA del contexto)
  c) Retenciones según proveedores_config (autoretenedores → NO ReteFuente)
  d) Período IVA cuatrimestral (Ene-Abr | May-Ago | Sep-Dic) — nunca bimestral
  e) Mostrar asiento COMPLETO al usuario antes de confirmar y ejecutar

PRINCIPIO 4 — Diagnóstico ante errores repetidos:
  Si en esta sesión ya ocurrieron 2+ errores similares, activa diagnóstico:
  "Noto problemas repetidos. Estado del sistema:
   • Inventario: [disponible/no disponible]
   • Conexión Alegra: [estado]
   • Loanbooks activos: [N]
   Puedo ayudarte con: [lista alternativas concretas]"

═══════════════════════════════════════════════════
INSTRUCCIÓN PRIORITARIA DE ESTA SESIÓN:
═══════════════════════════════════════════════════
{honorarios_instruccion}"""

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

    # ── MEJORA 3: Actividad del día desde roddos_events ──────────────────────
    try:
        from datetime import timezone as _tz
        hoy_inicio = datetime.now(_tz.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        eventos_hoy = await db.roddos_events.find(
            {"timestamp": {"$gte": hoy_inicio}},
            {"_id": 0, "event_type": 1, "timestamp": 1, "data": 1},
        ).sort("timestamp", -1).limit(10).to_list(10)

        if eventos_hoy:
            lineas = []
            for ev in reversed(eventos_hoy):
                ts = ev.get("timestamp", "")[:16].replace("T", " ")
                tipo = ev.get("event_type", "")
                data = ev.get("data") or {}
                detalle = ""
                if tipo == "factura.venta.creada":
                    detalle = f"FV {_safe_str(data.get('factura_numero'))} — {_safe_str(data.get('cliente_nombre'))} ${_safe_num(data.get('total')):,.0f}"
                elif tipo in ("pago.cuota.registrado", "cuota_pagada"):
                    detalle = f"{_safe_str(data.get('cliente_nombre'))} cuota ${_safe_num(data.get('monto')):,.0f}"
                elif tipo == "asiento.contable.creado":
                    detalle = data.get("concepto", data.get("observations", ""))[:40]
                elif tipo == "factura.compra.creada":
                    detalle = f"{_safe_str(data.get('proveedor'))} ${_safe_num(data.get('total')):,.0f}"
                elif tipo == "loanbook.activado":
                    detalle = f"Entrega moto — {data.get('cliente','')}"
                elif tipo == "inventario.moto.baja":
                    detalle = f"Venta {data.get('moto_desc','')} chasis {data.get('moto_chasis','')}"
                else:
                    detalle = str(data)[:40]
                lineas.append(f"  - {ts} {tipo}: {detalle}")
            context["actividad_hoy"] = "\n".join(lineas)
    except Exception:
        pass
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

    # ── Inject chart of accounts for causacion / journal entry scenarios ─────
    causacion_kws = ["causaci", "gasto", "comprobante", "journal", "asiento", "registro contable",
                     "contabiliz", "débito", "debito", "crédito", "credito", "cuenta"]
    if any(kw in msg_lower for kw in causacion_kws):
        try:
            accts = await alegra_service.get_accounts_from_categories()
            leaf_accts = alegra_service.get_leaf_accounts(accts)
            # Send condensed list: id, code, name (no type/nature to save tokens)
            context["cuentas_contables"] = [
                {"id": a["id"], "code": a.get("code", ""), "name": a["name"]}
                for a in leaf_accts
                if a.get("status", "active") == "active"
            ]
        except Exception:
            pass

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

    # ── Inject available inventory context for moto sale/query scenarios ──────
    sale_kws = ["vende", "venta", "moto", "cb", "fz", "tvs", "kawas", "akt", "chasis",
                "vin", "plan", "p39", "p52", "p78", "financ", "cuota", "entrega", "entregó",
                "inventario", "disponible", "stock", "cuántas motos", "cuantas motos"]
    if any(kw in msg_lower for kw in sale_kws):
        # Ruta 1: MongoDB (fuente principal)
        try:
            motos = await db.inventario_motos.find(
                {"estado": "Disponible"},
                {"_id": 0, "id": 1, "marca": 1, "version": 1, "color": 1, "chasis": 1,
                 "motor": 1, "estado": 1, "total": 1},
            ).sort("created_at", -1).to_list(30)
            if motos:
                context["inventario_disponible"] = motos
                context["inventario_fuente"] = "mongodb"
        except Exception:
            motos = []
        # Ruta 2: Fallback Alegra /items si MongoDB falla o está vacío
        if not motos:
            try:
                alegra_items = await alegra_service.request("items")
                if isinstance(alegra_items, list):
                    motos_alegra = [
                        {"id": it["id"], "marca": "Alegra", "version": it["name"],
                         "color": "", "chasis": "", "motor": "", "estado": "Disponible",
                         "total": it.get("price", [{}])[0].get("price", 0) if it.get("price") else 0}
                        for it in alegra_items
                        if it.get("status") == "active" and it.get("type") == "product"
                    ]
                    if motos_alegra:
                        context["inventario_disponible"] = motos_alegra
                        context["inventario_fuente"] = "alegra"
            except Exception:
                pass
        # Ruta 3: Inferencia desde loanbooks si ambas fuentes fallan
        if not context.get("inventario_disponible"):
            try:
                total_activos = await db.loanbook.count_documents({"estado": "activo"})
                total_motos_inv = await db.inventario_motos.count_documents({})
                context["inventario_inferido"] = {
                    "loanbooks_activos": total_activos,
                    "total_en_inventario_db": total_motos_inv,
                    "nota": "Datos directos no disponibles — usar módulo Motos para detalle exacto"
                }
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
    """Build accounts context from roddos_cuentas (fast) + Alegra patterns.
    Returns (accounts_context_str, patterns_context_str, honorarios_instruccion)."""
    msg_lower = user_message.lower()
    needs_accounts = any(w in msg_lower for w in REGISTER_KEYWORDS)

    accounts_str = "No se requiere plan de cuentas para esta consulta."
    patterns_str = "Sin patrones aprendidos aún."
    honorarios_instruccion = "(Sin instrucción especial para esta consulta.)"

    if not needs_accounts:
        return accounts_str, patterns_str, honorarios_instruccion

    # ── 1. Transaction-type detection → targeted account selection ───────────
    # Detect proveedor type first (needed for honorarios rule)
    tipo_proveedor = _detectar_tipo_proveedor(user_message)

    # Honorarios retención depends on PN vs PJ
    if tipo_proveedor == "PN":
        honorarios_ret = ["23651501"]          # 10% PN
    elif tipo_proveedor == "PJ":
        honorarios_ret = ["23651502"]          # 11% PJ
    else:
        honorarios_ret = ["23651501", "23651502"]  # ambas — agente preguntará

    TRANSACTION_RULES = [
        (["arriendo", "arrendamiento", "alquiler", "calle 127"],
         ["512010", "23653001"]),
        (["honorario", "asesor", "jurídic", "contad", "profesional"],
         ["511025", "511030"] + honorarios_ret),
        (["venta moto", "vender moto", "factura moto", "venta de moto"],
         ["41350501", "61350501", "14350101", "13050501"]),
        (["cuota", "loanbook", "crédito directo", "abono crédito", "pago cuota"],
         ["13050502", "41502001"]),
        (["nómina", "salario", "sueldo", "empleado"],
         ["510506"]),
        (["software", "emergent", "alegra", "mercately", "sistema", "tecnología", "licencia"],
         ["513520"]),
        (["teléfono", "internet", "celular"],
         ["513535"]),
        (["4x1000", "gmf", "gravamen", "cuatro por mil"],
         ["531520"]),
        (["papelería", "útiles", "tóner", "papel"],
         ["519530"]),
        (["iva generado", "iva cobrado", "iva venta"],
         ["24080601"]),
        (["iva descontable", "iva compra", "iva proveedor"],
         ["24081001"]),
        (["retención", "retefuente", "retener"],
         ["23651501", "23651502", "23652501", "23653001", "23654001"]),
        (["matrícula", "matricula"],
         ["41459507", "61459507"]),
        (["repuesto", "accesorio"],
         ["41350601", "61350601", "14350102"]),
    ]

    # Collect codes relevant to detected transaction types
    relevant_codes: set[str] = set()
    for keywords, codes in TRANSACTION_RULES:
        if any(kw in msg_lower for kw in keywords):
            relevant_codes.update(codes)

    # Always include main banks for any payment/receipt
    if any(w in msg_lower for w in ["pagar","pago","recibir","cobrar","recaudo","banco","consign"]):
        relevant_codes.update(["11100501","11100502","11100505","11200501","11200502","11050501"])

    # ── 2. Build accounts string from roddos_cuentas (MongoDB, fast) ─────────
    try:
        if relevant_codes:
            accounts_cursor = db.roddos_cuentas.find(
                {"codigo": {"$in": list(relevant_codes)}}, {"_id": 0}
            )
        else:
            # Fallback: all uso_frecuente=True accounts
            accounts_cursor = db.roddos_cuentas.find(
                {"uso_frecuente": True}, {"_id": 0}
            )
        roddos_accts = await accounts_cursor.to_list(60)

        if roddos_accts:
            lines = [
                f"  [{a['alegra_id']}] {a['codigo']} — {a['nombre']}"
                for a in sorted(roddos_accts, key=lambda x: x["codigo"])
            ]
            cuentas_str = (
                "CUENTAS REALES DE RODDOS (usar estas — ya configuradas en Alegra):\n"
                + "\n".join(lines)
            )

            # ── Honorarios: detect case and build honorarios_instruccion ──────
            is_honorario_msg = any(kw in msg_lower for kw in
                                   ["honorario", "asesor", "profesional", "contad"])
            if is_honorario_msg:
                id_detected = _detectar_identificacion(user_message)
                if tipo_proveedor == "PN":
                    if id_detected:
                        honorarios_instruccion = (
                            f"INSTRUCCION OBLIGATORIA (Caso 1 — Tipo+ID conocidos):\n"
                            f"El sistema detectó: PERSONA NATURAL con CC={id_detected}.\n"
                            f"ACCION INMEDIATA: Genera el bloque <action> crear_contacto+crear_causacion AHORA.\n"
                            f"Retención 10%: cuenta [5381] 23651501. NO hagas ninguna pregunta."
                        )
                    else:
                        honorarios_instruccion = (
                            "INSTRUCCION OBLIGATORIA (Caso 2 — Tipo conocido, CC faltante):\n"
                            "El sistema detectó: PERSONA NATURAL (por el nombre en el mensaje).\n"
                            "ACCION INMEDIATA: Hacer UNA SOLA PREGUNTA, exactamente: "
                            "'¿Cuál es el número de cédula de [nombre del proveedor]?'\n"
                            "PROHIBIDO: NO preguntar si es PN o PJ — ya está determinado.\n"
                            "PROHIBIDO: NO hacer ninguna otra pregunta."
                        )
                elif tipo_proveedor == "PJ":
                    if id_detected:
                        honorarios_instruccion = (
                            f"INSTRUCCION OBLIGATORIA (Caso 1 — Tipo+ID conocidos):\n"
                            f"El sistema detectó: PERSONA JURÍDICA con NIT={id_detected}.\n"
                            f"ACCION INMEDIATA: Genera el bloque <action> crear_contacto+crear_causacion AHORA.\n"
                            f"Retención 11%: cuenta [5382] 23651502. NO hagas ninguna pregunta."
                        )
                    else:
                        honorarios_instruccion = (
                            "INSTRUCCION OBLIGATORIA (Caso 2 — Tipo conocido, NIT faltante):\n"
                            "El sistema detectó: PERSONA JURÍDICA (por sufijo en el nombre).\n"
                            "ACCION INMEDIATA: Hacer UNA SOLA PREGUNTA, exactamente: "
                            "'¿Cuál es el NIT de [nombre del proveedor]?'\n"
                            "PROHIBIDO: NO preguntar si es PN o PJ — ya está determinado.\n"
                            "PROHIBIDO: NO hacer ninguna otra pregunta."
                        )
                else:
                    honorarios_instruccion = (
                        "INSTRUCCION OBLIGATORIA (Caso 3 — Tipo no detectado):\n"
                        "El sistema NO pudo determinar si el proveedor es PN o PJ.\n"
                        "ACCION INMEDIATA: Hacer UNA SOLA PREGUNTA: "
                        "'¿[nombre] es persona natural (PN) o empresa (persona jurídica)?'\n"
                        "NO pedir el NIT/CC todavía — primero confirmar el tipo."
                    )
                # Add compact provider-type note to accounts_str
                pn_note = {
                    "PN": "\n[Sistema: Proveedor detectado como PERSONA NATURAL — retención 10%]",
                    "PJ": "\n[Sistema: Proveedor detectado como PERSONA JURÍDICA — retención 11%]",
                    "UNCLEAR": "\n[Sistema: Tipo de proveedor no determinado]",
                }
                accounts_str = cuentas_str + pn_note.get(tipo_proveedor, "")
            else:
                accounts_str = cuentas_str
        else:
            # Final fallback: full Alegra categories
            accounts_tree = await alegra_service.get_accounts_from_categories()
            leaves = alegra_service.get_leaf_accounts(accounts_tree)
            by_type: dict = {}
            for acc in leaves:
                t = acc.get("type", "asset")
                by_type.setdefault(t, []).append(f"  [{acc['id']}] {acc['name']}")
            TYPE_LABELS = {"asset":"ACTIVOS","liability":"PASIVOS","equity":"PATRIMONIO",
                           "income":"INGRESOS","expense":"GASTOS","cost":"COSTOS"}
            accounts_str = "\n".join(
                f"{TYPE_LABELS.get(t,t.upper())}:\n" + "\n".join(accs[:20])
                for t, accs in by_type.items()
            ) or "Sin cuentas disponibles."
    except Exception as e:
        accounts_str = "Error cargando plan de cuentas."
        print(f"[gather_accounts_context] {e}")

    # ── 3. Load RODDOS learned patterns ──────────────────────────────────────
    try:
        similar = await find_similar_pattern(db, user_message)
        patterns = await db.agent_memory.find(
            {"tipo": {"$in": ["crear_causacion", "crear_factura_venta", "registrar_factura_compra"]}},
            {"_id": 0}
        ).sort("frecuencia_count", -1).limit(8).to_list(8)

        if patterns:
            plines = []
            TIPO_LABELS = {
                "crear_causacion":          "Causación",
                "crear_factura_venta":      "Factura venta",
                "registrar_factura_compra": "Factura compra",
            }
            if similar:
                sim_pct   = round(similar.get("_similitud", 0) * 100)
                freq_sim  = similar.get("frecuencia_count", 1)
                tipo_sim  = TIPO_LABELS.get(similar["tipo"], similar["tipo"])
                cuentas_sim_str = " | ".join([
                    f"{c.get('rol','?')}: [{c.get('id','')}] {c.get('name','')}"
                    for c in similar.get("cuentas_usadas", [])[:2]
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

    # ── 4. BUILD 9: Patrón contable aprendido por NIT ────────────────────────
    try:
        nit_detected = _detectar_identificacion(user_message)
        if nit_detected:
            patron_contable = await db.learning_patterns.find_one(
                {"tipo": "patron_contable",
                 "entidad_id": str(nit_detected),
                 "activo": True,
                 "confianza": {"$gte": 0.7}},
                {"_id": 0},
            )
            if patron_contable:
                d = patron_contable.get("datos", {})
                nota = (
                    f"\n\n[BUILD 9 — PATRÓN APRENDIDO PARA NIT {nit_detected}]\n"
                    f"Cuenta débito: {d.get('cuenta_debito_id','?')} {d.get('cuenta_debito_nombre','')}\n"
                    f"Cuenta crédito: {d.get('cuenta_credito_id','?')} {d.get('cuenta_credito_nombre','')}\n"
                    f"Retención: {d.get('retencion_pct','?')}%\n"
                    f"Confianza: {round(_safe_num(patron_contable.get('confianza'))*100,0):.0f}% "
                    f"({_safe_num(patron_contable.get('muestra_n'),0):.0f} registros)\n"
                    f"→ Usar este patrón si el tipo de transacción coincide con transacciones anteriores."
                )
                patterns_str += nota
    except Exception:
        pass

    # ── 5. Autoretenedores — inyectar reglas para facturas de compra PJ ──────
    _compra_kws = ["compra", "factura compra", "factura de compra", "bill", "proveedor",
                   "auteco", "kawasaki", "comprar", "adquisicion", "adquisición", "proveedor externo"]
    _is_compra_scenario = any(kw in msg_lower for kw in _compra_kws)
    _is_pn = tipo_proveedor == "PN"  # personas naturales nunca son autoretenedoras
    if _is_compra_scenario and not _is_pn:
        try:
            _autoretenedores = await db.proveedores_config.find(
                {"es_autoretenedor": True}, {"_id": 0, "nombre": 1, "nit": 1}
            ).to_list(100)
            if _autoretenedores:
                _lista = "\n".join(
                    f"  • {a['nombre']}" + (f" (NIT: {a['nit']})" if a.get("nit") else "")
                    for a in _autoretenedores
                )
            else:
                _lista = "  (ninguno registrado aún)"
            accounts_str += (
                "\n\n══════════ REGLAS AUTORETENEDORES ══════════\n"
                f"Proveedores AUTORETENEDORES (NO aplicar ReteFuente):\n{_lista}\n\n"
                "REGLA 1 — Si el proveedor está en la lista: OMITIR ReteFuente completamente.\n"
                "REGLA 2 — Si el proveedor PJ NO está en la lista: registra CON ReteFuente estándar. "
                "Al finalizar incluye EXACTAMENTE esta nota:\n"
                '  "ℹ️ Apliqué ReteFuente [X]% a **[Proveedor]**. ¿Es autoretenedora? '
                "Responde 'Sí, [Proveedor] es autoretenedora' para revertir la retención.\"\n"
                "REGLA 3 — Persona Natural: SIEMPRE ReteFuente. NUNCA preguntar si es autoretenedora.\n"
                "════════════════════════════════════════════"
            )
        except Exception:
            pass

    return accounts_str, patterns_str, honorarios_instruccion


DOCUMENT_ANALYSIS_SYSTEM_PROMPT = """Eres el Agente Contable IA de RODDOS Colombia, experto en contabilidad NIIF Colombia.
Has recibido un comprobante contable (factura, recibo, comprobante de pago, extracto u otro documento).

CUENTAS REALES DE RODDOS EN ALEGRA (usar estos IDs en entries):
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
    accounts_str, _, _hon = await gather_accounts_context("causar registrar factura proveedor compra", alegra_service, db)

    # ── Memoria de preferencias (Parte 5): proveedor recurrente ──────────────
    _prov_memory_ctx = ""
    try:
        # Try to detect provider name from filename or message
        _fname_upper = (file_name or "").upper()
        _msg_upper = (user_message or "").upper()
        _search_text = f"{_fname_upper} {_msg_upper}"

        # Look for known providers in filename/message
        _known_provs = await db.agent_memory.find(
            {"tipo": "registrar_factura_compra"},
            {"_id": 0, "descripcion": 1, "frecuencia_count": 1, "payload_alegra": 1}
        ).sort("frecuencia_count", -1).limit(10).to_list(10)

        _matched_prov = None
        for kp in _known_provs:
            desc = (kp.get("descripcion") or "").upper()
            # Check if any word from the description appears in filename/message
            words = [w for w in desc.split() if len(w) > 4]
            if any(w in _search_text for w in words):
                _matched_prov = kp
                break

        if _matched_prov:
            freq = _matched_prov.get("frecuencia_count", 1)
            _prov_memory_ctx = (
                f"\n\n[MEMORIA: PROVEEDOR RECURRENTE DETECTADO — {freq}x registrado]\n"
                f"Descripción patrón habitual: {_matched_prov.get('descripcion', '')}\n"
                "→ Usa este patrón si coincide con el documento actual. Indica al usuario si lo estás aplicando."
            )
        elif not _matched_prov:
            # For unknown provider, inject instruction to ask if unclassifiable
            _prov_memory_ctx = (
                "\n\n[MEMORIA: Primer documento de este proveedor detectado]\n"
                "Si el documento es ilegible o no puedes determinar el tipo → "
                "pregunta al usuario: '¿Este documento es factura de compra, recibo de servicio o comprobante de pago?'"
            )
    except Exception:
        pass

    # ── Autoretenedores context para análisis de documentos ──────────────────
    _autoret_doc_ctx = ""
    try:
        _autoretenedores_doc = await db.proveedores_config.find(
            {"es_autoretenedor": True}, {"_id": 0, "nombre": 1, "nit": 1}
        ).to_list(100)
        if _autoretenedores_doc:
            _lista_doc = "\n".join(
                f"  • {a['nombre']}" + (f" (NIT: {a['nit']})" if a.get("nit") else "")
                for a in _autoretenedores_doc
            )
            _autoret_doc_ctx = (
                "\n\nREGLAS AUTORETENEDORES (CRÍTICO para calcular retenciones):\n"
                f"Proveedores que NO aplican ReteFuente:\n{_lista_doc}\n"
                "REGLA: Si el proveedor del documento está en la lista → retefuente_valor=0 y retefuente_tipo='ninguna'.\n"
                "Si el proveedor PJ no está en la lista → aplica ReteFuente normal. "
                "Al finalizar incluye: 'ℹ️ Apliqué ReteFuente X% a **[Proveedor]**. ¿Es autoretenedora?'"
            )
    except Exception:
        pass

    # Get active loanbooks for payment detection
    loanbook_str = "Sin loanbooks activos."
    try:
        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}},
            {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "saldo_pendiente": 1, "plan": 1}
        ).to_list(15)
        if loans:
            loanbook_str = "\n".join([
                f"• [{_safe_str(l.get('codigo'))}] {_safe_str(l.get('cliente_nombre'))} — Plan: {_safe_str(l.get('plan'))} Saldo: ${_safe_num(l.get('saldo_pendiente')):,.0f}"
                for l in loans
            ])
    except Exception:
        pass

    fecha_actual = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = (
        DOCUMENT_ANALYSIS_SYSTEM_PROMPT
        .replace("{accounts_context}", accounts_str + _autoret_doc_ctx + _prov_memory_ctx)
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
    accounts_str, patterns_str, honorarios_instruccion = await gather_accounts_context(user_message, alegra_service, db)
    context_str = json.dumps(context_data, ensure_ascii=False)

    # Build IVA context string
    iva_ctx = context_data.get("iva_status")
    if iva_ctx:
        iva_context_str = (
            f"Período: {_safe_str(iva_ctx.get('periodo'))} | Tipo: {_safe_str(iva_ctx.get('tipo'))} | "
            f"Mes {_safe_str(iva_ctx.get('meses_transcurridos'))} de {_safe_str(iva_ctx.get('meses_total'))}\n"
            f"Fecha límite: {_safe_str(iva_ctx.get('fecha_limite'))} ({_safe_str(iva_ctx.get('dias_restantes'))} días)\n"
            f"IVA cobrado acumulado: ${_safe_num(iva_ctx.get('iva_cobrado_acumulado')):,.0f}\n"
            f"IVA descontable acumulado: ${_safe_num(iva_ctx.get('iva_descontable_acumulado')):,.0f}\n"
            f"IVA bruto del período: ${_safe_num(iva_ctx.get('iva_bruto_periodo')):,.0f}\n"
            f"Saldo a favor DIAN: ${_safe_num(iva_ctx.get('saldo_favor_dian')):,.0f}\n"
            f"⚠️ IVA ESTIMADO A PAGAR DIAN: ${_safe_num(iva_ctx.get('iva_pagar_estimado')):,.0f}\n"
            f"Facturas: {iva_ctx.get('facturas_venta')} ventas / {iva_ctx.get('facturas_compra')} compras registradas"
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
        fuente = context_data.get("inventario_fuente", "local")
        lines = [f"  • [{_safe_str(m.get('id'))}] {_safe_str(m.get('marca'))} {_safe_str(m.get('version'))} {_safe_str(m.get('color'))} — Chasis: {_safe_str(m.get('chasis'))} Motor: {_safe_str(m.get('motor'))} Precio: ${_safe_num(m.get('total')):,.0f}" for m in motos_list[:20]]
        extra_context += f"\n\nINVENTARIO_DISPONIBLE (fuente: {fuente}, motos en stock):\n" + "\n".join(lines)
    elif context_data.get("inventario_inferido"):
        inf = context_data["inventario_inferido"]
        extra_context += (
            f"\n\nINVENTARIO (datos directos no disponibles — fuentes MongoDB e Alegra sin datos):\n"
            f"  • Loanbooks activos (motos entregadas a crédito): {inf.get('loanbooks_activos', '?')}\n"
            f"  • Registros totales en inventario local: {inf.get('total_en_inventario_db', '?')}\n"
            f"  • NOTA: {inf.get('nota', '')}\n"
            f"  → Dirige al usuario al módulo Motos para ver el detalle exacto del stock disponible."
        )
    if context_data.get("loanbook_activos"):
        lb_list = context_data["loanbook_activos"]
        lines = [
            f"  • [{_safe_str(l.get('codigo'))}] id={_safe_str(l.get('id'))} — {_safe_str(l.get('cliente'))} | Plan: {_safe_str(l.get('plan'))} | "
            f"Saldo: ${_safe_num(l.get('saldo_pendiente')):,.0f} | Estado: {_safe_str(l.get('estado'))} | "
            f"Alegra factura: {_safe_str(l.get('factura_alegra_id'), '?')} | "
            f"Entrega: {_safe_str(l.get('fecha_entrega'), 'pendiente')}"
            for l in lb_list[:10]
        ]
        extra_context += "\n\nLOANBOOK_ACTIVOS:\n" + "\n".join(lines)

    if context_data.get("actividad_hoy"):
        extra_context += (
            "\n\nACTIVIDAD DE HOY (" + context_data["fecha_actual"] + "):\n"
            + context_data["actividad_hoy"]
        )
        acct_list = context_data.get("cuentas_contables", [])
        lines = [f"  • id={a['id']} | code={a.get('code','')} | {a['name']}" for a in acct_list]
        extra_context += (
            "\n\nCUENTAS_CONTABLES_ALEGRA — USA ESTOS IDs EN crear_causacion (NO inventes IDs):\n"
            + "\n".join(lines)
        )

    # Build system prompt with all context
    # ── CFO context + Monday report ───────────────────────────────────────────
    from datetime import date as _date
    _today = _date.today()
    cfo_context_lines = []

    # Real-time cartera data
    _lbs_activos = await db.loanbook.count_documents({"estado": "activo"})
    _cfg_fin = await db.cfo_financiero_config.find_one({}, {"_id": 0}) or {}
    _gastos = _safe_num(_cfg_fin.get("gastos_fijos_semanales"))
    _deuda_np_doc = await db.cfo_deudas.aggregate([
        {"$match": {"tipo": "no_productiva", "estado": {"$ne": "pagada"}}},
        {"$group": {"_id": None, "total": {"$sum": "$saldo_pendiente"}}}
    ]).to_list(1)
    _deuda_np = _safe_num(_deuda_np_doc[0].get("total")) if _deuda_np_doc else 0
    _ci_doc = await db.loanbook.aggregate([
        {"$match": {"cuota_inicial_pendiente": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$cuota_inicial_pendiente"}}}
    ]).to_list(1)
    _ci_pendiente = _safe_num(_ci_doc[0].get("total")) if _ci_doc else 0
    _creditos_min = int(-(-_gastos // 167722)) if _gastos > 0 else 0

    cfo_context_lines.append(
        f"ESTADO CARTERA HOY ({_today.isoformat()}): "
        f"{_lbs_activos} créditos activos | Recaudo base $1,509,500/sem | "
        f"Deuda NP: ${_deuda_np:,.0f} | CI pendientes: ${_ci_pendiente:,.0f} | "
        f"Gastos fijos config: ${_gastos:,.0f}/sem | Mínimo créditos: {_creditos_min}"
    )

    # Alerta piso créditos
    if _gastos > 0 and _lbs_activos < _creditos_min:
        cfo_context_lines.append(
            f"⚠️ ALERTA CFO REGLA 3: Solo {_lbs_activos} créditos activos, mínimo recomendado: {_creditos_min}"
        )

    # Monday report — inject automatically
    if _today.weekday() == 0:  # Monday
        try:
            from routers.cfo_estrategico import get_reporte_lunes
            _reporte = await get_reporte_lunes(current_user=user)
            alertas_reporte = _reporte.get("alertas", [])
            _rec = _safe_num(_reporte.get("ingresos", {}).get("recaudo_cartera"))
            _gast = _safe_num(_reporte.get("egresos", {}).get("gastos_fijos"))
            _caja = _safe_num(_reporte.get("caja", {}).get("proyectada"))
            cfo_context_lines.append(
                f"\n📊 REPORTE CFO LUNES ({_today.isoformat()}):\n"
                f"  Recaudo esta semana: ${_rec:,.0f} ({_safe_num(_reporte.get('ingresos', {}).get('num_cuotas')):.0f} cuotas)\n"
                f"  Gastos fijos: ${_gast:,.0f}\n"
                f"  Caja proyectada fin de semana: ${_caja:,.0f} {'✅' if _caja >= 0 else '🔴'}\n"
                f"  Deuda NP: ${_safe_num(_reporte.get('deuda', {}).get('no_productiva')):,.0f}\n"
                + ("\n".join(f"  {a['msg']}" for a in alertas_reporte) if alertas_reporte else "  Sin alertas.")
            )
        except Exception:
            pass

    # ── Recordatorios CFO pendientes ─────────────────────────────────────────
    try:
        _recordatorios = await db.roddos_events.find(
            {
                "event_type": "cfo.recordatorio",
                "estado":     "pendiente",
                "fecha_recordatorio": {"$lte": _today.isoformat()},
            },
            {"_id": 0},
        ).to_list(5)
        for r in _recordatorios:
            cfo_context_lines.append(
                f"\n🔔 RECORDATORIO PENDIENTE ({r.get('fecha_recordatorio', '')}) — {r.get('titulo', '')}:\n"
                f"  {r.get('descripcion', '')}\n"
                f"  Prioridad: {r.get('prioridad', 'normal').upper()} | "
                f"  Acciones: {' | '.join(r.get('acciones_requeridas', [])[:3])}"
            )
    except Exception:
        pass

    # ── BUILD 12: Estado de Resultados en contexto CFO ────────────────────────
    try:
        from routers.estado_resultados import _build_pl
        periodo = f"{_today.year}-{_today.month:02d}"
        _pl = await _build_pl(periodo, user)
        _ing  = _safe_num(_pl["ingresos"]["total"]) if _pl.get("ingresos") else 0
        _neta = _safe_num(_pl.get("utilidad_neta"))
        _modo = _safe_str(_pl.get("modo"))
        _margen = _safe_num(_pl.get("margen_bruto_pct"))
        _gastos = _safe_num(_pl["gastos_operacionales"]["total"]) if _pl.get("gastos_operacionales") else 0
        cfo_context_lines.append(
            f"\n📊 P&L {_pl['mes_label']} (modo={_modo}):\n"
            f"  Ingresos: ${_ing:,.0f} | COGS: ${_safe_num(_pl.get('costo_ventas', {}).get('total')):,.0f} | "
            f"Utilidad bruta: ${_safe_num(_pl.get('utilidad_bruta')):,.0f} ({_margen:.1f}%)\n"
            f"  Gastos oper.: ${_gastos:,.0f} | Utilidad neta: ${_neta:,.0f}"
            + (f"\n  ⚠️ ALERTA: Margen bruto {_margen:.1f}% por debajo del 15% mínimo." if _pl.get("alerta_margen_critico") else "")
            + (f"\n  ⚠️ {_pl['costo_ventas']['advertencia']}" if _pl["costo_ventas"].get("advertencia") else "")
            + (f"\n  ⚠️ {_pl['gastos_operacionales']['advertencia']}" if _pl["gastos_operacionales"].get("advertencia") else "")
        )
    except Exception:
        pass

    cfo_ctx_str = "\n".join(cfo_context_lines)

    system_prompt = (
        AGENT_SYSTEM_PROMPT
        .replace("{context}", context_str + extra_context)
        .replace("{iva_context}", iva_context_str)
        .replace("{accounts_context}", accounts_str)
        .replace("{patterns_context}", patterns_str)
        .replace("{honorarios_instruccion}", honorarios_instruccion)
        .replace("{cfo_context}", cfo_ctx_str)
    )


    # ── MEJORA 4: Comandos especiales de contexto ─────────────────────────────
    msg_lower_cmd = user_message.lower().strip()

    # ── BUILD 12: Detectar solicitud de exportación P&L ───────────────────────
    _export_keywords = ["exporta", "exportar", "estado de resultado", "p&l", "pl de", "informe financiero", "generar informe"]
    if any(kw in msg_lower_cmd for kw in _export_keywords):
        from datetime import date as _date
        # Extract period from message (look for month name or YYYY-MM)
        _meses_map = {"enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
                     "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"}
        _periodo_export = None
        for _m, _n in _meses_map.items():
            if _m in msg_lower_cmd:
                _ano = str(_date.today().year)
                _ano_match = re.search(r'\b(20\d\d)\b', user_message)
                if _ano_match: _ano = _ano_match.group(1)
                _periodo_export = f"{_ano}-{_n}"
                break
        if not _periodo_export:
            _h = _date.today()
            _periodo_export = f"{_h.year}-{_h.month:02d}"

        _ml = _meses_map.get(next((m for m in _meses_map if m in msg_lower_cmd), ""), _periodo_export[5:7])
        _ano_label = _periodo_export[:4]
        _mes_label = next((m.capitalize() for m in _meses_map if _meses_map[m] == _periodo_export[5:7]), _periodo_export)

        export_card = {
            "type":    "pl_export_card",
            "titulo":  f"Estado de Resultados — {_mes_label} {_ano_label}",
            "periodo": _periodo_export,
            "periodo_label": f"01/{_periodo_export[5:7]}/{_ano_label} — {_periodo_export[5:7]}/{_ano_label}",
        }

        resp = f"Aquí tienes el Estado de Resultados de **{_mes_label} {_ano_label}**. Elige el formato de exportación:"
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
            "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
            "content": resp, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        return {"message": resp, "pending_action": None, "session_id": session_id, "export_card": export_card}

    # ── BUILD 13: Detectar consulta de cuotas iniciales pendientes ─────────────
    _ci_keywords = ["cuota inicial pendiente", "cuotas iniciales pendientes", "quiénes tienen cuota inicial",
                    "quienes tienen cuota inicial", "lista de cuotas iniciales", "cobrar cuota inicial",
                    "dame la lista de cuotas", "recordatorios de cuota inicial", "cuota inicial por cobrar"]
    if any(kw in msg_lower_cmd for kw in _ci_keywords):
        try:
            _lbs_ci = await db.loanbook.find(
                {"cuota_inicial_pagada": False, "cuota_inicial_total": {"$gt": 0}},
                {"_id": 0, "cliente_nombre": 1, "codigo": 1, "cuota_inicial_total": 1, "cliente_telefono": 1, "cliente_id": 1}
            ).to_list(50)

            _cuotas_pending = []
            for lb in _lbs_ci:
                _cuotas_pending.append({
                    "cliente":   lb.get("cliente_nombre", "—"),
                    "codigo":    lb.get("codigo", ""),
                    "monto":     float(lb.get("cuota_inicial_total", 0)),
                    "telefono":  lb.get("cliente_telefono", ""),
                })

            _total_ci = sum(c["monto"] for c in _cuotas_pending)

            cuotas_card = {
                "type":     "cuotas_iniciales_card",
                "clientes": _cuotas_pending,
                "total":    _total_ci,
                "count":    len(_cuotas_pending),
            }
            _fmt = lambda n: f"${n:,.0f}".replace(",",".")
            resp_ci = (
                f"Hay **{len(_cuotas_pending)} clientes** con cuota inicial pendiente "
                f"por un total de **{_fmt(_total_ci)}**.\n"
                "Usa los botones de la tarjeta para enviar recordatorios por WhatsApp."
            )
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
                "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
                "content": resp_ci, "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            return {"message": resp_ci, "pending_action": None, "session_id": session_id, "cuotas_iniciales_card": cuotas_card}
        except Exception:
            pass  # fall through to LLM

    # ── BUILD 13: Detectar confirmación autoretenedor ─────────────────────────
    _autoret_sí_patterns = [
        r'sí[,\s].*autoretenedor', r'si[,\s].*autoretenedor',
        r'sí[,\s].*es\s+autoret', r'si[,\s].*es\s+autoret',
        r'confirmo.*autoretenedor', r'es\s+autoretenedor',
    ]
    _is_autoret_confirm = False
    for _ap in _autoret_sí_patterns:
        if re.search(_ap, msg_lower_cmd, re.IGNORECASE):
            _is_autoret_confirm = True
            break
    if _is_autoret_confirm:
        try:
            # Find provider from recent assistant messages
            _recent_msgs = await db.chat_messages.find(
                {"session_id": session_id, "role": "assistant"},
                {"_id": 0, "content": 1},
            ).sort("timestamp", -1).limit(5).to_list(5)
            _prov_autoret = None
            for _rm in _recent_msgs:
                _content = _rm.get("content", "")
                _m = re.search(
                    r'Apliqué ReteFuente.*?a \*?\*?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s.]+?)\*?\*?[.?]',
                    _content
                )
                if _m:
                    _prov_autoret = _m.group(1).strip()
                    break
            # Also extract from current message: "Sí, [Proveedor] es autoretenedora"
            _m2 = re.search(
                r'(?:sí|si)[,\s]+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s.]{3,50?})\s+es\s+autoretenedor',
                user_message, re.IGNORECASE
            )
            if _m2:
                _prov_autoret = _m2.group(1).strip()
            if _prov_autoret:
                await db.proveedores_config.update_one(
                    {"nombre": {"$regex": f"^{re.escape(_prov_autoret)}$", "$options": "i"}},
                    {"$set": {
                        "nombre": _prov_autoret,
                        "es_autoretenedor": True,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "updated_by": user.get("email"),
                    }},
                    upsert=True,
                )
                # Inject reversal instruction into system_prompt
                system_prompt += (
                    f"\n\nINSTRUCCIÓN URGENTE — REVERSIÓN AUTORETENEDOR:\n"
                    f"El usuario confirmó que **{_prov_autoret}** ES AUTORETENEDORA.\n"
                    "Debes:\n"
                    "1. Crear asiento de reversión (crear_causacion) para REVERTIR la ReteFuente aplicada:\n"
                    "   Débito: cuenta ReteFuente por pagar (23654001 Compras 2.5% o la que corresponda)\n"
                    f"   Crédito: cuenta por pagar a {_prov_autoret} (5070)\n"
                    "   Concepto: 'Reversión ReteFuente — proveedor autoretenedor'\n"
                    f"2. Confirmar: '{_prov_autoret} quedó registrada como AUTORETENEDORA. "
                    "ReteFuente revertida correctamente.'"
                )
        except Exception:
            pass

    # ── Modo diagnóstico automático (errores repetidos en sesión) ────────────
    try:
        _session_errors = await db.agent_errors.count_documents(
            {"stack_trace": {"$regex": session_id}, "fase": "process_chat"}
        )
        if _session_errors == 0:
            # Also check by recent timestamp (last 30 min, same user)
            from datetime import timedelta
            _cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            _session_errors = await db.agent_errors.count_documents({
                "timestamp": {"$gte": _cutoff},
                "user_message": {"$exists": True}
            })
        if _session_errors >= 2:
            system_prompt += (
                "\n\nINSTRUCCIÓN DIAGNÓSTICO (activada por errores repetidos en sesión):\n"
                "El usuario ha tenido 2+ errores en esta sesión. "
                "Incluye al inicio de tu próxima respuesta un diagnóstico breve:\n"
                "Estado del sistema:\n"
                f"• Inventario: {'disponible (' + str(len(context_data.get('inventario_disponible', []))) + ' motos)' if context_data.get('inventario_disponible') else 'no disponible desde contexto — usa módulo Motos'}\n"
                f"• Loanbooks: {context_data.get('loanbooks_total', '?')} activos\n"
                "• Luego propón 3 acciones alternativas concretas que puedas ejecutar ahora mismo."
            )
    except Exception:
        pass

    is_context_cmd = any(kw in msg_lower_cmd for kw in [
        "en qué íbamos", "en que ibamos", "qué falta", "que falta",
        "resumen", "qué hice", "que hice", "qué pasó hoy", "que paso hoy",
        "qué se hizo", "que se hizo",
    ])
    is_pausa = any(kw in msg_lower_cmd for kw in ["pausa la tarea", "pausar la tarea", "pausar tarea"])
    is_continua = any(kw in msg_lower_cmd for kw in ["continúa la tarea", "continua la tarea", "retomar tarea", "retoma la tarea"])

    # ── MEJORA 2: Cargar tarea activa ─────────────────────────────────────────
    tarea_activa = await db.agent_memory.find_one(
        {"tipo": "tarea_activa", "estado": "en_curso"},
        {"_id": 0},
    )

    if is_pausa and tarea_activa:
        await db.agent_memory.update_one(
            {"tipo": "tarea_activa", "estado": "en_curso"},
            {"$set": {"estado": "pausada", "ultimo_avance": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "message": f"⏸️ Tarea pausada: **{tarea_activa['descripcion']}** (paso {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)}).\nPuedes continuar cuando quieras diciendo **\"Continúa la tarea\"**.",
            "pending_action": None,
            "session_id": session_id,
        }

    if is_continua:
        tarea_pausada = await db.agent_memory.find_one(
            {"tipo": "tarea_activa", "estado": "pausada"},
            {"_id": 0},
        )
        if tarea_pausada:
            await db.agent_memory.update_one(
                {"tipo": "tarea_activa", "estado": "pausada"},
                {"$set": {"estado": "en_curso", "ultimo_avance": datetime.now(timezone.utc).isoformat()}},
            )
            tarea_activa = {**tarea_pausada, "estado": "en_curso"}
            pendientes = tarea_activa.get("pasos_pendientes", [])
            proximo = pendientes[0] if pendientes else "No hay pasos pendientes"
            return {
                "message": (
                    f"▶️ Retomando tarea: **{tarea_activa['descripcion']}**\n"
                    f"Progreso: {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)} pasos\n"
                    f"Siguiente paso: {proximo}"
                ),
                "pending_action": None,
                "session_id": session_id,
            }

    if is_context_cmd:
        from datetime import timezone as _tz
        lines = [f"## Resumen de contexto operativo ({datetime.now(_tz.utc).strftime('%Y-%m-%d')})"]

        if tarea_activa:
            pendientes = tarea_activa.get("pasos_pendientes", [])
            lines.append(
                f"\n**TAREA EN CURSO:** {tarea_activa['descripcion']}\n"
                f"Progreso: {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)} pasos\n"
                + ("Pendiente:\n" + "\n".join(f"  • {p}" for p in pendientes[:5]) if pendientes else "")
            )
        else:
            lines.append("\n*Sin tarea activa en curso.*")

        actividad = context_data.get("actividad_hoy", "")
        if actividad:
            lines.append(f"\n**Actividad de hoy:**\n{actividad}")
        else:
            lines.append("\n*Sin actividad registrada hoy.*")

        alertas = await db.cfo_alertas.find(
            {}, {"_id": 0, "mensaje": 1, "tipo": 1}
        ).sort("created_at", -1).limit(3).to_list(3)
        if alertas:
            lines.append("\n**Alertas pendientes CFO:**")
            for a in alertas:
                lines.append(f"  • {a.get('tipo','')}: {a.get('mensaje','')}")

        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
            "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        resp = "\n".join(lines)
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
            "content": resp, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        return {"message": resp, "pending_action": None, "session_id": session_id}

    # ── MEJORA 1: Cargar historial de la sesión y resumir si es largo ─────────
    CHARS_PER_TOKEN = 4
    MAX_HISTORY_TOKENS = 6000
    KEEP_RECENT_PAIRS = 6

    raw_history = await db.chat_messages.find(
        {"session_id": session_id},
        {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
    ).sort("timestamp", 1).to_list(200)

    # Convert to LiteLLM message dicts (omit system messages already in initial_messages)
    history_msgs = [
        {"role": m["role"], "content": str(m.get("content", ""))}
        for m in raw_history
        if m["role"] in ("user", "assistant")
    ]

    total_chars = sum(len(m["content"]) for m in history_msgs)
    total_tokens_est = total_chars // CHARS_PER_TOKEN

    summary_msg = None
    if total_tokens_est > MAX_HISTORY_TOKENS and len(history_msgs) > KEEP_RECENT_PAIRS * 2:
        # Split: old messages to summarize + recent messages to keep
        split_idx = len(history_msgs) - KEEP_RECENT_PAIRS * 2
        old_msgs  = history_msgs[:split_idx]
        recent_msgs = history_msgs[split_idx:]

        # Summarize the old portion
        try:
            summary_chat = LlmChat(
                api_key=api_key,
                session_id=f"{session_id}-summary",
                system_message=(
                    "Eres un asistente que resume conversaciones de contabilidad. "
                    "Extrae: tareas completadas, datos mencionados (clientes, montos, facturas, NITs), pendientes. "
                    "Máximo 200 palabras en español."
                ),
                initial_messages=(
                    [{"role": "system", "content": "Resume la siguiente conversación en máximo 200 palabras."}]
                    + old_msgs[:60]
                ),
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            summary_text = await summary_chat.send_message(
                UserMessage(text="Resume los puntos clave de esta conversación.")
            )
            summary_msg = {
                "role": "system",
                "content": f"RESUMEN DE CONVERSACIÓN ANTERIOR:\n{summary_text}",
            }
            history_msgs = recent_msgs
        except Exception:
            history_msgs = history_msgs[-(KEEP_RECENT_PAIRS * 2):]

    # Build initial_messages for this request
    initial_messages: list = [{"role": "system", "content": system_prompt}]
    if summary_msg:
        initial_messages.append(summary_msg)

    # ── MEJORA 2: Inyectar tarea activa en el contexto ────────────────────────
    if tarea_activa:
        pendientes = tarea_activa.get("pasos_pendientes", [])
        tarea_ctx = (
            f"TAREA EN CURSO: {tarea_activa['descripcion']}\n"
            f"Progreso: {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)} pasos completados.\n"
            + (f"Pasos pendientes: {', '.join(pendientes[:5])}\n" if pendientes else "")
            + "Continúa exactamente desde donde quedaste sin repetir pasos ya completados."
        )
        initial_messages.append({"role": "system", "content": tarea_ctx})

    initial_messages.extend(history_msgs)

    # Save user message to MongoDB
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # Call Claude with full history context
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_prompt,
        initial_messages=initial_messages,
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
        "crear_nota_credito": ("credit-notes", "POST"),
        "crear_nota_debito": ("debit-notes", "POST"),
    }

    # ── Special case: crear_comprobante_ingreso / crear_comprobante_egreso ────
    if action_type in ("crear_comprobante_ingreso", "crear_comprobante_egreso"):
        # Map to journals endpoint (Alegra uses journal-entries for comprobantes)
        comprobante_result = await service.request("journals", "POST", payload)
        from post_action_sync import post_action_sync
        sync_result = await post_action_sync(action_type, comprobante_result, payload, db, user)
        return {
            "success": True,
            "result": comprobante_result,
            "id": str(comprobante_result.get("id", "")),
            "message": f"Comprobante {'de ingreso' if 'ingreso' in action_type else 'de egreso'} registrado",
            "sync": sync_result,
        }

    # ── Special case: anular_factura_compra ───────────────────────────────────
    if action_type == "anular_factura_compra":
        bill_id     = payload.get("bill_id", "")
        bill_numero = payload.get("bill_numero", "") or internal_metadata.get("bill_numero", "")
        proveedor   = payload.get("proveedor_nombre", "") or internal_metadata.get("proveedor_nombre", "")

        if not bill_id:
            raise ValueError("Falta bill_id para anular la factura de compra.")

        # Guard: check motos linked to this bill
        motos_bloqueadas = await db.inventario_motos.find(
            {"factura_compra_alegra_id": bill_id,
             "estado": {"$in": ["Vendida", "Entregada"]}},
            {"_id": 0, "chasis": 1, "marca": 1, "version": 1, "estado": 1},
        ).to_list(10)

        if motos_bloqueadas:
            detalle = ", ".join(
                f"chasis {m.get('chasis') or m.get('marca','')+' '+m.get('version','')} ({m.get('estado')})"
                for m in motos_bloqueadas
            )
            raise ValueError(
                f"❌ No se puede anular la factura {bill_numero}. "
                f"La(s) siguiente(s) moto(s) vinculadas ya fueron vendidas/entregadas: {detalle}. "
                "Resuelve primero esas ventas antes de anular la compra."
            )

        # Execute: DELETE /bills/{id} in Alegra
        alegra_result = await service.request(f"bills/{bill_id}", "DELETE")

        # Post-action sync
        from post_action_sync import post_action_sync
        sync_result = await post_action_sync(
            "anular_factura_compra",
            {"id": bill_id, "numero": bill_numero, "proveedor": proveedor},
            payload,
            db,
            user,
            metadata=internal_metadata,
        )
        return {
            "success": True,
            "result": alegra_result,
            "id": bill_id,
            "message": f"Factura {bill_numero} anulada en Alegra",
            "sync": sync_result,
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

    # ── CREAR_CAUSACION: validate entry IDs and translate if needed ──────────
    if action_type == "crear_causacion":
        entries = payload.get("entries", [])
        normalized = [
            {
                "id":     e["id"],
                "debit":  e.get("debit", 0),
                "credit": e.get("credit", 0),
                "_name":  e.get("name", ""),
            }
            for e in entries
        ]

        # Translate invalid IDs → real Alegra IDs using roddos_cuentas (fast)
        if not await service.is_demo_mode():
            try:
                roddos = await db.roddos_cuentas.find(
                    {}, {"_id": 0, "alegra_id": 1, "nombre": 1, "palabras_clave": 1}
                ).to_list(200)
                valid_ids = {str(r["alegra_id"]) for r in roddos}
                name_to_id = {r["nombre"].lower(): str(r["alegra_id"]) for r in roddos}
                # Also index palabras_clave for fuzzy match
                kw_to_id: dict[str, str] = {}
                for r in roddos:
                    for kw in r.get("palabras_clave", []):
                        kw_to_id[kw.lower()] = str(r["alegra_id"])

                for entry in normalized:
                    if str(entry["id"]) not in valid_ids:
                        entry_name = (entry.get("_name") or "").lower().strip()
                        matched = False
                        if entry_name:
                            # 1. Exact name match
                            if entry_name in name_to_id:
                                entry["id"] = int(name_to_id[entry_name])
                                matched = True
                            # 2. Keywords match
                            if not matched:
                                for kw, kid in kw_to_id.items():
                                    if kw in entry_name:
                                        entry["id"] = int(kid)
                                        matched = True
                                        break
                            # 3. Partial name match
                            if not matched:
                                words = [w for w in entry_name.split() if len(w) > 3]
                                for rname, rid in name_to_id.items():
                                    if all(w in rname for w in words[:2]):
                                        entry["id"] = int(rid)
                                        break

                        if not matched and str(entry["id"]) not in valid_ids:
                            # Final fallback: Alegra /categories
                            try:
                                cats = await service.request("categories")
                                cat_ids: set = set()
                                cat_name_map: dict = {}
                                def _scan(items: list) -> None:
                                    for item in items:
                                        cat_ids.add(str(item["id"]))
                                        cat_name_map[(item.get("name") or "").lower()] = str(item["id"])
                                        for child in item.get("children", []):
                                            _scan([child])
                                _scan(cats if isinstance(cats, list) else [])
                                if entry_name in cat_name_map:
                                    entry["id"] = int(cat_name_map[entry_name])
                            except Exception:
                                pass
            except Exception as lookup_err:
                        print(f"[causacion] ID translation: {lookup_err}")

        # Final normalization: strip helper _name
        payload["entries"] = [
            {"id": e["id"], "debit": e["debit"], "credit": e["credit"]}
            for e in normalized
        ]

    endpoint, method = ACTION_MAP[action_type]

    # ── Guard: prevent double-selling same moto ───────────────────────────────
    if action_type == "crear_factura_venta":
        moto_id   = internal_metadata.get("moto_id", "")
        moto_chas = internal_metadata.get("moto_chasis", "")
        moto_desc = internal_metadata.get("moto_descripcion", "")

        if moto_id or moto_chas:
            query = {"id": moto_id} if moto_id else {"chasis": moto_chas}
            moto = await db.inventario_motos.find_one(
                query,
                {"_id": 0, "estado": 1, "chasis": 1, "marca": 1, "version": 1,
                 "factura_numero": 1, "fecha_venta": 1, "cliente_nombre": 1},
            )
            if not moto:
                raise ValueError(
                    f"❌ No encontré la moto con {'chasis' if moto_chas else 'ID'} "
                    f"'{moto_chas or moto_id}' en el inventario. "
                    "Verifica el chasis o registra la entrada de esa unidad primero."
                )
            estado = moto.get("estado", "")
            if estado not in ("Disponible", None, ""):
                detalle = ""
                if estado == "Vendida":
                    fv = moto.get("factura_numero", "")
                    fecha = moto.get("fecha_venta", "")
                    cli   = moto.get("cliente_nombre", "")
                    detalle = (
                        f" Vinculada a factura {fv} del {fecha}"
                        f"{(' — ' + cli) if cli else ''}."
                    )
                raise ValueError(
                    f"❌ La moto {moto_chas or moto_id} tiene estado '{estado}'. "
                    f"No se puede facturar.{detalle}"
                )

        elif moto_desc:
            # Generic sale by model — verify stock exists
            partes = (moto_desc or "").split()
            marca_q = partes[0] if partes else ""
            disponibles = await db.inventario_motos.count_documents(
                {"estado": "Disponible", **({"marca": {"$regex": marca_q, "$options": "i"}} if marca_q else {})}
            )
            if disponibles == 0:
                raise ValueError(
                    f"❌ No hay unidades disponibles de {moto_desc}. "
                    "Registra una compra primero para agregar unidades al inventario."
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
