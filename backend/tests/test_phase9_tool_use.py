"""
Phase 9 Tests: Tool Use Migration — Agente Contador
====================================================
TDD RED phase: Define contract for the tool_use loop BEFORE implementation.

T1-T4: GREEN  — Validate tool_definitions.py structure (can pass immediately).
T5-T9: xfail  — Assert process_chat() tool_use behavior (RED: not implemented yet).

Run: cd backend && python -m pytest tests/test_phase9_tool_use.py -v
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Stub anthropic before any import that pulls it in ─────────────────────────
if "anthropic" not in sys.modules:
    _anthropic_stub = MagicMock()
    sys.modules["anthropic"] = _anthropic_stub


# =============================================================================
# GROUP 1: TOOL_DEFS structure — T1-T4 (GREEN)
# =============================================================================

class TestToolDefsStructure:
    """
    T1-T4: Validate TOOL_DEFS dict in tool_definitions.py.
    These tests validate the contract BEFORE implementation. They should pass
    immediately once tool_definitions.py is created.
    """

    # T1: Exactly 6 tools
    def test_t1_tool_defs_has_6_tools(self):
        """T1: TOOL_DEFS must contain exactly 6 MVP tools."""
        from tool_definitions import TOOL_DEFS
        assert len(TOOL_DEFS) == 6, (
            f"Expected 6 tools, got {len(TOOL_DEFS)}: {list(TOOL_DEFS.keys())}"
        )
        expected_names = {
            "crear_causacion",
            "registrar_pago_cartera",
            "registrar_nomina",
            "consultar_facturas",
            "consultar_cartera",
            "crear_factura_venta",
        }
        assert set(TOOL_DEFS.keys()) == expected_names

    # T2: Write tools require confirmation
    def test_t2_write_tools_require_confirmation(self):
        """T2: All write tools must have requires_confirmation == True."""
        from tool_definitions import TOOL_DEFS
        write_tools = [
            "crear_causacion",
            "registrar_pago_cartera",
            "registrar_nomina",
            "crear_factura_venta",
        ]
        for tool_name in write_tools:
            assert tool_name in TOOL_DEFS, f"Tool {tool_name!r} not found in TOOL_DEFS"
            assert TOOL_DEFS[tool_name]["requires_confirmation"] is True, (
                f"Write tool {tool_name!r} must have requires_confirmation=True"
            )

    # T3: Read tools do NOT require confirmation
    def test_t3_read_tools_do_not_require_confirmation(self):
        """T3: All read tools must have requires_confirmation == False."""
        from tool_definitions import TOOL_DEFS
        read_tools = [
            "consultar_facturas",
            "consultar_cartera",
        ]
        for tool_name in read_tools:
            assert tool_name in TOOL_DEFS, f"Tool {tool_name!r} not found in TOOL_DEFS"
            assert TOOL_DEFS[tool_name]["requires_confirmation"] is False, (
                f"Read tool {tool_name!r} must have requires_confirmation=False"
            )

    # T4: crear_causacion has correct required fields for double-entry accounting
    def test_t4_crear_causacion_required_fields(self):
        """T4: crear_causacion.input_schema.required must have entries/date/observations (ROG-1 fix)."""
        from tool_definitions import TOOL_DEFS
        schema = TOOL_DEFS["crear_causacion"]["input_schema"]
        required = schema.get("required", [])
        # entries/date/observations — matches execute_chat_action expectation (ROG-1 hotfix)
        expected_required = {"entries", "date", "observations"}
        assert set(required) == expected_required, (
            f"crear_causacion required mismatch. "
            f"Expected: {expected_required}, got: {set(required)}"
        )
        assert len(required) == 3, (
            f"crear_causacion should have exactly 3 required fields, got {len(required)}: {required}"
        )
        # Verify entries items schema has id/debit/credit
        entries_items = schema["properties"]["entries"]["items"]["properties"]
        assert "id" in entries_items, "entries items must have 'id' (Alegra account ID)"
        assert "debit" in entries_items, "entries items must have 'debit'"
        assert "credit" in entries_items, "entries items must have 'credit'"

    def test_t4b_get_tool_schemas_strips_internal_fields(self):
        """T4b: get_tool_schemas_for_api() must not include requires_confirmation/endpoint/method."""
        from tool_definitions import get_tool_schemas_for_api
        schemas = get_tool_schemas_for_api()
        assert len(schemas) == 6
        for schema in schemas:
            assert "requires_confirmation" not in schema, (
                f"Internal field 'requires_confirmation' leaked into API schema for {schema.get('name')}"
            )
            assert "endpoint" not in schema, (
                f"Internal field 'endpoint' leaked into API schema for {schema.get('name')}"
            )
            assert "method" not in schema, (
                f"Internal field 'method' leaked into API schema for {schema.get('name')}"
            )
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema


# =============================================================================
# GROUP 2: process_chat() tool_use behavior — T5-T9 (xfail RED)
# =============================================================================
# These tests define the contract for the tool_use loop implementation.
# They MUST FAIL today because process_chat() has no TOOL_USE_ENABLED branch.
# They will be promoted to GREEN in Plan 09-02 when implementation is added.
# =============================================================================

def _make_async_cursor(items=None):
    """Return a mock Motor cursor with .to_list() and chaining support (.sort(), .limit())."""
    items = items or []
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=items)
    # Chaining: .sort() / .limit() / .skip() return another cursor
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    return cursor


class _AsyncCollection:
    """
    Auto-mocking DB collection: any method returns an AsyncMock or cursor.
    This avoids having to enumerate every collection method used in process_chat().
    """

    def __getattr__(self, name):
        if name in ("find", "aggregate"):
            return MagicMock(return_value=_make_async_cursor([]))
        return AsyncMock(return_value=None)


class _AsyncDb:
    """
    Auto-mocking DB: any attribute access returns an _AsyncCollection.
    Specific collections that need custom behavior are set as class attributes.
    """

    def __init__(self):
        # agent_sessions — T6 needs to track update_one calls
        self.agent_sessions = _AsyncCollection()
        self.agent_sessions.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        self.agent_sessions.find_one = AsyncMock(return_value=None)

        # chat_messages — needs insert_one
        self.chat_messages = _AsyncCollection()
        self.chat_messages.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="test-id")
        )
        self.chat_messages.find = MagicMock(return_value=_make_async_cursor([]))

        # loanbook — count_documents used directly in process_chat
        self.loanbook = _AsyncCollection()
        self.loanbook.count_documents = AsyncMock(return_value=5)
        self.loanbook.find = MagicMock(return_value=_make_async_cursor([]))
        self.loanbook.aggregate = MagicMock(return_value=_make_async_cursor([]))
        self.loanbook.find_one = AsyncMock(return_value=None)

    def __getattr__(self, name):
        # Any other collection → auto _AsyncCollection
        col = _AsyncCollection()
        object.__setattr__(self, name, col)
        return col


def _make_mock_db():
    """Build a realistic mock DB with all collections used by process_chat()."""
    return _AsyncDb()


def _make_tool_use_response(tool_name: str, tool_input: dict, text: str = "Voy a procesar eso."):
    """Build a mock Anthropic response with stop_reason='tool_use'."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = "toolu_test_001"

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [text_block, tool_block]
    response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return response


