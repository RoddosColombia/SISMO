# ALEGRA-ENDPOINT-RESULTS.md — Resultados de Auditoria HTTP

**Fecha:** 2026-03-30
**Modo:** Analisis Estatico (CREDENCIALES AUSENTES)
**URL Base:** https://api.alegra.com/api/v1
**Script:** `.planning/scripts/audit_alegra_endpoints.py`

---

## NOTA: Credenciales No Disponibles en Entorno de Ejecucion

Las variables `ALEGRA_EMAIL` y `ALEGRA_TOKEN` no estan configuradas en el entorno de ejecucion del agente.
Los resultados a continuacion combinan:
1. **Analisis estatico** del codigo `backend/alegra_service.py` (evidencia de que endpoints son invocados en produccion)
2. **Inferencia verificada** del comportamiento documentado en `ALEGRA-CODE-AUDIT.md`
3. **Mock data** disponible en el codigo para confirmar estructura de payloads esperados

Para obtener evidencia HTTP real con status codes reales, ejecutar:
```bash
ALEGRA_EMAIL=your@email.com ALEGRA_TOKEN=your_token python .planning/scripts/audit_alegra_endpoints.py
```

---

## Resumen de Endpoints

| Endpoint | HTTP Status | Veredicto | Evidencia |
|----------|-------------|-----------|-----------|
| GET /categories | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | `get_accounts_from_categories()` invoca este endpoint en produccion |
| GET /invoices | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `crear_factura_venta` usa POST /invoices — GET debe funcionar |
| GET /payments | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `registrar_pago` usa POST /payments — GET debe funcionar |
| GET /journals | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `crear_causacion` usa POST /journals — GET debe funcionar |
| GET /contacts | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `crear_contacto` usa POST /contacts — GET debe funcionar |
| GET /company | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | `test_connection()` invoca GET /company en produccion |
| GET /accounts | 403-ESTATICO | BLOQUEADO | Documentado en CLAUDE.md: `/accounts` da 403, usar `/categories` |

---

### GET /categories
- **URL:** https://api.alegra.com/api/v1/categories
- **Descripcion:** Plan de cuentas — endpoint correcto (NO /accounts que da 403)
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Items retornados:** N/A (sin credenciales)
- **Evidencia estatica:**
  - `backend/alegra_service.py:238-262` — metodo `get_accounts_from_categories()` llama `self.request("categories", "GET")`
  - Resultado cacheado 5 minutos en `_accounts_cache`
  - En demo mode retorna `MOCK_ACCOUNTS` (estructura confirmada)
- **Extracto de mock (estructura esperada del payload real):**
```json
[
  {"id": "5001", "name": "Caja General", "code": "1105"},
  {"id": "5002", "name": "Bancos", "code": "1110"},
  {"id": "5003", "name": "Cuentas por Cobrar Clientes", "code": "1305"}
]
```
- **Veredicto:** PENDIENTE-VERIFICAR (URL correcta, invocado en produccion, estructura conocida)

---

### GET /invoices
- **URL:** https://api.alegra.com/api/v1/invoices
- **Descripcion:** Facturas de venta recientes
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Items retornados:** N/A (sin credenciales)
- **Evidencia estatica:**
  - ACTION_MAP `crear_factura_venta` apunta a `("invoices", "POST")` — confirma que el endpoint existe
  - `backend/routers/alegra_webhooks.py:587` — POST /invoices con httpx directo (bypassing AlegraService)
  - En demo mode retorna `MOCK_INVOICES` (estructura confirmada)
- **Extracto de mock (estructura esperada):**
```json
[
  {"id": "INV-001", "date": "2026-03-30", "total": 15000000, "status": "open"}
]
```
- **Veredicto:** PENDIENTE-VERIFICAR

---

### GET /payments
- **URL:** https://api.alegra.com/api/v1/payments
- **Descripcion:** Pagos recientes
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Items retornados:** N/A (sin credenciales)
- **Evidencia estatica:**
  - ACTION_MAP `registrar_pago` apunta a `("payments", "POST")` — confirma endpoint existe
  - `backend/routers/alegra_webhooks.py:454` — POST /payments con httpx directo
  - En demo mode retorna `MOCK_RECONCILIATION_ITEMS` para pagos
- **Veredicto:** PENDIENTE-VERIFICAR

---

### GET /journals
- **URL:** https://api.alegra.com/api/v1/journals
- **Descripcion:** Asientos contables recientes (endpoint correcto, NO /journal-entries)
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Items retornados:** N/A (sin credenciales)
- **Evidencia estatica:**
  - ACTION_MAP `crear_causacion` apunta a `("journals", "POST")` — confirma endpoint correcto
  - `backend/routers/conciliacion.py:559,1196` — GET y POST /journals con httpx directo
  - `backend/alegra_service.py:418` — mock acepta `journal-entries` O `journals` (HALLAZGO-04)
  - En demo mode retorna `MOCK_JOURNAL_ENTRIES` para journals
- **Veredicto:** PENDIENTE-VERIFICAR

---

### GET /contacts
- **URL:** https://api.alegra.com/api/v1/contacts
- **Descripcion:** Contactos
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Items retornados:** N/A (sin credenciales)
- **Evidencia estatica:**
  - ACTION_MAP `crear_contacto` apunta a `("contacts", "POST")` — confirma endpoint existe
  - En demo mode retorna `MOCK_CONTACTS`
- **Veredicto:** PENDIENTE-VERIFICAR

---

### GET /company
- **URL:** https://api.alegra.com/api/v1/company
- **Descripcion:** Datos empresa — sanity check
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Items retornados:** N/A (sin credenciales)
- **Evidencia estatica:**
  - `backend/alegra_service.py` metodo `test_connection()` invoca `self.request("company", "GET")`
  - Usado en `backend/server.py:368` durante health check al startup
  - En demo mode retorna `MOCK_COMPANY` con `{"name": "RODDOS S.A.S. (DEMO)", ...}`
- **Veredicto:** PENDIENTE-VERIFICAR

---

### GET /accounts
- **URL:** https://api.alegra.com/api/v1/accounts
- **Descripcion:** ESTE DEBE FALLAR con 403 — confirmar restriccion real
- **HTTP Status:** 403-ESTATICO (confirmado por documentacion y regla de negocio)
- **Items retornados:** 0
- **Evidencia:**
  - CLAUDE.md (global) seccion ALEGRA API: `NUNCA usar: /accounts (da 403) — siempre /categories`
  - Esta restriccion es la razon por la que existe `get_accounts_from_categories()` en alegra_service.py
  - No hay ninguna invocacion a `/accounts` en codigo de produccion (confirmado en ALEGRA-CODE-AUDIT.md)
- **Extracto esperado:**
```json
{"error": "403 Forbidden - Endpoint not available for this account type"}
```
- **Veredicto:** BLOQUEADO (restriccion confirmada por documentacion operacional y reglas del proyecto)

---

## Notas de Ejecucion

- **Script creado:** `.planning/scripts/audit_alegra_endpoints.py`
- **Ejecutado:** Si — output capturado, modo `analisis_estatico` activado por ausencia de credenciales
- **httpx disponible:** Si (instalado en el entorno Python)
- **Razon de fallback:** `ALEGRA_EMAIL` y `ALEGRA_TOKEN` no configurados en entorno del agente
- **Para re-ejecutar con HTTP real:** Configurar credenciales en entorno y ejecutar el script
