from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
import uuid


def utc_now_str():
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    model_config = {"populate_by_name": True}

    def to_mongo(self):
        d = self.model_dump()
        return d

    @classmethod
    def from_mongo(cls, doc):
        if doc is None:
            return None
        doc.pop("_id", None)
        return cls(**doc)


class UserModel(BaseDocument):
    email: str
    password_hash: str
    name: str
    role: str = "user"
    is_active: bool = True
    created_at: str = Field(default_factory=utc_now_str)


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    file_content: Optional[str] = None  # base64 encoded
    file_name: Optional[str] = None
    file_type: Optional[str] = None     # MIME type e.g. image/jpeg, application/pdf


class SaveCredentialsRequest(BaseModel):
    email: str
    token: str


class DemoModeRequest(BaseModel):
    is_demo_mode: bool


class DefaultAccountItem(BaseModel):
    operation_type: str
    account_id: str
    account_code: str
    account_name: str


class SaveDefaultAccountsRequest(BaseModel):
    accounts: List[DefaultAccountItem]


class MercatelyCredentialsRequest(BaseModel):
    api_key: str
    phone_number: str = ""
    whitelist: list[str] = []
    ceo_number: str = ""
    destinatarios_resumen: list[str] = []
    global_activo: bool = True
    horario_inicio: str = "08:00"
    horario_fin: str = "19:00"
    templates_activos: dict = {}          # {"T1": True, "T2": True, ...}
    datos_bancarios: str = ""             # Datos para Template 2 (vencimiento)
