"""Auteco inventory service: PDF parsing + Alegra item registration."""
import io
import os
import uuid
import json
from datetime import datetime, timezone

import pdfplumber
from emergentintegrations.llm.chat import LlmChat, UserMessage


PARSE_PROMPT = """Eres un extractor especializado en facturas de Auteco (distribuidor motos TVS/Apache Colombia).

Del texto de esta factura extrae TODAS las motos que aparezcan. Devuelve ÚNICAMENTE un JSON array:
[
  {{
    "marca": "TVS",
    "version": "RAIDER 125",
    "color": "NEGRO NEBULOSA",
    "ano_modelo": 2027,
    "motor": "BF3AT13C2338",
    "chasis": "9FL25AF3XVDB95057",
    "costo": 5638974,
    "iva_compra": 1071405,
    "ipoconsumo": 0,
    "total": 6710379,
    "factura_no": "FAC-001",
    "fecha_compra": "2025-10-15"
  }}
]

Reglas:
- costo = precio base sin impuestos
- iva_compra = 19% del costo
- ipoconsumo = impuesto al consumo (aplica a motos)
- total = costo + iva_compra + ipoconsumo
- Si un campo no está, usa null
- Solo devuelve JSON válido, sin texto adicional

TEXTO FACTURA:
{text}
"""


async def extract_motos_from_pdf(pdf_bytes: bytes, filename: str) -> list:
    """Extract motorcycle data from Auteco invoice PDF using AI."""
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                # Also try to get tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text += " | ".join([str(c) if c else "" for c in row]) + "\n"
    except Exception as e:
        raise ValueError(f"Error leyendo PDF: {str(e)}")

    if not text.strip():
        raise ValueError("No se pudo extraer texto del PDF. Verifique que no esté protegido.")

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("EMERGENT_LLM_KEY no configurado")

    session_id = f"pdf-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message="Eres un extractor preciso de datos. Responde SOLO con JSON válido.",
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    prompt = PARSE_PROMPT.format(text=text[:8000])
    response = await chat.send_message(UserMessage(text=prompt))

    # Parse JSON
    json_start = response.find("[")
    json_end = response.rfind("]") + 1
    if json_start == -1 or json_end <= json_start:
        raise ValueError("La IA no pudo extraer datos de la factura. Verifique el formato del PDF.")

    motos = json.loads(response[json_start:json_end])
    # Enrich with metadata
    for m in motos:
        m["id"] = str(uuid.uuid4())
        m["archivo_origen"] = filename
        m["estado"] = "Disponible"
        m["placa"] = None
        m["ubicacion"] = "BODEGA"
        m["alegra_item_id"] = None
        m["created_at"] = datetime.now(timezone.utc).isoformat()
        # Calculate missing fields
        if m.get("costo") and not m.get("total"):
            costo = m["costo"]
            iva = m.get("iva_compra") or round(costo * 0.19)
            ipoc = m.get("ipoconsumo") or 0
            m["iva_compra"] = iva
            m["ipoconsumo"] = ipoc
            m["total"] = costo + iva + ipoc

    return motos


async def register_moto_in_alegra(moto: dict, alegra_service) -> dict:
    """Register a motorcycle as an item in Alegra."""
    description = (
        f"{moto.get('marca', 'TVS')} {moto.get('version', '')} "
        f"{moto.get('color', '')} - Motor: {moto.get('motor', '')} "
        f"/ Chasis: {moto.get('chasis', '')}"
    )
    payload = {
        "name": f"{moto.get('marca', 'TVS')} {moto.get('version', '')} - {moto.get('chasis', '')}",
        "description": description,
        "type": "product",
        "price": [{"price": moto.get("total", 0)}],
        "reference": moto.get("chasis"),
    }
    result = await alegra_service.request("items", "POST", payload)
    return result
