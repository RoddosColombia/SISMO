"""
Shared pytest configuration for SISMO V1 backend tests.

Stubs out heavy dependencies (MongoDB, Alegra, qrcode) so individual
test modules can import specific routers without needing real credentials.
"""
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# ── 1. Set required env vars BEFORE any app module is imported ─────────────────
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "sismo_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("ALEGRA_USER", "test@test.com")
os.environ.setdefault("ALEGRA_TOKEN", "test-token")

# ── 2. Stub `database` module so Motor never connects ─────────────────────────
_mock_db = MagicMock()
_mock_db_module = MagicMock()
_mock_db_module.db = _mock_db
sys.modules.setdefault("database", _mock_db_module)

# ── 3. Stub other heavy/optional modules ─────────────────────────────────────
for _mod in ["qrcode", "pyotp", "motor", "motor.motor_asyncio"]:
    sys.modules.setdefault(_mod, MagicMock())
