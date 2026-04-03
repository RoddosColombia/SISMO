"""limpiar_hash_extracto.py — Elimina el hash del extracto Bancolombia enero 2026
que está bloqueando el reprocesamiento.

Busca por nombre de archivo o por banco=bancolombia, sin depender del formato de fecha.

Uso desde Render Shell (ya en ~/project/src/backend):
    python scripts/limpiar_hash_extracto.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ.get("DB_NAME", "roddos")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    col = db.conciliacion_extractos_procesados

    print("="*60)
    print("DIAGNÓSTICO — conciliacion_extractos_procesados")
    print("="*60)

    # Ver TODOS los documentos existentes
    todos = await col.find({}, {"_id": 1, "hash": 1, "banco": 1,
                                "filename": 1, "created_at": 1,
                                "journals_creados": 1}).to_list(100)

    print(f"  Total documentos en colección: {len(todos)}")
    for d in todos:
        h = str(d.get("hash", ""))[:16]
        print(f"  _id={d['_id']} | banco={d.get('banco')} | file={d.get('filename')} | "
              f"journals={d.get('journals_creados')} | hash={h}... | at={d.get('created_at')}")

    if not todos:
        print("  Colección vacía — no hay nada que eliminar.")
        client.close()
        return

    # Buscar el de Bancolombia enero 2026
    # Puede estar por banco='bancolombia' o filename contiene 'Bancolombia'
    candidatos = []
    for d in todos:
        banco = str(d.get("banco", "")).lower()
        fname = str(d.get("filename", "")).lower()
        if "bancolombia" in banco or "bancolombia" in fname:
            candidatos.append(d)

    print(f"\n  Candidatos Bancolombia: {len(candidatos)}")

    if not candidatos:
        # Si no hay filtro por banco, eliminar el más reciente
        print("  No hay filtro por banco — mostrando todos para eliminación manual.")
        print("  Ejecuta: db.conciliacion_extractos_procesados.deleteOne({_id: ObjectId('...')})")
        client.close()
        return

    # Eliminar todos los de Bancolombia (puede haber más de uno si falló antes)
    ids = [d["_id"] for d in candidatos]
    result = await col.delete_many({"_id": {"$in": ids}})
    print(f"\n  ELIMINADOS: {result.deleted_count} documento(s)")
    print("  El extracto Bancolombia enero puede volver a procesarse.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
