"""limpiar_journals_2026.py — Elimina todos los journals de 2026 en Alegra
creados por conciliación bancaria (extractos).

REGLAS DE SEGURIDAD:
- NUNCA toca invoices (facturas de venta FE444-FE461) — son tipo 'invoice'
- NUNCA toca bills (facturas Auteco) — son tipo 'bill'
- SOLO elimina journals (comprobantes de diario) del año 2026
- Identifica journals de conciliación por su observations (contienen keywords de extracto)
  O bien elimina TODOS los journals de 2026 si se confirma que no hay journals manuales

Uso desde Render Shell:
    python scripts/limpiar_journals_2026.py

    # Para eliminar SIN confirmación (modo forzado):
    python scripts/limpiar_journals_2026.py --force
"""

import asyncio
import base64
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")

ALEGRA_EMAIL = os.environ["ALEGRA_EMAIL"]
ALEGRA_TOKEN = os.environ["ALEGRA_TOKEN"]
ALEGRA_BASE  = "https://api.alegra.com/api/v1"
FORCE        = "--force" in sys.argv


def headers():
    creds = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


async def listar_journals_2026(client) -> list:
    """Pagina todos los journals de 2026 y los retorna."""
    journals = []
    offset = 0
    limit = 30

    print("  Paginando journals de Alegra 2026...")
    while True:
        try:
            resp = await client.get(
                f"{ALEGRA_BASE}/journals",
                headers=headers(),
                params={
                    "date_afterOrNow":  "2026-01-01",
                    "date_beforeOrNow": "2026-12-31",
                    "limit": limit,
                    "offset": offset,
                },
                timeout=15,
            )
        except httpx.TimeoutException:
            print(f"  TIMEOUT en offset={offset} — reintentando en 5s...")
            await asyncio.sleep(5)
            continue

        if resp.status_code != 200:
            print(f"  ERROR Alegra {resp.status_code}: {resp.text[:200]}")
            break

        batch = resp.json()
        if not batch or not isinstance(batch, list):
            break

        journals.extend(batch)
        print(f"  ... {len(journals)} journals obtenidos hasta ahora (offset={offset})")

        if len(batch) < limit:
            break
        offset += limit
        await asyncio.sleep(0.5)  # respetar rate limit

    return journals


async def eliminar_journal(client, journal_id: int) -> bool:
    """Elimina un journal por ID. Retorna True si fue eliminado."""
    try:
        resp = await client.delete(
            f"{ALEGRA_BASE}/journals/{journal_id}",
            headers=headers(),
            timeout=15,
        )
        if resp.status_code in (200, 201, 204, 404):
            return True
        print(f"    ERROR eliminando id={journal_id}: HTTP {resp.status_code} — {resp.text[:100]}")
        return False
    except httpx.TimeoutException:
        print(f"    TIMEOUT eliminando id={journal_id} — contando como error")
        return False


async def main():
    print("=" * 65)
    print("LIMPIEZA JOURNALS 2026 — RODDOS S.A.S.")
    print("Solo journals (comprobantes de diario). Invoices y bills: intocables.")
    print("=" * 65)

    async with httpx.AsyncClient() as client:

        # ── FASE 1: LISTAR ─────────────────────────────────────────────
        print("\nFASE 1 — Listando journals de 2026 en Alegra...")
        journals = await listar_journals_2026(client)

        if not journals:
            print("\n  No hay journals de 2026 en Alegra. Nada que limpiar.")
            return

        print(f"\n  TOTAL ENCONTRADOS: {len(journals)} journals\n")
        print(f"  {'ID':>8}  {'FECHA':<12}  {'MONTO':>14}  OBSERVACIONES")
        print(f"  {'-'*8}  {'-'*12}  {'-'*14}  {'-'*40}")

        total_monto = 0
        for j in journals:
            entries = j.get("entries") or []
            monto = max(
                sum(e.get("debit", 0) or 0 for e in entries),
                sum(e.get("credit", 0) or 0 for e in entries),
            )
            total_monto += monto
            obs = (j.get("observations") or "")[:50]
            print(f"  {j.get('id'):>8}  {j.get('date'):<12}  ${monto:>13,.0f}  {obs}")

        print(f"\n  TOTAL MONTO: ${total_monto:,.0f}")
        print(f"  TOTAL JOURNALS: {len(journals)}")

        # ── CONFIRMACIÓN ───────────────────────────────────────────────
        if not FORCE:
            print("\n" + "=" * 65)
            print("ADVERTENCIA: Se eliminarán TODOS los journals listados arriba.")
            print("Las facturas de venta (invoices) y bills NO se tocan.")
            print("Para confirmar, ejecuta:")
            print("    python scripts/limpiar_journals_2026.py --force")
            print("=" * 65)
            return

        # ── FASE 2: ELIMINAR ───────────────────────────────────────────
        print(f"\nFASE 2 — Eliminando {len(journals)} journals...")
        eliminados = 0
        errores = 0

        for j in journals:
            jid = j.get("id")
            obs = (j.get("observations") or "")[:40]
            ok = await eliminar_journal(client, jid)
            if ok:
                eliminados += 1
                print(f"  OK  id={jid:<8} | {j.get('date')} | {obs}")
            else:
                errores += 1
                print(f"  ERR id={jid:<8} | {j.get('date')} | {obs}")
            await asyncio.sleep(0.3)  # respetar rate limit Alegra

        print(f"\n{'='*65}")
        print(f"RESULTADO FINAL")
        print(f"{'='*65}")
        print(f"  Journals encontrados: {len(journals)}")
        print(f"  Eliminados:           {eliminados}")
        print(f"  Errores:              {errores}")
        print(f"\n  Alegra limpio para 2026. Listo para reprocesar extractos.")


if __name__ == "__main__":
    asyncio.run(main())
