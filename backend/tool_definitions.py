"""
tool_definitions.py — Definiciones de herramientas para el Agente Contador de SISMO.

Contiene TOOL_DEFS: dict con los 6 tools MVP de Phase 9, incluyendo:
  - input_schema (JSON Schema, lo que se envía a Anthropic)
  - requires_confirmation (metadata interna: true=escritura, false=lectura)
  - description (en español)
  - endpoint: el action interno que ejecuta el tool
  - method: HTTP method

Uso:
  from tool_definitions import TOOL_DEFS, get_tool_schemas_for_api

get_tool_schemas_for_api() devuelve la lista en formato Anthropic API
(sin campos internos requires_confirmation/endpoint/method).
"""

# ── 6 herramientas MVP — Phase 9 ─────────────────────────────────────────────

TOOL_DEFS: dict = {

    "crear_causacion": {
        "description": (
            "Crea un asiento contable (causación) en Alegra para registrar un gasto. "
            "Úsalo cuando el usuario quiera registrar un pago o gasto con cargo a una cuenta del plan de cuentas. "
            "Requiere monto, descripción, cuenta contable, fecha y banco de origen."
        ),
        "input_schema": {
            "type": "object",
            "required": ["monto", "descripcion", "cuenta_id", "fecha", "banco_id"],
            "properties": {
                "monto": {
                    "type": "number",
                    "description": "Monto bruto de la transacción en COP (ej: 150000.0)"
                },
                "descripcion": {
                    "type": "string",
                    "description": "Descripción del gasto (ej: 'Arrendamiento bodega enero 2026')"
                },
                "cuenta_id": {
                    "type": "integer",
                    "description": "ID de la cuenta Alegra del gasto según plan_cuentas_roddos (ej: 5493)"
                },
                "fecha": {
                    "type": "string",
                    "description": "Fecha de la transacción en formato yyyy-MM-dd estricto (ej: '2026-01-15')"
                },
                "banco_id": {
                    "type": "string",
                    "description": "ID de la cuenta bancaria de origen en Alegra (ej: 'bbva_cte')"
                },
            },
        },
        "requires_confirmation": True,
        "endpoint": "crear_causacion",
        "method": "POST",
    },

    "registrar_pago_cartera": {
        "description": (
            "Registra un pago recibido de un cliente en la cartera activa de RODDOS. "
            "Actualiza el loanbook en MongoDB y el estado del cliente. "
            "Requiere identificar el loanbook, el monto del pago, el banco receptor y el número de cuota."
        ),
        "input_schema": {
            "type": "object",
            "required": ["loanbook_id", "monto", "banco", "numero_cuota"],
            "properties": {
                "loanbook_id": {
                    "type": "string",
                    "description": "ID del loanbook en SISMO (ej: 'LB-0042')"
                },
                "monto": {
                    "type": "number",
                    "description": "Monto del pago recibido en COP (ej: 149900.0)"
                },
                "banco": {
                    "type": "string",
                    "description": "Nombre del banco origen del pago (ej: 'Nequi', 'Bancolombia', 'BBVA')"
                },
                "numero_cuota": {
                    "type": "integer",
                    "description": "Número de cuota que corresponde al pago (ej: 3)"
                },
            },
        },
        "requires_confirmation": True,
        "endpoint": "registrar_pago_cartera",
        "method": "POST",
    },

    "registrar_nomina": {
        "description": (
            "Registra la nómina mensual de RODDOS en Alegra. "
            "Crea los asientos contables de salarios y prestaciones sociales. "
            "Requiere el período (mes y año) y la lista de empleados con sus montos."
        ),
        "input_schema": {
            "type": "object",
            "required": ["mes", "anio", "empleados"],
            "properties": {
                "mes": {
                    "type": "integer",
                    "description": "Mes de la nómina (1-12, ej: 1 para enero)"
                },
                "anio": {
                    "type": "integer",
                    "description": "Año de la nómina (ej: 2026)"
                },
                "empleados": {
                    "type": "array",
                    "description": "Lista de empleados con sus salarios brutos",
                    "items": {
                        "type": "object",
                        "required": ["nombre", "monto"],
                        "properties": {
                            "nombre": {
                                "type": "string",
                                "description": "Nombre completo del empleado"
                            },
                            "monto": {
                                "type": "number",
                                "description": "Salario bruto mensual en COP"
                            },
                        },
                    },
                },
            },
        },
        "requires_confirmation": True,
        "endpoint": "registrar_nomina",
        "method": "POST",
    },

    "consultar_facturas": {
        "description": (
            "Consulta las facturas de venta registradas en Alegra para un período dado. "
            "Es una operación de solo lectura — no requiere confirmación del usuario. "
            "Devuelve lista de facturas con cliente, monto, estado y fecha."
        ),
        "input_schema": {
            "type": "object",
            "required": [],
            "properties": {
                "fecha_inicio": {
                    "type": "string",
                    "description": "Fecha de inicio del rango en formato yyyy-MM-dd (ej: '2026-01-01')"
                },
                "fecha_fin": {
                    "type": "string",
                    "description": "Fecha de fin del rango en formato yyyy-MM-dd (ej: '2026-01-31')"
                },
            },
        },
        "requires_confirmation": False,
        "endpoint": "consultar_facturas",
        "method": "GET",
    },

    "consultar_cartera": {
        "description": (
            "Consulta el estado actual de la cartera de loanbooks de RODDOS desde MongoDB. "
            "Es una operación de solo lectura — no requiere confirmación del usuario. "
            "Devuelve resumen de cartera con totales, estado por bucket y loanbooks activos."
        ),
        "input_schema": {
            "type": "object",
            "required": [],
            "properties": {
                "filtro_estado": {
                    "type": "string",
                    "enum": ["activo", "al_dia", "mora", "cancelado"],
                    "description": "Filtro opcional por estado del loanbook"
                },
            },
        },
        "requires_confirmation": False,
        "endpoint": "consultar_cartera",
        "method": "GET",
    },

    "crear_factura_venta": {
        "description": (
            "Crea una factura de venta de motocicleta en Alegra. "
            "VIN y número de motor son OBLIGATORIOS por ERROR-014 — toda venta de moto debe tener estos datos. "
            "Requiere datos del cliente, VIN, motor, modelo y plan de financiamiento."
        ),
        "input_schema": {
            "type": "object",
            "required": [
                "cliente_nombre", "cliente_cedula", "vin", "motor", "modelo", "plan"
            ],
            "properties": {
                "cliente_nombre": {
                    "type": "string",
                    "description": "Nombre completo del cliente (ej: 'Juan Carlos Pérez')"
                },
                "cliente_cedula": {
                    "type": "string",
                    "description": "Cédula o documento de identidad del cliente (ej: '1234567890')"
                },
                "vin": {
                    "type": "string",
                    "description": "Número VIN / chasis de la motocicleta — OBLIGATORIO (ERROR-014)"
                },
                "motor": {
                    "type": "string",
                    "description": "Número de motor de la motocicleta — OBLIGATORIO (ERROR-014)"
                },
                "modelo": {
                    "type": "string",
                    "description": "Modelo de la motocicleta (ej: 'TVS HLX 150')"
                },
                "plan": {
                    "type": "string",
                    "description": "Nombre del plan de financiamiento desde catalogo_planes (ej: 'P78S')"
                },
            },
        },
        "requires_confirmation": True,
        "endpoint": "crear_factura_venta",
        "method": "POST",
    },

}

# ── Nombres esperados (6 tools MVP) ──────────────────────────────────────────
_EXPECTED_TOOLS = {
    "crear_causacion",
    "registrar_pago_cartera",
    "registrar_nomina",
    "consultar_facturas",
    "consultar_cartera",
    "crear_factura_venta",
}

assert set(TOOL_DEFS.keys()) == _EXPECTED_TOOLS, (
    f"TOOL_DEFS keys mismatch. Expected: {_EXPECTED_TOOLS}, got: {set(TOOL_DEFS.keys())}"
)


def get_tool_schemas_for_api() -> list:
    """
    Retorna la lista de tool schemas en formato Anthropic API.

    Excluye campos internos (requires_confirmation, endpoint, method) que no
    deben enviarse a la API de Anthropic.

    Returns:
        list[dict]: Lista de dicts con {name, description, input_schema}
    """
    return [
        {
            "name": name,
            "description": defn["description"],
            "input_schema": defn["input_schema"],
        }
        for name, defn in TOOL_DEFS.items()
    ]
