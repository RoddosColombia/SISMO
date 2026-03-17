"""
test_build21_accounting_engine.py — Tests unitarios para BUILD 21 Módulos 1 & 2.

Verifica:
- Módulo 1: Lógica Contable (clasificación, retenciones, diagnóstico)
- Módulo 2: AlegraService enhanced (error translation, verify, retry)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.accounting_engine import (
    clasificar_transaccion,
    calcular_retenciones,
    diagnosticar_asiento,
    formatear_retenciones_para_prompt,
    formatear_diagnostico_para_prompt,
    UMBRAL_SERVICIOS_RETEFUENTE,
    UMBRAL_COMPRAS_RETEFUENTE,
    UMBRAL_HONORARIOS,
)


# ── MODULE 1: Tests de clasificación automática ───────────────────────────────

class TestClasificacionTransaccion:
    def test_arriendo_clasificado(self):
        r = clasificar_transaccion("Arriendo local comercial Calle 127", monto=3_000_000)
        assert r["categoria"] == "Operaciones"
        assert r["subcategoria"] == "Arriendo"
        assert r["alegra_id"] == 5480
        assert r["tipo_retencion"] == "arrendamiento_3.5"
        assert r["confianza"] > 0

    def test_honorarios_pn(self):
        r = clasificar_transaccion("Honorarios profesionales asesoría contable", tipo_proveedor="PN")
        assert r["categoria"] == "Personal"
        assert r["subcategoria"] == "Honorarios"
        assert r["tipo_retencion"] == "honorarios_pn"

    def test_honorarios_pj(self):
        r = clasificar_transaccion("Honorarios consultoría legal", tipo_proveedor="PJ")
        assert r["tipo_retencion"] == "honorarios_pj"

    def test_servicios_publicos(self):
        r = clasificar_transaccion("Factura energía eléctrica EPM", monto=450_000)
        assert r["categoria"] == "Operaciones"
        assert r["subcategoria"] == "Servicios_Publicos"
        assert r["tipo_retencion"] == "servicios_4"

    def test_transporte(self):
        r = clasificar_transaccion("Servicio de transporte domicilio")
        assert r["categoria"] == "Operaciones"
        assert r["subcategoria"] == "Transporte"

    def test_software_tecnologia(self):
        r = clasificar_transaccion("Suscripción software Alegra mensual")
        assert r["categoria"] == "Operaciones"
        assert r["subcategoria"] == "Mantenimiento"
        assert r["aplica_reteica"] is True

    def test_salario_sin_retencion(self):
        r = clasificar_transaccion("Pago de nómina empleados enero")
        assert r["categoria"] == "Personal"
        assert r["subcategoria"] == "Salarios"
        assert r["tipo_retencion"] == "ninguna"

    def test_sin_match_fallback(self):
        r = clasificar_transaccion("XYZABC 99999 zqwfp no clasif")
        assert r["confianza"] == 0.0
        assert r["categoria"] == "Otros"
        assert r["subcategoria"] == "Varios"


# ── MODULE 1: Tests de cálculo de retenciones ─────────────────────────────────

class TestCalcularRetenciones:
    def test_arriendo_retefuente_35(self):
        r = calcular_retenciones("PJ", "arriendo", 3_000_000)
        assert r["retefuente_pct"] == 0.035
        assert r["retefuente_valor"] == 105_000
        assert r["neto_a_pagar"] == 2_895_000

    def test_honorarios_pn_10pct(self):
        r = calcular_retenciones("PN", "honorarios", 1_000_000)
        assert r["retefuente_pct"] == 0.10
        assert r["retefuente_valor"] == 100_000
        assert r["neto_a_pagar"] == 900_000

    def test_honorarios_pj_11pct(self):
        r = calcular_retenciones("PJ", "honorarios", 1_000_000)
        assert r["retefuente_pct"] == 0.11
        assert r["retefuente_valor"] == 110_000
        assert r["neto_a_pagar"] == 890_000

    def test_servicios_bajo_umbral_sin_retef(self):
        # Por debajo del umbral $199.196
        r = calcular_retenciones("PJ", "servicios", 100_000)
        assert r["retefuente_valor"] == 0

    def test_servicios_sobre_umbral_4pct(self):
        # $500.000 > $199.196 → aplica ReteFuente 4%
        r = calcular_retenciones("PJ", "servicios", 500_000)
        assert r["retefuente_pct"] == 0.04
        assert r["retefuente_valor"] == 20_000

    def test_autoretenedor_sin_retefuente(self):
        r = calcular_retenciones("PJ", "honorarios", 2_000_000, es_autoretenedor=True)
        assert r["retefuente_valor"] == 0
        assert len(r["advertencias"]) > 0
        assert "autoretenedor" in r["advertencias"][0].lower()

    def test_con_iva(self):
        r = calcular_retenciones("PJ", "servicios", 1_000_000, aplica_iva=True)
        assert r["iva_valor"] == 190_000

    def test_reteica_bogota(self):
        r = calcular_retenciones("PJ", "honorarios", 1_000_000, aplica_reteica=True, ciudad="Bogota")
        assert r["reteica_valor"] > 0

    def test_reteica_no_aplica_fuera_bogota(self):
        r = calcular_retenciones("PJ", "honorarios", 1_000_000, aplica_reteica=True, ciudad="Medellín")
        assert r["reteica_valor"] == 0

    def test_formato_prompt(self):
        r = calcular_retenciones("PJ", "arriendo", 3_000_000)
        texto = formatear_retenciones_para_prompt(r)
        assert "BASE:" in texto
        assert "ReteFuente" in texto
        assert "NETO A PAGAR:" in texto


# ── MODULE 1: Tests de diagnóstico de asientos ───────────────────────────────

class TestDiagnosticarAsiento:
    def test_asiento_valido(self):
        entries = [
            {"id": 5480, "debit": 3_000_000, "credit": 0},
            {"id": 5386, "debit": 0, "credit": 105_000},
            {"id": 5376, "debit": 0, "credit": 2_895_000},
        ]
        d = diagnosticar_asiento(entries, "2026-01-31")
        assert d["valido"] is True
        assert len(d["errores"]) == 0
        assert d["total_debito"] == 3_000_000
        assert d["total_credito"] == 3_000_000

    def test_asiento_descuadrado(self):
        entries = [
            {"id": 5480, "debit": 3_000_000, "credit": 0},
            {"id": 5376, "debit": 0, "credit": 2_000_000},
        ]
        d = diagnosticar_asiento(entries, "2026-01-31")
        assert d["valido"] is False
        assert any("descuadrado" in e.lower() for e in d["errores"])

    def test_asiento_menos_dos_entradas(self):
        entries = [{"id": 5480, "debit": 3_000_000, "credit": 0}]
        d = diagnosticar_asiento(entries)
        assert d["valido"] is False
        assert any("entradas" in e.lower() or "al menos" in e.lower() for e in d["errores"])

    def test_entrada_sin_id(self):
        entries = [
            {"debit": 1_000_000, "credit": 0},
            {"id": 5376, "debit": 0, "credit": 1_000_000},
        ]
        d = diagnosticar_asiento(entries)
        assert d["valido"] is False
        assert any("falta el id" in e.lower() for e in d["errores"])

    def test_montos_cero(self):
        entries = [
            {"id": 5480, "debit": 0, "credit": 0},
            {"id": 5376, "debit": 0, "credit": 0},
        ]
        d = diagnosticar_asiento(entries)
        assert d["valido"] is False

    def test_monto_negativo(self):
        entries = [
            {"id": 5480, "debit": -100_000, "credit": 0},
            {"id": 5376, "debit": 0, "credit": 100_000},
        ]
        d = diagnosticar_asiento(entries)
        assert d["valido"] is False
        assert any("negativos" in e.lower() for e in d["errores"])

    def test_id_no_numerico(self):
        entries = [
            {"id": "abc", "debit": 1_000_000, "credit": 0},
            {"id": 5376, "debit": 0, "credit": 1_000_000},
        ]
        d = diagnosticar_asiento(entries)
        assert d["valido"] is False

    def test_formato_prompt(self):
        entries = [
            {"id": 5480, "debit": 3_000_000, "credit": 0},
            {"id": 5376, "debit": 0, "credit": 3_000_000},
        ]
        d = diagnosticar_asiento(entries)
        texto = formatear_diagnostico_para_prompt(d)
        assert "✅" in texto or "Asiento válido" in texto


# ── MODULE 2: Tests de AlegraService enhanced ────────────────────────────────

class TestAlegraServiceEnhanced:
    """Tests para los nuevos métodos de AlegraService (BUILD 21)."""

    def setup_method(self):
        from unittest.mock import MagicMock
        self.db_mock = MagicMock()
        from alegra_service import AlegraService
        self.service = AlegraService(self.db_mock)

    def test_translate_error_401(self):
        msg = self.service._translate_error_to_spanish(401, {}, "journals", "POST")
        assert "Credenciales" in msg
        assert "Alegra" in msg

    def test_translate_error_400_journals_balance(self):
        msg = self.service._translate_error_to_spanish(
            400, {"message": "debit and credit must be equal"}, "journals", "POST"
        )
        assert "balance" in msg.lower() or "asiento" in msg.lower()

    def test_translate_error_400_journals_id(self):
        msg = self.service._translate_error_to_spanish(
            400, {"message": "invalid account id"}, "journals", "POST"
        )
        assert "id" in msg.lower() or "cuenta" in msg.lower()

    def test_translate_error_400_bills_item(self):
        msg = self.service._translate_error_to_spanish(
            400, {"message": "item not found"}, "bills", "POST"
        )
        assert "catálogo" in msg.lower() or "item" in msg.lower()

    def test_translate_error_403_get_silencioso(self):
        msg = self.service._translate_error_to_spanish(403, {}, "categories", "GET")
        assert msg == ""  # GET 403 es silencioso

    def test_translate_error_403_post_con_mensaje(self):
        msg = self.service._translate_error_to_spanish(
            403, {"message": "No tiene permisos"}, "journals", "POST"
        )
        assert "permisos" in msg.lower() or "Permisos" in msg

    def test_translate_error_409_duplicado(self):
        msg = self.service._translate_error_to_spanish(409, {}, "journals", "POST")
        assert "duplicado" in msg.lower() or "conflicto" in msg.lower()

    def test_translate_error_429(self):
        msg = self.service._translate_error_to_spanish(429, {}, "journals", "POST")
        assert "30" in msg or "espera" in msg.lower()

    def test_translate_error_503(self):
        msg = self.service._translate_error_to_spanish(503, {}, "journals", "POST")
        assert "temporalmente" in msg.lower() or "disponible" in msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
