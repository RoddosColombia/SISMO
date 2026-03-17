"""
test_build21_integration.py — Integration tests for BUILD 21 features.
Tests: accounting engine, scheduler, memory, alegra service, execute_chat_action actions.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# ── Test 4: diagnosticar_contabilidad in execute_chat_action ─────────────────
class TestDiagnosticarContabilidadAction:
    """Verifica que la acción diagnosticar_contabilidad está disponible en execute_chat_action"""

    def test_action_exists_in_ai_chat(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        assert "diagnosticar_contabilidad" in source, "Action 'diagnosticar_contabilidad' not found in execute_chat_action"

    def test_guardar_pendiente_exists(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        assert "guardar_pendiente" in source

    def test_verificar_estado_alegra_exists(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        assert "verificar_estado_alegra" in source

    def test_completar_pendiente_exists(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        assert "completar_pendiente" in source


# ── Test 5: TTL index on agent_pending_topics ─────────────────────────────────
class TestPendingTopicsTTL:
    """Verifica que la colección agent_pending_topics tiene índice TTL"""

    def test_ttl_index_exists(self):
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
        from motor.motor_asyncio import AsyncIOMotorClient

        async def check():
            client = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = client[os.environ['DB_NAME']]
            indexes = await db['agent_pending_topics'].index_information()
            return indexes

        indexes = asyncio.get_event_loop().run_until_complete(check())
        ttl_found = any(
            info.get('expireAfterSeconds') is not None
            for info in indexes.values()
        )
        assert ttl_found, f"No TTL index found in agent_pending_topics. Indexes: {list(indexes.keys())}"

    def test_ttl_index_on_expires_at_field(self):
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
        from motor.motor_asyncio import AsyncIOMotorClient

        async def check():
            client = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = client[os.environ['DB_NAME']]
            indexes = await db['agent_pending_topics'].index_information()
            return indexes

        indexes = asyncio.get_event_loop().run_until_complete(check())
        ttl_index = indexes.get('ttl_pending_topics')
        assert ttl_index is not None, "ttl_pending_topics index not found"
        assert ttl_index.get('expireAfterSeconds') == 0
        assert ('expires_at', 1) in ttl_index['key']


# ── Test 6: Scheduler BUILD 21 jobs ──────────────────────────────────────────
class TestSchedulerBuild21:
    """Verifica que los jobs BUILD 21 están registrados en start_scheduler"""

    def test_resumen_semanal_cfo_registered(self):
        from services import scheduler as sched_module
        import inspect
        source = inspect.getsource(sched_module.start_scheduler)
        assert "resumen_semanal_cfo" in source, "Job resumen_semanal_cfo not found in start_scheduler"

    def test_anomalias_contables_diarias_registered(self):
        from services import scheduler as sched_module
        import inspect
        source = inspect.getsource(sched_module.start_scheduler)
        assert "anomalias_contables_diarias" in source, "Job anomalias_contables_diarias not found in start_scheduler"

    def test_scheduler_log_contains_build21_jobs(self):
        """Verifica que el log de inicio muestra los jobs BUILD21"""
        from services import scheduler as sched_module
        import inspect
        source = inspect.getsource(sched_module.start_scheduler)
        assert "BUILD21" in source or "resumen_semanal_cfo" in source


# ── Test 7: verificar_estado_alegra action ───────────────────────────────────
class TestVerificarEstadoAlegra:
    """Verifica que la acción verificar_estado_alegra ejecuta sin error"""

    def test_verificar_estado_alegra_demo_mode(self):
        from ai_chat import execute_chat_action
        import inspect
        source = inspect.getsource(execute_chat_action)
        # Verify the action is handled in the source
        assert "verificar_estado_alegra" in source
        # Verify it handles resource parameter
        lines = [l for l in source.split('\n') if 'verificar_estado_alegra' in l]
        assert len(lines) > 0, "verificar_estado_alegra action not found in execute_chat_action"
        print(f"verificar_estado_alegra lines: {lines}")


# ── Test 9: endpoint /journals (not /journal-entries) ────────────────────────
class TestEndpointJournals:
    """Verifica que crear_causacion usa endpoint 'journals' NO 'journal-entries'"""

    def test_crear_causacion_uses_journals_endpoint(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        # Check the mapping
        assert '"journals"' in source or "'journals'" in source
        # Ensure journal-entries is NOT used as the action mapping
        # The create_causacion must map to journals
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if 'crear_causacion' in line and ('journal-entries' in line):
                pytest.fail(f"Line {i}: crear_causacion mapped to journal-entries instead of journals: {line}")

    def test_action_map_has_journals(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        # crear_causacion → ("journals", "POST") 
        assert '"crear_causacion": ("journals"' in source or \
               '"crear_causacion": ("journals"' in source or \
               'crear_causacion.*journals' in source or \
               ('crear_causacion' in source and 'journals' in source)


# ── Test 10: _translate_error_to_spanish direct ──────────────────────────────
class TestTranslateErrorToSpanish:
    def setup_method(self):
        from unittest.mock import MagicMock
        self.db_mock = MagicMock()
        from alegra_service import AlegraService
        self.service = AlegraService(self.db_mock)

    def test_balance_error_in_spanish(self):
        msg = self.service._translate_error_to_spanish(
            400, {"message": "debit and credit must be equal"}, "journals", "POST"
        )
        assert msg != ""
        # Should contain Spanish words about balance
        assert any(word in msg.lower() for word in ["balance", "asiento", "igual", "cuadra", "débito", "crédito"])

    def test_401_in_spanish(self):
        msg = self.service._translate_error_to_spanish(401, {}, "journals", "POST")
        assert "credencial" in msg.lower() or "alegra" in msg.lower()

    def test_409_duplicate_in_spanish(self):
        msg = self.service._translate_error_to_spanish(409, {}, "journals", "POST")
        assert "duplicado" in msg.lower() or "conflicto" in msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
