# External Integrations

**Analysis Date:** 2026-03-24

## APIs & External Services

**Accounting Software - Alegra:**
- **Purpose:** Core accounting system integration; invoice, bill, client, item sync
- **Base URL:** https://api.alegra.com/api/v1
- **Webhook Base URL:** https://app.alegra.com/api/r1
- **SDK/Client:** Custom HTTP via httpx
- **Auth:** Basic Auth (email:token) Base64 encoded OR environment variables (ALEGRA_EMAIL, ALEGRA_TOKEN)
- **Configuration:**
  - Primary source: Environment variables (ALEGRA_EMAIL, ALEGRA_TOKEN)
  - Fallback: MongoDB collection `alegra_credentials`
  - Demo mode supported when credentials unavailable
- **Key Endpoints:**
  - GET /accounts - Chart of accounts
  - GET/POST /invoices - Sales invoices
  - GET/POST /bills - Purchase bills
  - GET/POST /contacts - Clients/vendors
  - GET/POST /items - Products/services
- **Backend File:** `/backend/alegra_service.py`, `/backend/routers/alegra.py`

**AI & LLM - Anthropic Claude:**
- **Purpose:** Intelligent chat agent for accounting analysis, document processing, CFO strategic planning
- **SDK/Client:** anthropic 0.34.0 (AsyncAnthropic)
- **Auth:** API Key via environment variable
  - ANTHROPIC_API_KEY - Primary Claude API key
  - EMERGENT_LLM_KEY - Alternative/internal LLM provider (Emergent brand)
- **Models Used:**
  - claude-3.5-sonnet (inferred from code structure)
  - Used in: /backend/ai_chat.py, /backend/routers/cfo_chat.py, /backend/services/cfo_agent.py
- **Capabilities:**
  - Document analysis (PDF, Excel, CSV, bank statements)
  - Accounting entry recommendations
  - Financial forecasting
  - Chat-based query interface
  - Multi-turn conversation with context windows
- **Backend Files:**
  - `/backend/ai_chat.py` - Main AI chat and document processing
  - `/backend/routers/cfo_chat.py` - CFO-specific chat endpoint
  - `/backend/services/cfo_agent.py` - CFO agent logic
  - `/backend/inventory_service.py` - Inventory analysis with Claude

**WhatsApp Business API - Mercately:**
- **Purpose:** Customer communication via WhatsApp; payment status, balance inquiries, confirmations
- **Base URL:** https://api.mercately.com/api/v1
- **Webhook Endpoint:** POST /api/mercately/webhook (public, no JWT)
- **SDK/Client:** Custom HTTP via httpx
- **Auth:** API token (stored in MongoDB `mercately_config`)
- **Message Types:**
  - Customer: Payment confirmations, balance inquiries
  - Internal: Supplier invoice notifications
  - Unknown: Intelligent routing
- **Intent Detection:**
  - Saldo/deuda queries (balance due)
  - Pago/transferencia notifications (payment made)
  - Dificultad/acuerdo (payment difficulty requests)
- **Sender Classification:** CLIENTE, INTERNO, DESCONOCIDO
- **Backend File:** `/backend/routers/mercately.py`
- **Configuration:**
  - Phone number: Stored in `mercately_config` collection
  - Session TTL: 5 minutes

**Messaging - Telegram Bot:**
- **Purpose:** Document upload and accounting intelligence via Telegram; users send photos of receipts/invoices
- **Base URL:** https://api.telegram.org
- **Webhook Endpoint:** POST /api/telegram/webhook (public, no JWT)
- **SDK/Client:** Custom HTTP via httpx
- **Auth:** Bot token (stored in MongoDB `telegram_config`)
- **Capabilities:**
  - Photo/document upload with AI analysis
  - Accounting entry proposal
  - Direct execution in Alegra
  - Message routing to appropriate team member
- **Document Types Recognized:**
  - Factura de compra (purchase invoice)
  - Factura de venta (sales invoice)
  - Recibo de pago (payment receipt)
  - Comprobante de egreso (expense voucher)
  - Extracto bancario (bank statement)
  - Otros (other documents)
- **Backend File:** `/backend/routers/telegram.py`

**Tax Authority - DIAN (Colombia):**
- **Purpose:** Colombian tax compliance and electronic invoice validation
- **Base URL:** Not explicitly shown in code
- **Backend File:** `/backend/routers/dian.py`
- **Scope:** Tax authority integration (implementation details in router)

