"""
init_mongodb_sismo.py — Inicialización de MongoDB para SISMO / RODDOS S.A.S.

Uso:
    MONGO_URL="mongodb+srv://..." DB_NAME="sismo" python init_mongodb_sismo.py

Crea colecciones, índices y datos iniciales necesarios para el arranque del backend.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME   = os.environ.get("DB_NAME", "sismo")

if not MONGO_URL:
    print("ERROR: MONGO_URL no definida. Exporta la variable antes de ejecutar.")
    sys.exit(1)

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import CollectionInvalid
except ImportError:
    print("ERROR: pymongo no instalado. Ejecuta: pip install pymongo")
    sys.exit(1)

client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=8000)
db = client[DB_NAME]

# ── Test conexión ─────────────────────────────────────────────────────────────
try:
    client.admin.command("ping")
    print(f"✅ Conectado a MongoDB Atlas — DB: {DB_NAME}")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
    sys.exit(1)

# ── Colecciones e índices ─────────────────────────────────────────────────────
INDEXES = {
    "users":              [("email", ASCENDING)],
    "chat_messages":      [("session_id", ASCENDING), ("timestamp", DESCENDING)],
    "loanbook":           [("codigo", ASCENDING), ("estado", ASCENDING)],
    "cartera_pagos":      [("loan_id", ASCENDING), ("fecha_pago", DESCENDING)],
    "inventario_motos":   [("estado", ASCENDING), ("chasis", ASCENDING)],
    "cfo_informes":       [("fecha_generacion", DESCENDING)],
    "cfo_alertas":        [("resuelta", ASCENDING), ("periodo", ASCENDING)],
    "cfo_instrucciones":  [("activa", ASCENDING)],
    "cfo_compromisos":    [("activo", ASCENDING)],
    "cfo_chat_historia":  [("session_id", ASCENDING), ("ts", ASCENDING)],
    "audit_log":          [("timestamp", DESCENDING)],
    "alegra_credentials": [],
}

for col_name, idx_fields in INDEXES.items():
    try:
        col = db[col_name]
        if idx_fields:
            col.create_index(idx_fields)
        print(f"  ✅ Colección lista: {col_name}")
    except Exception as e:
        print(f"  ⚠️  {col_name}: {e}")

# ── Usuarios default ──────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

if db.users.count_documents({}) == 0:
    users = [
        {
            "id": str(uuid.uuid4()),
            "email": "contabilidad@roddos.com",
            "password_hash": _hash_password("Admin@RODDOS2025!"),
            "name": "Contabilidad RODDOS",
            "role": "admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": str(uuid.uuid4()),
            "email": "compras@roddos.com",
            "password_hash": _hash_password("Contador@2025!"),
            "name": "Compras RODDOS",
            "role": "user",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    db.users.insert_many(users)
    print("  ✅ Usuarios default creados")
else:
    print(f"  ℹ️  Usuarios ya existen ({db.users.count_documents({})} encontrados)")

# ── Credenciales Alegra vacías (placeholder) ──────────────────────────────────
if not db.alegra_credentials.find_one({}):
    db.alegra_credentials.insert_one({
        "id": str(uuid.uuid4()),
        "user": os.environ.get("ALEGRA_USER", ""),
        "token": os.environ.get("ALEGRA_TOKEN", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print("  ✅ Credenciales Alegra inicializadas")
else:
    print("  ℹ️  Credenciales Alegra ya existen")

# ── Config CFO default ────────────────────────────────────────────────────────
if not db.cfo_config.find_one({}):
    db.cfo_config.insert_one({
        "gastos_fijos_semanales": 7_500_000,
        "umbral_mora_pct": 5,
        "umbral_caja_cop": 5_000_000,
        "tarifa_ica_por_mil": 11.04,
        "fechas_dian": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    print("  ✅ Config CFO default creada")
else:
    print("  ℹ️  Config CFO ya existe")

print("\n🚀 Inicialización completa. SISMO listo para arrancar.")
client.close()
