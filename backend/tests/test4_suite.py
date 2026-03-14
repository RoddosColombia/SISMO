"""TEST 4 — Validación funciones CFO: analizar_exposicion_tributaria,
analizar_flujo_caja, analizar_inventario, analizar_kpis_comerciales.

Casos:
  4A — analizar_exposicion_tributaria (IVA, retenciones, ICA 11.04‰, alertas DIAN)
  4B — analizar_flujo_caja (ingresos reales + proyectados, egresos bills, brecha)
  4C — analizar_inventario (días en stock, alertas >60 días)
  4D — analizar_kpis_comerciales (meta ventas, mix planes, tasa pago puntual)
  4E — GET /api/cfo/semaforo: impuestos ya no es siempre VERDE (dinámico)
  4F — ICA 11.04‰ en calculo real con ingresos

Ejecutar: cd /app/backend && python tests/test4_suite.py
"""
import asyncio
import sys
import os
import json
import subprocess
from datetime import date, timedelta, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ["DB_NAME"]

# ── Helper ──────────────────────────────────────────────────────────────────

def past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()

def future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()

PASS = "[✅ PASS]"
FAIL = "[❌ FAIL]"
results: list[dict] = []


def check(name: str, expected, actual, tolerance: float = 0.5) -> bool:
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


# ── Datos sintéticos para pruebas unitarias ──────────────────────────────────

def make_datos_base(
    bills=None,
    cartera_pagos=None,
    ingresos_proyectados=0,
    ventas_alegra=None,
    journals=None,
    motos=None,
    loans=None,
    presupuesto=None,
    cfo_cfg=None,
    cobrado_mes=0,
) -> dict:
    """Construye el dict datos con valores por defecto seguros."""
    hoy = date.today()
    return {
        "periodo":                  hoy.strftime("%B %Y"),
        "mes_inicio":               hoy.replace(day=1).isoformat(),
        "mes_fin":                  hoy.isoformat(),
        "journals_items":           journals or [],
        "ventas_alegra":            ventas_alegra or [],
        "bills_mes":                bills or [],
        "portfolio":                {},
        "inventario":               {"total": 0, "disponibles": 0, "vendidas_mes": 0},
        "motos_detalle":            motos or [],
        "cobrado_mes":              cobrado_mes,
        "esperado_mes":             cobrado_mes,
        "mora_cobrada_mes":         0,
        "ingresos_proyectados_mes": ingresos_proyectados,
        "cartera_pagos_mes":        cartera_pagos or [],
        "presupuesto":              presupuesto or {},
        "margenes":                 {},
        "top_morosos":              [],
        "loans_activos":            0,
        "loans_raw":                loans or [],
        "catalogo":                 [],
        "cfo_cfg":                  cfo_cfg or {},
    }


# ── TEST 4A — analizar_exposicion_tributaria ─────────────────────────────────

