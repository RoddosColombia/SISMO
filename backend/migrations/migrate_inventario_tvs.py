"""
Migración de Inventario TVS — RODDOS
- Elimina registros fantasma (Honda, Yamaha)
- Elimina 10 placeholders PENDIENTE-LB-XXXX
- Carga 33 motos TVS reales con upsert por chasis
- Cruza con facturas Alegra para asignar VINs a loanbooks
- Registra 2 bills en Alegra (E670155732, E670156766)
- Agrega a cfo_deudas como productivas
"""
import asyncio
import os
import sys
import uuid
import re
import httpx
from datetime import datetime, timezone
from base64 import b64encode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import motor.motor_asyncio

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ALEGRA_USER = os.environ.get("ALEGRA_USER", "")
ALEGRA_TOKEN = os.environ.get("ALEGRA_TOKEN", "")
ALEGRA_BASE = "https://app.alegra.com/api/r1"

# ── 33 motos TVS reales ──────────────────────────────────────────────────────

MOTOS_TVS = [
    # FACTURA E670155732 — 25/02/2026 — 10 Raider 125 Negro Nebulosa
    {"chasis": "9FL25AF31VDB95058", "motor": "BF3AT18C2356", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF32VDB95022", "motor": "BF3AT14C2502", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF32VDB95036", "motor": "BF3AT15C2406", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF33VDB95059", "motor": "BF3AT13C2342", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF35VDB95046", "motor": "BF3AT13C2568", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF36VDB95055", "motor": "BF3AT18C2341", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF38VDB95025", "motor": "BF3AT15C2331", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF39VDB95048", "motor": "BF3AT15C2365", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF3XVDB95043", "motor": "BF3AT15C2580", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FL25AF3XVDB95057", "motor": "BF3AT13C2338", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    # 13 Sport 100 ELS Negro Azul
    {"chasis": "9FLT81000VDB62403", "motor": "RF5AT14A5361", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81000VDB62417", "motor": "RF5AT17A5427", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81001VDB62264", "motor": "RF5AT1XA5588", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81001VDB62314", "motor": "RF5AT16A5561", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81003VDB62265", "motor": "RF5AT15A5593", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81003VDB62329", "motor": "RF5AT11A5603", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81003VDB62413", "motor": "RF5AT18A5448", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81004VDB62260", "motor": "RF5AT17A5597", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81005VDB62414", "motor": "RF5AT1XA5494", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81006VDB62258", "motor": "RF5AT11A5581", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81006VDB62261", "motor": "RF5AT14A5515", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT81008VDB62410", "motor": "RF5AT12A5432", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    {"chasis": "9FLT8100XVDB62263", "motor": "RF5AT11A5524", "modelo": "Sport 100 ELS", "color": "Negro Azul",
     "marca": "TVS", "referencia": "60006459", "año": 2027, "precio_compra": 4157461,
     "factura_compra": "E670155732", "fecha_compra": "2026-02-25"},
    # FACTURA E670156766 — 05/03/2026 — 6 Raider 125 Negro Nebulosa
    {"chasis": "9FL25AF30VDB96072", "motor": "BF3AV14L1887", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF31VDB95190", "motor": "BF3AV10L1705", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF34VDB95376", "motor": "BF3AV14L1412", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF35VDB95371", "motor": "BF3AV17L1441", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF35VDB96052", "motor": "BF3AV11L1858", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF36VDB96075", "motor": "BF3AV19L1754", "modelo": "Raider 125", "color": "Negro Nebulosa",
     "marca": "TVS", "referencia": "60006449", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    # 4 Raider 125 Slate Green
    {"chasis": "9FL25AF30VDB95987", "motor": "BF3AV14L1853", "modelo": "Raider 125", "color": "Slate Green",
     "marca": "TVS", "referencia": "60006450", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF30VDB96167", "motor": "BF3AV11L0917", "modelo": "Raider 125", "color": "Slate Green",
     "marca": "TVS", "referencia": "60006450", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF33VDB95997", "motor": "BF3AV19L1950", "modelo": "Raider 125", "color": "Slate Green",
     "marca": "TVS", "referencia": "60006450", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
    {"chasis": "9FL25AF35VDB95984", "motor": "BF3AV11L1937", "modelo": "Raider 125", "color": "Slate Green",
     "marca": "TVS", "referencia": "60006450", "año": 2027, "precio_compra": 5638974,
     "factura_compra": "E670156766", "fecha_compra": "2026-03-05"},
]

# ── VIN regex patterns ────────────────────────────────────────────────────────
VIN_PATTERN = re.compile(r'9FL[A-Z0-9]{14,17}', re.IGNORECASE)
MOTOR_PATTERN = re.compile(r'(BF3[A-Z0-9]{6,12}|RF5[A-Z0-9]{6,12})', re.IGNORECASE)


async def alegra_get(path: str) -> dict:
    """GET request to Alegra API."""
    if not ALEGRA_USER or not ALEGRA_TOKEN:
        return {}
    token = b64encode(f"{ALEGRA_USER}:{ALEGRA_TOKEN}".encode()).decode()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{ALEGRA_BASE}/{path}",
            headers={"Authorization": f"Basic {token}"},
        )
        if resp.status_code == 200:
            return resp.json()
        return {}


async def alegra_post(path: str, payload: dict) -> dict:
    """POST request to Alegra API."""
    if not ALEGRA_USER or not ALEGRA_TOKEN:
        return {}
    token = b64encode(f"{ALEGRA_USER}:{ALEGRA_TOKEN}".encode()).decode()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{ALEGRA_BASE}/{path}",
            json=payload,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
        )
        data = resp.json()
        return data


async def run_migration():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    results = {}

    print("\n════════════════════════════════════════════════")
    print("MIGRACIÓN INVENTARIO TVS — RODDOS")
    print("════════════════════════════════════════════════\n")

    # ── PASO 1: Diagnóstico inicial ───────────────────────────────────────────
    total_antes = await db.inventario_motos.count_documents({})
    print(f"[DIAGNÓSTICO] Total motos antes: {total_antes}")

    fantasmas = await db.inventario_motos.find(
        {"$or": [{"marca": "Honda"}, {"marca": "Yamaha"}, {"chasis": {"$regex": "^PENDIENTE-LB-"}}]},
        {"_id": 1, "id": 1, "marca": 1, "modelo": 1, "chasis": 1}
    ).to_list(20)
    print(f"[DIAGNÓSTICO] Registros a eliminar: {len(fantasmas)}")
    for f in fantasmas:
        print(f"  → id={f.get('id','?')} | marca={f.get('marca','?')} | chasis={f.get('chasis','?')}")

    # ── PASO 2: Eliminar fantasmas y placeholders ─────────────────────────────
    deleted_ids = [f["_id"] for f in fantasmas]
    eliminados_data = []
    for f in fantasmas:
        moto_full = await db.inventario_motos.find_one({"_id": f["_id"]})
        if moto_full:
            moto_full["_id"] = str(moto_full["_id"])
            eliminados_data.append(moto_full)

    if deleted_ids:
        del_result = await db.inventario_motos.delete_many({"_id": {"$in": deleted_ids}})
        print(f"\n[PASO 2] Eliminados {del_result.deleted_count} registros fantasma/placeholder")
        results["eliminados"] = del_result.deleted_count

        # Registrar en eventos
        await db.roddos_events.insert_one({
            "event_type": "inventario.limpieza.ejecutada",
            "motivo": "Migración: eliminación de registros fantasma y placeholders sin VIN real",
            "registros_eliminados": eliminados_data,
            "timestamp": now,
            "ejecutado_por": "migration_inventario_tvs",
        })
    else:
        print("[PASO 2] No hay registros a eliminar.")
        results["eliminados"] = 0

    # ── PASO 3: Cargar 33 motos TVS reales ────────────────────────────────────
    upserted = 0
    skipped = 0
    for moto in MOTOS_TVS:
        chasis = moto["chasis"]
        # Verificar si ya existe
        existing = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0, "id": 1, "estado": 1})
        if existing:
            skipped += 1
            continue

        doc = {
            "id": str(uuid.uuid4()),
            "marca": moto["marca"],
            "modelo": moto["modelo"],
            "version": moto["modelo"],
            "chasis": moto["chasis"],
            "motor": moto["motor"],
            "color": moto["color"],
            "referencia": moto["referencia"],
            "año": moto["año"],
            "precio_compra": moto["precio_compra"],
            "factura_compra": moto["factura_compra"],
            "fecha_compra": moto["fecha_compra"],
            "estado": "Disponible",
            "total": moto["precio_compra"],
            "costo": moto["precio_compra"],
            "placa": "",
            "propietario": "",
            "ubicacion": "Local Calle 127",
            "created_at": now,
            "updated_at": now,
        }
        await db.inventario_motos.insert_one(doc)
        upserted += 1

    print(f"\n[PASO 3] Motos TVS cargadas: {upserted} nuevas, {skipped} ya existían")
    results["motos_cargadas"] = upserted
    results["motos_ya_existian"] = skipped

    total_despues = await db.inventario_motos.count_documents({})
    print(f"[PASO 3] Total motos ahora: {total_despues}")
    results["total_despues"] = total_despues

    # ── PASO 4: Cruzar con facturas Alegra para asignar VINs ─────────────────
    print("\n[PASO 4] Cruzando loanbooks con facturas Alegra...")
    lbs = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}},
        {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "factura_alegra_id": 1, "estado": 1, "moto_chasis": 1},
    ).to_list(20)

    cruzados = 0
    sin_cruzar = []

    for lb in lbs:
        factura_id = lb.get("factura_alegra_id")
        if not factura_id:
            sin_cruzar.append({"codigo": lb["codigo"], "cliente": lb["cliente_nombre"], "motivo": "Sin factura_alegra_id"})
            continue

        # Consultar la factura en Alegra
        try:
            factura = await alegra_get(f"invoices/{factura_id}")
        except Exception as e:
            print(f"  Error consultando factura {factura_id}: {e}")
            sin_cruzar.append({"codigo": lb["codigo"], "cliente": lb["cliente_nombre"], "motivo": f"Error Alegra: {e}"})
            continue

        if not factura or not factura.get("items"):
            sin_cruzar.append({"codigo": lb["codigo"], "cliente": lb["cliente_nombre"], "motivo": "Factura sin items en Alegra"})
            continue

        # Buscar VIN en los items
        chasis_encontrado = None
        motor_encontrado = None
        modelo_encontrado = None
        color_encontrado = None

        for item in factura.get("items", []):
            texto = (
                item.get("name", "") + " " +
                item.get("description", "") + " " +
                item.get("observations", "")
            ).upper()

            vin_m = VIN_PATTERN.search(texto)
            if vin_m:
                chasis_encontrado = vin_m.group().strip()

            motor_m = MOTOR_PATTERN.search(texto)
            if motor_m:
                motor_encontrado = motor_m.group().strip()

            for modelo in ["RAIDER 125", "SPORT 100"]:
                if modelo in texto:
                    modelo_encontrado = modelo.title()
                    break
            for color in ["NEGRO NEBULOSA", "SLATE GREEN", "NEGRO AZUL"]:
                if color in texto:
                    color_encontrado = color.title()
                    break

        if chasis_encontrado:
            # Actualizar loanbook
            lb_estado = lb.get("estado", "activo")
            moto_estado = "Entregada" if lb_estado == "activo" else "Vendida"
            await db.loanbook.update_one(
                {"id": lb["id"]},
                {"$set": {
                    "moto_chasis": chasis_encontrado,
                    "motor": motor_encontrado,
                    "modelo_moto": modelo_encontrado,
                    "color_moto": color_encontrado,
                    "updated_at": now,
                }},
            )
            # Actualizar moto en inventario
            await db.inventario_motos.update_one(
                {"chasis": chasis_encontrado},
                {"$set": {
                    "estado": moto_estado,
                    "propietario": lb["cliente_nombre"],
                    "fecha_venta": now[:10],
                    "loanbook_id": lb["id"],
                    "loanbook_codigo": lb["codigo"],
                    "updated_at": now,
                }},
            )
            cruzados += 1
            print(f"  ✅ {lb['codigo']} — {lb['cliente_nombre'][:25]} → VIN: {chasis_encontrado}")
        else:
            sin_cruzar.append({
                "codigo": lb["codigo"],
                "cliente": lb["cliente_nombre"],
                "motivo": "VIN no encontrado en descripción de items de la factura",
                "factura_id": str(factura_id),
            })
            print(f"  ⚠️ {lb['codigo']} — {lb['cliente_nombre'][:25]} → Sin VIN en factura {factura_id}")

    results["loanbooks_cruzados"] = cruzados
    results["loanbooks_sin_cruzar"] = sin_cruzar

    print(f"\n[PASO 4] Resultado: {cruzados}/10 loanbooks cruzados con VIN")
    if sin_cruzar:
        print(f"  ⚠️ {len(sin_cruzar)} sin cruzar:")
        for s in sin_cruzar:
            print(f"     • {s['codigo']} | {s['cliente'][:25]} | {s['motivo']}")

    # ── PASO 5: Registrar bills en Alegra ─────────────────────────────────────
    print("\n[PASO 5] Registrando bills en Alegra...")

    # Buscar ID de Auteco en Alegra
    auteco_id = None
    try:
        contacts = await alegra_get("contacts?type=provider&identification=890900317")
        if isinstance(contacts, list) and contacts:
            auteco_id = contacts[0].get("id")
        elif isinstance(contacts, dict) and contacts.get("id"):
            auteco_id = contacts.get("id")

        # Fallback: buscar por nombre
        if not auteco_id:
            contacts2 = await alegra_get("contacts?type=provider")
            if isinstance(contacts2, list):
                for c in contacts2:
                    nombre = c.get("name", "").upper()
                    nit = str(c.get("identification", {}).get("number", "") if isinstance(c.get("identification"), dict) else c.get("identification", ""))
                    if "AUTOTECNICA" in nombre or "AUTECO" in nombre or "890900317" in nit or "890.900.317" in nit:
                        auteco_id = c.get("id")
                        print(f"  Auteco encontrado: {c.get('name')} — ID: {auteco_id}")
                        break
    except Exception as e:
        print(f"  Error buscando Auteco: {e}")

    if not auteco_id:
        print("  ⚠️ No se encontró Auteco en Alegra — omitiendo registro de bills")
        results["bills_alegra"] = "Auteco no encontrado en Alegra"
    else:
        bills_to_create = [
            {
                "date": "2026-02-25",
                "dueDate": "2026-05-26",
                "paymentForm": "CREDIT",
                "provider": {"id": str(auteco_id)},
                "observations": "Factura de compra E670155732 — 23 motos TVS (10 Raider 125 + 13 Sport 100 ELS) - AUTORRETENEDOR, sin ReteFuente",
                "purchases": {
                    "items": [
                        {
                            "name": "Raider 125 Negro Nebulosa — Ref 60006449 (x10)",
                            "quantity": 10,
                            "price": 5638974,
                            "tax": [{"id": "4"}],
                        },
                        {
                            "name": "Sport 100 ELS Negro Azul — Ref 60006459 (x13)",
                            "quantity": 13,
                            "price": 4157461,
                            "tax": [{"id": "4"}],
                        },
                    ]
                },
                "_ref": "E670155732",
                "_total_esperado": 132668200,
            },
            {
                "date": "2026-03-05",
                "dueDate": "2026-06-03",
                "paymentForm": "CREDIT",
                "provider": {"id": str(auteco_id)},
                "observations": "Factura de compra E670156766 — 10 motos TVS Raider 125 (6 Negro Nebulosa + 4 Slate Green) - AUTORRETENEDOR, sin ReteFuente",
                "purchases": {
                    "items": [
                        {
                            "name": "Raider 125 Negro Nebulosa — Ref 60006449 (x6)",
                            "quantity": 6,
                            "price": 5638974,
                            "tax": [{"id": "4"}],
                        },
                        {
                            "name": "Raider 125 Slate Green — Ref 60006450 (x4)",
                            "quantity": 4,
                            "price": 5638974,
                            "tax": [{"id": "4"}],
                        },
                    ]
                },
                "_ref": "E670156766",
                "_total_esperado": 67741277,
            },
        ]

        bills_results = []
        for bill_data in bills_to_create:
            ref = bill_data.pop("_ref")
            total_esp = bill_data.pop("_total_esperado")

            # Check if already exists in cfo_deudas
            existing_deuda = await db.cfo_deudas.find_one({"referencia_externa": ref})
            if existing_deuda:
                print(f"  ℹ️ Deuda {ref} ya existe en cfo_deudas — omitiendo")
                bills_results.append({"ref": ref, "status": "ya_existe"})
                continue

            try:
                bill_result = await alegra_post("bills", bill_data)
                bill_id = bill_result.get("id")
                if bill_id:
                    print(f"  ✅ Bill {ref} creado en Alegra — ID: {bill_id}")
                    bills_results.append({"ref": ref, "alegra_id": bill_id, "status": "creado"})
                else:
                    print(f"  ⚠️ Bill {ref} — respuesta Alegra: {bill_result}")
                    bills_results.append({"ref": ref, "status": "error", "resp": str(bill_result)[:200]})
                    bill_id = None
            except Exception as e:
                print(f"  ❌ Error creando bill {ref}: {e}")
                bills_results.append({"ref": ref, "status": "error", "error": str(e)})
                bill_id = None

            # Agregar a cfo_deudas como productiva
            await db.cfo_deudas.insert_one({
                "id": str(uuid.uuid4()),
                "tipo": "productiva",
                "descripcion": f"Factura compra motos TVS — {ref}",
                "referencia_externa": ref,
                "acreedor": "Autotecnica Colombiana S.A.S. (Auteco)",
                "nit_acreedor": "890900317",
                "monto_total": float(total_esp),
                "saldo_pendiente": float(total_esp),
                "fecha_inicio": bill_data.get("date"),
                "fecha_vencimiento": bill_data.get("dueDate"),
                "estado": "activa",
                "alegra_bill_id": str(bill_id) if bill_id else None,
                "es_autoretenedor": True,
                "notas": "Sin ReteFuente — autorretenedor confirmado",
                "created_at": now,
                "updated_at": now,
            })
            print(f"  ✅ Deuda {ref} agregada a cfo_deudas — ${total_esp:,.0f}")

        results["bills_alegra"] = bills_results

    # ── PASO 6: Resumen final ─────────────────────────────────────────────────
    total_final = await db.inventario_motos.count_documents({})
    disponibles = await db.inventario_motos.count_documents({"estado": "Disponible"})
    vendidas = await db.inventario_motos.count_documents({"estado": "Vendida"})
    entregadas = await db.inventario_motos.count_documents({"estado": "Entregada"})
    honda_check = await db.inventario_motos.count_documents({"marca": "Honda"})
    yamaha_check = await db.inventario_motos.count_documents({"marca": "Yamaha"})
    pendiente_check = await db.inventario_motos.count_documents({"chasis": {"$regex": "^PENDIENTE-LB-"}})

    print("\n════════════════════════════════════════════════")
    print("RESUMEN FINAL")
    print("════════════════════════════════════════════════")
    print(f"Total motos:          {total_final}")
    print(f"Disponibles:          {disponibles}")
    print(f"Vendidas:             {vendidas}")
    print(f"Entregadas:           {entregadas}")
    print(f"Suma D+V+E:           {disponibles + vendidas + entregadas}")
    print(f"Honda en sistema:     {honda_check} (debe ser 0)")
    print(f"Yamaha en sistema:    {yamaha_check} (debe ser 0)")
    print(f"PENDIENTE-LB:         {pendiente_check} (debe ser 0)")
    print(f"Loanbooks con VIN:    {cruzados}/10")
    print("════════════════════════════════════════════════")

    results["total_final"] = total_final
    results["disponibles"] = disponibles
    results["vendidas"] = vendidas
    results["entregadas"] = entregadas
    results["tests"] = {
        "total_33": total_final == 33,
        "sin_honda": honda_check == 0,
        "sin_yamaha": yamaha_check == 0,
        "sin_pendiente": pendiente_check == 0,
    }

    return results


if __name__ == "__main__":
    asyncio.run(run_migration())