def _make_end_turn_response(text: str):
    """Build a mock Anthropic response with stop_reason='end_turn' and XML action."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [text_block]
    response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return response


def test_t5_tool_use_enabled_write_tool_returns_pending_action():
    """
    T5: TOOL_USE_ENABLED=true + stop_reason=tool_use + requires_confirmation=true
    → process_chat() returns pending_action (NOT executed, no Alegra call).

    Expected: result["pending_action"]["type"] == "crear_causacion"
    Expected: result["pending_action"]["payload"] contains the tool input
    Expected: NO AlegraService.request_with_verify call made
    """
    from ai_chat import process_chat

    mock_db = _make_mock_db()
    mock_user = {"id": "user-test", "email": "test@roddos.co", "role": "admin"}

    tool_input = {
        "monto": 150000.0,
        "descripcion": "Arrendamiento enero 2026",
        "cuenta_id": 5493,
        "fecha": "2026-01-15",
        "banco_id": "bbva_cte",
    }

    mock_response = _make_tool_use_response("crear_causacion", tool_input)

    # Patch gather_context and gather_accounts_context to avoid deep import chain
    _ctx_data = {"loanbook_activos": [], "iva_status": None}
    _acct_data = ("", "", "")

    with patch.dict(os.environ, {"TOOL_USE_ENABLED": "true"}):
        with patch("ai_chat.gather_context", AsyncMock(return_value=_ctx_data)):
            with patch("ai_chat.gather_accounts_context", AsyncMock(return_value=_acct_data)):
                with patch("ai_chat.get_pending_topics", AsyncMock(return_value=[])):
                    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
                        mock_client = MagicMock()
                        mock_anthropic_cls.return_value = mock_client
                        mock_client.messages.create = AsyncMock(return_value=mock_response)

                        with patch("alegra_service.AlegraService") as mock_alegra_cls:
                            mock_alegra = MagicMock()
                            mock_alegra_cls.return_value = mock_alegra
                            mock_alegra.request_with_verify = AsyncMock(return_value={})

                            result = asyncio.run(
                                process_chat(
                                    session_id="test-session-001",
                                    user_message="Registra causación arrendamiento $150.000",
                                    db=mock_db,
                                    user=mock_user,
                                )
                            )

    # T5 assertions
    assert result is not None
    assert "pending_action" in result
    assert result["pending_action"] is not None, "pending_action debe ser un dict, no None"
    assert result["pending_action"]["type"] == "crear_causacion"
    assert result["pending_action"]["payload"] == tool_input

    # No Alegra call — write tools require user confirmation first
    mock_alegra.request_with_verify.assert_not_called()


def test_t6_write_tool_pending_action_persisted_to_mongodb():
    """
    T6: TOOL_USE_ENABLED=true + stop_reason=tool_use + requires_confirmation=true
    → pending_action MUST be persisted to MongoDB agent_sessions (NOT just returned in dict).

    Critical production-safety constraint: if the frontend crashes after receiving
    the confirmation request, the pending_action must survive in DB for recovery.

    Expected: db.agent_sessions.update_one() called with pending_action payload.
    """
    from ai_chat import process_chat

    mock_db = _make_mock_db()
    mock_user = {"id": "user-test", "email": "test@roddos.co", "role": "admin"}

    tool_input = {
        "monto": 200000.0,
        "descripcion": "Nomina febrero 2026",
        "cuenta_id": 5400,
        "fecha": "2026-02-28",
        "banco_id": "bbva_cte",
    }

    mock_response = _make_tool_use_response("crear_causacion", tool_input)

    # Patch gather_context and gather_accounts_context to avoid deep import chain
    _ctx_data = {"loanbook_activos": [], "iva_status": None}
    _acct_data = ("", "", "")

    with patch.dict(os.environ, {"TOOL_USE_ENABLED": "true"}):
        with patch("ai_chat.gather_context", AsyncMock(return_value=_ctx_data)):
            with patch("ai_chat.gather_accounts_context", AsyncMock(return_value=_acct_data)):
                with patch("ai_chat.get_pending_topics", AsyncMock(return_value=[])):
                    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
                        mock_client = MagicMock()
                        mock_anthropic_cls.return_value = mock_client
                        mock_client.messages.create = AsyncMock(return_value=mock_response)

                        asyncio.run(
                            process_chat(
                                session_id="test-session-t6",
                                user_message="Crea causación nómina",
                                db=mock_db,
                                user=mock_user,
                            )
                        )

    # T6 critical assertion: pending_action persisted to MongoDB
    mock_db.agent_sessions.update_one.assert_called()
    call_args = mock_db.agent_sessions.update_one.call_args
    assert call_args is not None, "db.agent_sessions.update_one() was never called"

    # Verify the payload contains the pending_action
    update_doc = call_args[0][1] if call_args[0] else call_args.args[1]
    # The update doc should set pending_action in $set
    assert "$set" in update_doc, (
        f"update_one call missing $set operator. Got: {update_doc}"
    )
    set_fields = update_doc["$set"]
    assert "pending_action" in set_fields, (
        f"$set does not contain 'pending_action'. Got fields: {list(set_fields.keys())}"
    )
    assert set_fields["pending_action"]["type"] == "crear_causacion"


def test_t7_tool_use_enabled_end_turn_falls_back_to_xml():
    """
    T7: TOOL_USE_ENABLED=true + stop_reason=end_turn (model chose no tool)
    → process_chat() falls back to XML flow and parses <action> tag.

    This is the hybrid fallback (D-04): when the model answers without calling
    any tool, the existing XML parsing still works.
    """
    from ai_chat import process_chat

    mock_db = _make_mock_db()
    mock_user = {"id": "user-test", "email": "test@roddos.co", "role": "admin"}

    xml_action = json.dumps({"type": "consultar_cartera", "payload": {}})
    response_text = f"Aquí está la cartera. <action>{xml_action}</action>"
    mock_response = _make_end_turn_response(response_text)

    # Patch gather_context and gather_accounts_context to avoid deep import chain
    _ctx_data = {"loanbook_activos": [], "iva_status": None}
    _acct_data = ("", "", "")

    with patch.dict(os.environ, {"TOOL_USE_ENABLED": "true"}):
        with patch("ai_chat.gather_context", AsyncMock(return_value=_ctx_data)):
            with patch("ai_chat.gather_accounts_context", AsyncMock(return_value=_acct_data)):
                with patch("ai_chat.get_pending_topics", AsyncMock(return_value=[])):
                    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
                        mock_client = MagicMock()
                        mock_anthropic_cls.return_value = mock_client
                        mock_client.messages.create = AsyncMock(return_value=mock_response)

                        result = asyncio.run(
                            process_chat(
                                session_id="test-session-t7",
                                user_message="Consulta la cartera",
                                db=mock_db,
                                user=mock_user,
                            )
                        )

    # T7 assertion: XML fallback parsed the action
    assert result is not None
    assert result.get("pending_action") is not None, (
        "XML fallback should parse <action> tag when stop_reason=end_turn"
    )
    assert result["pending_action"]["type"] == "consultar_cartera"


def test_t8_tool_use_disabled_no_tools_passed_to_api():
    """
    T8: TOOL_USE_ENABLED=false → process_chat() uses XML flow only.
    tools= parameter must NOT be passed to messages.create().

    This ensures the feature flag disables tool_use completely for rollback.
    """
    from ai_chat import process_chat

    mock_db = _make_mock_db()
    mock_user = {"id": "user-test", "email": "test@roddos.co", "role": "admin"}

    mock_response = _make_end_turn_response("Aquí está la información solicitada.")

    # Patch gather_context and gather_accounts_context to avoid deep import chain
    _ctx_data = {"loanbook_activos": [], "iva_status": None}
    _acct_data = ("", "", "")

    with patch.dict(os.environ, {"TOOL_USE_ENABLED": "false"}):
        with patch("ai_chat.gather_context", AsyncMock(return_value=_ctx_data)):
            with patch("ai_chat.gather_accounts_context", AsyncMock(return_value=_acct_data)):
                with patch("ai_chat.get_pending_topics", AsyncMock(return_value=[])):
                    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
                        mock_client = MagicMock()
                        mock_anthropic_cls.return_value = mock_client
                        mock_client.messages.create = AsyncMock(return_value=mock_response)

                        asyncio.run(
                            process_chat(
                                session_id="test-session-t8",
                                user_message="¿Cuánto hay en cartera?",
                                db=mock_db,
                                user=mock_user,
                            )
                        )

    # T8 assertion: messages.create() was called WITHOUT tools= kwarg
    assert mock_client.messages.create.called, "messages.create() should have been called"
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs, (
        f"TOOL_USE_ENABLED=false must not pass tools= to messages.create(). "
        f"Got kwargs: {list(call_kwargs.keys())}"
    )


def test_t9_tool_use_enabled_cache_control_preserved_in_system():
    """
    T9: TOOL_USE_ENABLED=true → messages.create() called with:
      - system=[{"type": "text", ..., "cache_control": {"type": "ephemeral"}}]
      - tools= kwarg present (the 6 tool schemas)

    Validates that prompt caching (D-05) is preserved when tool_use is enabled.
    """
    from ai_chat import process_chat
    from tool_definitions import get_tool_schemas_for_api

    mock_db = _make_mock_db()
    mock_user = {"id": "user-test", "email": "test@roddos.co", "role": "admin"}

    mock_response = _make_end_turn_response("Respuesta normal sin tool call.")

    # Patch gather_context and gather_accounts_context to avoid deep import chain
    _ctx_data = {"loanbook_activos": [], "iva_status": None}
    _acct_data = ("", "", "")

    with patch.dict(os.environ, {"TOOL_USE_ENABLED": "true"}):
        with patch("ai_chat.gather_context", AsyncMock(return_value=_ctx_data)):
            with patch("ai_chat.gather_accounts_context", AsyncMock(return_value=_acct_data)):
                with patch("ai_chat.get_pending_topics", AsyncMock(return_value=[])):
                    with patch("anthropic.AsyncAnthropic") as mock_anthropic_cls:
                        mock_client = MagicMock()
                        mock_anthropic_cls.return_value = mock_client
                        mock_client.messages.create = AsyncMock(return_value=mock_response)

                        asyncio.run(
                            process_chat(
                                session_id="test-session-t9",
                                user_message="Consulta de información",
                                db=mock_db,
                                user=mock_user,
                            )
                        )

    assert mock_client.messages.create.called
    call_kwargs = mock_client.messages.create.call_args.kwargs

    # T9a: tools= must be present
    assert "tools" in call_kwargs, (
        f"TOOL_USE_ENABLED=true must pass tools= to messages.create(). "
        f"Got kwargs: {list(call_kwargs.keys())}"
    )
    assert len(call_kwargs["tools"]) == 6, (
        f"tools= should have 6 entries, got {len(call_kwargs['tools'])}"
    )

    # T9b: system= must have cache_control ephemeral
    assert "system" in call_kwargs, "messages.create() must receive system= param"
    system_param = call_kwargs["system"]
    assert isinstance(system_param, list), "system= must be a list for cache_control"
    assert len(system_param) >= 1
    first_block = system_param[0]
    assert first_block.get("cache_control") == {"type": "ephemeral"}, (
        f"system[0] must have cache_control ephemeral. Got: {first_block.get('cache_control')}"
    )
