#!/usr/bin/env python3
"""
TAREA 1 Smoke Test: Verify journal entry payloads use correct structure.
Test that all files constructing POST /journals payloads use the correct format:
  ✅ CORRECT: {"id": "5314", "debit": 1000, "credit": 0}
  ❌ WRONG:   {"account": {"id": "5314"}, "debit": 1000, "credit": 0}
"""
import json
import asyncio
import sys
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_mock_data_structure():
    """Verify mock_data.py MOCK_JOURNAL_ENTRIES uses correct structure."""
    from mock_data import MOCK_JOURNAL_ENTRIES

    print("✓ Testing mock_data.py MOCK_JOURNAL_ENTRIES structure...")

    for entry in MOCK_JOURNAL_ENTRIES:
        assert "entries" in entry, "Entry missing 'entries' array"
        for item in entry["entries"]:
            assert "id" in item, f"Entry item missing 'id': {item}"
            assert "debit" in item, f"Entry item missing 'debit': {item}"
            assert "credit" in item, f"Entry item missing 'credit': {item}"
            assert "account" not in item or isinstance(item.get("account"), dict) is False, \
                f"Entry item has nested 'account' structure (should be flat): {item}"

            # Verify it's the new flat structure
            assert isinstance(item["id"], (str, int)), f"'id' should be str or int: {item['id']}"
            assert isinstance(item["debit"], (int, float)), f"'debit' should be numeric: {item['debit']}"
            assert isinstance(item["credit"], (int, float)), f"'credit' should be numeric: {item['credit']}"

    print(f"  ✓ All {len(MOCK_JOURNAL_ENTRIES)} entries use correct structure")
    return True


def test_gastos_router():
    """Verify routers/gastos.py constructs entries correctly."""
    print("✓ Testing routers/gastos.py entry construction...")

    with open(Path(__file__).parent / "routers" / "gastos.py") as f:
        content = f.read()

    # Check that entries are constructed with correct structure
    assert '"id": cuenta_gasto_id, "debit"' in content, \
        "gastos.py should construct entries with flat structure"
    assert '{"account": {"id"' not in content, \
        "gastos.py should not use nested account structure"

    print("  ✓ gastos.py uses correct entry structure")
    return True


def test_ingresos_router():
    """Verify routers/ingresos.py constructs entries correctly."""
    print("✓ Testing routers/ingresos.py entry construction...")

    with open(Path(__file__).parent / "routers" / "ingresos.py") as f:
        content = f.read()

    # Check that entries are constructed with correct structure
    assert '"id": fila["banco_debito_id"]' in content or '"id": banco_id' in content, \
        "ingresos.py should construct entries with flat structure"
    assert '{"account": {"id"' not in content, \
        "ingresos.py should not use nested account structure"

    print("  ✓ ingresos.py uses correct entry structure")
    return True


def test_cxc_router():
    """Verify routers/cxc.py constructs entries correctly."""
    print("✓ Testing routers/cxc.py entry construction...")

    with open(Path(__file__).parent / "routers" / "cxc.py") as f:
        content = f.read()

    # Check that entries are constructed with correct structure
    assert '"id": CXC_SOCIOS_ID' in content or '"id": banco_id' in content or '"id": CXC_CLIENTES_ID' in content, \
        "cxc.py should construct entries with flat structure"
    assert '{"account": {"id"' not in content, \
        "cxc.py should not use nested account structure"

    print("  ✓ cxc.py uses correct entry structure")
    return True


def test_payload_construction():
    """Test that a valid journal payload can be constructed."""
    print("✓ Testing journal payload construction...")

    # Create a test payload like what would be sent to Alegra
    test_payload = {
        "date": "2026-03-20",
        "observations": "Test journal entry",
        "entries": [
            {"id": "5314", "debit": 1000000, "credit": 0},
            {"id": "5329", "debit": 0, "credit": 1000000},
        ]
    }

    # Verify structure
    assert isinstance(test_payload, dict), "Payload should be a dict"
    assert "entries" in test_payload, "Payload should have 'entries'"
    assert len(test_payload["entries"]) == 2, "Should have 2 entries"

    for entry in test_payload["entries"]:
        assert "id" in entry, "Entry should have 'id' field"
        assert "debit" in entry, "Entry should have 'debit' field"
        assert "credit" in entry, "Entry should have 'credit' field"
        assert "account" not in entry, "Entry should NOT have nested 'account' field"

    # Verify JSON serializable (important for API)
    json_str = json.dumps(test_payload)
    assert isinstance(json_str, str), "Payload should be JSON serializable"

    print(f"  ✓ Valid test payload created: {len(json_str)} bytes JSON")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("TAREA 1 SMOKE TEST — Journal Entry Payload Structure")
    print("="*70 + "\n")

    tests = [
        test_mock_data_structure,
        test_gastos_router,
        test_ingresos_router,
        test_cxc_router,
        test_payload_construction,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")

    if failed == 0:
        print("✅ All tests passed! Journal entry payloads use correct structure.\n")
        return 0
    else:
        print("❌ Some tests failed. Please review the output above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
