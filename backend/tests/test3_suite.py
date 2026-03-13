"""TEST 3 — Validación DPD, Mora 15%EA, Scores, Protocolo, Migración.

Casos según spec del usuario:
  3A — DPD y Buckets
  3B — Fórmula de Mora 15%EA
  3C — Scores A+..E
  3D — Protocolo recuperación + performance
  3E — Migración: campos BUILD 3 presentes en todos los loanbooks

Ejecutar: cd /app/backend && python tests/test3_suite.py
"""
import asyncio
import sys
import os
import time
import math
from datetime import date, timedelta, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ["DB_NAME"]

# Tasa mora idéntica a la del scheduler
TASA_MORA_DIARIA: float = (1.15 ** (1 / 365)) - 1  # ≈ 0.00038426


# ── Helpers ──────────────────────────────────────────────────────────────────

def past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()

def future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()

def mora_esperada(valor: float, dpd: int) -> float:
    return round(valor * ((1 + TASA_MORA_DIARIA) ** dpd - 1), 2)

PASS = "[✅ PASS]"
FAIL = "[❌ FAIL]"

results: list[dict] = []

def check(name: str, expected, actual, tolerance: float = 1.0) -> bool:
    """Verifica expected==actual (con tolerancia para floats)."""
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        ok = abs(float(actual) - float(expected)) <= tolerance
    else:
        ok = actual == expected
    icon = PASS if ok else FAIL
    print(f"  {icon} {name}")
    if not ok:
        print(f"       expected={expected!r}  got={actual!r}")
    results.append({"name": name, "ok": ok, "expected": expected, "actual": actual})
    return ok


# ── Datos de prueba ───────────────────────────────────────────────────────────

