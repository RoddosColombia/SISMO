"""RODDOS Contable IA — FastAPI entry point.
Thin bootstrap: middleware, startup, shutdown, webhook handler, include_routers.
All business logic lives in routers/.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

from auth import hash_password
from database import db, client
from routers import auth, settings, alegra, chat, inventory, taxes, budget, dashboard, audit
from routers import repuestos, loanbook, telegram, radar as radar_router, cfo as cfo_router
from routers import cfo_estrategico as cfo_est_router
from routers import cfo_chat as cfo_chat_router
from routers import mercately as mercately_router, crm as crm_router
from routers import dian as dian_router
from routers import ingresos as ingresos_router
from routers import cxc as cxc_router
from routers import proveedores_config as proveedores_router
from routers import scheduler as scheduler_router
from routers import learning as learning_router
from routers import estado_resultados as er_router
from routers import alegra_webhooks as webhooks_router
from routers import gastos as gastos_router
from routers import ventas as ventas_router
from routers import reports as reports_router
from routers import contabilidad_pendientes as contabilidad_pendientes_router
from routers import conciliacion as conciliacion_router
from routers import sync_manual as sync_manual_router
from services.scheduler import start_scheduler, stop_scheduler
from services.loanbook_scheduler import start_loanbook_scheduler, stop_loanbook_scheduler
from migration_v24 import run_migration_v24

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RODDOS Contable IA", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    count = await db.users.count_documents({})
    if count == 0:
        users = [
            {
                "id": str(uuid.uuid4()),
                "email": "contabilidad@roddos.com",
                "password_hash": hash_password("Admin@RODDOS2025!"),
                "name": "Contabilidad RODDOS",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "email": "compras@roddos.com",
                "password_hash": hash_password("Contador@2025!"),
                "name": "Compras RODDOS",
                "role": "user",
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        await db.users.insert_many(users)
        logger.info("Default users created")

    if not await db.alegra_credentials.find_one({}):
        await db.alegra_credentials.insert_one({
            "id": str(uuid.uuid4()),
            "email": "",
            "token": "",
            "is_demo_mode": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Catálogo de motos (seed once) ─────────────────────────────────────────
    if not await db.catalogo_motos.find_one({}):
        now = datetime.now(timezone.utc).isoformat()
        await db.catalogo_motos.insert_many([
            {
                "id": str(uuid.uuid4()),
                "modelo": "Sport 100",
                "marca": "Auteco",
                "costo": 4157461,
                "pvp": 5749900,
                "cuota_inicial": 500000,
                "matricula": 660000,
                "planes": {
                    "P39S": {"semanas": 39, "cuota": 175000},
                    "P52S": {"semanas": 52, "cuota": 160000},
                    "P78S": {"semanas": 78, "cuota": 130000},
                },
                "activo": True,
                "actualizado_en": now,
                "actualizado_por": "sistema",
            },
            {
                "id": str(uuid.uuid4()),
                "modelo": "Raider 125",
                "marca": "Auteco",
                "costo": 5638974,
                "pvp": 7800000,
                "cuota_inicial": 800000,
                "matricula": 660000,
                "planes": {
                    "P39S": {"semanas": 39, "cuota": 210000},
                    "P52S": {"semanas": 52, "cuota": 179900},
                    "P78S": {"semanas": 78, "cuota": 149900},
                },
                "activo": True,
                "actualizado_en": now,
                "actualizado_por": "sistema",
            },
        ])
        logger.info("catalogo_motos initialized with 2 default models")

    try:
        await db.agent_memory.create_index([("user_id", 1), ("tipo", 1)])
        await db.agent_memory.create_index([("frecuencia_count", -1)])
        await db.agent_memory.create_index([("ultima_ejecucion", -1)])
        await db.audit_logs.create_index([("timestamp", -1)])
        await db.audit_logs.create_index([("user_email", 1), ("timestamp", -1)])
        await db.chat_messages.create_index([("session_id", 1), ("timestamp", 1)])
        await db.inventario_motos.create_index([("estado", 1)])
        await db.inventario_motos.create_index([("chasis", 1)], unique=True, sparse=True)
        await db.catalogo_motos.create_index([("activo", 1)])
        await db.roddos_events.create_index([("estado", 1), ("timestamp", -1)])
        await db.loanbook.create_index([("dpd_bucket", 1)])
        await db.loanbook.create_index([("score_pago", 1)])
        logger.info("MongoDB indexes ensured")
    except Exception as e:
        logger.warning(f"Index creation (non-fatal): {e}")

    # ── Seed proveedores_config con AUTECO KAWASAKI como autoretenedor ────────
    existing_auteco = await db.proveedores_config.find_one(
        {"nombre": {"$regex": "auteco", "$options": "i"}}
    )
    if not existing_auteco:
        await db.proveedores_config.insert_one({
            "nombre": "AUTECO KAWASAKI S.A.S.",
            "nit": "860024781",
            "es_autoretenedor": True,
            "tipo_retencion": "ninguna",
            "notas": "Autoretenedor — no aplicar ReteFuente",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "sistema",
        })
        logger.info("proveedores_config: AUTECO KAWASAKI seeded as autoretenedor")

    # ── Migración: asegurar que IVA config sea cuatrimestral ─────────────────
    _iva_cfg = await db.iva_config.find_one({}, {"_id": 0})
    if _iva_cfg and _iva_cfg.get("tipo_periodo") == "bimestral":
        await db.iva_config.update_one(
            {},
            {"$set": {
                "tipo_periodo": "cuatrimestral",
                "periodos": [
                    {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
                    {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
                    {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
                ],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "migración_cuatrimestral",
            }}
        )
        logger.info("IVA config migrated from bimestral to cuatrimestral")

    await run_migration_v24(db)

    # ── Inicializar plan_cuentas_roddos ───────────────────────────────────────
    plan_count = await db.plan_cuentas_roddos.count_documents({})
    if plan_count == 0:
        from routers.gastos import PLAN_CUENTAS_RODDOS
        now = datetime.now(timezone.utc).isoformat()
        docs = [{**e, "activo": True, "creado_en": now} for e in PLAN_CUENTAS_RODDOS]
        await db.plan_cuentas_roddos.insert_many(docs)
        await db.plan_cuentas_roddos.create_index([("categoria", 1), ("subcategoria", 1)])
        logger.info("plan_cuentas_roddos initialized with %d entries", len(docs))
    else:
        # Update existing entries with current data (idempotent upsert)
        from routers.gastos import PLAN_CUENTAS_RODDOS
        for entry in PLAN_CUENTAS_RODDOS:
            await db.plan_cuentas_roddos.update_one(
                {"categoria": entry["categoria"], "subcategoria": entry["subcategoria"]},
                {"$set": {**entry, "activo": True}},
                upsert=True,
            )

    start_scheduler()
    start_loanbook_scheduler()

    # ── Inicializar plan_ingresos_roddos ──────────────────────────────────────
    from routers.ingresos import PLAN_INGRESOS_RODDOS
    now_str = datetime.now(timezone.utc).isoformat()
    for entry in PLAN_INGRESOS_RODDOS:
        await db.plan_ingresos_roddos.update_one(
            {"tipo_ingreso": entry["tipo_ingreso"]},
            {"$set": {**entry, "actualizado_en": now_str}},
            upsert=True,
        )
    logger.info("plan_ingresos_roddos sincronizado: %d tipos", len(PLAN_INGRESOS_RODDOS))

    # ── Índices CXC ───────────────────────────────────────────────────────────
    await db.cxc_socios.create_index([("socio", 1), ("estado", 1)])
    await db.cxc_socios.create_index([("fecha", 1)])
    await db.cxc_clientes.create_index([("nit_cliente", 1)])
    await db.cxc_clientes.create_index([("vencimiento", 1)])
    await db.ingresos_registrados.create_index([("fecha", 1), ("tipo_ingreso", 1)])
    logger.info("MongoDB indexes for CXC/Ingresos ensured")

    # ── BUILD 21: Memoria conversacional persistente (MODULE 4) ──────────────
    await db.agent_pending_topics.create_index([("user_id", 1), ("estado", 1)])
    await db.agent_pending_topics.create_index([("user_id", 1), ("topic_key", 1)])
    # TTL index: expires_at field — documents auto-deleted after 72h + buffer
    try:
        await db.agent_pending_topics.create_index(
            [("expires_at", 1)],
            expireAfterSeconds=0,
            name="ttl_pending_topics",
        )
    except Exception:
        pass  # Index may already exist

    # ── BUILD 21: CFO alertas (Module 5) ────────────────────────────────────
    await db.cfo_alertas.create_index([("created_at", -1)])
    await db.cfo_alertas.create_index([("tipo", 1), ("leido", 1)])
    logger.info("MongoDB indexes for BUILD 21 (pending_topics + cfo_alertas) ensured")


@app.on_event("shutdown")
async def shutdown():
    stop_loanbook_scheduler()
    stop_scheduler()
    client.close()


# ─── Webhook (public, on app not router — bypasses /api prefix) ───────────────

@app.post("/api/webhook/alegra")
async def receive_webhook(request: Request):
    webhook_secret = os.environ.get("WEBHOOK_SECRET", "")
    if webhook_secret:
        incoming = request.headers.get("X-Alegra-Secret", "") or request.headers.get("Authorization", "")
        if incoming != webhook_secret:
            logger.warning(f"Webhook: invalid secret from {request.client.host if request.client else 'unknown'}")
            return {"ok": True}
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    event_type = body.get("event") or body.get("type") or "unknown"
    data = body.get("data") or body
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "data": data,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


# ─── Include routers ──────────────────────────────────────────────────────────

PREFIX = "/api"
app.include_router(auth.router,      prefix=PREFIX)
app.include_router(settings.router,  prefix=PREFIX)
app.include_router(alegra.router,    prefix=PREFIX)
app.include_router(chat.router,      prefix=PREFIX)
app.include_router(inventory.router, prefix=PREFIX)
app.include_router(taxes.router,     prefix=PREFIX)
app.include_router(budget.router,    prefix=PREFIX)
app.include_router(dashboard.router, prefix=PREFIX)
app.include_router(audit.router,     prefix=PREFIX)
app.include_router(repuestos.router,     prefix=PREFIX)
app.include_router(loanbook.router,      prefix=PREFIX)
# cartera.py removed in BUILD 6 — endpoints migrated to radar.py and crm.py
app.include_router(telegram.router,      prefix=PREFIX)
app.include_router(radar_router.router,    prefix=PREFIX)
app.include_router(cfo_router.router,      prefix=PREFIX)
app.include_router(cfo_est_router.router,  prefix=PREFIX)
app.include_router(mercately_router.router, prefix=PREFIX)
app.include_router(crm_router.router,      prefix=PREFIX)
app.include_router(scheduler_router.router, prefix=PREFIX)
app.include_router(learning_router.router,  prefix=PREFIX)
app.include_router(er_router.router,        prefix=PREFIX)
app.include_router(webhooks_router.router,  prefix=PREFIX)
app.include_router(cfo_chat_router.router,  prefix=PREFIX)
app.include_router(proveedores_router.router, prefix=PREFIX)
app.include_router(gastos_router.router,     prefix=PREFIX)
app.include_router(ventas_router.router,     prefix=PREFIX)
app.include_router(dian_router.router,       prefix=PREFIX)
app.include_router(ingresos_router.router,   prefix=PREFIX)
app.include_router(cxc_router.router,        prefix=PREFIX)
app.include_router(reports_router.router,                      prefix=PREFIX)
app.include_router(contabilidad_pendientes_router.router,      prefix=PREFIX)
app.include_router(conciliacion_router.router,                 prefix=PREFIX)
app.include_router(sync_manual_router.router,                  prefix=PREFIX)


# ─── Smoke Test (PASO 5 — verificación post-deploy) ───────────────────────────

@app.get("/api/health/smoke")
async def smoke_test():
    """
    Smoke test rápido (<10s) para verificar que todos los módulos
    tienen datos reales después de cada deploy.
    Estado: ok / degradado / critico
    """
    result = {
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "loanbooks_activos": 0,
        "cartera_total":     0,
        "inventario_motos":  0,
        "cfo_configuracion": False,
        "alegra_conectado":  False,
        "anthropic_disponible": False,
        "status":            "ok",
        "alertas":           [],
    }

    try:
        await client.admin.command("ping")
    except Exception:
        result["alertas"].append("MongoDB no responde")
        result["status"] = "critico"
        return result

    try:
        result["loanbooks_activos"] = await db.loanbook.count_documents(
            {"estado": {"$in": ["activo", "mora", "al_dia"]}}
        )
        if result["loanbooks_activos"] == 0:
            result["alertas"].append("Sin loanbooks activos — posible pérdida de datos")
            result["status"] = "critico"
        elif result["loanbooks_activos"] < 5:
            result["alertas"].append(f"Pocos loanbooks ({result['loanbooks_activos']}) — verificar datos")
            if result["status"] == "ok":
                result["status"] = "degradado"

        # Calcular cartera total desde cuotas pendientes
        loans = await db.loanbook.find(
            {"estado": {"$in": ["activo", "mora", "al_dia"]}},
            {"_id": 0, "cuotas": 1}
        ).to_list(200)
        total_cartera = 0
        for lb in loans:
            for c in lb.get("cuotas", []):
                if c.get("estado") in ("pendiente", "vencida"):
                    total_cartera += c.get("valor", 0) or 0
        result["cartera_total"] = total_cartera
        if total_cartera == 0:
            result["alertas"].append("Cartera total = $0 — verificar cuotas pendientes")
            if result["status"] == "ok":
                result["status"] = "degradado"

        result["inventario_motos"] = await db.inventario_motos.count_documents({})
        if result["inventario_motos"] == 0:
            result["alertas"].append("Sin motos en inventario")
            if result["status"] == "ok":
                result["status"] = "degradado"

        cfo_cfg = await db.cfo_config.find_one({})
        result["cfo_configuracion"] = cfo_cfg is not None
        if not result["cfo_configuracion"]:
            result["alertas"].append("Falta cfo_config en BD")
            if result["status"] == "ok":
                result["status"] = "degradado"

    except Exception as e:
        result["alertas"].append(f"Error BD: {str(e)[:80]}")
        result["status"] = "critico"

    try:
        creds = await db.alegra_credentials.find_one({}, {"_id": 0, "token": 1})
        result["alegra_conectado"] = bool(creds and creds.get("token"))
        if not result["alegra_conectado"]:
            result["alertas"].append("Alegra sin credenciales")
            if result["status"] == "ok":
                result["status"] = "degradado"
    except Exception:
        result["alertas"].append("Alegra no accesible")

    llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
    result["anthropic_disponible"] = bool(llm_key)
    if not result["anthropic_disponible"]:
        result["alertas"].append("EMERGENT_LLM_KEY no configurado")
        if result["status"] == "ok":
            result["status"] = "degradado"

    return result

@app.get("/api/health")
async def health_check():
    """Diagnóstico rápido del estado del sistema."""
    result = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alegra": "desconocido",
        "mongodb": "desconocido",
        "anthropic": "desconocido",
        "agent_memory": "desconocido",
        "loanbooks_activos": 0,
        "proveedores_config": 0,
    }
    # MongoDB
    try:
        await client.admin.command("ping")
        result["mongodb"] = "conectado"
    except Exception as e:
        result["mongodb"] = f"error: {str(e)[:80]}"
        result["status"] = "degradado"

    # Collections
    try:
        result["loanbooks_activos"] = await db.loanbook.count_documents({"estado": "activo"})
        result["proveedores_config"] = await db.proveedores_config.count_documents({})
        mem_count = await db.agent_memory.count_documents({})
        result["agent_memory"] = "ok" if mem_count > 0 else "vacío"
    except Exception as e:
        result["agent_memory"] = f"error: {str(e)[:60]}"

    # Alegra
    try:
        creds = await db.alegra_credentials.find_one({}, {"_id": 0, "token": 1})
        result["alegra"] = "conectado" if creds and creds.get("token") else "sin credenciales"
    except Exception as e:
        result["alegra"] = f"error: {str(e)[:60]}"

    # Anthropic (EMERGENT_LLM_KEY)
    llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
    result["anthropic"] = "key presente" if llm_key else "error: EMERGENT_LLM_KEY no configurado"

    return result
