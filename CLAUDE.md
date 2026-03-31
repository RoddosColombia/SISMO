<!-- GSD:project-start source:PROJECT.md -->
## Project

**SISMO — Sistema Inteligente de Soporte y Monitoreo Operativo**

Plataforma de orquestacion de agentes IA especializados para automatizar las operaciones completas de RODDOS S.A.S., fintech de movilidad sostenible en Bogota, Colombia. Financia motocicletas con cobro 100% remoto (WhatsApp + transferencias). Equipo pequeno (2-5 personas) gestiona 10 loanbooks activos, cartera de $94M COP, 34 motos TVS con VINs reales.

**Core Value:** Contabilidad automatizada sin intervencion humana (cada operacion financiera reflejada correctamente en Alegra) + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos.

### Constraints

- **Tech stack**: FastAPI + React 19 + MongoDB Atlas — ya en produccion, no migrar
- **Integraciones**: Alegra es el sistema contable de record — toda operacion contable pasa por Alegra API
- **LLM**: Claude Sonnet via Anthropic SDK — ya integrado en ai_chat.py y cfo_agent.py
- **WhatsApp**: Mercately como proveedor — webhooks ya configurados
- **Produccion**: Sistema en uso real con datos financieros reales — no romper funcionalidad existente
- **Idioma**: Interfaz y datos en espanol (Colombia)
- **Principio rector**: Soberania Digital — ninguna plataforma de terceros debe ser duena del corazon operativo
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- TypeScript 5.9.3 - Frontend application (React + React Router)
- Python 3.11.0 - Backend API server (FastAPI)
- JavaScript - Frontend tooling and configuration
## Runtime
- Node.js (yarn package manager) - v1.22.22+sha512
- React 19.0.0 - UI framework with React Router 7.5.1
- React Scripts 5.0.1 - Build and development server
- Python 3.11.0 (specified in render.yaml)
- uvicorn 0.25.0 - ASGI server
- Motor 3.7.0 - Async MongoDB driver
## Frameworks
- **FastAPI** 0.110.1 - Backend REST API framework
- **React** 19.0.0 - Frontend UI framework
- **Radix UI** (comprehensive set of v1.x components) - Headless component library
- **Tailwind CSS** 3.4.17 - Utility-first CSS framework
- **Tailwindcss-animate** 1.0.7 - Animation utilities
- **Autoprefixer** 10.4.20 - CSS vendor prefix auto-injection
- **React Hook Form** 7.56.2 - Form state management
- **Zod** 3.24.4 - TypeScript-first schema validation
- @hookform/resolvers 5.0.1 - Integration between Hook Form and Zod
- **class-variance-authority** 0.7.1 - Type-safe CSS component variants
- **Craco** 7.1.0 - Create React App configuration overrides
- **TypeScript** 5.9.3 - Type checking
- **ESLint** 9.23.0 - Code linting
- **Autoprefixer** 10.4.20 - CSS processing
- **PostCSS** 8.4.49 - CSS transformations
## Key Dependencies
- **pymongo** 4.9.2 - MongoDB Python driver (synchronous)
- **motor** 3.7.0 - Async MongoDB driver
- **pydantic** 2.7.1 - Data validation and serialization
- **python-jose** 3.3.0 - JWT token generation/validation
- **bcrypt** 4.1.2 - Password hashing
- **passlib** 1.7.4 - Password hashing framework
- **PyJWT** 2.8.0 - JWT library
- **anthropic** 0.34.0 - Claude API client for AI chat and document analysis
- EMERGENT_LLM_KEY - Custom LLM integration (key-based)
- **httpx** 0.27.0 - Async HTTP client (Alegra, Mercately, Telegram, DIAN APIs)
- **requests** 2.32.3 - HTTP client for synchronous requests
- **aiohttp** 3.9.5 - Alternative async HTTP client
- **apscheduler** 3.10.4 - Advanced job scheduling for background tasks
- **openpyxl** 3.1.5 - Excel file reading/writing
- **pandas** 2.2.2 - Tabular data analysis
- **pdfplumber** 0.11.0 - PDF text extraction
- **python-dateutil** 2.9.0 - Date utilities
- **pytz** 2024.1 - Timezone utilities
- **pyotp** 2.9.0 - TOTP/HOTP one-time password generation
- **qrcode** 7.4.2 - QR code generation for 2FA
- **cryptography** 43.0.1 - Cryptographic operations
- **python-dotenv** 1.0.1 - .env file loading
- **python-multipart** 0.0.9 - Form and file upload parsing
- **xlsx** 0.18.5 - Excel file parsing and generation
- **date-fns** 4.1.0 - Date formatting and manipulation
- **react-day-picker** 8.10.1 - Date picker component
- **jspdf** 4.2.0 - PDF generation from HTML/DOM
- **jspdf-autotable** 5.0.7 - Automatic table formatting for jsPDF
- **axios** 1.8.4 - HTTP client for API calls
- **recharts** 3.6.0 - Charting library built on React
- **embla-carousel-react** 8.6.0 - Carousel/slider component
- **lucide-react** 0.507.0 - Icon library
- **cmdk** 1.1.1 - Command/search palette component
- **input-otp** 1.4.2 - OTP input component
- **react-markdown** 10.1.0 - Markdown rendering
- **sonner** 2.0.3 - Toast notification library
- **react-resizable-panels** 3.0.1 - Resizable panel layout
- **vaul** 1.1.2 - Sheet/drawer component
- **tailwind-merge** 3.2.0 - Merge Tailwind classes intelligently
- **clsx** 2.1.1 - Conditional className utility
- **next-themes** 0.4.6 - Theme management (light/dark mode)
- **@dnd-kit/core** 6.3.1 - Headless drag-drop library
- **@dnd-kit/sortable** 10.0.0 - Sortable preset
- **@dnd-kit/utilities** 3.2.2 - Utility functions
- **@emergentbase/visual-edits** 1.0.8 - Visual code editor integration
## Configuration
- `tsconfig.json` - TypeScript configuration (target: ES5, strict: false)
- `craco.config.js` - Create React App configuration overrides
- `.env.production` - Production build settings
- `MONGO_URL` - MongoDB Atlas connection string (mongodb+srv://...)
- `DB_NAME` - Database name (default: "sismo")
- `ALEGRA_EMAIL` - Alegra accounting software credentials
- `ALEGRA_TOKEN` - Alegra API token
- `ALEGRA_WEBHOOK_SECRET` - Webhook validation token (default: "roddos-webhook-2026")
- `JWT_SECRET` - JWT signing secret (default: "roddos-jwt-secret-2025-secure")
- `ANTHROPIC_API_KEY` - Claude API key for AI features
- `EMERGENT_LLM_KEY` - Alternative/internal LLM provider key
- `APP_URL` - Application public URL (for Alegra webhook callbacks)
- `REACT_APP_BACKEND_URL` - Backend API base URL (e.g., http://localhost:8000 or production URL)
- `ALEGRA_USER` - Alternate Alegra authentication (some legacy usage)
- `MERCATELY_API_URL` - WhatsApp integration endpoint
- `TELEGRAM_API_TOKEN` - Telegram bot token
- `ENABLE_HEALTH_CHECK` - Enable webpack health check plugin in frontend
## Platform Requirements
- Node.js with Yarn 1.22.22+
- Python 3.11.0+
- MongoDB Atlas account (or local MongoDB)
- Git for version control
- Render.com (specified in render.yaml) or compatible Python hosting
- MongoDB Atlas (or compatible MongoDB service)
- Environment variable configuration for all API keys and credentials
## Database
- **MongoDB** (atlas) - Document database via Motor async driver
- Collections:
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Components: PascalCase (e.g., `FiltroFecha.tsx`, `AgentChatPage.tsx`, `BucketBadge.tsx`)
- Utilities: camelCase (e.g., `formatters.js`, `descargar.ts`, `exportUtils.js`)
- Contexts: PascalCase with "Context" suffix (e.g., `AuthContext.tsx`, `AlegraContext.tsx`)
- Hooks: camelCase with "use" prefix (e.g., `useRadarQueue.ts`, `useSharedState.ts`)
- Services: camelCase (e.g., `alegra_service.py`, `inventory_service.py`, `security_service.py`)
- Tests: prefix with `test_` or match source file name (e.g., `test_build21_integration.py`, `test_roddos_backend.py`)
- React components: PascalCase (e.g., `FiltroFecha()`, `ProtectedRoute()`, `App()`)
- JavaScript/TypeScript utilities: camelCase (e.g., `formatCOP()`, `formatDate()`, `descargarArchivo()`)
- Python functions: snake_case (e.g., `hash_password()`, `verify_token()`, `_detectar_tipo_proveedor()`)
- Internal/private functions: prefix with `_` (e.g., `_is_gastos_csv()`, `_detectar_identificacion()`)
- Async functions: same naming, clearly prefixed with `async` (e.g., `async def get_settings()`)
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_PRESET_ID`, `ALEGRA_BASE_URL`, `EXPIRE_HOURS`)
- Local variables: camelCase in JS/TS (e.g., `customDesde`, `customHasta`, `moduleKey`)
- Database variables: snake_case (e.g., `mongo_url`, `db_name`, `cache_key`)
- State variables: camelCase in React (e.g., `open`, `custom`, `loading`)
- TypeScript: PascalCase (e.g., `User`, `DateRange`, `Props`, `AuthContextType`)
- Union types with "Type" or "Result" suffix (e.g., `LoginResult`, `TareaActiva`)
- Pydantic models: PascalCase with suffix (e.g., `UserModel`, `LoginRequest`, `ChatMessageRequest`)
- Discriminated unions: use `type` field (e.g., `type: "pl_export_card"`)
## Code Style
- Frontend: Tailwind CSS for all styling, inline utility classes (no separate CSS files for components)
- Backend: 4-space indentation (Python standard)
- Line length: Generally follows project defaults, but pragmatic about readability
- Quote style: Double quotes in TypeScript/JavaScript, single quotes acceptable in Python strings
- Semicolons: Used consistently in TypeScript (enforced by config)
- Frontend ESLint rules configured in `craco.config.js`:
- Backend: No strict linting enforced, but follows PEP8 conventions pragmatically
- No prettier/ESLint rc files found — config via `craco.config.js` and `tsconfig.json`
## Import Organization
- Frontend TypeScript: `@/*` maps to `src/` (configured in `tsconfig.json`)
- Backend: Relative imports, no aliases (flat structure with optional `sys.path` manipulation in test files)
## Error Handling
- HTTP errors caught in interceptors or try/catch blocks
- Auth errors (401) trigger redirect to `/login` with session flag to prevent redirect storms (see `AuthContext.tsx`)
- API errors often fail silently with fallback UI or toast notifications (see `useRadarQueue.ts`: `catch { // fail silently }`)
- Custom error messages for user-facing operations (see `descargar.ts`: detailed error messages in Spanish)
- File operations: explicit null/undefined checks before operations (e.g., `if (!customDesde || !customHasta) return`)
- HTTP exceptions from FastAPI: `raise HTTPException(status_code=, detail=)`
- Token verification: returns `None` on failure, caller checks (see `verify_token()`, `verify_temp_token()`)
- Database operations: wrapped in try/except, logged with context
- Service methods: return `None` on not-found conditions (see `get_cuenta_roddos()`)
- CSV parsing: explicit exception catch with fallback message (see `_parse_csv()`)
## Logging
- Frontend: `console.log()`, `console.error()` via browser console, toast notifications via `sonner`
- Backend: Python `logging` module with logger per module (`logger = logging.getLogger(__name__)`)
- Frontend: Use `toast()` from sonner for user-visible notifications
- Backend: Log with context:
- Debug logging: rarely used, prefer explicit error handling
- No structured logging (Sentry, etc.) detected
## Comments
- Complex algorithms: explain the "why" (e.g., date arithmetic, validation logic)
- Business logic assumptions: document domain rules (e.g., IVA calculations, Colombian accounting standards)
- Temporary workarounds: use TODO/FIXME tags (e.g., `// TODO: type - payload structure varies by action type`)
- Integration quirks: explain API behavior differences (e.g., real Alegra vs mock data, field naming variations)
- Used selectively, not pervasively
- Component interfaces documented with JSDoc comments (e.g., `/** FiltroFecha — Reusable date range selector for RODDOS. */`)
- Function parameters rarely documented; types provide clarity via TypeScript
- Example from `FiltroFecha.tsx`:
- Short, uppercase sections with dashes (e.g., `/* ── types ── */`, `/* ── constants ── */`)
- Explain non-obvious state transitions (e.g., auth redirect logic in `AuthContext.tsx`)
- Clarify integration assumptions (e.g., mock vs real Alegra data handling)
## Function Design
- React components: typically 50-200 lines (includes JSX)
- Utility functions: 5-30 lines (keep focused)
- Service methods: vary widely (10-50 lines typical, up to 100+ for complex logic)
- Large functions: acceptable if cohesive (e.g., `execute_chat_action()` in `ai_chat.py` spans 5200+ lines but handles specific domain logic)
- React components: destructured props interface (e.g., `const FiltroFecha: React.FC<Props> = ({ moduleKey, onChange, compact })`)
- Utility functions: typically 1-3 parameters, optional parameters last
- API endpoints: Request models for body payload validation
- Async operations: callbacks for async results (e.g., `onError?: (msg: string) => void`)
- React components: JSX or null
- Utilities: explicit single return type (not multiple types)
- API handlers: Pydantic models or FastAPI responses
- Async operations: boolean success indicator common (`Promise<boolean>`)
- Database queries: single item or list, `None` for not-found
## Module Design
- Components: default export (e.g., `export default FiltroFecha`)
- Utilities: named exports (e.g., `export function formatCOP()`)
- Hooks: named exports (e.g., `export function useAuth()`)
- Contexts: both default (provider component) and named (hook) exports
- Python modules: service classes or functions, imported by name
- Not used explicitly
- UI components in `components/ui/` appear to be auto-generated from shadcn/ui (`.d.ts` files present)
- No `index.ts` barrel exports observed in src directories
- `contexts/`: State management (Auth, Alegra credentials)
- `components/`: UI components (shared, pages, ui)
- `hooks/`: React hooks for custom logic
- `utils/`: Pure utility functions (formatting, downloads, exports)
- `pages/`: Page-level components (routed views)
- Backend `routers/`: FastAPI route handlers, organized by domain (auth, alegra, chat, inventory, etc.)
- Backend services: Business logic classes and functions
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- FastAPI backend with MongoDB for persistence
- React 19 frontend with React Router for navigation
- Microservices-like router organization (each feature owns its API endpoint)
- Async/await patterns throughout (Motor for async MongoDB, async FastAPI handlers)
- Service layer abstractions for business logic (accounting engine, scheduling, CRM)
- Context-based state management on frontend (React Context + localStorage)
- Event bus for cross-module communication (emit_event pattern)
## Layers
- Purpose: HTTP endpoints, request/response validation, authentication enforcement
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/server.py` (FastAPI app), `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/routers/` (endpoint handlers)
- Contains: Router modules for each domain (chat, loanbook, alegra, inventory, taxes, etc.)
- Depends on: Service layer, database, dependencies (auth guards)
- Used by: Frontend via HTTP/axios
- Purpose: Core algorithms and domain operations (accounting classification, scheduling, CRM)
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/` (accounting_engine.py, cfo_agent.py, scheduler.py, loanbook_scheduler.py, etc.)
- Contains:
- Depends on: Database, Alegra SDK, LLM APIs (Anthropic/LiteLLM)
- Used by: Routers, background schedulers, chat processing
- Purpose: LLM orchestration, prompt building, structured outputs
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/ai_chat.py`, `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/cfo_agent.py`
- Contains:
- Depends on: Anthropic SDK, MongoDB for session/message history
- Used by: Chat router, CFO strategic module
- Purpose: MongoDB persistence, connection pooling
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/database.py`
- Contains: Motor async client initialization, collection references (users, loanbooks, audit_logs, agent_errors, etc.)
- Depends on: Motor (async MongoDB driver), environment configuration
- Used by: All routers, services, schedulers
- Purpose: Feature-specific page components with data fetching and UI
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/pages/`
- Contains:
- Depends on: React Context (auth, alegra), API (useAuth().api)
- Used by: Router at App level
- Purpose: Reusable UI elements and business component composition
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/components/`
- Contains:
- Depends on: Radix UI, Lucide React icons, Tailwind CSS
- Used by: Pages, other components
- Purpose: Application authentication state and Alegra integration
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/contexts/`
- Contains:
- Depends on: localStorage, axios
- Used by: All pages via useAuth() and useAlegra() hooks
## Data Flow
- Authentication: JWT in localStorage (`roddos_token`), verified on each API request
- Auth Context maintains user object and axios instance with Bearer token interceptor
- Alegra credentials stored server-side in `user_settings` collection
- Shared state (KPIs, semaforo) cached in MongoDB with TTL, frontend polls
## Key Abstractions
- Purpose: Organize endpoints by domain (cada router es un módulo de negocio)
- Examples: `routers/chat.py`, `routers/loanbook.py`, `routers/alegra.py`, `routers/cfo_estrategico.py`
- Pattern: Each router defines Pydantic models for validation, async endpoint handlers, calls service layer
- Adding new feature: Create `routers/new_feature.py`, define models + endpoints, import in `server.py`
- Purpose: Decouple business logic from HTTP/DB details
- Examples: `AccountingEngine`, `CfoAgent`, `LoanBookScheduler`, `BankReconciliation`
- Pattern: Class-based with methods that take db/context params, return typed results
- Benefit: Services can be called from routers, schedulers, or other services
- Purpose: Two-way sync with external accounting system
- Examples: `alegra_service.py` (main client), `services/accounting_engine.py` (classification)
- Pattern: Wrapper around Alegra REST API, caches account mappings, handles auth
- Data flow: Bank transactions → Accounting Engine → Alegra Journal Entries
- Purpose: Multi-turn conversation with tools
- Location: `ai_chat.py`, `services/cfo_agent.py`
- Pattern: Build context dict → send to LLM → parse actions → execute → loop
- Tool execution: Actions like "save_account_mapping", "create_plan", etc.
- Purpose: Decouple modules via event publishing (emit_event)
- Examples: Loanbook emits "payment_received", Chat emits "accounting_updated"
- Pattern: Simple in-process event dispatch (not message queue)
- Used for: Notifications, cross-feature triggers
## Entry Points
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/server.py`
- Triggers: `uvicorn backend.server:app --reload` or production deployment
- Responsibilities:
- Location: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/App.tsx`
- Triggers: Browser load of `/`
- Responsibilities:
- Pattern: Each router file in `routers/` defines APIRouter with prefix
- Examples:
## Error Handling
## Cross-Cutting Concerns
- Backend: Python logging module with console output, structured logs to MongoDB (agent_errors, audit_logs)
- Frontend: Console.error for React errors, API errors caught in context
- Backend: Pydantic BaseModel for all request bodies + manual validation in handlers
- Frontend: React Hook Form with Zod schemas on major forms (Loanbook creation, CRM updates)
- Backend: JWT tokens (7-day expiry), verified via `dependencies.get_current_user()`
- Frontend: Token stored in localStorage, refreshed via login, auto-logout on 401
- Backend: Role-based checks via `require_admin` dependency on sensitive endpoints
- Audit logging: All actions logged with user_id, endpoint, timestamp, request body
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

### ERRORES DOCUMENTADOS — SISMO RODDOS
### Última actualización: 26 de marzo 2026

### ERROR-001: Worktrees GSD sobreescriben código en merges
- Síntoma: correcciones desaparecían con cada deploy
- Causa: GSD crea ramas separadas. Cherry-pick en orden incorrecto sobrescribe commits anteriores
- Prevención: GSD solo para discuss+plan. Ejecución SIEMPRE directo en main. NUNCA confiar en worktrees para código crítico

### ERROR-002: catalogo_planes se vaciaba en cada redeploy
- Síntoma: "Plan no encontrado" después de cada deploy
- Causa: seed usaba delete_many() + insert_many(). En cold start borraba todo antes de reinsertar
- Prevención: Siempre upsert idempotente, nunca delete+reinsert en seeds

### ERROR-003: Loanbooks legacy sin campo id UUID
- Síntoma: PUT /loanbook retornaba 500 para LB-0001 al LB-0010
- Causa: docs legacy solo tenían _id ObjectId. Frontend enviaba undefined al usar .id
- Prevención: Todo doc MongoDB debe tener campo id. GET sintetiza id si no existe

### ERROR-004: ACTION_MAP llamaba Alegra directo (no endpoint interno)
- Síntoma: agente decía éxito pero no había factura, loanbook ni inventario
- Causa: service.request("ventas/crear-factura") intentaba llamar api.alegra.com — no existe
- Prevención: ACTION_MAP SIEMPRE a endpoints internos SISMO. Nunca a Alegra directo. Import directo from routers.*

### ERROR-005: Regla del Miércoles calculada como +7 días exactos
- Síntoma: RADAR mostraba 2 de 11 loanbooks. Fechas incorrectas
- Causa: implementada como fecha_entrega+7. Correcto es semana siguiente calendario
- Prevención: calcular_primer_cobro() usa semana calendario, no días exactos

### ERROR-006: tipo_identificacion ignorado — siempre salía CC
- Síntoma: cliente PPT se creaba como CC en Alegra
- Causa: ventas.py no tenía mapeo completo PPT/CE/PAS/TI. Default era CC
- Prevención: tipo_identificacion obligatorio HTTP 400 si falta. Mapeo completo: CC/CE/PPT/PAS/NIT/TI

### ERROR-007: LLM calcula valor_cuota dividiendo precio/cuotas
- Síntoma: cuota P78S mostraba $65.345 en vez de $149.900
- Causa: LLM recibe precio_venta + num_cuotas y calcula. Ignora el catálogo de planes
- Prevención: ventas.py sobrescribe valor_cuota desde catalogo_planes en Python ANTES del LLM. NUNCA calcular cuota desde precio — siempre leer de catalogo_planes MongoDB

### ERROR-008: Endpoint /journal-entries da 403 — debe ser /journals
- Síntoma: 403 silencioso. El sistema reportaba fallo de auth cuando era el endpoint incorrecto
- Causa: Alegra tiene dos endpoints de comprobantes. /journal-entries retorna 403 sin mensaje claro
- Prevención: SIEMPRE usar /journals para comprobantes. NUNCA /journal-entries. Costó un build completo descubrirlo

### ERROR-009: ID 5495 usado como fallback — causó 143 journals en cuenta incorrecta
- Síntoma: 143 asientos de enero 2026 en cuenta incorrecta. Limpieza manual de Alegra
- Causa: fallback del plan de cuentas apuntaba a ID 5495 (Gastos de Representación) en vez de 5493
- Prevención: Fallback correcto SIEMPRE es ID 5493 (Gastos Generales). NUNCA 5495. plan_cuentas_roddos es la única fuente de verdad. Nunca IDs hardcodeados

### ERROR-010: BackgroundTasks sin job_id en lotes > 10 — timeout silencioso reporta éxito falso
- Síntoma: "Procesados exitosamente" pero al verificar en Alegra solo había 3 de 50 registros
- Causa: operaciones síncronas masivas agotan timeout. HTTP response enviado antes de completar
- Prevención: BackgroundTasks + job_id OBLIGATORIO para cualquier lote > 10 registros. Estado del job en MongoDB. Nunca operaciones síncronas masivas

### ERROR-011: Anti-duplicados faltantes — 176 journals duplicados en Alegra
- Síntoma: 176 journals del mismo valor en Alegra. Limpieza manual tardó 2 horas
- Causa: el sistema reintentaba sin verificar si el primer intento había funcionado parcialmente
- Prevención: Anti-duplicados en 3 capas — (1) hash MD5 extracto completo, (2) hash MD5 movimiento individual, (3) GET verificación en Alegra post-POST

### ERROR-012: IVA configurado como bimestral — debe ser cuatrimestral
- Síntoma: cálculos de IVA acumulado incorrectos. Calendario fiscal con fechas equivocadas
- Causa: configuración inicial usaba períodos bimestrales
- Prevención: IVA SIEMPRE cuatrimestral para régimen ordinario Colombia. Períodos: ene-abr / may-ago / sep-dic

### ERROR-013: CFO cache sin invalidación inmediata al registrar operaciones
- Síntoma: dashboard CFO mostraba datos incorrectos hasta 36 segundos después de registrar pagos
- Causa: CFO leía de caché TTL 30s incluso después de escrituras contables
- Prevención: emit_state_change() invalida cfo_cache SIEMPRE e INMEDIATAMENTE después de cualquier escritura en Alegra

### ERROR-014: VIN y motor no obligatorios en factura de venta de moto
- Síntoma: motos vendidas seguían apareciendo como Disponibles. Riesgo de doble venta
- Causa: endpoint de ventas no validaba obligatoriedad de chasis y motor
- Prevención: VIN y motor OBLIGATORIOS en toda factura de moto. HTTP 400 si faltan. Formato: "[Modelo] [Color] - VIN: [chasis] / Motor: [motor]"

### ERROR-015: Router sin confidence threshold — identidades mezcladas entre agentes
- Síntoma: el CFO respondía mensajes del Contador. RADAR respondía preguntas de loanbook
- Causa: process_chat() despachaba sin verificar confianza en el intent
- Prevención: threshold mínimo 0.70 antes de despachar. Si confianza < 0.70 → preguntar clarificación. NUNCA despachar a agente incorrecto

## Event Bus Protocol (BUILD 24)

Use `bus.emit()` for ALL event publishing. The old patterns are DELETED:
- `emit_event()` — REMOVED, do not use
- `emit_state_change()` — REMOVED from shared_state.py
- `from backend.event_bus import` — REMOVED, file deleted

Correct pattern:
```python
from services.event_bus_service import EventBusService

bus = EventBusService(db)
await bus.emit(
    event_type="payment_received",   # Must be in EVENT_TYPES catalog
    agent="loanbook",                # Agent name
    payload={"loanbook_id": "...", "amount": 150000},
    source="routers/loanbook.py"
)
```

Key rules:
- event_type MUST be one of the 28 types in `backend/models/event_models.py` EVENT_TYPES
- Failed emits go to DLQ (roddos_events_dlq), never block the caller
- Bus health: GET /api/health/bus returns dlq_pending, events_last_hour, status

## Worktrees Workflow

This project uses git worktrees for parallel development:
```bash
# Create a worktree for a feature branch
git worktree add .claude/worktrees/<branch-name> -b <branch-name>

# Work in the worktree
cd .claude/worktrees/<branch-name>

# Clean up after merge
git worktree remove .claude/worktrees/<branch-name>
```

Each worktree has its own working directory. Changes in one worktree do not affect others.

## Known Errors and Solutions

### Motor AsyncIOMotorClient import
Error: `cannot import name 'AsyncIOMotorClient'`
Fix: Use `from motor.motor_asyncio import AsyncIOMotorClient` (not `from motor import`)

### pytest-asyncio deprecation warning
Warning: `PytestUnraisableExceptionWarning`
Fix: Add `asyncio_mode = "auto"` in pytest.ini or use `@pytest.mark.asyncio` on each test

### MongoDB index creation on existing collection
Error: `IndexOptionsConflict` when running init script twice
Fix: Use `create_index()` with `background=True` — it's idempotent (unlike `createIndex` with different options)

### Pydantic V2 model_dump vs dict
Error: `AttributeError: 'RoddosEvent' object has no attribute 'dict'`
Fix: Use `.model_dump()` instead of `.dict()` (Pydantic V2)