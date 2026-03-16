# RODDOS Contable IA — ROADMAP

## P0 — BUILD 14 (siguiente)
- Integración WhatsApp automática (Mercately — actualmente mocked)
  - Procesar mensajes libres de clientes
  - Enviar recordatorios automáticos de cuotas

## P2 — Futuro
- Dashboard Inventory Widget (tabla motos disponibles)
- Panel de Aprendizaje ML (patrones de mora)
- Detección automática UVT para retenciones
- Integración DIAN para semáforo impuestos

## COMPLETADO

### HOTFIX Agente Contador (2026-03-15)
- **Causa raíz:** `import re` duplicado en línea 1758 dentro de `process_chat` (ai_chat.py). Python marcaba `re` como variable local en todo el scope de la función async → UnboundLocalError en TODOS los mensajes.
- **Fix:** Eliminado el import duplicado (re ya importado a nivel módulo en línea 2)
- **Blindaje:** Nuevo `GET /api/health` con diagnóstico completo (MongoDB, Alegra, Anthropic, loanbooks, proveedores_config). Logging de errores del agente a colección `agent_errors`. Mensajes de error descriptivos en lugar del genérico "Hubo un error".
- **Test:** 13/13 grupos G1–G6 verificados (básicos, MongoDB, Alegra, contables, BUILD13, CFO).

### BUILD 13 COMPLETO (2026-03-15)
- Menú simplificado: 10 items exactos
- Chat CFO Estratégico: /cfo-estrategico con Claude Sonnet
- Multi-PDF: file input múltiple + drag&drop
- Cuotas Iniciales Card en Agente Contador
- **CORRECCIÓN CRÍTICA 1 — Autoretenedores:**
  - Colección `proveedores_config` creada
  - AUTECO KAWASAKI S.A.S. seeded como autoretenedor
  - Endpoints GET/POST /api/proveedores/config
  - Agente inyecta reglas autoretenedor en contexto
  - Detección de confirmación: "Sí, [Proveedor] es autoretenedora" → reversión automática
- **CORRECCIÓN CRÍTICA 2 — IVA Cuatrimestral:**
  - Backend: DEFAULT_IVA_CONFIG ya era cuatrimestral
  - Migración: configs bimestral → cuatrimestral automática en startup
  - CFO Estratégico quick action: "cuatrimestre" (no "bimestre")
- **PENDIENTE 1 — Memoria de preferencias:**
  - process_document_chat detecta proveedor recurrente en agent_memory
  - Inyecta patrón habitual en system prompt de análisis de documentos
  - Para PDFs sin patrón: instrucción para preguntar tipo de documento
- **PENDIENTE 2/3 — Módulos conectados:**
  - Impuestos: período cuatrimestral verificado y funcional
  - Presupuesto: muestra CfoInstruccionesPanel (reglas CFO estratégico) y CfoPresupuestoPanel

### BUILD 12 (2026-03-15)
- Corrección déficit semanal: -$5,840,600
- P&L dual view: SECCIÓN A (devengada) + SECCIÓN B (caja)
- Widget Sostenibilidad 10/45 créditos
- Carga de costos de inventario

### BUILD 11 y anteriores — ver CHANGELOG.md