async def test_4a() -> None:
    from services.cfo_agent import analizar_exposicion_tributaria

    print("\n── TEST 4A — analizar_exposicion_tributaria ──────────────────")

    # 4A-1: Sin journals, sin DIAN → VERDE
    datos = make_datos_base()
    r = await analizar_exposicion_tributaria(datos)
    check("4A-1 sin obligaciones → color_impuestos=VERDE", "VERDE", r["color_impuestos"])
    check("4A-1 iva_generado=0",    0, r["iva_generado"])
    check("4A-1 ica_estimado=0",    0, r["ica_estimado"])

    # 4A-2: Obligación DIAN vencida hace 3 días → ROJO
    datos_rojo = make_datos_base(cfo_cfg={
        "fechas_dian": [{"nombre": "Declaración IVA", "fecha": past(3)}],
    })
    r2 = await analizar_exposicion_tributaria(datos_rojo)
    check("4A-2 DIAN vencida 3 días → ROJO",      "ROJO", r2["color_impuestos"])
    check("4A-2 alerta estado=VENCIDA",            "VENCIDA",
          r2["alertas_tributarias"][0]["estado"] if r2["alertas_tributarias"] else None)
    check("4A-2 dias_restantes < 0",               True,
          r2["alertas_tributarias"][0]["dias_restantes"] < 0 if r2["alertas_tributarias"] else False)

    # 4A-3: Obligación DIAN en 5 días → AMARILLO
    datos_amarillo = make_datos_base(cfo_cfg={
        "fechas_dian": [{"nombre": "Declaración ICA", "fecha": future(5)}],
    })
    r3 = await analizar_exposicion_tributaria(datos_amarillo)
    check("4A-3 DIAN en 5 días → AMARILLO",        "AMARILLO", r3["color_impuestos"])
    check("4A-3 alerta estado=PROXIMA",             "PROXIMA",
          r3["alertas_tributarias"][0]["estado"] if r3["alertas_tributarias"] else None)

    # 4A-4: Obligación en 10 días → sin alerta, VERDE
    datos_sin = make_datos_base(cfo_cfg={
        "fechas_dian": [{"nombre": "Renta", "fecha": future(10)}],
    })
    r4 = await analizar_exposicion_tributaria(datos_sin)
    check("4A-4 DIAN en 10 días → VERDE, sin alertas", "VERDE", r4["color_impuestos"])
    check("4A-4 alertas_tributarias vacías",           0, len(r4["alertas_tributarias"]))

    # 4A-5: IVA desde journals: 2408 crédito=1.000.000, 2409 débito=200.000
    journals_iva = [{
        "entries": [
            {"account": {"code": "2408"}, "debit": 0,       "credit": 1_000_000},
            {"account": {"code": "2409"}, "debit": 200_000, "credit": 0},
        ]
    }]
    datos_iva = make_datos_base(journals=journals_iva)
    r5 = await analizar_exposicion_tributaria(datos_iva)
    check("4A-5 iva_generado=1.000.000",   1_000_000, r5["iva_generado"])
    check("4A-5 iva_descontable=200.000",   200_000,  r5["iva_descontable"])
    check("4A-5 iva_neto=800.000",          800_000,  r5["iva_neto_trimestre"])


# ── TEST 4B — analizar_flujo_caja ────────────────────────────────────────────

async def test_4b() -> None:
    from services.cfo_agent import analizar_flujo_caja

    print("\n── TEST 4B — analizar_flujo_caja ────────────────────────────")

    # 4B-1: cobrado 5M + proyectado 2M − bills pendientes 3M = brecha 4M (positiva)
    bills_open = [{"total": 3_000_000, "status": "open"}]
    datos = make_datos_base(
        cobrado_mes=5_000_000,
        ingresos_proyectados=2_000_000,
        bills=bills_open,
    )
    r = await analizar_flujo_caja(datos)
    check("4B-1 ingresos_reales=5.000.000",       5_000_000, r["ingresos_reales"])
    check("4B-1 ingresos_proyectados=2.000.000",  2_000_000, r["ingresos_proyectados"])
    check("4B-1 egresos_pendientes=3.000.000",    3_000_000, r["egresos_pendientes"])
    check("4B-1 brecha_caja=4.000.000",           4_000_000, r["brecha_caja"])
    check("4B-1 caja_negativa=False",             False,     r["caja_negativa"])

    # 4B-2: cobrado 1M − bills 3M = brecha −2M (negativa → ROJO)
    datos2 = make_datos_base(cobrado_mes=1_000_000, bills=bills_open)
    r2 = await analizar_flujo_caja(datos2)
    check("4B-2 brecha negativa → caja_negativa=True", True, r2["caja_negativa"])
    check("4B-2 brecha = -2.000.000",                 -2_000_000, r2["brecha_caja"])

    # 4B-3: bills pagadas NO cuentan como egresos
    bills_mixed = [
        {"total": 1_000_000, "status": "open"},
        {"total": 2_000_000, "status": "paid"},   # pagada → no cuenta
        {"total": 500_000,   "status": "overdue"},
    ]
    datos3 = make_datos_base(cobrado_mes=5_000_000, bills=bills_mixed)
    r3 = await analizar_flujo_caja(datos3)
    check("4B-3 solo open+overdue en egresos=1.500.000", 1_500_000, r3["egresos_pendientes"])

    # 4B-4: cartera_pagos tiene prioridad sobre cobrado_mes
    pago_real = [{"valor_pagado": 800_000}, {"monto": 200_000}]
    datos4 = make_datos_base(cobrado_mes=9_999_999, cartera_pagos=pago_real, bills=[])
    r4 = await analizar_flujo_caja(datos4)
    check("4B-4 cartera_pagos prioridad: ingresos_reales=1.000.000", 1_000_000, r4["ingresos_reales"])


