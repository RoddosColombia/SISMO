"""
Intent Router — LLM-based message classification for SISMO agents.

Replaces keyword-based is_cfo_query() with confidence-scored routing.
Uses Claude Haiku for fast, cheap classification (~100 tokens per call).
"""

import json
import logging
import os
from typing import TypedDict

import anthropic

logger = logging.getLogger(__name__)

INTENT_THRESHOLD = 0.7

VALID_AGENTS = {"contador", "cfo", "radar", "loanbook"}

ROUTER_SYSTEM_PROMPT = """Eres un clasificador de intents para SISMO, sistema de RODDOS Colombia (fintech de movilidad).

Dado un mensaje del usuario, clasifica a cual agente debe ir:

- **contador**: Registro de asientos contables, facturas, gastos, retenciones, IVA, causaciones en Alegra. Todo lo transaccional contable.
- **cfo**: Analisis financiero estrategico, P&L, semaforo, flujo de caja, margen, EBITDA, estado general de la empresa, metas financieras.
- **radar**: Cobranza, mora, clientes en atraso, recordatorios de pago, WhatsApp de cobro, DPD, buckets de mora.
- **loanbook**: Creacion de financiamientos, planes de pago (P39S, P52S, P78S), cuotas, VINs, entregas de motos, inventario.

Responde SOLO con JSON valido:
{"agent": "<nombre>", "confidence": <0.0-1.0>}

Reglas:
- Si el mensaje es ambiguo o podria ir a multiples agentes, usa confidence < 0.7
- Si es claramente de un dominio, usa confidence >= 0.8
- Si es un saludo generico o pregunta no relacionada, usa "contador" con confidence 0.5
"""


class RouteResult(TypedDict):
    agent: str
    confidence: float
    needs_clarification: bool
    clarification_message: str | None


async def classify_intent(message: str) -> RouteResult:
    """
    Classify user message intent using Claude Haiku.
    Returns agent name, confidence score, and whether clarification is needed.
    """
    try:
        client = anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=ROUTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )

        text = response.content[0].text.strip()
        # Parse JSON response
        result = json.loads(text)
        agent = result.get("agent", "contador")
        confidence = float(result.get("confidence", 0.5))

        # Validate agent name
        if agent not in VALID_AGENTS:
            agent = "contador"
            confidence = 0.5

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        needs_clarification = confidence < INTENT_THRESHOLD

        clarification_msg = None
        if needs_clarification:
            clarification_msg = (
                "No estoy seguro de como ayudarte. "
                "\u00bfQuieres que te ayude con:\n"
                "\u2022 **Contabilidad** (registrar gastos, facturas, retenciones)\n"
                "\u2022 **Analisis financiero** (P&L, semaforo, flujo de caja)\n"
                "\u2022 **Cobranza** (mora, cobros, recordatorios)\n"
                "\u2022 **Financiamientos** (crear loanbooks, cuotas, entregas)"
            )

        return RouteResult(
            agent=agent,
            confidence=confidence,
            needs_clarification=needs_clarification,
            clarification_message=clarification_msg,
        )

    except Exception as e:
        logger.warning("[Router] LLM classification failed: %s — defaulting to contador", e)
        return RouteResult(
            agent="contador",
            confidence=0.5,
            needs_clarification=False,
            clarification_message=None,
        )
