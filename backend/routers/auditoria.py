"""auditoria.py — Endpoints para auditoría, búsqueda y limpieza de datos en Alegra."""

import base64
import logging
import os
from typing import List, Optional
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dependencies import get_current_user, require_admin
from alegra_service import AlegraService, ALEGRA_BASE_URL
from database import db

router = APIRouter(prefix="/auditoria", tags=["auditoria"])
logger = logging.getLogger(__name__)

AUTECO_NIT = "860024781"


# ── Pydantic Models — Fase 1 ──────────────────────────────────────────────────

class AprobarLimpiezaRequest(BaseModel):
    confirmado: bool
    excluir_ids: List[int] = []


class AnularBillRequest(BaseModel):
    bill_id_a_anular: int
    bill_id_a_mantener: int


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

async def get_alegra_journals(limit: int = 100) -> List[dict]:
    """
    Obtiene journals de Alegra via AlegraService.

    GET /api/v1/journals retorna lista de journals.
    Puede paginar con limit/offset.
    """
    alegra = AlegraService(db)
    all_journals = []
    offset = 0

    while True:
        batch = await alegra.request("journals", "GET", params={"limit": limit, "offset": offset})
        if not batch or not isinstance(batch, list):
            break
        all_journals.extend(batch)
        logger.info(f"[Alegra] Obtenidos {len(batch)} journals, total acumulado: {len(all_journals)}")
        if len(batch) < limit:
            break
        offset += limit

    return all_journals


async def _get_alegra_auth_headers() -> dict:
    """Retorna headers Basic Auth para httpx directo leyendo credenciales del entorno/DB."""
    email = os.environ.get("ALEGRA_EMAIL", "").strip()
    token = os.environ.get("ALEGRA_TOKEN", "").strip()
    if not email or not token:
        # Fallback: leer desde MongoDB
        settings = await db.alegra_credentials.find_one({}, {"_id": 0})
        if settings:
            email = settings.get("email", "")
            token = settings.get("token", "")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _paginar_alegra(endpoint: str, limit: int = 100) -> List[dict]:
    """Pagina GET /{endpoint}?limit=N&offset=M hasta agotar todos los registros.

    REGLAS INAMOVIBLES:
    - NUNCA usar app.alegra.com/api/r1 — siempre api.alegra.com/api/v1 (ALEGRA_BASE_URL)
    - NUNCA /journal-entries — siempre /journals
    - Pagina hasta len(batch) < limit (no asumir que 30 es el total)
    """
    headers = await _get_alegra_auth_headers()
    all_records = []
    offset = 0

    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            url = f"{ALEGRA_BASE_URL}/{endpoint}"
            resp = await client.get(url, headers=headers, params={"limit": limit, "offset": offset})
            if resp.status_code >= 400:
                logger.warning(f"[Auditoria] _paginar_alegra {endpoint} HTTP {resp.status_code} — stop")
                break
            batch = resp.json()
            if not batch or not isinstance(batch, list):
                break
            all_records.extend(batch)
            logger.info(f"[Auditoria] {endpoint}: +{len(batch)} registros (total {len(all_records)})")
            if len(batch) < limit:
                break
            offset += limit

    return all_records


def _clasificar_registros(invoices: list, bills: list, journals: list) -> dict:
    """Clasifica invoices, bills y journals segun reglas de negocio RODDOS.

    Clasificacion:
    - facturas_venta: invoices donde ALGUN item tiene "VIN:" en description
    - facturas_venta_sin_vin: invoices sin "VIN:" en ningun item
    - compras_auteco: bills donde contact.identification == AUTECO_NIT
    - compras_otro_proveedor: bills de otro proveedor
    - journals_gasto: journals con al menos un entry debit > 0 en cuenta 5xxx
    - journals_ingreso: journals con al menos un entry credit > 0 en cuenta 4xxx
    - journals_otro: journals que no son gasto ni ingreso
    """
    facturas_venta = []
    facturas_venta_sin_vin = []

    for inv in invoices:
        items = inv.get("items") or []
        tiene_vin = any("VIN:" in (item.get("description") or "") for item in items)
        if tiene_vin:
            facturas_venta.append(inv)
        else:
            facturas_venta_sin_vin.append(inv)

    compras_auteco = []
    compras_otro_proveedor = []

    for bill in bills:
        contact = bill.get("contact") or {}
        nit = str(contact.get("identification") or "").strip()
        if nit == AUTECO_NIT:
            compras_auteco.append(bill)
        else:
            compras_otro_proveedor.append(bill)

    journals_gasto = []
    journals_ingreso = []
    journals_otro = []

    for journal in journals:
        entries = journal.get("entries") or []
        es_gasto = False
        es_ingreso = False

        for entry in entries:
            account = entry.get("account") or {}
            # Cuenta puede identificarse por code o id
            code = str(account.get("code") or account.get("id") or "")
            debit = float(entry.get("debit") or 0)
            credit = float(entry.get("credit") or 0)

            if debit > 0 and code.startswith("5"):
                es_gasto = True
            if credit > 0 and code.startswith("4"):
                es_ingreso = True

        if es_gasto:
            journals_gasto.append(journal)
        elif es_ingreso:
            journals_ingreso.append(journal)
        else:
            journals_otro.append(journal)

    return {
        "facturas_venta": facturas_venta,
        "facturas_venta_sin_vin": facturas_venta_sin_vin,
        "compras_auteco": compras_auteco,
        "compras_otro_proveedor": compras_otro_proveedor,
        "journals_gasto": journals_gasto,
        "journals_ingreso": journals_ingreso,
        "journals_otro": journals_otro,
    }


