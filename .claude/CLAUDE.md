# SISMO — Skills y Reglas de Proyecto

Estas instrucciones aplican a todas las sesiones de Claude Code en el proyecto SISMO / RODDOS S.A.S.

---

## SKILL: SUPERPOWERS

Antes de escribir cualquier función nueva con lógica de negocio:

1. Hacer brainstorming: qué casos edge existen, qué puede fallar
2. Escribir el test primero (TDD) — especialmente para todo lo que toque Alegra o MongoDB
3. Solo después escribir la implementación mínima que pase el test

---

## SKILL: SYSTEMATIC DEBUGGING

Antes de proponer cualquier fix:

1. Reproducir el error con evidencia concreta (log, HTTP status, output)
2. Formular hipótesis de causa raíz — mínimo 2 candidatos
3. Validar la hipótesis con evidencia antes de tocar código
4. Aplicar el fix mínimo que resuelve la causa raíz

**NUNCA parchear síntomas. NUNCA proponer un fix sin haber completado los 4 pasos.**

---

## SKILL: CONTEXT OPTIMIZER

Al inicio de cada sesión:

1. Leer CLAUDE.md completo antes de cualquier acción
2. Preguntar en qué BUILD estamos y qué está pendiente
3. No asumir estado del proyecto — siempre verificar

Al llegar al 60% del context window: hacer /compact automáticamente.

---

## SKILL: ALEGRA API — REGLAS INAMOVIBLES

- URL base correcta: `https://api.alegra.com/api/v1/`
- **NUNCA usar:** `app.alegra.com/api/r1/` — da 404 en todos los endpoints
- **NUNCA usar:** `/journal-entries` — da 403, siempre usar `/journals`
- **NUNCA usar:** `/accounts` — da 403, siempre usar `/categories`
- Formato fechas: `yyyy-MM-dd` estricto (ejemplo: `2026-03-30`)
- **NUNCA enviar ISO-8601 con timezone** — retorna 0 resultados sin error visible
- Autenticación: Basic Auth `base64(email:token)` — el token NO expira automáticamente
- **GET /journals da TIMEOUT consistente** — inutilizable para listas grandes. NUNCA usar en scripts masivos.
- **NUNCA usar `date_afterOrNow` / `date_beforeOrNow`** — causan TIMEOUT adicional.
- **Para eliminar journals en bulk: DELETE /journals/{id}** — único método confiable.
- **Journals a CONSERVAR en RODDOS:** solo facturas de venta (/invoices) y bills de Auteco (/bills).

---

## SKILL: RENDER SHELL — REGLAS INAMOVIBLES

- **Scripts > 60 segundos:** SIEMPRE usar `nohup python -u script.py > /tmp/nombre.log 2>&1 &`
- **Flag `-u` OBLIGATORIO con nohup** — sin `-u` el output se bufferiza.
- **Monitoreo:** `tail -f /tmp/nombre.log`
- **Verificar proceso vivo:** `ps aux | grep script_name`
- **Scripts en Render Shell:** siempre correr desde `~/project/src/backend/`
- **Variables de entorno en Render Shell:** `os.environ['MONGO_URL']` directo, sin load_dotenv

---

## SKILL: CONTABILIDAD COLOMBIANA RODDOS

**Retenciones 2026:**
- Arrendamiento: ReteFuente 3.5%
- Servicios: ReteFuente 4%
- Honorarios persona natural: ReteFuente 10%
- Honorarios persona jurídica: ReteFuente 11%
- Compras: ReteFuente 2.5% (base mínima $1.344.573)
- ReteICA Bogotá: 0.414% en toda operación
- Auteco NIT 860024781: AUTORETENEDOR — **NUNCA aplicar ReteFuente**

**IVA:** CUATRIMESTRAL — períodos ene-abr / may-ago / sep-dic — **NUNCA bimestral**

**Socios:** Andrés CC 80075452 / Iván CC 80086601 → CXC socios, **NUNCA gasto operativo**

**Fallback cuentas Alegra:** ID 5493 (Gastos Generales) — **NUNCA ID 5495**

