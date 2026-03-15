# RODDOS Contable IA — ROADMAP

## P0 — BUILD 14 (siguiente)
- Integración WhatsApp automática (Mercately — actualmente mocked)
  - Procesar mensajes libres de clientes
  - Enviar recordatorios automáticos de cuotas

## P1 — BUILD 14/15
- Módulo Presupuesto: Conexión completa con CFO Estratégico
  - Sincronización bidireccional con `cfo_presupuesto_mensual`
  - Instrucciones CFO reflejadas en módulo
- Módulo Impuestos: Datos reales desde Alegra
  - IVA bimestral cobrado vs descontable
  - ReteFuente del período
  - ReteICA Bogotá 0.414%
  - Provisión renta 33% automática

## P2 — Futuro
- Dashboard Inventory Widget (tabla motos disponibles)
- Panel de Aprendizaje ML (patrones de mora)
- Detección automática UVT para retenciones
- Parte 5 de BUILD 13: Procesamiento inteligente con memoria de preferencias (Auteco → mismo tratamiento)

## COMPLETADO

### BUILD 13 (2026-03-15)
- Menú simplificado: 10 items exactos (eliminados Facturación/Causaciones/Conciliación)
- Chat CFO Estratégico: nuevo chat en /cfo-estrategico con Claude Sonnet
  - System prompt estratégico diferente al Agente Contador
  - Instrucciones permanentes (cfo_instrucciones)
  - Compromisos con seguimiento (cfo_compromisos)
  - Historial independiente (cfo_chat_historia)
  - Badges dinámicos con datos reales en tiempo real
- Multi-PDF: file input acepta múltiples archivos + drag&drop múltiple + MultiFilePreview
- Cuotas Iniciales Card en Agente Contador
- Renombrado: CRM → Cartera, Agente CFO → Panel CFO

### BUILD 12 (2026-03-15)
- Corrección déficit semanal: -$5,840,600
- P&L dual view: SECCIÓN A (devengada) + SECCIÓN B (caja)
- Widget Sostenibilidad 10/45 créditos
- Carga de costos de inventario

### BUILD 11 y anteriores — ver CHANGELOG.md
