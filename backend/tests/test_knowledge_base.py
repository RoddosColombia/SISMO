"""
test_knowledge_base.py — Tests para KnowledgeBaseService (RAG).

Patron de isolation: MagicMock para AsyncIOMotorCollection.
Lazy import de ai_chat para evitar 'anthropic not installed' en entornos CI.
"""
import sys
import types
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Stub de modulos opcionales que pueden no estar en CI ─────────────────────
_OPTIONAL_STUBS = [
    "anthropic", "qrcode", "cryptography", "pdfplumber",
    "motor", "motor.motor_asyncio",
]
for _mod in _OPTIONAL_STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_db(rules: list):
    """Crea un mock de db con sismo_knowledge que retorna las reglas dadas."""
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=rules)

    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_collection.update_one = AsyncMock(return_value=MagicMock(upserted_id="test_id"))

    mock_db = MagicMock()
    mock_db.sismo_knowledge = mock_collection
    return mock_db


# ── Task 1 Tests ──────────────────────────────────────────────────────────────

class TestGetContextForOperation(unittest.TestCase):

    def test_get_context_registrar_arriendo_returns_formatted_block(self):
        """get_context_for_operation con op conocida retorna bloque formateado."""
        from services.knowledge_base_service import get_context_for_operation

        rules = [
            {
                "rule_id": "retefuente_arriendo",
                "titulo": "ReteFuente arriendo",
                "contenido": "ReteFuente 3.5% para arrendamiento.",
                "tags": ["retefuente", "arrendamiento"],
            }
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_context_for_operation("registrar_arriendo", mock_db))

        self.assertIn("REGLAS APLICABLES", result)
        self.assertIn("ReteFuente arriendo", result)
        self.assertIn("3.5%", result)

    def test_get_context_crear_factura_moto_returns_vin_rules(self):
        """get_context_for_operation para factura moto retorna reglas con VIN."""
        from services.knowledge_base_service import get_context_for_operation

        rules = [
            {
                "rule_id": "vin_motor_factura",
                "titulo": "VIN y Motor obligatorios",
                "contenido": "VIN y motor OBLIGATORIOS en toda factura de moto.",
                "tags": ["VIN", "factura", "moto"],
            }
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_context_for_operation("crear_factura_moto", mock_db))

        self.assertIn("REGLAS APLICABLES", result)
        self.assertIn("VIN", result)

    def test_get_context_registrar_pago_cartera_returns_cartera_rules(self):
        """get_context_for_operation para pago de cartera retorna reglas cartera."""
        from services.knowledge_base_service import get_context_for_operation

        rules = [
            {
                "rule_id": "mora_diaria",
                "titulo": "Mora diaria",
                "contenido": "Mora $2.000/dia desde jueves post-vencimiento.",
                "tags": ["cartera", "mora"],
            }
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_context_for_operation("registrar_pago_cartera", mock_db))

        self.assertIn("REGLAS APLICABLES", result)
        self.assertIn("Mora", result)

    def test_get_context_registrar_nomina_returns_nomina_rules(self):
        """get_context_for_operation para nomina retorna reglas de nomina."""
        from services.knowledge_base_service import get_context_for_operation

        rules = [
            {
                "rule_id": "retefuente_nomina",
                "titulo": "ReteFuente nomina",
                "contenido": "Retenciones de nomina aplican segun tabla DIAN.",
                "tags": ["nomina", "retefuente"],
            }
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_context_for_operation("registrar_nomina", mock_db))

        self.assertIn("REGLAS APLICABLES", result)

    def test_get_context_unknown_operation_returns_empty(self):
        """get_context_for_operation con op desconocida retorna string vacio."""
        from services.knowledge_base_service import get_context_for_operation

        mock_db = _make_mock_db([])

        result = asyncio.run(get_context_for_operation("unknown_operation", mock_db))

        self.assertEqual(result, "")


class TestGetAllRulesByCategory(unittest.TestCase):

    def test_get_all_rules_by_category_returns_list(self):
        """get_all_rules_by_category retorna lista de reglas de la categoria."""
        from services.knowledge_base_service import get_all_rules_by_category

        rules = [
            {"rule_id": "reteica_bogota", "categoria": "impuestos", "titulo": "ReteICA"},
            {"rule_id": "iva_cuatrimestral", "categoria": "impuestos", "titulo": "IVA"},
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_all_rules_by_category("impuestos", mock_db))

        self.assertEqual(len(result), 2)
        # Verifica que no contengan _id
        for rule in result:
            self.assertNotIn("_id", rule)


