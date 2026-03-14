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
from routers import mercately as mercately_router, crm as crm_router
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

    await run_migration_v24(db)
    start_scheduler()
    start_loanbook_scheduler()


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
app.include_router(mercately_router.router, prefix=PREFIX)
app.include_router(crm_router.router,      prefix=PREFIX)
