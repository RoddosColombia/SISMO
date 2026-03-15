"""migrate_inventario_from_loanbook.py — Backfill idempotente de inventario_motos desde loanbook.

Para cada préstamo en loanbook:
  - Si ya existe una moto en inventario_motos con el mismo chasis → skip.
  - Si no existe → crear con estado "Vendida" y datos del préstamo.

Es idempotente: puede ejecutarse múltiples veces sin crear duplicados.
"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import motor.motor_asyncio


async def run_migration():
    mongo_url = os.environ.get("MONGO_URL")
    db_name   = os.environ.get("DB_NAME")
    client    = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    db        = client[db_name]

    total = 0
    created = 0
    skipped = 0

    async for loan in db.loanbook.find(
        {},
        {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1,
         "moto_id": 1, "moto_descripcion": 1,
         "precio_venta": 1, "fecha_factura": 1,
         "factura_alegra_id": 1, "factura_numero": 1,
         "estado": 1, "created_at": 1},
    ):
        total += 1
        moto_id    = loan.get("moto_id", "")
        moto_desc  = loan.get("moto_descripcion", "")
        loan_id    = loan.get("id", "")

        # Si ya existe un inventario con este moto_id (y no está vacío) → skip
        if moto_id:
            existing = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0, "id": 1})
            if existing:
                skipped += 1
                continue

        # Intentar parsear marca/version de moto_descripcion
        partes = (moto_desc or "").split(" ", 1)
        marca   = partes[0] if partes else ""
        version = partes[1] if len(partes) > 1 else ""

        # Estado del inventario depende del estado del préstamo
        estado_inv = "Vendida"  # todos los loanbook representan motos vendidas

        inv_doc = {
            "id": moto_id if moto_id else str(uuid.uuid4()),
            "marca": marca,
            "version": version,
            "descripcion": moto_desc,
            "estado": estado_inv,
            "costo": 0.0,
            "total": float(loan.get("precio_venta", 0)),
            "factura_alegra_id": loan.get("factura_alegra_id", ""),
            "factura_numero": loan.get("factura_numero", ""),
            "chasis": "",
            "motor": "",
            "proveedor": "",
            "fecha_venta": loan.get("fecha_factura", ""),
            "cliente_nombre": loan.get("cliente_nombre", ""),
            "loanbook_id": loan_id,
            "loanbook_codigo": loan.get("codigo", ""),
            "created_at": loan.get("created_at", ""),
            "fuente": "migration_loanbook",
        }

        # Evitar duplicado por loanbook_id
        existing_lb = await db.inventario_motos.find_one(
            {"loanbook_id": loan_id}, {"_id": 0, "id": 1}
        )
        if existing_lb:
            skipped += 1
            continue

        await db.inventario_motos.insert_one(inv_doc)
        created += 1
        print(f"  [inventario] Creado: {moto_desc} — {loan.get('codigo','?')} ({loan.get('cliente_nombre','?')})")

    print(f"\nloanbook: {total} préstamos revisados")
    print(f"inventario_motos: {created} creados, {skipped} ya existían")
    print("Migración completada.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
