"""cfo_agent.py — BUILD 4: Agente CFO de RODDOS.

Funciones:
  consolidar_datos_financieros(db)  → dict
  analizar_pyg(datos)               → dict
  analizar_cartera(datos)           → dict
  generar_semaforo(datos)           → dict
  generar_informe_cfo(db)           → dict  (llama a Claude, guarda en cfo_informes)
  process_cfo_query(msg, db, user, session_id)  → dict  (para chat routing)
"""
import os
import uuid
import json
import logging
from datetime import datetime, timezone, date, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

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

    # ── Alegra: journal-entries del mes ──────────────────────────────────────
    journals_items: list = []
    try:
        resp = await alegra.request(
            "journal-entries",
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
            params={"date_afterOrNow": mes_inicio, "date_beforeOrNow": mes_fin, "status": "open"},
        )
        ventas_alegra = v if isinstance(v, list) else []
    except Exception as e:
        logger.warning(f"[CFO] invoices: {e}")

    # ── Portfolio health (shared_state) ──────────────────────────────────────
    portfolio: dict = {}
    try:
        portfolio = await get_portfolio_health(db)
    except Exception as e:
        logger.warning(f"[CFO] portfolio_health: {e}")

    # ── Inventario motos ─────────────────────────────────────────────────────
    motos_all = await db.inventario_motos.find(
        {}, {"_id": 0, "estado": 1, "version": 1, "total": 1, "fecha_entrega": 1}
    ).to_list(2000)
    motos_disponibles = [m for m in motos_all if m.get("estado") == "disponible"]
    motos_vendidas_mes = [
        m for m in motos_all
        if m.get("estado") in ("vendida", "entregada")
        and (m.get("fecha_entrega") or "") >= mes_inicio
    ]

    # ── Loanbook: cobros del mes ──────────────────────────────────────────────
    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora", "recuperacion", "completado"]}},
        {"_id": 0, "cuotas": 1, "codigo": 1, "cliente_nombre": 1,
         "dpd_actual": 1, "interes_mora_acumulado": 1},
    ).to_list(5000)

    cobrado_mes = 0.0
    esperado_mes = 0.0
    mora_cobrada_mes = 0.0

    for loan in loans:
        for cuota in loan.get("cuotas", []):
            fv = cuota.get("fecha_vencimiento", "")
            if mes_inicio <= fv <= mes_fin:
                esperado_mes += cuota.get("valor", 0)
                if cuota.get("estado") == "pagada":
                    cobrado_mes += cuota.get("valor_pagado", cuota.get("valor", 0))
                    mora_cobrada_mes += cuota.get("interes_mora_cobrado", 0)

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
        [l for l in loans if l.get("dpd_actual", 0) > 0],
        key=lambda x: x.get("dpd_actual", 0),
        reverse=True,
    )[:5]
    top_morosos = [
        {"codigo": m.get("codigo"), "cliente": m.get("cliente_nombre"), "dpd": m.get("dpd_actual", 0)}
        for m in loans_mora
    ]

    # ── Configuración CFO ────────────────────────────────────────────────────
    cfo_cfg = await db.cfo_config.find_one({}, {"_id": 0}) or {}

    return {
        "periodo":           hoy.strftime("%B %Y"),
        "mes_inicio":        mes_inicio,
        "mes_fin":           mes_fin,
        "journals_items":    journals_items,
        "ventas_alegra":     ventas_alegra,
        "portfolio":         portfolio,
        "inventario": {
            "total":           len(motos_all),
            "disponibles":     len(motos_disponibles),
            "vendidas_mes":    len(motos_vendidas_mes),
        },
        "cobrado_mes":       cobrado_mes,
        "esperado_mes":      esperado_mes,
        "mora_cobrada_mes":  mora_cobrada_mes,
        "presupuesto":       presupuesto,
        "margenes":          margenes,
        "top_morosos":       top_morosos,
        "loans_activos":     len(loans),
        "catalogo":          catalogo,
        "cfo_cfg":           cfo_cfg,
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
    """Análisis de cartera desde portfolio_health + top morosos."""
    portfolio = datos.get("portfolio", {})
    return {
        "tasa_mora_pct":  portfolio.get("tasa_mora", 0),
        "valor_mora":     portfolio.get("por_estado", {}).get("mora", {}).get("saldo_total", 0),
        "roll_rate":      0,  # BUILD future: add roll_rate to shared_state
        "total_cartera":  portfolio.get("saldo_cartera_total", 0),
        "en_mora":        portfolio.get("en_mora", 0),
        "activos":        portfolio.get("activos", 0),
        "top_morosos":    datos.get("top_morosos", []),
    }


# ── 4. generar_semaforo ───────────────────────────────────────────────────────

async def generar_semaforo(datos: dict) -> dict:
    """Semáforo 5 dimensiones: caja, cartera, ventas, roll_rate, impuestos."""
    pyg = await analizar_pyg(datos)
    cartera = await analizar_cartera(datos)

    tasa_mora = cartera.get("tasa_mora_pct", 0)
    roll_rate = cartera.get("roll_rate", 0)
    cobrado = datos.get("cobrado_mes", 0)
    esperado = datos.get("esperado_mes", 1)
    meta_ventas = datos.get("presupuesto", {}).get("meta_ventas", 0)
    resultado_neto = pyg.get("resultado_neto", 0)
    pct_cobrado = round(cobrado / max(esperado, 1) * 100, 1)
    pct_meta = round(cobrado / meta_ventas * 100, 1) if meta_ventas > 0 else 100.0

    cfo_cfg = datos.get("cfo_cfg", {})
    umbral_mora = float(cfo_cfg.get("umbral_mora_pct", 5))
    umbral_caja = float(cfo_cfg.get("umbral_caja_cop", 5_000_000))

    def _color(rojo: bool, amarillo: bool) -> str:
        if rojo:     return "ROJO"
        if amarillo: return "AMARILLO"
        return "VERDE"

    return {
        "caja":       _color(resultado_neto < 0, 0 < resultado_neto < umbral_caja),
        "cartera":    _color(tasa_mora > 15, umbral_mora <= tasa_mora <= 15),
        "ventas":     _color(pct_meta < 70 and meta_ventas > 0, 70 <= pct_meta < 99 and meta_ventas > 0),
        "roll_rate":  _color(roll_rate > 20, 10 <= roll_rate <= 20),
        "impuestos":  "VERDE",  # BUILD future: DIAN deadline integration
        "metricas": {
            "tasa_mora_pct":     tasa_mora,
            "roll_rate_pct":     roll_rate,
            "pct_cobrado":       pct_cobrado,
            "resultado_neto":    resultado_neto,
            "pct_meta_ventas":   pct_meta,
            "cobrado_mes":       cobrado,
            "esperado_mes":      esperado,
        },
    }


# ── 5. generar_informe_cfo ────────────────────────────────────────────────────

async def generar_informe_cfo(db, triggered_by: str = "manual") -> dict:
    """Genera informe CFO completo con análisis IA. Guarda en cfo_informes."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    now_iso = datetime.now(timezone.utc).isoformat()

    datos   = await consolidar_datos_financieros(db)
    pyg     = await analizar_pyg(datos)
    cartera = await analizar_cartera(datos)
    semaforo = await generar_semaforo(datos)

    resumen = {
        "periodo":    datos["periodo"],
        "pyg":        pyg,
        "cartera":    cartera,
        "semaforo":   {k: v for k, v in semaforo.items() if k != "metricas"},
        "metricas":   semaforo.get("metricas", {}),
        "inventario": datos["inventario"],
        "top_morosos": datos["top_morosos"],
    }

    analisis_ia = ""
    plan_acciones: list[dict] = []

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cfo-informe-{uuid.uuid4().hex[:8]}",
            system_message=(
                "Eres el asesor CFO de RODDOS Colombia — concesionario Auteco en Bogotá. "
                "Analizas datos financieros reales y das recomendaciones accionables y concretas."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        prompt = (
            f"DATOS FINANCIEROS RODDOS — {datos['periodo']}:\n"
            f"{json.dumps(resumen, ensure_ascii=False, indent=2)}\n\n"
            "Genera en español:\n"
            "1) DIAGNÓSTICO: exactamente 3 puntos positivos y 3 negativos con cifras reales.\n"
            "2) PLAN DE ACCIÓN: exactamente 5 líneas, cada una con formato:\n"
            "   ACCIÓN|RESPONSABLE|FECHA|MÉTRICA\n"
            "Sé preciso. Usa solo los números del JSON. No inventes datos."
        )
        analisis_ia = await chat.send_message(UserMessage(text=prompt))

        # Parse plan
        for line in analisis_ia.split("\n"):
            parts = [p.strip() for p in line.strip().split("|")]
            if len(parts) == 4 and parts[0] and not parts[0].startswith("#"):
                plan_acciones.append({
                    "accion":       parts[0],
                    "responsable":  parts[1],
                    "fecha":        parts[2],
                    "metrica":      parts[3],
                    "estado":       "pendiente",
                })
    except Exception as e:
        logger.error(f"[CFO] Error IA: {e}")
        analisis_ia = "Análisis IA no disponible. Revisa la configuración de la clave API."

    informe = {
        "id":                str(uuid.uuid4()),
        "periodo":           datos["periodo"],
        "fecha_generacion":  now_iso,
        "generado_por":      triggered_by,
        "datos_financieros": {"pyg": pyg, "cartera": cartera, "inventario": datos["inventario"]},
        "semaforo":          semaforo,
        "analisis_ia":       analisis_ia,
        "plan_acciones":     plan_acciones,
    }

    await db.cfo_informes.insert_one(informe)
    informe.pop("_id", None)

    # Generar alertas para dimensiones en ROJO
    for dim, color in semaforo.items():
        if dim == "metricas":
            continue
        if color == "ROJO":
            await db.cfo_alertas.insert_one({
                "id":          str(uuid.uuid4()),
                "dimension":   dim,
                "color":       color,
                "mensaje":     f"Alerta crítica: {dim.upper()} en ROJO — {datos['periodo']}",
                "periodo":     datos["periodo"],
                "timestamp":   now_iso,
                "urgencia":    3,
                "resuelta":    False,
            })
        elif color == "AMARILLO":
            await db.cfo_alertas.insert_one({
                "id":          str(uuid.uuid4()),
                "dimension":   dim,
                "color":       color,
                "mensaje":     f"Atención: {dim.upper()} en AMARILLO — {datos['periodo']}",
                "periodo":     datos["periodo"],
                "timestamp":   now_iso,
                "urgencia":    2,
                "resuelta":    False,
            })

    return informe


# ── 6. process_cfo_query ──────────────────────────────────────────────────────

async def process_cfo_query(message: str, db, user: dict, session_id: str) -> dict:
    """Procesa consulta financiera/CFO desde el chat del agente."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    try:
        datos   = await consolidar_datos_financieros(db)
        pyg     = await analizar_pyg(datos)
        semaforo = await generar_semaforo(datos)
        cartera = await analizar_cartera(datos)

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
            "inventario": datos["inventario"],
        }

        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=(
                "Eres el Agente CFO de RODDOS Colombia. Respondes preguntas financieras "
                "con datos reales. Sé conciso, usa cifras. Responde en español."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        prompt = (
            f"CONTEXTO FINANCIERO RODDOS ({datos['periodo']}):\n"
            f"{json.dumps(contexto, ensure_ascii=False)}\n\n"
            f"CONSULTA: {message}"
        )
        response = await chat.send_message(UserMessage(text=prompt))

        return {
            "message":       response,
            "pending_action": None,
            "session_id":    session_id,
            "source":        "cfo_agent",
        }
    except Exception as e:
        logger.error(f"[CFO] process_cfo_query: {e}")
        return {
            "message":       f"Error consultando datos CFO: {str(e)}",
            "pending_action": None,
            "session_id":    session_id,
        }
