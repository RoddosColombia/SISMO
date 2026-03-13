# RODDOS Contable IA — PRD

**Fecha:** 2026-03-12
**Versión:** 2.0

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
- **PDF Parsing:** pdfplumber + Claude AI para extracción de facturas Auteco

---

## Módulos Implementados (v2.0)

### 1. Autenticación
- Login con JWT (bcrypt + PyJWT)
- Roles admin/user
- Botones demo en login
- **Sitio completamente privado** — todas las rutas requieren autenticación

### 2. Dashboard Financiero
- 4 KPIs: Ventas, Gastos, Flujo de caja, Por cobrar
- Gráfico de área (AreaChart recharts) — Ingresos vs Gastos 6 meses
- Tablas: Últimas facturas de venta y compra

### 3. Facturación de Venta (Módulo 1)
- Lista de facturas con estados (Pendiente/Pagada/Vencida)
- Nueva factura con: autocomplete cliente, items con IVA, AlegraAccountSelector
- Preview asiento contable en tiempo real (JournalEntryPreview)
- POST /invoices → Alegra

### 4. Facturación de Compra (Módulo 2)
- Lista de facturas de proveedor
- Nueva factura de compra con: múltiples líneas, selector de cuenta por ítem
- POST /bills → Alegra

### 5. Registro de Cuotas (Módulo 3)
- Lista facturas abiertas desde Alegra
- Formulario de pago con selección de cuenta bancaria
- POST /payments → Alegra

### 6. Causación de Ingresos (Módulo 4)
- Causación con tipo de ingreso (operacional, no operacional, etc.)
- Auto-carga cuenta de ingreso según tipo
- Preview asiento completo con validación débitos = créditos
- POST /journal-entries → Alegra

### 7. Causación de Egresos (Módulo 5)
- Causación con tipo de egreso (arrendamiento, honorarios, personal, etc.)
- Validación de cuentas NIIF
- POST /journal-entries → Alegra

### 8. Conciliación Bancaria (Módulo 8)
- Selector de cuenta bancaria
- Tabla de movimientos con checkbox
- POST /bank-accounts/{id}/reconciliations → Alegra

### 9. Inventario Auteco (NUEVO - Módulo 9)
- **Upload de factura PDF de Auteco** → Claude AI extrae datos de motos
- Tabla de inventario: Placa, Marca, Versión, Color, Año, Motor, Chasis, Costo, IVA, IPOC, Total, Estado, Ubicación
- **Registro automático de cada moto como ítem en Alegra** (POST /items)
- Estados: Disponible, Vendida, Entregada
- KPIs: Total motos, Disponibles, Inversión total
- CRUD completo en MongoDB (inventory_service.py)

### 10. Impuestos y Alertas (Módulo 6 — actualizado v2.1)
- **IVA configurable**: periodicidad (bimestral/cuatrimestral/anual) + períodos personalizados + fecha límite ajustable
- **Saldo a favor DIAN**: campo configurable con fecha y nota — se aplica automáticamente al IVA a pagar
- **Estado en tiempo real desde Alegra**: IVA cobrado acumulado, IVA descontable, IVA bruto, proyección al cierre del período
- **Sugerencias inteligentes** para reducir IVA (urgentes si quedan <45 días)
- **AI Chat actualizado**: incluye estado IVA cuatrimestral en contexto cuando el usuario pregunta por IVA
- Calendario fiscal dinámico basado en configuración guardada
- Tabla de tarifas vigentes Colombia 2025

### 11. Retenciones (Módulo 7)
- Calculadora ReteFuente según tipo de transacción (tabla DIAN 2025)
- Cálculo ReteIVA y ReteICA por ciudad
- Tabla de tarifas ReteFuente y ReteICA

### 12. Nómina (Módulo 9)
- Liquidación de nómina para múltiples empleados
- SMLMV 2025: $1,423,500 | Aux. Transporte: $200,000
- Deducciones empleado + aportes patronales
- Causación automática → POST /journal-entries Alegra

### 13. Prestaciones Sociales (Módulo 10)
- Calculadora cesantías, intereses cesantías, prima, vacaciones
- Provisión mensual recomendada
- Fórmulas según CST Colombia

