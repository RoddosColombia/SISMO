"""Auth router — login, JWT, 2FA."""
import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import create_token, verify_token, hash_password, verify_password, create_temp_token, verify_temp_token
from security_service import generate_totp_secret, encrypt_secret, verify_totp, generate_qr_base64
from database import db
from dependencies import get_current_user, require_admin
from models import LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(req: LoginRequest):
    user = await db.users.find_one({"email": req.email}, {"_id": 0})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    if user.get("totp_enabled") and user.get("totp_secret_enc"):
        temp_token = create_temp_token(user["id"], user["email"])
        return {"requires_2fa": True, "temp_token": temp_token}
    token = create_token(user["id"], user["email"], user["role"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


class TwoFALoginRequest(BaseModel):
    temp_token: str
    code: str


@router.post("/2fa/login")
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


@router.post("/2fa/setup")
async def setup_2fa(current_user=Depends(require_admin)):
    secret = generate_totp_secret()
    qr_b64 = generate_qr_base64(secret, current_user["email"])
    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"}


class TwoFASetupVerify(BaseModel):
    code: str
    secret: str


@router.post("/2fa/enable")
async def enable_2fa(req: TwoFASetupVerify, current_user=Depends(require_admin)):
    totp = pyotp.TOTP(req.secret)
    if not totp.verify(req.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Código incorrecto. Escanea el QR de nuevo.")
    encrypted = encrypt_secret(req.secret)
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"totp_secret_enc": encrypted, "totp_enabled": True}})
    return {"message": "2FA activado correctamente"}


@router.post("/2fa/disable")
async def disable_2fa(current_user=Depends(require_admin)):
    await db.users.update_one({"id": current_user["id"]}, {"$unset": {"totp_secret_enc": "", "totp_enabled": ""}})
    return {"message": "2FA desactivado"}


@router.get("/2fa/status")
async def get_2fa_status(current_user=Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return {"totp_enabled": user.get("totp_enabled", False)}
