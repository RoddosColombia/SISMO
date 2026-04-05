# SISMO — Registro Canónico de Variables y Rutas
**Última actualización:** 5 abril 2026  
**Propósito:** Referencia única para Claude Code, Claude Chat y el equipo. Nunca más adivinar nombres de variables ni rutas.

---

## 1. Variables de Entorno — Render (Producción)

| Variable | Uso | Notas |
|---|---|---|
| `MONGO_URL` | Conexión MongoDB Atlas | `mongodb+srv://sismo_admin:...@sismo-prod.rzebxlv.mongodb.net` |
| `ALEGRA_EMAIL` | Auth Alegra | `contabilidad@roddos.com` |
| `ALEGRA_TOKEN` | Auth Alegra | Token Plan Pro — Basic Base64(email:token) |
| `ANTHROPIC_API_KEY` | Claude Sonnet API | Modelo: `claude-sonnet-4-20250514` |
| `N8N_API_KEY` | Auth requests n8n → SISMO | Header: `X-N8N-Key` |
| `GLOBAL66_WEBHOOK_SECRET` | Auth webhook Global66 → SISMO | Header: `x-api-key` (NO HMAC) |

---

## 2. Base de Datos MongoDB

| Parámetro | Valor | Error histórico |
|---|---|---|
| **Nombre de la DB** | `sismo` | ❌ NO usar `sismo-prod` — existe pero está vacía |
| **Conexión en código** | `client['sismo']` | Viene de `MONGO_URL` via `database.py` |
| **Variable en Render** | `MONGO_URL` | ❌ NO `MONGODB_URI` ni `MONGO_URI` |

### Colecciones críticas

| Colección | Descripción | Owner |
|---|---|---|
| `loanbook` | Créditos activos | Agente Loanbook |
| `inventario_motos` | 33+ motos TVS con VIN y motor | Agente Loanbook |
| `cartera_pagos` | Pagos de cuotas registrados | Agente Contador |
| `plan_cuentas_roddos` | 28 entradas con IDs reales Alegra | Agente Contador |
| `plan_ingresos_roddos` | IDs Alegra para ingresos | Agente Contador |
| `cxc_socios` | CXC Andrés + Iván | Agente Contador |
| `contabilidad_pendientes` | Backlog movimientos sin causar | Agente Contador |
| `global66_eventos_recibidos` | Registro eventos Global66 | Sistema |
| `roddos_events` | Bus de eventos (append-only) | Todos los agentes |
| `agent_sessions` | Historial conversacional 72h TTL | Sistema |
| `cfo_cache` | Caché CFO invalidable | CFO |
| `conciliacion_jobs` | Jobs de conciliación con estado | Sistema |

---

## 3. URLs Canónicas

| Servicio | URL | Notas |
|---|---|---|
| **Backend** | `https://sismo-backend-40ca.onrender.com` | Render Starter |
| **Frontend** | `https://sismo-bice.vercel.app` | Vercel Hobby |
| **Alegra API** | `https://api.alegra.com/api/v1/` | ❌ NUNCA `app.alegra.com/api/r1/` |
| **n8n** | `https://roddos.app.n8n.cloud` | Plan free trial |
| **Repo GitHub** | `github.com/RoddosColombia/SISMO` | Privado |

---

## 4. Endpoints Alegra — Reglas Inamovibles

| Endpoint | Estado | Notas |
|---|---|---|
| `POST /journals` | ✅ ÚNICO para comprobantes | Siempre con `request_with_verify()` |
| `GET /journals` | ✅ Para verificación post-POST | NO usar en operaciones masivas — TIMEOUT |
| `GET /categories` | ✅ Para plan de cuentas | |
| `POST /journal-entries` | ❌ PROHIBIDO | Da 403 siempre |
| `GET /accounts` | ❌ PROHIBIDO | Da 403 siempre |

---

## 5. Endpoints SISMO — n8n Hooks

Base URL: `https://sismo-backend-40ca.onrender.com/api/n8n`  
Auth requerida (excepto health): Header `X-N8N-Key: {N8N_API_KEY}`

| Endpoint | Método | Auth | Descripción |
|---|---|---|---|
| `/health` | GET | No | Estado global del sistema |
| `/status/global66` | GET | No | Estado webhook Global66 |
| `/status/backlog` | GET | No | Backlog por banco |
| `/agente/contador` | POST | Sí | Trigger Agente Contador |
| `/agente/cfo` | POST | Sí | Trigger CFO Estratégico |
| `/agente/radar` | POST | Sí | Trigger RADAR |
| `/agente/loanbook` | POST | Sí | Trigger Agente Loanbook |
| `/scheduler/{job_id}` | POST | Sí | Trigger job APScheduler |
| `/evento` | POST | Sí | Publicar en bus roddos_events |
| `/alerta` | POST | Sí | Insertar en notifications + cfo_alertas |

