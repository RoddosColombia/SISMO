"""Agent write permissions — enforces collection and Alegra endpoint access control."""

# ── constants ──
# Maps each agent to the MongoDB collections it may write to and the Alegra API
# endpoints it may call.  Collection-level granularity (per D-07).
#
# Design notes:
# - D-08: This module is the single source of truth for agent write permissions.
# - D-09: Validation functions raise PermissionError only; no audit logging here.
# - D-10: validate_alegra_permission() normalises the endpoint to its base segment
#         so callers can pass "invoices/123" and it resolves to "invoices".

WRITE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "contador": {
        "collections": [
            "roddos_events",
            "audit_logs",
            "cartera_pagos",
            "inventario_motos",
            "loanbook",
            "catalogo_planes",
            "plan_cuentas_roddos",
        ],
        "alegra_endpoints": [
            "journals",
            "invoices",
            "payments",
            "contacts",
            "items",
            "bank-accounts",
            "categories",
        ],
    },
    "cfo": {
        "collections": [
            "roddos_events",
            "audit_logs",
            "portfolio_summaries",
            "financial_reports",
            "sismo_knowledge",
        ],
        "alegra_endpoints": [],  # CFO es read-only absoluto fuera de sus colecciones MongoDB
    },
    "radar": {
        "collections": [
            "roddos_events",
            "audit_logs",
            "loanbook",
            "cartera_pagos",
        ],
        "alegra_endpoints": [],  # RADAR tiene acceso de solo lectura — sin escritura en Alegra
    },
    "loanbook": {
        "collections": [
            "roddos_events",
            "audit_logs",
            "loanbook",
            "inventario_motos",
            "cartera_pagos",
        ],
        "alegra_endpoints": [
            "invoices",
            "payments",
        ],
    },
}


# ── delete protection ──
# Endpoints donde DELETE está prohibido sin excepción — son registros legales.
PROTECTED_DELETE_ENDPOINTS: list[str] = [
    "invoices",  # facturas de venta RODDOS — registro legal, NUNCA eliminar
    "bills",     # compras Auteco — NUNCA eliminar sin aprobación explícita
]


def validate_delete_protection(method: str, endpoint: str) -> None:
    """Raise PermissionError si method es DELETE sobre un endpoint protegido.

    Args:
        method:   HTTP method (e.g., "DELETE", "GET", "POST")
        endpoint: Alegra API endpoint path (e.g., "invoices", "invoices/123")

    Raises:
        PermissionError: Si method es DELETE y el base endpoint está en
            PROTECTED_DELETE_ENDPOINTS.
    """
    if method.upper() != "DELETE":
        return
    base_endpoint = endpoint.split("/")[0].split("?")[0]
    if base_endpoint in PROTECTED_DELETE_ENDPOINTS:
        raise PermissionError(
            f"DELETE en '{base_endpoint}' está prohibido — las facturas y compras "
            f"son registros legales y no pueden eliminarse."
        )


# ── validation functions ──

def validate_write_permission(agent: str, collection: str) -> None:
    """Raise PermissionError if agent is not allowed to write to collection.

    Args:
        agent: Agent identifier (e.g., "contador", "cfo", "radar", "loanbook")
        collection: MongoDB collection name (e.g., "loanbook", "cartera_pagos")

    Raises:
        PermissionError: If agent is not in WRITE_PERMISSIONS or collection is
            not in the agent's allowed list.
    """
    perms = WRITE_PERMISSIONS.get(agent)
    if perms is None:
        raise PermissionError(
            f"Agente '{agent}' no esta registrado en WRITE_PERMISSIONS"
        )
    if collection not in perms["collections"]:
        raise PermissionError(
            f"Agente '{agent}' no tiene permiso de escritura en coleccion '{collection}'"
        )


def validate_alegra_permission(agent: str, endpoint: str, method: str = None) -> None:
    """Raise PermissionError if agent is not allowed to call Alegra endpoint.

    Strips nested paths and query parameters before checking so that callers
    can pass full paths (e.g., "invoices/123?draft=true") and the check still
    resolves against the base endpoint ("invoices").

    Args:
        agent: Agent identifier (e.g., "contador", "cfo", "radar", "loanbook")
        endpoint: Alegra API endpoint path (e.g., "invoices", "journals",
            "invoices/123")

    Raises:
        PermissionError: If agent has no Alegra access or the base endpoint is
            not in the agent's allowed list.
    """
    perms = WRITE_PERMISSIONS.get(agent)
    if perms is None:
        raise PermissionError(
            f"Agente '{agent}' no esta registrado en WRITE_PERMISSIONS"
        )
    # Normalise: strip nested path segments and query-string parameters.
    # "invoices/123?draft=true"  ->  "invoices"
    base_endpoint = endpoint.split("/")[0].split("?")[0]
    if base_endpoint not in perms["alegra_endpoints"]:
        raise PermissionError(
            f"Agente '{agent}' no tiene permiso para endpoint Alegra '{base_endpoint}'"
        )
    if method is not None:
        validate_delete_protection(method, endpoint)
