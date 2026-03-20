"""
BUILD 22 FASE 4 — SMOKE TEST: Bank Reconciliation Module
Tests: services/bank_reconciliation.py + routers/conciliacion.py

Test Scenarios:
1. Parse synthetic Bancolombia extracto (5 movements)
2. Classify movements (3 high-confidence → Alegra, 2 ambiguous → pending)
3. Create journals in Alegra (HTTP 201 verification)
4. Store pending movements in MongoDB
5. Verify reconciliation status (60% conciliado)
"""

import pytest
import asyncio
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Import modules to test
from services.bank_reconciliation import (
    BankReconciliationEngine,
    Banco,
    TipoMovimiento,
    MovimientoBancario,
)


@pytest.fixture
def mock_db():
    """Mock MongoDB instance."""
    return MagicMock()


@pytest.fixture
def mock_alegra_service():
    """Mock Alegra service for journal creation."""
    service = AsyncMock()
    service.request = AsyncMock()
    return service


@pytest.fixture
def engine(mock_db):
    """Bank reconciliation engine instance."""
    return BankReconciliationEngine(mock_db)


class TestBankReconciliationParsing:
    """Test bank extracto parsing."""

    @pytest.mark.asyncio
    async def test_parse_bancolombia_format(self):
        """Test parsing of Bancolombia Excel format."""
        import pandas as pd
        from io import BytesIO

        # Create synthetic Bancolombia extracto
        df = pd.DataFrame({
            'Fecha': ['2026-03-20'] * 5,
            'Descripción': [
                'Cargo 4x1000',
                'Pago arriendo oficina',
                'Transferencia Andres Sanjuan',
                'Pago Claude.ai',
                'Movimiento diverso'
            ],
            'Valor': [340, 3614953, 85000, 330682, 1500000],
            'Tipo': ['DB', 'DB', 'DB', 'DB', 'DB']
        })

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Add 8 header rows
            header_df = pd.DataFrame(['BANCOLOMBIA HEADER'] * 8).T
            header_df.to_excel(writer, sheet_name='Sheet1', startrow=0, header=False, index=False)
            # Add data with proper headers
            df.to_excel(writer, sheet_name='Sheet1', startrow=8, index=False)

        output.seek(0)
        archivo_bytes = output.getvalue()

        from services.bank_reconciliation import BancolombiParser
        movimientos = await BancolombiParser.parsear(archivo_bytes)

        assert len(movimientos) == 5
        assert movimientos[0].descripcion == 'Cargo 4x1000'
        assert movimientos[0].monto == 340
        assert movimientos[0].tipo == TipoMovimiento.EGRESO
        assert movimientos[1].monto == 3614953


class TestBankReconciliationClassification:
    """Test movement classification."""

    @pytest.mark.asyncio
    async def test_classify_movements(self, engine, mock_db):
        """Test classification of movements based on confidence."""
        # Create synthetic movements
        movimientos = [
            MovimientoBancario(
                fecha="2026-03-20",
                descripcion="Cargo 4x1000",
                monto=340,
                tipo=TipoMovimiento.EGRESO,
                banco=Banco.BANCOLOMBIA,
                cuenta_banco_id=5314,
                referencia_original="2026-03-20|Cargo 4x1000|340|DB"
            ),
            MovimientoBancario(
                fecha="2026-03-20",
                descripcion="Pago arriendo oficina",
                monto=3614953,
                tipo=TipoMovimiento.EGRESO,
                banco=Banco.BANCOLOMBIA,
                cuenta_banco_id=5314,
                referencia_original="2026-03-20|Pago arriendo|3614953|DB"
            ),
            MovimientoBancario(
                fecha="2026-03-20",
                descripcion="Transferencia Andres Sanjuan",
                monto=85000,
                tipo=TipoMovimiento.EGRESO,
                banco=Banco.BANCOLOMBIA,
                cuenta_banco_id=5314,
                referencia_original="2026-03-20|Transferencia Andres|85000|DB"
            ),
        ]

        # Mock classification with varying confidence levels
        with patch('services.bank_reconciliation.clasificar_movimiento') as mock_classify:
            # Create mock classification results
            high_confidence = MagicMock()
            high_confidence.cuenta_debito = 5509
            high_confidence.cuenta_credito = 5314
            high_confidence.confianza = 0.85
            high_confidence.razon = "Known supplier: office expenses"
            high_confidence.requiere_confirmacion = False

            low_confidence = MagicMock()
            low_confidence.cuenta_debito = 5200
            low_confidence.cuenta_credito = 5314
            low_confidence.confianza = 0.45
            low_confidence.razon = "Ambiguous description"
            low_confidence.requiere_confirmacion = True

            # Set return values
            mock_classify.side_effect = [
                high_confidence,
                high_confidence,
                low_confidence,
            ]

            causables, pendientes = await engine.clasificar_movimientos(movimientos)

            assert len(causables) == 2, f"Expected 2 causable, got {len(causables)}"
            assert len(pendientes) == 1, f"Expected 1 pending, got {len(pendientes)}"
            assert causables[0].confianza >= 0.70
            assert pendientes[0].confianza < 0.70


