"""
test_smoke_build24.py — 6 tests for /api/health/smoke BUILD 24 checks.
Phase 5 — TST-05

Tests use unittest.mock to avoid needing a live MongoDB or event bus.
The smoke_test function from server.py is called directly with all
external dependencies patched.
"""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _run(coro):
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


def _make_full_mock_db(
    loanbook_count=10,
    cartera_cuotas=None,
    motos_count=34,
    cfo_config=True,
    coll_names=None,
    event_id_index=True,
    catalogo_count=5,
    alegra_token="tok123",
):
    """Build a fully-mocked Motor db object covering all smoke_test queries."""
    if coll_names is None:
        coll_names = [f"col_{i}" for i in range(32)]
    if cartera_cuotas is None:
        # One loan with one pending cuota of $1_000_000
        cartera_cuotas = [{"cuotas": [{"estado": "pendiente", "valor": 1_000_000}]}]

    db = MagicMock()
    db.name = "sismo"

    # loanbook
    db.loanbook.count_documents = AsyncMock(return_value=loanbook_count)
    find_mock = MagicMock()
    find_mock.to_list = AsyncMock(return_value=cartera_cuotas)
    db.loanbook.find = MagicMock(return_value=find_mock)

    # inventario_motos
    db.inventario_motos.count_documents = AsyncMock(return_value=motos_count)

    # cfo_config
    db.cfo_config.find_one = AsyncMock(return_value={"preset": "default"} if cfo_config else None)

    # roddos_events index_information
    if event_id_index:
        idx_info = {
            "_id_": {"key": [("_id", 1)]},
            "event_id_1": {"key": [("event_id", 1)]},
        }
    else:
        idx_info = {
            "_id_": {"key": [("_id", 1)]},
        }
    db.roddos_events.index_information = AsyncMock(return_value=idx_info)

    # catalogo_planes
    db.catalogo_planes.count_documents = AsyncMock(return_value=catalogo_count)

    # alegra_credentials
    db.alegra_credentials.find_one = AsyncMock(
        return_value={"token": alegra_token} if alegra_token else None
    )

    return db


def _make_mock_client(db_obj=None, ping_ok=True):
    """Build a mock Motor client with optional ping failure."""
    client = MagicMock()
    if ping_ok:
        client.admin.command = AsyncMock(return_value={"ok": 1})
    else:
        client.admin.command = AsyncMock(side_effect=Exception("connection refused"))

    if db_obj is not None:
        # client["sismo"].list_collection_names() -> coll_names list
        client.__getitem__ = MagicMock(return_value=MagicMock(
            list_collection_names=AsyncMock(return_value=db_obj._coll_names)
        ))

    return client


# ── Test 1: smoke returns status="ok" when all checks pass ───────────────────

class TestSmokeAllOk(unittest.TestCase):
    """smoke_test() returns status='ok' when MongoDB, bus, indices, catalogo all pass."""

    def test_smoke_all_ok(self):
        db = _make_full_mock_db()
        coll_names = [f"col_{i}" for i in range(32)]

        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1})
        client.__getitem__ = MagicMock(return_value=MagicMock(
            list_collection_names=AsyncMock(return_value=coll_names)
        ))

        bus_mock = MagicMock()
        bus_mock.get_bus_health = AsyncMock(return_value={"status": "ok", "dlq_pending": 0})

        app_state = MagicMock()
        app_state.event_bus = bus_mock

        with patch("server.db", db), \
             patch("server.client", client), \
             patch("server.app") as mock_app, \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            mock_app.state = app_state
            from server import smoke_test
            result = _run(smoke_test())

        self.assertEqual(result["status"], "ok", f"alertas: {result.get('alertas')}")


# ── Test 2: smoke returns collections_count matching mocked collection list ────

class TestSmokeCollectionsCount(unittest.TestCase):
    """smoke_test() returns collections_count equal to the number of collections returned."""

    def test_smoke_collections_count(self):
        coll_names = [f"collection_{i}" for i in range(32)]
        db = _make_full_mock_db(coll_names=coll_names)

        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1})
        client.__getitem__ = MagicMock(return_value=MagicMock(
            list_collection_names=AsyncMock(return_value=coll_names)
        ))

        bus_mock = MagicMock()
        bus_mock.get_bus_health = AsyncMock(return_value={"status": "ok"})

        app_state = MagicMock()
        app_state.event_bus = bus_mock

        with patch("server.db", db), \
             patch("server.client", client), \
             patch("server.app") as mock_app, \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            mock_app.state = app_state
            from server import smoke_test
            result = _run(smoke_test())

        self.assertEqual(result["collections_count"], 32)


