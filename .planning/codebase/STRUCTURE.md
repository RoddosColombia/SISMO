# Codebase Structure

**Analysis Date:** 2026-03-24

## Directory Layout

```
SISMO/
├── backend/                           # FastAPI application (Python)
│   ├── server.py                      # FastAPI app entry point
│   ├── models.py                      # Pydantic request/response schemas
│   ├── database.py                    # MongoDB connection (Motor)
│   ├── auth.py                        # JWT token creation and verification
│   ├── dependencies.py                # FastAPI dependency injection (auth guards, logging)
│   ├── ai_chat.py                     # LLM orchestration and action handling
│   ├── alegra_service.py              # Alegra API client wrapper
│   ├── routers/                       # Feature-specific endpoint handlers
│   │   ├── chat.py                    # AI chat messaging, action execution
│   │   ├── loanbook.py                # Payment plan CRUD and payment tracking
│   │   ├── alegra.py                  # Account sync endpoints
│   │   ├── cfo_estrategico.py         # Strategic CFO analytics
│   │   ├── cfo.py                     # Operational CFO dashboard
│   │   ├── cfo_chat.py                # CFO agent conversation
│   │   ├── cartera.py                 # Collections/receivables management
│   │   ├── inventory.py               # Inventory tracking (Auteco)
│   │   ├── impuestos.py               # Tax planning
│   │   ├── gastos.py                  # Expense classification
│   │   ├── ventas.py                  # Sales reporting
│   │   ├── crm.py                     # Client management
│   │   ├── radar.py                   # Payment monitoring dashboard
│   │   ├── mercately.py               # WhatsApp integration
│   │   ├── loanbook_scheduler.py      # (deprecated — moved to services/)
│   │   ├── scheduler.py               # Periodic task configuration
│   │   ├── settings.py                # User configuration endpoints
│   │   ├── dashboard.py               # KPI aggregation
│   │   ├── telegram.py                # Telegram notifications
│   │   ├── conciliacion.py            # Bank reconciliation
│   │   ├── estado_resultados.py       # Income statement
│   │   ├── nomina.py                  # Payroll integration
│   │   ├── ingresos.py                # Revenue recognition
│   │   ├── cxc.py                     # Accounts receivable
│   │   └── [15+ more...]              # Other features
│   ├── services/                      # Business logic and algorithms
│   │   ├── accounting_engine.py       # Transaction classification algorithm
│   │   ├── cfo_agent.py               # CFO decision engine
│   │   ├── scheduler.py               # Periodic task execution
│   │   ├── loanbook_scheduler.py      # Payment plan async processing
│   │   ├── bank_reconciliation.py     # Extract matching algorithm
│   │   ├── learning_engine.py         # Agent memory training
│   │   ├── shared_state.py            # Centralized state caching
│   │   ├── dian_service.py            # Colombian tax authority integration
│   │   ├── crm_service.py             # CRM business logic
│   │   └── __init__.py
│   ├── utils/                         # Shared utilities
│   │   ├── loanbook_constants.py      # Payment plan formulas (cuota calculation, días_entre_cuotas)
│   │   └── __init__.py
│   ├── migrations/                    # Database schema migrations
│   │   └── [*.py migration scripts]
│   ├── event_bus.py                   # Cross-module event publishing
│   └── [*.py scripts]                 # Data fixes, testing (carga_loanbooks.py, etc.)
│
├── frontend/                          # React 19 application (TypeScript)
│   ├── src/
│   │   ├── App.tsx                    # Root component, routing setup
│   │   ├── index.tsx                  # React entry point
│   │   ├── pages/                     # Feature pages (page per route)
│   │   │   ├── AgentChatPage.tsx      # AI chat interface
│   │   │   ├── Dashboard.tsx          # Main KPI dashboard
│   │   │   ├── Loanbook.tsx           # Payment plan list/detail
│   │   │   ├── CFOEstrategico.tsx     # Strategic CFO analytics
│   │   │   ├── CFO.tsx                # Operational dashboard
│   │   │   ├── CRMList.tsx, CRMCliente.tsx
│   │   │   ├── Radar.tsx              # Payment monitoring
│   │   │   ├── Impuestos.tsx          # Tax planning
│   │   │   ├── InventarioAuteco.tsx   # Inventory
│   │   │   ├── Presupuesto.tsx        # Budget planning
│   │   │   ├── Perfil.tsx             # User profile
│   │   │   ├── Settings.tsx           # Configuration
│   │   │   ├── Login.tsx              # Authentication
│   │   │   ├── CargarExtraacto.tsx    # Bank extract upload
│   │   │   ├── Proveedores.tsx        # Suppliers
│   │   │   └── [+10 more]
│   │   ├── components/                # Reusable UI/business components
│   │   │   ├── Layout.tsx             # Main layout wrapper
│   │   │   ├── FiltroFecha.tsx        # Date range picker
│   │   │   ├── shared/                # Domain-specific components
│   │   │   │   ├── RadarCard.tsx      # Payment radar card
│   │   │   │   ├── GestionModal.tsx   # Collection activity form
│   │   │   │   ├── BucketBadge.tsx    # Aging bucket display
│   │   │   │   ├── ScoreBadge.tsx     # Customer credit score
│   │   │   │   ├── DiasProtocolo.tsx  # Days in process
│   │   │   │   └── WhatsAppButton.tsx # WhatsApp contact button
│   │   │   └── ui/                    # Radix UI primitives (auto-generated)
│   │   │       ├── button.d.ts        # Button component
│   │   │       ├── dialog.d.ts        # Modal component
│   │   │       ├── input.d.ts         # Text input
│   │   │       ├── select.d.ts        # Dropdown
│   │   │       └── [+20 more UI]
│   │   ├── contexts/                  # React Context state management
│   │   │   ├── AuthContext.tsx        # User auth state, JWT token, api client
│   │   │   └── AlegraContext.tsx      # Alegra integration state
│   │   ├── hooks/                     # Custom React hooks
│   │   │   ├── useSharedState.ts      # Fetch server-side state cache
│   │   │   ├── useRadarQueue.ts       # Radar payment queue management
│   │   │   └── use-toast.js           # Toast notification hook
│   │   ├── utils/                     # Helper functions
│   │   │   ├── descargar.ts           # File download utilities
│   │   │   ├── exportUtils.js         # Excel/PDF export
│   │   │   └── formatters.js          # Number/date formatting
│   │   ├── lib/                       # Shared utilities and helpers
│   │   └── public/                    # Static assets
│   ├── package.json                   # Dependencies (React 19, Radix UI, TailwindCSS, etc.)
│   ├── tsconfig.json                  # TypeScript config (baseUrl: src, @/* alias)
│   ├── craco.config.js                # Create React App build config override
│   ├── tailwind.config.js             # Tailwind CSS customization
│   └── build/                         # Production build output (generated)
│
├── tests/                             # Test suite
│   └── [test_*.py files]
├── migrations/                        # Database migration scripts
├── docs/                              # Documentation
├── scripts/                           # Utility scripts
├── memory/                            # Agent memory/training data
│
├── .planning/                         # GSD planning artifacts
│   └── codebase/                      # Architecture analysis (this document)
│       ├── ARCHITECTURE.md
│       ├── STRUCTURE.md
│       ├── STACK.md
│       ├── INTEGRATIONS.md
│       ├── CONVENTIONS.md
│       └── TESTING.md
│
├── .github/                           # GitHub Actions workflows
├── render.yaml                        # Render deployment config
├── README.md                          # Project documentation
└── package.json / yarn.lock           # Workspaces (if monorepo)
```