**VIN y motor:** OBLIGATORIOS en toda factura de venta de moto

**Mora:** $2.000 COP por día desde el jueves post-vencimiento

**Multiplicadores cuota:** Semanal x1.0 / Quincenal x2.2 / Mensual x4.4

---

## SKILL: COMMIT PROTOCOL

Antes de cada commit verificar:

1. `grep -rn "app.alegra.com"` — debe dar 0 resultados
2. `grep -rn "api/r1"` — debe dar 0 resultados
3. `grep -rn "journal-entries"` — debe dar 0 resultados
4. `grep -rn "5495"` — debe dar 0 resultados (fallback siempre es 5493)
5. `pytest backend/tests/test_permissions.py backend/tests/test_event_bus.py backend/tests/test_mongodb_init.py backend/tests/test_phase4_agents.py -v` — todos deben pasar

**Si alguno falla: NO hacer commit hasta resolver.**

---

## SKILL: ANTI-DUP HASH — REGLA INAMOVIBLE (aprendida 4 abr 2026)

El hash de movimiento bancario DEBE incluir el índice de fila del Excel:
- CORRECTO: `f"{banco}{fecha}{descripcion}{str(monto)}{referencia_original}"`
- donde `referencia_original` incluye `|row{idx}` desde el parser
- SIN índice de fila: múltiples cargos idénticos el mismo día colisionan → se pierden
- TODOS los parsers (Bancolombia, BBVA, Davivienda, Nequi) ya tienen este fix

---

## SKILL: GLOBAL66 API — REGLAS

- Cuenta Alegra: ID 11100507 (Global66 Colombia)
- Anti-dup: MD5(transaction_id) en colección `global66_transacciones_procesadas`
- Clasificación: SIEMPRE usar `clasificar_movimiento()` de accounting_engine — NUNCA hardcodear 5493
- El webhook ya existe en `routers/global66.py` — NO recrear, solo mejorar
- Webhook secret: variable de entorno `GLOBAL66_WEBHOOK_SECRET`
- API key para pull diario: variable de entorno `GLOBAL66_API_KEY`
- API base URL: variable de entorno `GLOBAL66_API_URL` (default: `https://api.global66.com/v1`)
- El sync diario a las 6 AM debe usar anti-dup para no duplicar lo que el webhook ya causó

---

## SKILL: N8N INTEGRATION — REGLAS

- Los endpoints n8n usan `N8N_API_KEY` en header `X-N8N-Key` (NO JWT de usuario)
- Prefijo: `/api/n8n/`
- NUNCA duplicar lógica que ya existe en otros routers — llamar a los mismos services
- Los endpoints n8n son "triggers" ligeros que invocan los mismos jobs del scheduler
- El scheduler APScheduler se MANTIENE como fallback — n8n es capa adicional, no reemplazo
- Toda acción ejecutada vía n8n se registra en `roddos_events` con `source: "n8n"`

---

## ESTADO BUILD ACTUAL — 4 de abril 2026

### BUILDS COMPLETADOS
- BUILD 24 completo (`v24.0.0`) — 67 tests en verde
- BUILD 23 completo — commit 884a248 — 37/37 tests GREEN
  - S0: consultar_journals en ACTION_MAP
  - S1: crear_causacion usa request_with_verify (ROG-1)
  - S2: ventas.py VIN/motor validados
  - S3: cartera.py cuota pagada post-verify
  - S4: nomina.py anti-dup mes
  - S5: Módulo Backlog completo

### FIXES APLICADOS HOY (4 abr 2026)
- accounting_engine.py: GMF 4x1.000 (con punto), embargo ICA→5410, ABONO DOMI→cartera 5327, Banco Agrario→comisión 5508
- bank_reconciliation.py: row index en hash de todos los parsers (anti-dup rows idénticas)
- BacklogPage.tsx + contabilidad_pendientes.py: modal Causar con 3 sugerencias inteligentes
- contabilidad_pendientes.py: endpoint `/backlog/sugerencias/{id}` con CUENTAS_RODDOS dict

