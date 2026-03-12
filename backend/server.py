from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, UploadFile, File
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
from auth import create_token, verify_token, hash_password, verify_password
from alegra_service import AlegraService
from ai_chat import process_chat, execute_chat_action
from inventory_service import extract_motos_from_pdf, register_moto_in_alegra

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
            {"id": str(uuid.uuid4()), "email": "admin@roddos.com", "password_hash": hash_password("Admin@RODDOS2025!"),
             "name": "Administrador RODDOS", "role": "admin", "is_active": True,
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": str(uuid.uuid4()), "email": "contador@roddos.com", "password_hash": hash_password("Contador@2025!"),
             "name": "Contador Principal", "role": "user", "is_active": True,
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
    token = create_token(user["id"], user["email"], user["role"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}


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
        d["id"] = str(uuid.uuid4())
        d["updated_at"] = datetime.now(timezone.utc).isoformat()
        d["updated_by"] = current_user.get("email")
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


app.include_router(api_router)
