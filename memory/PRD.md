# RODDOS Contable IA — PRD

**Fecha:** 2025-10-20
**Versión:** 1.0 (MVP)

---

## Problema

Los contadores colombianos que usan Alegra ERP necesitan una capa inteligente que automatice el registro de transacciones contables, reduzca errores en la selección de cuentas NIIF, y acelere el trabajo diario a través de un asistente de IA.

---

## Usuarios

- **Administrador (admin@roddos.com):** Acceso total, configura credenciales Alegra, cuentas predeterminadas, modo demo.
- **Contador (contador@roddos.com):** Acceso a módulos, puede cambiar cuentas en cada formulario.

---

## Arquitectura

- **Frontend:** React 18 + Tailwind CSS + shadcn/ui · React Router v7
- **Backend:** FastAPI (Python) + MongoDB · Puerto 8001
- **IA:** Claude Sonnet 4.5 via emergentintegrations (EMERGENT_LLM_KEY)
- **Integración:** Alegra REST API (Basic Auth) — modo Demo con mock data NIIF Colombia

---

## Módulos Implementados (MVP v1.0)

### 1. Autenticación
- Login con JWT (bcrypt + PyJWT)
- Roles admin/user
- Botones demo en login

### 2. Dashboard Financiero
- 4 KPIs: Ventas, Gastos, Flujo de caja, Por cobrar
- Gráfico de área (AreaChart recharts) — Ingresos vs Gastos 6 meses
- Tablas: Últimas facturas de venta y compra
- Acciones rápidas

### 3. Facturación de Venta (Módulo 1)
- Lista de facturas con estados (Pendiente/Pagada/Vencida)
- Nueva factura con: autocomplete cliente, items con IVA, AlegraAccountSelector (cuenta ingreso + cuenta recaudo)
- Preview asiento contable en tiempo real (JournalEntryPreview)
- POST /invoices → Alegra

### 4. Facturación de Compra (Módulo 2)
- Lista de facturas de proveedor
- Nueva factura de compra con: múltiples líneas, selector de cuenta por ítem
- AlegraAccountSelector por línea (gastos 5xxx/6xxx)
- POST /bills → Alegra

### 5. Causación de Ingresos (Módulo 4)
- Causación con tipo de ingreso (operacional, no operacional, etc.)
- Auto-carga cuenta de ingreso según tipo
- Manejo de IVA y retención en la fuente
- Preview asiento completo con validación débitos = créditos
- POST /journal-entries → Alegra

### 6. Causación de Egresos (Módulo 5)
- Causación con tipo de egreso (arrendamiento, honorarios, personal, etc.)
- Validación: alerta si cuenta seleccionada no corresponde al tipo
- Manejo IVA descontable y retención practicada
- POST /journal-entries → Alegra

### 7. Conciliación Bancaria (Módulo 8)
- Selector de cuenta bancaria
- Input de saldo extracto
- Tabla de movimientos con checkbox para marcar como conciliados
- Resumen: saldo extracto vs conciliado, diferencia
- POST /bank-accounts/{id}/reconciliations → Alegra

### 8. Configuración (Settings)
- Tab "Integración Alegra": email + token + botón probar conexión
- Toggle modo demo (activo por defecto)
- Sincronizar cuentas (GET /accounts fresco)
- Tab "Cuentas Predeterminadas": AlegraAccountSelector para ~15 tipos de operaciones

### 9. Asistente IA Chat
- Botón flotante dorado en todas las páginas
- Panel slide-in con historial de conversación
- Claude Sonnet 4.5 con system prompt de contabilidad colombiana NIIF 2025
- Detecta acciones (<action> JSON) y las presenta como botones de navegación
- Eliminar historial de sesión

### 10. AlegraAccountSelector (Componente Central)
- Popover con búsqueda por código o nombre
- Árbol NIIF agrupado por clase (1xxx, 2xxx, ...)
- Filtro contextual por tipo (income/expense/asset/liability)
- allowedCodes para restricción por prefijo
- Badge "CUENTA ALEGRA", fondo #F0F4FF
- Indicadores de tipo con colores (verde=ingreso, rojo=gasto, azul=activo, etc.)

---

## Plan de Cuentas NIIF Colombia (Mock Data)
- 60+ cuentas: Activos (1), Pasivos (2), Patrimonio (3), Ingresos (4), Gastos admin (5), Gastos ventas (52), Gastos no operacionales (53), Impuestos (54), Costos (6)
- 10 contactos (5 clientes + 5 proveedores)
- 5 facturas de venta + 5 de compra
- 2 cuentas bancarias (Bancolombia, Davivienda)
- 2 comprobantes de diario

---

## Configuración .env Backend
- MONGO_URL: Local MongoDB
- DB_NAME: roddos_contable
- JWT_SECRET: configurado
- EMERGENT_LLM_KEY: configurado (Claude Sonnet 4.5)

---

## Lo que funciona (v1.0)
- [x] Auth JWT con roles admin/usuario
- [x] Dashboard con KPIs + gráfica + tablas
- [x] Facturación de Venta (crear + listar + anular)
- [x] Facturación de Compra (crear + listar)
- [x] Causación de Ingresos (con preview asiento)
- [x] Causación de Egresos (con preview asiento + validaciones)
- [x] Conciliación Bancaria (marcar movimientos)
- [x] Settings (credenciales Alegra + cuentas predeterminadas + demo mode)
- [x] AI Chat (Claude Sonnet 4.5 + acciones sugeridas)
- [x] AlegraAccountSelector en todos los módulos
- [x] Modo Demo (datos mock NIIF Colombia)
- [x] Proxy Alegra (funciona con API real o mock)

---

## Backlog Priorizado

### P0 — Funcionalidad bloqueante (próxima iteración)
- Registro de pagos a facturas existentes (POST /payments vinculado a facturas)
- Módulo de Impuestos (cálculo IVA período, pagos DIAN)

### P1 — Mejoras de alto valor
- Exportar facturas/causaciones a Excel o PDF
- Autocomplete de items en facturas (carga de items desde Alegra)
- Retenciones: calculadora DIAN con UVT 2025 y selección de cuenta
- Notificaciones de facturas próximas a vencer
- Módulo de Estado de Resultados (GET /reports)

### P2 — Features adicionales
- Módulos 9-14 del prompt original (Nómina, Prestaciones, Presupuesto)
- Módulo de gestión por Admin (activar/desactivar módulos)
- Webhooks de Alegra (invoice.created, payment.created)
- Log de auditoría en UI (tabla de acciones)
- 2FA para administradores

---

## Next Steps Recomendados
1. Conectar credenciales reales de Alegra en Configuración → Integración
2. Configurar las cuentas predeterminadas en Settings → Cuentas Predeterminadas
3. Probar creación real de facturas con la API de Alegra
4. Considerar activar módulo de Impuestos para liquidación IVA bimestral
