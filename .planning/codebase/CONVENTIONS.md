# Coding Conventions

**Analysis Date:** 2026-03-24

## Naming Patterns

**Files:**
- Components: PascalCase (e.g., `FiltroFecha.tsx`, `AgentChatPage.tsx`, `BucketBadge.tsx`)
- Utilities: camelCase (e.g., `formatters.js`, `descargar.ts`, `exportUtils.js`)
- Contexts: PascalCase with "Context" suffix (e.g., `AuthContext.tsx`, `AlegraContext.tsx`)
- Hooks: camelCase with "use" prefix (e.g., `useRadarQueue.ts`, `useSharedState.ts`)
- Services: camelCase (e.g., `alegra_service.py`, `inventory_service.py`, `security_service.py`)
- Tests: prefix with `test_` or match source file name (e.g., `test_build21_integration.py`, `test_roddos_backend.py`)

**Functions:**
- React components: PascalCase (e.g., `FiltroFecha()`, `ProtectedRoute()`, `App()`)
- JavaScript/TypeScript utilities: camelCase (e.g., `formatCOP()`, `formatDate()`, `descargarArchivo()`)
- Python functions: snake_case (e.g., `hash_password()`, `verify_token()`, `_detectar_tipo_proveedor()`)
- Internal/private functions: prefix with `_` (e.g., `_is_gastos_csv()`, `_detectar_identificacion()`)
- Async functions: same naming, clearly prefixed with `async` (e.g., `async def get_settings()`)

**Variables:**
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_PRESET_ID`, `ALEGRA_BASE_URL`, `EXPIRE_HOURS`)
- Local variables: camelCase in JS/TS (e.g., `customDesde`, `customHasta`, `moduleKey`)
- Database variables: snake_case (e.g., `mongo_url`, `db_name`, `cache_key`)
- State variables: camelCase in React (e.g., `open`, `custom`, `loading`)

**Types/Interfaces:**
- TypeScript: PascalCase (e.g., `User`, `DateRange`, `Props`, `AuthContextType`)
- Union types with "Type" or "Result" suffix (e.g., `LoginResult`, `TareaActiva`)
- Pydantic models: PascalCase with suffix (e.g., `UserModel`, `LoginRequest`, `ChatMessageRequest`)
- Discriminated unions: use `type` field (e.g., `type: "pl_export_card"`)

## Code Style

**Formatting:**
- Frontend: Tailwind CSS for all styling, inline utility classes (no separate CSS files for components)
- Backend: 4-space indentation (Python standard)
- Line length: Generally follows project defaults, but pragmatic about readability
- Quote style: Double quotes in TypeScript/JavaScript, single quotes acceptable in Python strings
- Semicolons: Used consistently in TypeScript (enforced by config)

**Linting:**
- Frontend ESLint rules configured in `craco.config.js`:
  - `react-hooks/rules-of-hooks`: error
  - `react-hooks/exhaustive-deps`: warn (note: sometimes suppressed with `// eslint-disable-line`)
- Backend: No strict linting enforced, but follows PEP8 conventions pragmatically
- No prettier/ESLint rc files found — config via `craco.config.js` and `tsconfig.json`

## Import Organization

**Order (Frontend - TypeScript/JSX):**
1. React and core React libraries: `import React from "react"`
2. Third-party dependencies: `import axios from "axios"`, `import { toast } from "sonner"`
3. UI/Icon libraries: `import { Calendar, ChevronDown } from "lucide-react"`
4. Markdown/rendering: `import ReactMarkdown from "react-markdown"`
5. Local contexts: `import { useAuth } from "../contexts/AuthContext"`
6. Local components: `import Layout from "./components/Layout"`
7. Local pages: `import Dashboard from "./pages/Dashboard"`
8. Local hooks: `import { useRadarQueue } from "../hooks/useRadarQueue"`
9. Local utilities: `import { descargarArchivo } from "../utils/descargar"`
10. Local types/interfaces (inline or from files)
11. CSS/styles: `import "./App.css"`

**Order (Backend - Python):**
1. Standard library: `import os`, `import logging`, `import asyncio`
2. Third-party: `import jwt`, `import bcrypt`, `from fastapi import FastAPI`
3. Async libraries: `from motor.motor_asyncio import AsyncIOMotorClient`
4. Local imports: `from auth import hash_password`, `from database import db`
5. Mock data: `from mock_data import MOCK_ACCOUNTS`

**Path Aliases:**
- Frontend TypeScript: `@/*` maps to `src/` (configured in `tsconfig.json`)
  - Example: `import { Button } from "@/components/ui/button"` resolves to `src/components/ui/button`
- Backend: Relative imports, no aliases (flat structure with optional `sys.path` manipulation in test files)

## Error Handling

**Frontend Patterns:**
- HTTP errors caught in interceptors or try/catch blocks
- Auth errors (401) trigger redirect to `/login` with session flag to prevent redirect storms (see `AuthContext.tsx`)
- API errors often fail silently with fallback UI or toast notifications (see `useRadarQueue.ts`: `catch { // fail silently }`)
- Custom error messages for user-facing operations (see `descargar.ts`: detailed error messages in Spanish)
- File operations: explicit null/undefined checks before operations (e.g., `if (!customDesde || !customHasta) return`)

