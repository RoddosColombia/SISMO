# RODDOS Contable IA — PRD

**Fecha:** 2026-03-13
**Versión:** 2.2

---

## Problema

Los contadores colombianos que usan Alegra ERP necesitan una capa inteligente que automatice el registro de transacciones contables, reduzca errores en la selección de cuentas NIIF, y acelere el trabajo diario a través de un asistente de IA.

---

## Usuarios

- **Administrador (contabilidad@roddos.com):** Acceso total, configura credenciales Alegra, cuentas predeterminadas, modo demo.
- **Contador (compras@roddos.com):** Acceso a módulos, puede cambiar cuentas en cada formulario.

---

## Arquitectura

- **Frontend:** React 18 + Tailwind CSS + shadcn/ui · React Router v7 · react-markdown
- **Backend:** FastAPI (Python) + MongoDB · Puerto 8001
- **IA:** Claude Sonnet 4.5 via emergentintegrations (EMERGENT_LLM_KEY)
- **Integración:** Alegra REST API (Basic Auth) — modo Demo con mock data NIIF Colombia
- **PDF Parsing:** pdfplumber + Claude AI para extracción de facturas Auteco

---

## Módulos Implementados (v2.2)

### 1. Autenticación
- Login con JWT (bcrypt + PyJWT)
- Roles admin/user
- Botones demo en login
- **Sitio completamente privado** — todas las rutas requieren autenticación

### 2. Dashboard Financiero
- 4 KPIs: Ventas, Gastos, Flujo de caja, Por cobrar
- **Filtro por fechas** (desde/hasta) — default mes actual
- Subtítulo dinámico con período seleccionado
- Gráfico de área (AreaChart recharts) — Ingresos vs Gastos 6 meses **con datos reales de Alegra**
- Tablas: Últimas facturas de venta y compra del período seleccionado

### 3. Facturación de Venta (Módulo 1)
- Lista de facturas con **filtro por fechas** (default mes actual)
- Nueva factura con: **Plan de pago** (Contado/P39S/P52S/P78S), auto-cálculo fecha finalización
- **Diálogo de confirmación** antes de anular factura
- Preview asiento contable en tiempo real (JournalEntryPreview)
- POST /invoices → Alegra

### 4. Facturación de Compra (Módulo 2)
- Lista de facturas de proveedor con **filtro por fechas**
- Nueva factura de compra con: **Plazo de pago** (Contado/30/60/80/90 días), auto-cálculo fecha pago
- POST /bills → Alegra

### 5. Registro de Cuotas (Módulo 3)
- Lista facturas abiertas desde Alegra — **solo desde marzo 2026**
- Banner informativo integración con módulo Loanbook
- Formulario de pago con selección de cuenta bancaria
- POST /payments → Alegra

### 6. Causación de Ingresos (Módulo 4)
- **Panel "Manual de uso"** con guía completa e integración IA
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

### 9. Motos (Módulo 9)
- **Upload de factura PDF de Auteco** → Claude AI extrae datos de motos
- Tabla de inventario: Placa, Marca, Versión, Color, Año, Motor, Chasis, Costo, IVA, IPOC, Total, Estado, Ubicación
- **Registro automático de cada moto como ítem en Alegra** (POST /items)
- Estados: Disponible, Vendida, Entregada
- CRUD completo en MongoDB (inventory_service.py)

### 10. Impuestos y Alertas (Módulo 6)
- **IVA configurable**: periodicidad (bimestral/cuatrimestral/anual) + períodos personalizados
- **Saldo a favor DIAN**: campo configurable
- **Estado en tiempo real desde Alegra**: IVA cobrado acumulado, IVA descontable, proyección
- **Sugerencias inteligentes** para reducir IVA
- Calendario fiscal dinámico basado en configuración guardada

### 11. Retenciones (Módulo 7)
- Calculadora ReteFuente según tipo de transacción (tabla DIAN 2025)
- Cálculo ReteIVA y ReteICA por ciudad

### 12. Nómina (Módulo 9)
- Liquidación de nómina para múltiples empleados
- SMLMV 2025: $1,423,500 | Aux. Transporte: $200,000
- Deducciones empleado + aportes patronales
- Causación automática → POST /journal-entries Alegra

### 13. Prestaciones Sociales (Módulo 10)
- Calculadora cesantías, intereses cesantías, prima, vacaciones

### 14. Estado de Resultados (Módulo 11)
- Ingresos vs egresos del período
- Gráfico BarChart por mes

### 15. Egresos Clasificados (Módulo 12)
- Clasificación automática fijos vs variables
- PieChart de distribución
- Top proveedores con barra de progreso

### 16. Presupuesto (Módulo 13)
- Plan presupuestal mensual almacenado en MongoDB
- Comparación vs ingresos reales de Alegra

