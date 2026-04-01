"""
tool_executor.py — Despachador de herramientas para el Agente Contador de SISMO.

Provee:
  execute_tool()          — Ejecuta un tool; si requires_confirmation=True, persiste
                            en MongoDB agent_sessions y retorna propuesta. Si False,
                            ejecuta inmediatamente (lectura).
  confirm_pending_action() — Ejecuta o cancela la acción pendiente almacenada en
                             agent_sessions para una sesión dada.

Reglas:
  - NUNCA llamar directamente a api.alegra.com — siempre via AlegraService
  - SIEMPRE usar /journals (NUNCA /journal-entries)
  - pending_action persiste en MongoDB para sobrevivir Render cold starts
"""

import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    db,
    user: dict,
    session_id: str = None,
) -> dict:
    """
    Ejecuta un tool.

    - Si requires_confirmation=True: persiste pending_action en agent_sessions
      (MongoDB) y retorna propuesta estructurada para el usuario.
    - Si requires_confirmation=False: ejecuta inmediatamente y retorna resultado.

    Args:
        tool_name:  Nombre del tool (debe existir en TOOL_DEFS)
        tool_input: Dict de parámetros del tool (ya validados por Anthropic)
        db:         Motor AsyncIOMotorDatabase — acceso a colecciones
        user:       Dict del usuario autenticado
        session_id: session_id para persistir pending_action (si aplica)

    Returns:
        dict con el resultado o la propuesta pendiente
    """
    from tool_definitions import TOOL_DEFS

    tool_def = TOOL_DEFS.get(tool_name)
    if not tool_def:
        raise ValueError(f"Tool desconocido: {tool_name}")

    # ── Tools que requieren confirmación del usuario ──────────────────────────
    if tool_def["requires_confirmation"]:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=72)

        # Formato de pending_action en MongoDB: usa "type" para coincidir con
        # el contrato que el frontend y los tests esperan
        pending = {
            "type": tool_name,
            "payload": tool_input,
            "tool_name": tool_name,    # alias para compatibilidad interna
            "tool_input": tool_input,  # alias para compatibilidad interna
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Persistir en MongoDB — belt-and-suspenders para Render cold starts
        if session_id:
            await db.agent_sessions.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "pending_action": pending,
                        "updated_at": now.isoformat(),
                    }
                },
                upsert=True,
            )

        return {
            "requires_confirmation": True,
            "pending_action": {"type": tool_name, "payload": tool_input},
            "message": (
                f"Propuesta de acción: {tool_def['description']}. "
                f"¿Confirmar? (monto: {tool_input.get('monto', '')})"
                if tool_input.get("monto")
                else f"Propuesta: {tool_def['description']}. ¿Confirmar?"
            ),
        }

    # ── Tools de lectura — auto-ejecutar sin confirmación ────────────────────
    if tool_name == "consultar_facturas":
        from alegra_service import AlegraService
        service = AlegraService(db)
        params = {}
        if tool_input.get("fecha_inicio"):
            params["date_start"] = tool_input["fecha_inicio"]
        if tool_input.get("fecha_fin"):
            params["date_end"] = tool_input["fecha_fin"]
        result = await service.request(
            "invoices", "GET", params if params else None
        )
        facturas = result if isinstance(result, list) else [result]
        return {"facturas": facturas}

    if tool_name == "consultar_cartera":
        query = {}
        if tool_input.get("filtro_estado"):
            query["estado"] = tool_input["filtro_estado"]
        cursor = db.loanbook.find(query, {"_id": 0}).limit(50)
        loanbooks = await cursor.to_list(length=50)
        return {"cartera": loanbooks, "total": len(loanbooks)}

    raise ValueError(f"execute_tool no implementado para: {tool_name}")


async def confirm_pending_action(
    session_id: str,
    confirmed: bool,
    db,
    user: dict,
) -> dict:
    """
    Ejecuta o cancela la acción pendiente almacenada en agent_sessions.

    Args:
        session_id: ID de la sesión que tiene la pending_action
        confirmed:  True = ejecutar la acción; False = cancelarla
        db:         Motor AsyncIOMotorDatabase
        user:       Dict del usuario autenticado

    Returns:
        dict con resultado de ejecución o confirmación de cancelación
    """
    session = await db.agent_sessions.find_one({"session_id": session_id})
    if not session or not session.get("pending_action"):
        raise ValueError("No hay acción pendiente para esta sesión")

    pending = session["pending_action"]
    tool_name = pending.get("tool_name") or pending.get("type")
    tool_input = pending.get("tool_input") or pending.get("payload", {})

    # Limpiar pending_action de la sesión (sea confirmada o cancelada)
    await db.agent_sessions.update_one(
        {"session_id": session_id},
        {"$unset": {"pending_action": ""}},
    )

    if not confirmed:
        return {"cancelled": True, "message": "Acción cancelada por el usuario"}

    # Ejecutar la acción confirmada via execute_chat_action (reutiliza ACTION_MAP)
    from ai_chat import execute_chat_action
    result = await execute_chat_action(tool_name, tool_input, db, user)
    return result
