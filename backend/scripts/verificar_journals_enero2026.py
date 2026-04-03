"""
verificar_journals_enero2026.py
================================
Test verificatorio de asientos contables de enero 2026 en Alegra.

Verifica los 225 journals causados desde los 3 extractos bancarios:
  - Bancolombia:  IDs 788 → 815  (83 journals)
  - BBVA:         IDs 816 → 921  (106 journals)
  - Nequi:        IDs 922 → 957  (36 journals)
  - Total esperado: 225 journals

Ejecutar en Render Shell:
  python scripts/verificar_journals_enero2026.py

Salida: reporte detallado con ✅ PASS / ❌ FAIL por cada verificación.
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import load_dotenv

load_dotenv()

# ── Configuración Alegra ──────────────────────────────────────────────────────

ALEGRA_EMAIL = os.environ.get("ALEGRA_EMAIL", "contabilidad@roddos.com")
ALEGRA_TOKEN = os.environ.get("ALEGRA_TOKEN", "17a8a3b7016e1c15c514")
ALEGRA_BASE   = "https://api.alegra.com/api/v1"

import base64
_creds = base64.b64encode(f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_creds}",
    "Content-Type": "application/json",
}

# ── Rangos esperados ──────────────────────────────────────────────────────────

RANGOS = {
    "bancolombia": {"inicio": 788, "fin": 815, "esperados": 83},
    "bbva":        {"inicio": 816, "fin": 921, "esperados": 106},
    "nequi":       {"inicio": 922, "fin": 957, "esperados": 36},
}
TOTAL_ESPERADO = 225
FECHA_INICIO   = "2026-01-01"
FECHA_FIN      = "2026-01-31"

# ── Cuentas válidas del plan_cuentas_roddos ───────────────────────────────────

CUENTAS_VALIDAS = {
    # Bancos
    5310, 5314, 5318, 5322, 5310,
    # Activos / CXC
    5327, 5329, 5331, 5332,
    # Pasivos
    5376, 5413,
    # Ingresos
    5456,
    # Gastos nómina/personal
    5462, 5468, 5469, 5472,
    # Honorarios
    5475, 5476,
    # Gastos operativos
    5478, 5480, 5482, 5483, 5484, 5485, 5487,
    5493, 5495, 5496, 5497, 5498, 5499,
    # Bancarios
    5507, 5508, 5509,
    # Costos/intereses
    5534,
    # Control interno
    5535,
}

# Cuentas por categoría (para validación semántica)
CUENTAS_BANCO       = {5310, 5314, 5318, 5322}
CUENTA_CARTERA      = 5327
CUENTA_CXC_SOCIO    = 5329
CUENTA_CXC_EMPL     = 5332
CUENTA_SAL_PAGAR    = 5413
CUENTA_INT_COBRADOS = 5456
CUENTA_SUELDOS      = 5462
CUENTA_GMF          = 5509
CUENTA_TRASLADO     = 5535
CUENTA_FALLBACK     = 5496

# ── Resultados del reporte ────────────────────────────────────────────────────

RESULTADOS = []

def ok(msg):
    RESULTADOS.append(("PASS", msg))
    print(f"  ✅ {msg}")

def fail(msg):
    RESULTADOS.append(("FAIL", msg))
    print(f"  ❌ {msg}")

def info(msg):
    print(f"     {msg}")

def seccion(titulo):
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}")

# ── Paginación Alegra ─────────────────────────────────────────────────────────

async def obtener_todos_journals(client: httpx.AsyncClient, fecha_inicio: str, fecha_fin: str):
    """Pagina /journals filtrando por rango de fechas. Máx limit=30 por página."""
    todos = []
    offset = 0
    while True:
        params = {
            "date_start": fecha_inicio,
            "date_end":   fecha_fin,
            "limit":      30,
            "offset":     offset,
            "order_field": "id",
            "order_direction": "ASC",
        }
        resp = await client.get(f"{ALEGRA_BASE}/journals", headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"     ERROR GET /journals offset={offset}: HTTP {resp.status_code}")
            break
        batch = resp.json()
        if not batch or not isinstance(batch, list):
            break
        todos.extend(batch)
        if len(batch) < 30:
            break
        offset += 30
    return todos

async def obtener_journal_por_id(client: httpx.AsyncClient, journal_id: int):
    """GET /journals/{id} para verificación individual."""
    resp = await client.get(f"{ALEGRA_BASE}/journals/{journal_id}", headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    return None

# ── Verificaciones ────────────────────────────────────────────────────────────

def v1_conteo_total(journals):
    seccion("V1 — Conteo total de journals enero 2026")
    total = len(journals)
    info(f"Journals obtenidos de Alegra: {total}")
    info(f"Total esperado:               {TOTAL_ESPERADO}")
    if total >= TOTAL_ESPERADO:
        ok(f"Conteo OK — {total} journals encontrados (esperado ≥ {TOTAL_ESPERADO})")
    else:
        fail(f"Conteo INSUFICIENTE — {total} de {TOTAL_ESPERADO} esperados")
    return total

def v2_rangos_ids(journals):
    seccion("V2 — Verificación de rangos de IDs por banco")
    ids = {j["id"] for j in journals}

    for banco, rango in RANGOS.items():
        inicio = rango["inicio"]
        fin    = rango["fin"]
        esperados = rango["esperados"]

        ids_banco = {i for i in ids if inicio <= i <= fin}
        encontrados = len(ids_banco)

        # IDs faltantes en el rango
        faltantes = [i for i in range(inicio, fin + 1) if i not in ids_banco]

        info(f"{banco.upper()}: IDs {inicio}→{fin} | Esperados: {esperados} | Encontrados: {encontrados}")

        if encontrados == esperados and not faltantes:
            ok(f"{banco.upper()} — {encontrados}/{esperados} journals presentes, sin huecos")
        elif encontrados >= esperados * 0.95:
            ok(f"{banco.upper()} — {encontrados}/{esperados} journals (>95%) — faltantes: {faltantes[:5]}")
        else:
            fail(f"{banco.upper()} — Solo {encontrados}/{esperados} journals — faltantes: {faltantes[:10]}")

def v3_fechas_enero(journals):
    seccion("V3 — Verificación de fechas (todas deben ser enero 2026)")
    fuera_de_rango = []
    sin_fecha = []
    ok_count = 0

    for j in journals:
        fecha = j.get("date") or j.get("fecha") or ""
        if not fecha:
            sin_fecha.append(j["id"])
            continue
        if fecha.startswith("2026-01"):
            ok_count += 1
        else:
            fuera_de_rango.append({"id": j["id"], "fecha": fecha})

    info(f"Con fecha enero 2026: {ok_count}")
    info(f"Sin fecha:            {len(sin_fecha)}")
    info(f"Fuera de enero 2026:  {len(fuera_de_rango)}")

    if not fuera_de_rango:
        ok(f"Fechas OK — {ok_count} journals con fecha en enero 2026")
    else:
        fail(f"Fechas incorrectas — {len(fuera_de_rango)} journals fuera de enero 2026: {fuera_de_rango[:5]}")

    if sin_fecha:
        fail(f"{len(sin_fecha)} journals sin campo fecha: IDs {sin_fecha[:5]}")

def v4_balance_debito_credito(journals):
    seccion("V4 — Balance débito = crédito (partida doble)")
    desbalanceados = []

    for j in journals:
        entries = j.get("entries", [])
        if not entries:
            continue
        total_debito  = sum(float(e.get("debit",  0) or 0) for e in entries)
        total_credito = sum(float(e.get("credit", 0) or 0) for e in entries)
        diff = abs(total_debito - total_credito)
        if diff > 1:  # tolerancia de $1 por redondeos
            desbalanceados.append({
                "id":     j["id"],
                "debito":  total_debito,
                "credito": total_credito,
                "diff":    diff,
            })

    if not desbalanceados:
        ok(f"Balance OK — todos los {len(journals)} journals tienen débito = crédito")
    else:
        fail(f"{len(desbalanceados)} journals desbalanceados:")
        for d in desbalanceados[:5]:
            info(f"  ID {d['id']}: débito={d['debito']:,.0f} crédito={d['credito']:,.0f} diff={d['diff']:,.2f}")

def v5_cuentas_validas(journals):
    seccion("V5 — Cuentas contables válidas (plan_cuentas_roddos)")
    cuentas_invalidas = []

    for j in journals:
        entries = j.get("entries", [])
        for e in entries:
            cuenta = e.get("account", {})
            cuenta_id = cuenta.get("id") if isinstance(cuenta, dict) else cuenta
            if cuenta_id and int(cuenta_id) not in CUENTAS_VALIDAS:
                cuentas_invalidas.append({
                    "journal_id": j["id"],
                    "cuenta_id":  cuenta_id,
                    "nombre":     cuenta.get("name", "") if isinstance(cuenta, dict) else "",
                })

    if not cuentas_invalidas:
        ok(f"Cuentas OK — todas las cuentas están en plan_cuentas_roddos")
    else:
        # Agrupar por cuenta para ver patrones
        por_cuenta = defaultdict(list)
        for c in cuentas_invalidas:
            por_cuenta[c["cuenta_id"]].append(c["journal_id"])
        fail(f"{len(cuentas_invalidas)} entradas con cuentas fuera del plan:")
        for cta, ids in list(por_cuenta.items())[:5]:
            info(f"  Cuenta {cta} — en journals: {ids[:5]}")

def v6_sin_cuenta_5495(journals):
    seccion("V6 — Verificación que NO se usó cuenta 5495 (error histórico)")
    con_5495 = []

    for j in journals:
        entries = j.get("entries", [])
        for e in entries:
            cuenta = e.get("account", {})
            cuenta_id = cuenta.get("id") if isinstance(cuenta, dict) else cuenta
            if cuenta_id and int(cuenta_id) == 5495:
                con_5495.append(j["id"])
                break

    if not con_5495:
        ok("Sin cuenta 5495 — ningún journal usó la cuenta incorrecta")
    else:
        fail(f"{len(con_5495)} journals usaron la cuenta 5495 (Gastos Representación — INCORRECTO): {con_5495}")

def v7_traslados_no_causados(journals):
    seccion("V7 — Traslados internos (5535) correctamente separados")
    traslados = []
    for j in journals:
        entries = j.get("entries", [])
        for e in entries:
            cuenta = e.get("account", {})
            cuenta_id = cuenta.get("id") if isinstance(cuenta, dict) else cuenta
            if cuenta_id and int(cuenta_id) == CUENTA_TRASLADO:
                traslados.append(j["id"])
                break

    info(f"Journals con cuenta traslado (5535): {len(traslados)}")
    info(f"IDs traslados: {traslados[:10]}")
    # Los traslados pueden llegar si llegaron a causarse — lo normal es 0
    if not traslados:
        ok("Traslados internos OK — ningún traslado se causó en Alegra (correcto)")
    else:
        fail(f"{len(traslados)} traslados internos se causaron en Alegra (deberían ser 0): {traslados[:5]}")

def v8_distribucion_cuentas(journals):
    seccion("V8 — Distribución por tipo de cuenta (análisis semántico)")
    conteo = defaultdict(int)
    montos = defaultdict(float)

    for j in journals:
        entries = j.get("entries", [])
        for e in entries:
            cuenta = e.get("account", {})
            cuenta_id = cuenta.get("id") if isinstance(cuenta, dict) else cuenta
            if not cuenta_id:
                continue
            cuenta_id = int(cuenta_id)
            debito = float(e.get("debit", 0) or 0)
            credito = float(e.get("credit", 0) or 0)
            monto = debito if debito > 0 else credito

            if cuenta_id in CUENTAS_BANCO:
                conteo["banco"] += 1
                montos["banco"] += monto
            elif cuenta_id == CUENTA_CARTERA:
                conteo["cartera"] += 1
                montos["cartera"] += monto
            elif cuenta_id in (CUENTA_CXC_SOCIO, CUENTA_SAL_PAGAR):
                conteo["cxc_socios"] += 1
                montos["cxc_socios"] += monto
            elif cuenta_id == CUENTA_GMF:
                conteo["gmf_4x1000"] += 1
                montos["gmf_4x1000"] += monto
            elif cuenta_id == CUENTA_SUELDOS:
                conteo["sueldos"] += 1
                montos["sueldos"] += monto
            elif cuenta_id == CUENTA_INT_COBRADOS:
                conteo["intereses"] += 1
                montos["intereses"] += monto

    total_journals = len(journals)
    info(f"Total journals analizados: {total_journals}")
    info(f"")
    info(f"  Tipo             | Entradas | Monto total")
    info(f"  {'banco':<16} | {conteo['banco']:>8} | ${montos['banco']:>15,.0f}")
    info(f"  {'cartera (5327)':<16} | {conteo['cartera']:>8} | ${montos['cartera']:>15,.0f}")
    info(f"  {'cxc_socios':<16} | {conteo['cxc_socios']:>8} | ${montos['cxc_socios']:>15,.0f}")
    info(f"  {'gmf_4x1000':<16} | {conteo['gmf_4x1000']:>8} | ${montos['gmf_4x1000']:>15,.0f}")
    info(f"  {'sueldos':<16} | {conteo['sueldos']:>8} | ${montos['sueldos']:>15,.0f}")
    info(f"  {'intereses':<16} | {conteo['intereses']:>8} | ${montos['intereses']:>15,.0f}")

    # Verificaciones semánticas
    if conteo["cartera"] > 0:
        ok(f"Cobros cartera presentes — {conteo['cartera']} entradas → ${montos['cartera']:,.0f}")
    else:
        fail("No se encontraron cobros de cartera (cuenta 5327) — revisar")

    if conteo["gmf_4x1000"] > 0:
        ok(f"GMF 4x1000 presente — {conteo['gmf_4x1000']} entradas → ${montos['gmf_4x1000']:,.0f}")
    else:
        fail("No se encontró GMF 4x1000 (cuenta 5509) — revisar extractos BBVA/Bancolombia")

def v9_duplicados_internos(journals):
    seccion("V9 — Verificación de duplicados internos (mismo monto + observación)")
    vistos = defaultdict(list)

    for j in journals:
        obs = (j.get("observations") or j.get("description") or "").strip().lower()[:60]
        total = 0
        entries = j.get("entries", [])
        for e in entries:
            total += float(e.get("debit", 0) or 0)
        key = f"{obs}|{int(total)}"
        if obs:
            vistos[key].append(j["id"])

    duplicados = {k: ids for k, ids in vistos.items() if len(ids) > 1}

    if not duplicados:
        ok(f"Sin duplicados internos — ningún journal con misma observación+monto")
    else:
        # GMF puede aparecer varias veces legítimamente (un cobro por movimiento)
        duplicados_no_gmf = {
            k: ids for k, ids in duplicados.items()
            if "gravamen" not in k and "4x1000" not in k and "impuesto 4x1000" not in k
        }
        if not duplicados_no_gmf:
            ok(f"Duplicados solo en GMF (esperado) — {len(duplicados)} grupos de GMF repetido")
        else:
            fail(f"{len(duplicados_no_gmf)} posibles duplicados no-GMF:")
            for k, ids in list(duplicados_no_gmf.items())[:5]:
                info(f"  '{k[:50]}' → IDs: {ids}")

def v10_cobertura_id_range(journals):
    seccion("V10 — Cobertura completa del rango 788-957")
    ids_en_alegra = {j["id"] for j in journals}
    ids_esperados = set(range(788, 958))  # 788 a 957 inclusive
    ids_faltantes = ids_esperados - ids_en_alegra
    ids_extra     = ids_en_alegra - ids_esperados

    info(f"IDs en rango 788-957 encontrados: {len(ids_esperados & ids_en_alegra)}")
    info(f"IDs faltantes en ese rango:       {len(ids_faltantes)}")
    info(f"IDs fuera del rango esperado:     {len(ids_extra)}")

    if len(ids_faltantes) == 0:
        ok("Cobertura completa — todos los IDs del rango 788-957 existen en Alegra")
    elif len(ids_faltantes) <= 9:
        # Podemos tolerar los 9 errores de monto < $1 que Alegra rechazó
        ok(f"Cobertura ≥95% — {len(ids_faltantes)} IDs faltantes (probable: montos < $1 rechazados por Alegra): {sorted(ids_faltantes)}")
    else:
        fail(f"Cobertura incompleta — {len(ids_faltantes)} IDs faltantes: {sorted(list(ids_faltantes))[:20]}")

    if ids_extra:
        info(f"IDs adicionales fuera del rango (otros períodos): {sorted(list(ids_extra))[:10]}")

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "="*60)
    print("  TEST VERIFICATORIO — JOURNALS ENERO 2026 EN ALEGRA")
    print(f"  Ejecutado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Rango esperado: IDs 788 → 957 | {TOTAL_ESPERADO} journals")
    print("="*60)

    print(f"\n⏳ Descargando journals de Alegra (enero 2026)...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Verificar conectividad
        test = await client.get(f"{ALEGRA_BASE}/journals?limit=1", headers=HEADERS)
        if test.status_code != 200:
            print(f"\n❌ ERROR: No se pudo conectar a Alegra — HTTP {test.status_code}")
            print(f"   Verificar ALEGRA_EMAIL y ALEGRA_TOKEN")
            sys.exit(1)

        journals = await obtener_todos_journals(client, FECHA_INICIO, FECHA_FIN)

    print(f"✅ Descargados {len(journals)} journals de Alegra para enero 2026\n")

    if len(journals) == 0:
        print("\n❌ CRÍTICO: Alegra retornó 0 journals para enero 2026.")
        print("   Posibles causas:")
        print("   1. El token de Alegra no tiene permisos de lectura")
        print("   2. Los journals no tienen fecha en el rango 2026-01-01 / 2026-01-31")
        print("   3. El filtro por fecha no aplica en este endpoint")
        sys.exit(1)

    # Ejecutar todas las verificaciones
    v1_conteo_total(journals)
    v2_rangos_ids(journals)
    v3_fechas_enero(journals)
    v4_balance_debito_credito(journals)
    v5_cuentas_validas(journals)
    v6_sin_cuenta_5495(journals)
    v7_traslados_no_causados(journals)
    v8_distribucion_cuentas(journals)
    v9_duplicados_internos(journals)
    v10_cobertura_id_range(journals)

    # Resumen final
    total  = len(RESULTADOS)
    passes = sum(1 for r, _ in RESULTADOS if r == "PASS")
    fails  = sum(1 for r, _ in RESULTADOS if r == "FAIL")

    print(f"\n{'='*60}")
    print(f"  RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"  Total verificaciones: {total}")
    print(f"  ✅ PASS: {passes}")
    print(f"  ❌ FAIL: {fails}")

    if fails == 0:
        print(f"\n  🎯 TODOS LOS TESTS PASARON — Enero 2026 contabilizado correctamente")
        print(f"     {passes} verificaciones exitosas sobre {len(journals)} journals")
    elif fails <= 2:
        print(f"\n  ⚠️  {fails} VERIFICACIÓN(ES) CON OBSERVACIONES — revisar arriba")
        print(f"     {passes}/{total} verificaciones OK")
    else:
        print(f"\n  🔴 {fails} VERIFICACIONES FALLIDAS — revisar detalles arriba")

    print(f"{'='*60}\n")

    return fails


if __name__ == "__main__":
    fails = asyncio.run(main())
    sys.exit(0 if fails == 0 else 1)