---

## 6. Endpoints SISMO — Webhook Global66

| Endpoint | Método | Auth | Descripción |
|---|---|---|---|
| `/api/global66/webhook` | POST | `x-api-key` header | Recibe eventos Global66 |

**Eventos que procesa:**
- `WALLET - Founding status` → Dinero recibido (INGRESO) — campos: `data.originAmount`, `data.thirdPartyClientName`, `data.transactionId`
- `RMT - Transaction` → Remesa enviada (EGRESO) — campos: `payload.originAmount`, `payload.purpose`, `payload.transactionId`
- Body vacío → Prueba de conexión Global66, responde 200 OK

---

## 7. IDs Alegra — Plan de Cuentas RODDOS

| Cuenta | ID Alegra | Notas |
|---|---|---|
| Gastos Generales | **5493** | ⚠️ Fallback correcto — NUNCA usar 5495 |
| Honorarios | 5470 | |
| Arrendamientos | 5480 | ReteFuente 3.5% |
| Servicios Públicos | 5484 | |
| Teléfono/Internet | 5487 | |
| Mantenimiento | 5490 | |
| Transporte | 5491 | |
| Sueldos | 5462 | |
| Seguridad Social | 5471 | |
| Dotaciones | 5472 | |
| Papelería | 5497 | |
| Publicidad | 5500 | |
| ICA | 5505 | |
| Comisiones Bancarias | 5508 | |
| Seguros | 5510 | |
| Intereses | 5533 | |
| ReteFuente practicada | 236505 | |
| ReteICA practicada | 236560 | |

---

## 8. Rutas Locales (Dev Machine)

| Recurso | Ruta |
|---|---|
| Repo local | `C:\Users\AndresSanJuan\roddos-workspace\SISMO` |
| Backend | `C:\Users\AndresSanJuan\roddos-workspace\SISMO\backend` |
| Routers | `C:\Users\AndresSanJuan\roddos-workspace\SISMO\backend\routers` |
| Tests | `C:\Users\AndresSanJuan\roddos-workspace\SISMO\tests` |
| CLAUDE.md global | `~/.claude/CLAUDE.md` |
| CLAUDE.md proyecto | `.claude/CLAUDE.md` |

---

## 9. Archivos Inamovibles — NUNCA Modificar

| Archivo | Razón |
|---|---|
| `backend/services/database.py` | Conexión central MongoDB |
| `backend/dependencies.py` | Inyección de dependencias FastAPI |
| `backend/services/alegra_service.py` | Cliente Alegra con request_with_verify |
| `backend/routers/conciliacion.py` | En producción con 3 bancos procesados |

---

## 10. Reglas de Negocio Críticas

| Regla | Valor |
|---|---|
| Día de cobro | **Siempre miércoles** |
| Mora empieza | **Jueves** (día siguiente al vencimiento) |
| Mora diaria | **$2.000 COP** acumulable |
| IVA | **Cuatrimestral**: ene-abr / may-ago / sep-dic |
| ReteICA Bogotá | **0.414%** |
| ReteFuente arrendamiento | **3.5%** |
| ReteFuente honorarios PN | **10%** |
| ReteFuente honorarios PJ | **11%** |
| ReteFuente servicios | **4%** |
| ReteFuente compras | **2.5%** (base > $1.344.573) |
| Auteco NIT 860024781 | **Autoretenedor** — NUNCA ReteFuente |
| Andrés Sanjuan CC 80075452 | Gastos → **CXC socios**, NUNCA gasto operativo |
| Iván Echeverri CC 80086601 | Gastos → **CXC socios**, NUNCA gasto operativo |
| Multiplicador quincenal | **×2.2** sobre cuota base semanal |
| Multiplicador mensual | **×4.4** sobre cuota base semanal |

---

## 11. Estado Builds

| Build | Commit | Tests | Estado |
|---|---|---|---|
| BUILD 24 | `v24.0.0` + hotfix-alegra | 67 ✅ | Completo |
| BUILD 23 | `884a248` | 37/37 ✅ | Completo |
| BUILD 25 | `8e84ff8` | 9/9 ✅ | Completo |
| Fix n8n loanbooks | `1d66772` | 65 ✅ | Completo |
| Fix tests | `665c124` | 67 ✅ | Completo |

---

*Este archivo se actualiza al cierre de cada build. Es la fuente de verdad para Claude Code y Claude Chat.*
