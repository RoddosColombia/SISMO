"""Shared FastAPI dependencies — auth guards and audit logger."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth import verify_token
from database import db

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


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


async def log_action(user: dict, endpoint: str, method: str, body: Any = None, status_code: int = 200):
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "endpoint": endpoint,
        "method": method,
        "request_body": body,
        "response_status": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
