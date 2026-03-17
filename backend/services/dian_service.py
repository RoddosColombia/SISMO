"""
dian_service.py — BUILD 19: Consulta y causación automática de facturas DIAN.

Modo: SIMULACIÓN (Opción A)
La DIAN usa SOAP/XML con certificado digital. Este servicio simula la consulta
con datos realistas de proveedores reales de RODDOS. Para activar datos reales,
reemplazar `_consultar_simulado()` con un cliente SOAP o proveedor REST
(Alanube, Facturalatam, MATIAS API).
"""
import uuid
import logging
import random
import os
from datetime import datetime, timezone, timedelta, date

import httpx

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
DIAN_MODO = os.environ.get("DIAN_MODO", "simulacion")   # "simulacion" | "produccion"
DIAN_TOKEN = os.environ.get("DIAN_TOKEN", "")
DIAN_NIT = os.environ.get("DIAN_NIT", "9010126221")
DIAN_AMBIENTE = os.environ.get("DIAN_AMBIENTE", "habilitacion")
DIAN_BASE_URL = os.environ.get("DIAN_BASE_URL", "https://api.dian.gov.co/v1")

ALEGRA_EMAIL = os.environ.get("ALEGRA_EMAIL", "")
ALEGRA_TOKEN = os.environ.get("ALEGRA_TOKEN", "")

# ── Proveedores reales de RODDOS (para la simulación) ─────────────────────────
_PROVEEDORES_SIM = [
    {
        "nit": "890900317",
        "nombre": "Autotecnica Colombiana S.A.S. (Auteco)",
        "es_autoretenedor": True,
        "tipo_gasto": "inventario_motos",
        "descripcion_template": "Motos TVS — pedido mensual",
        "monto_base": 11_700_000,
        "monto_variacion": 3_000_000,
        "frecuencia_dias": 30,
    },
    {
        "nit": "830103942",
        "nombre": "Hacienda Inmobiliaria Hainsas S.A.S.",
        "es_autoretenedor": False,
        "tipo_gasto": "arriendo",
        "descripcion_template": "Arrendamiento sede comercial",
        "monto_base": 3_500_000,
        "monto_variacion": 0,
        "frecuencia_dias": 30,
    },
    {
        "nit": "860003020",
        "nombre": "BBVA Colombia S.A.",
        "es_autoretenedor": True,
        "tipo_gasto": "servicios_bancarios",
        "descripcion_template": "Cuota de manejo y servicios bancarios",
        "monto_base": 85_000,
        "monto_variacion": 15_000,
        "frecuencia_dias": 30,
    },
    {
        "nit": "890903938",
        "nombre": "Bancolombia S.A.",
        "es_autoretenedor": True,
        "tipo_gasto": "servicios_bancarios",
        "descripcion_template": "Servicios bancarios y comisiones",
        "monto_base": 120_000,
        "monto_variacion": 20_000,
        "frecuencia_dias": 30,
    },
]

_IVA_RATE = 0.19


def _generar_cufe(nit_emisor: str, numero: str, fecha: str) -> str:
    """Genera un CUFE sintético determinista para la simulación."""
    raw = f"{nit_emisor}{numero}{fecha}{DIAN_NIT}"
    import hashlib
    return hashlib.sha384(raw.encode()).hexdigest()


def _numero_factura(proveedor_idx: int, fecha: date) -> str:
    return f"FE-SIM-{proveedor_idx + 1}-{fecha.strftime('%Y%m')}"


