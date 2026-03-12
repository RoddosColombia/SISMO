import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta

SECRET_KEY = os.environ.get("JWT_SECRET", "roddos-jwt-secret-2025-secure")
ALGORITHM = "HS256"
EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_temp_token(user_id: str, email: str) -> str:
    """Short-lived token for 2FA pending verification."""
    payload = {
        "sub": user_id,
        "email": email,
        "scope": "2fa_pending",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def verify_temp_token(token: str) -> dict | None:
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if decoded.get("scope") != "2fa_pending":
            return None
        return decoded
    except Exception:
        return None
