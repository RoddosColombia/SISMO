"""Tests for EventBusService — TST-01 (11 tests).

Covers:
- emit() persists with estado='processed'
- emit() is idempotent (duplicate event_id silently rejected)
- emit() raises PermissionError for invalid source_agent
- emit() persists all 13 RoddosEvent fields correctly
- DLQ receives event when MongoDB insert fails
- DLQ event has retry_count=0 and next_retry set
- retry_dlq() moves DLQ event back to roddos_events on success
- get_bus_health() returns required keys (dlq_pending, events_last_hour, status)
- get_bus_health() returns status='healthy' when DLQ is empty
- get_bus_health() returns status='degraded' when DLQ has pending items
- No Python file in backend/ imports from old event_bus module or calls emit_state_change
"""
import asyncio
import os
import sys
import subprocess
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from event_models import RoddosEvent, DLQEvent
from services.event_bus_service import EventBusService


# ── helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run a coroutine synchronously using asyncio.run()."""
    return asyncio.run(coro)


def _make_event(**overrides) -> RoddosEvent:
    """Build a valid RoddosEvent with sensible defaults for testing."""
    defaults = {
        "source_agent": "contador",   # Valid agent in WRITE_PERMISSIONS
        "event_type": "pago.cuota.registrado",
        "actor": "test@roddos.co",
        "target_entity": "LB-TEST-001",
        "payload": {"test": True},
    }
    defaults.update(overrides)
    return RoddosEvent(**defaults)


def _make_mock_db():
    """Create a mock Motor database with async collection methods."""
    db = MagicMock()

    # roddos_events collection
    db.roddos_events.insert_one = AsyncMock(return_value=MagicMock())
    db.roddos_events.delete_one = AsyncMock(return_value=MagicMock())
    db.roddos_events.find_one = AsyncMock(return_value=None)
    db.roddos_events.count_documents = AsyncMock(return_value=0)

    # roddos_events_dlq collection
    db.roddos_events_dlq.insert_one = AsyncMock(return_value=MagicMock())
    db.roddos_events_dlq.delete_one = AsyncMock(return_value=MagicMock())
    db.roddos_events_dlq.find_one = AsyncMock(return_value=None)
    db.roddos_events_dlq.count_documents = AsyncMock(return_value=0)
    db.roddos_events_dlq.update_one = AsyncMock(return_value=MagicMock())
    db.roddos_events_dlq.find = MagicMock()

    return db


# ── Test 1: emit persists event with estado='processed' ──────────────────────

class TestEmitPersistsProcessed(unittest.TestCase):
    """emit() stores event with estado='processed' in roddos_events."""

    def test_emit_persists_with_estado_processed(self):
        db = _make_mock_db()
        bus = EventBusService(db)
        event = _make_event()

        _run(bus.emit(event))

        # insert_one should have been called once
        db.roddos_events.insert_one.assert_called_once()
        # Extract the document passed to insert_one
        call_args = db.roddos_events.insert_one.call_args
        doc = call_args[0][0]
        self.assertEqual(doc["estado"], "processed")


# ── Test 2: emit is idempotent — duplicate event_id silently rejected ─────────

class TestEmitIdempotent(unittest.TestCase):
    """emit() with same event_id twice does NOT raise and only inserts once."""

    def test_emit_idempotent_duplicate_event_id(self):
        from pymongo.errors import DuplicateKeyError

        db = _make_mock_db()
        # Second call raises DuplicateKeyError
        db.roddos_events.insert_one = AsyncMock(
            side_effect=[MagicMock(), DuplicateKeyError("duplicate")]
        )
        bus = EventBusService(db)
        event = _make_event()

        # First emit — should succeed
        _run(bus.emit(event))
        # Second emit with same event_id — should NOT raise
        try:
            _run(bus.emit(event))
        except Exception as e:
            self.fail(f"emit() raised unexpectedly on duplicate: {e}")

        # insert_one called exactly twice (first insert + duplicate attempt)
        self.assertEqual(db.roddos_events.insert_one.call_count, 2)
        # DLQ should NOT have been touched
        db.roddos_events_dlq.insert_one.assert_not_called()


# ── Test 3: emit raises PermissionError for invalid source_agent ──────────────

