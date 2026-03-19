"""cfo_agent.py — BUILD 4: Agente CFO de RODDOS.

Funciones:
  consolidar_datos_financieros(db)       → dict
  analizar_pyg(datos)                    → dict
  analizar_cartera(datos)                → dict
  analizar_exposicion_tributaria(datos)  → dict  (IVA, retenciones, ICA, alertas DIAN)
  analizar_flujo_caja(datos)             → dict  (ingresos reales/proyectados, egresos, brecha)
  analizar_inventario(datos)             → dict  (días en stock, alertas >60 días)
  analizar_kpis_comerciales(datos)       → dict  (meta ventas, mix planes, pago puntual)
  generar_semaforo(datos)                → dict
  generar_informe_cfo(db)                → dict  (llama a Claude, guarda en cfo_informes)
  process_cfo_query(msg, db, user, session_id)  → dict  (para chat routing)
"""
import os
import uuid
import json
import logging
from datetime import datetime, timezone, date, timedelta

import anthropic

logger = logging.getLogger(__name__)


# ── Parser diagnóstico IA ─────────────────────────────────────────────────────

def _parse_diagnostico(analisis_ia: str) -> dict:
    """Extrae puntos positivos (bien) y negativos (mal) del texto IA."""
    bien: list[str] = []
    mal:  list[str] = []
    section: str | None = None

    for raw_line in analisis_ia.split("\n"):
        line = raw_line.strip().lstrip("*#").strip()
        if not line:
            continue
        lower = line.lower()
        if any(kw in lower for kw in ("positivo", "favorable", "fortaleza", "bien:")):
            section = "bien"
            continue
        if any(kw in lower for kw in ("negativo", "desfavorable", "debilidad", "preocup",
                                       "riesgo", "mal:", "crítico")):
            section = "mal"
            continue
        if section and len(line) > 15:
            content = line.lstrip("0123456789. )-•→").strip()
            if content and len(content) > 15:
                if section == "bien" and len(bien) < 5:
                    bien.append(content)
                elif section == "mal" and len(mal) < 5:
                    mal.append(content)

    # Fallback: si no se detectaron secciones, dividir el texto por la mitad
    if not bien and not mal and analisis_ia:
        lines = [ln.strip() for ln in analisis_ia.split("\n") if len(ln.strip()) > 20]
        mid = len(lines) // 2
        bien = lines[:mid][:3]
        mal  = lines[mid:][:3]

    return {"bien": bien, "mal": mal}


# ── Costos unitarios por modelo ───────────────────────────────────────────────
COSTO_MODELOS: dict[str, float] = {
    "sport 100":  4_157_461.0,
    "raider 125": 5_638_974.0,
}

# ── CFO intent keywords ───────────────────────────────────────────────────────
CFO_KEYWORDS: frozenset[str] = frozenset({
    "plan", "financiero", "cómo vamos", "como vamos",
    "margen", "flujo de caja", "rentabilidad", "presupuesto",
    "meta", "mora total", "semáforo", "semaforo", "informe cfo",
    "pérdida", "perdida", "ganancia", "ebitda",
    "iva total", "impuesto", "resultado neto", "utilidad",
    "cartera total", "cómo está la empresa", "balance",
})


