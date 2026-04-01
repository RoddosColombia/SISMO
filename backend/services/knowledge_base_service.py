"""
knowledge_base_service.py — Capa RAG para agentes SISMO.

Permite a los agentes consultar reglas de negocio institucionales de RODDOS
desde MongoDB (coleccion sismo_knowledge) antes de ejecutar operaciones contables.

Funciones publicas:
- get_context_for_operation(operation_type, db) -> str
- get_all_rules_by_category(categoria, db) -> list
- upsert_rule(rule_dict, db) -> str
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Mapeo operacion -> tags relevantes ────────────────────────────────────────
# Cada entrada mapea un tipo de operacion a los tags que se deben buscar en MongoDB.
# Los tags deben coincidir con los definidos en SISMO_KNOWLEDGE de init_mongodb_sismo.py.

OPERATION_TAG_MAP: dict[str, list[str]] = {
    "registrar_gasto": ["retenciones", "autoretenedores", "retefuente"],
    "crear_factura_moto": ["VIN", "factura", "moto", "motor"],
    "registrar_pago_cartera": ["cartera", "duplicado", "pago", "mora", "cobranza"],
    "registrar_nomina": ["nomina", "retefuente", "nómina"],
    "registrar_arriendo": ["retenciones", "retefuente", "arrendamiento", "reteica", "autoretenedores"],
    "conciliacion": ["bancos", "endpoints_alegra", "contabilidad"],
}


async def get_context_for_operation(operation_type: str, db) -> str:
    """Retorna bloque de reglas relevantes para el tipo de operacion.

    Busca en sismo_knowledge los documentos cuyos tags coincidan con los
    tags mapeados para operation_type. Si la operacion no esta en el mapa
    o no hay resultados, retorna "".

    Args:
        operation_type: Clave del OPERATION_TAG_MAP (ej: 'registrar_arriendo').
        db: Instancia de base de datos Motor o mock compatible.

    Returns:
        String formateado con las reglas relevantes, o "" si no hay ninguna.
    """
    relevant_tags = OPERATION_TAG_MAP.get(operation_type)
    if not relevant_tags:
        return ""

    try:
        cursor = db.sismo_knowledge.find({"tags": {"$in": relevant_tags}})
        rules = await cursor.to_list(length=20)
    except Exception as e:
        logger.warning(f"knowledge_base_service: error consultando sismo_knowledge: {e}")
        return ""

    if not rules:
        return ""

    lines = ["== REGLAS APLICABLES =="]
    for rule in rules:
        titulo = rule.get("titulo", "")
        contenido = rule.get("contenido", "")
        lines.append(f"- {titulo}: {contenido}")

    return "\n".join(lines)


async def get_all_rules_by_category(categoria: str, db) -> list:
    """Retorna lista de reglas de una categoria especifica.

    Args:
        categoria: Categoria a filtrar (ej: 'impuestos', 'cartera').
        db: Instancia de base de datos Motor o mock compatible.

    Returns:
        Lista de dicts con las reglas. El campo _id es removido.
    """
    try:
        cursor = db.sismo_knowledge.find({"categoria": categoria})
        rules = await cursor.to_list(length=100)
    except Exception as e:
        logger.warning(f"knowledge_base_service: error consultando categoria '{categoria}': {e}")
        return []

    # Remover _id para que sea serializable
    result = []
    for rule in rules:
        rule_clean = {k: v for k, v in rule.items() if k != "_id"}
        result.append(rule_clean)

    return result


async def upsert_rule(rule_dict: dict, db) -> str:
    """Crea o actualiza una regla en sismo_knowledge.

    Args:
        rule_dict: Dict con rule_id (requerido), categoria, titulo, contenido, tags.
        db: Instancia de base de datos Motor o mock compatible.

    Returns:
        rule_id de la regla creada/actualizada.

    Raises:
        ValueError: Si rule_id no esta presente en rule_dict.
    """
    rule_id = rule_dict.get("rule_id")
    if not rule_id:
        raise ValueError("rule_dict debe contener 'rule_id'")

    update_data = {
        **rule_dict,
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
    }

    await db.sismo_knowledge.update_one(
        {"rule_id": rule_id},
        {"$set": update_data},
        upsert=True,
    )

    return rule_id
