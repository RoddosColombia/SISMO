"""Tests for agent write permissions and event models.

Covers:
- RoddosEvent construction (valid, invalid type, missing fields)
- DLQEvent standalone construction
- EVENT_TYPES_LIST catalog count
- validate_write_permission() allowed and denied cases
- validate_alegra_permission() denied case
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pydantic import ValidationError
from event_models import RoddosEvent, DLQEvent, EVENT_TYPES_LIST
from permissions import (
    WRITE_PERMISSIONS,
    validate_write_permission,
    validate_alegra_permission,
)


# --- Event Model Tests ---

def test_roddos_event_valid():
    """RoddosEvent with valid fields constructs successfully."""
    e = RoddosEvent(
        event_type="pago.cuota.registrado",
        source_agent="contador",
        actor="andres@roddos.co",
        target_entity="LB-001",
    )
    assert len(e.event_id) == 36  # UUID format
    assert e.estado == "processed"
    assert e.version == 1
    assert e.alegra_synced is False
    assert e.event_type == "pago.cuota.registrado"


def test_roddos_event_invalid_type():
    """RoddosEvent rejects event_type not in EVENT_TYPES."""
    with pytest.raises(ValidationError):
        RoddosEvent(
            event_type="tipo.invalido.no.existe",
            source_agent="contador",
            actor="test@test.com",
            target_entity="X",
        )


def test_roddos_event_missing_fields():
    """RoddosEvent with no args raises ValidationError for required fields."""
    with pytest.raises(ValidationError) as exc_info:
        RoddosEvent()
    errors = exc_info.value.errors()
    missing_fields = {e["loc"][0] for e in errors}
    assert "event_type" in missing_fields
    assert "source_agent" in missing_fields
    assert "actor" in missing_fields
    assert "target_entity" in missing_fields


def test_dlq_event_standalone():
    """DLQEvent is standalone (not subclass of RoddosEvent) with retry defaults."""
    d = DLQEvent(
        event_id="evt-123",
        event_type="factura.venta.creada",
        timestamp_utc="2026-01-01T00:00:00+00:00",
        source_agent="contador",
        error_message="Connection timeout",
    )
    assert not isinstance(d, RoddosEvent)  # Not inherited per D-03
    assert d.retry_count == 0
    assert d.next_retry is None
    assert d.error_message == "Connection timeout"


def test_event_types_catalog():
    """EVENT_TYPES_LIST has exactly 28 event types, all strings."""
    assert len(EVENT_TYPES_LIST) == 28
    assert all(isinstance(t, str) for t in EVENT_TYPES_LIST)
    # Verify key types from existing codebase are present
    assert "factura.venta.creada" in EVENT_TYPES_LIST
    assert "pago.cuota.registrado" in EVENT_TYPES_LIST
    assert "cliente.mora.detectada" in EVENT_TYPES_LIST
    assert "loanbook.activado" in EVENT_TYPES_LIST


# --- Permission Tests ---

def test_write_permission_allowed():
    """Allowed agent+collection combination does not raise."""
    validate_write_permission("contador", "loanbook")
    validate_write_permission("cfo", "portfolio_summaries")
    validate_write_permission("radar", "loanbook")
    validate_write_permission("loanbook", "inventario_motos")
    # If we get here, no PermissionError was raised


def test_write_permission_denied():
    """Denied agent+collection raises PermissionError."""
    with pytest.raises(PermissionError):
        validate_write_permission("radar", "portfolio_summaries")
    with pytest.raises(PermissionError):
        validate_write_permission("loanbook", "sismo_knowledge")
    with pytest.raises(PermissionError):
        validate_write_permission("unknown_agent", "loanbook")


def test_alegra_permission_denied():
    """Denied agent+endpoint raises PermissionError; RADAR has zero Alegra access."""
    with pytest.raises(PermissionError):
        validate_alegra_permission("radar", "invoices")
    with pytest.raises(PermissionError):
        validate_alegra_permission("radar", "journal-entries")
    # Verify allowed case does not raise
    validate_alegra_permission("contador", "journal-entries")
    validate_alegra_permission("loanbook", "invoices")