### 14. Estado de Resultados (Módulo 11)
- Ingresos vs egresos del período
- Gráfico BarChart por mes
- KPIs: Ingresos, Egresos, Utilidad Bruta, Margen Bruto

### 15. Egresos Clasificados (Módulo 12)
- Clasificación automática fijos vs variables
- PieChart de distribución
- Top proveedores con barra de progreso

### 16. Presupuesto (Módulo 13)
- Plan presupuestal mensual almacenado en MongoDB
- Comparación vs ingresos reales de Alegra
- Variación presupuesto vs ejecución

### 17. Configuración (Settings)
- Tab "Integración Alegra": email + token + botón probar conexión
- Toggle modo demo (activo por defecto)
- Sincronizar cuentas
- Tab "Cuentas Predeterminadas": AlegraAccountSelector para 15 tipos

### 18. Asistente IA Chat (Ejecutor Real)
- Botón flotante en todas las páginas
- **Function calling real**: Claude detecta intención → genera payload JSON → muestra tarjeta de confirmación
- Flujo: mensaje → resumen en tarjeta → "Confirmar y ejecutar en Alegra" → resultado en Alegra
- Acciones soportadas: crear_factura_venta, registrar_factura_compra, crear_causacion, registrar_pago, crear_contacto
- Log de auditoría de acciones ejecutadas

---

## Plan de Cuentas NIIF Colombia (Mock Data)
- 60+ cuentas: Activos (1), Pasivos (2), Patrimonio (3), Ingresos (4), Gastos (5/52/53/54), Costos (6)
- 10 contactos, 5 facturas venta/compra, 2 cuentas bancarias

---

## Configuración .env Backend
- MONGO_URL: Local MongoDB
- DB_NAME: roddos_contable
- JWT_SECRET: configurado
- EMERGENT_LLM_KEY: configurado (Claude Sonnet 4.5)

---

## Colecciones MongoDB
- **users**: id, email, password_hash, name, role, is_active, created_at
- **alegra_credentials**: id, email, token, is_demo_mode
- **default_accounts**: operation_type, account_id, account_code, account_name
- **chat_messages**: id, session_id, role, content, timestamp, user_id
- **audit_logs**: id, user_id, user_email, endpoint, method, request_body, response_status, timestamp
- **inventario_motos**: id, marca, version, color, ano_modelo, motor, chasis, costo, iva_compra, ipoconsumo, total, estado, placa, ubicacion, alegra_item_id, archivo_origen, created_at
- **presupuesto**: id, mes, ano, categoria, concepto, valor_presupuestado, cuenta_alegra_id, updated_at

---

## Lo que funciona (v2.0)
- [x] Auth JWT con roles admin/usuario + sitio completamente privado
- [x] Dashboard con KPIs + gráfica + tablas
- [x] Facturación de Venta (crear + listar + anular)
- [x] Facturación de Compra (crear + listar)
- [x] Registro de Cuotas (listar facturas + pagar)
- [x] Causación de Ingresos (con preview asiento)
- [x] Causación de Egresos (con preview asiento + validaciones)
- [x] Conciliación Bancaria (marcar movimientos)
- [x] Inventario Auteco (PDF upload + AI parse + tabla + registro Alegra)
- [x] Impuestos y Alertas (calendario + calculadora IVA)
- [x] Retenciones (calculadora DIAN 2025)
- [x] Nómina (liquidación + causación Alegra)
- [x] Prestaciones Sociales (cesantías + prima + vacaciones)
- [x] Estado de Resultados (P&L desde Alegra)
- [x] Egresos Clasificados (fijos vs variables + análisis)
- [x] Presupuesto (MongoDB + comparación real Alegra)
- [x] Settings (credenciales Alegra + cuentas predeterminadas + demo mode)
- [x] AI Chat Ejecutor (Claude Sonnet 4.5 + function calling + confirmación + ejecución Alegra)
- [x] AlegraAccountSelector en todos los módulos relevantes
- [x] Modo Demo (datos mock NIIF Colombia)

---

## Backlog Priorizado

### P0 — Crítico
- Ninguno pendiente