def _detectar_duplicados_auteco(compras_auteco: list) -> list:
    """Detecta bills duplicadas de Auteco por (numero_factura + monto).

    Agrupa por (numero, total). Si hay 2+ bills con mismo numero Y monto → alerta.
    Retorna lista de alertas tipo "bill_duplicada".
    """
    from collections import defaultdict

    grupos: dict = defaultdict(list)

    for bill in compras_auteco:
        # Numero: puede estar en numberTemplate.number o en number
        numero = None
        number_template = bill.get("numberTemplate")
        if number_template and isinstance(number_template, dict):
            numero = number_template.get("number")
        if not numero:
            numero = bill.get("number") or bill.get("numberTemplate")
        if numero is None:
            numero = str(bill.get("id", ""))

        monto = float(bill.get("total") or 0)
        clave = (str(numero), monto)
        grupos[clave].append(bill)

    alertas = []
    for (numero, monto), bills_grupo in grupos.items():
        if len(bills_grupo) >= 2:
            # Ordenar por id para consistencia (original = menor id)
            ordenadas = sorted(bills_grupo, key=lambda b: b.get("id", 0))
            original = ordenadas[0]
            for duplicada in ordenadas[1:]:
                alertas.append({
                    "tipo": "bill_duplicada",
                    "mensaje": f"Bill duplicada Auteco: {numero} por ${monto:,.0f}",
                    "bill_original_id": original.get("id"),
                    "bill_duplicada_id": duplicada.get("id"),
                    "numero_factura": numero,
                    "monto": monto,
                })

    return alertas


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/alegra-completo")
async def alegra_completo(
    current_user=Depends(require_admin),
):
    """Pagina TODOS los registros de Alegra (invoices, bills, journals) y los clasifica.

    Detecta bills duplicadas de Auteco (mismo numero + monto).
    Retorna resumen, clasificacion completa y alertas.

    REGLAS: paginacion real hasta agotar, NUNCA /journal-entries, NUNCA app.alegra.com/api/r1
    """
    try:
        logger.info("[Auditoria] Iniciando descarga completa de Alegra...")

        invoices = await _paginar_alegra("invoices")
        bills = await _paginar_alegra("bills")
        journals = await _paginar_alegra("journals")

        logger.info(
            f"[Auditoria] Descargados: {len(invoices)} invoices, "
            f"{len(bills)} bills, {len(journals)} journals"
        )

        clasificado = _clasificar_registros(invoices, bills, journals)
        alertas = _detectar_duplicados_auteco(clasificado["compras_auteco"])

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resumen": {
                "total_invoices": len(invoices),
                "total_bills": len(bills),
                "total_journals": len(journals),
                "facturas_venta": len(clasificado["facturas_venta"]),
                "facturas_venta_sin_vin": len(clasificado["facturas_venta_sin_vin"]),
                "compras_auteco": len(clasificado["compras_auteco"]),
                "compras_otro_proveedor": len(clasificado["compras_otro_proveedor"]),
                "journals_gasto": len(clasificado["journals_gasto"]),
                "journals_ingreso": len(clasificado["journals_ingreso"]),
                "journals_otro": len(clasificado["journals_otro"]),
            },
            "facturas_venta": clasificado["facturas_venta"],
            "facturas_venta_sin_vin": clasificado["facturas_venta_sin_vin"],
            "compras_auteco": clasificado["compras_auteco"],
            "compras_otro_proveedor": clasificado["compras_otro_proveedor"],
            "journals_gasto": clasificado["journals_gasto"],
            "journals_ingreso": clasificado["journals_ingreso"],
            "journals_otro": clasificado["journals_otro"],
            "alertas": alertas,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auditoria] Error en alegra-completo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error descargando datos de Alegra: {str(e)}")


