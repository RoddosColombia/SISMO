"""
accounting_engine.py — Motor de Lógica Contable RODDOS (BUILD 21)

Módulo 1: Lógica Contable Profunda
- Clasificación automática de transacciones
- Cálculo de retenciones (ReteFuente, ReteICA, IVA)
- Diagnóstico de asientos contables
- Seguimiento del ciclo contable
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constantes Colombia 2025 ──────────────────────────────────────────────────
UVT_2025 = 49799
SMLMV_2025 = 1423500
AUX_TRANSPORTE_2025 = 200000

# Umbrales para retención (en pesos)
UMBRAL_SERVICIOS_RETEFUENTE = 4 * UVT_2025      # $199.196
UMBRAL_COMPRAS_RETEFUENTE   = 27 * UVT_2025     # $1.344.573
UMBRAL_HONORARIOS           = 1 * UVT_2025      # $49.799

# Tarifa ReteICA Bogotá por mil
RETEICA_SERVICIOS_BOGOTA   = 11.04 / 1000   # 0.01104 (11.04‰)
RETEICA_INDUSTRIA_BOGOTA   = 4.14  / 1000   # 0.00414 (4.14‰)
RETEICA_COMERCIO_BOGOTA    = 3.45  / 1000   # 0.00345 (3.45‰)

# ── Mapa de clasificación automática ─────────────────────────────────────────

CLASIFICACION_RULES = [
    # Palabras clave → (categoria, subcategoria, alegra_id, tipo_retencion, aplica_reteica)
    (["arriendo", "arrendamiento", "alquiler", "calle 127", "local comercial", "oficina"],
     "Operaciones", "Arriendo", 5480, "arrendamiento_3.5", False),

    (["honorario", "asesoría", "asesoria", "consultoría", "consultoria", "abogado", "contador",
      "profesional independiente", "prestación de servicios profesionales"],
     "Personal", "Honorarios", 5475, "honorarios_pn", True),

    (["salario", "sueldo", "nómina", "nomina", "empleado", "trabajador", "prima", "cesantía",
      "cesantia", "vacaciones", "prestaciones", "dotación", "dotacion"],
     "Personal", "Salarios", 5462, "ninguna", False),

    (["seguridad social", "aportes sociales", "eps", "afp", "arl", "pensión", "pension",
      "sena", "icbf", "parafiscales"],
     "Personal", "Seguridad_Social", 5472, "ninguna", False),

    (["teléfono", "telefono", "internet", "celular", "móvil", "movil", "telefonía", "telefonia",
      "datos", "banda ancha", "claro", "movistar", "tigo", "etb"],
     "Operaciones", "Telefonia", 5487, "servicios_4", True),

    (["acueducto", "agua", "alcantarillado", "gas", "energía", "energia", "eléctrico", "electrico",
      "epm", "codensa", "emcali", "servicios públicos", "servicios publicos"],
     "Operaciones", "Servicios_Publicos", 5485, "servicios_4", True),

    (["mantenimiento", "reparación", "reparacion", "asistencia técnica", "asistencia tecnica",
      "soporte", "técnico", "tecnico"],
     "Operaciones", "Mantenimiento", 5483, "servicios_4", True),

    (["aseo", "limpieza", "vigilancia", "seguridad física", "seguridad fisica", "portería",
      "porteria", "jardinería", "jardineria"],
     "Operaciones", "Aseo", 5482, "servicios_4", True),

    (["transporte", "domicilio", "mensajería", "mensajeria", "despacho", "envío", "envio",
      "flete", "taxi", "uber", "remis"],
     "Operaciones", "Transporte", 5499, "transporte_3.5", True),

    (["papelería", "papeleria", "útiles", "utiles", "tóner", "toner", "papel", "impresión",
      "impresion", "cartuchos"],
     "Operaciones", "Papeleria", 5497, "ninguna", False),

    (["combustible", "gasolina", "aceite", "lubricante", "gasolinera", "estación", "estacion"],
     "Operaciones", "Combustible", 5498, "ninguna", False),

    (["publicidad", "marketing", "redes sociales", "pauta", "campaña", "campaña", "anuncio",
      "diseño gráfico", "diseño grafico", "impresos", "volantes"],
     "Marketing", "Publicidad", 5495, "servicios_4", True),

    (["eventos", "activación", "activacion", "lanzamiento", "degustación", "degustacion"],
     "Marketing", "Eventos", 5495, "servicios_4", True),

    (["ica", "industria y comercio", "predial", "impuesto", "retención tributaria", "retencion",
      "dian", "declaración", "declaracion"],
     "Impuestos", "ICA", 5478, "ninguna", False),

    (["gmf", "4x1000", "gravamen", "movimiento financiero", "cuatro por mil"],
     "Financiero", "GMF", 5509, "ninguna", False),

    (["intereses", "interés", "interes", "crédito", "credito", "préstamo", "prestamo",
      "financiamiento", "financiación", "financiacion", "cuota crédito"],
     "Financiero", "Intereses", 5533, "ninguna", False),

    (["comisión bancaria", "comision bancaria", "gastos bancarios", "manejo cuenta"],
     "Financiero", "Comisiones_Bancarias", 5508, "ninguna", False),

    (["seguro", "póliza", "poliza", "aseguradora", "seguros"],
     "Financiero", "Seguros", 5493, "servicios_4", True),

    (["software", "sistema", "plataforma", "licencia", "suscripción", "suscripcion",
      "emergent", "alegra", "mercately", "nube", "cloud"],
     "Operaciones", "Mantenimiento", 5484, "servicios_4", True),
]

# ── Mapa de IDs de retenciones en Alegra ─────────────────────────────────────

RETENCIONES_ALEGRA = {
    "honorarios_pn":      {"alegra_id": 5381, "codigo": "23651501", "tarifa": 0.10, "nombre": "ReteFuente Honorarios 10% PN"},
    "honorarios_pj":      {"alegra_id": 5382, "codigo": "23651502", "tarifa": 0.11, "nombre": "ReteFuente Honorarios 11% PJ"},
    "servicios_4":        {"alegra_id": 5383, "codigo": "23652501", "tarifa": 0.04, "nombre": "ReteFuente Servicios 4%"},
    "servicios_6":        {"alegra_id": None, "codigo": None,       "tarifa": 0.06, "nombre": "ReteFuente Servicios Especializados 6%"},
    "arrendamiento_3.5":  {"alegra_id": 5386, "codigo": "23653001", "tarifa": 0.035, "nombre": "ReteFuente Arriendo 3.5%"},
    "compras_2.5":        {"alegra_id": 5388, "codigo": "23654001", "tarifa": 0.025, "nombre": "ReteFuente Compras 2.5%"},
    "transporte_3.5":     {"alegra_id": None, "codigo": None,       "tarifa": 0.035, "nombre": "ReteFuente Transporte 3.5%"},
    "reteica":            {"alegra_id": 5392, "codigo": "23680501", "tarifa": RETEICA_SERVICIOS_BOGOTA, "nombre": "ReteICA 11.04‰ Bogotá"},
    "reteiva_15":         {"alegra_id": 5410, "codigo": "241205",   "tarifa": 0.15,  "nombre": "ReteIVA 15% del IVA"},
    "ninguna":            {"alegra_id": None, "codigo": None,       "tarifa": 0.0,   "nombre": "Sin retención"},
}

# Cuenta proveedores
CUENTA_PROVEEDORES_ALEGRA_ID = 5376

# ── 1. Clasificación automática de transacciones ──────────────────────────────

def clasificar_transaccion(
    descripcion: str,
    proveedor: str = "",
    monto: float = 0,
    tipo_proveedor: str = "UNCLEAR",  # PN | PJ | UNCLEAR
) -> dict:
    """Clasifica automáticamente una transacción a partir de su descripción.

    Returns:
        {
            categoria, subcategoria, alegra_id,
            tipo_retencion, aplica_reteica,
            confianza: float (0-1),
            razon: str
        }
    """
    texto = f"{descripcion} {proveedor}".lower()
    texto = re.sub(r'[^\w\s]', ' ', texto)  # normalizar
    words = set(texto.split())

    best_match = None
    best_score = 0

    for keywords, categoria, subcategoria, alegra_id, tipo_ret, aplica_ica in CLASIFICACION_RULES:
        score = sum(1 for kw in keywords if kw in texto)
        if score > best_score:
            best_score = score
            best_match = (categoria, subcategoria, alegra_id, tipo_ret, aplica_ica, keywords[:2])

    if not best_match or best_score == 0:
        return {
            "categoria": "Otros",
            "subcategoria": "Varios",
            "alegra_id": 5493,
            "tipo_retencion": "ninguna",
            "aplica_reteica": False,
            "confianza": 0.0,
            "razon": "Sin coincidencia en reglas de clasificación — usando cuenta fallback Gastos generales",
        }

    cat, subcat, alid, tipo_ret, aplica_ica, matched_kw = best_match

    # Ajustar tipo retención si sabemos que es PN vs PJ para honorarios
    if tipo_ret == "honorarios_pn" and tipo_proveedor == "PJ":
        tipo_ret = "honorarios_pj"
    elif tipo_ret == "honorarios_pn" and tipo_proveedor == "UNCLEAR":
        tipo_ret = "honorarios_pn"  # será revisado por el agente

    confianza = min(1.0, best_score / max(len(matched_kw), 1))

    return {
        "categoria": cat,
        "subcategoria": subcat,
        "alegra_id": alid,
        "tipo_retencion": tipo_ret,
        "aplica_reteica": aplica_ica,
        "confianza": round(confianza, 2),
        "razon": f"Clasificado por palabras clave: {', '.join(matched_kw[:2])}",
    }


# ── 2. Cálculo de retenciones ─────────────────────────────────────────────────

def calcular_retenciones(
    tipo_proveedor: str,        # PN | PJ
    tipo_gasto: str,            # arriendo | honorarios | servicios | compras | etc.
    monto_bruto: float,
    es_autoretenedor: bool = False,
    aplica_iva: bool = False,
    aplica_reteica: bool = False,
    ciudad: str = "Bogota",
) -> dict:
    """Calcula todas las retenciones aplicables a una transacción Colombia.

    Returns:
        {
            base, iva_valor, retefuente_valor, retefuente_pct,
            reteica_valor, reteica_pct, reteiva_valor,
            total_retenciones, neto_a_pagar,
            entradas_causacion: [{"cuenta_id": ..., "monto": ..., "tipo": "debito|credito", "nombre": ...}],
            advertencias: []
        }
    """
    result = {
        "base": monto_bruto,
        "iva_valor": 0.0,
        "retefuente_valor": 0.0,
        "retefuente_pct": 0.0,
        "retefuente_tipo": "ninguna",
        "reteica_valor": 0.0,
        "reteica_pct": 0.0,
        "reteiva_valor": 0.0,
        "total_retenciones": 0.0,
        "neto_a_pagar": monto_bruto,
        "entradas_causacion": [],
        "advertencias": [],
    }

    # IVA
    if aplica_iva:
        result["iva_valor"] = round(monto_bruto * 0.19)

    # ReteFuente (nunca aplicar si es autoretenedor)
    if not es_autoretenedor:
        _tipo = tipo_gasto.lower()

        if "honorario" in _tipo:
            if tipo_proveedor == "PN":
                if monto_bruto >= UMBRAL_HONORARIOS:
                    result["retefuente_pct"] = 0.10
                    result["retefuente_tipo"] = "honorarios_pn"
            elif tipo_proveedor == "PJ":
                result["retefuente_pct"] = 0.11
                result["retefuente_tipo"] = "honorarios_pj"

        elif "arriendo" in _tipo or "arrendamiento" in _tipo:
            result["retefuente_pct"] = 0.035
            result["retefuente_tipo"] = "arrendamiento_3.5"

        elif "servicio" in _tipo:
            if monto_bruto >= UMBRAL_SERVICIOS_RETEFUENTE:
                result["retefuente_pct"] = 0.04
                result["retefuente_tipo"] = "servicios_4"

        elif "compra" in _tipo:
            if monto_bruto >= UMBRAL_COMPRAS_RETEFUENTE:
                result["retefuente_pct"] = 0.025
                result["retefuente_tipo"] = "compras_2.5"

        elif "transporte" in _tipo:
            if monto_bruto >= UMBRAL_SERVICIOS_RETEFUENTE:
                result["retefuente_pct"] = 0.035
                result["retefuente_tipo"] = "transporte_3.5"

        result["retefuente_valor"] = round(monto_bruto * result["retefuente_pct"])

    else:
        result["advertencias"].append(
            "Proveedor autoretenedor — ReteFuente omitida según configuración."
        )

    # ReteICA (solo en Bogotá, solo servicios/honorarios)
    if aplica_reteica and ciudad.lower() in ("bogota", "bogotá"):
        result["reteica_pct"] = RETEICA_SERVICIOS_BOGOTA
        result["reteica_valor"] = round(monto_bruto * result["reteica_pct"])

    # ReteIVA (15% del IVA, cuando aplica)
    if aplica_iva and result["iva_valor"] > 0 and not es_autoretenedor:
        result["reteiva_valor"] = round(result["iva_valor"] * 0.15)

    # Totales
    total_ret = (
        result["retefuente_valor"]
        + result["reteica_valor"]
        + result["reteiva_valor"]
    )
    result["total_retenciones"] = total_ret
    result["neto_a_pagar"] = monto_bruto + result["iva_valor"] - total_ret

    return result


def formatear_retenciones_para_prompt(ret: dict) -> str:
    """Formatea el resultado de calcular_retenciones para inyectar en el prompt del agente."""
    lines = [f"BASE: ${ret['base']:,.0f}"]
    if ret["iva_valor"] > 0:
        lines.append(f"IVA 19%: +${ret['iva_valor']:,.0f}")
    if ret["retefuente_valor"] > 0:
        lines.append(
            f"ReteFuente {ret['retefuente_tipo']} ({ret['retefuente_pct']*100:.1f}%): "
            f"-${ret['retefuente_valor']:,.0f}"
        )
    if ret["reteica_valor"] > 0:
        lines.append(f"ReteICA 11.04‰: -${ret['reteica_valor']:,.0f}")
    if ret["reteiva_valor"] > 0:
        lines.append(f"ReteIVA 15% del IVA: -${ret['reteiva_valor']:,.0f}")
    lines.append(f"NETO A PAGAR: ${ret['neto_a_pagar']:,.0f}")
    if ret.get("advertencias"):
        for adv in ret["advertencias"]:
            lines.append(f"⚠️ {adv}")
    return "\n".join(lines)


# ── 3. Diagnóstico de asientos contables ─────────────────────────────────────

VALID_ALEGRA_IDS: set[int] = {
    # Bancos
    5314, 5315, 5318, 5319, 5321, 5322, 5310,
    # Cartera/Activos
    5326, 5327, 5348, 5349, 5329,
    # Ingresos
    5442, 5445, 5456, 5453, 5451,
    5455, 5441, 5436, 5457,  # Ingresos no operacionales
    # Costos
    5520, 5523, 5531,
    # Pasivos IVA
    5404, 5406, 5408,
    # Pasivos Retenciones
    5381, 5382, 5383, 5386, 5388, 5392, 5410, 5376,
    # Gastos frecuentes
    5480, 5462, 5478, 5484, 5487, 5507, 5508, 5509, 5497,
    5475, 5476, 5472, 5470, 5469, 5468, 5466,
    5482, 5483, 5485, 5495, 5493, 5498, 5499,
    5533, 5504,
}


def diagnosticar_asiento(entries: list[dict], fecha: str = "", periodo: str = "") -> dict:
    """Valida un asiento contable antes de enviarlo a Alegra.

    Args:
        entries: [{"id": int, "debit": float, "credit": float}]
        fecha: YYYY-MM-DD
        periodo: contexto del período contable

    Returns:
        {
            valido: bool,
            errores: [str],
            advertencias: [str],
            total_debito: float,
            total_credito: float,
            diferencia: float,
        }
    """
    errores = []
    advertencias = []

    total_debito  = sum(float(e.get("debit",  0) or 0) for e in entries)
    total_credito = sum(float(e.get("credit", 0) or 0) for e in entries)
    diferencia    = abs(round(total_debito - total_credito, 2))

    # 1. Balance débito = crédito
    if diferencia > 0.01:
        errores.append(
            f"Asiento DESCUADRADO: débitos=${total_debito:,.0f} ≠ créditos=${total_credito:,.0f} "
            f"(diferencia: ${diferencia:,.0f}). Verifica cada entrada."
        )

    # 2. IDs de cuentas válidos
    for idx, entry in enumerate(entries):
        acc_id = entry.get("id")
        if not acc_id:
            errores.append(f"Entrada {idx+1}: falta el ID de cuenta.")
            continue
        try:
            acc_id_int = int(acc_id)
        except (TypeError, ValueError):
            errores.append(f"Entrada {idx+1}: ID '{acc_id}' no es numérico.")
            continue

        if acc_id_int not in VALID_ALEGRA_IDS:
            advertencias.append(
                f"Entrada {idx+1}: ID {acc_id_int} no está en el plan de cuentas conocido de RODDOS. "
                "Verifica que sea un ID real de Alegra para esta empresa."
            )

        # 3. Monto cero en ambos débito y crédito
        d = float(entry.get("debit",  0) or 0)
        c = float(entry.get("credit", 0) or 0)
        if d == 0 and c == 0:
            errores.append(f"Entrada {idx+1} (cuenta {acc_id}): débito y crédito son ambos cero.")

        # 4. Monto negativo
        if d < 0 or c < 0:
            errores.append(f"Entrada {idx+1} (cuenta {acc_id}): montos negativos no permitidos.")

    # 5. Al menos 2 entradas
    if len(entries) < 2:
        errores.append("El asiento debe tener al menos 2 entradas (1 débito + 1 crédito).")

    # 6. Fecha válida
    if fecha:
        try:
            dt = datetime.fromisoformat(fecha)
            hoy = datetime.now(timezone.utc).date()
            if dt.year < 2020 or dt.year > 2030:
                advertencias.append(f"Fecha {fecha} parece incorrecta. ¿Es el año correcto?")
        except ValueError:
            errores.append(f"Fecha '{fecha}' inválida. Usa formato YYYY-MM-DD.")

    return {
        "valido": len(errores) == 0,
        "errores": errores,
        "advertencias": advertencias,
        "total_debito": total_debito,
        "total_credito": total_credito,
        "diferencia": diferencia,
    }


def formatear_diagnostico_para_prompt(diag: dict) -> str:
    """Formatea el diagnóstico para inyectar en el prompt del agente."""
    if diag["valido"] and not diag["advertencias"]:
        return f"✅ Asiento válido. Débito=${diag['total_debito']:,.0f} = Crédito=${diag['total_credito']:,.0f}"

    lines = []
    if not diag["valido"]:
        lines.append("❌ ASIENTO INVÁLIDO — no enviar a Alegra hasta corregir:")
        for err in diag["errores"]:
            lines.append(f"  • ERROR: {err}")
    else:
        lines.append(f"✅ Balance: Débito=${diag['total_debito']:,.0f} = Crédito=${diag['total_credito']:,.0f}")

    if diag["advertencias"]:
        lines.append("⚠️ Advertencias:")
        for adv in diag["advertencias"]:
            lines.append(f"  • {adv}")

    return "\n".join(lines)


# ── 4. Ciclo contable ─────────────────────────────────────────────────────────

CICLO_FASES = ["causacion", "aprobacion", "pago", "conciliacion", "cierre"]

async def obtener_estado_ciclo(db, entidad_tipo: str, entidad_id: str) -> dict:
    """Obtiene el estado del ciclo contable para una entidad (factura, proveedor, período).

    Returns:
        {
            fase_actual: str,
            pasos_completados: [str],
            proximos_pasos: [str],
            bloqueantes: [str],
        }
    """
    pasos_completados = []
    proximos_pasos    = []
    bloqueantes       = []

    try:
        if entidad_tipo == "loanbook":
            lb = await db.loanbook.find_one({"id": entidad_id}, {"_id": 0})
            if not lb:
                return {"error": "Loanbook no encontrado"}

            estado = lb.get("estado", "")
            if lb.get("factura_alegra_id"):
                pasos_completados.append("causacion — Factura de venta creada en Alegra")
            if estado in ("activo", "mora"):
                pasos_completados.append("entrega — Moto entregada al cliente")
                pasos_completados.append("activacion — Loanbook activo con plan de cuotas")
            if lb.get("saldo_pendiente", 0) == 0:
                pasos_completados.append("pago — Crédito cancelado en su totalidad")

            if not lb.get("factura_alegra_id"):
                bloqueantes.append("No tiene factura de venta en Alegra")
            if estado == "pendiente_entrega":
                proximos_pasos.append("Registrar entrega de la moto")
            if estado in ("activo", "mora") and lb.get("saldo_pendiente", 0) > 0:
                proximos_pasos.append(f"Cobrar cuotas pendientes (saldo: ${lb.get('saldo_pendiente',0):,.0f})")

        elif entidad_tipo == "periodo":
            # Period closing check
            from datetime import date
            hoy = date.today()
            periodo_iso = entidad_id  # "2026-01"

            journals = await db.ingresos_registrados.count_documents(
                {"fecha": {"$regex": f"^{periodo_iso}"}}
            )
            gastos = await db.roddos_events.count_documents(
                {"event_type": "asiento.contable.creado", "timestamp": {"$regex": f"^{periodo_iso}"}}
            )

            if journals > 0 or gastos > 0:
                pasos_completados.append(f"causacion — {gastos} asientos de gasto + {journals} ingresos en {periodo_iso}")
            else:
                bloqueantes.append(f"No hay asientos registrados para {periodo_iso}")
                proximos_pasos.append("Registrar gastos e ingresos del período")

    except Exception as e:
        logger.error(f"[accounting_engine] obtener_estado_ciclo error: {e}")

    fase_actual = CICLO_FASES[len(pasos_completados)] if len(pasos_completados) < len(CICLO_FASES) else "cierre"
    return {
        "entidad_tipo": entidad_tipo,
        "entidad_id": entidad_id,
        "fase_actual": fase_actual,
        "pasos_completados": pasos_completados,
        "proximos_pasos": proximos_pasos,
        "bloqueantes": bloqueantes,
    }


# ── 5. Detección de anomalías contables ───────────────────────────────────────

async def detectar_anomalias(db) -> list[dict]:
    """Detecta anomalías contables en los datos actuales.

    Returns: lista de alertas [{tipo, mensaje, severidad, accion_sugerida}]
    """
    alertas = []

    try:
        # 1. CXC socios con saldo pendiente vencido
        from datetime import date
        hoy = date.today().isoformat()

        cxc_vencidas = await db.cxc_socios.find(
            {"estado": {"$ne": "pagada"}, "fecha": {"$lt": hoy}},
            {"_id": 0, "socio": 1, "monto": 1, "saldo_pendiente": 1, "fecha": 1}
        ).to_list(20)

        if cxc_vencidas:
            total_cxc = sum(c.get("saldo_pendiente", 0) or c.get("monto", 0) for c in cxc_vencidas)
            socios = list({c["socio"] for c in cxc_vencidas})
            alertas.append({
                "tipo": "cxc_socios_vencidas",
                "mensaje": (
                    f"CXC Socios con saldo pendiente: ${total_cxc:,.0f} "
                    f"({', '.join(socios)}). Gestionar cobro."
                ),
                "severidad": "alta" if total_cxc > 1_000_000 else "media",
                "accion_sugerida": "Registrar abono CXC socios o acordar plan de pago.",
            })

        # 2. Loanbooks en mora elevada (DPD > 15)
        lbs_mora_alta = await db.loanbook.count_documents(
            {"estado": "mora", "dpd": {"$gt": 15}}
        )
        if lbs_mora_alta > 0:
            alertas.append({
                "tipo": "mora_elevada",
                "mensaje": f"{lbs_mora_alta} loanbook(s) con DPD > 15 días en mora.",
                "severidad": "alta" if lbs_mora_alta > 3 else "media",
                "accion_sugerida": "Activar protocolo de recuperación en RADAR.",
            })

        # 3. Gastos sin clasificar (eventos sin categoría)
        gastos_sin_cat = await db.roddos_events.count_documents(
            {"event_type": "asiento.contable.creado", "categoria": {"$exists": False}}
        )
        if gastos_sin_cat > 5:
            alertas.append({
                "tipo": "gastos_sin_clasificar",
                "mensaje": f"{gastos_sin_cat} asientos sin categoría detectados.",
                "severidad": "baja",
                "accion_sugerida": "Revisar y clasificar asientos en módulo Contabilidad.",
            })

        # 4. Inventario descuadrado
        total_inv = await db.inventario_motos.count_documents({})
        disp = await db.inventario_motos.count_documents({"estado": "Disponible"})
        vend = await db.inventario_motos.count_documents({"estado": {"$in": ["Vendida", "Entregada"]}})
        anul = await db.inventario_motos.count_documents({"estado": "Anulada"})
        otros = total_inv - disp - vend - anul
        if otros != 0:
            alertas.append({
                "tipo": "inventario_descuadrado",
                "mensaje": f"Inventario descuadrado: {otros} moto(s) sin estado definido.",
                "severidad": "media",
                "accion_sugerida": "Auditar inventario: 'audita el inventario' en el chat.",
            })

    except Exception as e:
        logger.error(f"[accounting_engine] detectar_anomalias error: {e}")

    return alertas


# ── 6. Resumen semanal CFO ────────────────────────────────────────────────────

async def generar_resumen_semanal(db) -> dict:
    """Genera el resumen semanal del CFO para inyectar en el chat del agente.

    Returns: {resumen_texto, alertas, fecha_generacion}
    """
    from datetime import date, timedelta
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
    fin_semana    = inicio_semana + timedelta(days=6)    # domingo

    resumen = {
        "fecha_generacion": hoy.isoformat(),
        "semana": f"{inicio_semana.isoformat()} al {fin_semana.isoformat()}",
        "loanbooks_activos": 0,
        "recaudo_proyectado": 0,
        "gastos_fijos": 0,
        "deficit_superavit": 0,
        "alertas": [],
        "resumen_texto": "",
    }

    try:
        # Loanbooks activos
        lbs = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora"]}},
            {"_id": 0, "cuotas": 1}
        ).to_list(100)
        resumen["loanbooks_activos"] = len(lbs)

        # Recaudo esta semana (cuotas con vencimiento lunes-domingo)
        lunes_iso   = inicio_semana.isoformat()
        domingo_iso = fin_semana.isoformat()
        recaudo = 0
        for lb in lbs:
            for c in lb.get("cuotas", []):
                if (c.get("estado") in ("pendiente", "vencida")
                        and lunes_iso <= (c.get("fecha_vencimiento") or "") <= domingo_iso):
                    recaudo += float(c.get("valor", 0) or 0)
        resumen["recaudo_proyectado"] = recaudo

        # Gastos fijos configurados
        cfg_fin = await db.cfo_financiero_config.find_one({}, {"_id": 0}) or {}
        gastos_sem = float(cfg_fin.get("gastos_fijos_semanales") or 7_500_000)
        resumen["gastos_fijos"] = gastos_sem

        resumen["deficit_superavit"] = recaudo - gastos_sem

        # Anomalías
        anomalias = await detectar_anomalias(db)
        resumen["alertas"] = anomalias

        # Texto
        signo = "+" if resumen["deficit_superavit"] >= 0 else ""
        resumen["resumen_texto"] = (
            f"📊 RESUMEN SEMANAL CFO — {resumen['semana']}\n"
            f"• Créditos activos: {resumen['loanbooks_activos']}\n"
            f"• Recaudo proyectado esta semana: ${recaudo:,.0f}\n"
            f"• Gastos fijos: ${gastos_sem:,.0f}\n"
            f"• {'Superávit' if resumen['deficit_superavit'] >= 0 else 'Déficit'}: "
            f"{signo}${abs(resumen['deficit_superavit']):,.0f}\n"
        )
        if anomalias:
            resumen["resumen_texto"] += f"\n⚠️ {len(anomalias)} alertas detectadas:\n"
            for a in anomalias:
                resumen["resumen_texto"] += f"  • [{a['severidad'].upper()}] {a['mensaje']}\n"

    except Exception as e:
        logger.error(f"[accounting_engine] generar_resumen_semanal error: {e}")
        resumen["resumen_texto"] = f"Error al generar resumen semanal: {e}"

    return resumen
