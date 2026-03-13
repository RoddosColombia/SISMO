# RODDOS Contable IA — Changelog

## 2026-03-13 — Mejoras Funcionales (Sesión actual)

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
