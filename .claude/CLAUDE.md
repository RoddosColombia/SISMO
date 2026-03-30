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
4. `grep -rn "estado.*pending"` — debe dar 0 resultados
5. `pytest backend/tests/test_permissions.py backend/tests/test_event_bus.py backend/tests/test_mongodb_init.py backend/tests/test_phase4_agents.py -v` — todos deben pasar

**Si alguno falla: NO hacer commit hasta resolver.**

---

## ESTADO BUILD ACTUAL

- **BUILD:** 24 completo (`v24.0.0`)
- **Score:** 9.3/10
- **Tests:** 67 en verde
- **Próximo:** BUILD 25 — Agente Contador 8.5/10
- **Pendiente crítico:**
  - S1 chat transaccional F2 (3/10)
  - S2 facturación motos F6 (1/10)
  - S3 ingresos cuotas F7 (5/10)
  - S4 nómina F4 (0/10)
- **Hotfix aplicado:** ERROR-017 URL base Alegra — tag `v24-hotfix-alegra`
