"""
init_mongodb_sismo.py — Fuente unica de verdad para MongoDB en SISMO / RODDOS S.A.S.

Uso:
    MONGO_URL="mongodb+srv://..." DB_NAME="sismo" python init_mongodb_sismo.py

Crea TODAS las colecciones (30+), indices (ESR, TTL, parciales, unicos) y datos
semilla (catalogo_planes, plan_cuentas_roddos, sismo_knowledge, usuarios, etc.).

Script completamente idempotente: ejecutar dos veces produce resultados identicos
sin errores. Usa create_index (idempotente por diseno) y upsert para seed data.

Tambien expone init_all(db) como callable para tests.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME   = os.environ.get("DB_NAME", "sismo")

# ─────────────────────────────────────────────────────────────────────────────
# COLECCIONES — 30+ colecciones que conforman SISMO
# ─────────────────────────────────────────────────────────────────────────────

COLLECTIONS = [
    # Core usuarios y autenticacion
    "users",
    "alegra_credentials",
    "user_settings",

    # Chat y agentes IA
    "chat_messages",
    "cfo_chat_historia",
    "agent_memory",
    "agent_pending_topics",

    # Loanbook y cartera
    "loanbook",
    "cartera_pagos",
    "inventario_motos",
    "catalogo_motos",
    "catalogo_planes",

    # Conciliacion bancaria
    "conciliacion_extractos_procesados",
    "conciliacion_movimientos_procesados",
    "conciliacion_reintentos",

    # Contabilidad y gastos
    "plan_cuentas_roddos",
    "ingresos_registrados",
    "iva_config",

    # Proveedores y configuracion
    "proveedores_config",
    "cfo_config",

    # CFO y reportes
    "cfo_informes",
    "cfo_alertas",
    "cfo_instrucciones",
    "cfo_compromisos",
    "audit_log",
    "audit_logs",

    # CXC (cuentas por cobrar)
    "cxc_socios",
    "cxc_clientes",

    # Bus de eventos
    "roddos_events",
    "roddos_events_dlq",

    # Analitica y reportes pre-calculados (Phase 4)
    "portfolio_summaries",
    "financial_reports",

    # RAG base de conocimiento
    "sismo_knowledge",

    # Notificaciones
    "notifications",
]


# ─────────────────────────────────────────────────────────────────────────────
# INDICES — definiciones completas por coleccion
# ─────────────────────────────────────────────────────────────────────────────

def _safe_index(collection, keys, **kwargs):
    """create_index with automatic drop+recreate on name conflict.

    pymongo's create_index is idempotent ONLY if the index name matches.
    If the same key pattern exists with a different name (e.g. auto-generated
    'field_1_field2_1' vs our custom name), it raises OperationFailure.
    This helper catches that, drops the conflicting index, and retries.
    """
    from pymongo.errors import OperationFailure
    try:
        collection.create_index(keys, **kwargs)
    except OperationFailure as e:
        if "already exists with a different name" in str(e) or e.code == 85:
            # Find and drop the conflicting index by key pattern
            target_keys = list(keys) if not isinstance(keys, list) else keys
            for idx in collection.list_indexes():
                if idx.get("key") and list(idx["key"].items()) == target_keys and idx["name"] != kwargs.get("name"):
                    collection.drop_index(idx["name"])
                    break
            else:
                # Fallback: drop by the name pymongo reports
                name = kwargs.get("name")
                if name:
                    try:
                        collection.drop_index(name)
                    except OperationFailure:
                        pass
            # Retry
            collection.create_index(keys, **kwargs)
        else:
            raise


def _create_indexes(db):
    """Crea todos los indices. Usa _safe_index para manejar conflictos de nombre."""
    from pymongo import ASCENDING as ASC, DESCENDING as DESC

    total_indexes = 0

    # ── users ──────────────────────────────────────────────────────────────
    _safe_index(db.users, [("email", ASC)], unique=True, name="users_email_unique")
    total_indexes += 1

    # ── chat_messages ───────────────────────────────────────────────────────
    _safe_index(db.chat_messages, [("session_id", ASC), ("timestamp", ASC)],
                                   name="chat_session_ts")
    _safe_index(db.chat_messages, [("session_id", ASC), ("timestamp", DESC)],
                                   name="chat_session_ts_desc")
    total_indexes += 2

    # ── cfo_chat_historia ───────────────────────────────────────────────────
    _safe_index(db.cfo_chat_historia, [("session_id", ASC), ("ts", ASC)],
                                       name="cfo_chat_session_ts")
    total_indexes += 1

    # ── agent_memory ────────────────────────────────────────────────────────
    _safe_index(db.agent_memory, [("user_id", ASC), ("tipo", ASC)],
                                  name="agent_memory_user_tipo")
    _safe_index(db.agent_memory, [("frecuencia_count", DESC)],
                                  name="agent_memory_freq")
    _safe_index(db.agent_memory, [("ultima_ejecucion", DESC)],
                                  name="agent_memory_ultima_ej")
    total_indexes += 3

    # ── agent_pending_topics ─────────────────────────────────────────────────
    _safe_index(db.agent_pending_topics, [("user_id", ASC), ("estado", ASC)],
                                          name="pending_topics_user_estado")
    _safe_index(db.agent_pending_topics, [("user_id", ASC), ("topic_key", ASC)],
                                          name="pending_topics_user_topic")
    # TTL: documentos auto-eliminados al vencer expires_at (expireAfterSeconds=0
    # significa que se usa el valor del campo como timestamp de expiracion)
    try:
        _safe_index(db.agent_pending_topics, 
            [("expires_at", ASC)],
            expireAfterSeconds=0,
            name="ttl_pending_topics",
        )
        total_indexes += 1
    except Exception:
        pass  # El indice TTL ya existe
    total_indexes += 2

    # ── audit_log / audit_logs ───────────────────────────────────────────────
    _safe_index(db.audit_log, [("timestamp", DESC)], name="audit_log_ts")
    _safe_index(db.audit_logs, [("timestamp", DESC)], name="audit_logs_ts")
    _safe_index(db.audit_logs, [("user_email", ASC), ("timestamp", DESC)],
                                name="audit_logs_user_ts")
    total_indexes += 3

    # ── loanbook — ESR indices (MDB-03) ─────────────────────────────────────
    # ESR compuesto principal: Equality (estado) + Sort (dpd) + Range (score_pago)
    _safe_index(db.loanbook, 
        [("estado", ASC), ("dpd", ASC), ("score_pago", DESC)],
        name="loanbook_esr_estado_dpd_score",
    )
    # Indice simple para migraciones y consultas rapidas
    _safe_index(db.loanbook, [("codigo", ASC)], name="loanbook_codigo")
    _safe_index(db.loanbook, [("dpd_bucket", ASC)], name="loanbook_dpd_bucket")
    _safe_index(db.loanbook, [("score_pago", ASC)], name="loanbook_score_pago")
    # Unico sparse: chasis (motocicleta puede no tener chasis en staging)
    _safe_index(db.loanbook, [("chasis", ASC)], unique=True, sparse=True,
                              name="loanbook_chasis_unique")
    # Indice parcial: morosos activos (DPD > 0) — optimiza cobranza
    _safe_index(db.loanbook, 
        [("dpd", DESC), ("score_pago", ASC)],
        partialFilterExpression={"dpd": {"$gt": 0}},
        name="loanbook_morosos_partial",
    )
    # Indice parcial: cola de cobranza (activos con mora > 7 dias)
    _safe_index(db.loanbook, 
        [("dpd", DESC)],
        partialFilterExpression={"estado": "activo", "dpd": {"$gt": 7}},
        name="loanbook_cola_cobranza_partial",
    )
    total_indexes += 7

    # ── cartera_pagos ────────────────────────────────────────────────────────
    _safe_index(db.cartera_pagos, [("loan_id", ASC), ("fecha_pago", DESC)],
                                   name="cartera_loan_fecha")
    total_indexes += 1

    # ── inventario_motos ─────────────────────────────────────────────────────
    _safe_index(db.inventario_motos, [("estado", ASC)], name="inventario_estado")
    _safe_index(db.inventario_motos, [("chasis", ASC)], unique=True, sparse=True,
                                      name="inventario_chasis_unique")
    total_indexes += 2

    # ── catalogo_motos ───────────────────────────────────────────────────────
    _safe_index(db.catalogo_motos, [("activo", ASC)], name="catalogo_motos_activo")
    _safe_index(db.catalogo_motos, [("modelo", ASC)], unique=True,
                                    name="catalogo_motos_modelo_unique")
    total_indexes += 2

    # ── catalogo_planes ──────────────────────────────────────────────────────
    _safe_index(db.catalogo_planes, [("plan", ASC)], unique=True,
                                     name="catalogo_planes_plan_unique")
    total_indexes += 1

    # ── conciliacion bancaria ────────────────────────────────────────────────
    _safe_index(db.conciliacion_extractos_procesados, [("hash", ASC)], unique=True,
                                                       name="ext_hash_unique")
    _safe_index(db.conciliacion_extractos_procesados, [("banco", ASC), ("fecha", ASC)],
                                                       name="ext_banco_fecha")
    _safe_index(db.conciliacion_movimientos_procesados, [("hash", ASC)], unique=True,
                                                         name="mov_hash_unique")
    _safe_index(db.conciliacion_movimientos_procesados, [("banco", ASC), ("fecha", ASC)],
                                                         name="mov_banco_fecha")
    _safe_index(db.conciliacion_reintentos, [("movimiento_hash", ASC)], unique=True,
                                             name="reintentos_hash_unique")
    _safe_index(db.conciliacion_reintentos, [("estado", ASC), ("proximo_intento", ASC)],
                                             name="reintentos_estado_proximo")
    _safe_index(db.conciliacion_reintentos, [("banco", ASC), ("fecha", ASC)],
                                             name="reintentos_banco_fecha")
    total_indexes += 7

    # ── plan_cuentas_roddos ──────────────────────────────────────────────────
    _safe_index(db.plan_cuentas_roddos, [("categoria", ASC), ("subcategoria", ASC)],
                                         unique=True, name="plan_cuentas_cat_subcat")
    _safe_index(db.plan_cuentas_roddos, [("alegra_id", ASC)], name="plan_cuentas_alegra_id")
    total_indexes += 2

    # ── ingresos_registrados ─────────────────────────────────────────────────
    _safe_index(db.ingresos_registrados, [("fecha", ASC), ("tipo_ingreso", ASC)],
                                          name="ingresos_fecha_tipo")
    total_indexes += 1

    # ── proveedores_config ───────────────────────────────────────────────────
    _safe_index(db.proveedores_config, [("nit", ASC)], unique=True,
                                        name="proveedores_nit_unique")
    total_indexes += 1

    # ── cfo_informes ────────────────────────────────────────────────────────
    _safe_index(db.cfo_informes, [("fecha_generacion", DESC)], name="cfo_informes_fecha")
    total_indexes += 1

    # ── cfo_alertas ─────────────────────────────────────────────────────────
    _safe_index(db.cfo_alertas, [("resuelta", ASC), ("periodo", ASC)],
                                  name="cfo_alertas_resuelta_periodo")
    _safe_index(db.cfo_alertas, [("created_at", DESC)], name="cfo_alertas_created")
    _safe_index(db.cfo_alertas, [("tipo", ASC), ("leido", ASC)],
                                  name="cfo_alertas_tipo_leido")
    total_indexes += 3

    # ── cfo_instrucciones ────────────────────────────────────────────────────
    _safe_index(db.cfo_instrucciones, [("activa", ASC)], name="cfo_instrucciones_activa")
    total_indexes += 1

    # ── cfo_compromisos ──────────────────────────────────────────────────────
    _safe_index(db.cfo_compromisos, [("activo", ASC)], name="cfo_compromisos_activo")
    total_indexes += 1

    # ── cxc_socios ───────────────────────────────────────────────────────────
    _safe_index(db.cxc_socios, [("socio", ASC), ("estado", ASC)],
                                 name="cxc_socios_socio_estado")
    _safe_index(db.cxc_socios, [("fecha", ASC)], name="cxc_socios_fecha")
    total_indexes += 2

    # ── cxc_clientes ─────────────────────────────────────────────────────────
    _safe_index(db.cxc_clientes, [("nit_cliente", ASC)], name="cxc_clientes_nit")
    _safe_index(db.cxc_clientes, [("vencimiento", ASC)], name="cxc_clientes_vencimiento")
    total_indexes += 2

    # ── roddos_events — ESR + TTL (MDB-02, D-08) ────────────────────────────
    # Limpiar docs legacy sin event_id antes de crear indice unique
    _backfill_null = db.roddos_events.find(
        {"$or": [{"event_id": None}, {"event_id": {"$exists": False}}]}
    )
    for doc in _backfill_null:
        db.roddos_events.update_one(
            {"_id": doc["_id"]},
            {"$set": {"event_id": str(uuid.uuid4())}},
        )
    # Unico en event_id — sparse=True ignora docs legacy sin el campo
    _safe_index(db.roddos_events, [("event_id", ASC)], unique=True, sparse=True,
                                   name="roddos_events_event_id_unique")
    # Compuesto: event_type + timestamp_utc para filtrado cronologico por tipo
    _safe_index(db.roddos_events, 
        [("event_type", ASC), ("timestamp_utc", DESC)],
        name="roddos_events_type_ts",
    )
    # Indice de estado para cola de procesamiento
    _safe_index(db.roddos_events, [("estado", ASC), ("timestamp_utc", DESC)],
                                   name="roddos_events_estado_ts")
    # TTL: 90 dias = 7776000 segundos — expiracion automatica de eventos
    try:
        _safe_index(db.roddos_events, 
            [("timestamp_utc", ASC)],
            expireAfterSeconds=7776000,
            name="ttl_timestamp_90d",
        )
        total_indexes += 1
    except Exception:
        pass  # TTL index ya existe
    total_indexes += 3

    # ── roddos_events_dlq — Dead Letter Queue (MDB-09, D-09) ─────────────────
    _safe_index(db.roddos_events_dlq, [("next_retry", ASC)],
                                       name="dlq_next_retry")
    _safe_index(db.roddos_events_dlq, [("retry_count", ASC), ("status", ASC)],
                                       name="dlq_retry_count_status")
    _safe_index(db.roddos_events_dlq, [("status", ASC)], name="dlq_status")
    _safe_index(db.roddos_events_dlq, [("original_event_id", ASC)],
                                       name="dlq_original_event_id")
    total_indexes += 4

    # ── portfolio_summaries — resumen de cartera pre-calculado (MDB-07, D-11) ─
    _safe_index(db.portfolio_summaries, [("date", ASC)], unique=True,
                                         name="portfolio_date_unique")
    _safe_index(db.portfolio_summaries, [("created_at", DESC)],
                                         name="portfolio_created_at")
    total_indexes += 2

    # ── financial_reports — P&L y balances mensuales (MDB-08, D-11) ──────────
    _safe_index(db.financial_reports, 
        [("year", ASC), ("month", ASC)],
        unique=True,
        name="financial_reports_year_month_unique",
    )
    _safe_index(db.financial_reports, [("created_at", DESC)],
                                       name="financial_reports_created_at")
    total_indexes += 2

    # ── sismo_knowledge — base RAG de reglas de negocio (MDB-06) ─────────────
    _safe_index(db.sismo_knowledge, [("rule_id", ASC)], unique=True,
                                     name="sismo_knowledge_rule_id_unique")
    _safe_index(db.sismo_knowledge, [("categoria", ASC)], name="sismo_knowledge_categoria")
    total_indexes += 2

    # ── notifications ────────────────────────────────────────────────────────
    _safe_index(db.notifications, [("user_id", ASC), ("leido", ASC)],
                                   name="notifications_user_leido")
    _safe_index(db.notifications, [("created_at", DESC)], name="notifications_created")
    total_indexes += 2

    # ── user_settings ────────────────────────────────────────────────────────
    _safe_index(db.user_settings, [("user_id", ASC)], unique=True,
                                   name="user_settings_user_unique")
    total_indexes += 1

    return total_indexes


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — catalogo_planes
# ─────────────────────────────────────────────────────────────────────────────

CATALOGO_DEFAULT = [
    {
        "plan": "P39S", "modo_pago": "semanal",
        "cuotas_semanal": 39, "cuotas_quincenal": 20, "cuotas_mensual": 9,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Sport 100": {
                "precio_venta": 5_750_000,
                "valor_cuota_semanal": 175_000,
                "valor_cuota_quincenal": 385_000,
                "valor_cuota_mensual": 770_000,
            },
        },
    },
    {
        "plan": "P52S", "modo_pago": "semanal",
        "cuotas_semanal": 52, "cuotas_quincenal": 26, "cuotas_mensual": 12,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Sport 100": {
                "precio_venta": 5_750_000,
                "valor_cuota_semanal": 160_000,
                "valor_cuota_quincenal": 352_000,
                "valor_cuota_mensual": 704_000,
            },
        },
    },
    {
        "plan": "P78S_Raider", "modo_pago": "semanal",
        "cuotas_semanal": 78, "cuotas_quincenal": 39, "cuotas_mensual": 18,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Raider 125": {
                "precio_venta": 7_800_000,
                "valor_cuota_semanal": 149_900,
            },
        },
    },
    {
        "plan": "P78S_Sport", "modo_pago": "semanal",
        "cuotas_semanal": 78, "cuotas_quincenal": 39, "cuotas_mensual": 18,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Sport 100": {
                "precio_venta": 5_750_000,
                "valor_cuota_semanal": 130_000,
            },
        },
    },
    {
        "plan": "Contado", "modo_pago": "contado",
        "cuotas_semanal": 0, "cuotas_quincenal": 0, "cuotas_mensual": 0,
        "mora_diaria": 2000,
        "modelos": {},
    },
]


def seed_catalogo_planes(db) -> int:
    """Siembra los planes de financiacion con multiplicadores reales. Upsert por plan."""
    for plan in CATALOGO_DEFAULT:
        db.catalogo_planes.update_one(
            {"plan": plan["plan"]},
            {"$set": plan},
            upsert=True,
        )
    return db.catalogo_planes.count_documents({})


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — plan_cuentas_roddos
# Excluye todas las entradas con alegra_id == 5495 (per D-05)
# El fallback es 5493 (Gastos generales) que permanece en el catalogo
# ─────────────────────────────────────────────────────────────────────────────

PLAN_CUENTAS_RODDOS = [
    # PERSONAL
    {"categoria": "Personal", "subcategoria": "Salarios",         "alegra_id": 5462, "cuenta_codigo": "510506", "cuenta_nombre": "Sueldos y salarios",            "tipo_retefuente": "nomina"},
    {"categoria": "Personal", "subcategoria": "Honorarios",       "alegra_id": 5475, "cuenta_codigo": "511025", "cuenta_nombre": "Honorarios (asesoria)",          "tipo_retefuente": "honorarios_pn"},
    {"categoria": "Personal", "subcategoria": "Honorarios_PJ",    "alegra_id": 5476, "cuenta_codigo": "511030", "cuenta_nombre": "Honorarios PJ",                  "tipo_retefuente": "honorarios_pj"},
    {"categoria": "Personal", "subcategoria": "Seguridad_Social", "alegra_id": 5472, "cuenta_codigo": "510570", "cuenta_nombre": "Aportes seguridad social",       "tipo_retefuente": "nomina"},
    {"categoria": "Personal", "subcategoria": "Dotacion",         "alegra_id": 5470, "cuenta_codigo": "510551", "cuenta_nombre": "Dotacion a trabajadores",        "tipo_retefuente": "nomina"},
    {"categoria": "Personal", "subcategoria": "Vacaciones",       "alegra_id": 5469, "cuenta_codigo": "510539", "cuenta_nombre": "Vacaciones",                     "tipo_retefuente": "nomina"},
    {"categoria": "Personal", "subcategoria": "Prima",            "alegra_id": 5468, "cuenta_codigo": "510536", "cuenta_nombre": "Prima de servicios",             "tipo_retefuente": "nomina"},
    {"categoria": "Personal", "subcategoria": "Cesantias",        "alegra_id": 5466, "cuenta_codigo": "510530", "cuenta_nombre": "Cesantias",                      "tipo_retefuente": "nomina"},
    # OPERACIONES
    {"categoria": "Operaciones", "subcategoria": "Arriendo",          "alegra_id": 5480, "cuenta_codigo": "512010", "cuenta_nombre": "Arrendamientos",                                  "tipo_retefuente": "arrendamiento"},
    {"categoria": "Operaciones", "subcategoria": "Servicios_Publicos", "alegra_id": 5485, "cuenta_codigo": "513525", "cuenta_nombre": "Alcantarillado/Acueducto/Servicios publicos",    "tipo_retefuente": "servicios"},
    {"categoria": "Operaciones", "subcategoria": "Telefonia",          "alegra_id": 5487, "cuenta_codigo": "513535", "cuenta_nombre": "Telefono/Internet/Comunicaciones",               "tipo_retefuente": "servicios"},
    {"categoria": "Operaciones", "subcategoria": "Mantenimiento",      "alegra_id": 5483, "cuenta_codigo": "513515", "cuenta_nombre": "Asistencia tecnica/Mantenimiento",               "tipo_retefuente": "servicios"},
    {"categoria": "Operaciones", "subcategoria": "Transporte",         "alegra_id": 5499, "cuenta_codigo": "519545", "cuenta_nombre": "Taxis y buses/Transporte",                       "tipo_retefuente": "otros"},
    {"categoria": "Operaciones", "subcategoria": "Papeleria",          "alegra_id": 5497, "cuenta_codigo": "519530", "cuenta_nombre": "Utiles, papeleria y fotocopia",                  "tipo_retefuente": "compras"},
    {"categoria": "Operaciones", "subcategoria": "Aseo",               "alegra_id": 5482, "cuenta_codigo": "513505", "cuenta_nombre": "Aseo y vigilancia",                              "tipo_retefuente": "servicios"},
    {"categoria": "Operaciones", "subcategoria": "Combustible",        "alegra_id": 5498, "cuenta_codigo": "519535", "cuenta_nombre": "Combustibles y lubricantes",                     "tipo_retefuente": "compras"},
    # IMPUESTOS (excluye 5495 — ID invalido)
    {"categoria": "Impuestos", "subcategoria": "ICA",     "alegra_id": 5478, "cuenta_codigo": "511505", "cuenta_nombre": "Industria y Comercio (ICA)",     "tipo_retefuente": "impuesto"},
    {"categoria": "Impuestos", "subcategoria": "Predial", "alegra_id": 5478, "cuenta_codigo": "511505", "cuenta_nombre": "Industria y Comercio (predial)", "tipo_retefuente": "impuesto"},
    # FINANCIERO
    {"categoria": "Financiero", "subcategoria": "Intereses",           "alegra_id": 5533, "cuenta_codigo": "615020", "cuenta_nombre": "Intereses (creditos directos)", "tipo_retefuente": "otros"},
    {"categoria": "Financiero", "subcategoria": "Comisiones_Bancarias", "alegra_id": 5508, "cuenta_codigo": "530515", "cuenta_nombre": "Comisiones bancarias",           "tipo_retefuente": "otros"},
    {"categoria": "Financiero", "subcategoria": "Gastos_Bancarios",    "alegra_id": 5507, "cuenta_codigo": "530505", "cuenta_nombre": "Gastos bancarios",               "tipo_retefuente": "otros"},
    {"categoria": "Financiero", "subcategoria": "Seguros",             "alegra_id": 5493, "cuenta_codigo": "5195",   "cuenta_nombre": "Gastos generales (seguros)",     "tipo_retefuente": "otros"},
    {"categoria": "Financiero", "subcategoria": "GMF",                 "alegra_id": 5509, "cuenta_codigo": "531520", "cuenta_nombre": "Gravamen al movimiento financiero", "tipo_retefuente": "otros"},
    # BANCOS
    {"categoria": "Bancos", "subcategoria": "Global66", "alegra_id": 11100507, "cuenta_codigo": "11100507", "cuenta_nombre": "Global66 Colombia", "uso": "Banco principal operaciones RODDOS — pagos proveedores y recaudo", "tipo_retefuente": None},
    # OTROS — excluye Representacion (5495) pero mantiene Varios (5493) y Depreciacion
    {"categoria": "Otros", "subcategoria": "Varios",      "alegra_id": 5493, "cuenta_codigo": "5195", "cuenta_nombre": "Gastos generales",  "tipo_retefuente": "otros"},
    {"categoria": "Otros", "subcategoria": "Depreciacion", "alegra_id": 5501, "cuenta_codigo": "5160", "cuenta_nombre": "Depreciacion",      "tipo_retefuente": None},
]
# Nota: Las entradas originales con alegra_id == 5495 han sido removidas:
#   - Marketing/Publicidad (5495)
#   - Marketing/Eventos (5495)
#   - Otros/Representacion (5495)
# El ID fallback es 5493 (Gastos generales) — presente en Financiero/Seguros y Otros/Varios


def seed_plan_cuentas(db) -> int:
    """Siembra el plan de cuentas contable. Upsert por (categoria, subcategoria)."""
    now = datetime.now(timezone.utc).isoformat()
    for entry in PLAN_CUENTAS_RODDOS:
        db.plan_cuentas_roddos.update_one(
            {"categoria": entry["categoria"], "subcategoria": entry["subcategoria"]},
            {"$set": {**entry, "activo": True, "actualizado_en": now}},
            upsert=True,
        )
    return db.plan_cuentas_roddos.count_documents({})


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — sismo_knowledge (10 reglas de negocio para RAG)
# ─────────────────────────────────────────────────────────────────────────────

SISMO_KNOWLEDGE = [
    {
        "rule_id": "mora_definicion",
        "categoria": "cartera",
        "titulo": "Definicion de mora",
        "contenido": (
            "DPD (Days Past Due) > 0 significa mora. "
            "La mora diaria en RODDOS es de $2,000 COP por dia de atraso. "
            "Se calcula sobre la cuota vencida, no sobre el saldo total."
        ),
        "tags": ["mora", "dpd", "cartera", "cobranza"],
    },
    {
        "rule_id": "mora_buckets",
        "categoria": "cartera",
        "titulo": "Buckets de mora",
        "contenido": (
            "Clasificacion de clientes por dias de mora (DPD): "
            "Corriente: DPD = 0. "
            "Bucket 1: DPD 1-7 (mora inicial). "
            "Bucket 2: DPD 8-30 (mora moderada). "
            "Bucket 3: DPD 31-60 (mora grave). "
            "Bucket 4: DPD 61-90 (mora critica). "
            "Bucket 5: DPD > 90 (castigo)."
        ),
        "tags": ["mora", "buckets", "dpd", "clasificacion"],
    },
    {
        "rule_id": "retefuente_honorarios_pn",
        "categoria": "impuestos",
        "titulo": "Retencion en la fuente — Honorarios Persona Natural",
        "contenido": (
            "Tarifa: 10% sobre pagos de honorarios a personas naturales. "
            "Aplica cuando el pago acumulado en el mes supera $1,533,000 COP (base 2025). "
            "No aplica si el proveedor es autoretenedor."
        ),
        "tags": ["retefuente", "honorarios", "persona_natural", "impuestos"],
    },
    {
        "rule_id": "retefuente_honorarios_pj",
        "categoria": "impuestos",
        "titulo": "Retencion en la fuente — Honorarios Persona Juridica",
        "contenido": (
            "Tarifa: 11% sobre pagos de honorarios a personas juridicas. "
            "Aplica cuando el pago supera $1,533,000 COP (base 2025). "
            "No aplica si el proveedor es autoretenedor."
        ),
        "tags": ["retefuente", "honorarios", "persona_juridica", "impuestos"],
    },
    {
        "rule_id": "autoretenedor_regla",
        "categoria": "impuestos",
        "titulo": "Regla autoretenedor",
        "contenido": (
            "AUTECO KAWASAKI S.A.S. (NIT 860024781) es autoretenedor. "
            "A proveedores autoretenedores NO se les aplica ReteFuente. "
            "Ellos mismos hacen la retencion y la declaran. "
            "Verificar siempre el certificado de autoretenedor vigente."
        ),
        "tags": ["autoretenedor", "auteco", "retefuente", "proveedores"],
    },
    {
        "rule_id": "iva_cuatrimestral",
        "categoria": "impuestos",
        "titulo": "IVA cuatrimestral RODDOS",
        "contenido": (
            "RODDOS declara IVA en periodos cuatrimestrales: "
            "Periodo 1: Enero-Abril (plazo 30 mayo). "
            "Periodo 2: Mayo-Agosto (plazo 30 septiembre). "
            "Periodo 3: Septiembre-Diciembre (plazo 30 enero del siguiente anno). "
            "Aplica para responsables del regimen comun con ingresos anuales entre 15 y 92 UVT."
        ),
        "tags": ["iva", "cuatrimestral", "declaracion", "impuestos"],
    },
    {
        "rule_id": "ica_bogota",
        "categoria": "impuestos",
        "titulo": "Impuesto de Industria y Comercio (ICA) Bogota",
        "contenido": (
            "Tarifa ICA Bogota para actividades de servicios financieros: 11.04 por mil. "
            "Se liquida sobre los ingresos brutos del periodo. "
            "Declaracion bimestral o anual segun nivel de ingresos."
        ),
        "tags": ["ica", "bogota", "impuestos", "industria_comercio"],
    },
    {
        "rule_id": "cuenta_fallback",
        "categoria": "contabilidad",
        "titulo": "Cuenta contable fallback",
        "contenido": (
            "Si no hay cuenta contable especifica para una categoria de gasto, "
            "usar cuenta Alegra ID 5493 (Gastos generales, codigo 5195). "
            "El ID 5495 NO es valido en la cuenta de Alegra de RODDOS — "
            "fue removido del catalogo y cualquier gasto que lo usara debe "
            "reclasificarse a 5493."
        ),
        "tags": ["contabilidad", "fallback", "alegra", "gastos_generales"],
    },
    {
        "rule_id": "loanbook_estados",
        "categoria": "cartera",
        "titulo": "Estados validos en loanbook",
        "contenido": (
            "Los estados posibles de un loanbook en SISMO son: "
            "activo (financiamiento vigente con pagos en curso), "
            "mora (cliente con DPD > 0 y notificaciones activas), "
            "pagado (financiamiento cancelado en su totalidad), "
            "cancelado (financiamiento terminado anticipadamente sin pago completo), "
            "restructurado (condiciones renegociadas)."
        ),
        "tags": ["loanbook", "estados", "cartera"],
    },
    {
        "rule_id": "frecuencias_pago",
        "categoria": "loanbook",
        "titulo": "Frecuencias de pago y multiplicadores",
        "contenido": (
            "RODDOS ofrece tres frecuencias de pago con multiplicadores sobre la cuota semanal: "
            "Semanal (x1.0): la cuota base del plan. "
            "Quincenal (x2.2): equivale a 2.2 cuotas semanales. "
            "Mensual (x4.4): equivale a 4.4 cuotas semanales. "
            "Planes disponibles: P39S (39 semanas), P52S (52 semanas), P78S (78 semanas), Contado."
        ),
        "tags": ["frecuencias", "multiplicadores", "loanbook", "planes"],
    },
]


def seed_sismo_knowledge(db) -> int:
    """Siembra las 10 reglas de negocio para RAG. Upsert por rule_id."""
    now = datetime.now(timezone.utc).isoformat()
    for rule in SISMO_KNOWLEDGE:
        db.sismo_knowledge.update_one(
            {"rule_id": rule["rule_id"]},
            {"$set": {**rule, "actualizado_en": now}},
            upsert=True,
        )
    return db.sismo_knowledge.count_documents({})


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — usuarios default
# ─────────────────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()


def seed_users(db) -> int:
    """Siembra los 2 usuarios default. Upsert por email."""
    users = [
        {
            "id": str(uuid.uuid4()),
            "email": "contabilidad@roddos.com",
            "password_hash": _hash_password("Admin@RODDOS2025!"),
            "name": "Contabilidad RODDOS",
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "email": "compras@roddos.com",
            "password_hash": _hash_password("Contador@2025!"),
            "name": "Compras RODDOS",
            "role": "user",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    count = 0
    for user in users:
        email = user["email"]
        existing = db.users.find_one({"email": email})
        if not existing:
            db.users.insert_one(user)
            count += 1
    return count


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — cfo_config
# ─────────────────────────────────────────────────────────────────────────────

def seed_cfo_config(db) -> int:
    """Config CFO default. Upsert: si no existe, crea; si existe, no modifica."""
    result = db.cfo_config.update_one(
        {},
        {"$setOnInsert": {
            "gastos_fijos_semanales": 7_500_000,
            "umbral_mora_pct": 5,
            "umbral_caja_cop": 5_000_000,
            "tarifa_ica_por_mil": 11.04,
            "fechas_dian": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return 1 if result.upserted_id else 0


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — proveedores_config
# ─────────────────────────────────────────────────────────────────────────────

def seed_proveedores_config(db) -> int:
    """Siembra AUTECO KAWASAKI como autoretenedor. Upsert por NIT."""
    result = db.proveedores_config.update_one(
        {"nit": "860024781"},
        {"$set": {
            "nombre": "AUTECO KAWASAKI S.A.S.",
            "nit": "860024781",
            "es_autoretenedor": True,
            "tipo_retencion": "ninguna",
            "notas": "Autoretenedor — no aplicar ReteFuente",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "sistema",
        }},
        upsert=True,
    )
    return 1 if (result.upserted_id or result.modified_count) else 0


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — catalogo_motos
# ─────────────────────────────────────────────────────────────────────────────

CATALOGO_MOTOS_DEFAULT = [
    {
        "modelo": "Sport 100",
        "marca": "Auteco",
        "costo": 4_157_461,
        "pvp": 5_749_900,
        "cuota_inicial": 500_000,
        "matricula": 660_000,
        "planes": {
            "P39S": {"semanas": 39, "cuota": 175_000},
            "P52S": {"semanas": 52, "cuota": 160_000},
            "P78S": {"semanas": 78, "cuota": 130_000},
        },
        "activo": True,
    },
    {
        "modelo": "Raider 125",
        "marca": "Auteco",
        "costo": 5_638_974,
        "pvp": 7_800_000,
        "cuota_inicial": 800_000,
        "matricula": 660_000,
        "planes": {
            "P39S": {"semanas": 39, "cuota": 210_000},
            "P52S": {"semanas": 52, "cuota": 179_900},
            "P78S": {"semanas": 78, "cuota": 149_900},
        },
        "activo": True,
    },
]


def seed_catalogo_motos(db) -> int:
    """Siembra los 2 modelos de moto disponibles. Upsert por modelo."""
    now = datetime.now(timezone.utc).isoformat()
    for moto in CATALOGO_MOTOS_DEFAULT:
        db.catalogo_motos.update_one(
            {"modelo": moto["modelo"]},
            {"$set": {**moto, "actualizado_en": now, "actualizado_por": "sistema"}},
            upsert=True,
        )
    return db.catalogo_motos.count_documents({})


# ─────────────────────────────────────────────────────────────────────────────
# SEED DATA — alegra_credentials (placeholder vacio)
# ─────────────────────────────────────────────────────────────────────────────

def seed_alegra_credentials(db) -> int:
    """Crea el placeholder de credenciales Alegra si no existe."""
    result = db.alegra_credentials.update_one(
        {},
        {"$setOnInsert": {
            "id": str(uuid.uuid4()),
            "email": os.environ.get("ALEGRA_EMAIL", ""),
            "token": os.environ.get("ALEGRA_TOKEN", ""),
            "is_demo_mode": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return 1 if result.upserted_id else 0


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA PRINCIPAL — init_all(db)
# ─────────────────────────────────────────────────────────────────────────────

def init_all(db):
    """
    Inicializa completamente la base de datos SISMO.

    Callable desde tests y desde CLI. Retorna dict con metricas de ejecucion.
    Completamente idempotente — ejecutar multiples veces no produce errores.
    """
    results = {
        "collections": len(COLLECTIONS),
        "indexes": 0,
        "seed_documents": 0,
        "details": {},
    }

    # 1. Asegurar que todas las colecciones existen (basta con referenciarlas)
    print(f"  Verificando {len(COLLECTIONS)} colecciones...")
    for col_name in COLLECTIONS:
        _ = db[col_name]  # Motor las crea al primer uso; esto las registra
    print(f"  {len(COLLECTIONS)} colecciones verificadas")

    # 2. Crear indices
    print("  Creando indices...")
    try:
        n_indexes = _create_indexes(db)
        results["indexes"] = n_indexes
        print(f"  {n_indexes} indices creados/verificados")
    except Exception as e:
        print(f"  ADVERTENCIA indices: {e}")

    # 3. Seed data
    print("  Sembrando datos...")

    n = seed_catalogo_planes(db)
    results["details"]["catalogo_planes"] = n
    results["seed_documents"] += n
    print(f"    catalogo_planes: {n} documentos")

    n = seed_plan_cuentas(db)
    results["details"]["plan_cuentas_roddos"] = n
    results["seed_documents"] += n
    print(f"    plan_cuentas_roddos: {n} documentos")

    n = seed_sismo_knowledge(db)
    results["details"]["sismo_knowledge"] = n
    results["seed_documents"] += n
    print(f"    sismo_knowledge: {n} documentos")

    n = seed_users(db)
    results["details"]["users"] = n
    results["seed_documents"] += n
    print(f"    users: {n} documentos")

    n = seed_cfo_config(db)
    results["details"]["cfo_config"] = n
    results["seed_documents"] += n
    print(f"    cfo_config: {n} documentos")

    n = seed_proveedores_config(db)
    results["details"]["proveedores_config"] = n
    results["seed_documents"] += n
    print(f"    proveedores_config: {n} documentos")

    n = seed_catalogo_motos(db)
    results["details"]["catalogo_motos"] = n
    results["seed_documents"] += n
    print(f"    catalogo_motos: {n} documentos")

    n = seed_alegra_credentials(db)
    results["details"]["alegra_credentials"] = n
    results["seed_documents"] += n
    print(f"    alegra_credentials: {n} documentos")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not MONGO_URL:
        print("ERROR: MONGO_URL no definida. Exporta la variable antes de ejecutar.")
        sys.exit(1)

    try:
        from pymongo import MongoClient
    except ImportError:
        print("ERROR: pymongo no instalado. Ejecuta: pip install pymongo")
        sys.exit(1)

    print(f"Conectando a MongoDB — DB: {DB_NAME}")
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)

    try:
        client.admin.command("ping")
        print(f"Conectado a MongoDB Atlas — DB: {DB_NAME}")
    except Exception as e:
        print(f"ERROR de conexion: {e}")
        sys.exit(1)

    db = client[DB_NAME]

    try:
        results = init_all(db)
        print(
            f"\nInicializacion completa: "
            f"{results['collections']} colecciones, "
            f"{results['indexes']} indices, "
            f"{results['seed_documents']} documentos semilla upserted"
        )
        print("SISMO listo para arrancar.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