class TestEmitPermissionEnforcement(unittest.TestCase):
    """emit() raises PermissionError immediately for unregistered agent."""

    def test_emit_invalid_agent_raises_permission_error(self):
        db = _make_mock_db()
        bus = EventBusService(db)
        event = _make_event(source_agent="agente_desconocido")

        with self.assertRaises(PermissionError):
            _run(bus.emit(event))

        # insert_one must NOT have been called — permission check is pre-insert
        db.roddos_events.insert_one.assert_not_called()
        # PermissionError must NOT go to DLQ (D-06)
        db.roddos_events_dlq.insert_one.assert_not_called()


# ── Test 4: emit persists all 13 RoddosEvent fields correctly ─────────────────

class TestEmitPersistsAllFields(unittest.TestCase):
    """emit() persists all 13 canonical RoddosEvent fields to roddos_events."""

    def test_emit_persists_all_13_fields(self):
        db = _make_mock_db()
        bus = EventBusService(db)
        event = _make_event(
            modules_to_notify=["cartera", "dashboard"],
            alegra_synced=False,
            version=1,
        )

        _run(bus.emit(event))

        doc = db.roddos_events.insert_one.call_args[0][0]

        # All 13 mandatory fields must be present
        expected_fields = {
            "event_id", "event_type", "timestamp_utc",
            "source_agent", "actor", "target_entity",
            "payload", "modules_to_notify", "correlation_id",
            "version", "alegra_synced", "estado", "label",
        }
        for field in expected_fields:
            self.assertIn(field, doc, f"Field '{field}' missing from persisted document")

        # Spot-check key values
        self.assertEqual(doc["source_agent"], "contador")
        self.assertEqual(doc["event_type"], "pago.cuota.registrado")
        self.assertEqual(doc["estado"], "processed")
        self.assertEqual(doc["target_entity"], "LB-TEST-001")


# ── Test 5: DLQ receives event when MongoDB insert fails ──────────────────────

class TestDLQOnMongoFailure(unittest.TestCase):
    """When MongoDB insert_one raises a non-Duplicate error, event goes to DLQ."""

    def test_dlq_receives_event_on_mongo_failure(self):
        db = _make_mock_db()
        db.roddos_events.insert_one = AsyncMock(
            side_effect=Exception("MongoDB connection timeout")
        )
        bus = EventBusService(db)
        event = _make_event()

        # emit() must NOT raise — failure goes silently to DLQ
        try:
            _run(bus.emit(event))
        except Exception as e:
            self.fail(f"emit() raised to caller when it should have gone to DLQ: {e}")

        # DLQ must have received the event
        db.roddos_events_dlq.insert_one.assert_called_once()


# ── Test 6: DLQ event has retry_count=0 and next_retry set ───────────────────

class TestDLQMetadata(unittest.TestCase):
    """DLQ event created by _send_to_dlq has retry_count=0 and next_retry set."""

    def test_dlq_event_has_correct_retry_metadata(self):
        db = _make_mock_db()
        db.roddos_events.insert_one = AsyncMock(
            side_effect=Exception("Simulated network error")
        )
        bus = EventBusService(db)
        event = _make_event()

        _run(bus.emit(event))

        dlq_call_args = db.roddos_events_dlq.insert_one.call_args
        dlq_doc = dlq_call_args[0][0]

        self.assertEqual(dlq_doc["retry_count"], 0)
        self.assertIsNotNone(dlq_doc.get("next_retry"), "next_retry must be set")
        self.assertIn("T", dlq_doc["next_retry"], "next_retry must be ISO datetime")
        self.assertEqual(dlq_doc["event_id"], event.event_id)
        self.assertIn("error_message", dlq_doc)


# ── Test 7: retry_dlq moves event from DLQ to roddos_events on success ────────

class TestRetryDLQSuccess(unittest.TestCase):
    """retry_dlq() re-publishes a DLQ event to roddos_events and removes it from DLQ."""

    def test_retry_dlq_moves_event_on_success(self):
        from datetime import datetime, timezone, timedelta

        db = _make_mock_db()

        # Simulate a DLQ event that is ready for retry (next_retry in the past)
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        dlq_doc = {
            "event_id": "test-dlq-retry-001",
            "event_type": "pago.cuota.registrado",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_agent": "contador",
            "original_actor": "test@roddos.co",
            "target_entity": "LB-TEST-001",
            "payload": {"test": True},
            "retry_count": 0,
            "next_retry": past_time,
        }

        # Mock the async cursor returned by find()
        async def _async_gen():
            yield dlq_doc

        db.roddos_events_dlq.find = MagicMock(return_value=_async_gen())
        db.roddos_events.insert_one = AsyncMock(return_value=MagicMock())
        db.roddos_events_dlq.delete_one = AsyncMock(return_value=MagicMock())

        bus = EventBusService(db)
        result = _run(bus.retry_dlq())

        # Should return 1 successfully retried event
        self.assertEqual(result, 1)
        # insert_one to roddos_events must have been called
        db.roddos_events.insert_one.assert_called_once()
        # delete_one from DLQ must have been called to remove the entry
        db.roddos_events_dlq.delete_one.assert_called_once_with(
            {"event_id": "test-dlq-retry-001"}
        )


