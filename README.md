# SISMO — Sistema Inteligente de Soporte y Monitoreo Operativo

## Que es SISMO / RODDOS

SISMO es la plataforma de orquestacion de agentes IA especializados que automatiza las operaciones completas de **RODDOS S.A.S.**, fintech de movilidad sostenible en Bogota, Colombia.

RODDOS financia motocicletas con cobro 100% remoto (WhatsApp + transferencias). El equipo pequeno (2-5 personas) gestiona 10 loanbooks activos, cartera de $94M COP y 34 motos TVS con VINs reales.

**Principio rector:** Soberania Digital — ninguna plataforma de terceros es duena del corazon operativo.

**Build actual:** BUILD 24 — Cimientos Definitivos

---

## Stack BUILD 24

| Capa | Tecnologia |
|------|-----------|
| Frontend | React 19 + TypeScript + Tailwind CSS + Shadcn/UI |
| Backend | FastAPI (Python 3.11) + Motor (async MongoDB) |
| Base de datos | MongoDB Atlas |
| IA | Claude Sonnet via Anthropic SDK |
| Contabilidad | Alegra API v1 (sistema contable de record) |
| WhatsApp | Mercately |
| Hosting | Render.com |
| CI/CD | GitHub Actions (pytest + smoke test) |

---

## Los 4 agentes core

- **Contador** — Automatiza contabilidad en Alegra: facturas, journals, conciliacion bancaria, clasificacion de movimientos con confianza.
- **CFO** — Analisis financiero estrategico: semaforo (caja, cartera, ventas, roll rate, impuestos), PyG mensual, plan de deudas, proyecciones.
- **RADAR** — Cobranza inteligente via WhatsApp: cola semanal, gestiones, PTPs, recordatorios automaticos, alertas de mora.
- **Loanbook** — Ciclo completo de credito: solicitud, entrega, plan de cuotas (semanal/quincenal/mensual), registro de pagos, estados de cartera.

Ningun agente llama a otro directamente — toda comunicacion pasa por el bus de eventos (EventBusService + MongoDB roddos_events).

---

## Como correr el proyecto

### Requisitos

- Node.js 18+ y Yarn
- Python 3.11+
- MongoDB Atlas (o MongoDB local 6.0+)
- Cuenta Alegra con token API
- ANTHROPIC_API_KEY (Claude Sonnet)

### Setup local

```bash
# Backend
cd backend
cp .env.example .env  # Editar con valores reales
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Frontend (en otra terminal)
cd frontend
yarn install
yarn start
```

### Variables de entorno obligatorias

**backend/.env:**
```
MONGO_URL=mongodb+srv://...
DB_NAME=sismo
ALEGRA_EMAIL=email@empresa.com
ALEGRA_TOKEN=tu-token-alegra
ALEGRA_WEBHOOK_SECRET=roddos-webhook-2026
JWT_SECRET=secreto-largo-seguro
ANTHROPIC_API_KEY=sk-ant-...
APP_URL=https://tu-dominio.com
CORS_ORIGINS=http://localhost:3000
```

**frontend/.env:**
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## Licencia

Uso interno — RODDOS S.A.S. — Bogota D.C., Colombia.
