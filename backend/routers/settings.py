"""Settings router — Alegra credentials, demo mode, default accounts, webhooks."""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user, require_admin
from models import SaveCredentialsRequest, DemoModeRequest, SaveDefaultAccountsRequest, MercatelyCredentialsRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/credentials")
async def get_credentials(current_user=Depends(require_admin)):
    creds = await db.alegra_credentials.find_one({}, {"_id": 0})
    if not creds:
        return {"email": "", "token": "", "is_demo_mode": True}
    return {
        "email": creds.get("email", ""),
        "token_masked": ("*" * 8 + creds.get("token", "")[-4:]) if creds.get("token") else "",
        "is_demo_mode": creds.get("is_demo_mode", True),
    }


@router.post("/credentials")
async def save_credentials(req: SaveCredentialsRequest, current_user=Depends(require_admin)):
    await db.alegra_credentials.update_one(
        {},
        {"$set": {"email": req.email, "token": req.token, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    AlegraService(db).invalidate_settings_cache()
    return {"message": "Credenciales guardadas correctamente"}


@router.get("/demo-mode")
async def get_demo_mode(current_user=Depends(get_current_user)):
    creds = await db.alegra_credentials.find_one({}, {"_id": 0})
    return {"is_demo_mode": creds.get("is_demo_mode", True) if creds else True}


@router.put("/demo-mode")
async def set_demo_mode(req: DemoModeRequest, current_user=Depends(require_admin)):
    await db.alegra_credentials.update_one({}, {"$set": {"is_demo_mode": req.is_demo_mode}}, upsert=True)
    return {"is_demo_mode": req.is_demo_mode}


@router.get("/default-accounts")
async def get_default_accounts(current_user=Depends(get_current_user)):
    accounts = await db.default_accounts.find({}, {"_id": 0}).to_list(100)
    return accounts


@router.post("/default-accounts")
async def save_default_accounts(req: SaveDefaultAccountsRequest, current_user=Depends(require_admin)):
    for item in req.accounts:
        await db.default_accounts.update_one(
            {"operation_type": item.operation_type},
            {"$set": item.model_dump()},
            upsert=True,
        )
    return {"message": f"{len(req.accounts)} cuentas predeterminadas guardadas"}


@router.post("/webhooks/register")
async def register_webhook(current_user=Depends(require_admin)):
    service = AlegraService(db)
    backend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not backend_url:
        raise HTTPException(status_code=400, detail="REACT_APP_BACKEND_URL no configurado")
    webhook_url = f"{backend_url}/api/webhook/alegra"
    payload = {
        "url": webhook_url,
        "events": ["invoice.created", "invoice.voided", "bill.created", "payment.created"],
        "status": "active",
    }
    try:
        result = await service.request("webhooks", "POST", payload)
        webhook_id = result.get("id") if isinstance(result, dict) else str(result)
        await db.webhook_config.update_one(
            {},
            {"$set": {"webhook_id": webhook_id, "url": webhook_url, "registered_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"success": True, "webhook_id": webhook_id, "url": webhook_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registrando webhook en Alegra: {str(e)}")


@router.get("/webhooks/status")
async def get_webhook_status(current_user=Depends(require_admin)):
    cfg = await db.webhook_config.find_one({}, {"_id": 0})
    return cfg or {"webhook_id": None, "url": None, "registered_at": None}


# ─── Mercately (WhatsApp) Configuration ───────────────────────────────────────

@router.get("/mercately")
async def get_mercately_credentials(current_user=Depends(require_admin)):
    cfg = await db.mercately_config.find_one({}, {"_id": 0})
    if not cfg:
        return {"has_credentials": False, "api_key_masked": "", "configured_at": ""}
    ak = cfg.get("api_key", "")
    return {
        "has_credentials": bool(ak and cfg.get("api_secret")),
        "api_key_masked": ("*" * 8 + ak[-4:]) if len(ak) > 4 else ("*" * len(ak)),
        "configured_at": cfg.get("updated_at", ""),
    }


@router.post("/mercately")
async def save_mercately_credentials(req: MercatelyCredentialsRequest, current_user=Depends(require_admin)):
    await db.mercately_config.update_one(
        {},
        {"$set": {
            "api_key": req.api_key,
            "api_secret": req.api_secret,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"message": "Credenciales Mercately guardadas. Lista para integración WhatsApp."}