class TestUpsertRule(unittest.TestCase):

    def test_upsert_rule_calls_update_one_with_upsert(self):
        """upsert_rule llama update_one con upsert=True y retorna rule_id."""
        from services.knowledge_base_service import upsert_rule

        mock_db = _make_mock_db([])
        rule_dict = {
            "rule_id": "test_rule_001",
            "categoria": "test",
            "titulo": "Test rule",
            "contenido": "Contenido de prueba.",
            "tags": ["test"],
        }

        result = asyncio.run(upsert_rule(rule_dict, mock_db))

        # Verifica que update_one fue llamado
        mock_db.sismo_knowledge.update_one.assert_called_once()
        call_args = mock_db.sismo_knowledge.update_one.call_args
        # Primer arg: filtro por rule_id
        self.assertEqual(call_args[0][0], {"rule_id": "test_rule_001"})
        # upsert=True en kwargs
        self.assertTrue(call_args[1].get("upsert") or call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("upsert"))
        # Retorna rule_id
        self.assertEqual(result, "test_rule_001")


# ── Task 3: Integration E2E Tests ─────────────────────────────────────────────

class TestArriendoE2E(unittest.TestCase):

    def test_arriendo_produces_retefuente_and_reteica_context(self):
        """
        Criterio principal: 'registra el arriendo de marzo' debe producir
        ReteFuente 3.5% y ReteICA 0.414% en el contexto.
        """
        from services.knowledge_base_service import get_context_for_operation

        rules = [
            {
                "rule_id": "retefuente_arriendo",
                "titulo": "ReteFuente arriendo",
                "contenido": "ReteFuente arriendo: 3.5% sobre pagos de arrendamiento.",
                "tags": ["retefuente", "arrendamiento", "retenciones"],
            },
            {
                "rule_id": "reteica_bogota",
                "titulo": "ReteICA Bogota",
                "contenido": "ReteICA Bogota: 0.414% en toda operacion comercial.",
                "tags": ["reteica", "retenciones", "bogota"],
            },
            {
                "rule_id": "auteco_autoretenedor",
                "titulo": "Auteco autoretenedor",
                "contenido": "Auteco NIT 860024781 es autoretenedor — NUNCA aplicar ReteFuente.",
                "tags": ["autoretenedores", "retefuente", "auteco"],
            },
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_context_for_operation("registrar_arriendo", mock_db))

        self.assertIn("3.5%", result)
        self.assertIn("0.414%", result)
        self.assertIn("REGLAS APLICABLES", result)

    def test_factura_moto_produces_vin_context(self):
        """'crear factura moto' debe incluir regla de VIN y motor obligatorios."""
        from services.knowledge_base_service import get_context_for_operation

        rules = [
            {
                "rule_id": "vin_motor_factura",
                "titulo": "VIN y Motor obligatorios",
                "contenido": "VIN y motor OBLIGATORIOS en toda factura de moto.",
                "tags": ["VIN", "motor", "factura", "moto"],
            }
        ]
        mock_db = _make_mock_db(rules)

        result = asyncio.run(get_context_for_operation("crear_factura_moto", mock_db))

        self.assertIn("VIN", result)
        self.assertIn("motor", result.lower())

    def test_unknown_operation_returns_empty(self):
        """Operacion desconocida retorna string vacio exacto."""
        from services.knowledge_base_service import get_context_for_operation

        mock_db = _make_mock_db([])
        result = asyncio.run(get_context_for_operation("operacion_inexistente", mock_db))

        self.assertEqual(result, "")

    def test_seed_knowledge_count(self):
        """SISMO_KNOWLEDGE debe tener >= 22 reglas despues del seed ampliado."""
        import os
        # Detectar raiz del proyecto (dos niveles arriba de backend/tests/)
        _here = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.dirname(os.path.dirname(_here))
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        # Limpiar modulo cacheado si existia con ruta distinta
        if "init_mongodb_sismo" in sys.modules:
            del sys.modules["init_mongodb_sismo"]
        from init_mongodb_sismo import SISMO_KNOWLEDGE
        self.assertGreaterEqual(
            len(SISMO_KNOWLEDGE),
            22,
            f"SISMO_KNOWLEDGE solo tiene {len(SISMO_KNOWLEDGE)} reglas — se esperan >= 22",
        )


if __name__ == "__main__":
    unittest.main()
