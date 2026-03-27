"""
Portfolio Pipeline — Pre-computed summaries for CFO agent.

compute_portfolio_summary(): Daily 11:30 PM — persists semaforo + cartera snapshot.
compute_financial_report_mensual(): Monthly day 1 — persists P&L from Alegra + MongoDB.
get_portfolio_data_for_cfo(): Read today's pre-computed summary (CFO cache layer).
"""

import logging
from datetime import datetime, timezone, date as date_type

logger = logging.getLogger(__name__)


async def compute_portfolio_summary(db) -> dict:
    """
    Compute daily portfolio snapshot reusing existing analysis functions.
    Persists to portfolio_summaries collection with today's date.
    Called by scheduler at 11:30 PM COT daily.

    Document schema:
    {
        "fecha": "2026-03-26",
        "semaforo": { ... },  # Output of generar_semaforo()
        "cartera": { ... },   # Output of analizar_cartera()
        "timestamp_utc": "2026-03-27T04:30:00Z",
        "source": "scheduler",
    }
    """
    from services.cfo_agent import (
        consolidar_datos_financieros,
        analizar_cartera,
        generar_semaforo,
    )

    try:
        datos = await consolidar_datos_financieros(db)
        cartera = await analizar_cartera(datos)
        semaforo = await generar_semaforo(datos)

        now = datetime.now(timezone.utc)
        fecha = now.strftime("%Y-%m-%d")

        doc = {
            "fecha": fecha,
            "semaforo": semaforo,
            "cartera": cartera,
            "timestamp_utc": now.isoformat(),
            "source": "scheduler",
        }

        # Upsert by fecha (one snapshot per day)
        result = await db.portfolio_summaries.update_one(
            {"fecha": fecha},
            {"$set": doc},
            upsert=True,
        )

        logger.info(
            "[Pipeline] Portfolio summary for %s: upserted=%s",
            fecha,
            result.upserted_id is not None,
        )

        # Emit event via bus (portfolio.resumen.calculado is registered in EventType catalog)
        try:
            from services.event_bus_service import EventBusService
            from event_models import RoddosEvent
            bus = EventBusService(db)
            event = RoddosEvent(
                event_type="portfolio.resumen.calculado",
                source_agent="cfo",
                actor="scheduler",
                target_entity="global",
                payload={"fecha": fecha},
            )
            await bus.emit(event)
        except Exception as e:
            logger.warning("[Pipeline] Event emit failed (non-fatal): %s", e)

        return doc

    except Exception as e:
        logger.error("[Pipeline] compute_portfolio_summary failed: %s", e)
        raise


async def compute_financial_report_mensual(db) -> dict:
    """
    Compute monthly P&L report on day 1 of each month.
    Calls Alegra + MongoDB for real accounting data, persists to financial_reports.

    Document schema:
    {
        "periodo": "2026-03",
        "tipo": "mensual",
        "pyg": { ... },          # Output of analizar_pyg()
        "semaforo": { ... },
        "cartera": { ... },
        "exposicion_tributaria": { ... },
        "timestamp_utc": "...",
        "source": "scheduler",
    }
    """
    from services.cfo_agent import (
        consolidar_datos_financieros,
        analizar_pyg,
        analizar_cartera,
        generar_semaforo,
        analizar_exposicion_tributaria,
    )

    try:
        datos = await consolidar_datos_financieros(db)
        pyg = await analizar_pyg(datos)
        cartera = await analizar_cartera(datos)
        semaforo = await generar_semaforo(datos)
        tributaria = await analizar_exposicion_tributaria(datos)

        now = datetime.now(timezone.utc)
        periodo = now.strftime("%Y-%m")

        doc = {
            "periodo": periodo,
            "tipo": "mensual",
            "pyg": pyg,
            "cartera": cartera,
            "semaforo": semaforo,
            "exposicion_tributaria": tributaria,
            "timestamp_utc": now.isoformat(),
            "source": "scheduler",
        }

        result = await db.financial_reports.update_one(
            {"periodo": periodo, "tipo": "mensual"},
            {"$set": doc},
            upsert=True,
        )

        logger.info(
            "[Pipeline] Financial report for %s: upserted=%s",
            periodo,
            result.upserted_id is not None,
        )

        return doc

    except Exception as e:
        logger.error("[Pipeline] compute_financial_report_mensual failed: %s", e)
        raise


async def get_portfolio_data_for_cfo(db) -> dict | None:
    """
    Read today's pre-computed portfolio summary.
    Returns the document if available, None if no summary for today.
    CFO agent calls this first; falls back to Alegra only if None.
    """
    fecha = date_type.today().isoformat()
    doc = await db.portfolio_summaries.find_one(
        {"fecha": fecha},
        {"_id": 0},
    )
    return doc