# ── Test 8: get_bus_health returns required keys ──────────────────────────────

class TestBusHealthKeys(unittest.TestCase):
    """get_bus_health() returns dict with keys: dlq_pending, events_last_hour, status."""

    def test_get_bus_health_returns_required_keys(self):
        db = _make_mock_db()
        db.roddos_events_dlq.count_documents = AsyncMock(return_value=0)
        db.roddos_events.count_documents = AsyncMock(return_value=5)
        bus = EventBusService(db)

        result = _run(bus.get_bus_health())

        self.assertIn("dlq_pending", result)
        self.assertIn("events_last_hour", result)
        self.assertIn("status", result)
        self.assertIsInstance(result["dlq_pending"], int)
        self.assertIsInstance(result["events_last_hour"], int)
        self.assertIsInstance(result["status"], str)


# ── Test 9: get_bus_health returns 'healthy' when DLQ is empty ───────────────

class TestBusHealthHealthy(unittest.TestCase):
    """get_bus_health() returns status='healthy' when DLQ pending count is 0."""

    def test_get_bus_health_healthy_when_dlq_empty(self):
        db = _make_mock_db()
        db.roddos_events_dlq.count_documents = AsyncMock(return_value=0)
        db.roddos_events.count_documents = AsyncMock(return_value=3)
        bus = EventBusService(db)

        result = _run(bus.get_bus_health())

        self.assertEqual(result["dlq_pending"], 0)
        self.assertEqual(result["status"], "healthy")


# ── Test 10: get_bus_health returns 'degraded' when DLQ has pending items ────

class TestBusHealthDegraded(unittest.TestCase):
    """get_bus_health() returns status='degraded' when DLQ has pending items (< 10)."""

    def test_get_bus_health_degraded_when_dlq_pending(self):
        db = _make_mock_db()
        # 3 pending DLQ items — degraded threshold (< 10)
        db.roddos_events_dlq.count_documents = AsyncMock(return_value=3)
        db.roddos_events.count_documents = AsyncMock(return_value=0)
        bus = EventBusService(db)

        result = _run(bus.get_bus_health())

        self.assertEqual(result["dlq_pending"], 3)
        self.assertEqual(result["status"], "degraded")


# ── Test 11: No old imports in codebase ───────────────────────────────────────

class TestNoOldImports(unittest.TestCase):
    """No Python file in backend/ imports from event_bus or calls emit_state_change."""

    def _scan_backend(self, pattern: str) -> list[str]:
        """Return list of (file:line) strings matching pattern in backend/ .py files."""
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        matches = []
        for root, dirs, files in os.walk(backend_dir):
            # Skip the tests directory itself (allowed to reference old patterns in comments)
            if "tests" in root.split(os.sep):
                continue
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, start=1):
                            # Skip comment lines and docstrings
                            stripped = line.strip()
                            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                                continue
                            if pattern in line:
                                matches.append(f"{filepath}:{lineno}: {line.rstrip()}")
                except OSError:
                    pass
        return matches

    def test_no_import_from_old_event_bus(self):
        """No file imports from the deleted event_bus module."""
        old_import_matches = self._scan_backend("from event_bus import")
        old_import_matches += self._scan_backend("from backend.event_bus import")
        self.assertEqual(
            old_import_matches,
            [],
            f"Found old event_bus imports:\n" + "\n".join(old_import_matches),
        )

    def test_no_emit_state_change_calls(self):
        """No file calls the removed emit_state_change() function."""
        matches = self._scan_backend("emit_state_change(")
        self.assertEqual(
            matches,
            [],
            f"Found emit_state_change() calls:\n" + "\n".join(matches),
        )


if __name__ == "__main__":
    unittest.main()
