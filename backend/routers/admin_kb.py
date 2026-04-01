"""
admin_kb.py — Admin API para Knowledge Base (base RAG de reglas de negocio).

Endpoints:
    POST /admin/knowledge-base/upsert  — Crear o actualizar una regla
    GET  /admin/knowledge-base/{categoria} — Listar reglas por categoria

Ambos endpoints requieren rol admin.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import db
from dependencies import get_current_user, require_admin
from services.knowledge_base_service import upsert_rule, get_all_rules_by_category

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin-knowledge-base"])


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class KnowledgeRuleRequest(BaseModel):
    rule_id: str
    categoria: Optional[str] = None
    titulo: Optional[str] = None
    contenido: Optional[str] = None
    tags: Optional[List[str]] = None


class UpsertResponse(BaseModel):
    ok: bool
    rule_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/admin/knowledge-base/upsert", response_model=UpsertResponse)
async def upsert_knowledge_rule(
    rule: KnowledgeRuleRequest,
    current_user=Depends(require_admin),
):
    """Crear o actualizar una regla de negocio en sismo_knowledge.

    Requiere rol admin. Usa upsert por rule_id (idempotente).
    """
    try:
        rule_dict = rule.model_dump(exclude_none=True)
        result_id = await upsert_rule(rule_dict, db)
        logger.info(f"admin_kb: upserted rule '{result_id}' by user {current_user.get('email', '?')}")
        return UpsertResponse(ok=True, rule_id=result_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"admin_kb: error upserting rule: {e}")
        raise HTTPException(status_code=500, detail=f"Error guardando regla: {e}")


@router.get("/admin/knowledge-base/{categoria}")
async def get_rules_by_category(
    categoria: str,
    current_user=Depends(require_admin),
):
    """Listar todas las reglas de una categoria especifica.

    Requiere rol admin. Retorna lista de reglas sin campo _id.
    """
    try:
        rules = await get_all_rules_by_category(categoria, db)
        return {"categoria": categoria, "total": len(rules), "reglas": rules}
    except Exception as e:
        logger.error(f"admin_kb: error consultando categoria '{categoria}': {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando reglas: {e}")
