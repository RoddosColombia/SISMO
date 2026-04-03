"""
limpiar_journals_2026.py — Elimina todos los journals de 2026 en Alegra
creados por conciliación bancaria.

REGLA CRÍTICA APRENDIDA EN PRODUCCIÓN:
  NUNCA usar date_afterOrNow / date_beforeOrNow como params en GET /journals.
  Causan TIMEOUT en offset=0 de forma consistente (bug de Alegra confirmado).
  Estrategia correcta: paginar SIN filtros de fecha, filtrar localmente.

SEGURIDAD:
  - NUNCA toca invoices ni bills — solo type=='journal' o sin type
  - Solo elimina journals donde date >= 2026-01-01
  - Muestra lista completa antes de borrar (sin --force no borra nada)

Uso desde Render Shell:
    python scripts/limpiar_journals_2026.py          # solo lista
    python scripts/limpiar_journals_2026.py --force  # lista + elimina
"""

import asyncio
import base64
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")

ALEGRA_EMAIL = os.environ["ALEGRA_EMAIL"]
ALEGRA_TOKEN = os.environ["ALEGRA_TOKEN"]
ALEGRA_BASE  = "https://api.alegra.com/api/v1"
FORCE        = "--force" in sys.argv
DESDE        = "2026-01-01"  # filtro local


def headers():
    creds = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


async def paginar_todos_journals(client) -> list:
    """
    Pagina GET /journals SIN filtros de fecha (evita timeout de Alegra).
    Retorna todos los journals que existen en la cuenta.
    Se detiene al recibir un batch vacío o con menos de `limit` ítems.
    """
    todos = []
    offset = 0
    limit  = 30
    MAX_PAGINAS = 100  # tope de seguridad (3.000 registros)

    print("  Paginando GET /journals (sin filtros de fecha — evita timeout)...")

    for pagina in range(MAX_PAGINAS):
        try:
            resp = await client.get(
                f"{ALEGRA_BASE}/journals",
                headers=headers(),
                params={"limit": limit, "offset": offset},
                timeout=20,
            )
        except httpx.TimeoutException:
            print(f"  TIMEOUT en offset={offset} — reintentando en 3s...")
            await asyncio.sleep(3)
            continue  # reintenta el mismo offset

        if resp.status_code != 200:
            print(f"  ERROR Alegra {resp.status_code}: {resp.text[:200]}")
            break

        batch = resp.json()
        if not batch or not isinstance(batch, list):
            break  # fin de la paginación

        todos.extend(batch)
        print(f"    página {pagina+1}: {len(batch)} journals (total={len(todos)}, offset={offset})")

        if len(batch) < limit:
            break  # última página

        offset += limit
        await asyncio.sleep(0.3)

    return todos


async def eliminar_journal(client, journal_id) -> bool:
    try:
        resp = await client.delete(
            f"{ALEGRA_BASE}/journals/{journal_id}",
            headers=headers(),
            timeout=15,
        )
        return resp.status_code in (200, 201, 204, 404)
    except httpx.TimeoutException:
        print(f"    TIMEOUT eliminando id={journal_id}")
        return False


async def main():
    print("=" * 65)
    print("LIMPIEZA JOURNALS 2026 — RODDOS S.A.S.")
    print("Paginación sin filtros de fecha (estrategia correcta).")
    print("Solo elimina journals. Invoices y bills: intocables.")
    print("=" * 65)

    async with httpx.AsyncClient() as client:

        # ── FASE 1: OBTENER TODOS ────────────────────────────────────────
        print("\nFASE 1 — Obteniendo todos los journals de Alegra...")
        todos = await paginar_todos_journals(client)
        print(f"\n  Total journals en cuenta: {len(todos)}")

        # ── FILTRAR LOCALMENTE POR FECHA ─────────────────────────────────
        de_2026 = [j for j in todos if (j.get("date") or "") >= DESDE]
        print(f"  Journals >= {DESDE}: {len(de_2026)}\n")

        if not de_2026:
            print("  Alegra ya está limpio para 2026. Nada que eliminar.")
            return

        # ── MOSTRAR LISTA ────────────────────────────────────────────────
        print(f"  {'ID':>8}  {'FECHA':<12}  {'MONTO':>14}  OBSERVACIONES")
        print(f"  {'-'*8}  {'-'*12}  {'-'*14}  {'-'*40}")

        total_monto = 0
        for j in de_2026:
            entries = j.get("entries") or []
            monto = max(
                sum(e.get("debit",  0) or 0 for e in entries),
                sum(e.get("credit", 0) or 0 for e in entries),
            )
            total_monto += monto
            obs = (j.get("observations") or "")[:50]
            print(f"  {str(j.get('id')):>8}  {j.get('date'):<12}  ${monto:>13,.0f}  {obs}")

        print(f"\n  TOTAL MONTO:    ${total_monto:,.0f}")
        print(f"  TOTAL JOURNALS: {len(de_2026)}")

        if not FORCE:
            print("\n" + "=" * 65)
            print("  Sin --force: solo se listó. Para eliminar ejecutar:")
            print("  python scripts/limpiar_journals_2026.py --force")
            print("=" * 65)
            return

        # ── FASE 2: ELIMINAR ─────────────────────────────────────────────
        print(f"\nFASE 2 — Eliminando {len(de_2026)} journals...")
        eliminados = 0
        errores    = 0

        for j in de_2026:
            jid = j.get("id")
            obs = (j.get("observations") or "")[:40]
            ok  = await eliminar_journal(client, jid)
            if ok:
                eliminados += 1
                print(f"  OK  id={str(jid):<8} | {j.get('date')} | {obs}")
            else:
                errores += 1
                print(f"  ERR id={str(jid):<8} | {j.get('date')} | {obs}")
            await asyncio.sleep(0.3)

        print(f"\n{'='*65}")
        print(f"RESULTADO FINAL")
        print(f"{'='*65}")
        print(f"  Journals encontrados: {len(de_2026)}")
        print(f"  Eliminados:           {eliminados}")
        print(f"  Errores:              {errores}")
        if errores == 0:
            print("\n  Alegra limpio. Listo para reprocesar extractos.")
        else:
            print(f"\n  {errores} errores — revisar manualmente en app.alegra.com.")


if __name__ == "__main__":
    asyncio.run(main())
