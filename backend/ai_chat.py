import os
import re
import uuid
import json
import base64
import csv
import io
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
import anthropic

logger = logging.getLogger(__name__)


# ── Helpers para context builders (evitar NoneType format errors) ─────────────

def _safe_num(val, default: float = 0) -> float:
    """Safe numeric: returns `default` if val is None or non-numeric."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_str(val, default: str = "") -> str:
    """Safe string: returns `default` if val is None."""
    if val is None:
        return default
    return str(val)


# ── Tabular file (CSV/Excel) → text helper ───────────────────────────────────
_TABULAR_TYPES = {
    "text/csv", "application/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
_GASTOS_COLS = {"fecha", "monto", "descripcion", "categoria", "proveedor"}

def _is_tabular_file(file_name: str, file_type: str) -> bool:
    name = (file_name or "").lower()
    return (
        file_type in _TABULAR_TYPES
        or name.endswith(".csv")
        or name.endswith(".xlsx")
        or name.endswith(".xls")
    )

def _tabular_to_text(file_content_b64: str, file_name: str, file_type: str) -> tuple[str, list, list]:
    """Decode base64 CSV/Excel and return (text_table, headers, rows)."""
    raw = base64.b64decode(file_content_b64)
    name = (file_name or "").lower()
    headers = []
    rows = []

    try:
        if name.endswith(".xlsx") or name.endswith(".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
            ws = wb.active
            data = [[str(c.value) if c.value is not None else "" for c in row] for row in ws.iter_rows()]
        else:
            # CSV — try UTF-8 then latin-1
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            # Remove null bytes
            text = text.replace("\x00", "")
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            data = list(csv.reader(io.StringIO(text), dialect))

        if not data:
            return "Archivo vacío.", [], []

        headers = [h.strip().lower() for h in data[0]]
        rows = data[1:]  # raw row lists

        # Build text table (max 60 rows to avoid token overflow)
        display_rows = rows[:60]
        lines = [" | ".join(data[0])]  # header with original casing
        lines.append("-" * min(80, len(lines[0])))
        for r in display_rows:
            lines.append(" | ".join(r))
        if len(rows) > 60:
            lines.append(f"... ({len(rows) - 60} filas adicionales no mostradas)")

        return "\n".join(lines), headers, rows

    except Exception as e:
        return f"Error al leer el archivo: {str(e)}", [], []


def _is_gastos_csv(headers: list) -> bool:
    """Detect if CSV columns match the gastos template format."""
    h_set = set(h.strip().lower() for h in headers)
    return len(_GASTOS_COLS & h_set) >= 3  # at least 3 of the 5 key columns match


# ── Helpers de detección de tipo de proveedor ────────────────────────────────
_PJ_SUFFIXES = (
    "SAS", "S.A.S", "LTDA", "S.A.", "SA ", "CORP", "INC", "SOCIEDAD",
    "EMPRESA", "CONSULTORÍA", "CONSULTORIA", "COMPAÑÍA", "COMPANIA",
    "GROUP", "SERVICIOS", "SOLUTIONS", "SOLUCIONES", "ASOCIADOS",
    "ASOCIADAS", "CIA ", "CÍA ", "LIMITADA", "INMOBILIARIA", "AGENCIA",
)
_PN_PATTERN = re.compile(
    r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b'
)
# Detecta "CC 1020345678", "cédula: 1020345678", "NIT 900.888.777-1", etc.
_ID_PATTERN = re.compile(
    r'\b(?:cc|cédula|cedula|nit|c\.c\.)\s*[:\#]?\s*([\d.]{6,12}(?:-\d)?)',
    re.IGNORECASE,
)


def _detectar_tipo_proveedor(msg: str) -> str:
    """Detecta si el proveedor en el mensaje es PN (persona natural) o PJ (empresa).

    Returns: 'PN', 'PJ', o 'UNCLEAR'.
    """
    upper = msg.upper()
    if any(suf.upper() in upper for suf in _PJ_SUFFIXES):
        return "PJ"
    if _PN_PATTERN.search(msg):
        return "PN"
    return "UNCLEAR"


def _detectar_identificacion(msg: str) -> str | None:
    """Detecta si hay un número de CC o NIT explícito en el mensaje.

    Returns: número como string, o None si no hay.
    """
    m = _ID_PATTERN.search(msg)
    return m.group(1) if m else None

AGENT_SYSTEM_PROMPT = """Eres el Agente Contable IA de RODDOS — ejecutas acciones reales en Alegra desde el chat.

CONTEXTO:
{context}
{accounts_context}
{patterns_context}

COMPORTAMIENTO:
1. Ejecuta desde chat (sin formularios)
2. Sugiere cuentas de RODDOS antes de actuar
3. Calcula IVA, retenciones, totales automáticamente
4. Presenta resumen antes de ejecutar
5. Incluye <action> con payload listo

BUILD 23 - F2 RETENCIONES (CRÍTICAS):
- Arrendamiento: ReteFuente 3.5% SIEMPRE
- Honorarios PN: ReteFuente 10% SIEMPRE
- Honorarios PJ: ReteFuente 11% SIEMPRE
- Servicios: ReteFuente 4% (si >= 199K)
- Compras: ReteFuente 2.5% (si >= 1.3M)
- TODOS: ReteICA 0.414%

EXCEPCIONES CRÍTICAS (ROG-1):
- Auteco (NIT 860024781): NUNCA ReteFuente (autoretenedor)
- Andrés (CC 80075452) / Iván (CC 80086601): CXC Socios (ID 5491), nunca gasto
- Estructura: Débito=Gasto, Crédito=ReteFuente+ReteICA+Banco. Balancear siempre.

BUILD 23 - F6 VENTA MOTOS:
- VIN (chasis) obligatorio
- Motor obligatorio
- Descripción: "[Modelo] [Color] - VIN: [chasis] / Motor: [motor]"
- Inventario: Disponible->Vendida; Loanbook: pendiente_entrega

BUILD 23 - F7/F8/F9 CRITICAL POST+VERIFY:
1. POST a Alegra
2. request_with_verify(): GET confirmación HTTP 200
3. SOLO si HTTP 200 -> modificar MongoDB (loanbook, cartera_pagos, etc)
4. SI Alegra falla: NO modificar MongoDB. Retornar error.

REGLA CONSISTENCIA: POST success solo si Alegra responde HTTP 200.
"""

# Keywords that indicate the user wants to register or ask about accounts
REGISTER_KEYWORDS = [
    "causar", "registrar", "crear", "factura", "asiento", "cuenta",
    "débito", "crédito", "débito", "credito", "pagar", "cobrar",
    "proveedor", "gasto", "ingreso", "nomina", "nómina", "arrendamiento",
    "honorario", "servicio", "compra", "venta", "retención", "iva",
    "que cuenta", "qué cuenta", "cuál cuenta", "cual cuenta",
]


# ─── Similitud de patrones aprendidos ────────────────────────────────────────

async def find_similar_pattern(db, concepto: str, threshold: float = 0.80) -> dict | None:
    """Busca en agent_memory el patrón con mayor similitud Jaccard al concepto dado.
    Retorna el patrón si similitud >= threshold, sino None.
    """
    try:
        patterns = await db.agent_memory.find(
            {"tipo": {"$in": ["crear_causacion", "crear_factura_venta", "registrar_factura_compra"]}},
            {"_id": 0},
        ).sort("frecuencia_count", -1).to_list(50)

        if not patterns:
            return None

        concepto_words = set(concepto.lower().split())
        if not concepto_words:
            return None

        best_match = None
        best_sim   = 0.0

        for p in patterns:
            desc_words = set(p.get("descripcion", "").lower().split())
            if not desc_words:
                continue
            intersection = len(concepto_words & desc_words)
            union        = len(concepto_words | desc_words)
            sim          = intersection / union if union > 0 else 0.0
            if sim > best_sim:
                best_sim   = sim
                best_match = p

        if best_sim >= threshold and best_match:
            best_match = dict(best_match)
            best_match["_similitud"] = round(best_sim, 3)
            return best_match
        return None
    except Exception:
        return None


# ─── Guardar patrón confirmado ────────────────────────────────────────────────

async def save_action_pattern(db, user: dict, action_type: str, payload: dict) -> None:
    """Guarda o actualiza el patrón de acción en agent_memory (agent_memory.save_pattern)."""
    if action_type not in ("crear_causacion", "crear_factura_venta", "registrar_factura_compra"):
        return

    description = (
        payload.get("description")
        or payload.get("observations")
        or f"Acción {action_type}"
    )
    amount = 0.0
    if isinstance(payload.get("items"), list) and payload["items"]:
        amount = sum(float(i.get("price") or i.get("debit") or 0) for i in payload["items"])
    elif payload.get("total"):
        amount = float(payload["total"])

    cuentas_usadas: list[dict] = []
    if action_type == "crear_causacion":
        for entry in (payload.get("entries") or []):
            acc_id = str(entry.get("id", ""))
            if float(entry.get("debit", 0) or 0) > 0:
                cuentas_usadas.append({"id": acc_id, "rol": "debito",  "name": ""})
            elif float(entry.get("credit", 0) or 0) > 0:
                cuentas_usadas.append({"id": acc_id, "rol": "credito", "name": ""})

    await db.agent_memory.update_one(
        {"user_id": user.get("id"), "tipo": action_type, "descripcion": description},
        {"$set": {
            "id":               str(uuid.uuid4()),
            "user_id":          user.get("id"),
            "user_email":       user.get("email"),
            "tipo":             action_type,
            "descripcion":      description,
            "payload_alegra":   payload,
            "monto":            amount,
            "cuentas_usadas":   cuentas_usadas,
            "ultima_ejecucion": datetime.now(timezone.utc).isoformat(),
            "frecuencia":       "mensual",
        }, "$inc": {"frecuencia_count": 1}},
        upsert=True,
    )


# ── MODULE 4: Memoria Conversacional Persistente ─────────────────────────────
# Pendientes conversacionales por usuario (TTL 72 horas)

PENDING_TOPICS_TTL_HOURS = 72


async def save_pending_topic(db, user_id: str, topic_key: str, descripcion: str,
                              datos_contexto: dict | None = None) -> None:
    """Guarda o actualiza un tema pendiente para el usuario (TTL 72h).

    topic_key: identificador corto único ej: 'registrar_gastos_enero', 'completar_cxc_socios'
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=PENDING_TOPICS_TTL_HOURS)
    await db.agent_pending_topics.update_one(
        {"user_id": user_id, "topic_key": topic_key, "estado": "pendiente"},
        {"$set": {
            "user_id": user_id,
            "topic_key": topic_key,
            "descripcion": descripcion,
            "datos_contexto": datos_contexto or {},
            "estado": "pendiente",
            "updated_at": now.isoformat(),
            "expires_at": expires_at,  # BSON Date — required for TTL index
        }, "$setOnInsert": {
            "id": str(uuid.uuid4()),
            "created_at": now.isoformat(),
        }},
        upsert=True,
    )


