"""
tool_executor.py — Despachador de herramientas para el Agente Contador de SISMO.

Provee:
  execute_tool()               — Ejecuta un tool; si requires_confirmation=True, persiste
                                  en MongoDB agent_sessions y retorna propuesta. Si False,
                                  ejecuta inmediatamente (lectura).
  confirm_pending_action()     — Ejecuta o cancela la acción pendiente almacenada en
                                  agent_sessions para una sesión dada.
  create_plan()                — Crea un plan multi-acción en agent_plans con status
                                  pending_approval. NO ejecuta nada.
  execute_plan()               — Carga un plan y ejecuta sus acciones en orden.
  cancel_plan()                — Cancela un plan (status cancelled).
  execute_chat_action_for_plan() — Wrapper de execute_chat_action para execute_plan().

Reglas:
  - NUNCA llamar directamente a api.alegra.com — siempre via AlegraService
  - SIEMPRE usar /journals (NUNCA /journal-entries)
  - pending_action persiste en MongoDB para sobrevivir Render cold starts
  - execute_plan() llama execute_chat_action() — NUNCA llama Alegra directo
"""

import json
import logging
import uuid as _uuid
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


# =============================================================================
# ReAct Nivel 1 — Plan Multi-Acción (Phase 10A)
# =============================================================================

async def create_plan(
    request: str,
    tool_calls: list,
    session_id: str,
    db,
    user: dict,
) -> dict:
    """
    Crea un plan multi-acción en agent_plans con status pending_approval.
    NO ejecuta nada — solo persiste el plan y retorna descripción natural.

    Args:
        request:    El mensaje original del usuario
        tool_calls: Lista de dicts {tool_name, tool_input, description?}
        session_id: ID de la sesión activa
        db:         Motor AsyncIOMotorDatabase
        user:       Dict del usuario autenticado

    Returns:
        {"plan_id": str, "description": str, "total_steps": int}
    """
    from tool_definitions import TOOL_DEFS

    plan_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc)

    actions = []
    desc_lines = []
    for i, tc in enumerate(tool_calls, start=1):
        tool_name = tc.get("tool_name") or tc.get("name", "")
        tool_input = tc.get("tool_input") or tc.get("input", {})
        tool_def = TOOL_DEFS.get(tool_name, {})
        natural = tc.get("description") or tool_def.get("description", tool_name)
        actions.append({
            "step": i,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "description": natural,
            "status": "pending",
            "result": None,
            "alegra_id": None,
            "error": None,
            "executed_at": None,
        })
        desc_lines.append(f"Paso {i}: {natural}")

    plan_doc = {
        "plan_id": plan_id,
        "session_id": session_id,
        "user_id": user.get("id"),
        "created_at": now.isoformat(),
        "status": "pending_approval",
        "original_request": request,
        "actions": actions,
        "completed_steps": 0,
        "total_steps": len(actions),
        "summary": None,
    }

    await db.agent_plans.insert_one(plan_doc)

    description = (
        f"Plan de {len(actions)} pasos para: {request}\n\n"
        + "\n".join(desc_lines)
    )

    return {
        "plan_id": plan_id,
        "description": description,
        "total_steps": len(actions),
    }


async def execute_chat_action_for_plan(tool_name: str, tool_input: dict, db, user: dict) -> dict:
    """
    Wrapper de execute_chat_action para uso dentro de execute_plan().
    Retorna siempre {"success": bool, "alegra_id": str|None, "result": dict, "error": str|None}.

    Regla: NUNCA llama Alegra directo — siempre via execute_chat_action() (que usa ACTION_MAP interno).
    """
    from ai_chat import execute_chat_action
    try:
        result = await execute_chat_action(tool_name, tool_input, db, user)
        success = result.get("success", True)
        alegra_id = (
            result.get("alegra_id")
            or result.get("journal_id")
            or result.get("invoice_id")
            or result.get("payment_id")
        )
        return {
            "success": success,
            "alegra_id": str(alegra_id) if alegra_id else None,
            "result": result,
            "error": result.get("error") if not success else None,
        }
    except Exception as exc:
        logger.error(f"execute_chat_action_for_plan error [{tool_name}]: {exc}")
        return {"success": False, "alegra_id": None, "result": {}, "error": str(exc)}


