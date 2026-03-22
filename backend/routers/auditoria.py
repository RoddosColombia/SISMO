"""auditoria.py — Endpoints para auditoría, búsqueda y limpieza de datos en Alegra."""

import logging
import os
import base64
import httpx
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dependencies import get_current_user, require_admin

router = APIRouter(prefix="/auditoria", tags=["auditoria"])
logger = logging.getLogger(__name__)


# ── Pydantic Models ────────────────────────────────────────────────────────

class BuscarJournalsRequest(BaseModel):
    codigos: List[str]  # Ej: ["CC-AC-584", "CC-AC-484", "CC-AC-384"]


class JournalInfo(BaseModel):
    id: int  # ID numérico en Alegra
    codigo_interno: str  # Código CC-AC-XXX
    fecha: Optional[str] = None
    observations: str
    monto_total: Optional[float] = None
    status: str = "encontrado"


# ── Helper Functions ───────────────────────────────────────────────────────

async def get_alegra_credentials():
    """Obtiene credenciales de Alegra del entorno."""
    email = os.environ.get("ALEGRA_EMAIL", "")
    token = os.environ.get("ALEGRA_TOKEN", "")

    if not email or not token:
        raise HTTPException(
            status_code=500,
            detail="Credenciales de Alegra no configuradas (ALEGRA_EMAIL/ALEGRA_TOKEN)"
        )

    return email, token


async def get_alegra_journals(email: str, token: str, limit: int = 100) -> List[dict]:
    """
    Obtiene journals de Alegra.

    GET /api/v1/journals retorna lista de journals.
    Puede paginar con limit/offset.
    """
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    base_url = "https://api.alegra.com/api/v1"
    all_journals = []
    offset = 0

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                url = f"{base_url}/journals?limit={limit}&offset={offset}"
                logger.info(f"[Alegra] GET {url}")

                response = await client.get(url, headers=headers)

                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    logger.error(f"[Alegra] Error {response.status_code}: {error_data}")
                    break

                data = response.json()

                # Alegra retorna: {"entries": [...]} o ["entrada1", "entrada2"]
                # Intentamos ambos formatos
                journals = data.get("entries") if isinstance(data, dict) else data

                if not journals or len(journals) == 0:
                    break

                all_journals.extend(journals)
                offset += limit
                logger.info(f"[Alegra] Obtenidos {len(journals)} journals, total acumulado: {len(all_journals)}")

                # Si la respuesta tiene menos items que el limit, es la última página
                if len(journals) < limit:
                    break

    except Exception as e:
        logger.error(f"[Alegra] Error obteniendo journals: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error consultando Alegra: {str(e)}"
        )

    return all_journals


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/buscar-journals-por-codigo")
async def buscar_journals_por_codigo(
    request: BuscarJournalsRequest,
    current_user=Depends(require_admin),
):
    """
    Busca journals en Alegra por código interno (ej: CC-AC-584).

    Retorna los IDs numéricos de Alegra y detalles de cada journal encontrado.
    Esto es necesario porque Alegra usa IDs numéricos, pero internamente
    usamos códigos CC-AC-XXX.

    IMPORTANTE: Solo admins pueden usar este endpoint.

    Ejemplo de entrada:
    {
      "codigos": ["CC-AC-584", "CC-AC-484", "CC-AC-384"]
    }

    Ejemplo de salida:
    {
      "codigos_buscados": 3,
      "journals_encontrados": 2,
      "resultados": [
        {
          "id": 12345,
          "codigo_interno": "CC-AC-584",
          "fecha": "2026-01-31",
          "observations": "NÓMINA ENERO 2026 (CC-AC-584)",
          "monto_total": 7912000,
          "status": "encontrado"
        }
      ],
      "no_encontrados": ["CC-AC-384"]
    }
    """
    try:
        email, token = await get_alegra_credentials()

        # Obtener todos los journals de Alegra
        logger.info(f"[Auditoria] Buscando {len(request.codigos)} códigos en Alegra...")
        journals_alegra = await get_alegra_journals(email, token, limit=100)

        logger.info(f"[Auditoria] Total de journals en Alegra: {len(journals_alegra)}")

        # Buscar coincidencias
        resultados = []
        codigos_encontrados = set()

        for codigo in request.codigos:
            encontrado = False

            for journal in journals_alegra:
                # El journal puede ser un dict o un objeto
                if isinstance(journal, dict):
                    journal_id = journal.get("id")
                    observations = journal.get("observations", "")
                    fecha = journal.get("date") or journal.get("fecha")
                else:
                    # Si es un objeto, intentar acceder como dict
                    try:
                        journal_id = journal.get("id") if hasattr(journal, "get") else getattr(journal, "id", None)
                        observations = journal.get("observations") if hasattr(journal, "get") else getattr(journal, "observations", "")
                        fecha = (journal.get("date") if hasattr(journal, "get") else getattr(journal, "date", None)) or \
                                (journal.get("fecha") if hasattr(journal, "get") else getattr(journal, "fecha", None))
                    except:
                        continue

                # Buscar el código en las observations
                if codigo in observations:
                    encontrado = True
                    codigos_encontrados.add(codigo)

                    # Intentar extraer monto total (suma de debits o credits)
                    entries = journal.get("entries") if isinstance(journal, dict) else getattr(journal, "entries", [])
                    monto_total = None
                    if entries:
                        total_debits = sum(e.get("debit", 0) if isinstance(e, dict) else getattr(e, "debit", 0) for e in entries)
                        total_credits = sum(e.get("credit", 0) if isinstance(e, dict) else getattr(e, "credit", 0) for e in entries)
                        monto_total = max(total_debits, total_credits)

                    resultados.append({
                        "id": journal_id,
                        "codigo_interno": codigo,
                        "fecha": fecha,
                        "observations": observations[:100],  # Limitar a 100 caracteres
                        "monto_total": monto_total,
                        "status": "encontrado"
                    })

                    logger.info(f"[Auditoria] ✅ Encontrado: {codigo} → ID Alegra {journal_id}")
                    break

            if not encontrado:
                logger.warning(f"[Auditoria] ⚠️ NO ENCONTRADO: {codigo}")

        # Códigos no encontrados
        no_encontrados = [cod for cod in request.codigos if cod not in codigos_encontrados]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "codigos_buscados": len(request.codigos),
            "journals_encontrados": len(resultados),
            "resultados": resultados,
            "no_encontrados": no_encontrados,
            "nota": "Los IDs numéricos en 'resultados' son los IDs reales de Alegra. Úsalos para eliminar journals."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auditoria] Error buscando journals: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error buscando journals: {str(e)}"
        )