## Directory Purposes

**Backend Root (`backend/`):**
- Purpose: FastAPI application with routers and services
- All Python application code
- Entry point: `server.py`

**Routers (`backend/routers/`):**
- Purpose: HTTP endpoint handlers organized by feature
- Contains: One module per business domain (chat, loanbook, alegra, etc.)
- Pattern: Each file defines APIRouter with prefix, Pydantic models, async handlers
- Key files: `chat.py` (AI agent), `loanbook.py` (payment plans), `alegra.py` (accounting sync)

**Services (`backend/services/`):**
- Purpose: Business logic and algorithms (no HTTP/request details)
- Contains: Stateless or minimal-state classes with methods
- Key files:
  - `accounting_engine.py` - Classify transactions to accounts
  - `cfo_agent.py` - Financial analysis and recommendations
  - `scheduler.py` - Periodic task execution
  - `bank_reconciliation.py` - Extract matching
  - `learning_engine.py` - LLM fine-tuning data
- Calling pattern: Routers call services, services call database/external APIs

**Frontend Pages (`frontend/src/pages/`):**
- Purpose: One component per route (feature page)
- Contains: Full page layout with forms, tables, charts
- Pattern: Fetch data in useEffect, render with components, handle form submission
- Each page:
  - Uses `useAuth().api` for backend calls
  - Manages local state for forms/filters
  - Calls services for complex logic

**Components (`frontend/src/components/`):**
- Purpose: Reusable UI and business-specific components
- `shared/` - Domain components (RadarCard for cartera, GestionModal for collections)
- `ui/` - Low-level Radix UI primitives with Tailwind styling
- Composition: Pages build from components, components compose from UI primitives

**Contexts (`frontend/src/contexts/`):**
- Purpose: Global state via React Context API
- `AuthContext.tsx` - User session, JWT token, authenticated axios instance
- `AlegraContext.tsx` - Alegra API integration state
- Usage: Wrap App in providers, consume via useAuth() / useAlegra() hooks

**Utils (`frontend/src/utils/`):**
- Purpose: Pure functions for calculations and data transformation
- `descargar.ts` - Trigger file downloads
- `exportUtils.js` - Generate Excel/PDF from data
- `formatters.js` - Format numbers/dates for display

## Key File Locations