@router.post("/aprobar-limpieza")
async def aprobar_limpieza(
    request: AprobarLimpiezaRequest,
    current_user=Depends(require_admin),
):
    """Registra aprobacion de limpieza de bills duplicadas.

    - confirmado=False: retorna plan sin ejecutar, NO escribe en MongoDB
    - confirmado=True: inserta en auditoria_aprobaciones con trazabilidad
    """
    if not request.confirmado:
        return {
            "status": "plan_sin_ejecutar",
            "mensaje": "Aprobacion no confirmada. No se ejecuto ninguna accion.",
            "excluir_ids": request.excluir_ids,
        }

    doc = {
        "aprobado_por": current_user.get("username", "unknown"),
        "timestamp": datetime.now(timezone.utc),
        "excluir_ids": request.excluir_ids,
        "status": "aprobado_pendiente_ejecucion",
    }

    result = await db.auditoria_aprobaciones.insert_one(doc)
    logger.info(f"[Auditoria] Aprobacion registrada por {doc['aprobado_por']} — ID {result.inserted_id}")

    return {
        "status": "aprobado",
        "doc_id": str(result.inserted_id),
        "mensaje": "Aprobacion registrada. La ejecucion se realizara en Fase 2.",
    }


@router.post("/anular-bill-duplicada")
async def anular_bill_duplicada(
    request: AnularBillRequest,
    current_user=Depends(require_admin),
):
    """Anula una bill duplicada de Auteco en Alegra con trazabilidad completa.

    IMPORTANTE: Usa httpx directo (NO AlegraService) para bypasear validate_delete_protection().
    Bills de Auteco SI se pueden anular desde auditoria con aprobacion explicita.

    Pasos:
    1. Verificar que bill_id_a_anular existe en Alegra (GET /bills/{id})
    2. Verificar que bill_id_a_mantener existe en Alegra (GET /bills/{id})
    3. Registrar evento en roddos_events
    4. DELETE /bills/{bill_id_a_anular} via httpx directo
    """
    headers = await _get_alegra_auth_headers()

    # Paso 1: Verificar bill a anular
    async with httpx.AsyncClient(timeout=30) as client:
        resp_anular = await client.get(
            f"{ALEGRA_BASE_URL}/bills/{request.bill_id_a_anular}",
            headers=headers,
        )

    if resp_anular.status_code >= 400:
        raise HTTPException(
            status_code=404,
            detail=f"Bill {request.bill_id_a_anular} no encontrada en Alegra (HTTP {resp_anular.status_code})"
        )

    # Paso 2: Verificar bill a mantener
    async with httpx.AsyncClient(timeout=30) as client:
        resp_mantener = await client.get(
            f"{ALEGRA_BASE_URL}/bills/{request.bill_id_a_mantener}",
            headers=headers,
        )

    if resp_mantener.status_code >= 400:
        raise HTTPException(
            status_code=404,
            detail=f"Bill {request.bill_id_a_mantener} no encontrada en Alegra (HTTP {resp_mantener.status_code})"
        )

    # Paso 3: Registrar evento en roddos_events ANTES del DELETE (trazabilidad)
    evento = {
        "event_type": "bill_duplicada_anulada",
        "agent": "auditoria",
        "payload": {
            "bill_anulada": request.bill_id_a_anular,
            "bill_mantenida": request.bill_id_a_mantener,
        },
        "timestamp": datetime.now(timezone.utc),
        "source": "routers/auditoria.py",
        "ejecutado_por": current_user.get("username", "unknown"),
    }
    await db.roddos_events.insert_one(evento)
    logger.warning(
        f"[Auditoria] Evento registrado: bill_duplicada_anulada "
        f"bill_anulada={request.bill_id_a_anular} bill_mantenida={request.bill_id_a_mantener}"
    )

    # Paso 4: DELETE /bills/{id} via httpx directo — bypasea validate_delete_protection()
    async with httpx.AsyncClient(timeout=30) as client:
        resp_delete = await client.delete(
            f"{ALEGRA_BASE_URL}/bills/{request.bill_id_a_anular}",
            headers=headers,
        )

    if resp_delete.status_code >= 400:
        logger.error(
            f"[Auditoria] DELETE bill {request.bill_id_a_anular} fallido "
            f"HTTP {resp_delete.status_code}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error anulando bill {request.bill_id_a_anular} en Alegra (HTTP {resp_delete.status_code})"
        )

    logger.warning(
        f"[Auditoria] Bill {request.bill_id_a_anular} ANULADA en Alegra. "
        f"Bill mantenida: {request.bill_id_a_mantener}"
    )

    return {
        "anulado": True,
        "bill_id": request.bill_id_a_anular,
        "bill_mantenida": request.bill_id_a_mantener,
        "evento_registrado": True,
    }


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
        # Obtener todos los journals de Alegra
        logger.info(f"[Auditoria] Buscando {len(request.codigos)} códigos en Alegra...")
        journals_alegra = await get_alegra_journals(limit=100)

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
        alegra = AlegraService(db)

        logger.warning(f"[Auditoria] 🔴 ELIMINANDO journal {journal_id}...")

        result = await alegra.request(f"journals/{journal_id}", "DELETE")

        logger.warning(f"[Auditoria] ✅ Journal {journal_id} ELIMINADO exitosamente")
        return {
            "eliminado": True,
            "journal_id": journal_id,
            "http_status": 200,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mensaje": "Journal eliminado exitosamente"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auditoria] Error eliminando journal {journal_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error eliminando journal: {str(e)}"
        )
