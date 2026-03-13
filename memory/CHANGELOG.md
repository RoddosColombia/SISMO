# RODDOS Contable IA — Changelog

## 2026-03-13 — Refactorización Estructural: Bus de Eventos + Cartera Mobile-First

### Backend — Arquitectura de Eventos
- `post_action_sync.py`: Sync completo tras acciones del Agente IA → actualiza loanbook cuotas, inserta en cartera_pagos, emite eventos
- `ai_chat.py`: Integra post_action_sync; respuesta incluye `sync.sync_messages` mostrando qué módulos fueron actualizados
- `AIChatWidget.js`: Muestra sync_messages en el chat después de ejecutar cada acción
- `routers/cartera.py`: Nuevo `GET /api/cartera/ruta-hoy` — vencidas + hoy con info de contacto
- `routers/dashboard.py`: Nuevos `GET /api/events/recent` y `GET /api/events/stats`
- `routers/loanbook.py`: Emite evento `pago.cuota.registrado` al bus tras registrar un pago

### Frontend — Cartera Mobile-First
- Rediseño completo de Cartera.js para cobrador de campo
- Header dark con stats en tiempo real y barra de progreso de cobro del día
- Tab "Ruta de Hoy": cuotas vencidas + para hoy con tarjetas coloreadas por urgencia
- Botones COBRAR (verde), Llamar y WhatsApp en cada tarjeta
- PagoBottomSheet: flujo de 3 toques para registrar un cobro, genera PDF automáticamente


### Dashboard
- Filtro por fechas (desde/hasta) — default: mes actual
- Subtítulo dinámico mostrando el período seleccionado
- Gráfico de 6 meses ahora carga datos reales de Alegra (en lugar de datos hardcodeados de Oct 2025)
- KPIs responden al filtro de fechas seleccionado

### Facturación de Venta
- Filtro por fechas (default mes actual) en la lista
- Columna "Vencimiento" renombrada a "Finalización"
- Nueva opción "Plan de pago" en el formulario (Contado, P39S, P52S, P78S)
  - Calcula automáticamente la Fecha de Finalización según el plan
  - Modelo vigente desde marzo 2026
- Diálogo de confirmación antes de anular una factura (previene anulaciones accidentales)

### Facturación de Compra
- Filtro por fechas (default mes actual) en la lista
- Columna "Descripción" renombrada a "Fecha de pago" (muestra dueDate de Alegra)
- Columna "Estado" renombrada a "Estado pago" (clarifica que es el estado de pago)
- Nueva opción "Plazo de pago" en el formulario con opciones:
  - Contado (mismo día), 30 días, 60 días, 80 días (Repuestos), 90 días (Motos Auteco)
  - Calcula automáticamente la fecha de pago estimada

### Registro de Cuotas
- Ahora solo muestra facturas desde el 1 de marzo de 2026
- Banner informativo que explica la integración con el módulo Loanbook

### Causación de Ingresos
- Nuevo panel "Manual de uso — Módulo de Causaciones IA" con:
  - Explicación de qué es una causación
  - Cómo usar el chat IA para crear causaciones automáticamente
  - Integración con Facturación de Venta
  - Integración con Registro de Pagos (Cartera)

### Módulo Motos (ex Inventario Auteco)
- Renombrado de "Inventario Auteco" a "Motos" en sidebar y página
- Descripción actualizada

### Bug fix
- Cartera.js: ícono `Calendar` faltaba en el import (causaba error de runtime)
