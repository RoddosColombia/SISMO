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

from database import db, client
from routers import auth, settings, alegra, chat, inventory, taxes, budget, dashboard, audit
from routers import repuestos, loanbook, telegram, radar as radar_router, cfo as cfo_router
from routers import cfo_estrategico as cfo_est_router
from routers import cfo_chat as cfo_chat_router
from routers import mercately as mercately_router, crm as crm_router
from routers import dian as dian_router
try:
    from routers import ingresos as ingresos_router
    print("[OK] ingresos router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load ingresos router: {e}")
    ingresos_router = None

try:
    from routers import cartera as cartera_router
    print("[OK] cartera router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load cartera router: {e}")
    cartera_router = None

try:
    from routers import nomina as nomina_router
    print("[OK] nomina router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load nomina router: {e}")
    nomina_router = None

try:
    from routers import cxc as cxc_router
    print("[OK] cxc router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load cxc router: {e}")
    cxc_router = None

try:
    from routers import cxc_socios as cxc_socios_router
    print("[OK] cxc_socios router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load cxc_socios router: {e}")
    cxc_socios_router = None

try:
    from routers import admin_kb as admin_kb_router
    print("[OK] admin_kb router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load admin_kb router: {e}")
    admin_kb_router = None
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
from routers import auditoria as auditoria_router
from routers import sync_manual as sync_manual_router
from routers import diagnostico as diagnostico_router
from services.scheduler import start_scheduler, stop_scheduler
from services.event_bus_service import EventBusService
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
    # MongoDB collections, indices, and seed data are managed by init_mongodb_sismo.py
    # Run: MONGO_URL="..." python init_mongodb_sismo.py
    # This startup only connects and initializes runtime services.

    await run_migration_v24(db)

    start_scheduler()
    start_loanbook_scheduler()

    # Event bus — exposes health metrics and holds bus instance for health endpoint
    app.state.event_bus = EventBusService(db)

    logger.info("SISMO startup complete — runtime services initialized")


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
if ingresos_router:
    app.include_router(ingresos_router.router,   prefix=PREFIX)
else:
    print("[WARN] ingresos_router not loaded, skipping registration")

if cartera_router:
    app.include_router(cartera_router.router,    prefix=PREFIX)
else:
    print("[WARN] cartera_router not loaded, skipping registration")

if nomina_router:
    app.include_router(nomina_router.router,     prefix=PREFIX)
else:
    print("[WARN] nomina_router not loaded, skipping registration")

if cxc_router:
    app.include_router(cxc_router.router,        prefix=PREFIX)
else:
    print("[WARN] cxc_router not loaded, skipping registration")

if cxc_socios_router:
    app.include_router(cxc_socios_router.router, prefix=PREFIX)
else:
    print("[WARN] cxc_socios_router not loaded, skipping registration")

if admin_kb_router:
    app.include_router(admin_kb_router.router, prefix=PREFIX)
else:
    print("[WARN] admin_kb_router not loaded, skipping registration")

app.include_router(reports_router.router,                      prefix=PREFIX)
app.include_router(contabilidad_pendientes_router.router,      prefix=PREFIX)
app.include_router(conciliacion_router.router,                 prefix=PREFIX)
app.include_router(auditoria_router.router,                    prefix=PREFIX)
app.include_router(sync_manual_router.router,                  prefix=PREFIX)
app.include_router(diagnostico_router.router,                  prefix=PREFIX)


# ─── Bus Health (BUS-05 / D-11) ──────────────────────────────────────────────

@app.get(f"{PREFIX}/health/bus")
async def bus_health():
    """Live Event Bus health metrics — DLQ pending count, events last hour, status."""
    bus = app.state.event_bus
    return await bus.get_bus_health()


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
        "collections_count": 0,
        "bus_status":        "unknown",
        "indices_ok":        False,
        "catalogo_present":  False,
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

        # Collections count (D-06)
        coll_names = await client[db.name].list_collection_names()
        result["collections_count"] = len(coll_names)

        # Indices check on roddos_events (D-06)
        try:
            indices = await db.roddos_events.index_information()
            has_event_id_idx = any(
                "event_id" in str(idx_info.get("key", []))
                for idx_info in indices.values()
            )
            result["indices_ok"] = has_event_id_idx
            if not has_event_id_idx:
                result["alertas"].append("roddos_events missing event_id index")
                if result["status"] == "ok":
                    result["status"] = "degradado"
        except Exception:
            result["indices_ok"] = False

        # Catalogo planes presence (D-06)
        try:
            cat_count = await db.catalogo_planes.count_documents({})
            result["catalogo_present"] = cat_count > 0
            if not result["catalogo_present"]:
                result["alertas"].append("catalogo_planes empty")
                if result["status"] == "ok":
                    result["status"] = "degradado"
        except Exception:
            result["catalogo_present"] = False

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

    # Bus health (D-06 / BUS-05)
    try:
        bus = app.state.event_bus
        bus_health = await bus.get_bus_health()
        result["bus_status"] = bus_health.get("status", "unknown")
    except Exception:
        result["bus_status"] = "error"
        result["alertas"].append("Event bus health check failed")
        if result["status"] == "ok":
            result["status"] = "degradado"

    llm_key = os.environ.get("ANTHROPIC_API_KEY", "")
    result["anthropic_disponible"] = bool(llm_key)
    if not result["anthropic_disponible"]:
        result["alertas"].append("ANTHROPIC_API_KEY no configurado")
        if result["status"] == "ok":
            result["status"] = "degradado"

    return result

@app.get("/api/debug-env")
async def debug_env():
    """Debug: show environment variable status."""
    email = os.environ.get("ALEGRA_EMAIL", "").strip()
    token = os.environ.get("ALEGRA_TOKEN", "").strip()
    return {
        "ALEGRA_EMAIL": "PRESENT" if email else "MISSING",
        "ALEGRA_EMAIL_LENGTH": len(email),
        "ALEGRA_TOKEN": "PRESENT" if token else "MISSING",
        "ALEGRA_TOKEN_LENGTH": len(token),
        "debug_note": "If both show MISSING, env vars are not configured in Render"
    }

@app.get("/api/debug-alegra")
async def debug_alegra():
    """Debug: Test AlegraService connection and fetch categories."""
    try:
        from alegra_service import AlegraService
        service = AlegraService(db)

        # Check if demo mode
        is_demo = await service.is_demo_mode()
        if is_demo:
            return {
                "status": "DEMO_MODE",
                "message": "AlegraService is in demo mode - credentials not loaded"
            }

        # Get categories
        categories = await service.get_accounts_from_categories()

        if not categories:
            return {
                "status": "ERROR",
                "message": "No categories returned from Alegra"
            }

        # Return results
        return {
            "status": "CONNECTED",
            "total_categories": len(categories),
            "first_three": [
                {"name": c.get("name"), "id": c.get("id"), "type": c.get("type")}
                for c in categories[:3]
            ]
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e)
        }

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
    alegra_email = os.environ.get("ALEGRA_EMAIL", "").strip()
    alegra_token = os.environ.get("ALEGRA_TOKEN", "").strip()
    result["alegra"] = "conectado" if alegra_email and alegra_token else "sin credenciales"

    # Anthropic (ANTHROPIC_API_KEY)
    llm_key = os.environ.get("ANTHROPIC_API_KEY", "")
    result["anthropic"] = "key presente" if llm_key else "error: ANTHROPIC_API_KEY no configurado"

    return result
