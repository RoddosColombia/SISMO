"""
test_fase0_proteccion.py — Fase 0: protección de facturas + corrección de permissions.py

T1:  validate_alegra_permission("contador", "journal-entries") → PermissionError
T2:  validate_alegra_permission("cfo", "invoices")             → PermissionError
T3:  validate_alegra_permission("cfo", "payments")             → PermissionError
T4:  validate_delete_protection("DELETE", "invoices")          → PermissionError
T5:  validate_delete_protection("DELETE", "bills")             → PermissionError
T6:  validate_delete_protection("GET",    "invoices")          → no error
T7:  validate_delete_protection("POST",   "invoices")          → no error
T8:  validate_delete_protection("DELETE", "journals")          → no error
T9:  validate_alegra_permission("contador", "journals")        → no error
T10: validate_alegra_permission("loanbook", "invoices")        → no error
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from permissions import validate_alegra_permission, validate_delete_protection


# ── T1-T3: endpoints bloqueados por agente ────────────────────────────────────

def test_t1_contador_journal_entries_bloqueado():
    with pytest.raises(PermissionError):
        validate_alegra_permission("contador", "journal-entries")


def test_t2_cfo_invoices_bloqueado():
    with pytest.raises(PermissionError):
        validate_alegra_permission("cfo", "invoices")


def test_t3_cfo_payments_bloqueado():
    with pytest.raises(PermissionError):
        validate_alegra_permission("cfo", "payments")


# ── T4-T8: validate_delete_protection ────────────────────────────────────────

def test_t4_delete_invoices_lanza_error():
    with pytest.raises(PermissionError):
        validate_delete_protection("DELETE", "invoices")


def test_t5_delete_bills_lanza_error():
    with pytest.raises(PermissionError):
        validate_delete_protection("DELETE", "bills")


def test_t6_get_invoices_no_error():
    validate_delete_protection("GET", "invoices")  # no debe lanzar


def test_t7_post_invoices_no_error():
    validate_delete_protection("POST", "invoices")  # no debe lanzar


def test_t8_delete_journals_no_error():
    validate_delete_protection("DELETE", "journals")  # journals sí se pueden borrar


# ── T9-T10: permisos legítimos siguen funcionando ─────────────────────────────

def test_t9_contador_journals_permitido():
    validate_alegra_permission("contador", "journals")  # journals reemplaza journal-entries


def test_t10_loanbook_invoices_permitido():
    validate_alegra_permission("loanbook", "invoices")  # loanbook puede crear facturas