@router.delete("/eliminar-journal/{journal_id}")
async def eliminar_journal(
    journal_id: int,
    current_user=Depends(require_admin),
):
    """
    Elimina un journal de Alegra por su ID numérico.

    PELIGRO: Esta acción es IRREVERSIBLE. Asegúrate de que es el journal duplicado.

    Parámetros:
    - journal_id: ID numérico del journal en Alegra (ej: 12345)

    Retorna:
    {
      "eliminado": true,
      "journal_id": 12345,
      "http_status": 200,
      "timestamp": "2026-03-21T10:30:45.123Z"
    }
    """
    try:
        email, token = await get_alegra_credentials()

        creds = base64.b64encode(f"{email}:{token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        base_url = "https://api.alegra.com/api/v1"
        url = f"{base_url}/journals/{journal_id}"

        logger.warning(f"[Auditoria] 🔴 ELIMINANDO journal {journal_id}...")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(url, headers=headers)

            if response.status_code == 200:
                logger.warning(f"[Auditoria] ✅ Journal {journal_id} ELIMINADO exitosamente")
                return {
                    "eliminado": True,
                    "journal_id": journal_id,
                    "http_status": response.status_code,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mensaje": "Journal eliminado exitosamente"
                }
            else:
                error_data = response.json() if response.content else {}
                logger.error(f"[Auditoria] Error {response.status_code} eliminando journal {journal_id}: {error_data}")

                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Alegra retornó {response.status_code}: {error_data.get('message', 'Error desconocido')}"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auditoria] Error eliminando journal {journal_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando journal: {str(e)}"
        )