def _consultar_simulado(fecha_desde: date, fecha_hasta: date) -> list[dict]:
    """Genera facturas simuladas para el rango de fechas solicitado."""
    facturas = []
    rng = random.Random(str(fecha_desde))   # seed determinista → misma fecha = mismas facturas

    for idx, proveedor in enumerate(_PROVEEDORES_SIM):
        # Generar 1 factura por proveedor si la fecha_desde está en el ciclo de emisión
        # Emite el día 1 de cada mes (para simplificar)
        emit_day = date(fecha_desde.year, fecha_desde.month, 1)
        if not (fecha_desde <= emit_day <= fecha_hasta):
            continue

        subtotal = proveedor["monto_base"] + rng.randint(0, max(1, proveedor["monto_variacion"]))
        iva = round(subtotal * _IVA_RATE)
        total = subtotal + iva
        numero = _numero_factura(idx, emit_day)
        cufe = _generar_cufe(proveedor["nit"], numero, emit_day.isoformat())

        facturas.append({
            "cufe": cufe,
            "nit_emisor": proveedor["nit"],
            "nombre_emisor": proveedor["nombre"],
            "numero_factura": numero,
            "fecha": emit_day.isoformat(),
            "descripcion": f"{proveedor['descripcion_template']} — {emit_day.strftime('%B %Y')}",
            "subtotal": subtotal,
            "iva": iva,
            "total": total,
            "tipo_gasto": proveedor["tipo_gasto"],
            "es_autoretenedor_emisor": proveedor["es_autoretenedor"],
            "fuente": "simulacion_dian",
        })

    return facturas


# ── Anti-duplicados ─────────────────────────────────────────────────────────────
async def ya_fue_procesada(cufe: str, db) -> bool:
    """3-layer anti-duplicate check."""
    # Capa 1 — colección dian_facturas_procesadas
    if await db.dian_facturas_procesadas.find_one({"cufe": cufe}, {"_id": 0}):
        return True
    # Capa 2 — bus de eventos
    if await db.roddos_events.find_one({"cufe": cufe, "event_type": "dian.factura.causada"}, {"_id": 0}):
        return True
    return False


async def _ya_existe_en_alegra(numero_factura: str) -> bool:
    """Capa 3 — verifica si el bill ya existe en Alegra."""
    if not ALEGRA_EMAIL or not ALEGRA_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://app.alegra.com/api/r1/bills",
                auth=(ALEGRA_EMAIL, ALEGRA_TOKEN),
                params={"fields": "id,numberTemplate", "limit": 30},
            )
            if r.status_code == 200:
                bills = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
                for b in bills:
                    nt = b.get("numberTemplate", {})
                    num = nt.get("number", "") if isinstance(nt, dict) else str(nt)
                    if str(num) == str(numero_factura):
                        return True
    except Exception as e:
        logger.warning("Alegra bills check failed: %s", e)
    return False


# ── Retenciones ────────────────────────────────────────────────────────────────
def _calcular_retenciones(subtotal: float, tipo_gasto: str, es_autoretenedor: bool) -> dict:
    if es_autoretenedor:
        return {"rete_fuente": 0, "rete_ica": 0, "nota": "autoretenedor — sin ReteFuente ni ReteICA"}
    rete_fuente_pct = {
        "arriendo": 0.035,
        "servicios_bancarios": 0.04,
        "inventario_motos": 0.025,
    }.get(tipo_gasto, 0.035)
    rete_ica_pct = 0.00414  # Bogotá estándar comercio
    return {
        "rete_fuente": round(subtotal * rete_fuente_pct),
        "rete_fuente_pct": rete_fuente_pct,
        "rete_ica": round(subtotal * rete_ica_pct),
        "rete_ica_pct": rete_ica_pct,
    }


