"""migration_v24.py — Migración no-destructiva: agrega campos DPD/Score/PTP/gestiones.

Idempotente: usa la presencia de 'dpd_actual' como centinela.
Llamar desde server.py startup — siempre seguro ejecutar múltiples veces.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SENTINEL = "dpd_actual"


async def run_migration_v24(db) -> None:
    """Agrega campos DPD/Score/PTP/gestiones/reestructuraciones a loanbooks existentes."""

    count_pending = await db.loanbook.count_documents({_SENTINEL: {"$exists": False}})
    if count_pending == 0:
        logger.info("[Migration v24] Ya aplicada — skipping")
        return

    logger.info("[Migration v24] Aplicando a %d loanbook(s)...", count_pending)
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── 1. Actualización masiva de campos de nivel raíz ───────────────────────
    result = await db.loanbook.update_many(
        {_SENTINEL: {"$exists": False}},
        {"$set": {
            "dpd_actual":             0,
            "dpd_bucket":             "0",
            "dpd_maximo_historico":   0,
            "score_pago":             "A+",
            "estrella_nivel":         5,
            "score_historial":        [],
            "interes_mora_acumulado": 0.0,
            "ptp_fecha":              None,
            "ptp_monto":              None,
            "ptp_registrado_por":     None,
            "gestiones":              [],
            "reestructuraciones":     [],
            "migrated_v24_at":        now_iso,
        }},
    )
    logger.info("[Migration v24] %d loanbooks actualizados (campos raíz)", result.modified_count)

    # ── 2. Actualizar campo canal_pago / registrado_por / dpd_al_pagar en cuotas ─
    loans = await db.loanbook.find(
        {"cuotas.0": {"$exists": True}},
        {"_id": 0, "id": 1, "cuotas": 1},
    ).to_list(10_000)

    cuotas_docs_updated = 0
    for loan in loans:
        cuotas = loan.get("cuotas", [])
        if all("canal_pago" in c for c in cuotas):
            continue  # ya migradas
        updated_cuotas = []
        for cuota in cuotas:
            if "canal_pago" not in cuota:
                cuota = {
                    **cuota,
                    "canal_pago":     "manual",
                    "registrado_por": "migración",
                    "dpd_al_pagar":   0,
                }
            updated_cuotas.append(cuota)
        await db.loanbook.update_one(
            {"id": loan["id"]},
            {"$set": {"cuotas": updated_cuotas}},
        )
        cuotas_docs_updated += 1

    logger.info("[Migration v24] Cuotas actualizadas en %d loanbooks", cuotas_docs_updated)
    logger.info("[Migration v24] Completada exitosamente")