def is_cfo_query(message: str) -> bool:
    """Retorna True si el mensaje contiene keywords financieros/CFO."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in CFO_KEYWORDS)


# ── 1. consolidar_datos_financieros ──────────────────────────────────────────

async def consolidar_datos_financieros(db) -> dict:
    """Consolida Alegra + MongoDB para análisis CFO del mes actual."""
    from alegra_service import AlegraService
    from services.shared_state import get_portfolio_health

    alegra = AlegraService(db)
    hoy = date.today()
    mes_inicio = hoy.replace(day=1).isoformat()
    mes_fin = hoy.isoformat()
    prox_mes_fin = (hoy.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat()

    # ── Alegra: journals del mes ──────────────────────────────────────────────
    journals_items: list = []
    try:
        resp = await alegra.request(
            "journals",
            params={"date_afterOrNow": mes_inicio, "date_beforeOrNow": mes_fin},
        )
        if isinstance(resp, list):
            journals_items = resp
        elif isinstance(resp, dict):
            journals_items = resp.get("items", resp.get("data", []))
    except Exception as e:
        logger.warning(f"[CFO] journals: {e}")

    # ── Alegra: facturas de venta del mes ────────────────────────────────────
    ventas_alegra: list = []
    try:
        v = await alegra.request(
            "invoices",
            params={"date_afterOrNow": mes_inicio, "date_beforeOrNow": mes_fin},
        )
        ventas_alegra = v if isinstance(v, list) else []
    except Exception as e:
        logger.warning(f"[CFO] invoices: {e}")

    # ── Alegra: cuentas por pagar (bills) del mes ────────────────────────────
    bills_mes: list = []
    try:
        b = await alegra.request(
            "bills",
            params={"date_afterOrNow": mes_inicio, "date_beforeOrNow": mes_fin},
        )
        bills_mes = b if isinstance(b, list) else []
    except Exception as e:
        logger.warning(f"[CFO] bills: {e}")

    # ── Portfolio health (shared_state) ──────────────────────────────────────
    portfolio: dict = {}
    try:
        portfolio = await get_portfolio_health(db)
    except Exception as e:
        logger.warning(f"[CFO] portfolio_health: {e}")

    # ── Inventario motos — detalle completo para análisis de stock ────────────
    motos_detalle = await db.inventario_motos.find(
        {},
        {"_id": 0, "estado": 1, "version": 1, "modelo": 1, "color": 1,
         "vin": 1, "total": 1, "fecha_entrega": 1, "fecha_ingreso": 1},
    ).to_list(2000)
    motos_disponibles = [m for m in motos_detalle if m.get("estado") == "disponible"]
    motos_vendidas_mes = [
        m for m in motos_detalle
        if m.get("estado") in ("vendida", "entregada")
        and (m.get("fecha_entrega") or "") >= mes_inicio
    ]

    # ── Loanbook: cobros del mes + proyección cuotas futuras ─────────────────
    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora", "recuperacion", "completado"]}},
        {"_id": 0, "cuotas": 1, "codigo": 1, "cliente_nombre": 1,
         "dpd_actual": 1, "interes_mora_acumulado": 1, "plan": 1, "created_at": 1},
    ).to_list(5000)

    cobrado_mes = 0.0
    esperado_mes = 0.0
    mora_cobrada_mes = 0.0
    ingresos_proyectados_mes = 0.0

    for loan in loans:
        for cuota in loan.get("cuotas", []):
            fv = cuota.get("fecha_vencimiento", "")
            if mes_inicio <= fv <= mes_fin:
                esperado_mes += cuota.get("valor", 0)
                if cuota.get("estado") == "pagada":
                    cobrado_mes += cuota.get("valor_pagado", cuota.get("valor", 0))
                    mora_cobrada_mes += cuota.get("interes_mora_cobrado", 0)
            # Proyección: cuotas pendientes del próximo mes
            elif mes_fin < fv < prox_mes_fin and cuota.get("estado") == "pendiente":
                ingresos_proyectados_mes += cuota.get("valor", 0)

    # ── cartera_pagos: pagos reales registrados en el mes ─────────────────────
    cartera_pagos_mes: list = []
    try:
        cartera_pagos_mes = await db.cartera_pagos.find(
            {"fecha_pago": {"$gte": mes_inicio, "$lte": mes_fin}},
            {"_id": 0, "valor_pagado": 1, "monto": 1, "fecha_pago": 1},
        ).to_list(5000)
    except Exception as e:
        logger.warning(f"[CFO] cartera_pagos: {e}")

    # ── Presupuesto del mes ───────────────────────────────────────────────────
    presupuesto = await db.presupuesto.find_one(
        {"periodo": {"$regex": f"^{hoy.strftime('%Y-%m')}"}},
        {"_id": 0},
    ) or {}

    # ── Catálogo: márgenes ────────────────────────────────────────────────────
    catalogo = await db.catalogo_motos.find({"activo": True}, {"_id": 0}).to_list(50)
    margenes: dict = {}
    for m in catalogo:
        pvp = m.get("pvp", 0)
        costo = m.get("costo", 0)
        if pvp > 0:
            margenes[m["modelo"]] = {
                "pvp": pvp,
                "costo": costo,
                "margen_pct": round((pvp - costo) / pvp * 100, 1),
            }

    # ── Top 5 morosos ─────────────────────────────────────────────────────────
    loans_mora = sorted(
        [ln for ln in loans if ln.get("dpd_actual", 0) > 0],
        key=lambda x: x.get("dpd_actual", 0),
        reverse=True,
    )[:5]
    top_morosos = [
        {"codigo": m.get("codigo"), "cliente": m.get("cliente_nombre"), "dpd": m.get("dpd_actual", 0)}
        for m in loans_mora
    ]

    # ── Configuración CFO ────────────────────────────────────────────────────
    cfo_cfg = await db.cfo_config.find_one({}, {"_id": 0}) or {}

    # ── BUILD 9: Métricas predictivas del learning engine ─────────────────────
    metricas_predictivas: dict = {}
    try:
        from services.learning_engine import get_metricas_predictivas
        metricas_predictivas = await get_metricas_predictivas(db)
    except Exception as e:
        logger.warning(f"[CFO] metricas_predictivas: {e}")

    return {
        "periodo":                    hoy.strftime("%B %Y"),
        "mes_inicio":                 mes_inicio,
        "mes_fin":                    mes_fin,
        "journals_items":             journals_items,
        "ventas_alegra":              ventas_alegra,
        "bills_mes":                  bills_mes,
        "portfolio":                  portfolio,
        "inventario": {
            "total":        len(motos_detalle),
            "disponibles":  len(motos_disponibles),
            "vendidas_mes": len(motos_vendidas_mes),
        },
        "motos_detalle":              motos_detalle,
        "cobrado_mes":                cobrado_mes,
        "esperado_mes":               esperado_mes,
        "mora_cobrada_mes":           mora_cobrada_mes,
        "ingresos_proyectados_mes":   ingresos_proyectados_mes,
        "cartera_pagos_mes":          cartera_pagos_mes,
        "presupuesto":                presupuesto,
        "margenes":                   margenes,
        "top_morosos":                top_morosos,
        "loans_activos":              len(loans),
        "loans_raw":                  loans,
        "catalogo":                   catalogo,
        "cfo_cfg":                    cfo_cfg,
        "metricas_predictivas":       metricas_predictivas,
    }


# ── 2. analizar_pyg ───────────────────────────────────────────────────────────

async def analizar_pyg(datos: dict) -> dict:
    """P&G del mes: ingresos, costos, margen, gastos, resultado neto."""
    catalogo = datos.get("catalogo", [])
    journals_items = datos.get("journals_items", [])
    ventas_alegra = datos.get("ventas_alegra", [])

    # Ingresos ventas motos desde Alegra invoices
    ingresos_ventas = sum(float(v.get("total", 0) or 0) for v in ventas_alegra)

    # Si Alegra no tiene datos reales, usar loanbook como proxy
    if ingresos_ventas == 0:
        ingresos_ventas = datos.get("cobrado_mes", 0)

    ingresos_mora_cobrada = datos.get("mora_cobrada_mes", 0)
    ingresos_repuestos = 0.0

    # Extraer gastos desde journal-entries (cuentas 5xxx = gastos)
    gastos_operativos = 0.0
    for j in journals_items:
        for entry in j.get("entries", []):
            acct = entry.get("account", {})
            code = str(acct.get("code", "") or acct.get("id", ""))
            debit = float(entry.get("debit", 0) or 0)
            # Cuentas de gasto: 5105 nómina, 5160 depreciaciones, etc.
            if code.startswith("5") and debit > 0:
                gastos_operativos += debit

    # Costo motos vendidas
    motos_vendidas = datos.get("inventario", {}).get("vendidas_mes", 0)
    costo_prom = sum(c.get("costo", 0) for c in catalogo) / max(len(catalogo), 1)
    costo_motos = motos_vendidas * costo_prom

    ingresos_totales = ingresos_ventas + ingresos_mora_cobrada + ingresos_repuestos
    margen_bruto = ingresos_totales - costo_motos
    margen_bruto_pct = round(margen_bruto / max(ingresos_totales, 1) * 100, 1)
    resultado_neto = margen_bruto - gastos_operativos

    return {
        "ingresos_ventas":       round(ingresos_ventas),
        "ingresos_mora_cobrada": round(ingresos_mora_cobrada),
        "ingresos_repuestos":    round(ingresos_repuestos),
        "ingresos_totales":      round(ingresos_totales),
        "costo_motos":           round(costo_motos),
        "margen_bruto":          round(margen_bruto),
        "margen_bruto_pct":      margen_bruto_pct,
        "gastos_operativos":     round(gastos_operativos),
        "resultado_neto":        round(resultado_neto),
    }


# ── 3. analizar_cartera ───────────────────────────────────────────────────────

async def analizar_cartera(datos: dict) -> dict:
    """Análisis de cartera desde portfolio_health + top morosos + BUILD 9 métricas predictivas."""
    portfolio = datos.get("portfolio", {})
    pred = datos.get("metricas_predictivas", {})
    return {
        "tasa_mora_pct":                portfolio.get("tasa_mora", 0),
        "valor_mora":                   portfolio.get("por_estado", {}).get("mora", {}).get("saldo_total", 0),
        "roll_rate":                    0,
        "total_cartera":                portfolio.get("saldo_cartera_total", 0),
        "en_mora":                      portfolio.get("en_mora", 0),
        "activos":                      portfolio.get("activos", 0),
        "top_morosos":                  datos.get("top_morosos", []),
        # BUILD 9 — Inteligencia Predictiva
        "efectividad_canal":            pred.get("efectividad_canal", {}),
        "clientes_en_riesgo_predictivo": pred.get("clientes_en_riesgo_predictivo", 0),
        "tendencia_mora":               pred.get("tendencia_mora", "estable"),
        "outcomes_analizados":          pred.get("outcomes_last_30d", 0),
    }


# ── 4. analizar_exposicion_tributaria ────────────────────────────────────────

async def analizar_exposicion_tributaria(datos: dict) -> dict:
    """IVA neto trimestral, retenciones acumuladas, ICA estimado, alertas DIAN.

    Tarifa ICA Bogotá — RODDOS: 11.04‰ (once coma cero cuatro por mil).
    Configurable vía cfo_cfg.tarifa_ica_por_mil (default 11.04).
    """
    journals = datos.get("journals_items", [])
    cfo_cfg = datos.get("cfo_cfg", {})
    ventas_alegra = datos.get("ventas_alegra", [])
    hoy = date.today()

    # ── IVA desde asientos contables ─────────────────────────────────────────
    iva_generado = 0.0       # cuenta 2408 (IVA por pagar) — lado crédito
    iva_descontable = 0.0    # cuenta 2409 (IVA descontable) — lado débito
    retenciones_fuente = 0.0 # cuentas 2365/2366 — lado crédito
    retenciones_iva = 0.0    # cuenta 2367 (ReteIVA) — lado crédito
    retenciones_ica = 0.0    # cuenta 2368 (ReteICA) — lado crédito

    for j in journals:
        for entry in j.get("entries", []):
            acct = entry.get("account", {})
            code = str(acct.get("code", "") or acct.get("id", ""))
            debit = float(entry.get("debit", 0) or 0)
            credit = float(entry.get("credit", 0) or 0)

            if code == "2408":
                iva_generado += credit
            elif code == "2409":
                iva_descontable += debit
            elif code in ("2365", "2366"):
                retenciones_fuente += credit
            elif code == "2367":
                retenciones_iva += credit
            elif code == "2368":
                retenciones_ica += credit

    iva_neto = iva_generado - iva_descontable

    # ── ICA estimado sobre ingresos brutos del mes ────────────────────────────
    # Tarifa REAL RODDOS Bogotá: 11.04‰
    tarifa_ica = float(cfo_cfg.get("tarifa_ica_por_mil", 11.04))
    ingresos_brutos = sum(float(v.get("total", 0) or 0) for v in ventas_alegra)
    if ingresos_brutos == 0:
        # Fallback: usar cobrado del loanbook si Alegra no tiene datos
        ingresos_brutos = datos.get("cobrado_mes", 0)
    ica_estimado = round(ingresos_brutos * tarifa_ica / 1000, 0)

    # ── Alertas DIAN desde configuración ────────────────────────────────────
    alertas_tributarias: list[dict] = []
    color_impuestos = "VERDE"

    fechas_obligaciones: list = cfo_cfg.get("fechas_dian", [])
    for obligacion in fechas_obligaciones:
        fecha_str = obligacion.get("fecha", "")
        nombre = obligacion.get("nombre", "Obligación DIAN")
        try:
            fecha_ob = date.fromisoformat(fecha_str)
            dias_restantes = (fecha_ob - hoy).days
            if dias_restantes < 0:
                estado = "VENCIDA"
                color_impuestos = "ROJO"
            elif dias_restantes < 7:
                estado = "PROXIMA"
                if color_impuestos != "ROJO":
                    color_impuestos = "AMARILLO"
            else:
                continue  # No alert needed
            alertas_tributarias.append({
                "nombre": nombre,
                "fecha": fecha_str,
                "dias_restantes": dias_restantes,
                "estado": estado,
            })
        except (ValueError, TypeError):
            pass

    return {
        "iva_generado":           round(iva_generado),
        "iva_descontable":        round(iva_descontable),
        "iva_neto_trimestre":     round(iva_neto),
        "retenciones_fuente":     round(retenciones_fuente),
        "retenciones_iva":        round(retenciones_iva),
        "retenciones_ica":        round(retenciones_ica),
        "tarifa_ica_por_mil":     tarifa_ica,
        "ica_estimado":           int(ica_estimado),
        "alertas_tributarias":    alertas_tributarias,
        "color_impuestos":        color_impuestos,
    }


# ── 5. analizar_flujo_caja ────────────────────────────────────────────────────

async def analizar_flujo_caja(datos: dict) -> dict:
    """Ingresos reales (cartera_pagos) + proyectados (loanbook futuro) vs egresos (bills).

    brecha_caja = total_ingresos - egresos_pendientes
    Si brecha < 0 → semáforo caja = ROJO.
    """
    # Ingresos reales del mes desde cartera_pagos
    cartera_pagos = datos.get("cartera_pagos_mes", [])
    ingresos_reales = sum(
        float(p.get("valor_pagado", p.get("monto", 0)) or 0)
        for p in cartera_pagos
    )
    # Si cartera_pagos está vacío, usar cobrado_mes como proxy
    if ingresos_reales == 0:
        ingresos_reales = datos.get("cobrado_mes", 0)

    # Ingresos proyectados desde cuotas futuras del loanbook
    ingresos_proyectados = datos.get("ingresos_proyectados_mes", 0.0)

    # Egresos: bills de Alegra pendientes (open + overdue) del mes
    bills = datos.get("bills_mes", [])
    egresos_pendientes = sum(
        float(b.get("total", 0) or 0)
        for b in bills
        if b.get("status") in ("open", "overdue", None)
    )

    total_ingresos = ingresos_reales + ingresos_proyectados
    brecha_caja = total_ingresos - egresos_pendientes

    return {
        "ingresos_reales":        round(ingresos_reales),
        "ingresos_proyectados":   round(ingresos_proyectados),
        "total_ingresos":         round(total_ingresos),
        "egresos_pendientes":     round(egresos_pendientes),
        "brecha_caja":            round(brecha_caja),
        "caja_negativa":          brecha_caja < 0,
        "num_bills_pendientes":   len([b for b in bills if b.get("status") in ("open", "overdue", None)]),
    }


# ── 6. analizar_inventario ────────────────────────────────────────────────────

async def analizar_inventario(datos: dict) -> dict:
    """Días en stock, unidades por estado, alerta >60 días sin vender."""
    motos_detalle = datos.get("motos_detalle", [])
    hoy = date.today()

    disponibles_detalle: list[dict] = []
    vendidas_count = 0
    entregadas_count = 0
    alertas_stock: list[dict] = []

    for moto in motos_detalle:
        estado = moto.get("estado", "")
        if estado == "disponible":
            dias_en_stock = 0
            fecha_ingreso = moto.get("fecha_ingreso", "")
            if fecha_ingreso:
                try:
                    fi = date.fromisoformat(str(fecha_ingreso)[:10])
                    dias_en_stock = (hoy - fi).days
                except (ValueError, TypeError):
                    pass
            disponibles_detalle.append({
                "modelo":        moto.get("version", moto.get("modelo", "N/A")),
                "color":         moto.get("color", ""),
                "vin":           moto.get("vin", ""),
                "dias_en_stock": dias_en_stock,
            })
            if dias_en_stock > 60:
                alertas_stock.append({
                    "modelo":        moto.get("version", moto.get("modelo", "N/A")),
                    "dias_en_stock": dias_en_stock,
                    "color":         moto.get("color", ""),
                    "vin":           moto.get("vin", ""),
                })
        elif estado == "vendida":
            vendidas_count += 1
        elif estado == "entregada":
            entregadas_count += 1

    dias_lista = [m["dias_en_stock"] for m in disponibles_detalle]
    promedio_dias = round(sum(dias_lista) / max(len(dias_lista), 1), 1)

    return {
        "total_inventario":       len(motos_detalle),
        "disponibles":            len(disponibles_detalle),
        "vendidas":               vendidas_count,
        "entregadas":             entregadas_count,
        "promedio_dias_en_stock": promedio_dias,
        "alertas_stock_antiguo":  alertas_stock,
        "tiene_stock_critico":    len(alertas_stock) > 0,
        "disponibles_detalle":    disponibles_detalle[:20],  # top 20 para el informe
    }


# ── 7. analizar_kpis_comerciales ─────────────────────────────────────────────

async def analizar_kpis_comerciales(datos: dict) -> dict:
    """Cumplimiento de meta ventas, mix de planes financieros, tasa de pago puntual."""
    presupuesto = datos.get("presupuesto", {})
    loans_raw = datos.get("loans_raw", [])
    mes_inicio = datos.get("mes_inicio", "")
    mes_fin = datos.get("mes_fin", "")

    # ── Ventas vs meta ────────────────────────────────────────────────────────
    meta_motos = int(presupuesto.get("meta_motos", 0))
    motos_vendidas_mes = datos.get("inventario", {}).get("vendidas_mes", 0)
    pct_cumplimiento_ventas = (
        round(motos_vendidas_mes / meta_motos * 100, 1) if meta_motos > 0 else None
    )

    # ── Mix de planes: contar préstamos creados este mes ─────────────────────
    benchmark_planes: dict = presupuesto.get("benchmark_planes", {
        "P39S": 30.0, "P52S": 50.0, "P78S": 20.0,
    })
    conteo_planes: dict[str, int] = {"P39S": 0, "P52S": 0, "P78S": 0}
    for loan in loans_raw:
        plan = loan.get("plan", "")
        created = str(loan.get("created_at", ""))
        # Considerar solo los préstamos creados en el mes actual
        if plan in conteo_planes and created[:7] == mes_inicio[:7]:
            conteo_planes[plan] += 1

    total_planes = sum(conteo_planes.values())
    mix_actual: dict[str, float] = {
        plan: round(count / max(total_planes, 1) * 100, 1)
        for plan, count in conteo_planes.items()
    }

    # ── Tasa de pago puntual: cuotas del mes pagadas con DPD=0 ───────────────
    cuotas_totales_mes = 0
    cuotas_pagadas_puntual = 0

    for loan in loans_raw:
        for cuota in loan.get("cuotas", []):
            fv = cuota.get("fecha_vencimiento", "")
            if mes_inicio <= fv <= mes_fin:
                cuotas_totales_mes += 1
                if cuota.get("estado") == "pagada":
                    dpd_al_pagar = cuota.get("dpd_al_pagar", 0) or 0
                    if dpd_al_pagar == 0:
                        cuotas_pagadas_puntual += 1

    tasa_pago_puntual = round(
        cuotas_pagadas_puntual / max(cuotas_totales_mes, 1) * 100, 1
    )

    return {
        "meta_motos":                meta_motos,
        "motos_vendidas_mes":        motos_vendidas_mes,
        "pct_cumplimiento_ventas":   pct_cumplimiento_ventas,
        "conteo_planes_mes":         conteo_planes,
        "total_planes_mes":          total_planes,
        "mix_planes_actual":         mix_actual,
        "mix_planes_benchmark":      benchmark_planes,
        "cuotas_totales_mes":        cuotas_totales_mes,
        "cuotas_pagadas_puntual":    cuotas_pagadas_puntual,
        "tasa_pago_puntual_pct":     tasa_pago_puntual,
    }


# ── 8. generar_semaforo ───────────────────────────────────────────────────────

async def generar_semaforo(datos: dict) -> dict:
    """Semáforo 5 dimensiones: caja, cartera, ventas, roll_rate, impuestos."""
    pyg         = await analizar_pyg(datos)
    cartera     = await analizar_cartera(datos)
    flujo_caja  = await analizar_flujo_caja(datos)
    tributaria  = await analizar_exposicion_tributaria(datos)

    tasa_mora = cartera.get("tasa_mora_pct", 0)
    roll_rate = cartera.get("roll_rate", 0)
    cobrado   = datos.get("cobrado_mes", 0)
    esperado  = datos.get("esperado_mes", 1)

    meta_ventas = datos.get("presupuesto", {}).get("meta_ventas", 0)
    resultado_neto = pyg.get("resultado_neto", 0)
    pct_cobrado = round(cobrado / max(esperado, 1) * 100, 1)
    pct_meta = round(cobrado / meta_ventas * 100, 1) if meta_ventas > 0 else 100.0

    cfo_cfg      = datos.get("cfo_cfg", {})
    umbral_mora  = float(cfo_cfg.get("umbral_mora_pct", 5))
    umbral_caja  = float(cfo_cfg.get("umbral_caja_cop", 5_000_000))

    def _color(rojo: bool, amarillo: bool) -> str:
        if rojo:
            return "ROJO"
        if amarillo:
            return "AMARILLO"
        return "VERDE"

    # ── caja: usar brecha de flujo real cuando hay datos, si no → resultado neto ──
    brecha = flujo_caja.get("brecha_caja", resultado_neto)
    color_caja = _color(brecha < 0, 0 <= brecha < umbral_caja)

    # ── impuestos: dinámico desde analizar_exposicion_tributaria ──────────────
    color_impuestos = tributaria.get("color_impuestos", "VERDE")

    return {
        "caja":       color_caja,
        "cartera":    _color(
            tasa_mora > 15 or cartera.get("clientes_en_riesgo_predictivo", 0) >= 3,
            umbral_mora <= tasa_mora <= 15 or cartera.get("clientes_en_riesgo_predictivo", 0) >= 1,
        ),
        "ventas":     _color(pct_meta < 70 and meta_ventas > 0, 70 <= pct_meta < 99 and meta_ventas > 0),
        "roll_rate":  _color(roll_rate > 20, 10 <= roll_rate <= 20),
        "impuestos":  color_impuestos,
        "metricas": {
            "tasa_mora_pct":                    tasa_mora,
            "roll_rate_pct":                    roll_rate,
            "pct_cobrado":                      pct_cobrado,
            "resultado_neto":                   resultado_neto,
            "pct_meta_ventas":                  pct_meta,
            "cobrado_mes":                      cobrado,
            "esperado_mes":                     esperado,
            "brecha_caja":                      brecha,
            "iva_neto":                         tributaria.get("iva_neto_trimestre", 0),
            "ica_estimado":                     tributaria.get("ica_estimado", 0),
            "alertas_tributarias":              tributaria.get("alertas_tributarias", []),
            # BUILD 9
            "clientes_en_riesgo_predictivo":    cartera.get("clientes_en_riesgo_predictivo", 0),
            "tendencia_mora":                   cartera.get("tendencia_mora", "estable"),
            "efectividad_canal":                cartera.get("efectividad_canal", {}),
        },
    }


# ── 9. generar_informe_cfo ────────────────────────────────────────────────────

async def generar_informe_cfo(db, triggered_by: str = "manual") -> dict:
    """Genera informe CFO completo con análisis IA. Guarda en cfo_informes."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    now_iso = datetime.now(timezone.utc).isoformat()

    datos      = await consolidar_datos_financieros(db)
    pyg        = await analizar_pyg(datos)
    cartera    = await analizar_cartera(datos)
    tributaria = await analizar_exposicion_tributaria(datos)
    flujo      = await analizar_flujo_caja(datos)
    inventario = await analizar_inventario(datos)
    kpis       = await analizar_kpis_comerciales(datos)
    semaforo   = await generar_semaforo(datos)

    resumen = {
        "periodo":     datos["periodo"],
        "pyg":         pyg,
        "cartera":     cartera,
        "semaforo":    {k: v for k, v in semaforo.items() if k != "metricas"},
        "metricas":    semaforo.get("metricas", {}),
        "inventario":  inventario,
        "flujo_caja":  flujo,
        "tributario":  tributaria,
        "kpis":        kpis,
        "top_morosos": datos["top_morosos"],
        # BUILD 9 — Inteligencia Predictiva para el prompt de Claude
        "inteligencia_predictiva": {
            "clientes_en_riesgo":    cartera.get("clientes_en_riesgo_predictivo", 0),
            "tendencia_mora":        cartera.get("tendencia_mora", "estable"),
            "efectividad_canal":     cartera.get("efectividad_canal", {}),
            "outcomes_analizados":   cartera.get("outcomes_analizados", 0),
        },
    }

    analisis_ia = ""
    plan_acciones: list[dict] = []

    try:
        _cfo_client = anthropic.AsyncAnthropic(api_key=api_key)
        prompt = (
            f"DATOS FINANCIEROS RODDOS — {datos['periodo']}:\n"
            f"{json.dumps(resumen, ensure_ascii=False, indent=2)}\n\n"
            "Genera en español:\n"
            "1) DIAGNÓSTICO: exactamente 3 puntos positivos y 3 negativos con cifras reales.\n"
            "2) FLUJO DE CAJA: analiza la brecha entre ingresos y egresos.\n"
            "3) TRIBUTARIO: comenta el IVA neto, ICA estimado y cualquier alerta DIAN.\n"
            "4) INVENTARIO: menciona motos con stock >60 días si las hay.\n"
            "5) INTELIGENCIA PREDICTIVA: comenta clientes_en_riesgo, tendencia_mora y canal más efectivo.\n"
            "6) PLAN DE ACCIÓN: exactamente 5 líneas, cada una con formato:\n"
            "   ACCIÓN|RESPONSABLE|FECHA|MÉTRICA\n"
            "Sé preciso. Usa solo los números del JSON. No inventes datos."
        )
        _cfo_resp = await _cfo_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=(
                "Eres el asesor CFO de RODDOS Colombia — concesionario Auteco en Bogotá. "
                "Analizas datos financieros reales y das recomendaciones accionables y concretas."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        analisis_ia = _cfo_resp.content[0].text

        # Parse plan
        for line in analisis_ia.split("\n"):
            parts = [p.strip() for p in line.strip().split("|")]
            if len(parts) == 4 and parts[0] and not parts[0].startswith("#"):
                plan_acciones.append({
                    "accion":      parts[0],
                    "responsable": parts[1],
                    "fecha":       parts[2],
                    "metrica":     parts[3],
                    "estado":      "pendiente",
                })
    except Exception as e:
        logger.error(f"[CFO] Error IA: {e}")
        analisis_ia = "Análisis IA no disponible. Revisa la configuración de la clave API."

    informe = {
        "id":               str(uuid.uuid4()),
        "periodo":          datos["periodo"],
        "fecha_generacion": now_iso,
        "generado_en":      now_iso,
        "generado_por":     triggered_by,
        "datos_financieros": {
            "pyg":         pyg,
            "cartera":     cartera,
            "inventario":  inventario,
            "flujo_caja":  flujo,
            "tributario":  tributaria,
            "kpis":        kpis,
        },
        "inteligencia_predictiva": {
            "clientes_en_riesgo":  cartera.get("clientes_en_riesgo_predictivo", 0),
            "tendencia_mora":      cartera.get("tendencia_mora", "estable"),
            "efectividad_canal":   cartera.get("efectividad_canal", {}),
            "outcomes_analizados": cartera.get("outcomes_analizados", 0),
        },
        "semaforo":     semaforo,
        "analisis_ia":  analisis_ia,
        "diagnostico":  _parse_diagnostico(analisis_ia),
        "plan_acciones": plan_acciones,
        "plan_accion":   plan_acciones,        # alias para la API
    }

    await db.cfo_informes.insert_one(informe)
    informe.pop("_id", None)

    # Generar alertas para dimensiones en ROJO / AMARILLO
    # Dedup: no insertar si ya hay alerta no resuelta de la misma dimensión y periodo
    alertas_existentes = await db.cfo_alertas.distinct(
        "dimension", {"resuelta": False, "periodo": datos["periodo"]}
    )
    for dim, color in semaforo.items():
        if dim == "metricas" or dim in alertas_existentes:
            continue
        if color == "ROJO":
            await db.cfo_alertas.insert_one({
                "id":        str(uuid.uuid4()),
                "dimension": dim,
                "color":     color,
                "mensaje":   f"Alerta crítica: {dim.upper()} en ROJO — {datos['periodo']}",
                "periodo":   datos["periodo"],
                "timestamp": now_iso,
                "urgencia":  3,
                "resuelta":  False,
                "estado":    "nueva",
            })
        elif color == "AMARILLO":
            await db.cfo_alertas.insert_one({
                "id":        str(uuid.uuid4()),
                "dimension": dim,
                "color":     color,
                "mensaje":   f"Atención: {dim.upper()} en AMARILLO — {datos['periodo']}",
                "periodo":   datos["periodo"],
                "timestamp": now_iso,
                "urgencia":  2,
                "resuelta":  False,
                "estado":    "nueva",
            })

    return informe


# ── 10. process_cfo_query ──────────────────────────────────────────────────────

async def process_cfo_query(message: str, db, user: dict, session_id: str) -> dict:
    """Procesa consulta financiera/CFO desde el chat del agente."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    try:
        datos      = await consolidar_datos_financieros(db)
        pyg        = await analizar_pyg(datos)
        semaforo   = await generar_semaforo(datos)
        cartera    = await analizar_cartera(datos)
        tributaria = await analizar_exposicion_tributaria(datos)
        flujo      = await analizar_flujo_caja(datos)
        inventario = await analizar_inventario(datos)
        kpis       = await analizar_kpis_comerciales(datos)

        contexto = {
            "periodo":   datos["periodo"],
            "pyg":       pyg,
            "semaforo":  {k: v for k, v in semaforo.items() if k != "metricas"},
            "metricas":  semaforo.get("metricas", {}),
            "cartera": {
                "tasa_mora_pct": cartera["tasa_mora_pct"],
                "total_cartera": cartera["total_cartera"],
                "en_mora":       cartera["en_mora"],
                "top_morosos":   cartera["top_morosos"][:3],
            },
            "inventario": inventario,
            "flujo_caja": flujo,
            "tributario": {
                "iva_neto":           tributaria.get("iva_neto_trimestre"),
                "ica_estimado":       tributaria.get("ica_estimado"),
                "tarifa_ica_por_mil": tributaria.get("tarifa_ica_por_mil"),
                "alertas":            tributaria.get("alertas_tributarias", []),
            },
            "kpis": kpis,
        }

        _query_client = anthropic.AsyncAnthropic(api_key=api_key)
        prompt = (
            f"CONTEXTO FINANCIERO RODDOS ({datos['periodo']}):\n"
            f"{json.dumps(contexto, ensure_ascii=False)}\n\n"
            f"CONSULTA: {message}"
        )
        _query_resp = await _query_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=(
                "Eres el Agente CFO de RODDOS Colombia. Respondes preguntas financieras "
                "con datos reales. Sé conciso, usa cifras. Responde en español."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        response = _query_resp.content[0].text

        return {
            "message":        response,
            "pending_action": None,
            "session_id":     session_id,
            "source":         "cfo_agent",
        }
    except Exception as e:
        logger.error(f"[CFO] process_cfo_query: {e}")
        return {
            "message":        f"Error consultando datos CFO: {str(e)}",
            "pending_action": None,
            "session_id":     session_id,
        }