## Data Storage

**Databases:**
- **MongoDB Atlas** (recommended production)
  - Connection: Environment variable `MONGO_URL` (mongodb+srv://...)
  - Database Name: Environment variable `DB_NAME` (default: "sismo")
  - Client: Motor 3.7.0 (async driver), pymongo 4.9.2 (sync driver for utilities)
  - Shared Connection: `database.py` exports singleton `db` object

**Collections:**
- `roddos_cuentas` - Account chart mapping (codigo, nombre, tipo, palabras_clave, transacciones_tipicas, uso_frecuente)
- `alegra_credentials` - Fallback Alegra credentials (email, token, is_demo_mode)
- `loanbook` - Motorcycle financing records (cliente, moto, cuotas, estado, fechas, montos)
- `inventario` - Inventory management (moto_id, chasis, motor, modelo, VIN, condicion)
- `crm` - Customer data (cedula, nombre, telefono, email, historial)
- `roddos_events` - Event audit log (event_type, source, payload, timestamp, processed)
- `mercately_config` - WhatsApp configuration (phone_number, api_token, templates)
- `telegram_config` - Telegram configuration (bot_token, chat_id, admin_ids)
- `gastos` - Expense records
- `ingresos` - Income records
- `factura_*` - Invoice transaction tables

**File Storage:**
- Local filesystem only - No cloud storage integration detected
- Files handled: Excel (.xlsx), CSV, PDF (via pdfplumber)

**Caching:**
- In-memory TTL caches in `alegra_service.py`:
  - `_settings_cache` - Alegra credentials (TTL: 60 seconds)
  - `_accounts_cache` - Alegra accounts (TTL: 300 seconds)

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based implementation
- **Framework:** python-jose 3.3.0, PyJWT 2.8.0

**Token Strategy:**
- **Standard Token:**
  - Type: JWT (HS256 algorithm)
  - Secret: JWT_SECRET environment variable (default: "roddos-jwt-secret-2025-secure")
  - Payload: {sub: user_id, email, role, exp: +7 days}
  - Expiration: 168 hours (7 days)
  - Location: Authorization: Bearer <token> header

- **2FA Temporary Token:**
  - Scope: 2fa_pending
  - Expiration: 5 minutes
  - Used during 2FA verification flow

**Password Storage:**
- **Hashing:** bcrypt (4.1.2)
- **Verification:** bcrypt.checkpw() with .encode() fallback

**2FA Implementation:**
- **TOTP Generation:** pyotp 2.9.0
- **QR Code Generation:** qrcode 7.4.2
- **Backup Codes:** Supported via temporary token scope

**Backend Files:**
- `/backend/auth.py` - Token generation and verification functions
- `/backend/routers/auth.py` - Login, registration, 2FA endpoints
- `/backend/dependencies.py` - JWT validation dependency

## Monitoring & Observability

**Error Tracking:**
- Not detected - No Sentry, Rollbar, or equivalent integration

**Logs:**
- Python logging module (standard library)
- Log level: INFO by default
- Destination: Console output
- Loggers: Per-module loggers in all routers and services

**Health Check:**
- Optional webpack health check plugin in frontend (`ENABLE_HEALTH_CHECK` env var)
- Backend: No dedicated /health endpoint detected

## CI/CD & Deployment

**Hosting:**
- **Render.com** (specified in `render.yaml`)
- Service: `sismo-backend`
- Runtime: Python 3.11.0
- Region: Oregon
- Plan: Free tier
- Root directory: `/backend`

**Build Command:**
```bash
pip install --force-reinstall -r requirements.txt
```

**Start Command:**
```bash
uvicorn server:app --host 0.0.0.0 --port $PORT
```

**Frontend Deployment:**
- Not specified in repository (likely separate from render.yaml)
- Build: `yarn build` (creates optimized React build)
- Server: Any static hosting (Vercel, Netlify, etc.)

**CI Pipeline:**
- GitHub repository detected (.github/ directory)
- Specific CI workflow configuration not provided

## Environment Configuration

**Required Environment Variables:**

**Backend:**
- `MONGO_URL` - MongoDB connection string (mongodb+srv://username:password@cluster.mongodb.net/)
- `DB_NAME` - Database name (e.g., "sismo")
- `ALEGRA_EMAIL` - Alegra accounting software email
- `ALEGRA_TOKEN` - Alegra API token
- `ALEGRA_WEBHOOK_SECRET` - Secret for webhook signature validation (default: "roddos-webhook-2026")
- `JWT_SECRET` - Secret for JWT token signing (default: "roddos-jwt-secret-2025-secure")
- `ANTHROPIC_API_KEY` - Claude API key for AI features
- `EMERGENT_LLM_KEY` - Alternative LLM provider key (fallback)
- `APP_URL` - Public URL for webhook callbacks (e.g., https://api.roddos.com)

**Frontend:**
- `REACT_APP_BACKEND_URL` - Backend API base URL (e.g., http://localhost:8000 or https://api.roddos.com)

**Optional:**
- `ALEGRA_USER` - Legacy Alegra username field
- `MERCATELY_API_TOKEN` - WhatsApp Mercately API token
- `TELEGRAM_API_TOKEN` - Telegram bot token
- `PYTHON_VERSION` - Python version override (default: 3.11.0)
- `ENABLE_HEALTH_CHECK` - Enable frontend webpack health check (false by default)

**Secrets Location:**
- Environment variables via hosting platform (Render, Vercel, etc.)
- Fallback credentials in MongoDB `alegra_credentials` collection (not recommended for production)
- `.env` file in development (never committed)

## Webhooks & Callbacks

**Incoming Webhooks (Public Endpoints):**

**Alegra Webhooks:**
- **Endpoint:** POST /api/webhooks/alegra
- **Authentication:** x-api-key header matching ALEGRA_WEBHOOK_SECRET
- **Events Handled:**
  - new-invoice, edit-invoice, delete-invoice (sales invoices)
  - new-bill, edit-bill, delete-bill (purchase invoices)
  - new-client, edit-client, delete-client (customer records)
  - new-item, edit-item, delete-item (products/services)
- **Processing:** Async background task (responds <1s, processes in background)
- **Auto-Creation:** Creates loanbook records from invoices when VIN/chasis detected
- **Backend File:** `/backend/routers/alegra_webhooks.py`

**Mercately Webhooks:**
- **Endpoint:** POST /api/mercately/webhook
- **Authentication:** None required (public)
- **Message Types:** CLIENTE, INTERNO, DESCONOCIDO
- **Intent Detection:** Automatic intent classification for payment/balance/difficulty queries
- **Backend File:** `/backend/routers/mercately.py`

**Telegram Webhooks:**
- **Endpoint:** POST /api/telegram/webhook
- **Authentication:** None required (public)
- **Message Types:** Text messages with optional photo attachments
- **Processing:** Document analysis with Claude AI
- **Backend File:** `/backend/routers/telegram.py`

**Outgoing Webhooks:**

**Alegra Webhook Setup:**
- **Endpoint:** POST /api/webhooks/setup
- **Purpose:** Subscribe to 12 Alegra events
- **Configuration:** Requires ALEGRA_EMAIL and ALEGRA_TOKEN

**Status/Health:**
- **Endpoint:** GET /api/webhooks/status
- **Purpose:** List active subscriptions and cron job status

**Scheduled Sync Tasks:**
- Payment synchronization cron job (frequency determined by scheduler)
- Polling fallback when webhooks unavailable
- Backend Files: `/backend/services/scheduler.py`, `/backend/services/loanbook_scheduler.py`

## Integration Patterns

**Async Processing:**
- Alegra webhooks use BackgroundTasks to process events asynchronously
- Immediate response (<1s) to webhook, processing in background
- All API calls via httpx async client

**Data Sync:**
- Alegra → MongoDB: Automatic sync on webhook events
- MongoDB → Alegra: Manual and automatic (on loanbook actions like payment)
- MongoDB → PDF/Excel: Export for reports via jsPDF and xlsx libraries

**Document Processing Pipeline:**
1. User uploads (Telegram, web, API) or Alegra webhook
2. PDF/Excel/CSV → Claude AI analysis
3. Accounting entry proposed to user
4. User confirmation
5. Automatic sync to Alegra if enabled

**Error Handling:**
- Webhook events logged to `roddos_events` collection regardless of processing success
- Demo mode fallback when Alegra credentials unavailable
- Background task failures logged but don't block webhook response

---

*Integration audit: 2026-03-24*
