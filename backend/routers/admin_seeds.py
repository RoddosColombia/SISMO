"""
admin_seeds.py — Admin API para ejecutar seeds de MongoDB en runtime.

Endpoints:
    POST /admin/run-seed    — Ejecutar seed por nombre (knowledge_base, plan_cuentas, all)
    GET  /admin/seed-status — Verificar conteo de documentos en colecciones seed

Ambos endpoints requieren rol admin.
"""
import sys
import os
import logging

# ── sys.path para importar init_mongodb_sismo.py desde raiz del proyecto ──
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from init_mongodb_sismo import SISMO_KNOWLEDGE, PLAN_CUENTAS_RODDOS

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import db
from dependencies import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin-seeds"])

VALID_SEEDS = ("knowledge_base", "plan_cuentas", "all")


# ── Modelos Pydantic ──────────────────────────────────────────────────────────

class RunSeedRequest(BaseModel):
    seed_name: str


class RunSeedResponse(BaseModel):
    seed_name: str
    documentos_cargados: int
    status: str
    mensaje: str


# ── Helpers internos ──────────────────────────────────────────────────────────

async def _seed_knowledge_base() -> int:
    """Upsert todos los documentos de SISMO_KNOWLEDGE por rule_id."""
    count = 0
    for doc in SISMO_KNOWLEDGE:
        await db.sismo_knowledge.update_one(
            {"rule_id": doc["rule_id"]},
            {"$set": doc},
            upsert=True,
        )
        count += 1
    return count


async def _seed_plan_cuentas() -> int:
    """Upsert todos los documentos de PLAN_CUENTAS_RODDOS por (categoria, subcategoria)."""
    count = 0
    for doc in PLAN_CUENTAS_RODDOS:
        await db.plan_cuentas_roddos.update_one(
            {"categoria": doc["categoria"], "subcategoria": doc["subcategoria"]},
            {"$set": doc},
            upsert=True,
        )
        count += 1
    return count


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/admin/run-seed", response_model=RunSeedResponse)
async def run_seed(
    request: RunSeedRequest,
    current_user=Depends(require_admin),
):
    """Ejecutar seed de MongoDB por nombre.

    seed_name validos: knowledge_base, plan_cuentas, all.
    Requiere rol admin. Operaciones son idempotentes (upsert).
    """
    seed_name = request.seed_name

    if seed_name not in VALID_SEEDS:
        raise HTTPException(
            status_code=400,
            detail=f"seed_name invalido: '{seed_name}'. Valores validos: {list(VALID_SEEDS)}",
        )

    try:
        total = 0

        if seed_name in ("knowledge_base", "all"):
            kb_count = await _seed_knowledge_base()
            total += kb_count
            logger.info(f"admin_seeds: knowledge_base seed — {kb_count} docs cargados por {current_user.get('email', '?')}")

        if seed_name in ("plan_cuentas", "all"):
            pc_count = await _seed_plan_cuentas()
            total += pc_count
            logger.info(f"admin_seeds: plan_cuentas seed — {pc_count} docs cargados por {current_user.get('email', '?')}")

        return RunSeedResponse(
            seed_name=seed_name,
            documentos_cargados=total,
            status="ok",
            mensaje=f"Seed '{seed_name}' completado: {total} documentos cargados.",
        )

    except Exception as e:
        logger.error(f"admin_seeds: error ejecutando seed '{seed_name}': {e}")
        return RunSeedResponse(
            seed_name=seed_name,
            documentos_cargados=0,
            status="error",
            mensaje=f"Error ejecutando seed '{seed_name}': {e}",
        )


@router.get("/admin/seed-status")
async def seed_status(
    current_user=Depends(require_admin),
):
    """Verificar conteo de documentos en colecciones seed.

    Requiere rol admin. Retorna conteos actuales de sismo_knowledge y plan_cuentas_roddos.
    """
    try:
        count_kb = await db.sismo_knowledge.count_documents({})
        count_pc = await db.plan_cuentas_roddos.count_documents({})
        return {
            "sismo_knowledge": count_kb,
            "plan_cuentas_roddos": count_pc,
        }
    except Exception as e:
        logger.error(f"admin_seeds: error consultando seed-status: {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando estado seeds: {e}")
