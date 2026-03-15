# SISMO — RODDOS Contable IA

> Agente contador inteligente integrado con Alegra ERP para RODDOS Colombia SAS, concesionario Auteco en Bogotá.

**Builder**: [emergent.sh](https://emergent.sh)  
**Stack**: React 19 + TypeScript + Tailwind + FastAPI + MongoDB + Claude Sonnet 4.5 + Alegra API

---

## Descripción

SISMO es un ERP contable asistido por IA que permite:

- Registrar facturas de compra/venta y causaciones directamente desde el chat
- Gestionar cartera de crédito (Loanbook) con reglas de cobro específicas
- Controlar inventario de motos Auteco (carga automática desde PDF)
- Ejecutar acciones reales en Alegra desde lenguaje natural
- Gestionar cobranza 100% remota (sistema RADAR)

---

## Requisitos

- Node.js 18+
- Python 3.10+
- MongoDB 6+ (local o Atlas)
- Cuenta Alegra Plan Pro Colombia
- API Key Anthropic o Emergent LLM Key

---

## Instalación

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Completar .env con valores reales
uvicorn server:app --reload --port 8001
```

### Frontend

```bash
cd frontend
yarn install
cp ../.env.example .env
# Ajustar REACT_APP_BACKEND_URL en .env
yarn start
```

---

## Variables de entorno

Copiar `.env.example` a `.env` (en la raíz o en `backend/`) y completar con los valores reales. Ver comentarios en el archivo para instrucciones por campo.

**Campos obligatorios para funcionamiento básico:**
- `ALEGRA_EMAIL` + `ALEGRA_TOKEN` — credenciales Alegra
- `MONGO_URL` — conexión MongoDB
- `JWT_SECRET` — clave secreta para tokens (mínimo 32 caracteres)
- `EMERGENT_LLM_KEY` — clave para Claude Sonnet 4.5

---

## Estado actual del proyecto

### Implementado ✅

| Módulo | Descripción |
|--------|-------------|
| **Bus de eventos** | `roddos_events` en MongoDB — sincronizan todos los módulos tras cada acción Alegra |
| **Loanbook** | Flujo completo 3 momentos: registro venta → entrega física → cobro. Cálculo automático de fechas (siempre miércoles) |
| **RADAR (Cartera)** | Cola de Gestión Remota con prioridades URGENTE/HOY/PREVENTIVO. 100% remota, sin visitas en campo |
| **Plan de cuentas** | 233 cuentas NIIF reales vía `/categories` de Alegra. ⚠️ Nunca usar `/accounts` (devuelve 403) |
| **post_action_sync()** | Sincronización automática de módulos después de cada acción en Alegra |
| **Memoria del agente** | Historial persistente de chat, tarea activa con progreso, contexto del día desde `roddos_events` |
| **Inventario motos** | Carga PDF Auteco → extracción automática chasis/motor/color. 1 objeto por unidad |
| **Anulación facturas** | Bloqueo si hay motos vinculadas vendidas. Flujo de anulación completo |
| **Chat pantalla completa** | Adjuntos PDF e imágenes, selector tipo documento, historial persistente |
| **Badge tarea activa** | Indicador en tiempo real del progreso de tareas multi-paso (cyan/amarillo/verde) |
| **Filtros módulo motos** | 6 filtros por estado con conteos en tiempo real. Default: Disponible |
| **Control IVA** | Control cuatrimestral de IVA por período |
| **Repuestos** | Catálogo, stock y facturación |

### Pendiente ❌

| Módulo | Descripción |
|--------|-------------|
| **BUILD 10** | Estado de Resultados automático desde Alegra |
| **Mercately WhatsApp** | Pendiente credenciales. Bot actualmente ignora mensajes de texto libre |
| **CFO Report** | `costo_motos` y `gastos_operativos` calculan $0 (bug conocido en `cfo_agent.py`) |

---

## Reglas críticas de arquitectura

> ⚠️ **Leer antes de modificar el código**

1. `post_action_sync()` se llama **SIEMPRE** después de cualquier acción en Alegra
2. `_metadata` incompleto → **bloqueo total** — nunca crear factura parcial
3. Pago sin `factura_alegra_id` → bloqueo + aviso al usuario
4. Cobranza: **100% remota** — NO hay visitas en campo ni geolocalización
5. Plan de cuentas: usar `/categories` (233 cuentas NIIF). **Nunca `/accounts`**
6. Extracción motos PDF: **1 objeto por unidad física** (nunca `cantidad: N`)
7. Regla de cobro: siempre **miércoles**. Primer cobro = primer miércoles ≥ (entrega + 7 días)

---

## Bancos reales en Alegra

| Banco | Cuenta Alegra |
|-------|--------------|
| Bancolombia | 111005 |
| BBVA | 111010 |
| Davivienda | 111015 |
| Banco de Bogotá | 111020 |

---

## Planes de financiación

| Plan | Semanas | Observación |
|------|---------|-------------|
| P39S | 39 sem | |
| P52S | 52 sem | |
| P78S | 78 sem | |

- Mora: **15% EA**. Día 1 de mora = jueves siguiente al miércoles de cobro
- DPD máximo sin pago: 21 días. DPD = 22 activa recuperación automática

---

## Estructura del proyecto

```
SISMO/
├── backend/
│   ├── server.py              # FastAPI app principal
│   ├── ai_chat.py             # Lógica del agente IA + Claude Sonnet
│   ├── post_action_sync.py    # Sincronización inter-módulos
│   ├── alegra_service.py      # Cliente Alegra ERP
│   ├── event_bus.py           # Bus de eventos MongoDB
│   ├── inventory_service.py   # Extracción motos desde PDF
│   ├── routers/               # Endpoints por módulo
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/             # AgentChatPage, InventarioAuteco, Loanbook, etc.
│   │   ├── components/        # UI components (Shadcn/UI)
│   │   └── App.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.js
├── scripts/                   # Utilidades y migraciones
├── memory/                    # PRD, arquitectura, changelog
├── .env.example
├── .gitignore
└── README.md
```

---

## Licencia

Proyecto propietario de RODDOS Colombia SAS. Desarrollo con [emergent.sh](https://emergent.sh).