### 17. Configuración (Settings)
- Tab "Integración Alegra": email + token + botón probar conexión
- Toggle modo demo (activo por defecto)
- Tab "Cuentas Predeterminadas"
- Tab "Mercately" (admin-only)

### 18. Asistente IA Chat — PANTALLA COMPLETA (v2.2)
- **Primera pantalla tras login**: chat full-screen a `/agente-contable`
- **Sidebar**: "Agente Contable" como PRIMER ítem con badge verde parpadeante
- **Botón flotante ELIMINADO**: chat integrado como página principal
- **Mensaje de bienvenida** personalizado al iniciar sesión
- **Function calling real**: Claude detecta intención → genera payload JSON → tarjeta confirmación → ejecuta en Alegra
- **Respuestas en Markdown**: bold, listas, tablas, código renderizados correctamente
- **Chat persistente**: historial cargado desde MongoDB por `session_id` estable
- Acciones soportadas: crear_factura_venta, registrar_factura_compra, crear_causacion, registrar_pago, crear_contacto, registrar_entrega

### 19. Procesamiento de Documentos PDF/Imagen (v2.2 — NUEVO)
- **Adjuntar archivos**: ícono 📎, drag & drop sobre chat, Ctrl+V portapapeles
- **Vista previa** del archivo en barra de entrada antes de enviar
- **Análisis multimodal**: backend envía archivo a Claude Sonnet vía FileContent (emergentintegrations)
- **System prompt específico** para extracción de: tipo documento, proveedor, NIT, montos, fecha, concepto, retenciones
- **Tarjeta de propuesta editable**: todos los campos editables inline antes de confirmar
- **Detección Loanbook**: identifica pagos de cuotas de Loanbook RODDOS
- **Manejo documentos ilegibles**: muestra campos faltantes con advertencia
- **Flujo confirm**: datos confirmados → Claude construye payload → ejecución automática en Alegra
- Solo imágenes (JPG, PNG, WebP) y PDF soportados, máx 20MB

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
- **loanbook**: id, codigo, cliente_nombre, factura_alegra_id, plan, num_cuotas, saldo_pendiente, estado, cuotas[]
- **agent_memory**: id, user_id, tipo, descripcion, payload_alegra, cuentas_usadas, frecuencia_count

---

## Backlog Priorizado

### P0 — Crítico
- Ninguno pendiente

### P1 — Alta prioridad
- Verificación E2E procesamiento documentos con comprobantes reales
- Dashboard rediseño con feed de eventos en tiempo real
- Sincronización Loanbook ↔ Cartera verificación E2E
- Notificaciones de facturas próximas a vencer

### P2 — Mejoras
- Integración Mercately (WhatsApp) — requiere credenciales del usuario
- Módulo ventas motos (vinculado al inventario)
- Log de auditoría visible en UI
- Autocomplete items en facturas
- Módulo gestión de usuarios desde UI admin
- Webhooks de Alegra (invoice.created, payment.created)

---

## Credenciales de prueba
- Admin: contabilidad@roddos.com / Admin@RODDOS2025!
- Usuario: compras@roddos.com / Contador@2025!

---

## Changelog
- 2025-03: Login bug P0 corregido
- 2025-03: Exportación PDF + Excel en Estado de Resultados, Facturación Venta/Compra, Inventario
- 2025-03: Rediseño Dark Mode según brandbook RODDOS: #121212, #00E5FF, #00C853
- 2025-03: Conexión real Alegra activada — RODDOS SAS
- 2026-02: Fix /api/alegra/accounts → GET /categories (233 cuentas reales NIIF)
- 2026-02: AI Chat — gather_accounts_context() + sistema aprendizaje patrones
- 2026-03-13: Sprint Agente Contable — Cartera mobile, Loanbook, post_action_sync, Bus de Eventos
- 2026-03-13: Fix CRÍTICO journal-entries → /journals, formato entries corregido
- 2026-03-13: Auditoría Integración Alegra — 64/67 puntos verificados (96%)
- **2026-03-13 v2.2: REDISEÑO CHAT IA + PROCESAMIENTO DOCUMENTOS**
  - Chat de IA transformado a página full-screen (`/agente-contable`) — botón flotante eliminado
  - Login redirige a `/agente-contable` como pantalla principal
  - Sidebar: "Agente Contable" como primer ítem con badge verde parpadeante
  - react-markdown integrado: respuestas con bold, listas, tablas, código renderizados
  - Historial de chat persistente por sesión (cargado desde MongoDB)
  - Procesamiento multimodal PDF/Imagen: FileContent de emergentintegrations
  - Tarjeta de propuesta editable con campos inline (proveedor, NIT, fecha, montos)
  - Drag & drop, clip 📎 y Ctrl+V para adjuntar archivos
  - Detección automática pagos Loanbook
  - System prompt específico para análisis contable de documentos
