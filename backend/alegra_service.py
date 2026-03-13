import base64
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from mock_data import (
    MOCK_ACCOUNTS, MOCK_CONTACTS, MOCK_ITEMS, MOCK_TAXES, MOCK_RETENTIONS,
    MOCK_COST_CENTERS, MOCK_BANK_ACCOUNTS, MOCK_INVOICES, MOCK_BILLS,
    MOCK_JOURNAL_ENTRIES, MOCK_COMPANY, MOCK_RECONCILIATION_ITEMS
)

ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"

# In-memory TTL caches (per-token)
_settings_cache: dict = {}   # {key: (expires_at, data)}
_accounts_cache: dict = {}   # {key: (expires_at, data)}
_SETTINGS_TTL = 60           # 1 minute
_ACCOUNTS_TTL = 300          # 5 minutes


class AlegraService:
    def __init__(self, db):
        self.db = db

    async def get_settings(self):
        """Return Alegra credentials with 60s in-memory cache to avoid repeated MongoDB reads."""
        cache_key = id(self.db)
        now = datetime.now(timezone.utc)
        if cache_key in _settings_cache:
            expires_at, cached = _settings_cache[cache_key]
            if now < expires_at:
                return cached
        settings = await self.db.alegra_credentials.find_one({}, {"_id": 0})
        result = settings or {"email": "", "token": "", "is_demo_mode": True}
        _settings_cache[cache_key] = (now + timedelta(seconds=_SETTINGS_TTL), result)
        return result

    def invalidate_settings_cache(self):
        """Call after updating credentials."""
        _settings_cache.pop(id(self.db), None)
        _accounts_cache.pop(id(self.db), None)

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
                raise HTTPException(status_code=400, detail="Credenciales de Alegra inválidas o token expirado. Ve a Configuración → Integración Alegra y genera un nuevo token.")
            if resp.status_code == 400:
                error_data = resp.json() if resp.content else {}
                raise HTTPException(
                    status_code=400,
                    detail=error_data.get("message") or error_data.get("error") or f"Error en Alegra ({endpoint}): solicitud inválida"
                )
            if resp.status_code == 403:
                if method == "GET":
                    # Plan no incluye este endpoint en lectura — devolver lista vacía sin error
                    return []
                else:
                    # POST/PUT con 403 → función no habilitada en el plan Alegra
                    raise HTTPException(
                        status_code=403,
                        detail=f"El plan actual de Alegra no permite ejecutar esta operación ({endpoint}). Verifica el plan en app.alegra.com."
                    )
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
            data = list(MOCK_INVOICES)
            p = params or {}
            if p.get("date_afterOrNow"):
                data = [x for x in data if (x.get("date") or "9999") >= p["date_afterOrNow"]]
            if p.get("date_beforeOrNow"):
                data = [x for x in data if (x.get("date") or "0000") <= p["date_beforeOrNow"]]
            if p.get("status"):
                data = [x for x in data if x.get("status") == p["status"]]
            return data
        if "bills" in endpoint:
            if method == "POST":
                new_id = f"bill-{uuid.uuid4().hex[:6]}"
                return {"id": new_id, "number": f"FC-2025-0{len(MOCK_BILLS)+1:02d}", "status": "open", **body}
            data = list(MOCK_BILLS)
            p = params or {}
            if p.get("date_afterOrNow"):
                data = [x for x in data if (x.get("date") or "9999") >= p["date_afterOrNow"]]
            if p.get("date_beforeOrNow"):
                data = [x for x in data if (x.get("date") or "0000") <= p["date_beforeOrNow"]]
            return data
        if "journal-entries" in endpoint:
            if method == "POST":
                return {"id": f"ce-{uuid.uuid4().hex[:6]}", "number": f"CE-2025-0{len(MOCK_JOURNAL_ENTRIES)+1:02d}", **body}
            data = list(MOCK_JOURNAL_ENTRIES)
            p = params or {}
            if p.get("date_afterOrNow"):
                data = [x for x in data if (x.get("date") or "9999") >= p["date_afterOrNow"]]
            if p.get("date_beforeOrNow"):
                data = [x for x in data if (x.get("date") or "0000") <= p["date_beforeOrNow"]]
            return data
        return {}

    async def get_accounts_from_categories(self):
        """Fetch complete account tree via /categories with 5-minute in-memory cache.
        Uses /categories endpoint (available on Alegra Contabilidad plan) instead of blocked /accounts."""
        if await self.is_demo_mode():
            return MOCK_ACCOUNTS
        cache_key = f"accounts_{id(self.db)}"
        now = datetime.now(timezone.utc)
        if cache_key in _accounts_cache:
            expires_at, cached = _accounts_cache[cache_key]
            if now < expires_at:
                return cached
        cats = await self.request("categories")
        if not cats or not isinstance(cats, list):
            return []
        result = self._transform_categories(cats)
        _accounts_cache[cache_key] = (now + timedelta(seconds=_ACCOUNTS_TTL), result)
        return result

    def _transform_categories(self, cats):
        """Recursively map Alegra /categories format → internal account tree (uses subAccounts key)."""
        result = []
        for cat in cats:
            children = cat.get('children', []) or []
            account = {
                'id': cat['id'],
                'name': cat['name'],
                'type': cat.get('type', 'asset'),
                'nature': cat.get('nature', 'debit'),
                'use': cat.get('use', 'movement'),
                'code': None,  # NIIF accounts have no PUC code
                'status': cat.get('status', 'active'),
                'subAccounts': self._transform_categories(children) if children else [],
            }
            result.append(account)
        return result

    def get_leaf_accounts(self, accounts, result=None):
        """Flatten account tree to only selectable leaf accounts (use=movement)."""
        if result is None:
            result = []
        for acc in accounts:
            subs = acc.get('subAccounts', []) or []
            if acc.get('use') == 'movement' or not subs:
                result.append({
                    'id': acc['id'],
                    'name': acc['name'],
                    'type': acc.get('type', 'asset'),
                    'nature': acc.get('nature', 'debit'),
                    'code': acc.get('code'),
                })
            if subs:
                self.get_leaf_accounts(subs, result)
        return result

    async def test_connection(self):
        if await self.is_demo_mode():
            return {"status": "demo", "message": "Modo demo activo", "company": MOCK_COMPANY}
        try:
            result = await self.request("company")
            return {"status": "connected", "message": "Conexión exitosa con Alegra", "company": result}
        except HTTPException as e:
            return {"status": "error", "message": e.detail}