**Entry Points:**
- Backend: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/server.py`
- Frontend: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/App.tsx` (root component)
- Frontend HTML: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/public/index.html`

**Configuration:**
- Backend env: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/.env` (not in repo)
- Frontend env: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/.env.local` (REACT_APP_BACKEND_URL)
- TypeScript: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/tsconfig.json` (baseUrl: src, paths: @/*)
- Tailwind: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/tailwind.config.js`

**Core Logic:**
- Accounting classification: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/accounting_engine.py`
- CFO analytics: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/cfo_agent.py`
- Payment plan calculations: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/utils/loanbook_constants.py`
- Bank reconciliation: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/bank_reconciliation.py`
- LLM orchestration: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/ai_chat.py`

**Testing:**
- Test files: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/tests/` (pytest)
- Test data: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/mock_data.py`

**Migrations & Data:**
- Database migrations: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/migrations/`
- Schema updates: `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/migration_v24.py`

## Naming Conventions

**Files:**

**Backend:**
- Router files: kebab-case or snake_case (e.g., `cfo_estrategico.py`, `alegra_webhooks.py`)
- Service files: snake_case (e.g., `accounting_engine.py`, `bank_reconciliation.py`)
- Utility files: snake_case (e.g., `loanbook_constants.py`)
- Script files: full snake_case (e.g., `create_test_extracto.py`, `smoke_test_final_20.py`)

**Frontend:**
- Pages: PascalCase ending with `Page` (e.g., `AgentChatPage.tsx`, `Dashboard.tsx`)
- Components: PascalCase (e.g., `Layout.tsx`, `RadarCard.tsx`, `GestionModal.tsx`)
- Hooks: camelCase starting with `use` (e.g., `useSharedState.ts`, `useRadarQueue.ts`)
- Utils: camelCase or descriptive (e.g., `descargar.ts`, `formatters.js`)
- Contexts: PascalCase ending with `Context` (e.g., `AuthContext.tsx`, `AlegraContext.tsx`)

**Directories:**

**Backend:**
- Feature routers: single word or snake_case (e.g., `routers/`, `services/`, `utils/`, `migrations/`)

**Frontend:**
- Folders in `src/`: lowercase (pages, components, contexts, hooks, utils, lib)
- Sub-folders: lowercase (shared, ui)

## Where to Add New Code

**New Feature (API + UI):**

1. **Backend endpoint:**
   - Create `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/routers/feature_name.py`
   - Define APIRouter with prefix `/feature_name`
   - Define Pydantic models for request/response
   - Implement async handlers
   - Import and include router in `server.py`: `app.include_router(feature_router)`

2. **Business logic:**
   - If complex, create `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/feature_name.py`
   - Implement stateless service class or module functions
   - Call from router handlers

3. **Frontend page:**
   - Create `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/pages/FeatureName.tsx`
   - Use `useAuth().api` to call backend endpoints
   - Add route in `App.tsx`: `<Route path="/feature-name" element={<FeatureName />} />`

4. **Frontend components:**
   - Create `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/components/FeatureComponent.tsx` if reusable
   - Or create inline in page if feature-specific

**New Component/Module:**

- **Shared logic:** `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/services/` (Python) or `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/utils/` (TypeScript)
- **Shared UI:** `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/components/shared/`
- **Hooks/Contexts:** `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/hooks/` or `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/contexts/`

**Utilities:**

- **Backend constants:** `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/utils/` (e.g., formulas, regex patterns, enums)
- **Frontend formatters:** `C:\Users\AndresSanJuan\roddos-workspace\SISMO/frontend/src/utils/` (date, currency formatting)

**Database Migrations:**

- Create `C:\Users\AndresSanJuan\roddos-workspace\SISMO/backend/migrations/migration_vXX.py`
- Implement async schema changes
- Call from `server.py::startup()` or manual script

## Special Directories

**`memory/` Directory:**
- Purpose: Agent training data and fine-tuning examples
- Generated: Yes (updated via agent learning)
- Committed: Yes (examples for improving classification)

**`migrations/` Directory:**
- Purpose: Database schema evolution scripts
- Generated: No (manually written)
- Committed: Yes (deployed to production)

**`docs/` Directory:**
- Purpose: Project documentation, design guidelines, API specs
- Generated: No
- Committed: Yes

**`scripts/` Directory:**
- Purpose: Data loading, testing, maintenance utilities
- Generated: No
- Committed: Selective (utility scripts yes, data loads maybe)

**`.planning/` Directory:**
- Purpose: GSD orchestration artifacts and analysis documents
- Generated: Yes (auto-created by /gsd:map-codebase, /gsd:plan-phase, etc.)
- Committed: Yes (for orchestrator continuity)

**`build/` Directory (Frontend):**
- Purpose: Production build output
- Generated: Yes (via `npm run build`)
- Committed: No (.gitignored)

**`.env` Files:**
- Location: `backend/.env` (not in repo), `frontend/.env.local` (not in repo)
- Committed: No (.gitignored — use .env.example instead)