# ── TEST 4C — analizar_inventario ────────────────────────────────────────────

async def test_4c() -> None:
    from services.cfo_agent import analizar_inventario

    print("\n── TEST 4C — analizar_inventario ───────────────────────────")

    motos = [
        # Disponible reciente (30 días) → sin alerta
        {"estado": "disponible", "version": "Sport 100", "color": "Rojo",
         "vin": "AAA001", "fecha_ingreso": past(30)},
        # Disponible antiguo (75 días) → alerta >60
        {"estado": "disponible", "version": "Raider 125", "color": "Negro",
         "vin": "AAA002", "fecha_ingreso": past(75)},
        # Vendida
        {"estado": "vendida", "version": "Sport 100", "color": "Azul",
         "vin": "AAA003", "fecha_ingreso": past(20)},
        # Entregada
        {"estado": "entregada", "version": "Raider 125", "color": "Blanco",
         "vin": "AAA004", "fecha_ingreso": past(50)},
    ]
    datos = make_datos_base(motos=motos)
    r = await analizar_inventario(datos)

    check("4C-1 total_inventario=4",          4, r["total_inventario"])
    check("4C-2 disponibles=2",               2, r["disponibles"])
    check("4C-3 vendidas=1",                  1, r["vendidas"])
    check("4C-4 entregadas=1",                1, r["entregadas"])
    check("4C-5 alertas_stock_antiguo tiene 1 moto >60 días", 1, len(r["alertas_stock_antiguo"]))
    check("4C-6 alerta es Raider 125", "Raider 125", r["alertas_stock_antiguo"][0]["modelo"])
    check("4C-7 tiene_stock_critico=True",    True, r["tiene_stock_critico"])

    # Promedio: (30 + 75) / 2 = 52.5
    check("4C-8 promedio_dias_en_stock ≈ 52.5", 52.5, r["promedio_dias_en_stock"], tolerance=2)

    # 4C-9: inventario vacío → sin alertas
    datos_vacio = make_datos_base(motos=[])
    r2 = await analizar_inventario(datos_vacio)
    check("4C-9 inventario vacío → tiene_stock_critico=False", False, r2["tiene_stock_critico"])


# ── TEST 4D — analizar_kpis_comerciales ─────────────────────────────────────

