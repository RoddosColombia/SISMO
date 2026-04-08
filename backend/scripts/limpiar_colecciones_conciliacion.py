"""
limpiar_colecciones_conciliacion.py
=====================================
Limpia las colecciones MongoDB de control de conciliacion bancaria
para permitir reprocesar extractos desde cero sin duplicados.

Colecciones que borra:
  - conciliacion_movimientos_procesados  (hashes de movimientos ya causados)
  - conciliacion_extractos_procesados    (hashes de archivos ya procesados)
  - conciliacion_reintentos              (movimientos en cola de reintento)

NO toca: loanbook, inventario_motos, cartera_pagos, roddos_events,
          plan_cuentas_roddos, cxc_socios, cxc_clientes — nada operativo.

Render Shell:
  python scripts/limpiar_colecciones_conciliacion.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ.get("DB_NAME", "sismo_prod")

COLECCIONES_A_LIMPIAR = [
    "conciliacion_movimientos_procesados",
    "conciliacion_extractos_procesados",
    "conciliacion_reintentos",
]

COLECCIONES_PROTEGIDAS = [
    "loanbook", "inventario_motos", "cartera_pagos", "roddos_events",
    "plan_cuentas_roddos", "cxc_socios", "cxc_clientes", "alegra_credentials",
    "inventario_motos", "facturas_venta", "loanbook",
]


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print("=" * 60)
    print("LIMPIEZA COLECCIONES CONCILIACION — RODDOS SISMO")
    print(f"DB: {DB_NAME}")
    print("=" * 60)

    total_borrados = 0

    for coleccion in COLECCIONES_A_LIMPIAR:
        # Verificar que no es protegida (doble seguro)
        if coleccion in COLECCIONES_PROTEGIDAS:
            print(f"  ⛔ BLOQUEADO (protegida): {coleccion}")
            continue

        count_antes = await db[coleccion].count_documents({})
        if count_antes == 0:
            print(f"  ✅ {coleccion}: ya vacía (0 documentos)")
            continue

        result = await db[coleccion].delete_many({})
        borrados = result.deleted_count
        total_borrados += borrados
        print(f"  ✅ {coleccion}: {borrados} documentos eliminados")

    print()
    print(f"TOTAL ELIMINADOS: {total_borrados} documentos")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    print("Colecciones operativas intactas:")
    for col in ["loanbook", "inventario_motos", "cartera_pagos", "cxc_socios"]:
        count = await db[col].count_documents({})
        print(f"  {col}: {count} documentos — INTACTO ✅")

    print()
    print("MongoDB limpio para conciliación. Listo para los pasos 3 y 4.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