async def execute_plan(plan_id: str, db, user: dict) -> dict:
    """
    Carga un plan de agent_plans y ejecuta sus acciones en orden.

    Reglas:
    - Cambia status a executing
    - Por cada acción: ejecuta via execute_chat_action_for_plan()
    - Si success: marca completed, guarda alegra_id, incrementa completed_steps
    - Si failure: marca failed en la acción Y en el plan, PARA y retorna error descriptivo
    - Cuando todos completan: status completed + genera summary

    NUNCA llama Alegra directo — toda ejecución pasa por execute_chat_action_for_plan().

    Returns:
        {"status": "completed"|"failed", "completed_steps": int, "total_steps": int,
         "summary": str|None, "error": str|None, "alegra_ids": list[str]}
    """
    plan = await db.agent_plans.find_one({"plan_id": plan_id})
    if not plan:
        return {
            "status": "failed",
            "error": f"Plan no encontrado: {plan_id}",
            "completed_steps": 0,
            "total_steps": 0,
            "summary": None,
            "alegra_ids": [],
        }

    total = plan.get("total_steps", len(plan.get("actions", [])))

    # Marcar como executing
    await db.agent_plans.update_one(
        {"plan_id": plan_id},
        {"$set": {"status": "executing"}},
    )

    alegra_ids = []
    completed = 0

    for action in plan.get("actions", []):
        step = action["step"]
        tool_name = action["tool_name"]
        tool_input = action["tool_input"]

        # Marcar acción como executing
        await db.agent_plans.update_one(
            {"plan_id": plan_id, "actions.step": step},
            {"$set": {"actions.$.status": "executing"}},
        )

        result = await execute_chat_action_for_plan(tool_name, tool_input, db, user)

        executed_at = datetime.now(timezone.utc).isoformat()

        if result["success"]:
            alegra_id = result.get("alegra_id")
            if alegra_id:
                alegra_ids.append(alegra_id)
            completed += 1
            await db.agent_plans.update_one(
                {"plan_id": plan_id, "actions.step": step},
                {"$set": {
                    "actions.$.status": "completed",
                    "actions.$.result": result.get("result", {}),
                    "actions.$.alegra_id": alegra_id,
                    "actions.$.executed_at": executed_at,
                    "completed_steps": completed,
                }},
            )
        else:
            error_msg = f"Paso {step} ({tool_name}) falló: {result.get('error', 'error desconocido')}"
            await db.agent_plans.update_one(
                {"plan_id": plan_id, "actions.step": step},
                {"$set": {
                    "actions.$.status": "failed",
                    "actions.$.error": result.get("error"),
                    "actions.$.executed_at": executed_at,
                    "status": "failed",
                }},
            )
            return {
                "status": "failed",
                "completed_steps": completed,
                "total_steps": total,
                "summary": None,
                "error": error_msg,
                "alegra_ids": alegra_ids,
            }

    # Todos los pasos completados
    summary = (
        f"Plan completado: {completed}/{total} pasos. "
        f"IDs Alegra: {', '.join(alegra_ids) if alegra_ids else 'ninguno (solo lecturas)'}."
    )
    await db.agent_plans.update_one(
        {"plan_id": plan_id},
        {"$set": {"status": "completed", "summary": summary, "completed_steps": completed}},
    )

    return {
        "status": "completed",
        "completed_steps": completed,
        "total_steps": total,
        "summary": summary,
        "error": None,
        "alegra_ids": alegra_ids,
    }


