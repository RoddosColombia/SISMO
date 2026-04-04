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
- **GET /journals da TIMEOUT consistente** — con o sin filtros de fecha, con cualquier offset. El endpoint es inutilizable para listas grandes. NUNCA usar GET /journals en scripts de operación masiva.
- **NUNCA usar `date_afterOrNow` / `date_beforeOrNow`** — causan TIMEOUT adicional (confirmado en producción 3+ veces).
- **Para eliminar journals en bulk: DELETE /journals/{id} con IDs conocidos** — único método confiable. Los 404 son inofensivos (ID no existe). AC-XX en Alegra = numeric ID XX (AC-69 = DELETE /journals/69).
- **Journals a CONSERVAR en RODDOS:** solo facturas de venta (/invoices) y bills de Auteco (/bills). Todo lo demás en /journals se puede eliminar si es necesario.
- **consultar_journals NO está en el ACTION_MAP** (ERROR-016 pendiente BUILD 23). El agente no puede verificar journals vía chat.

---

## SKILL: RENDER SHELL — REGLAS INAMOVIBLES

- **Scripts > 60 segundos:** SIEMPRE usar `nohup python -u script.py > /tmp/nombre.log 2>&1 &` — sin `nohup` la sesión SSH muere y el proceso se cancela.
- **Flag `-u` OBLIGATORIO con nohup** — sin `-u`, Python bufferiza el output y `tail -f` no muestra nada hasta que el buffer se llena. Con `-u` el output es inmediato.
- **Monitoreo:** `tail -f /tmp/nombre.log` para ver progreso. `Ctrl+C` sale del tail sin matar el proceso.
- **Verificar proceso vivo:** `ps aux | grep script_name`
- **Scripts en Render Shell:** siempre correr desde `~/project/src/backend/` — el `.env` vive ahí.
- **Comandos de una línea en python -c:** funcionan para operaciones < 30 segundos. Para operaciones largas, crear script + push + nohup.

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
- **Próximo:** BUILD 23 — Agente Contador 8.5/10
- **Pendiente crítico:**
  - ERROR-016: `consultar_journals` falta en ACTION_MAP — agente no puede auditar Alegra
  - S1 chat transaccional F2 (3/10)
  - S2 facturación motos F6 (1/10)
  - S3 ingresos cuotas F7 (5/10)
  - S4 nómina F4 (0/10)
- **Hotfix aplicado:** ERROR-017 URL base Alegra — tag `v24-hotfix-alegra`

## LIMPIEZA CONTABLE ENERO-FEBRERO 2026 — ESTADO

- ✅ Journals extracto conciliación (IDs 146-241 y 898-957) eliminados de Alegra
- ✅ MongoDB conciliacion_* limpio (303 hashes + 3 extractos eliminados)
- ✅ FASE 0 Plan Maestro completada (permissions.py bloqueo DELETE /invoices)
- ✅ FASE 1 Plan Maestro completada (auditoría Alegra)
- ✅ FASE 2 completa — Alegra limpio de enero y febrero 2026 (0 journals restantes)
- 🔜 FASE 3 siguiente — cargar extractos bancarios uno a uno con dry-run + aprobación
