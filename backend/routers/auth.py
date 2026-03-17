"""Auth router — login, JWT, 2FA, perfil, cambio de contraseña."""
import uuid
import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

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


# ── Perfil ─────────────────────────────────────────────────────────────────────

class PerfilUpdate(BaseModel):
    nombre: str
    cargo: Optional[str] = None


@router.put("/perfil")
async def actualizar_perfil(req: PerfilUpdate, current_user=Depends(get_current_user)):
    """Actualiza nombre y cargo del usuario autenticado."""
    if not req.nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"name": req.nombre.strip(), "cargo": req.cargo or ""}},
    )
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return {"id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"], "cargo": user.get("cargo", "")}


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str
    password_confirmar: str


@router.put("/cambiar-password")
async def cambiar_password(req: CambiarPasswordRequest, current_user=Depends(get_current_user)):
    """
    Cambia la contraseña del usuario autenticado.
    Valida la contraseña actual, aplica bcrypt y redirige al login.
    """
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 1. Verificar contraseña actual
    if not verify_password(req.password_actual, user["password_hash"]):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")

    # 2. No reusar la misma contraseña
    if verify_password(req.password_nueva, user["password_hash"]):
        raise HTTPException(status_code=400, detail="La nueva contraseña no puede ser igual a la actual")

    # 3. Confirmar coincidencia
    if req.password_nueva != req.password_confirmar:
        raise HTTPException(status_code=400, detail="Las contraseñas nuevas no coinciden")

    # 4. Validar complejidad mínima
    p = req.password_nueva
    if len(p) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
    if not any(c.isupper() for c in p):
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos una mayúscula")
    if not any(c.isdigit() for c in p):
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos un número")

    # 5. Actualizar hash + incrementar token_version (invalida JWTs anteriores)
    new_hash = hash_password(req.password_nueva)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash}, "$inc": {"token_version": 1}},
    )
    return {"message": "Contraseña actualizada. Inicia sesión de nuevo.", "logout_required": True}


@router.get("/sesiones")
async def get_sesiones(current_user=Depends(get_current_user)):
    """Lista de sesiones activas registradas para el usuario (simplificado)."""
    from datetime import datetime, timezone
    # En una implementación completa se guardarían sesiones en DB.
    # Por ahora retornamos la sesión actual más un historial de la colección.
    sesiones = await db.sesiones_activas.find(
        {"user_id": current_user["id"]},
        {"_id": 0},
        sort=[("last_active", -1)],
    ).limit(10).to_list(10)

    if not sesiones:
        # Si no hay sesiones registradas, devolver la sesión actual
        sesiones = [{
            "id": "current",
            "user_id": current_user["id"],
            "dispositivo": "Navegador web",
            "ip": "desconocida",
            "last_active": datetime.now(timezone.utc).isoformat(),
            "es_actual": True,
        }]
    return sesiones


class PreferenciasUpdate(BaseModel):
    notif_errores_agente: bool = True
    notif_resumen_cfo_lunes: bool = True
    notif_dian_errores: bool = True


@router.put("/preferencias")
async def actualizar_preferencias(req: PreferenciasUpdate, current_user=Depends(get_current_user)):
    """Guarda las preferencias de notificación del usuario."""
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"preferencias": req.model_dump()}},
    )
    return {"message": "Preferencias guardadas", "preferencias": req.model_dump()}


@router.get("/preferencias")
async def get_preferencias(current_user=Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return user.get("preferencias", {
        "notif_errores_agente": True,
        "notif_resumen_cfo_lunes": True,
        "notif_dian_errores": True,
    })
