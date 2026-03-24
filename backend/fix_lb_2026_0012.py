"""
Migration script: Recalculate LB-2026-0012 (Andrés Ovalles)
Fix: 52 cuotas semanales with quincenal value → 26 cuotas quincenales

Run: cd backend && python fix_lb_2026_0012.py
"""
import asyncio
import os
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

CODIGO = "LB-2026-0012"
EXPECTED_PLAN = "P52S"
EXPECTED_MODO = "quincenal"
VALOR_CUOTA = 395_781
NUM_CUOTAS = 26
INTERVALO_DIAS = 14
PRIMER_PAGO = date(2026, 4, 1)  # Wednesday April 1, 2026


def verify_wednesday(d: date) -> bool:
    return d.weekday() == 2  # 2 = Wednesday


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # 1. Find the loanbook
    loan = await db.loanbook.find_one({"codigo": CODIGO}, {"_id": 0})
    if not loan:
        print(f"ERROR: Loanbook {CODIGO} not found")
        return

    print(f"Found: {loan['codigo']} — {loan.get('cliente_nombre')}")
    print(f"  Plan: {loan.get('plan')} | Modo: {loan.get('modo_pago')} | Cuotas actuales: {len(loan.get('cuotas', []))}")

    # 2. Verify plan and modo_pago
    if loan.get("plan") != EXPECTED_PLAN:
        print(f"WARNING: Plan is '{loan.get('plan')}', expected '{EXPECTED_PLAN}'")
    if loan.get("modo_pago") != EXPECTED_MODO:
        print(f"  Updating modo_pago from '{loan.get('modo_pago')}' to '{EXPECTED_MODO}'")

    # 3. Keep cuota inicial (numero=0)
    cuotas = loan.get("cuotas", [])
    cuota_0 = next((c for c in cuotas if c.get("numero") == 0), None)
    if cuota_0:
        print(f"  Cuota inicial: valor={cuota_0.get('valor')} estado={cuota_0.get('estado')}")
    else:
        print("  WARNING: No cuota inicial found — creating placeholder")
        cuota_0 = {
            "numero": 0, "tipo": "inicial",
            "fecha_vencimiento": loan.get("fecha_factura", "2026-03-20"),
            "valor": loan.get("cuota_inicial", 0),
            "estado": "pendiente", "fecha_pago": None,
            "valor_pagado": 0.0, "alegra_payment_id": None,
            "comprobante": None, "notas": "",
        }

    # 4. Regenerate cuotas 1 to 26
    new_cuotas = [cuota_0]
    today_str = date.today().isoformat()

    print(f"\n  Generating {NUM_CUOTAS} cuotas quincenales:")
    print(f"  Primer pago: {PRIMER_PAGO} (Wednesday: {verify_wednesday(PRIMER_PAGO)})")

    for i in range(1, NUM_CUOTAS + 1):
        fecha_cuota = PRIMER_PAGO + timedelta(days=INTERVALO_DIAS * (i - 1))
        assert verify_wednesday(fecha_cuota), f"Cuota {i} ({fecha_cuota}) is NOT a Wednesday!"
        estado = "vencida" if fecha_cuota.isoformat() < today_str else "pendiente"
        new_cuotas.append({
            "numero": i,
            "tipo": "quincenal",
            "fecha_vencimiento": fecha_cuota.isoformat(),
            "valor": VALOR_CUOTA,
            "estado": estado,
            "fecha_pago": None,
            "valor_pagado": 0.0,
            "alegra_payment_id": None,
            "comprobante": None,
            "notas": "",
        })
        if i <= 3 or i == NUM_CUOTAS:
            print(f"    Cuota {i:2d}: {fecha_cuota} ({fecha_cuota.strftime('%A')}) — {estado}")

    # 5 & 6. Calculate new saldo
    saldo_pendiente = NUM_CUOTAS * VALOR_CUOTA
    print(f"\n  Total cuotas: {len(new_cuotas)} (1 inicial + {NUM_CUOTAS} quincenales)")
    print(f"  Saldo pendiente: ${saldo_pendiente:,.0f}")
    print(f"  Verification: {NUM_CUOTAS} × ${VALOR_CUOTA:,} = ${saldo_pendiente:,}")

    # 7. Update MongoDB
    update = {
        "cuotas": new_cuotas,
        "num_cuotas": NUM_CUOTAS,
        "modo_pago": EXPECTED_MODO,
        "saldo_pendiente": saldo_pendiente,
        "valor_financiado": saldo_pendiente,
    }

    result = await db.loanbook.update_one({"codigo": CODIGO}, {"$set": update})
    print(f"\n  MongoDB update: matched={result.matched_count}, modified={result.modified_count}")

    # Verify
    updated = await db.loanbook.find_one({"codigo": CODIGO}, {"_id": 0, "cuotas": 1, "num_cuotas": 1, "saldo_pendiente": 1})
    print(f"  Verified: {len(updated.get('cuotas', []))} cuotas, num_cuotas={updated.get('num_cuotas')}, saldo=${updated.get('saldo_pendiente'):,.0f}")
    print("\nDONE!")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
