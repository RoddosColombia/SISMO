"""Settings router — Alegra credentials, demo mode, default accounts, webhooks, catalogo."""
import os
import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
        return {
            "has_credentials": False, "api_key_masked": "",
            "phone_number": "", "whitelist": [], "ceo_number": "",
            "destinatarios_resumen": [], "configured_at": "",
            "global_activo": True, "horario_inicio": "08:00", "horario_fin": "19:00",
            "templates_activos": {"T1": True, "T2": True, "T3": True, "T4": True, "T5": True},
            "datos_bancarios": "",
        }
    ak = cfg.get("api_key", "")
    destinatarios = list(cfg.get("destinatarios_resumen", []))
    ceo = cfg.get("ceo_number", "")
    if ceo and ceo not in destinatarios:
        destinatarios = [ceo] + destinatarios
    # Default all templates to True if not set
    templates = cfg.get("templates_activos", {})
    for t in ("T1", "T2", "T3", "T4", "T5"):
        if t not in templates:
            templates[t] = True
    return {
        "has_credentials": bool(ak),
        "api_key_masked": ("*" * 8 + ak[-4:]) if len(ak) > 4 else ("*" * len(ak)),
        "phone_number": cfg.get("phone_number", ""),
        "whitelist": cfg.get("whitelist", []),
        "ceo_number": ceo,
        "destinatarios_resumen": destinatarios,
        "configured_at": cfg.get("updated_at", ""),
        "global_activo": cfg.get("global_activo", True),
        "horario_inicio": cfg.get("horario_inicio", "08:00"),
        "horario_fin": cfg.get("horario_fin", "19:00"),
        "templates_activos": templates,
        "datos_bancarios": cfg.get("datos_bancarios", ""),
    }


@router.post("/mercately")
async def save_mercately_credentials(req: MercatelyCredentialsRequest, current_user=Depends(require_admin)):
    destinatarios = list(req.destinatarios_resumen)
    if req.ceo_number and req.ceo_number not in destinatarios:
        destinatarios = [req.ceo_number] + destinatarios
    update_data = {
        "phone_number": req.phone_number,
        "whitelist": req.whitelist,
        "ceo_number": req.ceo_number,
        "destinatarios_resumen": destinatarios,
        "global_activo": req.global_activo,
        "horario_inicio": req.horario_inicio,
        "horario_fin": req.horario_fin,
        "templates_activos": req.templates_activos,
        "datos_bancarios": req.datos_bancarios,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Only update api_key if a new one was provided
    if req.api_key and req.api_key != "__keep__":
        update_data["api_key"] = req.api_key
    await db.mercately_config.update_one(
        {},
        {"$set": update_data, "$unset": {"api_secret": ""}},
        upsert=True,
    )
    return {"message": "Configuración Mercately guardada correctamente."}


@router.post("/mercately/test")
async def test_mercately_connection(current_user=Depends(require_admin)):
    cfg = await db.mercately_config.find_one({}, {"_id": 0})
    if not cfg or not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="No hay API Key configurada. Guarda primero las credenciales.")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.mercately.com/api/v1/agent",
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
            )
        if resp.status_code == 200:
            return {"ok": True, "message": "Conexión exitosa con Mercately ✓"}
        if resp.status_code == 401:
            raise HTTPException(status_code=400, detail="API Key inválida — verifica tus credenciales en Mercately.")
        raise HTTPException(status_code=400, detail=f"Mercately respondió HTTP {resp.status_code}.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="Mercately no responde (timeout 10 s). Verifica tu conexión.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Error de red al contactar Mercately: {e}")


# ─── Catálogo de Motos ────────────────────────────────────────────────────────

class PlanConfig(BaseModel):
    semanas: int
    cuota: float

class CatalogoMotoCreate(BaseModel):
    modelo: str
    marca: str = "Auteco"
    costo: float
    pvp: float
    cuota_inicial: float = 0
    matricula: float = 660000
    planes: dict  # {"P39S": {"semanas": 39, "cuota": 175000}, ...}
    activo: bool = True

class CatalogoMotoUpdate(BaseModel):
    modelo: Optional[str] = None
    marca: Optional[str] = None
    costo: Optional[float] = None
    pvp: Optional[float] = None
    cuota_inicial: Optional[float] = None
    matricula: Optional[float] = None
    planes: Optional[dict] = None
    activo: Optional[bool] = None


@router.get("/catalogo")
async def get_catalogo(
    include_inactive: bool = False,
    current_user=Depends(get_current_user),
):
    """List motorcycle models. By default returns only active models.
    Pass ?include_inactive=true to include inactive ones."""
    query = {} if include_inactive else {"activo": True}
    items = await db.catalogo_motos.find(query, {"_id": 0}).to_list(100)
    return items


@router.get("/catalogo/{item_id}")
async def get_catalogo_item(item_id: str, current_user=Depends(get_current_user)):
    """Get a single catalog model by id."""
    item = await db.catalogo_motos.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    return item


@router.post("/catalogo")
async def create_catalogo_item(req: CatalogoMotoCreate, current_user=Depends(require_admin)):
    """Add a new motorcycle model to the catalog."""
    doc = {
        "id": str(uuid.uuid4()),
        **req.model_dump(),
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "actualizado_por": current_user.get("email"),
    }
    await db.catalogo_motos.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/catalogo/{item_id}")
async def update_catalogo_item(item_id: str, req: CatalogoMotoUpdate, current_user=Depends(require_admin)):
    """Update prices, cuotas or active status of a catalog model.
    Changes apply ONLY to new sales — existing loanbooks are never modified.
    """
    item = await db.catalogo_motos.find_one({"id": item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Modelo no encontrado")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    updates["actualizado_por"] = current_user.get("email")
    await db.catalogo_motos.update_one({"id": item_id}, {"$set": updates})
    updated = await db.catalogo_motos.find_one({"id": item_id}, {"_id": 0})
    return updated



@router.get("/wa-logs")
async def get_wa_logs(limit: int = 100, current_user=Depends(get_current_user)):
    """Historial de mensajes WA enviados por el scheduler (roddos_events[event_type=wa.sent])."""
    logs = await db.roddos_events.find(
        {"event_type": "wa.sent"},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return logs