### FASE 3 — RECONSTRUCCIÓN CONTABLE ESTADO
- FASE 0: Protección DELETE /invoices ✅
- FASE 1: Auditoría Alegra ✅
- FASE 2: Limpieza Alegra enero-febrero ✅
- FASE 3 enero: BBVA (109+27) + Bancolombia (132+46) + Nequi completo ✅
- FASE 3 febrero: BBVA (16+2) + Bancolombia (267+) + Nequi ✅
- FASE 3 marzo: esperando extractos de los bancos 🔜
- FASE 4: Global66 diario + n8n — **EN CONSTRUCCIÓN** 🔴
- FASE 5: Sincronización Alegra→Motos 🔜
- FASE 6: Inventario repuestos 🔜
- FASE 7: Mercately WhatsApp completo 🔜
- FASE 8: RADAR + Loanbook arquitectura profunda 🔜
- FASE 9: Rediseño UX/UI 🔜

### LECCIONES INAMOVIBLES FASE 3

- contabilidad_pendientes usa schema NUEVO con backlog_hash — NUNCA borrar documentos con backlog_hash
- Anti-dup en conciliacion_movimientos_procesados (hashes por movimiento) es independiente de conciliacion_extractos_procesados (hash del archivo)
- Cuentas None en clasificación van a backlog, no a Alegra — fix en clasificar_movimientos
- Hash de extracto: solo se guarda si causados > 0 (permite reintento si falló)
- 9 errores Bancolombia: AJUSTE INTERES AHORROS DB → cuenta_debito=None → backlog
- Bancolombia febrero: 24 movimientos perdidos por hash collision (múltiples cargos idénticos mismo día) → fix row index aplicado
- Orden correcto Liz: primero Backlog (120+ pendientes), después auditoría Alegra

### BACKLOG ACTUAL
- BBVA enero: 31 pendientes
- BBVA febrero: 2 pendientes (PSE sin contexto)
- Bancolombia enero: 46 pendientes
- Bancolombia febrero: pendientes (24 de Opción A + nuevos)
- Nequi enero: 25 pendientes
- Total: ~120+ pendientes para resolver

### PRÓXIMO: BUILD 25 — Global66 Diario + n8n Integration

Objetivo: SISMO pasa de reconstrucción reactiva a contabilidad proactiva diaria.
- Global66 webhook usa motor matricial (no hardcoded 5493)
- Job 6 AM pull Global66 API → clasifica → journals Alegra o backlog
- n8n endpoints en SISMO para triggers externos
- Integración completa: el 1 de abril en adelante, contabilidad del día anterior disponible a las 6:10 AM

---

## ARQUITECTURA ACTUAL — RESUMEN PARA CLAUDE CODE

```
backend/
  server.py          — FastAPI bootstrap, include_routers, startup/shutdown
  services/
    scheduler.py     — APScheduler: todos los cron jobs. AGREGAR aquí el Global66 6AM
    accounting_engine.py — Motor matricial: clasificar_movimiento(). USAR desde global66
    bank_reconciliation.py — Parsers bancarios + BankReconciliationEngine
    event_bus_service.py — EventBusService
  routers/
    global66.py      — Webhook Global66 existente. MEJORAR con motor matricial
    conciliacion.py  — Cargar extracto. NO TOCAR
    scheduler.py     — Trigger manual de jobs. AGREGAR jobs nuevos
    n8n_hooks.py     — CREAR NUEVO: endpoints para n8n
  database.py        — Motor async MongoDB. NUNCA modificar
  alegra_service.py  — request_with_verify(). USAR siempre para escrituras
```

## COLECCIONES MONGODB RELEVANTES PARA BUILD 25

- `global66_transacciones_procesadas` — anti-dup Global66 (ya existe)
- `conciliacion_movimientos_procesados` — hashes de movimientos causados
- `contabilidad_pendientes` — backlog de movimientos para revisión manual
- `roddos_events` — bus de eventos (append-only)
- `cfo_alertas` — alertas para el CFO
