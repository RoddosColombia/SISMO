"""eliminar_journals_directo.py — Elimina journals 2026 por ID directo.

No hace GET previo — usa la lista de IDs ya conocidos del diagnóstico anterior.
Cada DELETE tiene timeout de 10s. Sin loop infinito.

Uso desde Render Shell:
    python scripts/eliminar_journals_directo.py
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

# IDs confirmados del diagnóstico anterior — todos son pruebas/tests/incorrectos
IDS_A_ELIMINAR = [
    # Tests de builds anteriores
    25, 28, 29, 30, 31, 32, 33, 35, 85, 88, 91,
    # Pruebas agente contador miércoles
    699, 700,
    # Extracto Bancolombia febrero (procesado con reglas incorrectas)
    682, 683, 684, 685, 686, 687, 688, 689, 690,
    691, 692, 693, 694, 695, 696, 697, 698,
]


def headers():
    creds = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}


async def eliminar(client, jid: int) -> str:
    """Elimina un journal. Retorna 'OK', '404', o 'ERR:...'"""
    try:
        resp = await client.delete(
            f"{ALEGRA_BASE}/journals/{jid}",
            headers=headers(),
            timeout=10,
        )
        if resp.status_code in (200, 201, 204):
            return "OK"
        if resp.status_code == 404:
            return "404"
        return f"ERR:{resp.status_code}"
    except httpx.TimeoutException:
        return "TIMEOUT"
    except Exception as e:
        return f"ERR:{str(e)[:40]}"


async def main():
    print("=" * 60)
    print(f"ELIMINAR {len(IDS_A_ELIMINAR)} JOURNALS — RODDOS 2026")
    print("Invoices y bills: intocables.")
    print("=" * 60)

    ok = 0
    nf = 0
    err = 0

    async with httpx.AsyncClient() as client:
        for jid in IDS_A_ELIMINAR:
            resultado = await eliminar(client, jid)
            if resultado == "OK":
                ok += 1
                print(f"  OK   id={jid}")
            elif resultado == "404":
                nf += 1
                print(f"  404  id={jid}  (ya no existía)")
            else:
                err += 1
                print(f"  ERR  id={jid}  {resultado}")
            await asyncio.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"RESULTADO")
    print(f"{'='*60}")
    print(f"  Eliminados:   {ok}")
    print(f"  No existían:  {nf}")
    print(f"  Errores:      {err}")
    print(f"  Total:        {len(IDS_A_ELIMINAR)}")
    print(f"\n  Alegra limpio. Listo para procesar extractos.")


if __name__ == "__main__":
    asyncio.run(main())