async def test_4d() -> None:
    from services.cfo_agent import analizar_kpis_comerciales

    print("\n── TEST 4D — analizar_kpis_comerciales ──────────────────────")

    hoy = date.today()
    mes_inicio = hoy.replace(day=1).isoformat()

    # Préstamos del mes actual con planes variados
    loans = [
        {"plan": "P52S", "created_at": mes_inicio, "cuotas": [
            {"fecha_vencimiento": mes_inicio, "estado": "pagada",
             "valor": 175_000, "dpd_al_pagar": 0},
        ]},
        {"plan": "P52S", "created_at": mes_inicio, "cuotas": [
            {"fecha_vencimiento": mes_inicio, "estado": "pagada",
             "valor": 175_000, "dpd_al_pagar": 3},  # tardío
        ]},
        {"plan": "P39S", "created_at": mes_inicio, "cuotas": []},
    ]
    presupuesto = {"meta_motos": 10, "benchmark_planes": {"P39S": 30.0, "P52S": 50.0, "P78S": 20.0}}
    datos = make_datos_base(
        loans=loans,
        presupuesto=presupuesto,
        cobrado_mes=0,
    )
    # vendidas_mes en inventario
    datos["inventario"]["vendidas_mes"] = 3

    r = await analizar_kpis_comerciales(datos)

    check("4D-1 meta_motos=10",                  10,   r["meta_motos"])
    check("4D-2 motos_vendidas_mes=3",            3,    r["motos_vendidas_mes"])
    check("4D-3 pct_cumplimiento_ventas=30.0",    30.0, r["pct_cumplimiento_ventas"])

    # Mix: 2 P52S + 1 P39S + 0 P78S → P52S=66.7%, P39S=33.3%, P78S=0%
    check("4D-4 conteo_P52S=2",                  2,    r["conteo_planes_mes"].get("P52S"))
    check("4D-5 conteo_P39S=1",                  1,    r["conteo_planes_mes"].get("P39S"))
    check("4D-6 conteo_P78S=0",                  0,    r["conteo_planes_mes"].get("P78S"))

    # Tasa pago puntual: 1/2 pagadas a tiempo (dpd=0 de 2 cuotas mes actual)
    check("4D-7 cuotas_totales_mes=2",            2,    r["cuotas_totales_mes"])
    check("4D-8 cuotas_pagadas_puntual=1",        1,    r["cuotas_pagadas_puntual"])
    check("4D-9 tasa_pago_puntual=50.0",          50.0, r["tasa_pago_puntual_pct"])

    # 4D-10: Sin presupuesto → pct_cumplimiento None
    datos_sin = make_datos_base(presupuesto={})
    r2 = await analizar_kpis_comerciales(datos_sin)
    check("4D-10 sin meta_motos → pct_cumplimiento=None", None, r2["pct_cumplimiento_ventas"])


# ── TEST 4E — semáforo impuestos dinámico (via API) ─────────────────────────

async def test_4e_semaforo_impuestos(db) -> None:
    print("\n── TEST 4E — semáforo impuestos no siempre VERDE ────────────")

    # Guardar config existente
    existing_cfg = await db.cfo_config.find_one({}, {"_id": 0})

    # Limpiar y poner config con DIAN vencida → debe resultar en ROJO
    await db.cfo_config.delete_many({})
    cfg_rojo = {
        "fechas_dian": [{"nombre": "TEST IVA", "fecha": past(2)}],
        "umbral_mora_pct": 5,
        "umbral_caja_cop": 5_000_000,
        "tarifa_ica_por_mil": 11.04,
    }
    await db.cfo_config.insert_one(cfg_rojo)

    from services.cfo_agent import consolidar_datos_financieros, generar_semaforo
    datos = await consolidar_datos_financieros(db)
    semaforo = await generar_semaforo(datos)

    check("4E-1 impuestos no es siempre VERDE", True, semaforo.get("impuestos") != "VERDE")
    check("4E-2 impuestos=ROJO con DIAN vencida", "ROJO", semaforo.get("impuestos"))
    check("4E-3 semaforo tiene 5 dimensiones", True,
          all(k in semaforo for k in ["caja", "cartera", "ventas", "roll_rate", "impuestos"]))

    # Config sin DIAN vencidas → VERDE
    await db.cfo_config.delete_many({})
    cfg_limpio = {"fechas_dian": [], "tarifa_ica_por_mil": 11.04}
    await db.cfo_config.insert_one(cfg_limpio)
    datos2 = await consolidar_datos_financieros(db)
    semaforo2 = await generar_semaforo(datos2)
    check("4E-4 sin DIAN vencidas → impuestos=VERDE", "VERDE", semaforo2.get("impuestos"))

    # Restaurar config original
    await db.cfo_config.delete_many({})
    if existing_cfg:
        await db.cfo_config.insert_one(existing_cfg)


# ── TEST 4F — ICA 11.04‰ correcto ───────────────────────────────────────────

