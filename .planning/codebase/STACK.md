# Technology Stack

**Analysis Date:** 2026-03-24

## Languages

**Primary:**
- TypeScript 5.9.3 - Frontend application (React + React Router)
- Python 3.11.0 - Backend API server (FastAPI)

**Secondary:**
- JavaScript - Frontend tooling and configuration

## Runtime

**Frontend Environment:**
- Node.js (yarn package manager) - v1.22.22+sha512
- React 19.0.0 - UI framework with React Router 7.5.1
- React Scripts 5.0.1 - Build and development server

**Backend Environment:**
- Python 3.11.0 (specified in render.yaml)
- uvicorn 0.25.0 - ASGI server
- Motor 3.7.0 - Async MongoDB driver

## Frameworks

**Core:**
- **FastAPI** 0.110.1 - Backend REST API framework
- **React** 19.0.0 - Frontend UI framework
- **Radix UI** (comprehensive set of v1.x components) - Headless component library
  - @radix-ui/react-accordion, @radix-ui/react-dialog, @radix-ui/react-select, etc.

**Styling:**
- **Tailwind CSS** 3.4.17 - Utility-first CSS framework
- **Tailwindcss-animate** 1.0.7 - Animation utilities
- **Autoprefixer** 10.4.20 - CSS vendor prefix auto-injection

**State & Forms:**
- **React Hook Form** 7.56.2 - Form state management
- **Zod** 3.24.4 - TypeScript-first schema validation
- @hookform/resolvers 5.0.1 - Integration between Hook Form and Zod
- **class-variance-authority** 0.7.1 - Type-safe CSS component variants

**Testing:**
- **Craco** 7.1.0 - Create React App configuration overrides

**Build/Dev:**
- **TypeScript** 5.9.3 - Type checking
- **ESLint** 9.23.0 - Code linting
- **Autoprefixer** 10.4.20 - CSS processing
- **PostCSS** 8.4.49 - CSS transformations

## Key Dependencies

**Critical Backend:**
- **pymongo** 4.9.2 - MongoDB Python driver (synchronous)
- **motor** 3.7.0 - Async MongoDB driver
- **pydantic** 2.7.1 - Data validation and serialization
- **python-jose** 3.3.0 - JWT token generation/validation
- **bcrypt** 4.1.2 - Password hashing
- **passlib** 1.7.4 - Password hashing framework
- **PyJWT** 2.8.0 - JWT library

**Backend - AI/LLM:**
- **anthropic** 0.34.0 - Claude API client for AI chat and document analysis
- EMERGENT_LLM_KEY - Custom LLM integration (key-based)

**Backend - External APIs:**
- **httpx** 0.27.0 - Async HTTP client (Alegra, Mercately, Telegram, DIAN APIs)
- **requests** 2.32.3 - HTTP client for synchronous requests
- **aiohttp** 3.9.5 - Alternative async HTTP client

**Backend - Scheduled Tasks:**
- **apscheduler** 3.10.4 - Advanced job scheduling for background tasks

**Backend - Data Processing:**
- **openpyxl** 3.1.5 - Excel file reading/writing
- **pandas** 2.2.2 - Tabular data analysis
- **pdfplumber** 0.11.0 - PDF text extraction
- **python-dateutil** 2.9.0 - Date utilities
- **pytz** 2024.1 - Timezone utilities

**Backend - 2FA & Security:**
- **pyotp** 2.9.0 - TOTP/HOTP one-time password generation
- **qrcode** 7.4.2 - QR code generation for 2FA
- **cryptography** 43.0.1 - Cryptographic operations

**Backend - Configuration:**
- **python-dotenv** 1.0.1 - .env file loading

**Backend - Multipart:**
- **python-multipart** 0.0.9 - Form and file upload parsing

**Frontend - Data Handling:**
- **xlsx** 0.18.5 - Excel file parsing and generation
- **date-fns** 4.1.0 - Date formatting and manipulation
- **react-day-picker** 8.10.1 - Date picker component

**Frontend - PDF Generation:**
- **jspdf** 4.2.0 - PDF generation from HTML/DOM
- **jspdf-autotable** 5.0.7 - Automatic table formatting for jsPDF

**Frontend - HTTP:**
- **axios** 1.8.4 - HTTP client for API calls

**Frontend - Charts & Visualization:**
- **recharts** 3.6.0 - Charting library built on React
- **embla-carousel-react** 8.6.0 - Carousel/slider component

**Frontend - UI Utilities:**
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

**Frontend - Drag & Drop:**
- **@dnd-kit/core** 6.3.1 - Headless drag-drop library
- **@dnd-kit/sortable** 10.0.0 - Sortable preset
- **@dnd-kit/utilities** 3.2.2 - Utility functions

**Frontend - Visual Editing (Dev):**
- **@emergentbase/visual-edits** 1.0.8 - Visual code editor integration

## Configuration

**Frontend Build Configuration:**
- `tsconfig.json` - TypeScript configuration (target: ES5, strict: false)
- `craco.config.js` - Create React App configuration overrides
  - Webpack alias: `@` → `src/`
  - ESLint rules for React hooks
  - Visual edits integration (Emergent)
- `.env.production` - Production build settings
  - DISABLE_ESLINT_PLUGIN=true
  - GENERATE_SOURCEMAP=false

**Environment Variables - Backend Required:**
- `MONGO_URL` - MongoDB Atlas connection string (mongodb+srv://...)
- `DB_NAME` - Database name (default: "sismo")
- `ALEGRA_EMAIL` - Alegra accounting software credentials
- `ALEGRA_TOKEN` - Alegra API token
- `ALEGRA_WEBHOOK_SECRET` - Webhook validation token (default: "roddos-webhook-2026")
- `JWT_SECRET` - JWT signing secret (default: "roddos-jwt-secret-2025-secure")
- `ANTHROPIC_API_KEY` - Claude API key for AI features
- `EMERGENT_LLM_KEY` - Alternative/internal LLM provider key
- `APP_URL` - Application public URL (for Alegra webhook callbacks)

**Environment Variables - Frontend Required:**
- `REACT_APP_BACKEND_URL` - Backend API base URL (e.g., http://localhost:8000 or production URL)

**Environment Variables - Optional:**
- `ALEGRA_USER` - Alternate Alegra authentication (some legacy usage)
- `MERCATELY_API_URL` - WhatsApp integration endpoint
- `TELEGRAM_API_TOKEN` - Telegram bot token
- `ENABLE_HEALTH_CHECK` - Enable webpack health check plugin in frontend

## Platform Requirements

**Development:**
- Node.js with Yarn 1.22.22+
- Python 3.11.0+
- MongoDB Atlas account (or local MongoDB)
- Git for version control

**Production:**
- Render.com (specified in render.yaml) or compatible Python hosting
- MongoDB Atlas (or compatible MongoDB service)
- Environment variable configuration for all API keys and credentials

## Database

**Primary:**
- **MongoDB** (atlas) - Document database via Motor async driver
- Collections:
  - `roddos_cuentas` - Account mapping between system and Alegra
  - `alegra_credentials` - Stored Alegra credentials (fallback)
  - `loanbook` - Loan/motorcycle financing records
  - `inventario` - Inventory management
  - `mercately_config` - WhatsApp bot configuration
  - `telegram_config` - Telegram bot configuration
  - `roddos_events` - Event log for webhooks and system actions
  - `crm` - Customer relationship data
  - `gastos`, `ingresos`, `factura_*` - Transaction records

---

*Stack analysis: 2026-03-24*
