# Architecture

**Analysis Date:** 2026-03-24

## Pattern Overview

**Overall:** Layered Client-Server with Domain-Driven Feature Modules

**Key Characteristics:**
- FastAPI backend with MongoDB for persistence
- React 19 frontend with React Router for navigation
- Microservices-like router organization (each feature owns its API endpoint)
- Async/await patterns throughout (Motor for async MongoDB, async FastAPI handlers)
- Service layer abstractions for business logic (accounting engine, scheduling, CRM)
- Context-based state management on frontend (React Context + localStorage)
- Event bus for cross-module communication (emit_event pattern)

## Layers

**API/Transport Layer:**
- Purpose: HTTP endpoints, request/response validation, authentication enforcement
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/server.py` (FastAPI app), `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/routers/` (endpoint handlers)
- Contains: Router modules for each domain (chat, loanbook, alegra, inventory, taxes, etc.)
- Depends on: Service layer, database, dependencies (auth guards)
- Used by: Frontend via HTTP/axios

**Business Logic / Service Layer:**
- Purpose: Core algorithms and domain operations (accounting classification, scheduling, CRM)
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/` (accounting_engine.py, cfo_agent.py, scheduler.py, loanbook_scheduler.py, etc.)
- Contains:
  - `accounting_engine.py` - Transaction classification to Alegra accounts
  - `cfo_agent.py` - CFO decision engine (cash flow, sustainability indicators)
  - `scheduler.py`, `loanbook_scheduler.py` - Periodic task execution
  - `bank_reconciliation.py` - Bank extract matching
  - `learning_engine.py` - Agent memory/training data
- Depends on: Database, Alegra SDK, LLM APIs (Anthropic/LiteLLM)
- Used by: Routers, background schedulers, chat processing

**AI Integration Layer:**
- Purpose: LLM orchestration, prompt building, structured outputs
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/ai_chat.py`, `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/cfo_agent.py`
- Contains:
  - Multi-message conversation handling
  - File processing (CSV/Excel tabular data)
  - Tool/action execution from LLM responses
  - Context builders with financial/business data
  - Error handling with agent diagnostics
- Depends on: Anthropic SDK, MongoDB for session/message history
- Used by: Chat router, CFO strategic module

**Data Access Layer:**
- Purpose: MongoDB persistence, connection pooling
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/database.py`
- Contains: Motor async client initialization, collection references (users, loanbooks, audit_logs, agent_errors, etc.)
- Depends on: Motor (async MongoDB driver), environment configuration
- Used by: All routers, services, schedulers

**Frontend Pages Layer:**
- Purpose: Feature-specific page components with data fetching and UI
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/pages/`
- Contains:
  - `AgentChatPage.tsx` - Main AI chat interface
  - `Dashboard.tsx` - Business KPIs (sales, cash, cartera)
  - `Loanbook.tsx` - Motorcycle payment plan management
  - `CFOEstrategico.tsx` - Strategic CFO analytics
  - `CFO.tsx` - Operational CFO dashboard
  - `CRMList.tsx`, `CRMCliente.tsx` - Client management
  - `Inventory*.tsx`, `Impuestos.tsx`, etc. - Domain-specific pages
- Depends on: React Context (auth, alegra), API (useAuth().api)
- Used by: Router at App level

**Frontend Component Layer:**
- Purpose: Reusable UI elements and business component composition
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/components/`
- Contains:
  - `shared/` - Domain-specific (RadarCard, GestionModal, BucketBadge, ScoreBadge)
  - `ui/` - Low-level inputs (button, dialog, input, tabs, textarea, etc.)
  - Top-level components like Layout, FiltroFecha
- Depends on: Radix UI, Lucide React icons, Tailwind CSS
- Used by: Pages, other components

