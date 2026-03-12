from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional, List, Any
import os
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone

from models import (
    LoginRequest, SaveCredentialsRequest, DemoModeRequest,
    SaveDefaultAccountsRequest, ChatMessageRequest
)
from auth import create_token, verify_token, hash_password, verify_password, create_temp_token, verify_temp_token
from alegra_service import AlegraService
from ai_chat import process_chat, execute_chat_action
from inventory_service import extract_motos_from_pdf, register_moto_in_alegra
from security_service import (
    generate_totp_secret, encrypt_secret, decrypt_secret,
    verify_totp, generate_qr_base64
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
db_name = os.environ["DB_NAME"]
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI(title="RODDOS Contable IA")
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Dependencies ────────────────────────────────────────────────────────────

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


async def require_admin(current_user=Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return current_user


# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    count = await db.users.count_documents({})
    if count == 0:
        users = [
            {"id": str(uuid.uuid4()), "email": "contabilidad@roddos.com", "password_hash": hash_password("Admin@RODDOS2025!"),
             "name": "Contabilidad RODDOS", "role": "admin", "is_active": True,
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": str(uuid.uuid4()), "email": "compras@roddos.com", "password_hash": hash_password("Contador@2025!"),
             "name": "Compras RODDOS", "role": "user", "is_active": True,
             "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        await db.users.insert_many(users)
        logger.info("Demo users created")

    creds = await db.alegra_credentials.find_one({})
    if not creds:
        await db.alegra_credentials.insert_one({
            "id": str(uuid.uuid4()), "email": "", "token": "",
            "is_demo_mode": True, "updated_at": datetime.now(timezone.utc).isoformat()
        })


@app.on_event("shutdown")
async def shutdown():
    client.close()


# ─── Audit Log ────────────────────────────────────────────────────────────────

async def log_action(user: dict, endpoint: str, method: str, body: Any = None, status_code: int = 200):
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "user_id": user.get("id"), "user_email": user.get("email"),
        "endpoint": endpoint, "method": method, "request_body": body,
        "response_status": status_code, "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@api_router.post("/auth/login")
async def login(req: LoginRequest):
    user = await db.users.find_one({"email": req.email}, {"_id": 0})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    # Check 2FA
    if user.get("totp_enabled") and user.get("totp_secret_enc"):
        temp_token = create_temp_token(user["id"], user["email"])
        return {"requires_2fa": True, "temp_token": temp_token}
    token = create_token(user["id"], user["email"], user["role"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}


@api_router.get("/auth/me")
async def get_me(current_user=Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


class TwoFALoginRequest(BaseModel):
    temp_token: str
    code: str


@api_router.post("/auth/2fa/login")
async def two_fa_login(req: TwoFALoginRequest):
    decoded = verify_temp_token(req.temp_token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Token temporal inválido o expirado")
    user = await db.users.find_one({"id": decoded["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if not verify_totp(user.get("totp_secret_enc", ""), req.code):
        raise HTTPException(status_code=401, detail="Código 2FA incorrecto")
    token = create_token(user["id"], user["email"], user["role"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}


class TwoFASetupVerify(BaseModel):
    code: str
    secret: str


@api_router.post("/auth/2fa/setup")
async def setup_2fa(current_user=Depends(require_admin)):
    secret = generate_totp_secret()
    qr_b64 = generate_qr_base64(secret, current_user["email"])
    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"}


@api_router.post("/auth/2fa/enable")
async def enable_2fa(req: TwoFASetupVerify, current_user=Depends(require_admin)):
    totp = __import__("pyotp").TOTP(req.secret)
    if not totp.verify(req.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Código incorrecto. Escanea el QR de nuevo.")
    encrypted = encrypt_secret(req.secret)
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"totp_secret_enc": encrypted, "totp_enabled": True}})
    return {"message": "2FA activado correctamente"}


@api_router.post("/auth/2fa/disable")
async def disable_2fa(current_user=Depends(require_admin)):
    await db.users.update_one({"id": current_user["id"]}, {"$unset": {"totp_secret_enc": "", "totp_enabled": ""}})
    return {"message": "2FA desactivado"}


@api_router.get("/auth/2fa/status")
async def get_2fa_status(current_user=Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return {"totp_enabled": user.get("totp_enabled", False)}


@api_router.get("/auth/me")
async def me(current_user=Depends(get_current_user)):
    return {"id": current_user["id"], "email": current_user["email"], "name": current_user["name"], "role": current_user["role"]}


# ─── SETTINGS ─────────────────────────────────────────────────────────────────

@api_router.get("/settings/credentials")
async def get_credentials(current_user=Depends(require_admin)):
    creds = await db.alegra_credentials.find_one({}, {"_id": 0})
    if not creds:
        return {"email": "", "token": "", "is_demo_mode": True}
    return {"email": creds.get("email", ""), "token_masked": ("*" * 8 + creds.get("token", "")[-4:]) if creds.get("token") else "", "is_demo_mode": creds.get("is_demo_mode", True)}


@api_router.post("/settings/credentials")
async def save_credentials(req: SaveCredentialsRequest, current_user=Depends(require_admin)):
    await db.alegra_credentials.update_one({}, {"$set": {"email": req.email, "token": req.token, "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"message": "Credenciales guardadas correctamente"}


@api_router.get("/settings/demo-mode")
async def get_demo_mode(current_user=Depends(get_current_user)):
    creds = await db.alegra_credentials.find_one({}, {"_id": 0})
    return {"is_demo_mode": creds.get("is_demo_mode", True) if creds else True}


@api_router.put("/settings/demo-mode")
async def set_demo_mode(req: DemoModeRequest, current_user=Depends(require_admin)):
    await db.alegra_credentials.update_one({}, {"$set": {"is_demo_mode": req.is_demo_mode}}, upsert=True)
    return {"is_demo_mode": req.is_demo_mode}


@api_router.get("/settings/default-accounts")
async def get_default_accounts(current_user=Depends(get_current_user)):
    accounts = await db.default_accounts.find({}, {"_id": 0}).to_list(100)
    return accounts


@api_router.post("/settings/default-accounts")
async def save_default_accounts(req: SaveDefaultAccountsRequest, current_user=Depends(require_admin)):
    for item in req.accounts:
        await db.default_accounts.update_one(
            {"operation_type": item.operation_type},
            {"$set": item.model_dump()},
            upsert=True
        )
    return {"message": f"{len(req.accounts)} cuentas predeterminadas guardadas"}


# ─── ALEGRA PROXY ─────────────────────────────────────────────────────────────

@api_router.post("/alegra/test-connection")
async def test_connection(current_user=Depends(get_current_user)):
    service = AlegraService(db)
    return await service.test_connection()


@api_router.get("/alegra/company")
async def get_company(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("company")


@api_router.get("/alegra/accounts")
async def get_accounts(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("accounts")


@api_router.get("/alegra/contacts")
async def get_contacts(name: Optional[str] = Query(None), current_user=Depends(get_current_user)):
    return await AlegraService(db).request("contacts", params={"name": name} if name else None)


@api_router.get("/alegra/items")
async def get_items(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("items")


@api_router.get("/alegra/taxes")
async def get_taxes(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("taxes")


@api_router.get("/alegra/retentions")
async def get_retentions(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("retentions")


@api_router.get("/alegra/cost-centers")
async def get_cost_centers(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("cost-centers")


@api_router.get("/alegra/bank-accounts")
async def get_bank_accounts(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("bank-accounts")


@api_router.get("/alegra/invoices")
async def get_invoices(
    date_start: Optional[str] = None, date_end: Optional[str] = None,
    status: Optional[str] = None, current_user=Depends(get_current_user)
):
    return await AlegraService(db).request("invoices", params={"date_start": date_start, "date_end": date_end, "status": status})


@api_router.post("/alegra/invoices")
async def create_invoice(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("invoices", "POST", body)
    await log_action(current_user, "/alegra/invoices", "POST", body)
    return result


@api_router.post("/alegra/invoices/{invoice_id}/void")
async def void_invoice(invoice_id: str, current_user=Depends(get_current_user)):
    return await AlegraService(db).request(f"invoices/{invoice_id}/void", "POST")


@api_router.get("/alegra/bills")
async def get_bills(date_start: Optional[str] = None, date_end: Optional[str] = None, current_user=Depends(get_current_user)):
    return await AlegraService(db).request("bills", params={"date_start": date_start, "date_end": date_end})


@api_router.post("/alegra/bills")
async def create_bill(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("bills", "POST", body)
    await log_action(current_user, "/alegra/bills", "POST", body)
    return result


@api_router.get("/alegra/payments")
async def get_payments(current_user=Depends(get_current_user)):
    return await AlegraService(db).request("payments")


@api_router.post("/alegra/payments")
async def create_payment(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("payments", "POST", body)
    await log_action(current_user, "/alegra/payments", "POST", body)
    return result


@api_router.get("/alegra/journal-entries")
async def get_journal_entries(date_start: Optional[str] = None, date_end: Optional[str] = None, current_user=Depends(get_current_user)):
    return await AlegraService(db).request("journal-entries", params={"date_start": date_start, "date_end": date_end})


@api_router.post("/alegra/journal-entries")
async def create_journal_entry(body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request("journal-entries", "POST", body)
    await log_action(current_user, "/alegra/journal-entries", "POST", body)
    return result


@api_router.get("/alegra/bank-accounts/{account_id}/reconciliations")
async def get_reconciliations(account_id: str, current_user=Depends(get_current_user)):
    return await AlegraService(db).request(f"bank-accounts/{account_id}/reconciliations")


@api_router.post("/alegra/bank-accounts/{account_id}/reconciliations")
async def create_reconciliation(account_id: str, body: dict, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    result = await service.request(f"bank-accounts/{account_id}/reconciliations", "POST", body)
    await log_action(current_user, f"/alegra/bank-accounts/{account_id}/reconciliations", "POST", body)
    return result


# ─── CHAT ─────────────────────────────────────────────────────────────────────

@api_router.post("/chat/message")
async def chat_message(req: ChatMessageRequest, current_user=Depends(get_current_user)):
    return await process_chat(req.session_id, req.message, db, current_user)


class ExecuteActionRequest(BaseModel):
    action: str
    payload: dict


@api_router.post("/chat/execute-action")
async def chat_execute_action(req: ExecuteActionRequest, current_user=Depends(get_current_user)):
    try:
        result = await execute_chat_action(req.action, req.payload, db, current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/chat/history/{session_id}")
async def chat_history(session_id: str, current_user=Depends(get_current_user)):
    msgs = await db.chat_messages.find({"session_id": session_id}, {"_id": 0}).sort("timestamp", 1).to_list(100)
    return msgs


@api_router.delete("/chat/history/{session_id}")
async def clear_chat(session_id: str, current_user=Depends(get_current_user)):
    await db.chat_messages.delete_many({"session_id": session_id})
    return {"message": "Historial eliminado"}


# ─── AUDIT LOGS ───────────────────────────────────────────────────────────────

@api_router.get("/audit-logs")
async def get_audit_logs(current_user=Depends(require_admin)):
    logs = await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(100).to_list(100)
    return logs


# ─── INVENTARIO AUTECO ────────────────────────────────────────────────────────

@api_router.post("/inventario/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos PDF")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo no puede superar 20MB")
    try:
        motos = await extract_motos_from_pdf(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not motos:
        raise HTTPException(status_code=422, detail="No se encontraron motos en el PDF")

    # Insert into MongoDB (avoid duplicates by chasis)
    inserted = []
    for m in motos:
        chasis = m.get("chasis")
        if chasis:
            existing = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0})
            if existing:
                continue
        await db.inventario_motos.insert_one({k: v for k, v in m.items()})
        inserted.append(m)

    await log_action(current_user, "/inventario/upload-pdf", "POST", {"filename": file.filename, "motos_found": len(motos)})
    return {"inserted": len(inserted), "total_found": len(motos), "motos": inserted}


@api_router.get("/inventario/motos")
async def get_inventario(
    estado: Optional[str] = None,
    marca: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    query = {}
    if estado:
        query["estado"] = estado
    if marca:
        query["marca"] = {"$regex": marca, "$options": "i"}
    motos = await db.inventario_motos.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return motos


@api_router.get("/inventario/stats")
async def get_inventario_stats(current_user=Depends(get_current_user)):
    total = await db.inventario_motos.count_documents({})
    disponibles = await db.inventario_motos.count_documents({"estado": "Disponible"})
    vendidas = await db.inventario_motos.count_documents({"estado": "Vendida"})
    entregadas = await db.inventario_motos.count_documents({"estado": "Entregada"})
    # Total investment
    pipeline = [{"$group": {"_id": None, "total_inversion": {"$sum": "$total"}, "total_costo": {"$sum": "$costo"}}}]
    agg = await db.inventario_motos.aggregate(pipeline).to_list(1)
    totals = agg[0] if agg else {"total_inversion": 0, "total_costo": 0}
    return {
        "total": total,
        "disponibles": disponibles,
        "vendidas": vendidas,
        "entregadas": entregadas,
        "total_inversion": totals.get("total_inversion", 0),
        "total_costo": totals.get("total_costo", 0),
    }


@api_router.put("/inventario/motos/{moto_id}")
async def update_moto(moto_id: str, body: dict, current_user=Depends(get_current_user)):
    body.pop("_id", None)
    body.pop("id", None)
    result = await db.inventario_motos.update_one({"id": moto_id}, {"$set": body})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    updated = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
    return updated


@api_router.delete("/inventario/motos/{moto_id}")
async def delete_moto(moto_id: str, current_user=Depends(require_admin)):
    result = await db.inventario_motos.delete_one({"id": moto_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    return {"message": "Moto eliminada"}


@api_router.post("/inventario/motos/{moto_id}/register-alegra")
async def register_in_alegra(moto_id: str, current_user=Depends(get_current_user)):
    moto = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
    if not moto:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    if moto.get("alegra_item_id"):
        raise HTTPException(status_code=400, detail="Esta moto ya está registrada en Alegra")
    service = AlegraService(db)
    result = await register_moto_in_alegra(moto, service)
    alegra_id = result.get("id")
    await db.inventario_motos.update_one({"id": moto_id}, {"$set": {"alegra_item_id": alegra_id}})
    await log_action(current_user, f"/inventario/motos/{moto_id}/register-alegra", "POST", {"alegra_id": alegra_id})
    return {"alegra_item_id": alegra_id, "result": result}


# ─── IMPUESTOS / IVA CONFIG ───────────────────────────────────────────────────

DEFAULT_IVA_CONFIG = {
    "tipo_periodo": "cuatrimestral",
    "periodos": [
        {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
    ],
    "saldo_favor_dian": 0,
    "fecha_saldo_favor": None,
    "nota_saldo_favor": "",
}

PERIODO_PRESETS = {
    "bimestral": [
        {"nombre": "Ene–Feb", "inicio_mes": 1, "fin_mes": 2, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Mar–Abr", "inicio_mes": 3, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "May–Jun", "inicio_mes": 5, "fin_mes": 6, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Jul–Ago", "inicio_mes": 7, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Sep–Oct", "inicio_mes": 9, "fin_mes": 10, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Nov–Dic", "inicio_mes": 11, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
    ],
    "cuatrimestral": [
        {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
    ],
    "anual": [
        {"nombre": "Ene–Dic", "inicio_mes": 1, "fin_mes": 12, "dia_limite": 31, "mes_limite_offset": 3},
    ],
}


@api_router.get("/impuestos/config")
async def get_iva_config(current_user=Depends(get_current_user)):
    cfg = await db.iva_config.find_one({}, {"_id": 0})
    if not cfg:
        return DEFAULT_IVA_CONFIG
    return cfg


class IvaConfigRequest(BaseModel):
    tipo_periodo: str
    periodos: List[Any]
    saldo_favor_dian: float = 0
    fecha_saldo_favor: Optional[str] = None
    nota_saldo_favor: Optional[str] = ""


@api_router.post("/impuestos/config")
async def save_iva_config(req: IvaConfigRequest, current_user=Depends(require_admin)):
    d = req.model_dump()
    d["updated_at"] = datetime.now(timezone.utc).isoformat()
    d["updated_by"] = current_user.get("email")
    await db.iva_config.update_one({}, {"$set": d}, upsert=True)
    return {"message": "Configuración IVA guardada"}


@api_router.get("/impuestos/periodos-preset")
async def get_periodos_preset(current_user=Depends(get_current_user)):
    return PERIODO_PRESETS


@api_router.get("/impuestos/iva-status")
async def get_iva_status(ano: int = None, current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    ano = ano or now.year
    mes_actual = now.month

    cfg = await db.iva_config.find_one({}, {"_id": 0}) or DEFAULT_IVA_CONFIG
    periodos = cfg.get("periodos", DEFAULT_IVA_CONFIG["periodos"])
    saldo_favor = float(cfg.get("saldo_favor_dian", 0))

    # Find current period
    periodo_actual = None
    for p in periodos:
        if p["inicio_mes"] <= mes_actual <= p["fin_mes"]:
            periodo_actual = p
            break
    if not periodo_actual:
        periodo_actual = periodos[-1]

    inicio_mes = periodo_actual["inicio_mes"]
    fin_mes = periodo_actual["fin_mes"]
    date_start = f"{ano}-{str(inicio_mes).zfill(2)}-01"
    date_end = f"{ano}-{str(fin_mes).zfill(2)}-28"

    # Fetch from Alegra
    service = AlegraService(db)
    try:
        invoices = await service.request("invoices", params={"date_start": date_start, "date_end": date_end})
        bills = await service.request("bills", params={"date_start": date_start, "date_end": date_end})
    except Exception:
        invoices, bills = [], []

    invoices = invoices if isinstance(invoices, list) else []
    bills = bills if isinstance(bills, list) else []

    # Estimate IVA from totals (19% of base = total/1.19*0.19)
    total_ventas = sum(float(inv.get("total") or 0) for inv in invoices)
    total_compras = sum(float(b.get("total") or 0) for b in bills)
    iva_cobrado = round(total_ventas / 1.19 * 0.19)
    iva_descontable = round(total_compras / 1.19 * 0.19)
    iva_bruto = max(0, iva_cobrado - iva_descontable)
    iva_pagar_neto = max(0, iva_bruto - saldo_favor)
    saldo_favor_restante = max(0, saldo_favor - iva_bruto)

    # Projection to end of period
    meses_periodo = fin_mes - inicio_mes + 1
    meses_transcurridos = max(1, mes_actual - inicio_mes + 1)
    factor = meses_periodo / meses_transcurridos
    iva_cobrado_proyectado = round(iva_cobrado * factor)
    iva_descontable_proyectado = round(iva_descontable * factor)
    iva_pagar_proyectado = max(0, round((iva_cobrado_proyectado - iva_descontable_proyectado) - saldo_favor))

    # Deadline
    mes_limite = fin_mes + periodo_actual.get("mes_limite_offset", 1)
    ano_limite = ano
    if mes_limite > 12:
        mes_limite -= 12
        ano_limite += 1
    dia_limite = periodo_actual.get("dia_limite", 30)
    fecha_limite = f"{ano_limite}-{str(mes_limite).zfill(2)}-{dia_limite}"
    from datetime import date
    try:
        hoy = date.today()
        limite = date.fromisoformat(fecha_limite)
        dias_restantes = (limite - hoy).days
    except Exception:
        dias_restantes = None

    # Avance del período
    pct_avance = round((meses_transcurridos / meses_periodo) * 100)

    return {
        "periodo": periodo_actual,
        "ano": ano,
        "date_start": date_start,
        "date_end": date_end,
        "mes_actual": mes_actual,
        "meses_transcurridos": meses_transcurridos,
        "meses_periodo": meses_periodo,
        "pct_avance": pct_avance,
        "fecha_limite": fecha_limite,
        "dias_restantes": dias_restantes,
        "facturas_venta": len(invoices),
        "facturas_compra": len(bills),
        "total_ventas": total_ventas,
        "total_compras": total_compras,
        "iva_cobrado": iva_cobrado,
        "iva_descontable": iva_descontable,
        "iva_bruto": iva_bruto,
        "saldo_favor_dian": saldo_favor,
        "iva_pagar_neto": iva_pagar_neto,
        "saldo_favor_restante": saldo_favor_restante,
        "proyeccion": {
            "iva_cobrado": iva_cobrado_proyectado,
            "iva_descontable": iva_descontable_proyectado,
            "iva_pagar": iva_pagar_proyectado,
        },
    }


# ─── PRESUPUESTO ──────────────────────────────────────────────────────────────

class PresupuestoItem(BaseModel):
    mes: str
    ano: int
    categoria: str
    concepto: str
    valor_presupuestado: float
    cuenta_alegra_id: Optional[str] = None
    cuenta_alegra_nombre: Optional[str] = None


@api_router.get("/presupuesto")
async def get_presupuesto(ano: int = 2025, current_user=Depends(get_current_user)):
    items = await db.presupuesto.find({"ano": ano}, {"_id": 0}).sort("mes", 1).to_list(500)
    return items


@api_router.post("/presupuesto")
async def save_presupuesto(items: List[PresupuestoItem], current_user=Depends(get_current_user)):
    for item in items:
        d = item.model_dump()
        d["updated_at"] = datetime.now(timezone.utc).isoformat()
        d["updated_by"] = current_user.get("email")
        # Only set id on insert, not on update
        existing = await db.presupuesto.find_one(
            {"mes": item.mes, "ano": item.ano, "concepto": item.concepto}, {"_id": 0, "id": 1}
        )
        if not existing:
            d["id"] = str(uuid.uuid4())
        await db.presupuesto.update_one(
            {"mes": item.mes, "ano": item.ano, "concepto": item.concepto},
            {"$set": d},
            upsert=True
        )
    return {"message": f"{len(items)} ítems guardados"}


@api_router.delete("/presupuesto/{item_id}")
async def delete_presupuesto_item(item_id: str, current_user=Depends(require_admin)):
    await db.presupuesto.delete_one({"id": item_id})
    return {"message": "Ítem eliminado"}


# ─── DASHBOARD ALERTS (Agente Proactivo) ──────────────────────────────────────

@api_router.get("/dashboard/alerts")
async def get_dashboard_alerts(current_user=Depends(get_current_user)):
    service = AlegraService(db)
    alerts = []

    try:
        # 1. Facturas de venta vencidas
        overdue = await service.request("invoices", params={"status": "overdue"})
        overdue = overdue if isinstance(overdue, list) else []
        if overdue:
            total_overdue = sum(float(inv.get("balance") or inv.get("total") or 0) for inv in overdue)
            alerts.append({
                "id": "overdue_invoices",
                "type": "overdue_invoices",
                "severity": "high",
                "icon": "warning",
                "title": f"Tienes {len(overdue)} factura(s) vencida(s)",
                "message": f"Total por cobrar: {total_overdue:,.0f}",
                "action_label": "Registrar cobros",
                "action_type": "navigate",
                "action_payload": {"route": "/registro-cuotas"},
                "data": {"count": len(overdue), "total": total_overdue, "invoices": [
                    {"id": i["id"], "client": i.get("client", {}).get("name", ""), "total": i.get("balance") or i.get("total")}
                    for i in overdue[:3]
                ]},
            })
    except Exception:
        pass

    try:
        # 2. Facturas de proveedor próximas a vencer (7 días)
        from datetime import date, timedelta
        today = date.today()
        week_later = today + timedelta(days=7)
        all_bills = await service.request("bills", params={"status": "open"})
        all_bills = all_bills if isinstance(all_bills, list) else []
        due_soon = []
        for b in all_bills:
            due = b.get("dueDate") or b.get("due_date")
            if due:
                try:
                    d = date.fromisoformat(due[:10])
                    if today <= d <= week_later:
                        due_soon.append(b)
                except Exception:
                    pass
        if due_soon:
            total_due = sum(float(b.get("balance") or b.get("total") or 0) for b in due_soon)
            alerts.append({
                "id": "bills_due_soon",
                "type": "bills_due_soon",
                "severity": "medium",
                "icon": "calendar",
                "title": f"{len(due_soon)} factura(s) de proveedor vencen esta semana",
                "message": f"Total: {total_due:,.0f}",
                "action_label": "Ver facturas",
                "action_type": "navigate",
                "action_payload": {"route": "/facturacion-compra"},
                "data": {"count": len(due_soon), "total": total_due},
            })
    except Exception:
        pass

    try:
        # 3. Impuesto venciendo en <7 días
        from datetime import date as _date
        cfg = await db.iva_config.find_one({}, {"_id": 0})
        if cfg:
            periodos = cfg.get("periodos", [])
            hoy = _date.today()
            mes_actual = hoy.month
            ano_actual = hoy.year
            for p in periodos:
                if p["inicio_mes"] <= mes_actual <= p["fin_mes"]:
                    mes_lim = p["fin_mes"] + p.get("mes_limite_offset", 1)
                    ano_lim = ano_actual + (1 if mes_lim > 12 else 0)
                    mes_lim_f = mes_lim if mes_lim <= 12 else mes_lim - 12
                    try:
                        limite = _date(ano_lim, mes_lim_f, min(p.get("dia_limite", 30), 28))
                        dias = (limite - hoy).days
                        if 0 <= dias <= 7:
                            alerts.append({
                                "id": "iva_due",
                                "type": "iva_due",
                                "severity": "critical",
                                "icon": "tax",
                                "title": f"IVA {cfg.get('tipo_periodo', 'cuatrimestral')} vence en {dias} día(s)",
                                "message": f"Período {p['nombre']} — Fecha límite: {limite}",
                                "action_label": "Ver estado IVA",
                                "action_type": "navigate",
                                "action_payload": {"route": "/impuestos"},
                                "data": {"dias_restantes": dias, "fecha_limite": str(limite)},
                            })
                    except Exception:
                        pass
    except Exception:
        pass

    return alerts


class AlertExecuteRequest(BaseModel):
    alert_type: str
    payload: Optional[dict] = None


@api_router.post("/dashboard/alerts/execute")
async def execute_alert_action(req: AlertExecuteRequest, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    if req.alert_type == "send_collection_reminder":
        # Get overdue invoices and mark as reminder sent (in demo, just return OK)
        overdue = await service.request("invoices", params={"status": "overdue"})
        overdue = overdue if isinstance(overdue, list) else []
        return {"success": True, "message": f"Recordatorio enviado a {len(overdue)} clientes", "count": len(overdue)}
    return {"success": True, "message": "Acción ejecutada"}


# ─── AGENT MEMORY ──────────────────────────────────────────────────────────────

@api_router.get("/agent/memory")
async def get_agent_memory(current_user=Depends(get_current_user)):
    items = await db.agent_memory.find(
        {"user_id": current_user["id"]}, {"_id": 0}
    ).sort("ultima_ejecucion", -1).limit(50).to_list(50)
    return items


@api_router.get("/agent/memory/suggestions")
async def get_memory_suggestions(current_user=Depends(get_current_user)):
    """Return entries executed last month for re-execution suggestions."""
    from datetime import date
    today = date.today()
    last_month = today.month - 1 if today.month > 1 else 12
    last_month_year = today.year if today.month > 1 else today.year - 1
    prefix = f"{last_month_year}-{str(last_month).zfill(2)}"
    items = await db.agent_memory.find(
        {"user_id": current_user["id"], "ultima_ejecucion": {"$regex": f"^{prefix}"}},
        {"_id": 0}
    ).to_list(10)
    return items


@api_router.delete("/agent/memory/{memory_id}")
async def delete_memory_item(memory_id: str, current_user=Depends(get_current_user)):
    await db.agent_memory.delete_one({"id": memory_id, "user_id": current_user["id"]})
    return {"message": "Memoria eliminada"}


# ─── INVENTARIO — VENTA DE MOTO ────────────────────────────────────────────────

class VentaMotoRequest(BaseModel):
    cliente_id: str
    cliente_nombre: str
    precio_venta: float
    tipo_pago: str = "contado"
    cuotas: int = 1
    valor_cuota: Optional[float] = None
    include_iva: bool = True
    ipoc_pct: float = 8.0


@api_router.post("/inventario/motos/{moto_id}/vender")
async def vender_moto(moto_id: str, req: VentaMotoRequest, current_user=Depends(get_current_user)):
    moto = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
    if not moto:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    if moto.get("estado") != "Disponible":
        raise HTTPException(status_code=400, detail=f"Moto no disponible (estado: {moto.get('estado')})")

    service = AlegraService(db)

    # Build invoice items
    price_base = req.precio_venta
    items = [{"description": f"{moto.get('marca')} {moto.get('version')} — Chasis: {moto.get('chasis')} Motor: {moto.get('motor')}", "quantity": 1, "price": price_base, "account": {"id": "4105"}}]
    if req.include_iva:
        items[0]["tax"] = [{"percentage": 19}]

    invoice_payload = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "dueDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "client": {"id": req.cliente_id},
        "items": items,
        "observations": f"Venta moto {moto.get('marca')} {moto.get('version')} — {req.tipo_pago}",
    }

    result = await service.request("invoices", "POST", invoice_payload)
    invoice_id = result.get("id")
    invoice_number = result.get("numberTemplate", {}).get("fullNumber") or result.get("number") or str(invoice_id)

    # Update moto status in MongoDB
    sale_data = {
        "estado": "Vendida",
        "cliente_id": req.cliente_id,
        "cliente_nombre": req.cliente_nombre,
        "precio_venta": req.precio_venta,
        "tipo_pago": req.tipo_pago,
        "cuotas": req.cuotas,
        "valor_cuota": req.valor_cuota,
        "factura_id": invoice_id,
        "factura_numero": invoice_number,
        "fecha_venta": datetime.now(timezone.utc).isoformat(),
        "vendido_por": current_user.get("email"),
    }
    await db.inventario_motos.update_one({"id": moto_id}, {"$set": sale_data})

    # Update item in Alegra if registered
    if moto.get("alegra_item_id"):
        try:
            await service.request(f"items/{moto['alegra_item_id']}", "PUT", {"status": "inactive"})
        except Exception:
            pass

    await log_action(current_user, f"/inventario/motos/{moto_id}/vender", "POST",
                     {"invoice_number": invoice_number, "cliente": req.cliente_nombre})

    return {
        "success": True,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "message": f"Moto vendida — Factura {invoice_number} creada en Alegra",
        "moto": {**moto, **sale_data},
    }


# ─── AUDIT LOG ENHANCED ───────────────────────────────────────────────────────

@api_router.get("/audit-logs")
async def get_audit_logs(
    user_email: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    only_errors: bool = False,
    page: int = 1,
    limit: int = 50,
    current_user=Depends(require_admin)
):
    query = {}
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if date_start:
        query.setdefault("timestamp", {})["$gte"] = date_start
    if date_end:
        query.setdefault("timestamp", {})["$lte"] = date_end + "T23:59:59"
    if only_errors:
        query["response_status"] = {"$gte": 400}

    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * limit
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "page": page, "limit": limit, "logs": logs}


# ─── WEBHOOKS ─────────────────────────────────────────────────────────────────

@api_router.post("/settings/webhooks/register")
async def register_webhook(current_user=Depends(require_admin)):
    """Register RODDOS as a webhook recipient in Alegra."""
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
        await db.webhook_config.update_one({}, {"$set": {"webhook_id": webhook_id, "url": webhook_url, "registered_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"success": True, "webhook_id": webhook_id, "url": webhook_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registrando webhook en Alegra: {str(e)}")


@api_router.get("/settings/webhooks/status")
async def get_webhook_status(current_user=Depends(require_admin)):
    cfg = await db.webhook_config.find_one({}, {"_id": 0})
    return cfg or {"webhook_id": None, "url": None, "registered_at": None}


# Public endpoint — no auth — receives events from Alegra
@app.post("/api/webhook/alegra")
async def receive_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    event_type = body.get("event") or body.get("type") or "unknown"
    data = body.get("data") or body
    notif_id = str(uuid.uuid4())
    await db.notifications.insert_one({
        "id": notif_id,
        "event_type": event_type,
        "data": data,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}


# ─── NOTIFICATIONS ─────────────────────────────────────────────────────────────

@api_router.get("/notifications")
async def get_notifications(unread_only: bool = False, current_user=Depends(get_current_user)):
    query = {}
    if unread_only:
        query["read"] = False
    notifs = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return notifs


@api_router.put("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, current_user=Depends(get_current_user)):
    await db.notifications.update_one({"id": notif_id}, {"$set": {"read": True}})
    return {"ok": True}


@api_router.put("/notifications/read-all")
async def mark_all_read(current_user=Depends(get_current_user)):
    await db.notifications.update_many({"read": False}, {"$set": {"read": True}})
    return {"ok": True}


app.include_router(api_router)