**Backend Patterns:**
- HTTP exceptions from FastAPI: `raise HTTPException(status_code=, detail=)`
- Token verification: returns `None` on failure, caller checks (see `verify_token()`, `verify_temp_token()`)
- Database operations: wrapped in try/except, logged with context
- Service methods: return `None` on not-found conditions (see `get_cuenta_roddos()`)
- CSV parsing: explicit exception catch with fallback message (see `_parse_csv()`)

**Common Error Handling Idioms:**
```typescript
// Frontend: Silent failures acceptable for non-critical operations
catch {
  // fail silently
}

// Frontend: Toast notifications for user-facing errors
onError?.(msg);  // optional callback pattern
return false;    // boolean success indicator

// Backend: Explicit None returns for not-found
return None

// Backend: Raise for invalid operations
if not item:
    raise ValueError("...")
```

## Logging

**Framework:**
- Frontend: `console.log()`, `console.error()` via browser console, toast notifications via `sonner`
- Backend: Python `logging` module with logger per module (`logger = logging.getLogger(__name__)`)

**Patterns:**
- Frontend: Use `toast()` from sonner for user-visible notifications
  - Example: `toast.error("Error message")`
- Backend: Log with context:
  - Example: `logger.info(f"[Alegra] ✅ Credenciales PRODUCCIÓN desde variables de entorno")`
  - Use emoji prefixes for clarity (✅ success, ❌ error, ⚠️ warning)
  - Include source/module prefix for traceability
- Debug logging: rarely used, prefer explicit error handling
- No structured logging (Sentry, etc.) detected

## Comments

**When to Comment:**
- Complex algorithms: explain the "why" (e.g., date arithmetic, validation logic)
- Business logic assumptions: document domain rules (e.g., IVA calculations, Colombian accounting standards)
- Temporary workarounds: use TODO/FIXME tags (e.g., `// TODO: type - payload structure varies by action type`)
- Integration quirks: explain API behavior differences (e.g., real Alegra vs mock data, field naming variations)

**JSDoc/TSDoc:**
- Used selectively, not pervasively
- Component interfaces documented with JSDoc comments (e.g., `/** FiltroFecha — Reusable date range selector for RODDOS. */`)
- Function parameters rarely documented; types provide clarity via TypeScript
- Example from `FiltroFecha.tsx`:
  ```typescript
  /**
   * FiltroFecha — Reusable date range selector for RODDOS.
   * Persists selection per module in localStorage.
   */
  ```

**Inline Comments:**
- Short, uppercase sections with dashes (e.g., `/* ── types ── */`, `/* ── constants ── */`)
- Explain non-obvious state transitions (e.g., auth redirect logic in `AuthContext.tsx`)
- Clarify integration assumptions (e.g., mock vs real Alegra data handling)

## Function Design

**Size:**
- React components: typically 50-200 lines (includes JSX)
- Utility functions: 5-30 lines (keep focused)
- Service methods: vary widely (10-50 lines typical, up to 100+ for complex logic)
- Large functions: acceptable if cohesive (e.g., `execute_chat_action()` in `ai_chat.py` spans 5200+ lines but handles specific domain logic)

**Parameters:**
- React components: destructured props interface (e.g., `const FiltroFecha: React.FC<Props> = ({ moduleKey, onChange, compact })`)
- Utility functions: typically 1-3 parameters, optional parameters last
- API endpoints: Request models for body payload validation
- Async operations: callbacks for async results (e.g., `onError?: (msg: string) => void`)

**Return Values:**
- React components: JSX or null
- Utilities: explicit single return type (not multiple types)
- API handlers: Pydantic models or FastAPI responses
- Async operations: boolean success indicator common (`Promise<boolean>`)
- Database queries: single item or list, `None` for not-found

## Module Design

**Exports:**
- Components: default export (e.g., `export default FiltroFecha`)
- Utilities: named exports (e.g., `export function formatCOP()`)
- Hooks: named exports (e.g., `export function useAuth()`)
- Contexts: both default (provider component) and named (hook) exports
- Python modules: service classes or functions, imported by name

**Barrel Files:**
- Not used explicitly
- UI components in `components/ui/` appear to be auto-generated from shadcn/ui (`.d.ts` files present)
- No `index.ts` barrel exports observed in src directories

**Module Responsibilities:**
- `contexts/`: State management (Auth, Alegra credentials)
- `components/`: UI components (shared, pages, ui)
- `hooks/`: React hooks for custom logic
- `utils/`: Pure utility functions (formatting, downloads, exports)
- `pages/`: Page-level components (routed views)
- Backend `routers/`: FastAPI route handlers, organized by domain (auth, alegra, chat, inventory, etc.)
- Backend services: Business logic classes and functions

---

*Convention analysis: 2026-03-24*
