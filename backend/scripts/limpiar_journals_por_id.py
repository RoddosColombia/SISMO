"""
limpiar_journals_por_id.py — Elimina journals de 2026 en Alegra por rango de IDs.

ESTRATEGIA: Bypasea GET /journals (que da TIMEOUT) y hace DELETE directo.
  - DELETE /journals/{id} -> 200/204: eliminado
  - DELETE /journals/{id} -> 404: no existe, skip silencioso
  - DELETE /journals/{id} -> otro: log de error

SEGURIDAD:
  - DELETE /journals/{id} solo afecta comprobantes de diario
  - Invoices viven en /invoices — completamente separados e intocables
  - Bills viven en /bills — completamente separados e intocables
  - Los 404 son inofensivos: el ID simplemente no existe

RANGO DE IDS:
  Del historial del proyecto, los journals de conciliación enero 2026
  están en el rango ~100 a ~960. Se prueba ese rango completo.
  Los IDs ya eliminados (25-35, 85, 88, 91, 682-700) darán 404 — OK.

Uso desde Render Shell:
    python scripts/limpiar_journals_por_id.py
"""

import asyncio
import base64
import os
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")

ALEGRA_EMAIL = os.environ["ALEGRA_EMAIL"]
ALEGRA_TOKEN = os.environ["ALEGRA_TOKEN"]
ALEGRA_BASE  = "https://api.alegra.com/api/v1"

# Rango de IDs a intentar eliminar
# Ajustar si el historial indica otro rango
ID_DESDE = 100
ID_HASTA = 1100  # conservador — los 404 son inocuos


def make_headers():
    creds = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


async def main():
    print("=" * 65)
    print("LIMPIEZA JOURNALS POR RANGO DE IDs — RODDOS S.A.S.")
    print(f"Intentando DELETE para IDs {ID_DESDE} a {ID_HASTA}")
    print("404 = no existe (inofensivo). Invoices/bills: intocables.")
    print("=" * 65)

    eliminados  = 0
    no_existe   = 0
    errores     = 0
    error_ids   = []

    headers = make_headers()

    async with httpx.AsyncClient(timeout=10) as client:
        for jid in range(ID_DESDE, ID_HASTA + 1):
            try:
                resp = await client.delete(
                    f"{ALEGRA_BASE}/journals/{jid}",
                    headers=headers,
                )

                if resp.status_code in (200, 201, 204):
                    eliminados += 1
                    print(f"  ELIMINADO  id={jid}")

                elif resp.status_code == 404:
                    no_existe += 1
                    # silencioso — la mayoría de IDs no existirán

                else:
                    errores += 1
                    error_ids.append(jid)
                    print(f"  ERROR      id={jid}  HTTP {resp.status_code}: {resp.text[:80]}")

            except httpx.TimeoutException:
                errores += 1
                error_ids.append(jid)
                print(f"  TIMEOUT    id={jid} — contando como error")

            # Pequeña pausa para no saturar la API
            await asyncio.sleep(0.15)

            # Reporte parcial cada 100 IDs
            if (jid - ID_DESDE + 1) % 100 == 0:
                pct = (jid - ID_DESDE + 1) / (ID_HASTA - ID_DESDE + 1) * 100
                print(f"\n  --- Progreso: {jid}/{ID_HASTA} ({pct:.0f}%) "
                      f"| eliminados={eliminados} no_existe={no_existe} errores={errores} ---\n")

    print(f"\n{'='*65}")
    print(f"RESULTADO FINAL")
    print(f"{'='*65}")
    print(f"  Rango intentado:  {ID_DESDE} — {ID_HASTA} ({ID_HASTA - ID_DESDE + 1} IDs)")
    print(f"  Eliminados:       {eliminados}")
    print(f"  No existían:      {no_existe}")
    print(f"  Errores:          {errores}")
    if error_ids:
        print(f"  IDs con error:    {error_ids}")
    print()
    if eliminados > 0:
        print(f"  {eliminados} journals eliminados. Alegra limpio para 2026.")
    else:
        print("  Ningún journal eliminado — ya estaba limpio o rango incorrecto.")
    if errores > 0:
        print(f"  ATENCIÓN: {errores} errores — revisar manualmente.")


if __name__ == "__main__":
    asyncio.run(main())