def make_lb(lb_id: str, codigo: str, cuotas: list, gestiones: list | None = None) -> dict:
    base = {
        "id": lb_id, "codigo": codigo,
        "estado": "activo",
        "cliente_nombre": f"Test {codigo}",
        "plan": "P52S",
        "cuotas": cuotas,
        "dpd_actual": 0, "dpd_bucket": "0", "dpd_maximo_historico": 0,
        "score_pago": None, "estrella_nivel": None,
        "interes_mora_acumulado": 0.0,
        "ptp_fecha": None, "ptp_monto": None, "ptp_registrado_por": None,
        "gestiones": gestiones or [],
        "reestructuraciones": [], "score_historial": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return base

def cuota_pendiente(n: int, valor: float, vencimiento: str) -> dict:
    return {
        "numero": n, "tipo": "cuota",
        "fecha_vencimiento": vencimiento,
        "valor": valor, "estado": "pendiente",
        "fecha_pago": None, "valor_pagado": 0.0,
    }

def cuota_pagada(n: int, valor: float, vencimiento: str, dpd_al_pagar: int = 0) -> dict:
    return {
        "numero": n, "tipo": "cuota",
        "fecha_vencimiento": vencimiento,
        "valor": valor, "estado": "pagada",
        "fecha_pago": past(1), "valor_pagado": valor,
        "dpd_al_pagar": dpd_al_pagar,
    }


async def setup_test_data(db) -> None:
    """Elimina e inserta los loanbooks de prueba."""
    await db.loanbook.delete_many({"codigo": {"$regex": "^TEST3-"}})

    loanbooks = [
        # 3A-1: cuota vencida 10 días
        make_lb("test3-lb001", "TEST3-LB001",
                [cuota_pendiente(1, 175_000, past(10))]),

        # 3A-2: todas las cuotas pagadas → DPD=0
        make_lb("test3-lb002", "TEST3-LB002", [
            cuota_pagada(1, 160_000, past(30), dpd_al_pagar=0),
            cuota_pagada(2, 160_000, past(23), dpd_al_pagar=0),
        ]),

        # 3A-3: cuota vencida 1 día
        make_lb("test3-lb003", "TEST3-LB003",
                [cuota_pendiente(1, 130_000, past(1))]),

        # 3B-1: $175.000 DPD=9
        make_lb("test3-lb004", "TEST3-LB004",
                [cuota_pendiente(1, 175_000, past(9))]),

        # 3B-2: $160.000 DPD=21
        make_lb("test3-lb005", "TEST3-LB005",
                [cuota_pendiente(1, 160_000, past(21))]),

        # 3B-3: $130.000 DPD=0 (no vencida) → mora=0
        make_lb("test3-lb006", "TEST3-LB006",
                [cuota_pendiente(1, 130_000, future(7))]),

        # 3C-1: score A+ — 0 vencidas históricas, no_contesto_ratio<10%
        make_lb("test3-lb007", "TEST3-LB007", [
            cuota_pagada(1, 120_000, past(14), dpd_al_pagar=0),
            cuota_pendiente(2, 120_000, future(7)),
        ], gestiones=[{"resultado": "contactado", "ptp_fue_cumplido": None}]),

        # 3C-2: dpd=5 + ptp_ratio >= 0.8 → score B
        make_lb("test3-lb008", "TEST3-LB008",
                [cuota_pendiente(1, 175_000, past(5))],
                gestiones=[
                    {"resultado": "prometió_pago", "ptp_fue_cumplido": True},
                    {"resultado": "prometió_pago", "ptp_fue_cumplido": True},
                    {"resultado": "prometió_pago", "ptp_fue_cumplido": True},
                    {"resultado": "prometió_pago", "ptp_fue_cumplido": True},
                    {"resultado": "prometió_pago", "ptp_fue_cumplido": True},
                ]),

        # 3C-3 + 3D: dpd=22 → score E, estrellas=0, protocolo, estado=recuperacion
        make_lb("test3-lb009", "TEST3-LB009",
                [cuota_pendiente(1, 175_000, past(22))]),
    ]

    for lb in loanbooks:
        await db.loanbook.insert_one(lb)
        lb.pop("_id", None)

    print(f"  [SETUP] Insertados {len(loanbooks)} loanbooks de prueba (TEST3-LB001..009)")


# ── Test suite ────────────────────────────────────────────────────────────────

async def run_tests() -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db     = client[DB_NAME]

    print("\n" + "=" * 65)
    print("  TEST 3 — DPD · Mora 15%EA · Scores · Protocolo · Migración")
    print("=" * 65)

    # ── SETUP ──────────────────────────────────────────────────────────────────
    print("\n[SETUP] Creando datos de prueba...")
    await setup_test_data(db)

    # ── Importar y ejecutar el scheduler ─────────────────────────────────────
    print("\n[RUN] calcular_dpd_todos()...")
    # Import the scheduler functions, providing the module context it needs
    # The scheduler functions do `from database import db` — we need the same db
    from database import db as sched_db  # noqa: F401 — triggers connection setup
    from services.loanbook_scheduler import calcular_dpd_todos, calcular_scores

    t0 = time.monotonic()
    await calcular_dpd_todos()
    ms_dpd = (time.monotonic() - t0) * 1000
    print(f"  calcular_dpd_todos() completado en {ms_dpd:.0f} ms")

    print("\n[RUN] calcular_scores()...")
    await calcular_scores()
    print("  calcular_scores() completado")

    # ── TEST 3A — DPD ─────────────────────────────────────────────────────────
    print("\n── TEST 3A — DPD ──────────────────────────────────────────────")
    lb1 = await db.loanbook.find_one({"id": "test3-lb001"}, {"_id": 0})
    lb2 = await db.loanbook.find_one({"id": "test3-lb002"}, {"_id": 0})
    lb3 = await db.loanbook.find_one({"id": "test3-lb003"}, {"_id": 0})

    # 3A-1
    check("3A-1 dpd_actual=10",   10,        lb1.get("dpd_actual"))
    check("3A-1 bucket='8-14'",   "8-14",    lb1.get("dpd_bucket"))
    check("3A-1 estado='mora'",   "mora",    lb1.get("estado"))

    # 3A-2
    check("3A-2 dpd_actual=0",    0,         lb2.get("dpd_actual"))
    check("3A-2 bucket='0'",      "0",       lb2.get("dpd_bucket"))
    check("3A-2 estado='activo'", "activo",  lb2.get("estado"))

    # 3A-3
    check("3A-3 dpd_actual=1",    1,         lb3.get("dpd_actual"))
    check("3A-3 bucket='1-7'",    "1-7",     lb3.get("dpd_bucket"))
    check("3A-3 estado='mora'",   "mora",    lb3.get("estado"))

    # ── TEST 3B — Fórmula Mora ───────────────────────────────────────────────
    print("\n── TEST 3B — Fórmula Mora 15%EA ───────────────────────────────")
    lb4 = await db.loanbook.find_one({"id": "test3-lb004"}, {"_id": 0})
    lb5 = await db.loanbook.find_one({"id": "test3-lb005"}, {"_id": 0})
    lb6 = await db.loanbook.find_one({"id": "test3-lb006"}, {"_id": 0})

    esperada_b1 = mora_esperada(175_000, 9)
    esperada_b2 = mora_esperada(160_000, 21)

    print(f"  Tasa mora diaria  : {TASA_MORA_DIARIA:.8f}")
    print(f"  3B-1 mora esperada: ${esperada_b1:.0f} (175000 × DPD=9)")
    print(f"  3B-2 mora esperada: ${esperada_b2:.0f} (160000 × DPD=21)")

    mora_b1 = lb4.get("interes_mora_acumulado", 0)
    mora_b2 = lb5.get("interes_mora_acumulado", 0)
    mora_b3 = lb6.get("interes_mora_acumulado", 0)

    check("3B-1 mora $175k DPD=9  ≈ $606",  esperada_b1,  mora_b1, tolerance=5.0)
    check("3B-2 mora $160k DPD=21 ≈ $1296", esperada_b2,  mora_b2, tolerance=5.0)
    check("3B-3 mora $130k DPD=0  = $0",    0.0,          mora_b3)

    # ── TEST 3C — Scores ────────────────────────────────────────────────────
    print("\n── TEST 3C — Scores ────────────────────────────────────────────")
    lb7 = await db.loanbook.find_one({"id": "test3-lb007"}, {"_id": 0})
    lb8 = await db.loanbook.find_one({"id": "test3-lb008"}, {"_id": 0})
    lb9 = await db.loanbook.find_one({"id": "test3-lb009"}, {"_id": 0})

    check("3C-1 score='A+'",      "A+",  lb7.get("score_pago"))
    check("3C-1 estrellas=5",     5,     lb7.get("estrella_nivel"))

    check("3C-2 score='B'",       "B",   lb8.get("score_pago"))
    check("3C-2 estrellas=3",     3,     lb8.get("estrella_nivel"))

    check("3C-3 score='E'",       "E",   lb9.get("score_pago"))
    check("3C-3 estrellas=0",     0,     lb9.get("estrella_nivel"))

    # score_historial no sobreescrito, sino append
    hist7 = lb7.get("score_historial", [])
    hist9 = lb9.get("score_historial", [])
    check("3C-1 score_historial tiene entrada", True, len(hist7) >= 1)
    check("3C-3 score_historial tiene fecha",   True,
          len(hist9) >= 1 and "fecha" in hist9[-1])

    # ── TEST 3D — Protocolo + Performance ───────────────────────────────────
    print("\n── TEST 3D — Protocolo + Performance ──────────────────────────")
    # lb9 (DPD=22) should now be estado='recuperacion'
    check("3D-1 lb DPD=22 → estado='recuperacion'", "recuperacion", lb9.get("estado"))

    # Verificar evento en roddos_events
    evt = await db.roddos_events.find_one(
        {"event_type": "protocolo_recuperacion", "entity_id": "test3-lb009"},
        {"_id": 0}
    )
    check("3D-2 evento protocolo_recuperacion emitido", True, evt is not None)

    # GET /api/radar/queue performance — curl with timing
    import subprocess
    API_URL = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not API_URL:
        # Get from frontend .env
        fe_env = os.path.join(ROOT, "..", "frontend", ".env")
        if os.path.exists(fe_env):
            with open(fe_env) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        API_URL = line.strip().split("=", 1)[1]
                        break

    if API_URL:
        # Get auth token first
        import json
        res = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{API_URL}/api/auth/login",
             "-H", "Content-Type: application/json",
             "-d", '{"email":"contabilidad@roddos.com","password":"Admin@RODDOS2025!"}'],
            capture_output=True, text=True, timeout=15
        )
        try:
            token = json.loads(res.stdout).get("token", "")
        except Exception:
            token = ""

        if token:
            t0 = time.monotonic()
            res2 = subprocess.run(
                ["curl", "-s", f"{API_URL}/api/radar/queue",
                 "-H", f"Authorization: Bearer {token}"],
                capture_output=True, text=True, timeout=15
            )
            ms_queue = (time.monotonic() - t0) * 1000
            check("3D-3 GET /api/radar/queue < 200ms", True, ms_queue < 200,
                  tolerance=0)
            print(f"       queue respondió en {ms_queue:.0f} ms")

            # GET /api/radar/roll-rate → 0..100
            res3 = subprocess.run(
                ["curl", "-s", f"{API_URL}/api/radar/roll-rate",
                 "-H", f"Authorization: Bearer {token}"],
                capture_output=True, text=True, timeout=15
            )
            try:
                rr = json.loads(res3.stdout)
                rr_pct = rr.get("roll_rate_pct", -1)
                check("3D-4 roll-rate 0≤value≤100", True, 0 <= rr_pct <= 100)
                print(f"       roll_rate_pct={rr_pct}")
            except Exception as e:
                check("3D-4 roll-rate JSON válido", True, False)
        else:
            print("  [SKIP] 3D-3/3D-4 — no se pudo obtener token (API no disponible)")
    else:
        print("  [SKIP] 3D-3/3D-4 — REACT_APP_BACKEND_URL no configurada")

    # ── TEST 3E — Migración ─────────────────────────────────────────────────
    print("\n── TEST 3E — Migración ────────────────────────────────────────")
    total_loans     = await db.loanbook.count_documents({})
    missing_dpd     = await db.loanbook.count_documents({"dpd_actual":     {"$exists": False}})
    missing_score   = await db.loanbook.count_documents({"score_pago":     {"$exists": False}})
    missing_gest    = await db.loanbook.count_documents({"gestiones":      {"$exists": False}})
    missing_reestr  = await db.loanbook.count_documents({"reestructuraciones": {"$exists": False}})

    print(f"  Total loanbooks en DB: {total_loans}")
    check("3E-1 todos tienen dpd_actual",         0, missing_dpd)
    check("3E-2 todos tienen score_pago",          0, missing_score)
    check("3E-3 todos tienen gestiones[]",         0, missing_gest)
    check("3E-4 todos tienen reestructuraciones[]", 0, missing_reestr)

    # Verify cuotas originales intactas (sample check)
    lb_test = await db.loanbook.find_one({"id": "test3-lb001"}, {"_id": 0})
    cuotas_ok = (lb_test and len(lb_test.get("cuotas", [])) == 1
                 and lb_test["cuotas"][0]["valor"] == 175_000)
    check("3E-5 cuotas originales intactas (sample)", True, cuotas_ok)

    # ── Resumen ────────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed

    print("\n" + "=" * 65)
    print(f"  RESULTADO: {passed}/{total} PASS  |  {failed} FAIL")
    print("=" * 65)

    if failed > 0:
        print("\nCasos fallidos:")
        for r in results:
            if not r["ok"]:
                print(f"  ❌ {r['name']}")
                print(f"     expected={r['expected']!r}  got={r['actual']!r}")

    # Cleanup (opcional — dejar datos para inspeccion manual)
    # await db.loanbook.delete_many({"codigo": {"$regex": "^TEST3-"}})
    client.close()
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