async def get_pending_topics(db, user_id: str) -> list[dict]:
    """Obtiene los temas pendientes activos del usuario (no expirados)."""
    now = datetime.now(timezone.utc)
    topics = await db.agent_pending_topics.find(
        {"user_id": user_id, "estado": "pendiente", "expires_at": {"$gt": now}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    return topics


async def complete_pending_topic(db, user_id: str, topic_key: str) -> None:
    """Marca un tema pendiente como completado."""
    await db.agent_pending_topics.update_many(
        {"user_id": user_id, "topic_key": topic_key},
        {"$set": {"estado": "completado", "completado_en": datetime.now(timezone.utc).isoformat()}}
    )


def _format_pending_topics_for_prompt(topics: list[dict]) -> str:
    """Formatea los temas pendientes para inyectar en el contexto del agente."""
    if not topics:
        return ""
    lines = [
        "\n═══════════════════════════════════════════════════",
        "TEMAS PENDIENTES DEL USUARIO (de sesiones anteriores — TTL 72h):",
        "═══════════════════════════════════════════════════",
    ]
    for t in topics:
        created = t.get("created_at", "")[:10]
        expires = t.get("expires_at", "")[:10]
        lines.append(
            f"• [{t.get('topic_key','')}] {t.get('descripcion','')} "
            f"(iniciado: {created}, expira: {expires})"
        )
        ctx = t.get("datos_contexto", {})
        if ctx:
            for k, v in list(ctx.items())[:3]:
                lines.append(f"  ↳ {k}: {v}")
    lines.append(
        "\nINSTRUCCIÓN: Si el usuario no menciona ninguno de estos temas, "
        "retómalos proactivamente al inicio de la respuesta: "
        "'Antes de continuar, quedamos pendientes de: [tema]. ¿Lo retomamos?'"
    )
    return "\n".join(lines)




async def gather_context(user_message: str, alegra_service, db) -> dict:
    """Gather relevant Alegra data to provide context to Claude."""
    context = {
        "fecha_actual": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "contactos": [],
        "cuentas_bancarias": [],
        "iva_status": None,
    }

    # ── MEJORA 3: Actividad del día desde roddos_events ──────────────────────
    try:
        from datetime import timezone as _tz
        hoy_inicio = datetime.now(_tz.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        eventos_hoy = await db.roddos_events.find(
            {"timestamp": {"$gte": hoy_inicio}},
            {"_id": 0, "event_type": 1, "timestamp": 1, "data": 1},
        ).sort("timestamp", -1).limit(10).to_list(10)

        if eventos_hoy:
            lineas = []
            for ev in reversed(eventos_hoy):
                ts = ev.get("timestamp", "")[:16].replace("T", " ")
                tipo = ev.get("event_type", "")
                data = ev.get("data") or {}
                detalle = ""
                if tipo == "factura.venta.creada":
                    detalle = f"FV {_safe_str(data.get('factura_numero'))} — {_safe_str(data.get('cliente_nombre'))} ${_safe_num(data.get('total')):,.0f}"
                elif tipo in ("pago.cuota.registrado", "cuota_pagada"):
                    detalle = f"{_safe_str(data.get('cliente_nombre'))} cuota ${_safe_num(data.get('monto')):,.0f}"
                elif tipo == "asiento.contable.creado":
                    detalle = data.get("concepto", data.get("observations", ""))[:40]
                elif tipo == "factura.compra.creada":
                    detalle = f"{_safe_str(data.get('proveedor'))} ${_safe_num(data.get('total')):,.0f}"
                elif tipo == "loanbook.activado":
                    detalle = f"Entrega moto — {data.get('cliente','')}"
                elif tipo == "inventario.moto.baja":
                    detalle = f"Venta {data.get('moto_desc','')} chasis {data.get('moto_chasis','')}"
                else:
                    detalle = str(data)[:40]
                lineas.append(f"  - {ts} {tipo}: {detalle}")
            context["actividad_hoy"] = "\n".join(lineas)
    except Exception:
        pass
    try:
        contacts = await alegra_service.request("contacts")
        context["contactos"] = [
            {"id": c["id"], "name": c["name"], "nit": c.get("identification", ""), "tipo": c.get("type", "")}
            for c in (contacts if isinstance(contacts, list) else [])
        ]
    except Exception:
        pass

    try:
        banks = await alegra_service.request("bank-accounts")
        context["cuentas_bancarias"] = [
            {"id": b["id"], "name": b["name"], "balance": b.get("balance", 0)}
            for b in (banks if isinstance(banks, list) else [])
        ]
    except Exception:
        pass

    # Pull IVA status for cuatrimestral context
    msg_lower = user_message.lower()

    # ── Inject chart of accounts for causacion / journal entry scenarios ─────
    causacion_kws = ["causaci", "gasto", "comprobante", "journal", "asiento", "registro contable",
                     "contabiliz", "débito", "debito", "crédito", "credito", "cuenta"]
    if any(kw in msg_lower for kw in causacion_kws):
        try:
            accts = await alegra_service.get_accounts_from_categories()
            leaf_accts = alegra_service.get_leaf_accounts(accts)
            context["cuentas_contables"] = [
                {"id": a["id"], "code": a.get("code", ""), "name": a["name"]}
                for a in leaf_accts
                if a.get("status", "active") == "active"
            ]
        except Exception:
            pass
        # Always include RODDOS plan de cuentas (static, no API needed)
        from routers.gastos import PLAN_CUENTAS_RODDOS
        context["plan_cuentas_roddos"] = [
            {"categoria": e["categoria"], "subcategoria": e["subcategoria"],
             "alegra_id": e["alegra_id"], "cuenta_codigo": e["cuenta_codigo"],
             "cuenta_nombre": e["cuenta_nombre"]}
            for e in PLAN_CUENTAS_RODDOS
        ]
        # Include plan_ingresos + CXC socios context
        from routers.ingresos import PLAN_INGRESOS_RODDOS
        context["plan_ingresos_roddos"] = PLAN_INGRESOS_RODDOS
        context["socios_cxc"] = [
            {"nombre": "Andres Sanjuan",  "cedula": "80075452", "cxc_alegra_id": 5329},
            {"nombre": "Ivan Echeverri",  "cedula": "80086601", "cxc_alegra_id": 5329},
        ]

    # ── Inject catalog items for compra/bill scenarios ──────────────────────
    compra_kws = ["compra", "factura compra", "factura de compra", "bill", "proveedor",
                  "moto", "inventario", "comprar", "adquisición", "adquisicion"]
    if any(kw in msg_lower for kw in compra_kws):
        try:
            catalog_items = await alegra_service.request("items")
            if isinstance(catalog_items, list):
                context["items_catalogo"] = [
                    {"id": it["id"], "name": it["name"], "type": it.get("type", ""),
                     "status": it.get("status", "active")}
                    for it in catalog_items
                    if it.get("status") == "active" and it.get("type") == "product"
                ]
        except Exception:
            pass

    # ── Inject available inventory context for moto sale/query scenarios ──────
    sale_kws = ["vende", "venta", "moto", "cb", "fz", "tvs", "kawas", "akt", "chasis",
                "vin", "plan", "p39", "p52", "p78", "financ", "cuota", "entrega", "entregó",
                "inventario", "disponible", "stock", "cuántas motos", "cuantas motos"]
    if any(kw in msg_lower for kw in sale_kws):
        # Ruta 1: MongoDB (fuente principal)
        try:
            motos = await db.inventario_motos.find(
                {"estado": "Disponible"},
                {"_id": 0, "id": 1, "marca": 1, "version": 1, "color": 1, "chasis": 1,
                 "motor": 1, "estado": 1, "total": 1},
            ).sort("created_at", -1).to_list(30)
            if motos:
                context["inventario_disponible"] = motos
                context["inventario_fuente"] = "mongodb"
        except Exception:
            motos = []
        # Ruta 2: Fallback Alegra /items si MongoDB falla o está vacío
        if not motos:
            try:
                alegra_items = await alegra_service.request("items")
                if isinstance(alegra_items, list):
                    motos_alegra = [
                        {"id": it["id"], "marca": "Alegra", "version": it["name"],
                         "color": "", "chasis": "", "motor": "", "estado": "Disponible",
                         "total": it.get("price", [{}])[0].get("price", 0) if it.get("price") else 0}
                        for it in alegra_items
                        if it.get("status") == "active" and it.get("type") == "product"
                    ]
                    if motos_alegra:
                        context["inventario_disponible"] = motos_alegra
                        context["inventario_fuente"] = "alegra"
            except Exception:
                pass
        # Ruta 3: Inferencia desde loanbooks si ambas fuentes fallan
        if not context.get("inventario_disponible"):
            try:
                total_activos = await db.loanbook.count_documents({"estado": "activo"})
                total_motos_inv = await db.inventario_motos.count_documents({})
                context["inventario_inferido"] = {
                    "loanbooks_activos": total_activos,
                    "total_en_inventario_db": total_motos_inv,
                    "nota": "Datos directos no disponibles — usar módulo Motos para detalle exacto"
                }
            except Exception:
                pass

    # ── Inject active loanbook context for payment/delivery scenarios ───────
    pay_kws = ["pago", "cuota", "cobr", "cancelar", "pagó", "cancel", "loanbook", "lb-", "entrega"]
    if any(kw in msg_lower for kw in pay_kws):
        try:
            loans = await db.loanbook.find(
                {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}},
                {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1,
                 "factura_alegra_id": 1, "plan": 1, "num_cuotas": 1,
                 "saldo_pendiente": 1, "estado": 1, "fecha_entrega": 1,
                 "cuotas": 1},
            ).sort("updated_at", -1).to_list(15)
            context["loanbook_activos"] = [
                {
                    "id": l["id"],
                    "codigo": l["codigo"],
                    "cliente": l["cliente_nombre"],
                    "factura_alegra_id": l.get("factura_alegra_id", ""),
                    "plan": l.get("plan", ""),
                    "saldo_pendiente": l.get("saldo_pendiente", 0),
                    "estado": l.get("estado", ""),
                    "fecha_entrega": l.get("fecha_entrega"),
                    "proximas_cuotas": [
                        c for c in l.get("cuotas", [])
                        if c.get("estado") in ("pendiente", "vencida", "sin_fecha")
                    ][:4],
                }
                for l in loans
            ]
        except Exception:
            pass

    if any(w in msg_lower for w in ["iva", "impuesto", "dian", "declaraci", "periodo", "cuatrimest", "cuánto", "cuanto", "pagar"]):
        try:
            from server import db as main_db
        except ImportError:
            main_db = db
        try:
            from datetime import date as _date
            now = datetime.now(timezone.utc)
            cfg = await db.iva_config.find_one({}, {"_id": 0})
            if not cfg:
                cfg = {"tipo_periodo": "cuatrimestral", "periodos": [
                    {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
                    {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
                    {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
                ], "saldo_favor_dian": 0}

            mes = now.month
            ano = now.year
            periodos = cfg.get("periodos", [])
            saldo_favor = float(cfg.get("saldo_favor_dian", 0))
            periodo = next((p for p in periodos if p["inicio_mes"] <= mes <= p["fin_mes"]), periodos[-1] if periodos else None)
            if periodo:
                ds = f"{ano}-{str(periodo['inicio_mes']).zfill(2)}-01"
                de = f"{ano}-{str(periodo['fin_mes']).zfill(2)}-28"
                inv = await alegra_service.request("invoices", params={"date_start": ds, "date_end": de})
                bills = await alegra_service.request("bills", params={"date_start": ds, "date_end": de})
                inv = inv if isinstance(inv, list) else []
                bills = bills if isinstance(bills, list) else []
                tv = sum(float(i.get("total") or 0) for i in inv)
                tc = sum(float(b.get("total") or 0) for b in bills)
                iva_cobrado = round(tv / 1.19 * 0.19)
                iva_desc = round(tc / 1.19 * 0.19)
                iva_bruto = max(0, iva_cobrado - iva_desc)
                iva_pagar = max(0, iva_bruto - saldo_favor)
                meses_trans = max(1, mes - periodo["inicio_mes"] + 1)
                meses_tot = periodo["fin_mes"] - periodo["inicio_mes"] + 1
                mes_lim = periodo["fin_mes"] + periodo.get("mes_limite_offset", 1)
                ano_lim = ano + (1 if mes_lim > 12 else 0)
                mes_lim = mes_lim if mes_lim <= 12 else mes_lim - 12
                fecha_lim = f"{ano_lim}-{str(mes_lim).zfill(2)}-{periodo.get('dia_limite', 30)}"
                dias_rest = (_date.fromisoformat(fecha_lim) - _date.today()).days
                context["iva_status"] = {
                    "periodo": periodo["nombre"],
                    "tipo": cfg.get("tipo_periodo", "cuatrimestral"),
                    "fecha_limite": fecha_lim,
                    "dias_restantes": dias_rest,
                    "meses_transcurridos": meses_trans,
                    "meses_total": meses_tot,
                    "iva_cobrado_acumulado": iva_cobrado,
                    "iva_descontable_acumulado": iva_desc,
                    "iva_bruto_periodo": iva_bruto,
                    "saldo_favor_dian": saldo_favor,
                    "iva_pagar_estimado": iva_pagar,
                    "facturas_venta": len(inv),
                    "facturas_compra": len(bills),
                }
        except Exception:
            pass

    return context


async def gather_accounts_context(user_message: str, alegra_service, db) -> tuple:
    """Build accounts context from roddos_cuentas (fast) + Alegra patterns.
    Returns (accounts_context_str, patterns_context_str, honorarios_instruccion)."""
    msg_lower = user_message.lower()
    needs_accounts = any(w in msg_lower for w in REGISTER_KEYWORDS)

    accounts_str = "No se requiere plan de cuentas para esta consulta."
    patterns_str = "Sin patrones aprendidos aún."
    honorarios_instruccion = "(Sin instrucción especial para esta consulta.)"

    if not needs_accounts:
        return accounts_str, patterns_str, honorarios_instruccion

    # ── 1. Transaction-type detection → targeted account selection ───────────
    # Detect proveedor type first (needed for honorarios rule)
    tipo_proveedor = _detectar_tipo_proveedor(user_message)

    # Honorarios retención depends on PN vs PJ
    if tipo_proveedor == "PN":
        honorarios_ret = ["23651501"]          # 10% PN
    elif tipo_proveedor == "PJ":
        honorarios_ret = ["23651502"]          # 11% PJ
    else:
        honorarios_ret = ["23651501", "23651502"]  # ambas — agente preguntará

    TRANSACTION_RULES = [
        (["arriendo", "arrendamiento", "alquiler", "calle 127"],
         ["512010", "23653001"]),
        (["honorario", "asesor", "jurídic", "contad", "profesional"],
         ["511025", "511030"] + honorarios_ret),
        (["venta moto", "vender moto", "factura moto", "venta de moto"],
         ["41350501", "61350501", "14350101", "13050501"]),
        (["cuota", "loanbook", "crédito directo", "abono crédito", "pago cuota"],
         ["13050502", "41502001"]),
        (["nómina", "salario", "sueldo", "empleado"],
         ["510506"]),
        (["software", "emergent", "alegra", "mercately", "sistema", "tecnología", "licencia"],
         ["513520"]),
        (["teléfono", "internet", "celular"],
         ["513535"]),
        (["4x1000", "gmf", "gravamen", "cuatro por mil"],
         ["531520"]),
        (["papelería", "útiles", "tóner", "papel"],
         ["519530"]),
        (["iva generado", "iva cobrado", "iva venta"],
         ["24080601"]),
        (["iva descontable", "iva compra", "iva proveedor"],
         ["24081001"]),
        (["retención", "retefuente", "retener"],
         ["23651501", "23651502", "23652501", "23653001", "23654001"]),
        (["matrícula", "matricula"],
         ["41459507", "61459507"]),
        (["repuesto", "accesorio"],
         ["41350601", "61350601", "14350102"]),
    ]

    # Collect codes relevant to detected transaction types
    relevant_codes: set[str] = set()
    for keywords, codes in TRANSACTION_RULES:
        if any(kw in msg_lower for kw in keywords):
            relevant_codes.update(codes)

    # Always include main banks for any payment/receipt
    if any(w in msg_lower for w in ["pagar","pago","recibir","cobrar","recaudo","banco","consign"]):
        relevant_codes.update(["11100501","11100502","11100505","11200501","11200502","11050501"])

    # ── 2. Build accounts string from roddos_cuentas (MongoDB, fast) ─────────
    try:
        if relevant_codes:
            accounts_cursor = db.roddos_cuentas.find(
                {"codigo": {"$in": list(relevant_codes)}}, {"_id": 0}
            )
        else:
            # Fallback: all uso_frecuente=True accounts
            accounts_cursor = db.roddos_cuentas.find(
                {"uso_frecuente": True}, {"_id": 0}
            )
        roddos_accts = await accounts_cursor.to_list(60)

        if roddos_accts:
            lines = [
                f"  [{a['alegra_id']}] {a['codigo']} — {a['nombre']}"
                for a in sorted(roddos_accts, key=lambda x: x["codigo"])
            ]
            cuentas_str = (
                "CUENTAS REALES DE RODDOS (usar estas — ya configuradas en Alegra):\n"
                + "\n".join(lines)
            )

            # ── Honorarios: detect case and build honorarios_instruccion ──────
            is_honorario_msg = any(kw in msg_lower for kw in
                                   ["honorario", "asesor", "profesional", "contad"])
            if is_honorario_msg:
                id_detected = _detectar_identificacion(user_message)
                if tipo_proveedor == "PN":
                    if id_detected:
                        honorarios_instruccion = (
                            f"INSTRUCCION OBLIGATORIA (Caso 1 — Tipo+ID conocidos):\n"
                            f"El sistema detectó: PERSONA NATURAL con CC={id_detected}.\n"
                            f"ACCION INMEDIATA: Genera el bloque <action> crear_contacto+crear_causacion AHORA.\n"
                            f"Retención 10%: cuenta [5381] 23651501. NO hagas ninguna pregunta."
                        )
                    else:
                        honorarios_instruccion = (
                            "INSTRUCCION OBLIGATORIA (Caso 2 — Tipo conocido, CC faltante):\n"
                            "El sistema detectó: PERSONA NATURAL (por el nombre en el mensaje).\n"
                            "ACCION INMEDIATA: Hacer UNA SOLA PREGUNTA, exactamente: "
                            "'¿Cuál es el número de cédula de [nombre del proveedor]?'\n"
                            "PROHIBIDO: NO preguntar si es PN o PJ — ya está determinado.\n"
                            "PROHIBIDO: NO hacer ninguna otra pregunta."
                        )
                elif tipo_proveedor == "PJ":
                    if id_detected:
                        honorarios_instruccion = (
                            f"INSTRUCCION OBLIGATORIA (Caso 1 — Tipo+ID conocidos):\n"
                            f"El sistema detectó: PERSONA JURÍDICA con NIT={id_detected}.\n"
                            f"ACCION INMEDIATA: Genera el bloque <action> crear_contacto+crear_causacion AHORA.\n"
                            f"Retención 11%: cuenta [5382] 23651502. NO hagas ninguna pregunta."
                        )
                    else:
                        honorarios_instruccion = (
                            "INSTRUCCION OBLIGATORIA (Caso 2 — Tipo conocido, NIT faltante):\n"
                            "El sistema detectó: PERSONA JURÍDICA (por sufijo en el nombre).\n"
                            "ACCION INMEDIATA: Hacer UNA SOLA PREGUNTA, exactamente: "
                            "'¿Cuál es el NIT de [nombre del proveedor]?'\n"
                            "PROHIBIDO: NO preguntar si es PN o PJ — ya está determinado.\n"
                            "PROHIBIDO: NO hacer ninguna otra pregunta."
                        )
                else:
                    honorarios_instruccion = (
                        "INSTRUCCION OBLIGATORIA (Caso 3 — Tipo no detectado):\n"
                        "El sistema NO pudo determinar si el proveedor es PN o PJ.\n"
                        "ACCION INMEDIATA: Hacer UNA SOLA PREGUNTA: "
                        "'¿[nombre] es persona natural (PN) o empresa (persona jurídica)?'\n"
                        "NO pedir el NIT/CC todavía — primero confirmar el tipo."
                    )
                # Add compact provider-type note to accounts_str
                pn_note = {
                    "PN": "\n[Sistema: Proveedor detectado como PERSONA NATURAL — retención 10%]",
                    "PJ": "\n[Sistema: Proveedor detectado como PERSONA JURÍDICA — retención 11%]",
                    "UNCLEAR": "\n[Sistema: Tipo de proveedor no determinado]",
                }
                accounts_str = cuentas_str + pn_note.get(tipo_proveedor, "")
            else:
                accounts_str = cuentas_str
        else:
            # Final fallback: full Alegra categories
            accounts_tree = await alegra_service.get_accounts_from_categories()
            leaves = alegra_service.get_leaf_accounts(accounts_tree)
            by_type: dict = {}
            for acc in leaves:
                t = acc.get("type", "asset")
                by_type.setdefault(t, []).append(f"  [{acc['id']}] {acc['name']}")
            TYPE_LABELS = {"asset":"ACTIVOS","liability":"PASIVOS","equity":"PATRIMONIO",
                           "income":"INGRESOS","expense":"GASTOS","cost":"COSTOS"}
            accounts_str = "\n".join(
                f"{TYPE_LABELS.get(t,t.upper())}:\n" + "\n".join(accs[:20])
                for t, accs in by_type.items()
            ) or "Sin cuentas disponibles."
    except Exception as e:
        accounts_str = "Error cargando plan de cuentas."
        print(f"[gather_accounts_context] {e}")

    # ── 3. Load RODDOS learned patterns ──────────────────────────────────────
    try:
        similar = await find_similar_pattern(db, user_message)
        patterns = await db.agent_memory.find(
            {"tipo": {"$in": ["crear_causacion", "crear_factura_venta", "registrar_factura_compra"]}},
            {"_id": 0}
        ).sort("frecuencia_count", -1).limit(8).to_list(8)

        if patterns:
            plines = []
            TIPO_LABELS = {
                "crear_causacion":          "Causación",
                "crear_factura_venta":      "Factura venta",
                "registrar_factura_compra": "Factura compra",
            }
            if similar:
                sim_pct   = round(similar.get("_similitud", 0) * 100)
                freq_sim  = similar.get("frecuencia_count", 1)
                tipo_sim  = TIPO_LABELS.get(similar["tipo"], similar["tipo"])
                cuentas_sim_str = " | ".join([
                    f"{c.get('rol','?')}: [{c.get('id','')}] {c.get('name','')}"
                    for c in similar.get("cuentas_usadas", [])[:2]
                ])
                plines.append(
                    f"[PATRÓN SIMILAR DETECTADO — {sim_pct}% similitud]\n"
                    f"• {tipo_sim} — \"{similar['descripcion']}\" ({freq_sim}x) {cuentas_sim_str}\n"
                    f"→ Puedes sugerir este patrón directamente al usuario\n"
                )
            for p in patterns:
                # Evitar duplicar el patrón ya incluido como similar
                if similar and p.get("descripcion") == similar.get("descripcion"):
                    continue
                freq = p.get("frecuencia_count", 1)
                cuentas = p.get("cuentas_usadas", [])
                cuentas_str = " | ".join([
                    f"{c.get('rol','?')}: [{c.get('id','')}] {c.get('name','')}"
                    for c in cuentas[:2]
                ])
                plines.append(
                    f"• {TIPO_LABELS.get(p['tipo'], p['tipo'])} — \"{p['descripcion']}\" "
                    f"({freq}x) {cuentas_str}"
                )
            patterns_str = "\n".join(plines)
            if any(p.get("frecuencia_count", 1) >= 5 for p in patterns):
                patterns_str += "\n\n[MODO AUTOMÁTICO ACTIVO: patrones con 5+ usos se ejecutan sin preguntar cuentas]"
        else:
            patterns_str = "Sin patrones aprendidos aún. Después de registrar 3+ transacciones similares, comenzaré a sugerirlas automáticamente."
    except Exception:
        patterns_str = "Sin patrones disponibles."

    # ── 4. BUILD 9: Patrón contable aprendido por NIT ────────────────────────
    try:
        nit_detected = _detectar_identificacion(user_message)
        if nit_detected:
            patron_contable = await db.learning_patterns.find_one(
                {"tipo": "patron_contable",
                 "entidad_id": str(nit_detected),
                 "activo": True,
                 "confianza": {"$gte": 0.7}},
                {"_id": 0},
            )
            if patron_contable:
                d = patron_contable.get("datos", {})
                nota = (
                    f"\n\n[BUILD 9 — PATRÓN APRENDIDO PARA NIT {nit_detected}]\n"
                    f"Cuenta débito: {d.get('cuenta_debito_id','?')} {d.get('cuenta_debito_nombre','')}\n"
                    f"Cuenta crédito: {d.get('cuenta_credito_id','?')} {d.get('cuenta_credito_nombre','')}\n"
                    f"Retención: {d.get('retencion_pct','?')}%\n"
                    f"Confianza: {round(_safe_num(patron_contable.get('confianza'))*100,0):.0f}% "
                    f"({_safe_num(patron_contable.get('muestra_n'),0):.0f} registros)\n"
                    f"→ Usar este patrón si el tipo de transacción coincide con transacciones anteriores."
                )
                patterns_str += nota
    except Exception:
        pass

    # ── 5. Autoretenedores — inyectar reglas para facturas de compra PJ ──────
    _compra_kws = ["compra", "factura compra", "factura de compra", "bill", "proveedor",
                   "auteco", "kawasaki", "comprar", "adquisicion", "adquisición", "proveedor externo"]
    _is_compra_scenario = any(kw in msg_lower for kw in _compra_kws)
    _is_pn = tipo_proveedor == "PN"  # personas naturales nunca son autoretenedoras
    if _is_compra_scenario and not _is_pn:
        try:
            _autoretenedores = await db.proveedores_config.find(
                {"es_autoretenedor": True}, {"_id": 0, "nombre": 1, "nit": 1}
            ).to_list(100)
            if _autoretenedores:
                _lista = "\n".join(
                    f"  • {a['nombre']}" + (f" (NIT: {a['nit']})" if a.get("nit") else "")
                    for a in _autoretenedores
                )
            else:
                _lista = "  (ninguno registrado aún)"
            accounts_str += (
                "\n\n══════════ REGLAS AUTORETENEDORES ══════════\n"
                f"Proveedores AUTORETENEDORES (NO aplicar ReteFuente):\n{_lista}\n\n"
                "REGLA 1 — Si el proveedor está en la lista: OMITIR ReteFuente completamente.\n"
                "REGLA 2 — Si el proveedor PJ NO está en la lista: registra CON ReteFuente estándar. "
                "Al finalizar incluye EXACTAMENTE esta nota:\n"
                '  "ℹ️ Apliqué ReteFuente [X]% a **[Proveedor]**. ¿Es autoretenedora? '
                "Responde 'Sí, [Proveedor] es autoretenedora' para revertir la retención.\"\n"
                "REGLA 3 — Persona Natural: SIEMPRE ReteFuente. NUNCA preguntar si es autoretenedora.\n"
                "════════════════════════════════════════════"
            )
        except Exception:
            pass

    return accounts_str, patterns_str, honorarios_instruccion


DOCUMENT_ANALYSIS_SYSTEM_PROMPT = """Eres el Agente Contable IA de RODDOS Colombia, experto en contabilidad NIIF Colombia.
Has recibido un comprobante contable (factura, recibo, comprobante de pago, extracto u otro documento).

CUENTAS REALES DE RODDOS EN ALEGRA (usar estos IDs en entries):
{accounts_context}

LOANBOOKS ACTIVOS EN RODDOS:
{loanbook_context}

FECHA ACTUAL: {fecha_actual}

TU TAREA:
1. Lee y analiza cuidadosamente el documento
2. Extrae TODOS los datos relevantes con máxima precisión
3. Determina el tipo de transacción contable
4. Detecta si es un pago de cuota de Loanbook RODDOS (busca: "RODDOS", moto, cuota, plan de pagos, o si el monto coincide con algún Loanbook activo)
5. Sugiere la cuenta contable correcta del plan de cuentas disponible
6. Propone la acción a ejecutar en Alegra

REGLAS CONTABLES:
- Facturas de proveedores con IVA → accion_contable = registrar_factura_compra
- Recibos, comprobantes de servicio sin facturas formales → accion_contable = crear_causacion
- Comprobantes de pago/transferencias → accion_contable = registrar_pago
- ReteFuente: calcula según tipo (servicios 4%, honorarios 10%, arrendamiento 3.5%, compras 2.5%)
- Si el documento es ilegible o incompleto → ilegible=true, lista campos en campos_faltantes

DESPUÉS de tu análisis en texto, incluye OBLIGATORIAMENTE este bloque:
<document_proposal>
{
  "es_pago_loanbook": false,
  "loanbook_codigo": null,
  "tipo_documento": "factura_compra",
  "proveedor_cliente": "",
  "nit": "",
  "fecha": "YYYY-MM-DD",
  "numero_documento": "",
  "concepto": "",
  "subtotal": 0,
  "iva_porcentaje": 0,
  "iva_valor": 0,
  "retefuente_valor": 0,
  "retefuente_tipo": "ninguna",
  "total": 0,
  "accion_contable": "crear_causacion",
  "cuenta_gasto_id": null,
  "cuenta_gasto_nombre": "",
  "ilegible": false,
  "campos_faltantes": []
}
</document_proposal>

Valores válidos tipo_documento: factura_compra | factura_venta | recibo_pago | comprobante_egreso | extracto_bancario | otro
Valores válidos accion_contable: registrar_factura_compra | crear_causacion | registrar_pago | ninguna
Valores retefuente_tipo: ninguna | servicios_4 | servicios_6 | honorarios_10 | arrendamiento_3.5 | compras_2.5

IMPORTANTE: cuenta_gasto_id debe ser un ID NUMÉRICO real del plan de cuentas listado arriba.
Responde en español colombiano. Sé muy preciso con montos y cuentas."""


async def process_document_chat(
    session_id: str, user_message: str,
    file_content: str, file_name: str, file_type: str,
    db, user: dict
) -> dict:
    """Process a chat message that includes a document (image/PDF) for accounting analysis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    from alegra_service import AlegraService
    alegra_service = AlegraService(db)

    # Always load full accounts context for document analysis
    accounts_str, _, _hon = await gather_accounts_context("causar registrar factura proveedor compra", alegra_service, db)

    # ── Memoria de preferencias (Parte 5): proveedor recurrente ──────────────
    _prov_memory_ctx = ""
    try:
        # Try to detect provider name from filename or message
        _fname_upper = (file_name or "").upper()
        _msg_upper = (user_message or "").upper()
        _search_text = f"{_fname_upper} {_msg_upper}"

        # Look for known providers in filename/message
        _known_provs = await db.agent_memory.find(
            {"tipo": "registrar_factura_compra"},
            {"_id": 0, "descripcion": 1, "frecuencia_count": 1, "payload_alegra": 1}
        ).sort("frecuencia_count", -1).limit(10).to_list(10)

        _matched_prov = None
        for kp in _known_provs:
            desc = (kp.get("descripcion") or "").upper()
            # Check if any word from the description appears in filename/message
            words = [w for w in desc.split() if len(w) > 4]
            if any(w in _search_text for w in words):
                _matched_prov = kp
                break

        if _matched_prov:
            freq = _matched_prov.get("frecuencia_count", 1)
            _prov_memory_ctx = (
                f"\n\n[MEMORIA: PROVEEDOR RECURRENTE DETECTADO — {freq}x registrado]\n"
                f"Descripción patrón habitual: {_matched_prov.get('descripcion', '')}\n"
                "→ Usa este patrón si coincide con el documento actual. Indica al usuario si lo estás aplicando."
            )
        elif not _matched_prov:
            # For unknown provider, inject instruction to ask if unclassifiable
            _prov_memory_ctx = (
                "\n\n[MEMORIA: Primer documento de este proveedor detectado]\n"
                "Si el documento es ilegible o no puedes determinar el tipo → "
                "pregunta al usuario: '¿Este documento es factura de compra, recibo de servicio o comprobante de pago?'"
            )
    except Exception:
        pass

    # ── Autoretenedores context para análisis de documentos ──────────────────
    _autoret_doc_ctx = ""
    try:
        _autoretenedores_doc = await db.proveedores_config.find(
            {"es_autoretenedor": True}, {"_id": 0, "nombre": 1, "nit": 1}
        ).to_list(100)
        if _autoretenedores_doc:
            _lista_doc = "\n".join(
                f"  • {a['nombre']}" + (f" (NIT: {a['nit']})" if a.get("nit") else "")
                for a in _autoretenedores_doc
            )
            _autoret_doc_ctx = (
                "\n\nREGLAS AUTORETENEDORES (CRÍTICO para calcular retenciones):\n"
                f"Proveedores que NO aplican ReteFuente:\n{_lista_doc}\n"
                "REGLA: Si el proveedor del documento está en la lista → retefuente_valor=0 y retefuente_tipo='ninguna'.\n"
                "Si el proveedor PJ no está en la lista → aplica ReteFuente normal. "
                "Al finalizar incluye: 'ℹ️ Apliqué ReteFuente X% a **[Proveedor]**. ¿Es autoretenedora?'"
            )
    except Exception:
        pass

    # Get active loanbooks for payment detection
    loanbook_str = "Sin loanbooks activos."
    try:
        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}},
            {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "saldo_pendiente": 1, "plan": 1}
        ).to_list(15)
        if loans:
            loanbook_str = "\n".join([
                f"• [{_safe_str(l.get('codigo'))}] {_safe_str(l.get('cliente_nombre'))} — Plan: {_safe_str(l.get('plan'))} Saldo: ${_safe_num(l.get('saldo_pendiente')):,.0f}"
                for l in loans
            ])
    except Exception:
        pass

    fecha_actual = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = (
        DOCUMENT_ANALYSIS_SYSTEM_PROMPT
        .replace("{accounts_context}", accounts_str + _autoret_doc_ctx + _prov_memory_ctx)
        .replace("{loanbook_context}", loanbook_str)
        .replace("{fecha_actual}", fecha_actual)
    )

    # Save user message to DB
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": f"{user_message or 'Analiza este comprobante'}\n[Archivo adjunto: {file_name}]",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # Call Claude with file content (use separate session to avoid polluting main chat context)
    _doc_client = anthropic.AsyncAnthropic(api_key=api_key)
    text = user_message or "Analiza este comprobante contable y extrae todos los datos para su registro en Alegra."
    if file_type == "application/pdf":
        _file_block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": file_content}}
    else:
        _file_block = {"type": "image", "source": {"type": "base64", "media_type": file_type, "data": file_content}}
    _doc_resp = await _doc_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": [_file_block, {"type": "text", "text": text}]}],
    )
    response_text = _doc_resp.content[0].text

    # Parse <document_proposal> block
    document_proposal = None
    clean_response = response_text
    if "<document_proposal>" in response_text and "</document_proposal>" in response_text:
        try:
            start = response_text.index("<document_proposal>") + len("<document_proposal>")
            end = response_text.index("</document_proposal>")
            proposal_json = response_text[start:end].strip()
            document_proposal = json.loads(proposal_json)
            clean_response = (
                response_text[:response_text.index("<document_proposal>")].strip()
                + response_text[end + len("</document_proposal>"):].strip()
            ).strip()
        except Exception:
            pass

    # Also parse <action> block if present
    action = None
    if "<action>" in clean_response and "</action>" in clean_response:
        try:
            start = clean_response.index("<action>") + 8
            end = clean_response.index("</action>")
            action = json.loads(clean_response[start:end].strip())
            clean_response = (
                clean_response[:clean_response.index("<action>")].strip()
                + clean_response[end + 9:].strip()
            ).strip()
        except Exception:
            pass

    # Save assistant response
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    return {
        "message": clean_response,
        "document_proposal": document_proposal,
        "pending_action": action,
        "session_id": session_id,
    }


async def process_tabular_chat(
    session_id: str, user_message: str,
    file_content: str, file_name: str, file_type: str,
    db, user: dict
) -> dict:
    """Handle CSV/Excel attachments by converting to text and routing to the agent."""
    text_table, headers, rows = _tabular_to_text(file_content, file_name, file_type)
    n_rows = len(rows)
    is_gastos = _is_gastos_csv(headers)

    # Save user message
    display_msg = user_message or f"Adjunté el archivo: {file_name}"
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": f"{display_msg}\n[Archivo adjunto: {file_name} — {n_rows} filas]",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # ── Gastos CSV/Excel: return preview card ──────────────────────────────
    if is_gastos:
        gastos_preview_msg = (
            f"Detecté un archivo de **carga masiva de gastos** (`{file_name}`) "
            f"con **{n_rows} fila(s)**.\n\n"
            f"**Primeras filas:**\n```\n{text_table[:1200]}\n```\n\n"
            "Usa la tarjeta de **Carga Masiva** para subir este archivo, validar las "
            "retenciones y registrar todos los gastos en Alegra de una vez."
        )
        gastos_card = {
            "type": "gastos_masivos_card",
            "titulo": "Carga Masiva de Gastos",
            "descripcion": (
                f"Archivo `{file_name}` listo — {n_rows} gastos detectados. "
                "Sube el archivo en la tarjeta para validar y registrar."
            ),
        }
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "assistant",
            "content": gastos_preview_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        return {
            "message": gastos_preview_msg,
            "pending_action": None,
            "session_id": session_id,
            "gastos_masivos_card": gastos_card,
        }

    # ── Generic CSV/Excel: inject as text context and call regular agent ────
    injected_message = (
        f"{user_message or 'Analiza este archivo'}\n\n"
        f"[ARCHIVO ADJUNTO: {file_name} — {n_rows} filas]\n"
        f"Contenido del archivo:\n```\n{text_table[:3000]}\n```"
    )
    # Delegate to regular process_chat but with text content (no file)
    return await process_chat(session_id, injected_message, db, user)


async def process_chat(
    session_id: str, user_message: str, db, user: dict,
    file_content: str = None, file_name: str = None, file_type: str = None,
) -> dict:
    # Route to document analysis if a file was attached
    if file_content:
        # CSV/Excel → text injection (not vision API)
        if _is_tabular_file(file_name or "", file_type or ""):
            return await process_tabular_chat(
                session_id, user_message, file_content,
                file_name or "archivo", file_type or "text/csv",
                db, user
            )
        return await process_document_chat(
            session_id, user_message, file_content,
            file_name or "documento", file_type or "image/jpeg",
            db, user
        )

    # ── CFO intent detection (antes del flujo contable normal) ───────────────
    from services.cfo_agent import is_cfo_query, process_cfo_query
    if is_cfo_query(user_message):
        return await process_cfo_query(user_message, db, user, session_id)
    # ─────────────────────────────────────────────────────────────────────────

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    # Import here to avoid circular import
    from alegra_service import AlegraService
    alegra_service = AlegraService(db)

    # Gather context (parallel where possible)
    context_data = await gather_context(user_message, alegra_service, db)
    accounts_str, patterns_str, honorarios_instruccion = await gather_accounts_context(user_message, alegra_service, db)
    context_str = json.dumps(context_data, ensure_ascii=False)

    # Build IVA context string
    iva_ctx = context_data.get("iva_status")
    if iva_ctx:
        iva_context_str = (
            f"Período: {_safe_str(iva_ctx.get('periodo'))} | Tipo: {_safe_str(iva_ctx.get('tipo'))} | "
            f"Mes {_safe_str(iva_ctx.get('meses_transcurridos'))} de {_safe_str(iva_ctx.get('meses_total'))}\n"
            f"Fecha límite: {_safe_str(iva_ctx.get('fecha_limite'))} ({_safe_str(iva_ctx.get('dias_restantes'))} días)\n"
            f"IVA cobrado acumulado: ${_safe_num(iva_ctx.get('iva_cobrado_acumulado')):,.0f}\n"
            f"IVA descontable acumulado: ${_safe_num(iva_ctx.get('iva_descontable_acumulado')):,.0f}\n"
            f"IVA bruto del período: ${_safe_num(iva_ctx.get('iva_bruto_periodo')):,.0f}\n"
            f"Saldo a favor DIAN: ${_safe_num(iva_ctx.get('saldo_favor_dian')):,.0f}\n"
            f"⚠️ IVA ESTIMADO A PAGAR DIAN: ${_safe_num(iva_ctx.get('iva_pagar_estimado')):,.0f}\n"
            f"Facturas: {iva_ctx.get('facturas_venta')} ventas / {iva_ctx.get('facturas_compra')} compras registradas"
        )
    else:
        iva_context_str = "Pregunta sobre IVA para obtener el estado actualizado del período cuatrimestral."

    # Append inventory / loanbook / catalog items context if injected
    extra_context = ""
    if context_data.get("items_catalogo"):
        items_list = context_data["items_catalogo"]
        lines = [f"  • [{it['id']}] {it['name']} (type={it['type']})" for it in items_list]
        extra_context += "\n\nITEMS_CATALOGO_ALEGRA (IDs válidos para registrar_factura_compra → purchases.items):\n" + "\n".join(lines)
    if context_data.get("inventario_disponible"):
        motos_list = context_data["inventario_disponible"]
        fuente = context_data.get("inventario_fuente", "local")
        lines = [f"  • [{_safe_str(m.get('id'))}] {_safe_str(m.get('marca'))} {_safe_str(m.get('version'))} {_safe_str(m.get('color'))} — Chasis: {_safe_str(m.get('chasis'))} Motor: {_safe_str(m.get('motor'))} Precio: ${_safe_num(m.get('total')):,.0f}" for m in motos_list]
        extra_context += f"\n\nINVENTARIO_DISPONIBLE (fuente: {fuente}, {len(motos_list)} motos en stock):\n" + "\n".join(lines)
    elif context_data.get("inventario_inferido"):
        inf = context_data["inventario_inferido"]
        extra_context += (
            f"\n\nINVENTARIO (datos directos no disponibles — fuentes MongoDB e Alegra sin datos):\n"
            f"  • Loanbooks activos (motos entregadas a crédito): {inf.get('loanbooks_activos', '?')}\n"
            f"  • Registros totales en inventario local: {inf.get('total_en_inventario_db', '?')}\n"
            f"  • NOTA: {inf.get('nota', '')}\n"
            f"  → Dirige al usuario al módulo Motos para ver el detalle exacto del stock disponible."
        )
    if context_data.get("loanbook_activos"):
        lb_list = context_data["loanbook_activos"]
        lines = [
            f"  • [{_safe_str(l.get('codigo'))}] id={_safe_str(l.get('id'))} — {_safe_str(l.get('cliente'))} | Plan: {_safe_str(l.get('plan'))} | "
            f"Saldo: ${_safe_num(l.get('saldo_pendiente')):,.0f} | Estado: {_safe_str(l.get('estado'))} | "
            f"Alegra factura: {_safe_str(l.get('factura_alegra_id'), '?')} | "
            f"Entrega: {_safe_str(l.get('fecha_entrega'), 'pendiente')}"
            for l in lb_list[:10]
        ]
        extra_context += "\n\nLOANBOOK_ACTIVOS:\n" + "\n".join(lines)

    if context_data.get("actividad_hoy"):
        extra_context += (
            "\n\nACTIVIDAD DE HOY (" + context_data["fecha_actual"] + "):\n"
            + context_data["actividad_hoy"]
        )
        acct_list = context_data.get("cuentas_contables", [])
        lines = [f"  • id={a['id']} | code={a.get('code','')} | {a['name']}" for a in acct_list]
        extra_context += (
            "\n\nCUENTAS_CONTABLES_ALEGRA — USA ESTOS IDs EN crear_causacion (NO inventes IDs):\n"
            + "\n".join(lines)
        )

    # Build system prompt with all context
    # ── CFO context + Monday report ───────────────────────────────────────────
    from datetime import date as _date
    _today = _date.today()
    cfo_context_lines = []

    # Real-time cartera data
    _lbs_activos = await db.loanbook.count_documents({"estado": "activo"})
    _cfg_fin = await db.cfo_financiero_config.find_one({}, {"_id": 0}) or {}
    _gastos = _safe_num(_cfg_fin.get("gastos_fijos_semanales"))
    _deuda_np_doc = await db.cfo_deudas.aggregate([
        {"$match": {"tipo": "no_productiva", "estado": {"$ne": "pagada"}}},
        {"$group": {"_id": None, "total": {"$sum": "$saldo_pendiente"}}}
    ]).to_list(1)
    _deuda_np = _safe_num(_deuda_np_doc[0].get("total")) if _deuda_np_doc else 0
    _ci_doc = await db.loanbook.aggregate([
        {"$match": {"cuota_inicial_pendiente": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$cuota_inicial_pendiente"}}}
    ]).to_list(1)
    _ci_pendiente = _safe_num(_ci_doc[0].get("total")) if _ci_doc else 0
    _creditos_min = int(-(-_gastos // 167722)) if _gastos > 0 else 0

    cfo_context_lines.append(
        f"ESTADO CARTERA HOY ({_today.isoformat()}): "
        f"{_lbs_activos} créditos activos | Recaudo base $1,509,500/sem | "
        f"Deuda NP: ${_deuda_np:,.0f} | CI pendientes: ${_ci_pendiente:,.0f} | "
        f"Gastos fijos config: ${_gastos:,.0f}/sem | Mínimo créditos: {_creditos_min}"
    )

    # Alerta piso créditos
    if _gastos > 0 and _lbs_activos < _creditos_min:
        cfo_context_lines.append(
            f"⚠️ ALERTA CFO REGLA 3: Solo {_lbs_activos} créditos activos, mínimo recomendado: {_creditos_min}"
        )

    # Monday report — inject automatically
    if _today.weekday() == 0:  # Monday
        try:
            from routers.cfo_estrategico import get_reporte_lunes
            _reporte = await get_reporte_lunes(current_user=user)
            alertas_reporte = _reporte.get("alertas", [])
            _rec = _safe_num(_reporte.get("ingresos", {}).get("recaudo_cartera"))
            _gast = _safe_num(_reporte.get("egresos", {}).get("gastos_fijos"))
            _caja = _safe_num(_reporte.get("caja", {}).get("proyectada"))
            cfo_context_lines.append(
                f"\n📊 REPORTE CFO LUNES ({_today.isoformat()}):\n"
                f"  Recaudo esta semana: ${_rec:,.0f} ({_safe_num(_reporte.get('ingresos', {}).get('num_cuotas')):.0f} cuotas)\n"
                f"  Gastos fijos: ${_gast:,.0f}\n"
                f"  Caja proyectada fin de semana: ${_caja:,.0f} {'✅' if _caja >= 0 else '🔴'}\n"
                f"  Deuda NP: ${_safe_num(_reporte.get('deuda', {}).get('no_productiva')):,.0f}\n"
                + ("\n".join(f"  {a['msg']}" for a in alertas_reporte) if alertas_reporte else "  Sin alertas.")
            )
        except Exception:
            pass

    # ── Recordatorios CFO pendientes ─────────────────────────────────────────
    try:
        _recordatorios = await db.roddos_events.find(
            {
                "event_type": "cfo.recordatorio",
                "estado":     "pendiente",
                "fecha_recordatorio": {"$lte": _today.isoformat()},
            },
            {"_id": 0},
        ).to_list(5)
        for r in _recordatorios:
            cfo_context_lines.append(
                f"\n🔔 RECORDATORIO PENDIENTE ({r.get('fecha_recordatorio', '')}) — {r.get('titulo', '')}:\n"
                f"  {r.get('descripcion', '')}\n"
                f"  Prioridad: {r.get('prioridad', 'normal').upper()} | "
                f"  Acciones: {' | '.join(r.get('acciones_requeridas', [])[:3])}"
            )
    except Exception:
        pass

    # ── BUILD 12: Estado de Resultados en contexto CFO ────────────────────────
    try:
        from routers.estado_resultados import _build_pl
        periodo = f"{_today.year}-{_today.month:02d}"
        _pl = await _build_pl(periodo, user)
        _ing  = _safe_num(_pl["ingresos"]["total"]) if _pl.get("ingresos") else 0
        _neta = _safe_num(_pl.get("utilidad_neta"))
        _modo = _safe_str(_pl.get("modo"))
        _margen = _safe_num(_pl.get("margen_bruto_pct"))
        _gastos = _safe_num(_pl["gastos_operacionales"]["total"]) if _pl.get("gastos_operacionales") else 0
        cfo_context_lines.append(
            f"\n📊 P&L {_pl['mes_label']} (modo={_modo}):\n"
            f"  Ingresos: ${_ing:,.0f} | COGS: ${_safe_num(_pl.get('costo_ventas', {}).get('total')):,.0f} | "
            f"Utilidad bruta: ${_safe_num(_pl.get('utilidad_bruta')):,.0f} ({_margen:.1f}%)\n"
            f"  Gastos oper.: ${_gastos:,.0f} | Utilidad neta: ${_neta:,.0f}"
            + (f"\n  ⚠️ ALERTA: Margen bruto {_margen:.1f}% por debajo del 15% mínimo." if _pl.get("alerta_margen_critico") else "")
            + (f"\n  ⚠️ {_pl['costo_ventas']['advertencia']}" if _pl["costo_ventas"].get("advertencia") else "")
            + (f"\n  ⚠️ {_pl['gastos_operacionales']['advertencia']}" if _pl["gastos_operacionales"].get("advertencia") else "")
        )
    except Exception:
        pass

    cfo_ctx_str = "\n".join(cfo_context_lines)

    system_prompt = (
        AGENT_SYSTEM_PROMPT
        .replace("{context}", context_str + extra_context)
        .replace("{iva_context}", iva_context_str)
        .replace("{accounts_context}", accounts_str)
        .replace("{patterns_context}", patterns_str)
        .replace("{honorarios_instruccion}", honorarios_instruccion)
        .replace("{cfo_context}", cfo_ctx_str)
    )

    # ── MODULE 4: Inyectar temas pendientes del usuario (BUILD 21) ────────────
    user_id = user.get("id", "")
    pending_topics_list = await get_pending_topics(db, user_id) if user_id else []
    pending_topics_txt = _format_pending_topics_for_prompt(pending_topics_list)
    if pending_topics_txt:
        system_prompt = system_prompt.replace(
            "{pending_topics}", pending_topics_txt
        )
    else:
        system_prompt = system_prompt.replace(
            "{pending_topics}", "Sin temas pendientes de sesiones anteriores."
        )

    # ── MODULE 1: Auto-detect gasto socio pattern and inject warning ──────────
    _socios_kws = ["andrés", "andres", "sanjuan", "iván", "ivan", "echeverri",
                   "socio", "gasto del socio", "pagó el socio", "pago del socio"]
    _gasto_kws  = ["gasto", "pago", "pagó", "pago de", "pagué", "costó", "compró", "retiro"]
    _msg_lower_m1 = user_message.lower()
    _is_gasto_socio = (
        any(kw in _msg_lower_m1 for kw in _socios_kws) and
        any(kw in _msg_lower_m1 for kw in _gasto_kws)
    )
    if _is_gasto_socio:
        system_prompt += (
            "\n\nINSTRUCCIÓN URGENTE — REGLA GASTO SOCIO ACTIVA:\n"
            "El usuario mencionó un gasto/pago relacionado con un socio (Andrés Sanjuan o Iván Echeverri).\n"
            "ANTES de registrar CUALQUIER cosa, OBLIGATORIO preguntar:\n"
            "'¿Este pago a [nombre socio] es:\n"
            "  a) CXC (dinero que le prestó la empresa — el socio lo devuelve)\n"
            "  b) Anticipo de nómina (adelanto de salario)\n"
            "  c) Gasto personal pagado por la empresa (= CXC también)'\n"
            "Solo DESPUÉS de la confirmación del usuario → ejecutar la acción correcta.\n"
            "NUNCA causes un gasto socio como gasto operativo P&L."
        )


    # ── MEJORA 4: Comandos especiales de contexto ─────────────────────────────
    msg_lower_cmd = user_message.lower().strip()

    # ── BUILD 12: Detectar solicitud de exportación P&L ───────────────────────
    _export_keywords = ["exporta", "exportar", "estado de resultado", "p&l", "pl de", "informe financiero", "generar informe"]
    if any(kw in msg_lower_cmd for kw in _export_keywords):
        from datetime import date as _date
        # Extract period from message (look for month name or YYYY-MM)
        _meses_map = {"enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
                     "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"}
        _periodo_export = None
        for _m, _n in _meses_map.items():
            if _m in msg_lower_cmd:
                _ano = str(_date.today().year)
                _ano_match = re.search(r'\b(20\d\d)\b', user_message)
                if _ano_match: _ano = _ano_match.group(1)
                _periodo_export = f"{_ano}-{_n}"
                break
        if not _periodo_export:
            _h = _date.today()
            _periodo_export = f"{_h.year}-{_h.month:02d}"

        _ml = _meses_map.get(next((m for m in _meses_map if m in msg_lower_cmd), ""), _periodo_export[5:7])
        _ano_label = _periodo_export[:4]
        _mes_label = next((m.capitalize() for m in _meses_map if _meses_map[m] == _periodo_export[5:7]), _periodo_export)

        export_card = {
            "type":    "pl_export_card",
            "titulo":  f"Estado de Resultados — {_mes_label} {_ano_label}",
            "periodo": _periodo_export,
            "periodo_label": f"01/{_periodo_export[5:7]}/{_ano_label} — {_periodo_export[5:7]}/{_ano_label}",
        }

        resp = f"Aquí tienes el Estado de Resultados de **{_mes_label} {_ano_label}**. Elige el formato de exportación:"
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
            "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
            "content": resp, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        return {"message": resp, "pending_action": None, "session_id": session_id, "export_card": export_card}

    # ── BUILD 13: Detectar consulta de cuotas iniciales pendientes ─────────────
    _ci_keywords = ["cuota inicial pendiente", "cuotas iniciales pendientes", "quiénes tienen cuota inicial",
                    "quienes tienen cuota inicial", "lista de cuotas iniciales", "cobrar cuota inicial",
                    "dame la lista de cuotas", "recordatorios de cuota inicial", "cuota inicial por cobrar"]
    if any(kw in msg_lower_cmd for kw in _ci_keywords):
        try:
            _lbs_ci = await db.loanbook.find(
                {"cuota_inicial_pagada": False, "cuota_inicial_total": {"$gt": 0}},
                {"_id": 0, "cliente_nombre": 1, "codigo": 1, "cuota_inicial_total": 1, "cliente_telefono": 1, "cliente_id": 1}
            ).to_list(50)

            _cuotas_pending = []
            for lb in _lbs_ci:
                _cuotas_pending.append({
                    "cliente":   lb.get("cliente_nombre", "—"),
                    "codigo":    lb.get("codigo", ""),
                    "monto":     float(lb.get("cuota_inicial_total", 0)),
                    "telefono":  lb.get("cliente_telefono", ""),
                })

            _total_ci = sum(c["monto"] for c in _cuotas_pending)

            cuotas_card = {
                "type":     "cuotas_iniciales_card",
                "clientes": _cuotas_pending,
                "total":    _total_ci,
                "count":    len(_cuotas_pending),
            }
            _fmt = lambda n: f"${n:,.0f}".replace(",",".")
            resp_ci = (
                f"Hay **{len(_cuotas_pending)} clientes** con cuota inicial pendiente "
                f"por un total de **{_fmt(_total_ci)}**.\n"
                "Usa los botones de la tarjeta para enviar recordatorios por WhatsApp."
            )
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
                "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
                "content": resp_ci, "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            return {"message": resp_ci, "pending_action": None, "session_id": session_id, "cuotas_iniciales_card": cuotas_card}
        except Exception:
            pass  # fall through to LLM

    # ── BUILD 16: Detectar solicitud de carga masiva de gastos ───────────────
    _gastos_kws = [
        "carga masiva", "cargar gastos", "excel gastos", "subir gastos",
        "plantilla gastos", "gastos excel", "registro masivo", "masiva de gastos",
        "masivo de gastos", "excel de gastos", "carga de gastos", "cargar excel",
        "upload gastos", "gastos masivos", "csv gastos", "gastos csv",
        "plantilla csv", "cargar csv", "subir csv",
    ]
    if any(kw in msg_lower_cmd for kw in _gastos_kws):
        gastos_card = {
            "type":        "gastos_masivos_card",
            "titulo":      "Carga Masiva de Gastos",
            "descripcion": (
                "Descarga la plantilla CSV, llena los gastos y súbela para "
                "registrarlos automáticamente en Alegra."
            ),
        }
        resp_gastos = (
            "Aquí tienes la herramienta de **Carga Masiva de Gastos**. El formato es **CSV exclusivamente**.\n\n"
            "**Cómo usarla:**\n"
            "1. Descarga la plantilla CSV con el botón de abajo\n"
            "2. Llena los gastos desde la fila 2 (sin el `#` al inicio)\n"
            "   Columnas: `fecha, categoria, subcategoria, descripcion, monto, proveedor, referencia`\n"
            "3. Sube el archivo `.csv` directamente al chat\n"
            "4. Revisa el preview y confirma el registro en Alegra\n\n"
            "**Montos**: números enteros sin separadores (ej: `3500000`, no `$3.500.000`)\n"
            "**Si tienes un .xlsx**: Archivo → Guardar como → CSV UTF-8\n\n"
            "Calcula automáticamente ReteFuente, IVA y diferencia contado/crédito."
        )
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
            "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
            "content": resp_gastos, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        return {
            "message":            resp_gastos,
            "pending_action":     None,
            "session_id":         session_id,
            "gastos_masivos_card": gastos_card,
        }

    # ── INVENTARIO — Auditoría automática ─────────────────────────────────────
    _audit_kws = [
        "audita el inventario", "audita inventario", "auditoría de inventario",
        "el inventario tiene datos incorrectos", "hay una moto que no existe",
        "falta una moto en el inventario", "el conteo de motos no cuadra",
        "inventario descuadrado", "inconsistencias de inventario",
    ]
    if any(kw in msg_lower_cmd for kw in _audit_kws):
        try:
            _total = await db.inventario_motos.count_documents({})
            _disp = await db.inventario_motos.count_documents({"estado": "Disponible"})
            _vend = await db.inventario_motos.count_documents({"estado": {"$in": ["Vendida", "Entregada"]}})
            _anuladas = await db.inventario_motos.count_documents({"estado": "Anulada"})
            _lbs = await db.loanbook.count_documents({"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}})
            _cuadra = _vend == _lbs

            # Find inconsistencies: phantoms + unlinked
            _inconsistencias = []
            async for _m in db.inventario_motos.find(
                {"$or": [{"chasis": None}, {"chasis": ""}, {"chasis": {"$regex": "^PENDIENTE-"}}]},
                {"_id": 0, "id": 1, "marca": 1, "modelo": 1, "chasis": 1}
            ):
                _inconsistencias.append(f"• FANTASMA: {_m.get('marca','?')} {_m.get('modelo','?')} — chasis '{_m.get('chasis','?')}' — acción: eliminar")

            async for _lb in db.loanbook.find(
                {"estado": {"$in": ["activo", "mora"]}, "$or": [{"moto_chasis": None}, {"moto_chasis": ""}]},
                {"_id": 0, "codigo": 1, "cliente_nombre": 1}
            ):
                _inconsistencias.append(f"• SIN VIN: Loanbook {_lb.get('codigo')} ({_lb.get('cliente_nombre','?')}) — acción: asignar VIN")

            _fmt_n = lambda n: f"${n:,.0f}".replace(",", ".")
            _cuadra_icon = "✅" if _cuadra else "❌"
            _inc_text = "\n".join(_inconsistencias) if _inconsistencias else "• Ninguna detectada ✅"

            _audit_msg = (
                f"**AUDITORÍA DE INVENTARIO**\n"
                f"{'─'*40}\n"
                f"Total motos en sistema:    **{_total}**\n"
                f"Disponibles:               **{_disp}**\n"
                f"Vendidas / Entregadas:     **{_vend}**\n"
                f"Anuladas:                  **{_anuladas}**\n"
                f"Loanbooks activos:         **{_lbs}**\n"
                f"¿Vendidas = Loanbooks?     {_cuadra_icon} {'SÍ — cuadra correctamente' if _cuadra else 'NO — hay ' + str(abs(_vend - _lbs)) + ' descuadre'}\n\n"
                f"**INCONSISTENCIAS DETECTADAS: {len(_inconsistencias)}**\n"
                f"{'─'*40}\n"
                f"{_inc_text}\n\n"
            )
            if _inconsistencias:
                _audit_msg += "¿Quieres que corrija automáticamente las inconsistencias detectadas?"

            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
                "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
                "content": _audit_msg, "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            return {"message": _audit_msg, "pending_action": None, "session_id": session_id}
        except Exception:
            pass  # fall through to LLM

    # ── INVENTARIO — Consulta moto de un cliente específico ───────────────────
    _qué_moto_kws = ["qué moto tiene", "que moto tiene", "qué moto le entregamos", "vin de",
                     "chasis de", "moto de ", "moto del cliente"]
    if any(kw in msg_lower_cmd for kw in _qué_moto_kws):
        try:
            # Extract client name from message
            _words = msg_lower_cmd
            _client_name = None
            for _kw in _qué_moto_kws:
                if _kw in _words:
                    _client_name = _words.split(_kw, 1)[-1].strip().rstrip("?").strip()
                    break
            if _client_name and len(_client_name) > 2:
                _lb = await db.loanbook.find_one(
                    {"cliente_nombre": {"$regex": _client_name, "$options": "i"}},
                    {"_id": 0, "codigo": 1, "cliente_nombre": 1, "moto_chasis": 1, "motor": 1,
                     "modelo_moto": 1, "color_moto": 1, "estado": 1}
                )
                if _lb:
                    _chasis = _lb.get("moto_chasis") or "No registrado"
                    _motor_v = _lb.get("motor") or "No registrado"
                    _modelo_v = _lb.get("modelo_moto") or "No registrado"
                    _moto_resp = (
                        f"**Moto asignada a {_lb['cliente_nombre']}** ({_lb['codigo']}):\n"
                        f"• Modelo:  {_modelo_v}\n"
                        f"• Color:   {_lb.get('color_moto', 'No registrado')}\n"
                        f"• VIN/Chasis: `{_chasis}`\n"
                        f"• Motor:   `{_motor_v}`\n"
                        f"• Estado loanbook: {_lb.get('estado', '?')}"
                    )
                    await db.chat_messages.insert_one({
                        "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
                        "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
                        "user_id": user.get("id"),
                    })
                    await db.chat_messages.insert_one({
                        "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
                        "content": _moto_resp, "timestamp": datetime.now(timezone.utc).isoformat(),
                        "user_id": user.get("id"),
                    })
                    return {"message": _moto_resp, "pending_action": None, "session_id": session_id}
        except Exception:
            pass  # fall through to LLM
    _autoret_sí_patterns = [
        r'sí[,\s].*autoretenedor', r'si[,\s].*autoretenedor',
        r'sí[,\s].*es\s+autoret', r'si[,\s].*es\s+autoret',
        r'confirmo.*autoretenedor', r'es\s+autoretenedor',
    ]
    _is_autoret_confirm = False
    for _ap in _autoret_sí_patterns:
        if re.search(_ap, msg_lower_cmd, re.IGNORECASE):
            _is_autoret_confirm = True
            break
    if _is_autoret_confirm:
        try:
            # Find provider from recent assistant messages
            _recent_msgs = await db.chat_messages.find(
                {"session_id": session_id, "role": "assistant"},
                {"_id": 0, "content": 1},
            ).sort("timestamp", -1).limit(5).to_list(5)
            _prov_autoret = None
            for _rm in _recent_msgs:
                _content = _rm.get("content", "")
                _m = re.search(
                    r'Apliqué ReteFuente.*?a \*?\*?([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s.]+?)\*?\*?[.?]',
                    _content
                )
                if _m:
                    _prov_autoret = _m.group(1).strip()
                    break
            # Also extract from current message: "Sí, [Proveedor] es autoretenedora"
            _m2 = re.search(
                r'(?:sí|si)[,\s]+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s.]{3,50?})\s+es\s+autoretenedor',
                user_message, re.IGNORECASE
            )
            if _m2:
                _prov_autoret = _m2.group(1).strip()
            if _prov_autoret:
                await db.proveedores_config.update_one(
                    {"nombre": {"$regex": f"^{re.escape(_prov_autoret)}$", "$options": "i"}},
                    {"$set": {
                        "nombre": _prov_autoret,
                        "es_autoretenedor": True,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "updated_by": user.get("email"),
                    }},
                    upsert=True,
                )
                # Inject reversal instruction into system_prompt
                system_prompt += (
                    f"\n\nINSTRUCCIÓN URGENTE — REVERSIÓN AUTORETENEDOR:\n"
                    f"El usuario confirmó que **{_prov_autoret}** ES AUTORETENEDORA.\n"
                    "Debes:\n"
                    "1. Crear asiento de reversión (crear_causacion) para REVERTIR la ReteFuente aplicada:\n"
                    "   Débito: cuenta ReteFuente por pagar (23654001 Compras 2.5% o la que corresponda)\n"
                    f"   Crédito: cuenta por pagar a {_prov_autoret} (5070)\n"
                    "   Concepto: 'Reversión ReteFuente — proveedor autoretenedor'\n"
                    f"2. Confirmar: '{_prov_autoret} quedó registrada como AUTORETENEDORA. "
                    "ReteFuente revertida correctamente.'"
                )
        except Exception:
            pass

    # ── Modo diagnóstico automático (errores repetidos en sesión) ────────────
    try:
        _session_errors = await db.agent_errors.count_documents(
            {"stack_trace": {"$regex": session_id}, "fase": "process_chat"}
        )
        if _session_errors == 0:
            # Also check by recent timestamp (last 30 min, same user)
            from datetime import timedelta
            _cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            _session_errors = await db.agent_errors.count_documents({
                "timestamp": {"$gte": _cutoff},
                "user_message": {"$exists": True}
            })
        if _session_errors >= 2:
            system_prompt += (
                "\n\nINSTRUCCIÓN DIAGNÓSTICO (activada por errores repetidos en sesión):\n"
                "El usuario ha tenido 2+ errores en esta sesión. "
                "Incluye al inicio de tu próxima respuesta un diagnóstico breve:\n"
                "Estado del sistema:\n"
                f"• Inventario: {'disponible (' + str(len(context_data.get('inventario_disponible', []))) + ' motos)' if context_data.get('inventario_disponible') else 'no disponible desde contexto — usa módulo Motos'}\n"
                f"• Loanbooks: {context_data.get('loanbooks_total', '?')} activos\n"
                "• Luego propón 3 acciones alternativas concretas que puedas ejecutar ahora mismo."
            )
    except Exception:
        pass

    is_context_cmd = any(kw in msg_lower_cmd for kw in [
        "en qué íbamos", "en que ibamos", "qué falta", "que falta",
        "resumen", "qué hice", "que hice", "qué pasó hoy", "que paso hoy",
        "qué se hizo", "que se hizo",
    ])
    is_pausa = any(kw in msg_lower_cmd for kw in ["pausa la tarea", "pausar la tarea", "pausar tarea"])
    is_continua = any(kw in msg_lower_cmd for kw in ["continúa la tarea", "continua la tarea", "retomar tarea", "retoma la tarea"])

    # ── MEJORA 2: Cargar tarea activa ─────────────────────────────────────────
    tarea_activa = await db.agent_memory.find_one(
        {"tipo": "tarea_activa", "estado": "en_curso"},
        {"_id": 0},
    )

    if is_pausa and tarea_activa:
        await db.agent_memory.update_one(
            {"tipo": "tarea_activa", "estado": "en_curso"},
            {"$set": {"estado": "pausada", "ultimo_avance": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "message": f"⏸️ Tarea pausada: **{tarea_activa['descripcion']}** (paso {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)}).\nPuedes continuar cuando quieras diciendo **\"Continúa la tarea\"**.",
            "pending_action": None,
            "session_id": session_id,
        }

    if is_continua:
        tarea_pausada = await db.agent_memory.find_one(
            {"tipo": "tarea_activa", "estado": "pausada"},
            {"_id": 0},
        )
        if tarea_pausada:
            await db.agent_memory.update_one(
                {"tipo": "tarea_activa", "estado": "pausada"},
                {"$set": {"estado": "en_curso", "ultimo_avance": datetime.now(timezone.utc).isoformat()}},
            )
            tarea_activa = {**tarea_pausada, "estado": "en_curso"}
            pendientes = tarea_activa.get("pasos_pendientes", [])
            proximo = pendientes[0] if pendientes else "No hay pasos pendientes"
            return {
                "message": (
                    f"▶️ Retomando tarea: **{tarea_activa['descripcion']}**\n"
                    f"Progreso: {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)} pasos\n"
                    f"Siguiente paso: {proximo}"
                ),
                "pending_action": None,
                "session_id": session_id,
            }

    if is_context_cmd:
        from datetime import timezone as _tz
        lines = [f"## Resumen de contexto operativo ({datetime.now(_tz.utc).strftime('%Y-%m-%d')})"]

        if tarea_activa:
            pendientes = tarea_activa.get("pasos_pendientes", [])
            lines.append(
                f"\n**TAREA EN CURSO:** {tarea_activa['descripcion']}\n"
                f"Progreso: {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)} pasos\n"
                + ("Pendiente:\n" + "\n".join(f"  • {p}" for p in pendientes[:5]) if pendientes else "")
            )
        else:
            lines.append("\n*Sin tarea activa en curso.*")

        # MODULE 4: Mostrar temas pendientes de sesiones anteriores
        if pending_topics_list:
            lines.append("\n**Temas pendientes de sesiones anteriores:**")
            for pt in pending_topics_list:
                lines.append(
                    f"  • [{pt.get('topic_key','')}] {pt.get('descripcion','')} "
                    f"(expira: {pt.get('expires_at','')[:10]})"
                )
        else:
            lines.append("\n*Sin temas pendientes de sesiones anteriores.*")

        actividad = context_data.get("actividad_hoy", "")
        if actividad:
            lines.append(f"\n**Actividad de hoy:**\n{actividad}")
        else:
            lines.append("\n*Sin actividad registrada hoy.*")

        alertas = await db.cfo_alertas.find(
            {}, {"_id": 0, "mensaje": 1, "tipo": 1}
        ).sort("created_at", -1).limit(3).to_list(3)
        if alertas:
            lines.append("\n**Alertas pendientes CFO:**")
            for a in alertas:
                lines.append(f"  • {a.get('tipo','')}: {a.get('mensaje','')}")

        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "user",
            "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        resp = "\n".join(lines)
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()), "session_id": session_id, "role": "assistant",
            "content": resp, "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user.get("id"),
        })
        return {"message": resp, "pending_action": None, "session_id": session_id}

    # ── MEJORA 1: Cargar historial de la sesión y resumir si es largo ─────────
    CHARS_PER_TOKEN = 4
    MAX_HISTORY_TOKENS = 6000
    KEEP_RECENT_PAIRS = 6

    raw_history = await db.chat_messages.find(
        {"session_id": session_id},
        {"_id": 0, "role": 1, "content": 1, "timestamp": 1},
    ).sort("timestamp", 1).to_list(200)

    # Convert to LiteLLM message dicts (omit system messages already in initial_messages)
    history_msgs = [
        {"role": m["role"], "content": str(m.get("content", ""))}
        for m in raw_history
        if m["role"] in ("user", "assistant")
    ]

    total_chars = sum(len(m["content"]) for m in history_msgs)
    total_tokens_est = total_chars // CHARS_PER_TOKEN

    summary_msg = None
    if total_tokens_est > MAX_HISTORY_TOKENS and len(history_msgs) > KEEP_RECENT_PAIRS * 2:
        # Split: old messages to summarize + recent messages to keep
        split_idx = len(history_msgs) - KEEP_RECENT_PAIRS * 2
        old_msgs  = history_msgs[:split_idx]
        recent_msgs = history_msgs[split_idx:]

        # Summarize the old portion
        try:
            _summary_client = anthropic.AsyncAnthropic(api_key=api_key)
            _summary_msgs = [m for m in old_msgs[:60] if m.get("role") in ("user", "assistant")]
            _summary_msgs.append({"role": "user", "content": "Resume los puntos clave de esta conversación."})
            _summary_resp = await _summary_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=512,
                system=(
                    "Eres un asistente que resume conversaciones de contabilidad. "
                    "Extrae: tareas completadas, datos mencionados (clientes, montos, facturas, NITs), pendientes. "
                    "Máximo 200 palabras en español."
                ),
                messages=_summary_msgs,
            )
            summary_text = _summary_resp.content[0].text
            summary_msg = {
                "role": "system",
                "content": f"RESUMEN DE CONVERSACIÓN ANTERIOR:\n{summary_text}",
            }
            history_msgs = recent_msgs
        except Exception:
            history_msgs = history_msgs[-(KEEP_RECENT_PAIRS * 2):]

    # Build initial_messages for this request
    initial_messages: list = [{"role": "system", "content": system_prompt}]
    if summary_msg:
        initial_messages.append(summary_msg)

    # ── MEJORA 2: Inyectar tarea activa en el contexto ────────────────────────
    if tarea_activa:
        pendientes = tarea_activa.get("pasos_pendientes", [])
        tarea_ctx = (
            f"TAREA EN CURSO: {tarea_activa['descripcion']}\n"
            f"Progreso: {tarea_activa.get('pasos_completados',0)}/{tarea_activa.get('pasos_total',0)} pasos completados.\n"
            + (f"Pasos pendientes: {', '.join(pendientes[:5])}\n" if pendientes else "")
            + "Continúa exactamente desde donde quedaste sin repetir pasos ya completados."
        )
        initial_messages.append({"role": "system", "content": tarea_ctx})

    initial_messages.extend(history_msgs)

    # Save user message to MongoDB
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    # ── Pre-LLM bypass: cargar_loanbooks_lote ────────────────────────────────
    # Fires when the message explicitly names the action OR contains the four
    # mandatory field markers of a bulk loanbook payload.  When the payload can
    # be parsed we skip the LLM entirely and return a confirmation card with
    # pending_action so the frontend "Confirmar y ejecutar" button can fire.
    import re as _re_lb

    _msg_lo_lb = user_message.lower()
    _is_lote_lb = (
        "cargar_loanbooks_lote" in user_message
        or (
            "cliente_nombre:" in _msg_lo_lb
            and "moto_chasis:"  in _msg_lo_lb
            and "cuota_base:"   in _msg_lo_lb
            and "modo_pago:"    in _msg_lo_lb
        )
    )

    if _is_lote_lb:
        _lb_list: list = []

        # Strategy 1 — JSON array in the message body
        _jarr_m = _re_lb.search(r'\[\s*\{.*?\}\s*\]', user_message, _re_lb.DOTALL)
        if _jarr_m:
            try:
                _parsed_lb = json.loads(_jarr_m.group())
                if isinstance(_parsed_lb, list) and _parsed_lb:
                    _lb_list = _parsed_lb
            except Exception:
                pass

        # Strategy 2 — {"loanbooks": [...]} wrapper object
        if not _lb_list:
            _jobj_m = _re_lb.search(
                r'\{[^{}]*"loanbooks"\s*:\s*\[.*?\]\s*\}', user_message, _re_lb.DOTALL
            )
            if _jobj_m:
                try:
                    _pobj_lb = json.loads(_jobj_m.group())
                    if isinstance(_pobj_lb.get("loanbooks"), list):
                        _lb_list = _pobj_lb["loanbooks"]
                except Exception:
                    pass

        # Strategy 3 — key:value pairs (single-loanbook fallback)
        if not _lb_list:
            def _kv_lb(field: str, text: str, cast=str):
                m = _re_lb.search(rf'(?i){field}\s*[:\-=]\s*([^\n,;]+)', text)
                if m:
                    try:
                        return cast(m.group(1).strip().strip('"\''))
                    except Exception:
                        return None
                return None

            _lb_candidate = {k: v for k, v in {
                "cliente_nombre":   _kv_lb("cliente_nombre",   user_message),
                "moto_chasis":      _kv_lb("moto_chasis",      user_message),
                "plan":             _kv_lb("plan",             user_message),
                "modo_pago":        _kv_lb("modo_pago",        user_message),
                "cuota_base":       _kv_lb("cuota_base",       user_message, int),
                "precio_venta":     _kv_lb("precio_venta",     user_message, int),
                "cuota_inicial":    _kv_lb("cuota_inicial",    user_message, int),
                "fecha_factura":    _kv_lb("fecha_factura",    user_message),
                "fecha_entrega":    _kv_lb("fecha_entrega",    user_message),
                "moto_descripcion": _kv_lb("moto_descripcion", user_message),
                "cliente_nit":      _kv_lb("cliente_nit",      user_message),
                "cliente_telefono": _kv_lb("cliente_telefono", user_message),
                "cuotas_pagadas":   _kv_lb("cuotas_pagadas",   user_message, int),
            }.items() if v is not None}
            if _lb_candidate.get("cliente_nombre") and _lb_candidate.get("moto_chasis"):
                _lb_list = [_lb_candidate]

        if _lb_list:
            # Build preview card and return immediately — no LLM call needed
            _preview_lines = []
            for _lb_item in _lb_list[:5]:
                _preview_lines.append(
                    f"• **{_lb_item.get('cliente_nombre', '?')}** — "
                    f"Chasis: `{_lb_item.get('moto_chasis', '?')}` "
                    f"| Plan: {_lb_item.get('plan', '?')} "
                    f"| Modo: {_lb_item.get('modo_pago', '?')} "
                    f"| Cuota base: ${int(_lb_item.get('cuota_base', 0)):,}"
                )
            _rem_lb = len(_lb_list) - 5
            _prev_txt_lb = "\n".join(_preview_lines)
            if _rem_lb > 0:
                _prev_txt_lb += f"\n  _(y {_rem_lb} más…)_"
            _confirm_msg_lb = (
                f"📋 Detecté **{len(_lb_list)} loanbook(s)** para carga masiva:\n\n"
                f"{_prev_txt_lb}\n\n"
                "Haz clic en **Confirmar y ejecutar** para insertar en MongoDB Atlas."
            )
            await db.chat_messages.insert_one({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": "assistant",
                "content": _confirm_msg_lb,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user.get("id"),
            })
            return {
                "message": _confirm_msg_lb,
                "pending_action": {
                    "action": "cargar_loanbooks_lote",
                    "payload": {"loanbooks": _lb_list},
                },
                "session_id": session_id,
            }
    # ── End pre-LLM bypass ───────────────────────────────────────────────────

    # Call Claude with full history context
    # Prompt caching enabled via cache_control (reduces token consumption ~90% on subsequent calls)
    _chat_client = anthropic.AsyncAnthropic(api_key=api_key)
    _system_parts = [m["content"] for m in initial_messages if m.get("role") == "system"]
    _chat_msgs = [m for m in initial_messages if m.get("role") in ("user", "assistant")]

    # RATE LIMIT OPTIMIZATION: Truncate history to last 6 messages (3 turns)
    # This reduces payload by 60-70% for long conversations while keeping context
    if len(_chat_msgs) > 6:
        _chat_msgs = _chat_msgs[-6:]

    _chat_msgs.append({"role": "user", "content": user_message})

    _system_text = "\n\n".join(_system_parts) if _system_parts else system_prompt

    _chat_resp = await _chat_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _system_text,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=_chat_msgs,
    )
    response_text = _chat_resp.content[0].text

    # Parse action block
    action = None
    clean_response = response_text
    if "<action>" in response_text and "</action>" in response_text:
        try:
            start = response_text.index("<action>") + 8
            end = response_text.index("</action>")
            action_json = response_text[start:end].strip()
            action = json.loads(action_json)
            clean_response = (
                response_text[:response_text.index("<action>")].strip()
                + response_text[end + 9:].strip()
            ).strip()
        except Exception:
            pass

    # Save assistant response
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user.get("id"),
    })

    return {
        "message": clean_response,
        "pending_action": action,
        "session_id": session_id,
    }


async def execute_chat_action(action_type: str, payload: dict, db, user: dict) -> dict:
    """Execute a confirmed action in Alegra."""
    from alegra_service import AlegraService
    service = AlegraService(db)

    # ── Extract internal _metadata BEFORE anything else ──────────────────────
    internal_metadata: dict = {}
    if isinstance(payload, dict):
        internal_metadata = payload.pop("_metadata", None) or {}

    # ── Special case: registrar_entrega (internal-only, no Alegra call) ──────
    if action_type == "registrar_entrega":
        loan_id = payload.get("loanbook_id", "") or internal_metadata.get("loanbook_id", "")
        loan_codigo = payload.get("loanbook_codigo", "")
        fecha_entrega = payload.get("fecha_entrega", "")
        if not fecha_entrega:
            raise ValueError("Falta fecha_entrega para registrar la entrega")

        # Look up by id or codigo
        loan = await db.loanbook.find_one({"id": loan_id}, {"_id": 0})
        if not loan and loan_codigo:
            loan = await db.loanbook.find_one({"codigo": loan_codigo}, {"_id": 0})
        if not loan:
            raise ValueError(f"Loanbook '{loan_id or loan_codigo}' no encontrado")

        from routers.loanbook import register_entrega as lb_entrega, EntregaRequest
        req_obj = EntregaRequest(fecha_entrega=fecha_entrega)
        result = await lb_entrega(loan["id"], req_obj, user)
        result_dict = dict(result) if not isinstance(result, dict) else result

        from post_action_sync import post_action_sync
        sync_result = await post_action_sync(
            "registrar_entrega", result_dict, payload, db, user, metadata=internal_metadata
        )
        return {
            "success": True,
            "result": result_dict,
            "id": loan["id"],
            "message": result_dict.get("message", "Entrega registrada y Loanbook activado"),
            "sync": sync_result,
        }

    ACTION_MAP = {
        "crear_factura_venta": ("invoices", "POST"),
        "registrar_factura_compra": ("bills", "POST"),
        "crear_causacion": ("journals", "POST"),
        "registrar_pago": ("payments", "POST"),
        "registrar_pago_cartera": ("cartera/registrar-pago", "POST"),
        "registrar_nomina": ("nomina/registrar", "POST"),
        "registrar_abono_socio": ("cxc/socios/abono", "POST"),
        "consultar_saldo_socio": ("cxc/socios/saldo", "GET"),
        "registrar_ingreso_no_operacional": ("ingresos/no-operacional", "POST"),
        "crear_contacto": ("contacts", "POST"),
        "crear_nota_credito": ("credit-notes", "POST"),
        "crear_nota_debito": ("debit-notes", "POST"),
    }

    # ── Special case: diagnosticar_contabilidad (MODULE 1 — BUILD 21) ────────
    if action_type == "diagnosticar_contabilidad":
        from services.accounting_engine import (
            diagnosticar_asiento, formatear_diagnostico_para_prompt,
            calcular_retenciones, formatear_retenciones_para_prompt,
            clasificar_transaccion,
        )
        entries = payload.get("entries", [])
        fecha   = payload.get("fecha", "")
        tipo    = payload.get("tipo", "diagnostico")

        if tipo == "retenciones":
            ret = calcular_retenciones(
                tipo_proveedor  = payload.get("tipo_proveedor", "PN"),
                tipo_gasto      = payload.get("tipo_gasto", "servicios"),
                monto_bruto     = float(payload.get("monto", 0)),
                es_autoretenedor = payload.get("es_autoretenedor", False),
                aplica_iva      = payload.get("aplica_iva", False),
                aplica_reteica  = payload.get("aplica_reteica", False),
            )
            return {
                "success": True,
                "result": ret,
                "message": formatear_retenciones_para_prompt(ret),
            }

        if tipo == "clasificacion":
            clf = clasificar_transaccion(
                descripcion     = payload.get("descripcion", ""),
                proveedor       = payload.get("proveedor", ""),
                monto           = float(payload.get("monto", 0)),
                tipo_proveedor  = payload.get("tipo_proveedor", "UNCLEAR"),
            )
            return {
                "success": True,
                "result": clf,
                "message": (
                    f"Clasificación: {clf['categoria']} → {clf['subcategoria']} "
                    f"(Cuenta Alegra ID: {clf['alegra_id']}, confianza: {clf['confianza']:.0%}). "
                    f"Retención sugerida: {clf['tipo_retencion']}"
                ),
            }

        # Default: diagnóstico de asiento
        diag = diagnosticar_asiento(entries, fecha)
        return {
            "success": diag["valido"],
            "result": diag,
            "message": formatear_diagnostico_para_prompt(diag),
        }

    # ── Special case: guardar_pendiente (MODULE 4 — BUILD 21) ────────────────
    if action_type == "guardar_pendiente":
        user_id = user.get("id", "")
        if not user_id:
            return {"success": False, "message": "No hay usuario autenticado para guardar pendiente."}
        topic_key   = payload.get("topic_key", f"tema_{uuid.uuid4().hex[:6]}")
        descripcion = payload.get("descripcion", "Tema sin descripción")
        datos_ctx   = payload.get("datos_contexto", {})
        await save_pending_topic(db, user_id, topic_key, descripcion, datos_ctx)
        return {
            "success": True,
            "message": f"Tema '{topic_key}' guardado como pendiente. Expira en 72 horas.",
            "topic_key": topic_key,
        }

    # ── Special case: completar_pendiente (MODULE 4 — BUILD 21) ──────────────
    if action_type == "completar_pendiente":
        user_id   = user.get("id", "")
        topic_key = payload.get("topic_key", "")
        if user_id and topic_key:
            await complete_pending_topic(db, user_id, topic_key)
        return {"success": True, "message": f"Tema '{topic_key}' marcado como completado."}

    # ── Special case: verificar_estado_alegra (MODULE 2 — BUILD 21) ──────────
    if action_type == "verificar_estado_alegra":
        resource = payload.get("resource", "")
        rid      = payload.get("id", "")
        if not resource:
            return {"success": False, "message": "Falta parámetro 'resource' (ej: 'journals', 'invoices')."}
        endpoint_v = f"{resource}/{rid}" if rid else resource
        try:
            ver_result = await service.request(endpoint_v, "GET")
            if isinstance(ver_result, list) and not ver_result:
                return {
                    "success": False,
                    "result": None,
                    "message": f"El recurso {endpoint_v} NO existe en Alegra (devolvió lista vacía o 404).",
                }
            return {
                "success": True,
                "result": ver_result,
                "message": f"Recurso {endpoint_v} verificado en Alegra. Existe y está accesible.",
            }
        except HTTPException as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error al verificar {endpoint_v} en Alegra: {e.detail}",
            }

    # ── Special case: crear_causacion (F2 — Chat Transaccional) ────────────────
    if action_type == "crear_causacion":
        # PHASE 2 — F2 Chat Transaccional: POST journal to /journals with verification
        # Validar que payload tiene entries array válido
        entries = payload.get("entries", [])
        if not entries or len(entries) < 2:
            return {
                "success": False,
                "error": "❌ Asiento requiere mínimo 2 líneas (débito y crédito)"
            }

        # Validar que débitos = créditos
        total_debito = sum(float(e.get("debit", 0) or 0) for e in entries)
        total_credito = sum(float(e.get("credit", 0) or 0) for e in entries)
        diferencia = abs(total_debito - total_credito)

        # Tolerancia: 1 COP por redondeo
        if diferencia > 1:
            return {
                "success": False,
                "error": f"❌ Desbalance en asiento: Débitos (${total_debito:,.0f}) ≠ Créditos (${total_credito:,.0f})"
            }

        # Validar que date está presente y es válido
        fecha = payload.get("date", "")
        if not fecha:
            from datetime import datetime as _dt
            fecha = _dt.now().isoformat()[:10]  # YYYY-MM-DD
            payload["date"] = fecha

        # Validar que observations (descripción) está presente
        if not payload.get("observations", ""):
            return {
                "success": False,
                "error": "❌ Asiento requiere descripción en el campo 'observations'"
            }

        logger.info(
            f"[F2] Crear causacion: {len(entries)} líneas, "
            f"débitos=${total_debito:,.0f}, créditos=${total_credito:,.0f}"
        )

        # POST a Alegra via request_with_verify() para garantizar HTTP 200
        try:
            result = await service.request_with_verify("journals", "POST", payload)
        except Exception as e:
            logger.error(f"[F2] POST a /journals falló: {str(e)}")
            return {
                "success": False,
                "error": f"❌ Error al crear asiento en Alegra: {str(e)}"
            }

        # Verificar que request_with_verify() retornó _verificado: True
        if not result.get("_verificado"):
            error_msg = result.get("_error_verificacion", "Verificación fallida sin detalles")
            logger.error(f"[F2] Verificación de journal falló: {error_msg}")
            return {
                "success": False,
                "error": f"❌ Asiento creado pero no verificado en Alegra: {error_msg}"
            }

        # Extraer alegra_id (el ID real del journal)
        alegra_id = result.get("id")
        if not alegra_id:
            logger.error(f"[F2] Alegra no retornó un ID válido en la respuesta: {result}")
            return {
                "success": False,
                "error": "❌ Alegra no retornó un ID del journal creado"
            }

        logger.info(f"[F2] ✅ Journal creado en Alegra: ID={alegra_id}")

        # Llamar post_action_sync() para sincronizar MongoDB
        try:
            sync_result = await post_action_sync(
                "crear_causacion",
                result,
                payload,
                db,
                user,
                metadata=internal_metadata
            )
        except Exception as e:
            logger.error(f"[F2] post_action_sync falló (no fatal): {str(e)}")
            sync_result = {"sync_messages": [f"⚠️ Asiento creado pero sincronización parcial: {str(e)}"]}

        # Llamar invalidar_cache_cfo() para limpiar caché CFO
        try:
            from routers.cfo import invalidar_cache_cfo
            await invalidar_cache_cfo()
            logger.info("[F2] CFO cache invalidada")
        except Exception as e:
            logger.warning(f"[F2] No se pudo invalidar CFO cache (no fatal): {str(e)}")

        return {
            "success": True,
            "id": alegra_id,
            "journal_number": result.get("number", ""),
            "message": f"✅ Asiento creado en Alegra con ID: {alegra_id}",
            "result": result,
            "sync": sync_result,
        }

    # ── Special case: crear_factura_venta (F6 — Facturación Venta Motos) ────────
    if action_type == "crear_factura_venta":
        # PHASE 2 — F6: POST to /ventas/crear-factura endpoint (already calls request_with_verify)
        # Validar campos obligatorios
        if not payload.get("moto_chasis") or not payload.get("moto_chasis").strip():
            return {
                "success": False,
                "error": "❌ VIN (moto_chasis) es obligatorio para crear factura"
            }
        if not payload.get("moto_motor") or not payload.get("moto_motor").strip():
            return {
                "success": False,
                "error": "❌ Motor (moto_motor) es obligatorio para crear factura"
            }

        logger.info(
            f"[F6] Crear factura venta: VIN {payload.get('moto_chasis')}, "
            f"cliente {payload.get('cliente_nombre')}, plan {payload.get('plan')}"
        )

        # Call the /ventas/crear-factura endpoint directly
        try:
            # The endpoint is POST /api/ventas/crear-factura, but via service it's just /ventas/crear-factura
            result = await service.request("ventas/crear-factura", "POST", payload)
        except Exception as e:
            logger.error(f"[F6] POST a /ventas/crear-factura falló: {str(e)}")
            return {
                "success": False,
                "error": f"❌ Error al crear factura venta: {str(e)}"
            }

        # Verificar que la respuesta tiene success: True
        if not result.get("success"):
            logger.error(f"[F6] Endpoint retornó success=False: {result.get('error', 'Error desconocido')}")
            return {
                "success": False,
                "error": f"❌ Error creando factura: {result.get('error', result.get('mensaje'))}"
            }

        # Extraer IDs
        invoice_id = result.get("factura_alegra_id")
        loanbook_id = result.get("loanbook_id")
        invoice_number = result.get("factura_numero")

        if not invoice_id or not loanbook_id:
            logger.error(f"[F6] Respuesta no contiene IDs válidos: {result}")
            return {
                "success": False,
                "error": "❌ Factura creada pero sin IDs válidos"
            }

        logger.info(f"[F6] ✅ Factura creada: {invoice_number} (ID: {invoice_id}), Loanbook: {loanbook_id}")

        return {
            "success": True,
            "factura_alegra_id": invoice_id,
            "factura_numero": invoice_number,
            "loanbook_id": loanbook_id,
            "message": f"✅ Factura creada en Alegra: {invoice_number}. Loanbook: {loanbook_id}",
            "result": result,
        }

    # ── Special case: registrar_pago_cartera (F7 — Ingresos por Cuotas) ────────
    if action_type == "registrar_pago_cartera":
        # PHASE 2 — F7: POST to /cartera/registrar-pago endpoint
        # Validar campos obligatorios
        if not payload.get("loanbook_id") or not payload.get("loanbook_id").strip():
            return {
                "success": False,
                "error": "❌ loanbook_id es obligatorio para registrar pago"
            }
        if payload.get("monto_pago", 0) <= 0:
            return {
                "success": False,
                "error": "❌ monto_pago debe ser > 0"
            }

        logger.info(
            f"[F7] Registrar pago cartera: Loanbook {payload.get('loanbook_id')}, "
            f"monto ${payload.get('monto_pago')}"
        )

        # Call the /cartera/registrar-pago endpoint directly
        try:
            result = await service.request("cartera/registrar-pago", "POST", payload)
        except Exception as e:
            logger.error(f"[F7] POST a /cartera/registrar-pago falló: {str(e)}")
            return {
                "success": False,
                "error": f"❌ Error registrando pago: {str(e)}"
            }

        # Verificar que la respuesta tiene success: True
        if not result.get("success"):
            logger.error(f"[F7] Endpoint retornó success=False: {result.get('error', 'Error desconocido')}")
            return {
                "success": False,
                "error": f"❌ Error registrando pago: {result.get('error', result.get('mensaje'))}"
            }

        # Extraer IDs
        journal_id = result.get("journal_id")
        loanbook_id = result.get("loanbook_id")
        cuota_numero = result.get("cuota_numero")
        saldo_pendiente = result.get("saldo_pendiente")

        if not journal_id:
            logger.error(f"[F7] Respuesta no contiene journal_id: {result}")
            return {
                "success": False,
                "error": "❌ Pago registrado pero sin journal_id de Alegra"
            }

        logger.info(
            f"[F7] ✅ Pago registrado: Journal {journal_id}, "
            f"Cuota #{cuota_numero}, Saldo: ${saldo_pendiente:,.0f}"
        )

        return {
            "success": True,
            "journal_id": journal_id,
            "loanbook_id": loanbook_id,
            "cuota_numero": cuota_numero,
            "saldo_pendiente": saldo_pendiente,
            "message": (
                f"✅ Pago cuota #{cuota_numero} registrado en Alegra. "
                f"Journal: {journal_id}. Saldo pendiente: ${saldo_pendiente:,.0f}"
            ),
            "result": result,
        }

    # ── Special case: registrar_nomina (F4 — Módulo Nómina Mensual) ───────────
    if action_type == "registrar_nomina":
        # PHASE 2 — F4: POST to /nomina/registrar endpoint
        # Validar campos obligatorios
        if not payload.get("mes") or not payload.get("mes").strip():
            return {
                "success": False,
                "error": "❌ mes es obligatorio (formato YYYY-MM, ej: 2026-01)"
            }
        if not payload.get("empleados") or len(payload.get("empleados", [])) == 0:
            return {
                "success": False,
                "error": "❌ empleados list no puede estar vacía"
            }

        logger.info(
            f"[F4] Registrar nómina {payload.get('mes')}: "
            f"{len(payload.get('empleados', []))} empleados"
        )

        # Call the /nomina/registrar endpoint directly
        try:
            result = await service.request("nomina/registrar", "POST", payload)
        except Exception as e:
            logger.error(f"[F4] POST a /nomina/registrar falló: {str(e)}")
            # Check if it's a 409 (duplicate)
            if "409" in str(e) or "ya registrada" in str(e):
                return {
                    "success": False,
                    "error": f"⚠️ Nómina de {payload.get('mes')} ya existe en el sistema"
                }
            return {
                "success": False,
                "error": f"❌ Error registrando nómina: {str(e)}"
            }

        # Verificar que la respuesta tiene success: True
        if not result.get("success"):
            logger.error(f"[F4] Endpoint retornó success=False: {result.get('error', 'Error desconocido')}")
            return {
                "success": False,
                "error": f"❌ Error registrando nómina: {result.get('error', result.get('mensaje'))}"
            }

        # Extraer IDs
        journal_id = result.get("journal_id")
        mes = result.get("mes")
        num_empleados = result.get("num_empleados")
        total_nomina = result.get("total_nomina")

        if not journal_id:
            logger.error(f"[F4] Respuesta no contiene journal_id: {result}")
            return {
                "success": False,
                "error": "❌ Nómina registrada pero sin journal_id de Alegra"
            }

        logger.info(
            f"[F4] ✅ Nómina {mes} registrada: Journal {journal_id}, "
            f"Total ${total_nomina:,.0f} ({num_empleados} empleados)"
        )

        return {
            "success": True,
            "journal_id": journal_id,
            "mes": mes,
            "num_empleados": num_empleados,
            "total_nomina": total_nomina,
            "message": (
                f"✅ Nómina {mes} registrada en Alegra. "
                f"Journal: {journal_id}. Total: ${total_nomina:,.0f} ({num_empleados} empleados)"
            ),
            "result": result,
        }

    # ── Special case: consultar_saldo_socio (F8 — CXC Socios en Tiempo Real) ──
    if action_type == "consultar_saldo_socio":
        # PHASE 2 — F8: GET /cxc/socios/saldo endpoint
        cedula = payload.get("cedula_socio", "").strip() if payload.get("cedula_socio") else None

        logger.info(f"[F8] Consultar saldo socio: {cedula or 'todos'}")

        try:
            result = await service.request(
                f"cxc/socios/saldo?cedula={cedula}" if cedula else "cxc/socios/saldo",
                "GET"
            )
        except Exception as e:
            logger.error(f"[F8] GET /cxc/socios/saldo falló: {str(e)}")
            return {
                "success": False,
                "error": f"❌ Error consultando saldo: {str(e)}"
            }

        # Verify response
        if not result or "saldo_pendiente" not in result and "socios" not in result:
            logger.error(f"[F8] Respuesta inválida: {result}")
            return {
                "success": False,
                "error": "❌ Respuesta inválida al consultar saldo"
            }

        logger.info(f"[F8] ✅ Saldo consultado exitosamente")

        return {
            "success": True,
            "result": result,
            "message": f"✅ Saldo consultado en tiempo real",
        }

    # ── Special case: registrar_abono_socio (F8 — CXC Socios) ─────────────────
    if action_type == "registrar_abono_socio":
        # PHASE 2 — F8: POST /cxc/socios/abono endpoint
        if not payload.get("cedula_socio") or not payload.get("cedula_socio").strip():
            return {
                "success": False,
                "error": "❌ cedula_socio es obligatoria"
            }
        if payload.get("monto_abono", 0) <= 0:
            return {
                "success": False,
                "error": "❌ monto_abono debe ser > 0"
            }

        logger.info(f"[F8] Registrar abono socio: ${payload.get('monto_abono')}")

        try:
            result = await service.request("cxc/socios/abono", "POST", payload)
        except Exception as e:
            logger.error(f"[F8] POST /cxc/socios/abono falló: {str(e)}")
            return {
                "success": False,
                "error": f"❌ Error registrando abono: {str(e)}"
            }

        # Verify response
        if not result.get("success"):
            logger.error(f"[F8] Endpoint retornó success=False: {result.get('error')}")
            return {
                "success": False,
                "error": f"❌ Error registrando abono: {result.get('error')}"
            }

        journal_id = result.get("journal_id")
        if not journal_id:
            logger.error(f"[F8] Respuesta sin journal_id: {result}")
            return {
                "success": False,
                "error": "❌ Abono registrado pero sin journal_id"
            }

        logger.info(f"[F8] ✅ Abono registrado: Journal {journal_id}")

        return {
            "success": True,
            "journal_id": journal_id,
            "cedula_socio": result.get("cedula_socio"),
            "nombre_socio": result.get("nombre_socio"),
            "monto_abono": result.get("monto_abono"),
            "saldo_nuevo": result.get("saldo_nuevo"),
            "message": (
                f"✅ Abono de ${result.get('monto_abono'):,.0f} registrado para "
                f"{result.get('nombre_socio')}. Saldo: ${result.get('saldo_nuevo'):,.0f}. "
                f"Journal: {journal_id}"
            ),
            "result": result,
        }

    # ── Special case: registrar_ingreso_no_operacional (F9 — Non-op Income) ────
    if action_type == "registrar_ingreso_no_operacional":
        # PHASE 2 — F9: POST /ingresos/no-operacional endpoint
        if not payload.get("tipo_ingreso") or not payload.get("tipo_ingreso").strip():
            return {
                "success": False,
                "error": "❌ tipo_ingreso es obligatorio"
            }
        if payload.get("monto", 0) <= 0:
            return {
                "success": False,
                "error": "❌ monto debe ser > 0"
            }
        if not payload.get("banco_destino") or not payload.get("banco_destino").strip():
            return {
                "success": False,
                "error": "❌ banco_destino es obligatorio"
            }

        logger.info(
            f"[F9] Registrar ingreso no operacional: {payload.get('tipo_ingreso')} - "
            f"${payload.get('monto'):,.0f}"
        )

        try:
            result = await service.request("ingresos/no-operacional", "POST", payload)
        except Exception as e:
            logger.error(f"[F9] POST /ingresos/no-operacional falló: {str(e)}")
            return {
                "success": False,
                "error": f"❌ Error registrando ingreso: {str(e)}"
            }

        # Verify response
        if not result.get("success"):
            logger.error(f"[F9] Endpoint retornó success=False: {result.get('error')}")
            return {
                "success": False,
                "error": f"❌ Error registrando ingreso: {result.get('error')}"
            }

        journal_id = result.get("journal_id")
        if not journal_id:
            logger.error(f"[F9] Respuesta sin journal_id: {result}")
            return {
                "success": False,
                "error": "❌ Ingreso registrado pero sin journal_id"
            }

        logger.info(f"[F9] ✅ Ingreso no operacional registrado: Journal {journal_id}")

        return {
            "success": True,
            "journal_id": journal_id,
            "tipo_ingreso": result.get("tipo_ingreso"),
            "monto": result.get("monto"),
            "banco_destino": result.get("banco_destino"),
            "message": (
                f"✅ Ingreso no operacional registrado. "
                f"Tipo: {result.get('tipo_ingreso')}. "
                f"Monto: ${result.get('monto'):,.0f}. "
                f"Journal: {journal_id}"
            ),
            "result": result,
        }

    # ── Special case: anular_causacion ────────────────────────────────────────
    if action_type == "anular_causacion":
        journal_id = payload.get("journal_id", "") or internal_metadata.get("journal_id", "")
        if not journal_id:
            raise ValueError("Falta journal_id para anular el asiento contable.")
        alegra_result = await service.request(f"journals/{journal_id}", "DELETE")
        return {
            "success": True,
            "result": alegra_result,
            "id": str(journal_id),
            "message": f"Asiento contable {journal_id} eliminado de Alegra.",
        }

    # ── Special case: cleanup_execute ─────────────────────────────────────────
    if action_type == "cleanup_execute":
        import asyncio as _asyncio
        from datetime import datetime as _dt, timezone as _tz
        import uuid as _uuid
        alegra_ids = payload.get("alegra_ids", [])
        if not alegra_ids:
            raise ValueError("Falta lista alegra_ids para la limpieza masiva de journals.")
        if len(alegra_ids) > 200:
            raise ValueError("Máximo 200 journals por operación de limpieza.")

        job_id = str(_uuid.uuid4())
        await db.gastos_cleanup_jobs.insert_one({
            "job_id":   job_id,
            "tipo":     "execute",
            "estado":   "en_progreso",
            "total":    len(alegra_ids),
            "ids_recibidos": list(alegra_ids),
            "inicio":   _dt.now(_tz.utc).isoformat(),
        })

        async def _do_cleanup(jid: str, ids: list):
            from alegra_service import AlegraService as _AS
            svc = _AS(db)
            eliminados_ok, eliminados_err = [], []
            for i, jrl_id in enumerate(ids):
                intentos = 0
                while intentos < 3:
                    try:
                        await svc.request(f"journals/{jrl_id}", "DELETE")
                        eliminados_ok.append(str(jrl_id))
                        break
                    except Exception as e:
                        intentos += 1
                        err_msg = str(e)
                        if intentos >= 3:
                            eliminados_err.append({"id": str(jrl_id), "error": err_msg})
                        else:
                            await _asyncio.sleep(3 * intentos)
                if (i + 1) % 10 == 0:
                    await _asyncio.sleep(1.0)

            # Guardar resultado REAL en MongoDB (nunca silencioso)
            fin = _dt.now(_tz.utc).isoformat()
            await db.gastos_cleanup_jobs.update_one(
                {"job_id": jid},
                {"$set": {
                    "estado":           "completado",
                    "eliminados":       len(eliminados_ok),
                    "errores":          len(eliminados_err),
                    "ids_eliminados":   eliminados_ok,
                    "detalle_errores":  eliminados_err,
                    "fin":              fin,
                }},
            )
            # Evento auditable en roddos_events
            await db.roddos_events.insert_one({
                "event_type":       "cleanup.journals.ejecutado",
                "job_id":           jid,
                "total_solicitado": len(ids),
                "eliminados":       len(eliminados_ok),
                "errores":          len(eliminados_err),
                "ids_eliminados":   eliminados_ok,
                "detalle_errores":  eliminados_err,
                "fecha":            fin,
            })

        _asyncio.create_task(_do_cleanup(job_id, list(alegra_ids)))
        return {
            "success":          True,
            "job_id":           job_id,
            "total_a_eliminar": len(alegra_ids),
            "message": (
                f"Eliminación iniciada en background para {len(alegra_ids)} journals. "
                f"El resultado real de Alegra se guarda en MongoDB. "
                f"Consulta el estado exacto con GET /api/gastos/cleanup-status/{job_id}"
            ),
            "aviso": "El número de journals efectivamente eliminados se confirmará al completar el job (puede tardar 1-3 minutos).",
        }

    # ── Special case: registrar_ingreso_manual ────────────────────────────────
    if action_type == "registrar_ingreso_manual":
        from routers.ingresos import IngresManualReq
        req = IngresManualReq(
            fecha         = payload.get("fecha", ""),
            tipo_ingreso  = payload.get("tipo_ingreso", ""),
            descripcion   = payload.get("descripcion", ""),
            monto         = float(payload.get("monto", 0)),
            tercero       = payload.get("tercero", ""),
            banco         = payload.get("banco", "Bancolombia"),
            referencia    = payload.get("referencia", ""),
        )
        from routers.ingresos import registrar_ingreso_manual
        result = await registrar_ingreso_manual(req, current_user=user)
        if not result.get("ok"):
            raise ValueError(result.get("error", "Error al registrar ingreso"))
        return {
            "success":  True,
            "result":   result,
            "id":       result.get("alegra_id", ""),
            "message":  result.get("mensaje", "Ingreso registrado en Alegra"),
        }

    # ── Special case: registrar_cxc_socio ────────────────────────────────────
    if action_type == "registrar_cxc_socio":
        from routers.cxc import CxcSocioReq, registrar_cxc_socio as _reg_cxc
        req = CxcSocioReq(
            fecha         = payload.get("fecha", ""),
            socio         = payload.get("socio", ""),
            descripcion   = payload.get("descripcion", ""),
            monto         = float(payload.get("monto", 0)),
            pagado_a      = payload.get("pagado_a", ""),
            banco_origen  = payload.get("banco_origen", "Bancolombia"),
        )
        result = await _reg_cxc(req, current_user=user)
        if not result.get("ok"):
            raise ValueError(result.get("error", "Error al registrar CXC"))
        return {
            "success": True, "result": result,
            "id": result.get("alegra_id", ""),
            "message": result.get("mensaje", "CXC socio registrada"),
        }

    # ── Special case: abonar_cxc_socio ───────────────────────────────────────
    if action_type == "abonar_cxc_socio":
        from routers.cxc import AbonoSocioReq, abonar_cxc_socio as _abo_cxc
        req = AbonoSocioReq(
            socio          = payload.get("socio", ""),
            monto          = float(payload.get("monto", 0)),
            fecha          = payload.get("fecha", ""),
            banco_destino  = payload.get("banco_destino", "Bancolombia"),
            descripcion    = payload.get("descripcion", ""),
            cxc_id         = payload.get("cxc_id", ""),
        )
        result = await _abo_cxc(req, current_user=user)
        return {
            "success": True, "result": result,
            "id": result.get("alegra_id", ""),
            "message": result.get("mensaje", "Abono registrado"),
        }

    # ── Special case: consultar_cxc_socios ───────────────────────────────────
    if action_type == "consultar_cxc_socios":
        socio = payload.get("socio", "")
        if socio:
            from routers.cxc import get_saldo_socio
            result = await get_saldo_socio(socio, current_user=user)
        else:
            from routers.cxc import resumen_cxc_socios
            result = await resumen_cxc_socios(current_user=user)
        return {"success": True, "result": result, "message": "Saldo CXC socios consultado"}

    # ── Special case: consultar_ingresos ─────────────────────────────────────
    if action_type == "consultar_ingresos":
        from routers.ingresos import get_historial_ingresos
        result = await get_historial_ingresos(
            fecha_desde = payload.get("fecha_desde", ""),
            fecha_hasta = payload.get("fecha_hasta", ""),
            tipo        = payload.get("tipo", ""),
            current_user = user,
        )
        return {"success": True, "result": result, "message": "Historial de ingresos consultado"}

    # ── Special case: registrar_cxc_cliente ──────────────────────────────────
    if action_type == "registrar_cxc_cliente":
        from routers.cxc import CxcClienteReq, registrar_cxc_cliente as _reg_cxc_cli
        req = CxcClienteReq(
            fecha        = payload.get("fecha", ""),
            cliente      = payload.get("cliente", ""),
            nit_cliente  = payload.get("nit_cliente", ""),
            descripcion  = payload.get("descripcion", ""),
            monto        = float(payload.get("monto", 0)),
            vencimiento  = payload.get("vencimiento", ""),
            referencia   = payload.get("referencia", ""),
        )
        result = await _reg_cxc_cli(req, current_user=user)
        return {
            "success": True, "result": result,
            "id": result.get("alegra_id", ""),
            "message": result.get("mensaje", "CXC cliente registrada"),
        }

    # ── Special case: crear_comprobante_ingreso / crear_comprobante_egreso ────
    if action_type in ("crear_comprobante_ingreso", "crear_comprobante_egreso"):        # Map to journals endpoint (Alegra uses journal-entries for comprobantes)
        comprobante_result = await service.request("journals", "POST", payload)
        from post_action_sync import post_action_sync
        sync_result = await post_action_sync(action_type, comprobante_result, payload, db, user)
        return {
            "success": True,
            "result": comprobante_result,
            "id": str(comprobante_result.get("id", "")),
            "message": f"Comprobante {'de ingreso' if 'ingreso' in action_type else 'de egreso'} registrado",
            "sync": sync_result,
        }

    # ── Special case: anular_factura_compra ───────────────────────────────────
    if action_type == "anular_factura_compra":
        bill_id     = payload.get("bill_id", "")
        bill_numero = payload.get("bill_numero", "") or internal_metadata.get("bill_numero", "")
        proveedor   = payload.get("proveedor_nombre", "") or internal_metadata.get("proveedor_nombre", "")

        if not bill_id:
            raise ValueError("Falta bill_id para anular la factura de compra.")

        # Guard: check motos linked to this bill
        motos_bloqueadas = await db.inventario_motos.find(
            {"factura_compra_alegra_id": bill_id,
             "estado": {"$in": ["Vendida", "Entregada"]}},
            {"_id": 0, "chasis": 1, "marca": 1, "version": 1, "estado": 1},
        ).to_list(10)

        if motos_bloqueadas:
            detalle = ", ".join(
                f"chasis {m.get('chasis') or m.get('marca','')+' '+m.get('version','')} ({m.get('estado')})"
                for m in motos_bloqueadas
            )
            raise ValueError(
                f"❌ No se puede anular la factura {bill_numero}. "
                f"La(s) siguiente(s) moto(s) vinculadas ya fueron vendidas/entregadas: {detalle}. "
                "Resuelve primero esas ventas antes de anular la compra."
            )

        # Execute: DELETE /bills/{id} in Alegra
        alegra_result = await service.request(f"bills/{bill_id}", "DELETE")

        # Post-action sync
        from post_action_sync import post_action_sync
        sync_result = await post_action_sync(
            "anular_factura_compra",
            {"id": bill_id, "numero": bill_numero, "proveedor": proveedor},
            payload,
            db,
            user,
            metadata=internal_metadata,
        )
        return {
            "success": True,
            "result": alegra_result,
            "id": bill_id,
            "message": f"Factura {bill_numero} anulada en Alegra",
            "sync": sync_result,
        }

    # ── Special case: registrar_loanbook ─────────────────────────────────────
    if action_type == "registrar_loanbook":
        from utils.loanbook_constants import (
            calcular_cuota_valor as _calc_cuota,
            resumen_cuota as _resumen_cuota,
            MODOS_VALIDOS as _MODOS_VALIDOS,
        )
        # Validar modo_pago
        modo_pago = payload.get("modo_pago", "semanal")
        if modo_pago not in _MODOS_VALIDOS:
            return {
                "success": False,
                "message": f"modo_pago inválido: '{modo_pago}'. Debe ser uno de: {sorted(_MODOS_VALIDOS)}",
            }
        cuota_base = int(payload.get("cuota_base") or payload.get("valor_cuota") or 0)
        if cuota_base <= 0:
            return {"success": False, "message": "cuota_base o valor_cuota requerido y > 0."}

        cuota_valor = _calc_cuota(cuota_base, modo_pago)
        resumen = _resumen_cuota(cuota_base, modo_pago)

        # Si solo es preview (dry_run=True), retornar el resumen sin crear
        if payload.get("dry_run"):
            return {
                "success": True,
                "preview": True,
                "cuota_base": cuota_base,
                "cuota_valor": cuota_valor,
                "modo_pago": modo_pago,
                "resumen": resumen,
                "message": f"Resumen de cuota calculada: {resumen}",
            }

        # Crear el loanbook directamente en MongoDB
        from routers.loanbook import PLAN_CUOTAS, _get_next_codigo, _first_wednesday
        from services.crm_service import normalizar_telefono as _norm_tel
        import math as _math
        from datetime import date as _date

        plan = payload.get("plan", "P52S")
        if plan not in PLAN_CUOTAS:
            return {"success": False, "message": f"Plan inválido: '{plan}'. Opciones: {list(PLAN_CUOTAS.keys())}"}

        codigo = await _get_next_codigo()
        num_cuotas = PLAN_CUOTAS[plan]
        precio_venta = float(payload.get("precio_venta", 0))
        cuota_inicial = float(payload.get("cuota_inicial", 0))
        valor_financiado = precio_venta - cuota_inicial

        cuota_0 = {
            "numero": 0, "tipo": "inicial",
            "fecha_vencimiento": payload.get("fecha_factura", _date.today().isoformat()),
            "valor": cuota_inicial, "estado": "pendiente",
            "fecha_pago": None, "valor_pagado": 0.0,
            "alegra_payment_id": None, "comprobante": None, "notas": "",
        }

        doc = {
            "id": str(uuid.uuid4()),
            "codigo": codigo,
            "factura_alegra_id": payload.get("factura_alegra_id"),
            "factura_numero": payload.get("factura_numero"),
            "moto_id": payload.get("moto_id"),
            "moto_descripcion": payload.get("moto_descripcion", ""),
            "cliente_id": payload.get("cliente_id"),
            "cliente_nombre": payload.get("cliente_nombre", ""),
            "cliente_nit": payload.get("cliente_nit", ""),
            "cliente_telefono": _norm_tel(payload.get("cliente_telefono", "")),
            "plan": plan,
            "fecha_factura": payload.get("fecha_factura", _date.today().isoformat()),
            "fecha_entrega": None,
            "fecha_primer_pago": None,
            "precio_venta": precio_venta,
            "cuota_inicial": cuota_inicial,
            "valor_financiado": valor_financiado,
            "num_cuotas": num_cuotas,
            "modo_pago": modo_pago,
            "cuota_base": cuota_base,
            "valor_cuota": cuota_valor,
            "cuota_valor": cuota_valor,
            "cuotas": [cuota_0],
            "estado": "pendiente_entrega",
            "num_cuotas_pagadas": 0,
            "num_cuotas_vencidas": 0,
            "total_cobrado": 0.0,
            "saldo_pendiente": valor_financiado,
            "ai_suggested": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.get("email", "agente"),
        }
        await db.loanbook.insert_one(doc)
        doc.pop("_id", None)
        return {
            "success": True,
            "result": doc,
            "codigo": codigo,
            "cuota_valor": cuota_valor,
            "resumen": resumen,
            "message": (
                f"Loanbook {codigo} creado — cliente: {doc['cliente_nombre']} | "
                f"Plan: {plan} | {resumen}"
            ),
        }

    # ── Special case: cargar_loanbooks_lote ──────────────────────────────────
    if action_type == "cargar_loanbooks_lote":
        import math as _math
        from datetime import date as _date, timedelta as _td

        # ── Constantes internas ───────────────────────────────────────────────
        _PLAN_CUOTAS = {"P26S": 26, "P39S": 39, "P52S": 52, "P78S": 78}
        _MULT = {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.33}
        _DIAS = {"semanal": 7,   "quincenal": 14,  "mensual": 28}

        def _first_wed(d: _date) -> _date:
            """Primer miércoles >= (d + 7 días)."""
            target = d + _td(days=7)
            wd = target.weekday()  # 0=Mon … 6=Sun
            if wd == 2:   return target
            if wd < 2:    return target + _td(days=2 - wd)
            return target + _td(days=9 - wd)

        # ── Obtener máximo código existente para continuar secuencia ──────────
        year = datetime.now(timezone.utc).year
        last = await db.loanbook.find_one(
            {"codigo": {"$regex": f"^LB-{year}-"}},
            {"codigo": 1},
            sort=[("codigo", -1)],
        )
        seq_start = 1
        if last:
            try:
                seq_start = int(last["codigo"].split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq_start = await db.loanbook.count_documents({}) + 1

        loans_input = payload.get("loanbooks", payload.get("loans", []))
        if not loans_input:
            return {"success": False, "message": "No se recibió ningún loanbook en el payload (key: 'loanbooks')."}
        if len(loans_input) > 200:
            return {"success": False, "message": "Máximo 200 loanbooks por lote."}

        insertados  = 0
        actualizados = 0
        codigos: list[str] = []
        errores: list[dict] = []

        for idx, lb in enumerate(loans_input):
            # ── Validaciones ──────────────────────────────────────────────────
            chasis = str(lb.get("moto_chasis") or lb.get("vin") or "").strip().upper()
            if not chasis:
                errores.append({"idx": idx, "error": "moto_chasis/vin requerido"})
                continue

            cliente = str(lb.get("cliente_nombre") or "").strip()
            cedula  = str(lb.get("cliente_cedula") or "").strip()
            motor   = str(lb.get("moto_motor") or "").strip().upper()
            ref     = str(lb.get("moto_referencia") or lb.get("modelo") or "").strip()
            color   = str(lb.get("moto_color") or "").strip()
            plan    = str(lb.get("plan") or "P52S").strip().upper()
            modo    = str(lb.get("modo_pago") or "semanal").strip().lower()

            if not cliente:
                errores.append({"idx": idx, "chasis": chasis, "error": "cliente_nombre requerido"})
                continue
            if plan not in _PLAN_CUOTAS:
                errores.append({"idx": idx, "chasis": chasis, "error": f"plan inválido: {plan}"})
                continue
            if modo not in _MULT:
                modo = "semanal"

            try:
                valor_total   = float(lb.get("valor_total") or 0)
                cuota_inicial = float(lb.get("cuota_inicial") or 0)
                cuota_base    = int(lb.get("cuota_base") or 0)
                cuotas_pagadas = int(lb.get("cuotas_pagadas") or 0)
                fecha_fac_str  = str(lb.get("fecha_factura") or _date.today().isoformat())
                fecha_ent_str  = str(lb.get("fecha_entrega")  or _date.today().isoformat())
                fecha_entrega  = _date.fromisoformat(fecha_ent_str[:10])
            except Exception as ve:
                errores.append({"idx": idx, "chasis": chasis, "error": f"Error en campos numéricos/fecha: {ve}"})
                continue

            if cuota_base <= 0:
                errores.append({"idx": idx, "chasis": chasis, "error": "cuota_base debe ser > 0"})
                continue

            # ── Cálculos ──────────────────────────────────────────────────────
            num_cuotas     = _PLAN_CUOTAS[plan]
            cuota_valor    = _math.ceil(cuota_base * _MULT[modo])
            intervalo_dias = _DIAS[modo]
            saldo_pendiente = max(0.0, valor_total - cuota_inicial - (cuota_base * cuotas_pagadas))
            fecha_primer_pago = _first_wed(fecha_entrega)
            codigo = f"LB-{year}-{str(seq_start + idx):>04}"

            # ── Cuotas schedule ───────────────────────────────────────────────
            cuotas: list[dict] = [{
                "numero": 0, "tipo": "inicial",
                "fecha_vencimiento": fecha_fac_str[:10],
                "valor": cuota_inicial,
                "estado": "pagada" if cuota_inicial > 0 else "pendiente",
                "fecha_pago": fecha_fac_str[:10] if cuota_inicial > 0 else None,
                "valor_pagado": cuota_inicial if cuota_inicial > 0 else 0.0,
                "alegra_payment_id": None, "comprobante": None, "notas": "",
            }]
            for i in range(1, num_cuotas + 1):
                fecha_c = fecha_primer_pago + _td(days=intervalo_dias * (i - 1))
                fv_str  = fecha_c.isoformat()
                hoy_str = _date.today().isoformat()
                if i <= cuotas_pagadas:
                    estado_c = "pagada"
                elif fv_str < hoy_str:
                    estado_c = "vencida"
                else:
                    estado_c = "pendiente"
                cuotas.append({
                    "numero": i, "tipo": modo,
                    "fecha_vencimiento": fv_str,
                    "valor": cuota_valor,
                    "estado": estado_c,
                    "fecha_pago": fv_str if estado_c == "pagada" else None,
                    "valor_pagado": cuota_valor if estado_c == "pagada" else 0.0,
                    "alegra_payment_id": None, "comprobante": None, "notas": "",
                })

            estado_lb = str(lb.get("estado") or "activo").strip().lower()
            if estado_lb not in ("activo", "mora", "completado", "pendiente_entrega"):
                estado_lb = "activo"

            doc = {
                "codigo":            codigo,
                "cliente_nombre":    cliente,
                "cliente_cedula":    cedula,
                "cliente_tipo_doc":  str(lb.get("cliente_tipo_doc") or "CC").strip().upper(),
                "cliente_telefono":  str(lb.get("cliente_telefono") or "").strip(),
                "moto_chasis":       chasis,
                "moto_motor":        motor,
                "moto_referencia":   ref,
                "moto_color":        color,
                "moto_placa":        str(lb.get("moto_placa") or "").strip() or None,
                "plan":              plan,
                "modo_pago":         modo,
                "cuota_base":        cuota_base,
                "valor_cuota":       cuota_valor,
                "cuota_valor":       cuota_valor,
                "valor_total":       valor_total,
                "cuota_inicial":     cuota_inicial,
                "num_cuotas":        num_cuotas,
                "cuotas_pagadas":    cuotas_pagadas,
                "saldo_pendiente":   saldo_pendiente,
                "fecha_factura":     fecha_fac_str[:10],
                "fecha_entrega":     fecha_ent_str[:10],
                "fecha_primer_pago": fecha_primer_pago.isoformat(),
                "cuotas":            cuotas,
                "estado":            estado_lb,
                "num_cuotas_pagadas":  cuotas_pagadas,
                "num_cuotas_vencidas": sum(1 for c in cuotas if c["estado"] == "vencida"),
                "total_cobrado":     cuota_base * cuotas_pagadas,
                "datos_completos":   True,
                "ai_suggested":      True,
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            }

            try:
                res = await db.loanbook.update_one(
                    {"moto_chasis": chasis},
                    {"$set": doc, "$setOnInsert": {
                        "id":         str(uuid.uuid4()),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                if res.upserted_id:
                    insertados += 1
                else:
                    actualizados += 1
                codigos.append(codigo)
            except Exception as e:
                errores.append({"chasis": chasis, "error": str(e)})

        total = insertados + actualizados

        # ── Registrar evento ──────────────────────────────────────────────────
        if total > 0:
            try:
                await db.roddos_events.insert_one({
                    "id":          str(uuid.uuid4()),
                    "event_type":  "loanbook.carga_masiva",
                    "entity_type": "loanbook",
                    "insertados":  insertados,
                    "actualizados": actualizados,
                    "total":       total,
                    "codigos":     codigos,
                    "actor":       user.get("email", "agente"),
                    "timestamp":   datetime.now(timezone.utc).isoformat(),
                    "estado":      "processed",
                })
            except Exception:
                pass

        msg = f"Lote procesado: {insertados} loanbooks insertados, {actualizados} actualizados"
        if errores:
            msg += f", {len(errores)} errores"
        return {
            "success": total > 0 or len(errores) == 0,
            "insertados":      insertados,
            "actualizados":    actualizados,
            "total_procesados": total,
            "codigos":         codigos,
            "errores":         errores,
            "message":         msg,
        }

    # ── Special case: cargar_inventario_motos_lote ───────────────────────────
    if action_type == "cargar_inventario_motos_lote":
        from datetime import date as _date
        motos_input = payload.get("motos", [])
        if not motos_input:
            return {"success": False, "message": "No se recibió ninguna moto en el payload."}
        if len(motos_input) > 200:
            return {"success": False, "message": "Máximo 200 motos por lote."}

        hoy = _date.today().isoformat()
        insertados = 0
        actualizados = 0
        errores = []

        for m in motos_input:
            # FIX: estandarizar a 'chasis' — acepta 'vin' o 'chasis' como alias
            chasis = (
                str(m.get("chasis") or m.get("vin") or "").strip().upper()
            )
            if not chasis:
                errores.append({"moto": m.get("modelo", "?"), "error": "chasis requerido"})
                continue

            doc = {
                "chasis":         chasis,
                "motor":          str(m.get("motor", "") or "").strip().upper(),
                "marca":          str(m.get("marca", "TVS") or "TVS").strip(),
                "referencia":     str(m.get("modelo", "") or m.get("version", "") or "").strip(),
                "color":          str(m.get("color", "") or "").strip(),
                "año":            int(m.get("año", m.get("ano_modelo", 0)) or 0),
                "estado":         str(m.get("estado", "Disponible") or "Disponible").strip(),
                "precio_costo":   float(m.get("costo", m.get("precio_costo", 0)) or 0),
                "factura_compra": str(m.get("factura_compra", m.get("factura_no", "")) or "").strip(),
                "placa":          str(m.get("placa", "") or "").strip() or None,
                "fecha_ingreso":  hoy,
                "updated_at":     datetime.now(timezone.utc).isoformat(),
            }

            try:
                result = await db.inventario_motos.update_one(
                    {"chasis": chasis},
                    {"$set": doc, "$setOnInsert": {
                        "id":         str(uuid.uuid4()),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                if result.upserted_id:
                    insertados += 1
                else:
                    actualizados += 1
            except Exception as e:
                errores.append({"chasis": chasis, "error": str(e)})

        total = insertados + actualizados
        msg = (
            f"Lote procesado: {insertados} motos insertadas, {actualizados} actualizadas"
            + (f", {len(errores)} errores." if errores else ".")
        )
        return {
            "success": total > 0,
            "insertados": insertados,
            "actualizados": actualizados,
            "total_procesadas": total,
            "errores": errores,
            "message": msg,
        }

    # ── Special case: sincronizar_inventario_loanbooks ─────────────────────
    if action_type == "sincronizar_inventario_loanbooks":
        now = datetime.now(timezone.utc).isoformat()
        cambios = []
        errores_sinc = []

        loanbooks = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]},
             "moto_chasis": {"$exists": True, "$ne": None}},
            {"_id": 0, "codigo": 1, "cliente_nombre": 1, "moto_chasis": 1, "estado": 1}
        ).to_list(1000)

        for lb in loanbooks:
            chasis_lb = lb.get("moto_chasis")
            if not chasis_lb:
                continue
            estado_correcto = "Entregada" if lb["estado"] in ("activo", "mora") else "Vendida"
            moto = await db.inventario_motos.find_one(
                {"$or": [{"chasis": chasis_lb}, {"vin": chasis_lb}]},
                {"_id": 0, "chasis": 1, "vin": 1, "estado": 1}
            )
            if not moto:
                errores_sinc.append({"loanbook": lb["codigo"], "chasis": chasis_lb, "error": "Moto no encontrada"})
                continue
            estado_actual = moto.get("estado", "")
            if estado_actual != estado_correcto:
                campo = "chasis" if moto.get("chasis") else "vin"
                await db.inventario_motos.update_one(
                    {campo: chasis_lb},
                    {"$set": {"estado": estado_correcto, "loanbook_codigo": lb["codigo"], "updated_at": now}}
                )
                cambios.append({
                    "chasis": chasis_lb, "cliente": lb["cliente_nombre"],
                    "estado_antes": estado_actual, "estado_ahora": estado_correcto,
                    "loanbook": lb["codigo"]
                })

        await db.roddos_events.insert_one({
            "event_type": "inventario.estados.sincronizados", "source": "agente_contador",
            "timestamp": now, "datos": {"cambios": len(cambios), "errores": len(errores_sinc)}
        })

        n = len(cambios)
        msg = f"Sincronización completada: {n} estado(s) corregido(s)."
        if cambios:
            detalles = "\n".join([f"• {c['chasis']} ({c['cliente']}): {c['estado_antes']} → {c['estado_ahora']}" for c in cambios])
            msg += f"\n\n{detalles}"
        else:
            msg += " ✅ Todos los estados ya estaban correctos."
        if errores_sinc:
            msg += f"\n\n⚠️ {len(errores_sinc)} motos no encontradas en inventario."

        return {"success": True, "cambios": n, "message": msg}

    if action_type not in ACTION_MAP:
        raise ValueError(f"Acción no reconocida: {action_type}")

    endpoint, method = ACTION_MAP[action_type]

    # ── CREAR_CONTACTO: handle _next_action and internal fields ──────────────
    if action_type == "crear_contacto":
        import json as _json
        next_action = payload.pop("_next_action", None)
        # Remove internal display-only fields before sending to Alegra
        payload.pop("accounting_account_suggested", None)
        payload.pop("accounting_account_name", None)
        # Ensure nameObject.lastName is never empty (Alegra Colombia requires it)
        name_obj = payload.get("nameObject")
        if isinstance(name_obj, dict) and not name_obj.get("lastName"):
            full_name = name_obj.get("firstName", "") or payload.get("name", "")
            parts = full_name.strip().split(" ", 1)
            name_obj["firstName"] = parts[0]
            name_obj["lastName"] = parts[1] if len(parts) > 1 else "."
        # Note: keep 'name' and 'nameObject' - both are used by Alegra

        result = await service.request(endpoint, method, payload)
        # Check if Alegra returned an error in the body (200 with error code)
        if isinstance(result, dict) and result.get("code") and not result.get("id"):
            err_msg = result.get("message", "Error al crear el contacto en Alegra")
            raise HTTPException(status_code=400, detail=f"Alegra: {err_msg} (código {result.get('code')})")
        new_contact_id = str(result.get("id", "")) if isinstance(result, dict) else ""
        contact_name = ""
        if isinstance(result, dict):
            no = result.get("nameObject") or {}
            contact_name = f"{no.get('firstName','')} {no.get('lastName','')}".strip() or result.get("name", "")

        # Replace placeholder in next_action payload with real ID
        if next_action and new_contact_id:
            next_str = _json.dumps(next_action)
            next_str = next_str.replace('"__NEW_CONTACT_ID__"', new_contact_id)
            next_str = next_str.replace("__NEW_CONTACT_ID__", new_contact_id)
            next_action = _json.loads(next_str)

        return {
            "success": True,
            "result": result,
            "id": new_contact_id,
            "message": f"Tercero '{contact_name}' creado exitosamente en Alegra",
            "sync": {},
            **({"next_pending_action": next_action} if next_action else {}),
        }

    # ── CREAR_CAUSACION: validate entry IDs and translate if needed ──────────
    if action_type == "crear_causacion":
        entries = payload.get("entries", [])
        normalized = [
            {
                "id":     e["id"],
                "debit":  e.get("debit", 0),
                "credit": e.get("credit", 0),
                "_name":  e.get("name", ""),
            }
            for e in entries
        ]

        # Translate invalid IDs → real Alegra IDs using roddos_cuentas (fast)
        if not await service.is_demo_mode():
            try:
                roddos = await db.roddos_cuentas.find(
                    {}, {"_id": 0, "alegra_id": 1, "nombre": 1, "palabras_clave": 1}
                ).to_list(200)
                valid_ids = {str(r["alegra_id"]) for r in roddos}
                name_to_id = {r["nombre"].lower(): str(r["alegra_id"]) for r in roddos}
                # Also index palabras_clave for fuzzy match
                kw_to_id: dict[str, str] = {}
                for r in roddos:
                    for kw in r.get("palabras_clave", []):
                        kw_to_id[kw.lower()] = str(r["alegra_id"])

                for entry in normalized:
                    if str(entry["id"]) not in valid_ids:
                        entry_name = (entry.get("_name") or "").lower().strip()
                        matched = False
                        if entry_name:
                            # 1. Exact name match
                            if entry_name in name_to_id:
                                entry["id"] = int(name_to_id[entry_name])
                                matched = True
                            # 2. Keywords match
                            if not matched:
                                for kw, kid in kw_to_id.items():
                                    if kw in entry_name:
                                        entry["id"] = int(kid)
                                        matched = True
                                        break
                            # 3. Partial name match
                            if not matched:
                                words = [w for w in entry_name.split() if len(w) > 3]
                                for rname, rid in name_to_id.items():
                                    if all(w in rname for w in words[:2]):
                                        entry["id"] = int(rid)
                                        break

                        if not matched and str(entry["id"]) not in valid_ids:
                            # Final fallback: Alegra /categories
                            try:
                                cats = await service.request("categories")
                                cat_ids: set = set()
                                cat_name_map: dict = {}
                                def _scan(items: list) -> None:
                                    for item in items:
                                        cat_ids.add(str(item["id"]))
                                        cat_name_map[(item.get("name") or "").lower()] = str(item["id"])
                                        for child in item.get("children", []):
                                            _scan([child])
                                _scan(cats if isinstance(cats, list) else [])
                                if entry_name in cat_name_map:
                                    entry["id"] = int(cat_name_map[entry_name])
                            except Exception:
                                pass
            except Exception as lookup_err:
                        print(f"[causacion] ID translation: {lookup_err}")

        # Final normalization: strip helper _name
        payload["entries"] = [
            {"id": e["id"], "debit": e["debit"], "credit": e["credit"]}
            for e in normalized
        ]

    endpoint, method = ACTION_MAP[action_type]

    # ── Guard: prevent double-selling same moto ───────────────────────────────
    if action_type == "crear_factura_venta":
        moto_id   = internal_metadata.get("moto_id", "")
        moto_chas = internal_metadata.get("moto_chasis", "")
        moto_desc = internal_metadata.get("moto_descripcion", "")

        if moto_id or moto_chas:
            query = {"id": moto_id} if moto_id else {"chasis": moto_chas}
            moto = await db.inventario_motos.find_one(
                query,
                {"_id": 0, "estado": 1, "chasis": 1, "marca": 1, "version": 1,
                 "factura_numero": 1, "fecha_venta": 1, "cliente_nombre": 1},
            )
            if not moto:
                raise ValueError(
                    f"❌ No encontré la moto con {'chasis' if moto_chas else 'ID'} "
                    f"'{moto_chas or moto_id}' en el inventario. "
                    "Verifica el chasis o registra la entrada de esa unidad primero."
                )
            estado = moto.get("estado", "")
            if estado not in ("Disponible", None, ""):
                detalle = ""
                if estado == "Vendida":
                    fv = moto.get("factura_numero", "")
                    fecha = moto.get("fecha_venta", "")
                    cli   = moto.get("cliente_nombre", "")
                    detalle = (
                        f" Vinculada a factura {fv} del {fecha}"
                        f"{(' — ' + cli) if cli else ''}."
                    )
                raise ValueError(
                    f"❌ La moto {moto_chas or moto_id} tiene estado '{estado}'. "
                    f"No se puede facturar.{detalle}"
                )

        elif moto_desc:
            # Generic sale by model — verify stock exists
            partes = (moto_desc or "").split()
            marca_q = partes[0] if partes else ""
            disponibles = await db.inventario_motos.count_documents(
                {"estado": "Disponible", **({"marca": {"$regex": marca_q, "$options": "i"}} if marca_q else {})}
            )
            if disponibles == 0:
                raise ValueError(
                    f"❌ No hay unidades disponibles de {moto_desc}. "
                    "Registra una compra primero para agregar unidades al inventario."
                )

    result = await service.request(endpoint, method, payload)

    # POST ACTION SYNC — updates internal modules and emits events
    from post_action_sync import post_action_sync
    sync_result = await post_action_sync(
        action_type,
        result if isinstance(result, dict) else {},
        payload,
        db,
        user,
        metadata=internal_metadata,
    )

    if isinstance(result, dict):
        doc_id = result.get("id") or result.get("number") or ""
    elif isinstance(result, list) and result:
        doc_id = result[0].get("id") if isinstance(result[0], dict) else ""
    else:
        doc_id = ""

    # agent_memory.save_pattern() — guarda patrón cuando el usuario confirma
    await save_action_pattern(db, user, action_type, payload)

    return {
        "success": True,
        "result": result,
        "id": doc_id,
        "message": "Ejecutado en Alegra exitosamente",
        "sync": sync_result,
    }