# ── Causación en Alegra ─────────────────────────────────────────────────────────
async def causar_factura_en_alegra(factura: dict) -> dict | None:
    """Crea el bill en Alegra. Retorna el bill creado o None si falla."""
    if not ALEGRA_EMAIL or not ALEGRA_TOKEN:
        logger.warning("DIAN: ALEGRA_EMAIL/ALEGRA_TOKEN no configurados — bill no creado")
        return None

    due_date = (date.fromisoformat(factura["fecha"]) + timedelta(days=30)).isoformat()
    payload = {
        "date": factura["fecha"],
        "dueDate": due_date,
        "provider": {
            "identification": factura["nit_emisor"],
            "name": factura["nombre_emisor"],
        },
        "numberTemplate": {"number": factura["numero_factura"]},
        "items": [{
            "description": factura["descripcion"],
            "price": factura["subtotal"],
            "quantity": 1,
        }],
        "observations": (
            f"Causada automáticamente desde DIAN. "
            f"CUFE: {factura['cufe'][:16]}..."
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://app.alegra.com/api/r1/bills",
                auth=(ALEGRA_EMAIL, ALEGRA_TOKEN),
                json=payload,
            )
            if r.status_code in (200, 201):
                return r.json()
            logger.warning("Alegra bill creation HTTP %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        logger.error("DIAN causar_en_alegra error: %s", e)
    return None


# ── Función principal ───────────────────────────────────────────────────────────
async def consultar_facturas_dian(fecha_desde: str, fecha_hasta: str) -> list[dict]:
    """
    Consulta facturas electrónicas recibidas por RODDOS.
    Modo simulación: genera datos realistas desde proveedores reales.
    Modo producción: llama al proveedor REST configurado.
    """
    d_desde = date.fromisoformat(fecha_desde)
    d_hasta = date.fromisoformat(fecha_hasta)

    if DIAN_MODO == "produccion" and DIAN_TOKEN:
        # TODO: implementar llamada SOAP/REST real cuando haya certificado/proveedor
        # Se puede usar Alanube (GET /api/v1/documents/received) o MATIAS API
        logger.info("DIAN modo producción — integrando con proveedor real (pendiente)")
        return []  # fallback a vacío hasta que se configure el proveedor real

    return _consultar_simulado(d_desde, d_hasta)


async def sync_facturas_dian(fecha_desde: str, fecha_hasta: str, db) -> dict:
    """
    Sincronización completa: consulta DIAN → anti-duplicados → causación Alegra.
    Retorna resumen del proceso.
    """
    facturas = await consultar_facturas_dian(fecha_desde, fecha_hasta)
    procesadas, omitidas, errores = 0, 0, []
    now = datetime.now(timezone.utc).isoformat()

    for factura in facturas:
        cufe = factura["cufe"]
        numero = factura["numero_factura"]

        # Anti-duplicados capas 1 y 2
        if await ya_fue_procesada(cufe, db):
            omitidas += 1
            continue

        # Anti-duplicado capa 3 — Alegra
        if await _ya_existe_en_alegra(numero):
            omitidas += 1
            await db.dian_facturas_procesadas.insert_one({
                "cufe": cufe,
                "numero_factura": numero,
                "nit_emisor": factura["nit_emisor"],
                "nombre_emisor": factura["nombre_emisor"],
                "total": factura["total"],
                "fecha_factura": factura["fecha"],
                "fecha_causacion": now,
                "fuente": "ya_existia_en_alegra",
                "alegra_bill_id": None,
            })
            continue

        try:
            retenciones = _calcular_retenciones(
                factura["subtotal"], factura["tipo_gasto"], factura["es_autoretenedor_emisor"]
            )
            bill = await causar_factura_en_alegra(factura)
            alegra_id = bill.get("id") if bill else None

            await db.dian_facturas_procesadas.insert_one({
                "id": str(uuid.uuid4()),
                "cufe": cufe,
                "nit_emisor": factura["nit_emisor"],
                "nombre_emisor": factura["nombre_emisor"],
                "numero_factura": numero,
                "fecha_factura": factura["fecha"],
                "descripcion": factura["descripcion"],
                "subtotal": factura["subtotal"],
                "iva": factura["iva"],
                "total": factura["total"],
                "alegra_bill_id": alegra_id,
                "fecha_causacion": now,
                "fuente": factura.get("fuente", "dian"),
                "retenciones_aplicadas": retenciones,
            })
            await db.roddos_events.insert_one({
                "id": str(uuid.uuid4()),
                "event_type": "dian.factura.causada",
                "cufe": cufe,
                "proveedor": factura["nombre_emisor"],
                "numero_factura": numero,
                "total": factura["total"],
                "timestamp": now,
                "fuente": "sync_dian",
                "alegra_bill_id": alegra_id,
            })
            procesadas += 1

        except Exception as e:
            logger.error("DIAN error causando %s: %s", cufe[:16], e)
            errores.append({"cufe": cufe[:16], "error": str(e)})

    resumen = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "consultadas": len(facturas),
        "procesadas": procesadas,
        "omitidas": omitidas,
        "errores": len(errores),
        "detalle_errores": errores,
        "timestamp": now,
        "modo": DIAN_MODO,
    }

    await db.roddos_events.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": "dian.sync.completado",
        **resumen,
    })

    if errores:
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()),
            "tipo": "dian_error",
            "mensaje": f"DIAN sync {fecha_desde}: {len(errores)} facturas con error",
            "timestamp": now,
            "resuelta": False,
        })

    return resumen
