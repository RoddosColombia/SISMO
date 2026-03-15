# RODDOS Contable IA — CHANGELOG

## 2026-03-15 — BUILD 12 (fase 1): CFO Liquidity Model + P&L + Inventory Costs

### Correcciones Críticas de Modelo de Negocio
- **Deficit semanal corregido**: Formula cambiada de `recaudo - gastos×3` a `recaudo - gastos`
  - Antes: -$20,840,600 (incorrecto — incluia reserva × 2 gastos extra)
  - Ahora: -$5,840,600 = $1,659,400 recaudo - $7,500,000 gastos
- **RECAUDO_SEMANAL_BASE actualizado**: $1,509,500 → $1,659,400 (10 loanbooks, incluye Sindy Beltrán)
- **REGLA FUNDAMENTAL DE LIQUIDEZ** agregada al system prompt del Agente CFO:
  - RODDOS vende 100% a cuotas (no cash sales)
  - Liquidez real = recaudo semanal (cuotas), NO facturación
  - Separación contable (P&L base devengada) vs financiera (base caja)
  - Agente ahora responde correctamente a "¿cuánto entra esta semana?" → $1,659,400

### Nuevas Features
- **Estado de Resultados P&L** (`GET /api/cfo/estado-resultados?periodo=YYYY-MM`):
  - Datos reales de Alegra (ingresos de facturas, gastos de bills)
  - Comparativo vs mes anterior
  - Modo "parcial" cuando gastos no están en Alegra todavía
  - $78M ingresos marzo 2026 desde Alegra real
- **Exportación PDF y Excel del P&L**:
  - `GET /api/cfo/estado-resultados/pdf?periodo=...`
  - `GET /api/cfo/estado-resultados/excel?periodo=...`
- **UI P&L en CFO.tsx**: Selector de período, botón "Cargar P&L", tabla de resultados
- **Widget Sostenibilidad en Dashboard**: 10/45 créditos, countdown dinámico a Jun 20 2026, recaudo $1.659.400, deficit -$5.840.600
- **Carga de costos de inventario (PARTE 1)**:
  - Backend: `GET /api/inventario/plantilla-costos`, `POST /api/inventario/cargar-costos/preview`, `POST /api/inventario/cargar-costos/confirmar`
  - Frontend: Botón "Cargar Costos" en InventarioAuteco.js, modal de 2 pasos (descarga plantilla → sube Excel → vista previa → confirmar)
- **PlExportCard en AgentChatPage**: El agente puede responder con tarjeta de exportación P&L (PDF + Excel) cuando se solicita exportar

### Bug Fixes
- `rollRateNum` indefinido en Dashboard.tsx → calculado como `(nuevas_moras / activos) * 100`
- CFO.tsx error de compilación por `</section>` stray tag → corregido añadiendo `<section>` wrapper
- `RECAUDO_SEMANAL_BASE` constante obsoleta en cfo_estrategico.py actualizada

## 2026-02 — BUILD 11: Deudas, Loanbook, Entrega Motos (ver PRD.md)
