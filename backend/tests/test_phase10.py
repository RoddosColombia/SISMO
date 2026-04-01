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
# GROUP 2: agent_memory — T5-T8 (GREEN — Phase 10B implemented)
# T9: xfail — end-to-end with real Alegra requires deploy
# =============================================================================

@pytest.mark.asyncio
async def test_t5_extract_and_save_memory_saves_with_high_confidence():
    """T5: extract_and_save_memory() guarda en agent_memory con confidence >= 0.7."""
    import json
    from tool_executor import extract_and_save_memory

    db = MagicMock()
    db.agent_memory = AsyncMock()
    db.agent_memory.update_one = AsyncMock()

    user = {"id": "user-001"}

    # Mock anthropic client para retornar aprendizaje válido
    mock_resp_content = MagicMock()
    mock_resp_content.text = json.dumps({
        "has_learning": True,
        "key": "auteco_autoretenedor",
        "value": "Auteco NIT 860024781 es AUTORETENEDOR — nunca aplicar ReteFuente",
        "source": "correction",
        "confidence": 0.95,
    })
    mock_resp = MagicMock()
    mock_resp.content = [mock_resp_content]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    import os
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("tool_executor._anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            result = await extract_and_save_memory(
                request="Registra gasto proveedor Auteco",
                result={"success": True, "alegra_id": "J-005"},
                db=db,
                user=user,
            )

    assert result is not None
    assert result["key"] == "auteco_autoretenedor"
    assert result["confidence"] >= 0.7
    assert db.agent_memory.update_one.called


@pytest.mark.asyncio
async def test_t6_extract_and_save_memory_upserts_not_duplicates():
    """T6: extract_and_save_memory() hace upsert — no duplica si key ya existe."""
    import json
    from tool_executor import extract_and_save_memory

    db = MagicMock()
    db.agent_memory = AsyncMock()
    db.agent_memory.update_one = AsyncMock()

    user = {"id": "user-001"}

    mock_resp_content = MagicMock()
    mock_resp_content.text = json.dumps({
        "has_learning": True,
        "key": "banco_preferido_nequi",
        "value": "Usuario prefiere Nequi para pagos de cartera",
        "source": "preference",
        "confidence": 0.80,
    })
    mock_resp = MagicMock()
    mock_resp.content = [mock_resp_content]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    import os
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("tool_executor._anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic.return_value = mock_client

            # Llamar 2 veces con mismo request
            await extract_and_save_memory("Pago cartera Nequi", {"success": True}, db, user)
            await extract_and_save_memory("Pago cartera Nequi", {"success": True}, db, user)

    # update_one con upsert=True fue llamado 2 veces (no insert_one)
    assert db.agent_memory.update_one.call_count == 2
    # Verificar que usa upsert=True en ambas llamadas
    for call in db.agent_memory.update_one.call_args_list:
        assert call[1].get("upsert") is True


@pytest.mark.asyncio
async def test_t7_system_prompt_includes_memory_section():
    """T7: _load_persistent_memory_section() incluye sección MEMORIA PERSISTENTE cuando hay registros."""
    from ai_chat import _load_persistent_memory_section

    db = MagicMock()
    db.agent_memory = MagicMock()

    # Mock the chained find().sort().to_list() call
    mock_cursor = MagicMock()
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=[
        {"key": "auteco_autoretenedor", "value": "Auteco NIT 860024781 es AUTORETENEDOR",
         "source": "correction", "confidence": 0.95, "usage_count": 3},
        {"key": "banco_preferido_nequi", "value": "Usuario prefiere Nequi para pagos",
         "source": "preference", "confidence": 0.80, "usage_count": 1},
    ])
    db.agent_memory.find = MagicMock(return_value=mock_cursor)

    section = await _load_persistent_memory_section(db, "user-001")

    assert "MEMORIA PERSISTENTE" in section
    assert "auteco_autoretenedor" in section or "Auteco NIT" in section


@pytest.mark.asyncio
async def test_t8_single_read_tool_no_plan_created():
    """T8: should_create_plan() retorna False para lectura única, True para escritura/multi."""
    from tool_executor import should_create_plan

    # Solo una lectura → no crear plan
    single_read = [{"tool_name": "consultar_facturas", "tool_input": {"fecha_inicio": "2026-04-01", "fecha_fin": "2026-04-30"}}]
    assert should_create_plan(single_read) is False

    # Una escritura → crear plan
    single_write = [{"tool_name": "crear_causacion", "tool_input": {"description": "Gasto", "date": "2026-04-01", "entries": []}}]
    assert should_create_plan(single_write) is True

    # Múltiples acciones → crear plan
    multi = [
        {"tool_name": "consultar_facturas", "tool_input": {}},
        {"tool_name": "crear_causacion", "tool_input": {}},
    ]
    assert should_create_plan(multi) is True


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