**State Management:**
- Purpose: Application authentication state and Alegra integration
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/contexts/`
- Contains:
  - `AuthContext.tsx` - User session, JWT token, axios instance with auth interceptor
  - `AlegraContext.tsx` - Accounting system integration state
- Depends on: localStorage, axios
- Used by: All pages via useAuth() and useAlegra() hooks

## Data Flow

**Chat/Agent Flow:**

1. User submits message in `AgentChatPage.tsx`
2. Message sent via `useAuth().api.post("/api/chat/message")`
3. Backend `routers/chat.py` routes to `ai_chat.process_chat()`
4. `ai_chat.py` builds context (financial data from MongoDB, file parsing)
5. Calls Anthropic LLM with system prompt + message
6. LLM responds with action(s) or analysis
7. `execute_chat_action()` handles action execution (save to DB, call external APIs)
8. Response with success/error returned to frontend
9. Message history stored in `agent_sessions` collection for context

**Loanbook Payment Plan Flow:**

1. Create plan via `Loanbook.tsx` form → `POST /api/loanbook/create`
2. `routers/loanbook.py::create_loanbook()` validates and stores in `loanbooks` collection
3. Calculates cuotas based on plan type (Contado/P39S/P52S/P78S) and payment frequency
4. `loanbook_scheduler.py` runs periodically:
   - Detects overdue payments
   - Emits radar events for collection activities
   - Syncs to Alegra for accounting integration
5. User records payment via modal → `POST /api/loanbook/{id}/pago`
6. Updates cuota status, recalculates schedule, triggers re-scheduling
7. Gestión (collection activity) recorded → `POST /api/loanbook/{id}/gestion`

**Financial Data Flow:**

1. Bank extract uploaded via `CargarExtraacto.tsx` → `POST /api/chat/message` with file
2. `ai_chat._tabular_to_text()` parses CSV/Excel
3. `accounting_engine.py` classifies each transaction:
   - Extracts proveedor name
   - Applies priority algorithm (socio > tech > interests > GMF > otros)
   - Returns classification with confidence score
4. LLM confirms or adjusts classifications
5. Confirmed entries stored in `accounting_entries` collection
6. Finance reports aggregate data (Estado Resultados, Gastos, Ventas, Cartera)

**Dashboard Update Flow:**

1. `Dashboard.tsx` mounts, calls APIs for:
   - `/api/dashboard/semaforo` - CFO status indicators
   - `/api/dashboard/radar` - Collection metrics
   - `/api/dashboard/kpis` - Inventory, sales, cash
   - `/api/cfo/indicadores` - Sustainability metrics
2. Results aggregated with timestamps, stored in `shared_state` (MongoDB)
3. Frontend polls or subscribes (currently polling every 30-60s)
4. RadarCard renders with color-coded status

**Scheduler Background Tasks:**

1. `services/scheduler.py` starts on app startup (`server.py::startup()`)
2. Periodic tasks execute:
   - Alegra sync (new transactions, invoice updates)
   - Loanbook overdue detection
   - Financial calculations
   - Telegram notifications for alerts
3. Tasks log to MongoDB for audit/diagnostics
4. Events emitted via `event_bus.py` for cross-module notification

**State Management:**

- Authentication: JWT in localStorage (`roddos_token`), verified on each API request
- Auth Context maintains user object and axios instance with Bearer token interceptor
- Alegra credentials stored server-side in `user_settings` collection
- Shared state (KPIs, semaforo) cached in MongoDB with TTL, frontend polls

## Key Abstractions

**Router Pattern:**
- Purpose: Organize endpoints by domain (cada router es un módulo de negocio)
- Examples: `routers/chat.py`, `routers/loanbook.py`, `routers/alegra.py`, `routers/cfo_estrategico.py`
- Pattern: Each router defines Pydantic models for validation, async endpoint handlers, calls service layer
- Adding new feature: Create `routers/new_feature.py`, define models + endpoints, import in `server.py`

**Service Abstraction:**
- Purpose: Decouple business logic from HTTP/DB details
- Examples: `AccountingEngine`, `CfoAgent`, `LoanBookScheduler`, `BankReconciliation`
- Pattern: Class-based with methods that take db/context params, return typed results
- Benefit: Services can be called from routers, schedulers, or other services

**Alegra Integration:**
- Purpose: Two-way sync with external accounting system
- Examples: `alegra_service.py` (main client), `services/accounting_engine.py` (classification)
- Pattern: Wrapper around Alegra REST API, caches account mappings, handles auth
- Data flow: Bank transactions → Accounting Engine → Alegra Journal Entries

**LLM Orchestration:**
- Purpose: Multi-turn conversation with tools
- Location: `ai_chat.py`, `services/cfo_agent.py`
- Pattern: Build context dict → send to LLM → parse actions → execute → loop
- Tool execution: Actions like "save_account_mapping", "create_plan", etc.

**Event Bus:**
- Purpose: Decouple modules via event publishing (emit_event)
- Examples: Loanbook emits "payment_received", Chat emits "accounting_updated"
- Pattern: Simple in-process event dispatch (not message queue)
- Used for: Notifications, cross-feature triggers

## Entry Points

**Backend Entry Point:**
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/server.py`
- Triggers: `uvicorn backend.server:app --reload` or production deployment
- Responsibilities:
  - Initialize FastAPI app
  - Register CORS middleware
  - Load all routers
  - Start/stop schedulers on startup/shutdown
  - Run initial migrations (v24)

**Frontend Entry Point:**
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/App.tsx`
- Triggers: Browser load of `/`
- Responsibilities:
  - Wrap app in AuthProvider and AlegraProvider
  - Define route structure (BrowserRouter)
  - ProtectedRoute guard for authentication
  - Route to pages or redirect to login

**Router Entry:**
- Pattern: Each router file in `routers/` defines APIRouter with prefix
- Examples:
  - `chat.py` → `POST /api/chat/message`, `POST /api/chat/execute-action`
  - `loanbook.py` → `GET/POST /api/loanbook/...`
  - `alegra.py` → `GET /api/alegra/accounts`, `POST /api/alegra/sync`

## Error Handling

**Strategy:** Multi-level error capture with context-specific messaging

**Patterns:**

1. **Router Level** (`routers/chat.py`):
   - Catch all exceptions, log with user context
   - Log to `agent_errors` collection for diagnostics
   - Return HTTPException with user-friendly detail message
   - Categorize by error source (LLM, DB, external API)

2. **Service Level** (`services/*.py`):
   - Raise ValueError for validation, HTTPException for auth/forbidden
   - Let database/network errors bubble with context

3. **Frontend Level** (`contexts/AuthContext.tsx`):
   - Catch 401 responses → redirect to login
   - Display error toast via Sonner for user feedback
   - Retry logic on specific status codes (503, timeouts)

4. **Async Task Level** (`services/scheduler.py`):
   - Wrap each task in try/catch
   - Log failures without stopping scheduler
   - Emit alert events on critical failures

## Cross-Cutting Concerns

**Logging:**
- Backend: Python logging module with console output, structured logs to MongoDB (agent_errors, audit_logs)
- Frontend: Console.error for React errors, API errors caught in context

**Validation:**
- Backend: Pydantic BaseModel for all request bodies + manual validation in handlers
- Frontend: React Hook Form with Zod schemas on major forms (Loanbook creation, CRM updates)

**Authentication:**
- Backend: JWT tokens (7-day expiry), verified via `dependencies.get_current_user()`
- Frontend: Token stored in localStorage, refreshed via login, auto-logout on 401

**Authorization:**
- Backend: Role-based checks via `require_admin` dependency on sensitive endpoints
- Audit logging: All actions logged with user_id, endpoint, timestamp, request body

