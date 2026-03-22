import base64
import uuid
import httpx
import os
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from mock_data import (
    MOCK_ACCOUNTS, MOCK_CONTACTS, MOCK_ITEMS, MOCK_TAXES, MOCK_RETENTIONS,
    MOCK_COST_CENTERS, MOCK_BANK_ACCOUNTS, MOCK_INVOICES, MOCK_BILLS,
    MOCK_JOURNAL_ENTRIES, MOCK_COMPANY, MOCK_RECONCILIATION_ITEMS
)

logger = logging.getLogger(__name__)

ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"
ALEGRA_EMAIL = os.environ.get("ALEGRA_EMAIL", "")
ALEGRA_TOKEN = os.environ.get("ALEGRA_TOKEN", "")

# In-memory TTL caches (per-token)
_settings_cache: dict = {}   # {key: (expires_at, data)}
_accounts_cache: dict = {}   # {key: (expires_at, data)}
_SETTINGS_TTL = 60           # 1 minute
_ACCOUNTS_TTL = 300          # 5 minutes


class AlegraService:
    def __init__(self, db):
        self.db = db

    async def get_cuenta_roddos(self, descripcion: str, tipo: str | None = None) -> dict | None:
        """Busca la cuenta RODDOS más relevante en MongoDB por nombre, palabras_clave o transacciones_tipicas.

        Returns: {codigo, alegra_id, nombre, tipo} o None si no hay match.
        """
        query: dict = {
            "$or": [
                {"nombre":               {"$regex": descripcion, "$options": "i"}},
                {"palabras_clave":       {"$regex": descripcion, "$options": "i"}},
                {"transacciones_tipicas":{"$regex": descripcion, "$options": "i"}},
            ]
        }
        if tipo:
            query["tipo"] = tipo
        doc = await self.db.roddos_cuentas.find_one(query, {"_id": 0})
        return doc

    async def get_cuentas_roddos_frecuentes(self) -> list[dict]:
        """Retorna las cuentas de uso frecuente de RODDOS."""
        return await self.db.roddos_cuentas.find(
            {"uso_frecuente": True}, {"_id": 0}
        ).to_list(100)

    async def get_settings(self):
        cache_key = id(self.db)
        now = datetime.now(timezone.utc)
        if cache_key in _settings_cache:
            expires_at, cached = _settings_cache[cache_key]
            if now < expires_at:
                return cached

        # PRIORITY 1: Environment variables (ALWAYS read fresh, never cached)
        env_email = os.environ.get("ALEGRA_EMAIL", "").strip()
        env_token = os.environ.get("ALEGRA_TOKEN", "").strip()

        if env_email and env_token:
            result = {
                "email": env_email,
                "token": env_token,
                "is_demo_mode": False,
                "_source": "environment_variables"
            }
            logger.info(f"[Alegra] ✅ Credenciales PRODUCCIÓN desde variables de entorno")
            _settings_cache[cache_key] = (now + timedelta(seconds=_SETTINGS_TTL), result)
            return result

        # PRIORITY 2: MongoDB collection (only if env vars not present)
        settings = await self.db.alegra_credentials.find_one({}, {"_id": 0})
        if settings and settings.get("email") and settings.get("token") and not settings.get("is_demo_mode"):
            logger.info(f"[Alegra] ✅ Credenciales PRODUCCIÓN desde MongoDB")
            _settings_cache[cache_key] = (now + timedelta(seconds=_SETTINGS_TTL), settings)
            return settings

        # FALLBACK: Demo mode
        result = {"email": "", "token": "", "is_demo_mode": True, "_source": "fallback_demo"}
        logger.warning(f"[Alegra] ⚠️ DEMO MODE - Configure ALEGRA_EMAIL y ALEGRA_TOKEN en Render")
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

    def _translate_error_to_spanish(self, status_code: int, error_data: dict, endpoint: str, method: str) -> str:
        """Traduce errores de Alegra a mensajes claros en español con acción sugerida."""
        raw_msg = error_data.get("message") or error_data.get("error") or ""

        if status_code == 401:
            return (
                "Credenciales de Alegra incorrectas o expiradas. "
                "Ve a Configuración → Integración Alegra y actualiza el token en app.alegra.com/user/profile#token"
            )
        if status_code == 400:
            # Contexto específico por endpoint
            if "journals" in endpoint:
                if "debit" in raw_msg.lower() or "credit" in raw_msg.lower():
                    return (
                        f"El asiento contable tiene un error de balance: {raw_msg}. "
                        "Verifica que débitos = créditos en todas las entradas."
                    )
                if "id" in raw_msg.lower() or "account" in raw_msg.lower():
                    return (
                        f"ID de cuenta inválido en el asiento: {raw_msg}. "
                        "Usa los IDs del plan de cuentas de RODDOS, no el código PUC."
                    )
                return f"Error en asiento contable: {raw_msg}. Revisa el formato de las entradas."

            if "bills" in endpoint:
                if "item" in raw_msg.lower() or "product" in raw_msg.lower():
                    return (
                        f"Error en factura de compra: {raw_msg}. "
                        "Solo items de tipo 'product' del catálogo de Alegra pueden usarse en bills."
                    )
                if "date" in raw_msg.lower():
                    return f"Fecha inválida en factura: {raw_msg}. Formato requerido: YYYY-MM-DD."

            if "invoices" in endpoint:
                if "client" in raw_msg.lower():
                    return (
                        f"Cliente no encontrado en Alegra: {raw_msg}. "
                        "Crea el cliente primero con la acción crear_contacto."
                    )
                if "dueDate" in raw_msg or "paymentForm" in raw_msg:
                    return (
                        f"Campos obligatorios faltantes en factura: {raw_msg}. "
                        "La factura requiere dueDate y paymentForm='CREDIT' o 'CASH'."
                    )

            if "contacts" in endpoint:
                if "identification" in raw_msg.lower() or "nit" in raw_msg.lower():
                    return (
                        f"Error en identificación del contacto: {raw_msg}. "
                        "Verifica que el NIT/CC sea correcto y usa 'identificationObject' en el formato."
                    )

            return raw_msg or f"Solicitud inválida para '{endpoint}'. Verifica el formato del payload."

        if status_code == 403:
            if method == "GET":
                return ""  # silencioso para GETs
            return (
                f"Sin permisos en Alegra para '{endpoint}'. "
                "Verifica en Alegra → Configuración → Usuarios que tengas permisos de escritura."
            )

        if status_code == 404:
            return f"No encontrado en Alegra: '{endpoint}'. Verifica que el ID exista."

        if status_code == 409:
            return (
                f"Conflicto en Alegra: {raw_msg}. "
                "Es posible que el registro ya exista (duplicado). "
                "Consulta el historial antes de crear de nuevo."
            )

        if status_code == 422:
            return (
                f"Datos inválidos para Alegra: {raw_msg}. "
                "Revisa los tipos de datos y campos requeridos."
            )

        if status_code == 429:
            return (
                "Límite de requests de Alegra excedido. "
                "Espera 30 segundos e intenta de nuevo. "
                "Si persiste, usa carga en lote con BackgroundTasks."
            )

        if status_code >= 500:
            return (
                f"Alegra no disponible temporalmente (HTTP {status_code}). "
                "Intenta en 1-2 minutos. Si persiste, contacta soporte de Alegra."
            )

        return raw_msg or f"Error desconocido de Alegra (HTTP {status_code})"

    async def request(self, endpoint: str, method: str = "GET", body: dict = None, params: dict = None):
        is_demo = await self.is_demo_mode()

        if is_demo:
            logger.debug(f"[Alegra DEMO] {method} {endpoint} (mock data)")
            return self._mock(endpoint, method, body, params)

        logger.info(f"[Alegra REAL] {method} {endpoint} → Calling production API")
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

            # Parse error body once
            error_data: dict = {}
            if resp.content and resp.status_code >= 400:
                try:
                    error_data = resp.json()
                except Exception:
                    pass

            if resp.status_code == 401:
                msg = self._translate_error_to_spanish(401, error_data, endpoint, method)
                raise HTTPException(status_code=400, detail=msg)

            if resp.status_code == 400:
                msg = self._translate_error_to_spanish(400, error_data, endpoint, method)
                raise HTTPException(status_code=400, detail=msg)

            if resp.status_code == 403:
                if method == "GET":
                    return []  # Plan no incluye este endpoint — silencioso
                msg = self._translate_error_to_spanish(403, error_data, endpoint, method)
                raise HTTPException(status_code=403, detail=msg)

            if resp.status_code == 404:
                return []

            if resp.status_code == 409:
                msg = self._translate_error_to_spanish(409, error_data, endpoint, method)
                raise HTTPException(status_code=409, detail=msg)

            if resp.status_code == 422:
                msg = self._translate_error_to_spanish(422, error_data, endpoint, method)
                raise HTTPException(status_code=422, detail=msg)

            if resp.status_code == 429:
                msg = self._translate_error_to_spanish(429, error_data, endpoint, method)
                raise HTTPException(status_code=429, detail=msg)

            if resp.status_code >= 500:
                msg = self._translate_error_to_spanish(resp.status_code, error_data, endpoint, method)
                raise HTTPException(status_code=503, detail=msg)

            result = resp.json()
            logger.info(f"[Alegra REAL] ✅ {method} {endpoint} HTTP {resp.status_code} - Response ID: {result.get('id', 'N/A')}")
            return result

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Error conectando con Alegra: {str(e)}")

    async def request_with_verify(self, endpoint: str, method: str, body: dict = None) -> dict:
        """Ejecuta una solicitud POST/PUT y verifica el resultado con GET.

        REGLA CRÍTICA: Nunca reportar éxito sin verificar HTTP 200 de Alegra.
        Retorna el resultado verificado o lanza HTTPException si la verificación falla.
        """
        result = await self.request(endpoint, method, body)

        # En modo demo no hay nada que verificar
        if await self.is_demo_mode():
            return {**result, "_verificado": True, "_fuente": "demo"}

        # Extraer el ID del recurso creado
        if not isinstance(result, dict):
            return result

        recurso_id = result.get("id")
        if not recurso_id:
            return result  # No hay ID para verificar (operación sin respuesta de ID)

        # Verificación: GET al recurso recién creado
        try:
            verification = await self.request(f"{endpoint}/{recurso_id}", "GET")
            if isinstance(verification, dict) and verification.get("id"):
                return {**result, "_verificado": True, "_verificacion_id": str(recurso_id)}
            elif isinstance(verification, list) and not verification:
                # 404 devuelve lista vacía — recurso no existe
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"VERIFICACIÓN FALLIDA: El recurso {endpoint}/{recurso_id} no existe en Alegra "
                        "después de la creación. La operación puede haber fallado silenciosamente."
                    )
                )
        except HTTPException as e:
            if "VERIFICACIÓN FALLIDA" in str(e.detail):
                raise
            # Otros errores de verificación no son fatales (ej: 403 en GET)
            return {**result, "_verificado": False, "_error_verificacion": str(e.detail)}

        return {**result, "_verificado": True}

    async def retry_request(self, endpoint: str, method: str, body: dict = None,
                             max_retries: int = 3, delay_base: float = 2.0) -> dict:
        """Ejecuta una solicitud con reintentos automáticos para 429/503.

        Args:
            max_retries: máximo de intentos (default 3)
            delay_base: segundos de espera inicial (se dobla en cada reintento)
        """
        import asyncio
        last_error = None

        for attempt in range(max_retries):
            try:
                result = await self.request(endpoint, method, body)
                return result
            except HTTPException as e:
                last_error = e
                if e.status_code in (429, 503):
                    wait = delay_base * (2 ** attempt)
                    await asyncio.sleep(wait)
                    continue
                raise  # Otros errores no se reintentan

        raise last_error or HTTPException(status_code=503, detail="Alegra no respondió después de 3 intentos.")

    async def check_duplicate_journal(self, db, fecha: str, observaciones: str, monto: float) -> dict | None:
        """Verifica si ya existe un journal con la misma fecha y observaciones en Alegra.

        Busca en roddos_events para detectar duplicados sin hacer un GET costoso a Alegra.
        Returns: el evento existente si hay duplicado, o None.
        """
        try:
            existing = await db.roddos_events.find_one({
                "event_type": "asiento.contable.creado",
                "data.fecha": fecha,
                "data.total": monto,
                "data.concepto": {"$regex": observaciones[:30], "$options": "i"},
            }, {"_id": 0})
            return existing
        except Exception:
            return None

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
            if method == "DELETE":
                bill_id = endpoint.split("/")[1] if "/" in endpoint else "unknown"
                return {"id": bill_id, "status": "void"}
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
        if "journal-entries" in endpoint or "journals" in endpoint:
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
                'code': cat.get('code'),          # PUC / local code from Alegra
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
