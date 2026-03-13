import base64
import uuid
import httpx
from datetime import datetime, timezone
from fastapi import HTTPException
from mock_data import (
    MOCK_ACCOUNTS, MOCK_CONTACTS, MOCK_ITEMS, MOCK_TAXES, MOCK_RETENTIONS,
    MOCK_COST_CENTERS, MOCK_BANK_ACCOUNTS, MOCK_INVOICES, MOCK_BILLS,
    MOCK_JOURNAL_ENTRIES, MOCK_COMPANY, MOCK_RECONCILIATION_ITEMS
)

ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"


class AlegraService:
    def __init__(self, db):
        self.db = db

    async def get_settings(self):
        settings = await self.db.alegra_credentials.find_one({}, {"_id": 0})
        return settings or {"email": "", "token": "", "is_demo_mode": True}

    async def is_demo_mode(self):
        s = await self.get_settings()
        return s.get("is_demo_mode", True)

    async def get_auth_header(self):
        s = await self.get_settings()
        creds = base64.b64encode(f"{s['email']}:{s['token']}".encode()).decode()
        return {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def request(self, endpoint: str, method: str = "GET", body: dict = None, params: dict = None):
        if await self.is_demo_mode():
            return self._mock(endpoint, method, body, params)
        headers = await self.get_auth_header()
        url = f"{ALEGRA_BASE_URL}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers, params=params or {})
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=body or {})
                elif method == "PUT":
                    resp = await client.put(url, headers=headers, json=body or {})
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    resp = await client.get(url, headers=headers)

            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Credenciales de Alegra inválidas. Verifique su email y token en Configuración.")
            if resp.status_code == 403:
                return []   # endpoint no disponible para este plan/cuenta — devolver lista vacía
            if resp.status_code == 404:
                return []
            if resp.status_code == 429:
                raise HTTPException(status_code=429, detail="Límite de requests de Alegra excedido. Intente en un momento.")
            if resp.status_code >= 500:
                raise HTTPException(status_code=503, detail="Alegra no disponible temporalmente.")
            return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Error conectando con Alegra: {str(e)}")

    def _now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _mock(self, endpoint: str, method: str, body: dict = None, params: dict = None):
        body = body or {}
        if endpoint == "accounts" or (endpoint.startswith("accounts") and "bank" not in endpoint):
            return MOCK_ACCOUNTS
        if "contacts" in endpoint:
            q = (params or {}).get("name", "").lower() if params else ""
            if q:
                return [c for c in MOCK_CONTACTS if q in c["name"].lower()]
            return MOCK_CONTACTS
        if "items" in endpoint:
            return MOCK_ITEMS
        if "taxes" in endpoint:
            return MOCK_TAXES
        if "retentions" in endpoint:
            return MOCK_RETENTIONS
        if "cost-centers" in endpoint:
            return MOCK_COST_CENTERS
        if "bank-accounts" in endpoint and "reconciliations" in endpoint:
            if method == "POST":
                return {"id": f"rec-{uuid.uuid4().hex[:6]}", "status": "created", **body}
            return {"items": MOCK_RECONCILIATION_ITEMS, "statementBalance": 58300000}
        if "bank-accounts" in endpoint:
            return MOCK_BANK_ACCOUNTS
        if "company" in endpoint:
            return MOCK_COMPANY
        if "invoices" in endpoint and "void" in endpoint:
            inv_id = endpoint.split("/")[1]
            return {"id": inv_id, "status": "voided"}
        if "invoices" in endpoint and "email" in endpoint:
            return {"status": "sent"}
        if "invoices" in endpoint:
            if method == "POST":
                new_id = f"inv-{uuid.uuid4().hex[:6]}"
                return {"id": new_id, "number": f"FV-2025-0{len(MOCK_INVOICES)+1:02d}", "status": "open", **body}
            return MOCK_INVOICES
        if "bills" in endpoint:
            if method == "POST":
                new_id = f"bill-{uuid.uuid4().hex[:6]}"
                return {"id": new_id, "number": f"FC-2025-0{len(MOCK_BILLS)+1:02d}", "status": "open", **body}
            return MOCK_BILLS
        if "payments" in endpoint:
            if method == "POST":
                return {"id": f"pago-{uuid.uuid4().hex[:6]}", "status": "paid", **body}
            return []
        if "journal-entries" in endpoint:
            if method == "POST":
                return {"id": f"ce-{uuid.uuid4().hex[:6]}", "number": f"CE-2025-0{len(MOCK_JOURNAL_ENTRIES)+1:02d}", **body}
            return MOCK_JOURNAL_ENTRIES
        return {}

    async def test_connection(self):
        if await self.is_demo_mode():
            return {"status": "demo", "message": "Modo demo activo", "company": MOCK_COMPANY}
        try:
            result = await self.request("company")
            return {"status": "connected", "message": "Conexión exitosa con Alegra", "company": result}
        except HTTPException as e:
            return {"status": "error", "message": e.detail}