async def test_4f_ica() -> None:
    from services.cfo_agent import analizar_exposicion_tributaria

    print("\n── TEST 4F — ICA 11.04‰ (tarifa real RODDOS Bogotá) ────────")

    # Caso: ingresos 10.000.000 → ICA = 10.000.000 * 11.04 / 1000 = 110.400
    ventas = [{"total": 10_000_000}]
    datos = make_datos_base(ventas_alegra=ventas, cfo_cfg={"tarifa_ica_por_mil": 11.04})
    r = await analizar_exposicion_tributaria(datos)
    check("4F-1 tarifa_ica_por_mil=11.04",                    11.04, r["tarifa_ica_por_mil"])
    check("4F-2 ICA sobre 10M = 110.400",                   110_400, r["ica_estimado"], tolerance=10)

    # Caso: tarifa por defecto (sin cfo_cfg) debe ser 11.04
    datos_default = make_datos_base(ventas_alegra=ventas)
    r2 = await analizar_exposicion_tributaria(datos_default)
    check("4F-3 tarifa default = 11.04",                      11.04, r2["tarifa_ica_por_mil"])
    check("4F-4 ICA default sobre 10M = 110.400",           110_400, r2["ica_estimado"], tolerance=10)

    # Caso: tarifa configurable distinta (e.g. 9.66 para prueba) → resultado diferente
    datos_custom = make_datos_base(ventas_alegra=ventas, cfo_cfg={"tarifa_ica_por_mil": 9.66})
    r3 = await analizar_exposicion_tributaria(datos_custom)
    check("4F-5 tarifa custom 9.66 → ica_estimado=96.600",   96_600, r3["ica_estimado"], tolerance=10)


# ── TEST 4G — Endpoint /api/cfo/semaforo via curl ────────────────────────────

async def test_4g_endpoint() -> None:
    print("\n── TEST 4G — GET /api/cfo/semaforo (endpoint) ───────────────")

    # Obtener API_URL
    API_URL = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not API_URL:
        fe_env = os.path.join(ROOT, "..", "frontend", ".env")
        if os.path.exists(fe_env):
            with open(fe_env) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        API_URL = line.strip().split("=", 1)[1]
                        break

    if not API_URL:
        print("  [SKIP] 4G — REACT_APP_BACKEND_URL no configurada")
        return

    # Auth
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

    if not token:
        print("  [SKIP] 4G — no se pudo obtener token")
        return

    # GET /api/cfo/semaforo
    res2 = subprocess.run(
        ["curl", "-s", f"{API_URL}/api/cfo/semaforo",
         "-H", f"Authorization: Bearer {token}"],
        capture_output=True, text=True, timeout=60
    )
    try:
        data = json.loads(res2.stdout)
        impuestos_val = data.get("impuestos")
        valid_values = {"VERDE", "AMARILLO", "ROJO"}
        check("4G-1 endpoint retorna JSON con impuestos", True, "impuestos" in data)
        check("4G-2 impuestos tiene valor válido", True, impuestos_val in valid_values)
        check("4G-3 endpoint retorna 5 dimensiones semaforo", True,
              all(k in data for k in ["caja", "cartera", "ventas", "roll_rate", "impuestos"]))
        print(f"       impuestos={impuestos_val}, caja={data.get('caja')}, cartera={data.get('cartera')}")
    except Exception as e:
        check("4G-1 endpoint retorna JSON válido", True, False)
        print(f"       Error: {e}  |  stdout: {res2.stdout[:200]}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def run_tests() -> bool:
    client = AsyncIOMotorClient(MONGO_URL)
    db     = client[DB_NAME]

    print("\n" + "=" * 65)
    print("  TEST 4 — CFO: Tributaria · Flujo Caja · Inventario · KPIs")
    print("=" * 65)

    await test_4a()
    await test_4b()
    await test_4c()
    await test_4d()
    await test_4e_semaforo_impuestos(db)
    await test_4f_ica()
    await test_4g_endpoint()

    total  = len(results)
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

    client.close()
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