# ── Test 3: smoke returns bus_status from event bus health ────────────────────

class TestSmokeBusStatus(unittest.TestCase):
    """smoke_test() returns bus_status matching the value from bus.get_bus_health()."""

    def test_smoke_bus_status(self):
        db = _make_full_mock_db()
        coll_names = [f"col_{i}" for i in range(5)]

        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1})
        client.__getitem__ = MagicMock(return_value=MagicMock(
            list_collection_names=AsyncMock(return_value=coll_names)
        ))

        bus_mock = MagicMock()
        bus_mock.get_bus_health = AsyncMock(return_value={"status": "ok", "dlq_pending": 0})

        app_state = MagicMock()
        app_state.event_bus = bus_mock

        with patch("server.db", db), \
             patch("server.client", client), \
             patch("server.app") as mock_app, \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            mock_app.state = app_state
            from server import smoke_test
            result = _run(smoke_test())

        self.assertEqual(result["bus_status"], "ok")


# ── Test 4: smoke returns indices_ok=True when event_id index exists ──────────

class TestSmokeIndicesOk(unittest.TestCase):
    """smoke_test() returns indices_ok=True when roddos_events has event_id index."""

    def test_smoke_indices_ok(self):
        db = _make_full_mock_db(event_id_index=True)
        coll_names = [f"col_{i}" for i in range(5)]

        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1})
        client.__getitem__ = MagicMock(return_value=MagicMock(
            list_collection_names=AsyncMock(return_value=coll_names)
        ))

        bus_mock = MagicMock()
        bus_mock.get_bus_health = AsyncMock(return_value={"status": "ok"})

        app_state = MagicMock()
        app_state.event_bus = bus_mock

        with patch("server.db", db), \
             patch("server.client", client), \
             patch("server.app") as mock_app, \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            mock_app.state = app_state
            from server import smoke_test
            result = _run(smoke_test())

        self.assertTrue(result["indices_ok"])


# ── Test 5: smoke returns catalogo_present=True when catalogo_planes has docs ─

class TestSmokeCatalogoPresentTrue(unittest.TestCase):
    """smoke_test() returns catalogo_present=True when catalogo_planes count > 0."""

    def test_smoke_catalogo_present(self):
        db = _make_full_mock_db(catalogo_count=5)
        coll_names = [f"col_{i}" for i in range(5)]

        client = MagicMock()
        client.admin.command = AsyncMock(return_value={"ok": 1})
        client.__getitem__ = MagicMock(return_value=MagicMock(
            list_collection_names=AsyncMock(return_value=coll_names)
        ))

        bus_mock = MagicMock()
        bus_mock.get_bus_health = AsyncMock(return_value={"status": "ok"})

        app_state = MagicMock()
        app_state.event_bus = bus_mock

        with patch("server.db", db), \
             patch("server.client", client), \
             patch("server.app") as mock_app, \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            mock_app.state = app_state
            from server import smoke_test
            result = _run(smoke_test())

        self.assertTrue(result["catalogo_present"])


# ── Test 6: smoke returns status="critico" when MongoDB ping fails ─────────────

class TestSmokeCriticoDbDown(unittest.TestCase):
    """smoke_test() returns status='critico' when client.admin.command('ping') raises."""

    def test_smoke_critico_when_db_down(self):
        db = _make_full_mock_db()

        client = MagicMock()
        client.admin.command = AsyncMock(side_effect=Exception("connection refused"))

        bus_mock = MagicMock()
        bus_mock.get_bus_health = AsyncMock(return_value={"status": "ok"})

        app_state = MagicMock()
        app_state.event_bus = bus_mock

        with patch("server.db", db), \
             patch("server.client", client), \
             patch("server.app") as mock_app, \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            mock_app.state = app_state
            from server import smoke_test
            result = _run(smoke_test())

        self.assertEqual(result["status"], "critico")


if __name__ == "__main__":
    unittest.main()
