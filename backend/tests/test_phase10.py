"""
Phase 10 Tests: ReAct Nivel 1 — Plan Multi-Acción + Ejecución Autónoma
=======================================================================
TDD approach: T1-T4 GREEN (agent_plans + create_plan + execute_plan + cancel_plan).
T5-T9 xfail RED (agent_memory — Phase 10B not implemented yet).

Run: cd backend && python -m pytest tests/test_phase10.py -v
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Stub anthropic before any import that pulls it in ─────────────────────────
if "anthropic" not in sys.modules:
    _anthropic_stub = MagicMock()
    sys.modules["anthropic"] = _anthropic_stub


# =============================================================================
# GROUP 1: agent_plans + create_plan + execute_plan + cancel_plan — T1-T4 (GREEN)
# =============================================================================

@pytest.mark.asyncio
async def test_t1_create_plan_creates_document():
    """T1: create_plan() crea documento en agent_plans con status pending_approval."""
    from tool_executor import create_plan

    db = MagicMock()
    db.agent_plans = AsyncMock()
    db.agent_plans.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc"))

    tool_calls = [
        {
            "tool_name": "crear_causacion",
            "tool_input": {
                "description": "Gasto internet",
                "date": "2026-04-01",
                "entries": [],
            },
        },
        {
            "tool_name": "registrar_pago_cartera",
            "tool_input": {
                "loanbook_id": "LB-0001",
                "monto": 150000,
                "fecha": "2026-04-01",
                "banco_origen": "Bancolombia",
            },
        },
    ]
    result = await create_plan(
        request="Registra un gasto de internet y un pago de cartera",
        tool_calls=tool_calls,
        session_id="test-session-001",
        db=db,
        user={"id": "user-001", "email": "test@roddos.com"},
    )

    assert "plan_id" in result
    assert "description" in result  # lenguaje natural con pasos numerados
    assert "Paso 1" in result["description"] or "paso 1" in result["description"].lower()
    assert db.agent_plans.insert_one.called

    # Verificar que el doc insertado tiene status pending_approval
    call_args = db.agent_plans.insert_one.call_args[0][0]
    assert call_args["status"] == "pending_approval"
    assert call_args["total_steps"] == 2
    assert len(call_args["actions"]) == 2


@pytest.mark.asyncio
async def test_t2_execute_plan_executes_in_order():
    """T2: execute_plan() ejecuta acciones en orden y marca completed."""
    from tool_executor import execute_plan
    import uuid

    plan_id = str(uuid.uuid4())
    plan_doc = {
        "plan_id": plan_id,
        "session_id": "sess-001",
        "user_id": "user-001",
        "status": "pending_approval",
        "original_request": "test",
        "actions": [
            {
                "step": 1,
                "tool_name": "crear_causacion",
                "tool_input": {"description": "Test", "date": "2026-04-01", "entries": []},
                "description": "Paso 1",
                "status": "pending",
                "result": None,
                "alegra_id": None,
                "error": None,
                "executed_at": None,
            },
            {
                "step": 2,
                "tool_name": "consultar_cartera",
                "tool_input": {},
                "description": "Paso 2",
                "status": "pending",
                "result": None,
                "alegra_id": None,
                "error": None,
                "executed_at": None,
            },
        ],
        "completed_steps": 0,
        "total_steps": 2,
        "summary": None,
    }

    db = MagicMock()
    db.agent_plans = AsyncMock()
    db.agent_plans.find_one = AsyncMock(return_value=plan_doc)
    db.agent_plans.update_one = AsyncMock()

    user = {"id": "user-001"}

    with patch("tool_executor.execute_chat_action_for_plan") as mock_exec:
        mock_exec.side_effect = [
            {"success": True, "alegra_id": "J-001", "result": {"id": "J-001"}},
            {"success": True, "alegra_id": None, "result": {"cartera": []}},
        ]
        result = await execute_plan(plan_id, db, user)

    assert result["status"] == "completed"
    assert result["completed_steps"] == 2
    assert mock_exec.call_count == 2

    # Verificar orden de llamadas
    first_call = mock_exec.call_args_list[0]
    assert first_call[0][0] == "crear_causacion"  # primer argumento = tool_name


@pytest.mark.asyncio
async def test_t3_execute_plan_stops_on_failure():
    """T3: execute_plan() para en step fallido y retorna error descriptivo."""
    from tool_executor import execute_plan
    import uuid

    plan_id = str(uuid.uuid4())
    plan_doc = {
        "plan_id": plan_id,
        "session_id": "sess-002",
        "user_id": "user-001",
        "status": "pending_approval",
        "original_request": "test fallo",
        "actions": [
            {
                "step": 1,
                "tool_name": "crear_causacion",
                "tool_input": {"description": "Gasto", "date": "2026-04-01", "entries": []},
                "description": "Paso 1",
                "status": "pending",
                "result": None,
                "alegra_id": None,
                "error": None,
                "executed_at": None,
            },
            {
                "step": 2,
                "tool_name": "registrar_pago_cartera",
                "tool_input": {
                    "loanbook_id": "LB-0001",
                    "monto": 100000,
                    "fecha": "2026-04-01",
                    "banco_origen": "X",
                },
                "description": "Paso 2",
                "status": "pending",
                "result": None,
                "alegra_id": None,
                "error": None,
                "executed_at": None,
            },
        ],
        "completed_steps": 0,
        "total_steps": 2,
        "summary": None,
    }

    db = MagicMock()
    db.agent_plans = AsyncMock()
    db.agent_plans.find_one = AsyncMock(return_value=plan_doc)
    db.agent_plans.update_one = AsyncMock()
    user = {"id": "user-001"}

    with patch("tool_executor.execute_chat_action_for_plan") as mock_exec:
        mock_exec.return_value = {"success": False, "error": "HTTP 422 de Alegra", "alegra_id": None}
        result = await execute_plan(plan_id, db, user)

    assert result["status"] == "failed"
    assert "error" in result
    assert "HTTP 422" in result["error"] or "Paso 1" in result["error"]
    # Solo se ejecutó el paso 1 (falló), el paso 2 NO se ejecutó
    assert mock_exec.call_count == 1


@pytest.mark.asyncio
async def test_t4_approve_plan_false_cancels():
    """T4: cancel_plan() cancela el plan cambiando status a cancelled."""
    from tool_executor import cancel_plan
    import uuid

    plan_id = str(uuid.uuid4())

    db = MagicMock()
    db.agent_plans = AsyncMock()
    db.agent_plans.update_one = AsyncMock()

    result = await cancel_plan(plan_id, db)

    assert result["cancelled"] is True
    assert db.agent_plans.update_one.called
    call_args = db.agent_plans.update_one.call_args
    assert call_args[0][1]["$set"]["status"] == "cancelled"


# =============================================================================
# GROUP 2: agent_memory — T5-T9 (xfail RED — Phase 10B not implemented yet)
# =============================================================================

@pytest.mark.xfail(reason="RED: Phase 10B — extract_and_save_memory not implemented yet")
@pytest.mark.asyncio
async def test_t5_extract_memory_saves_with_confidence():
    """T5: extract_and_save_memory() guarda en agent_memory con confidence >= 0.7."""
    from tool_executor import extract_and_save_memory

    db = MagicMock()
    db.agent_memory = AsyncMock()
    db.agent_memory.find_one = AsyncMock(return_value=None)
    db.agent_memory.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mem-001"))

    conversation_text = (
        "Usuario: ¿Cuánto le debo a Bancolombia?\n"
        "Agente: Según los loanbooks activos, la deuda total es $94M COP."
    )
    result = await extract_and_save_memory(
        conversation_text=conversation_text,
        session_id="sess-memory-001",
        db=db,
        user={"id": "user-001"},
    )

    assert result is not None
    assert "saved" in result or "memories" in result
    # Verificar que se llamó insert_one con confidence >= 0.7
    if db.agent_memory.insert_one.called:
        call_doc = db.agent_memory.insert_one.call_args[0][0]
        assert call_doc.get("confidence", 0) >= 0.7


@pytest.mark.xfail(reason="RED: Phase 10B — extract_and_save_memory upsert not implemented yet")
@pytest.mark.asyncio
async def test_t6_extract_memory_upsert_no_duplicate():
    """T6: extract_and_save_memory() hace upsert (no duplica si key existe)."""
    from tool_executor import extract_and_save_memory

    existing_memory = {
        "memory_key": "deuda_bancolombia",
        "value": "$94M COP",
        "confidence": 0.85,
        "user_id": "user-001",
    }

    db = MagicMock()
    db.agent_memory = AsyncMock()
    db.agent_memory.find_one = AsyncMock(return_value=existing_memory)
    db.agent_memory.update_one = AsyncMock()
    db.agent_memory.insert_one = AsyncMock()

    conversation_text = (
        "Usuario: ¿Cuánto le debo a Bancolombia?\n"
        "Agente: La deuda total es $94M COP."
    )
    await extract_and_save_memory(
        conversation_text=conversation_text,
        session_id="sess-memory-002",
        db=db,
        user={"id": "user-001"},
    )

    # Upsert: update_one debe ser llamado, insert_one NO
    assert db.agent_memory.update_one.called
    assert not db.agent_memory.insert_one.called


@pytest.mark.xfail(reason="RED: Phase 10B — build_agent_prompt memory section not implemented yet")
@pytest.mark.asyncio
async def test_t7_build_agent_prompt_includes_memory():
    """T7: build_agent_prompt() incluye sección MEMORIA PERSISTENTE cuando hay registros."""
    from ai_chat import build_agent_prompt

    db = MagicMock()
    db.agent_memory = AsyncMock()
    # Simulate 2 memory records
    db.agent_memory.find = MagicMock()
    db.agent_memory.find.return_value.to_list = AsyncMock(return_value=[
        {
            "memory_key": "cliente_frecuente",
            "value": "Andrés Martínez paga los lunes",
            "confidence": 0.9,
        },
        {
            "memory_key": "banco_preferido",
            "value": "Bancolombia cuenta corriente",
            "confidence": 0.8,
        },
    ])

    prompt = await build_agent_prompt(
        user_id="user-001",
        db=db,
        include_memory=True,
    )

    assert "MEMORIA" in prompt.upper() or "memoria" in prompt.lower()
    assert "cliente_frecuente" in prompt or "Andrés Martínez" in prompt


@pytest.mark.xfail(reason="RED: Phase 10B — single read action direct execution not implemented yet")
@pytest.mark.asyncio
async def test_t8_single_read_action_no_plan_created():
    """T8: Plan con una sola acción de lectura NO crea agent_plans — ejecuta directo."""
    from tool_executor import create_plan_or_execute_direct

    db = MagicMock()
    db.agent_plans = AsyncMock()
    db.agent_plans.insert_one = AsyncMock()

    tool_calls = [
        {
            "tool_name": "consultar_cartera",
            "tool_input": {},
        }
    ]

    with patch("tool_executor.execute_chat_action_for_plan") as mock_exec:
        mock_exec.return_value = {"success": True, "result": {"cartera": []}, "alegra_id": None}
        result = await create_plan_or_execute_direct(
            request="Muéstrame la cartera",
            tool_calls=tool_calls,
            session_id="sess-direct",
            db=db,
            user={"id": "user-001"},
        )

    # Single read action → executed directly, NO plan created
    assert not db.agent_plans.insert_one.called
    assert result.get("executed_direct") is True or result.get("status") == "completed"


@pytest.mark.xfail(reason="RED: Phase 10B — end-to-end 2 real actions not implemented yet")
@pytest.mark.asyncio
async def test_t9_execute_plan_2_real_actions_returns_alegra_ids():
    """T9: execute_plan() con 2 acciones reales retorna 2 alegra_ids."""
    from tool_executor import execute_plan
    import uuid

    plan_id = str(uuid.uuid4())
    plan_doc = {
        "plan_id": plan_id,
        "session_id": "sess-e2e",
        "user_id": "user-001",
        "status": "pending_approval",
        "original_request": "causación + pago cartera",
        "actions": [
            {
                "step": 1,
                "tool_name": "crear_causacion",
                "tool_input": {
                    "description": "Gasto internet",
                    "date": "2026-04-01",
                    "entries": [{"id": 5493, "debit": 50000, "credit": 0}],
                    "observations": "Gasto internet abril 2026",
                },
                "description": "Crear causación internet",
                "status": "pending",
                "result": None,
                "alegra_id": None,
                "error": None,
                "executed_at": None,
            },
            {
                "step": 2,
                "tool_name": "registrar_pago_cartera",
                "tool_input": {
                    "loanbook_id": "LB-0011",
                    "monto": 149900,
                    "fecha": "2026-04-01",
                    "banco_origen": "Bancolombia",
                },
                "description": "Registrar pago cartera LB-0011",
                "status": "pending",
                "result": None,
                "alegra_id": None,
                "error": None,
                "executed_at": None,
            },
        ],
        "completed_steps": 0,
        "total_steps": 2,
        "summary": None,
    }

    db = MagicMock()
    db.agent_plans = AsyncMock()
    db.agent_plans.find_one = AsyncMock(return_value=plan_doc)
    db.agent_plans.update_one = AsyncMock()

    # Simulate real Alegra responses
    with patch("tool_executor.execute_chat_action_for_plan") as mock_exec:
        mock_exec.side_effect = [
            {"success": True, "alegra_id": "J-2026-001", "result": {"id": "J-2026-001"}},
            {"success": True, "alegra_id": "PAY-2026-001", "result": {"id": "PAY-2026-001"}},
        ]
        result = await execute_plan(plan_id, db, {"id": "user-001"})

    assert result["status"] == "completed"
    assert len(result["alegra_ids"]) == 2
    assert "J-2026-001" in result["alegra_ids"]
    assert "PAY-2026-001" in result["alegra_ids"]
