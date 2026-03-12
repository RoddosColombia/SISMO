"""2FA TOTP service for admin users."""
import os
import base64
import hashlib
import io
import pyotp
import qrcode
from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    secret = os.environ.get("JWT_SECRET", "roddos-jwt-secret-2025-secure")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


def verify_totp(encrypted_secret: str, code: str) -> bool:
    try:
        secret = decrypt_secret(encrypted_secret)
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


def generate_qr_base64(secret: str, email: str, issuer: str = "RODDOS Contable IA") -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