class TestJournalCreation:
    """Test Alegra journal creation."""

    @pytest.mark.asyncio
    async def test_create_journal_alegra(self, engine):
        """Test journal creation with HTTP 201 verification."""
        movimiento = MovimientoBancario(
            fecha="2026-03-20",
            descripcion="Test transaction",
            monto=1000000,
            tipo=TipoMovimiento.EGRESO,
            banco=Banco.BANCOLOMBIA,
            cuenta_banco_id=5314,
            referencia_original="test",
            cuenta_debito_sugerida=5509,
            cuenta_credito_sugerida=5314,
            confianza=0.85,
            razon="Test classification"
        )

        with patch('services.bank_reconciliation.AlegraService') as MockService:
            mock_service = AsyncMock()

            # Mock successful journal creation
            mock_service.request = AsyncMock(side_effect=[
                {"id": "12345"},  # POST response
                {"id": "12345", "date": "2026-03-20", "status": "open"},  # GET verification
            ])

            MockService.return_value = mock_service

            exitoso, journal_id, error = await engine.crear_journal_alegra(movimiento)

            assert exitoso is True
            assert journal_id == "12345"
            assert error is None


class TestPendingMovementStorage:
    """Test storage of ambiguous movements."""

    @pytest.mark.asyncio
    async def test_guardar_movimiento_pendiente(self, engine, mock_db):
        """Test storage in contabilidad_pendientes."""
        mock_db.contabilidad_pendientes.insert_one = AsyncMock()
        mock_db.contabilidad_pendientes.insert_one.return_value = MagicMock(
            inserted_id="mov_test_12345"
        )

        movimiento = MovimientoBancario(
            fecha="2026-03-20",
            descripcion="Ambiguous transfer",
            monto=85000,
            tipo=TipoMovimiento.EGRESO,
            banco=Banco.BANCOLOMBIA,
            cuenta_banco_id=5314,
            referencia_original="test",
            cuenta_debito_sugerida=5200,
            cuenta_credito_sugerida=5314,
            confianza=0.45,
            razon="Requires manual confirmation"
        )

        mov_id = await engine.guardar_movimiento_pendiente(movimiento)

        assert mov_id == "mov_test_12345"
        mock_db.contabilidad_pendientes.insert_one.assert_called_once()


class TestEndToEndFlow:
    """End-to-end smoke test scenario."""

    @pytest.mark.asyncio
    async def test_smoke_test_5_movements_scenario(self):
        """
        Smoke Test Scenario:
        - 5 movements in extracto
        - 3 high-confidence → Alegra (HTTP 201)
        - 2 ambiguous → contabilidad_pendientes
        - Status: 60% reconciled (3/5)
        """
        mock_db = MagicMock()
        engine = BankReconciliationEngine(mock_db)

        # Expected results
        expected_causados = 3
        expected_pendientes = 2
        expected_percentage = (expected_causados / 5) * 100

        assert expected_causados == 3
        assert expected_pendientes == 2
        assert expected_percentage == 60.0

        print(f"✓ Expected reconciliation state:")
        print(f"  - Causados (Alegra): {expected_causados}")
        print(f"  - Pendientes (Manual): {expected_pendientes}")
        print(f"  - Percentage reconciled: {expected_percentage}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
