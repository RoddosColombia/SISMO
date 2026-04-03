"""seed_contabilidad_backlog.py — Crea colección contabilidad_backlog con items pendientes Fase 3.

Idempotente: usa upsert por descripcion. Ejecutar una vez en Render Shell.

Uso desde Render Shell (ya en ~/project/src/backend):
    python scripts/seed_contabilidad_backlog.py
"""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Cargar .env si existe (local), en Render las vars ya están en el entorno
load_dotenv(Path(__file__).parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ.get("DB_NAME", "roddos")

FECHA_LIMITE = "2026-04-08"

BACKLOG_ITEMS = [
    {
        "descripcion": "PAGO PSE Banco Davivienda SA",
        "categoria": "clasificacion_pendiente",
        "banco": "bancolombia",
        "monto_referencia": "múltiples montos — revisar 1 a 1",
        "nota": "~15 movimientos enero. No es deuda personal de Andrés ni obligación conocida de RODDOS. Revisar cada monto individualmente.",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "PAGO PSE GOU PAYMENTS S.A EAS",
        "categoria": "identificar_proveedor",
        "banco": "bancolombia",
        "monto_referencia": "$176.810 y $207.640",
        "nota": "Identificar qué servicio es GOU PAYMENTS.",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "PAGO PSE PATRIMONIOS AUTONOMO",
        "categoria": "identificar_concepto",
        "banco": "bancolombia",
        "monto_referencia": "$3.000.000",
        "nota": "¿Es arriendo, deuda, fideicomiso, inversión?",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "PAGO PSE 101 FINTECH S.A.S.",
        "categoria": "identificar_proveedor",
        "banco": "bancolombia",
        "monto_referencia": "$34.470",
        "nota": "Identificar qué servicio es 101 FINTECH.",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "COMPRA INTL FEENKO APP",
        "categoria": "clasificar_operativo_vs_personal",
        "banco": "bancolombia",
        "monto_referencia": "~$70.000 (2 movimientos)",
        "nota": "¿Es herramienta de trabajo (→ 5484) o gasto personal (→ 5413)?",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "COMPRA EN LEGRAND HE",
        "categoria": "clasificar_operativo_vs_personal",
        "banco": "bancolombia",
        "monto_referencia": "$30.000",
        "nota": "¿Insumo eléctrico de oficina (→ 5483) o gasto personal (→ 5413)?",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "COMPRA EN REDH ANTAR",
        "categoria": "clasificar_operativo_vs_personal",
        "banco": "bancolombia",
        "monto_referencia": "$80.000",
        "nota": "Identificar comercio y clasificar.",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
    {
        "descripcion": "RETIRO CAJERO",
        "categoria": "clasificar_pendiente",
        "banco": "bancolombia",
        "monto_referencia": "$2.700.000 y $1.100.000",
        "nota": "Puede ser caja chica operativa, gasto personal o pago proveedor informal. No clasificar como salario diferido sin contexto.",
        "fecha_limite": FECHA_LIMITE,
        "estado": "pendiente",
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    col = db.contabilidad_backlog

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0

    for item in BACKLOG_ITEMS:
        doc = {**item, "created_at": now}
        result = await col.update_one(
            {"descripcion": item["descripcion"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
            print(f"  OK Insertado: {item['descripcion']}")
        else:
            skipped += 1
            print(f"  -- Ya existe: {item['descripcion']}")

    print(f"\nBacklog: {inserted} insertados, {skipped} ya existian.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
