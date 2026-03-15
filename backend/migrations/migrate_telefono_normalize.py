"""migrate_telefono_normalize.py — Normaliza todos los teléfonos en BD al formato +57XXXXXXXXXX.

Colecciones afectadas:
  - loanbook.cliente_telefono
  - crm_clientes.telefono_principal
  - crm_clientes.telefono_alternativo

Es idempotente: puede ejecutarse múltiples veces sin efectos secundarios.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import motor.motor_asyncio
from services.crm_service import normalizar_telefono


async def run_migration():
    mongo_url = os.environ.get("MONGO_URL")
    db_name   = os.environ.get("DB_NAME")
    client    = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    db        = client[db_name]

    # ── 1. Normalizar loanbook.cliente_telefono ──────────────────────────────
    lb_total = 0
    lb_updated = 0
    async for loan in db.loanbook.find({}, {"_id": 0, "id": 1, "cliente_telefono": 1}):
        tel_raw = loan.get("cliente_telefono", "")
        tel_norm = normalizar_telefono(tel_raw)
        lb_total += 1
        if tel_norm != tel_raw:
            await db.loanbook.update_one(
                {"id": loan["id"]},
                {"$set": {"cliente_telefono": tel_norm}},
            )
            lb_updated += 1
            print(f"  [loanbook] {loan['id']}: '{tel_raw}' → '{tel_norm}'")

    print(f"\nloanbook: {lb_total} revisados, {lb_updated} actualizados")

    # ── 2. Normalizar crm_clientes.telefono_principal + telefono_alternativo ─
    crm_total = 0
    crm_updated = 0
    async for cli in db.crm_clientes.find(
        {}, {"_id": 0, "id": 1, "telefono_principal": 1, "telefono_alternativo": 1}
    ):
        updates = {}
        tp_raw  = cli.get("telefono_principal", "")
        ta_raw  = cli.get("telefono_alternativo", "")
        tp_norm = normalizar_telefono(tp_raw)
        ta_norm = normalizar_telefono(ta_raw) if ta_raw else ta_raw

        if tp_norm != tp_raw:
            updates["telefono_principal"] = tp_norm
            print(f"  [crm] {cli['id']}: principal '{tp_raw}' → '{tp_norm}'")
        if ta_raw and ta_norm != ta_raw:
            updates["telefono_alternativo"] = ta_norm
            print(f"  [crm] {cli['id']}: alternativo '{ta_raw}' → '{ta_norm}'")

        crm_total += 1
        if updates:
            await db.crm_clientes.update_one({"id": cli["id"]}, {"$set": updates})
            crm_updated += 1

    print(f"crm_clientes: {crm_total} revisados, {crm_updated} actualizados")
    print("\nMigración completada.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
