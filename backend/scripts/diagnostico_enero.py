"""diagnostico_enero.py — Diagnóstico extracto Bancolombia enero 2026 procesado hoy.

PASO 1: Ver job de hoy en conciliacion_jobs
PASO 2: Listar journals creados en Alegra (date >= 2026-01-01)
PASO 3: Eliminar hash del extracto de conciliacion_extractos_procesados

Uso desde Render Shell (ya en ~/project/src/backend):
    python scripts/diagnostico_enero.py
"""

import asyncio
import os
import base64
from datetime import datetime, timezone, date
from pathlib import Path
from dotenv import load_dotenv
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ.get("DB_NAME", "roddos")
ALEGRA_EMAIL = os.environ["ALEGRA_EMAIL"]
ALEGRA_TOKEN = os.environ["ALEGRA_TOKEN"]
ALEGRA_BASE  = "https://api.alegra.com/api/v1"

HOY = date.today().isoformat()  # 2026-04-03


def alegra_headers():
    creds = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


async def paso1_jobs(db):
    print("\n" + "="*60)
    print("PASO 1 — Jobs de conciliación creados HOY")
    print("="*60)

    jobs = await db.conciliacion_jobs.find(
        {"created_at": {"$regex": f"^{HOY}"}},
        {"_id": 0, "job_id": 1, "created_at": 1, "banco": 1, "estado": 1,
         "journals_creados": 1, "movimientos_procesados": 1, "filename": 1}
    ).sort("created_at", -1).to_list(20)

    if not jobs:
        print("  Sin jobs de hoy en conciliacion_jobs.")
    for j in jobs:
        print(f"  job_id:              {j.get('job_id')}")
        print(f"  created_at:          {j.get('created_at')}")
        print(f"  banco:               {j.get('banco')}")
        print(f"  estado:              {j.get('estado')}")
        print(f"  journals_creados:    {j.get('journals_creados')}")
        print(f"  movimientos_proc:    {j.get('movimientos_procesados')}")
        print(f"  filename:            {j.get('filename')}")
        print()

    return jobs


async def paso2_journals_alegra():
    print("="*60)
    print("PASO 2 — Journals en Alegra con date >= 2026-01-01")
    print("="*60)

    headers = alegra_headers()
    all_journals = []
    offset = 0
    limit = 30

    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            resp = await client.get(
                f"{ALEGRA_BASE}/journals",
                headers=headers,
                params={"limit": limit, "offset": offset, "date_afterOrNow": "2026-01-01"},
            )
            if resp.status_code >= 400:
                print(f"  ERROR Alegra {resp.status_code}: {resp.text[:200]}")
                break
            batch = resp.json()
            if not batch or not isinstance(batch, list):
                break
            all_journals.extend(batch)
            if len(batch) < limit:
                break
            offset += limit

    print(f"  Total journals encontrados: {len(all_journals)}\n")
    for j in all_journals:
        entries = j.get("entries") or []
        total = max(
            sum(e.get("debit", 0) for e in entries),
            sum(e.get("credit", 0) for e in entries),
        )
        obs = (j.get("observations") or "")[:60]
        print(f"  ID {j.get('id'):>8} | {j.get('date')} | ${total:>14,.0f} | {obs}")

    return all_journals


async def paso3_eliminar_hash(db):
    print("\n" + "="*60)
    print("PASO 3 — Eliminar hash extracto de hoy en conciliacion_extractos_procesados")
    print("="*60)

    # Buscar docs creados hoy
    docs = await db.conciliacion_extractos_procesados.find(
        {"created_at": {"$regex": f"^{HOY}"}},
        {"_id": 1, "hash": 1, "banco": 1, "created_at": 1, "journals_creados": 1}
    ).to_list(20)

    if not docs:
        print("  Sin documentos de hoy en conciliacion_extractos_procesados.")
        return 0

    for d in docs:
        print(f"  Encontrado: hash={d.get('hash')[:12]}... banco={d.get('banco')} journals={d.get('journals_creados')} at={d.get('created_at')}")

    ids = [d["_id"] for d in docs]
    result = await db.conciliacion_extractos_procesados.delete_many({"_id": {"$in": ids}})
    print(f"\n  ELIMINADOS: {result.deleted_count} documento(s) — extracto listo para reprocesar.")
    return result.deleted_count


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    await paso1_jobs(db)
    await paso2_journals_alegra()
    deleted = await paso3_eliminar_hash(db)

    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)
    print(f"  Hashes eliminados de conciliacion_extractos_procesados: {deleted}")
    print("  Journals de Alegra: NO tocados (solo listados).")
    print("  Extracto listo para reprocesar cuando lo indiques.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