### P1 — Alta prioridad
- ~~Exportar facturas/causaciones a PDF/Excel~~ ✅ COMPLETADO
- Notificaciones de facturas próximas a vencer
- Módulo de ventas de motos Auteco (vinculado al inventario)

### P2 — Mejoras
- Webhooks de Alegra (invoice.created, payment.created)
- 2FA para administradores
- Log de auditoría visible en UI
- Autocomplete items en facturas desde Alegra
- Módulo de gestión de usuarios desde UI admin

---

## Credenciales de prueba
- Admin: contabilidad@roddos.com / Admin@RODDOS2025!
- Usuario: compras@roddos.com / Contador@2025!


## Changelog
- 2025-03: Login bug P0 corregido (useNavigate faltante)
- 2025-03: Credenciales actualizadas: contabilidad@roddos.com / compras@roddos.com
- 2025-03: Exportación PDF + Excel en Estado de Resultados, Facturación Venta/Compra, Inventario Auteco
- 2025-03: Rediseño completo Dark Mode según brandbook RODDOS: #121212 negro base, #00E5FF cyan, #00C853 verde, fonts Montserrat/Raleway
- 2025-03: Diseño híbrido: contenido blanco (#F8FAFC) + sidebar/header dark RODDOS
- 2025-03: Conexión real Alegra activada — RODDOS SAS (contabilidad@roddos.com)
- 2025-03: Helpers getDocNumber/getVendorName para compatibilidad mock/real Alegra
- 2025-03: Fix 403 en alegra/accounts → devuelve [] sin crashear frontend
- 2025-03: Status badges migrados a light-mode (bg-blue-100 text-blue-700)
- 2025-03: Fix bug searchAccounts — eliminado filtro incorrecto subAccounts !== undefined
- 2025-03: AlegraAccountSelector mejora estado vacío: muestra link a Alegra para regenerar token
- 2025-03: Badge token_invalid en header y Settings cuando Alegra retorna 401
- 2025-03: Instrucciones de token actualizado para apuntar a app.alegra.com/user/profile#token
- **2026-02: FIX P0 — /api/alegra/accounts ahora usa GET /categories de Alegra (233 cuentas reales NIIF)**
- **2026-02: AlegraAccountSelector actualizado para NIIF sin códigos PUC — agrupa por tipo (asset/liability/income/expense/cost)**
- **2026-02: searchAccounts usa campo type en lugar de prefijos de código PUC**
- **2026-02: AI Chat — gather_accounts_context() carga plan de cuentas real en contexto del agente**
- **2026-02: AI Chat — sistema de aprendizaje de patrones RODDOS: cuentas_usadas + frecuencia_count en agent_memory**
- **2026-02: AI Chat — modo automático activo cuando patrón tiene 5+ usos**

## Backlog Priorizado

### P0 — Crítico
- Ninguno pendiente ✅

### P1 — Alta prioridad
- Prueba end-to-end módulos contables (Causación Ingresos/Egresos, Nómina) con cuentas reales
- Prueba creación de factura de venta real desde la aplicación
- Notificaciones de facturas próximas a vencer
- Módulo de ventas de motos Auteco (vinculado al inventario)

### P2 — Mejoras
- Webhooks de Alegra (invoice.created, payment.created)
- 2FA para administradores
- Log de auditoría visible en UI
- Autocomplete items en facturas desde Alegra
- Módulo de gestión de usuarios desde UI admin
- Refactorizar server.py en APIRouters modulares

## Refactoring ejecutado — Feb 2026
server.py 1.056 líneas → 130 líneas (thin bootstrap)
Estructura modular:
  backend/
  ├── server.py          (130 líneas — bootstrap only)
  ├── database.py        (13 líneas — MongoDB connection)
  ├── dependencies.py    (45 líneas — get_current_user, require_admin, log_action)
  └── routers/
      ├── auth.py        (85 líneas)
      ├── settings.py    (94 líneas)
      ├── alegra.py      (144 líneas)
      ├── chat.py        (51 líneas)
      ├── inventory.py   (191 líneas)
      ├── taxes.py       (161 líneas)
      ├── budget.py      (53 líneas)
      ├── dashboard.py   (178 líneas)
      └── audit.py       (35 líneas)