async def cancel_plan(plan_id: str, db) -> dict:
    """Cancela un plan cambiando su status a cancelled."""
    await db.agent_plans.update_one(
        {"plan_id": plan_id},
        {"$set": {"status": "cancelled"}},
    )
    return {"cancelled": True, "plan_id": plan_id, "message": "Plan cancelado por el usuario"}


# =============================================================================
# ReAct Nivel 1 — Memoria Persistente (Phase 10B)
# =============================================================================

def should_create_plan(tool_calls: list) -> bool:
    """
    Determina si se debe crear un agent_plan para las tool_calls dadas.

    Regla:
    - Una sola tool_call de LECTURA (consultar_facturas, consultar_cartera): False
    - Cualquier tool_call de ESCRITURA: True
    - Múltiples tool_calls (sin importar tipo): True

    Returns:
        True si se debe crear un plan y pedir aprobación al usuario
    """
    READ_TOOLS = {"consultar_facturas", "consultar_cartera"}

    if len(tool_calls) > 1:
        return True

    if len(tool_calls) == 1:
        tool_name = tool_calls[0].get("tool_name") or tool_calls[0].get("name", "")
        # Solo lectura pura → ejecutar directo
        if tool_name in READ_TOOLS:
            return False
        # Escritura → crear plan
        return True

    return False  # lista vacía — no crear plan


import anthropic as _anthropic  # noqa: E402 — needed for mock patching in tests


async def extract_and_save_memory(
    request: str,
    result: dict,
    db,
    user: dict,
) -> dict | None:
    """
    Extrae aprendizajes de la interacción y los persiste en agent_memory sin TTL.

    Usa claude-haiku-4-5-20251001 para detectar:
    - correction: usuario corrigió una clasificación o cuenta
    - pattern: una cuenta específica fue usada para un proveedor nuevo
    - preference: usuario prefirió un banco/forma de pago específica

    Solo guarda si confidence >= 0.7.
    Hace upsert por {user_id, key} — no duplica.

    Returns:
        dict con {key, value, source, confidence} si se guardó, None si no
    """
    import os
    import json as _json

    user_id = user.get("id", "unknown")

    # Prompt ligero para extracción de aprendizaje
    extraction_prompt = f"""Analiza esta interacción del Agente Contador de RODDOS y determina si hay un aprendizaje persistente.

Solicitud del usuario: {request}
Resultado: {str(result)[:500]}

Responde SOLO con JSON (sin markdown):
{{
  "has_learning": true/false,
  "key": "identificador_semantico_corto_snake_case",
  "value": "aprendizaje en lenguaje natural, máximo 100 caracteres",
  "source": "correction" | "pattern" | "preference",
  "confidence": 0.0-1.0
}}

Patrones a detectar:
- correction: el usuario corrigió una clasificación contable o cuenta
- pattern: una cuenta/proveedor específico fue usado por primera vez
- preference: el usuario eligió banco o forma de pago específica

Si no hay aprendizaje claro con confidence >= 0.7, retorna has_learning: false."""

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None

        client = _anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = resp.content[0].text.strip()

        # Limpiar markdown si viene envuelto
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = _json.loads(raw)

        if not data.get("has_learning") or float(data.get("confidence", 0)) < 0.7:
            return None

        key = data["key"]
        value = data["value"]
        source = data.get("source", "pattern")
        confidence = float(data["confidence"])

        now = datetime.now(timezone.utc).isoformat()

        await db.agent_memory.update_one(
            {"user_id": user_id, "key": key},
            {
                "$set": {
                    "value": value,
                    "source": source,
                    "confidence": confidence,
                    "updated_at": now,
                    "user_id": user_id,
                    "key": key,
                },
                "$setOnInsert": {"created_at": now},
                "$inc": {"usage_count": 1},
            },
            upsert=True,
        )

        return {"key": key, "value": value, "source": source, "confidence": confidence}

    except Exception as exc:
        logger.warning("extract_and_save_memory error: %s", exc)
        return None
