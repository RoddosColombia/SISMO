# QUICK REFERENCE — 32 TOOLS DEL AGENTE CONTADOR
## Ejemplos de uso, inputs, outputs

---

## CATEGORÍA 1: EGRESOS (6 Tools)

### 1. crear_causacion
**Descripción:** Gasto individual por chat conversacional
**Input:**
```json
{
  "descripcion": "Pagamos honorarios al abogado $800.000",
  "monto": 800000,
  "requiere_confirmacion": true
}
```
**Output (propuesta):**
```json
{
  "status": "pendiente_confirmacion",
  "propuesta": {
    "descripcion": "Pagamos honorarios al abogado $800.000",
    "monto": 800000,
    "cuenta_id": 5470,
    "cuenta_nombre": "Honorarios",
    "confianza": 0.95,
    "retenciones": {"ReteFuente": 80000}
  }
}
```
**ROG-1:** request_with_verify() POST /journals → GET /journals/{id}

---

### 2. crear_causacion_masiva
**Descripción:** Lote CSV >10 registros con BackgroundTasks
**Input:**
```json
{
  "csv_path": "/uploads/gastos_febrero_2026.xlsx",
  "banco": "BBVA",
  "mes": "febrero",
  "modo": "preview"
}
```
**Output (preview):**
```json
{
  "status": "preview_generado",
  "cantidad_registros": 96,
  "mensaje": "CSV cargado: 96 movimientos. Confirma con /ejecutar-csv para procesar."
}
```
**Si modo="ejecutar":**
```json
{
  "status": "job_lanzado",
  "job_id": "csv_job_1712530123.456",
  "mensaje": "Processing 96 registros en background. Ve a /backlog para ver progreso."
}
```

---

### 3. registrar_gasto_periodico
**Descripción:** Suscripciones/arrendamiento automático
**Input:**
```json
{
  "tipo_gasto": "arriendo",
  "monto": 3614953,
  "proveedor": "Arrendador Calle 127",
  "fecha_inicio": "2026-01-15",
  "frecuencia": "mensual"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "gasto_id": "60d5ec49c1234567890abcde",
  "mensaje": "Gasto periódico creado: Arrendador Calle 127 $3.614.953 mensual."
}
```

---

### 4. crear_nota_debito
**Descripción:** Corrección manual por Nota Débito
**Input:**
```json
{
  "numero_original": "JE-2026-03-0042",
  "razon": "Cuenta incorrecta: debió ser 5480 (Arriendo) no 5493 (Gastos Generales)",
  "ajuste_monto": -100000
}
```
**Output:**
```json
{
  "status": "exitoso",
  "alegra_id": "JE-2026-03-0145",
  "mensaje": "Nota Débito creada corrigiendo asiento #JE-2026-03-0042"
}
```

---

### 5. registrar_retenciones
**Descripción:** Manejo manual ReteFuente/ReteICA
**Input:**
```json
{
  "concepto": "honorarios_pn",
  "monto_base": 800000,
  "tasa_manual": null
}
```
**Output:**
```json
{
  "status": "calculado",
  "monto_base": 800000,
  "tasa": 0.1,
  "retencion": 80000,
  "a_pagar_neto": 720000,
  "mensaje": "Retención honorarios_pn: $80.000 sobre base $800.000"
}
```

---

### 6. crear_asiento_manual
**Descripción:** Acceso directo para correcciones urgentes
**Input:**
```json
{
  "descripcion": "Ajuste manual: comprobante extravío",
  "debitos": [{"cuenta_id": 5493, "monto": 50000}],
  "creditos": [{"cuenta_id": 111010, "monto": 50000}],
  "fecha": "2026-03-15"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "alegra_id": "JE-2026-03-0156",
  "mensaje": "Asiento manual creado: comprobante extravío"
}
```

---

## CATEGORÍA 2: INGRESOS (5 Tools)

### 7. registrar_ingreso_no_operacional
**Descripción:** Intereses, ventas recuperadas, otros
**Input:**
```json
{
  "tipo": "intereses_bancarios",
  "monto": 45000,
  "descripcion": "Intereses BBVA febrero",
  "fecha": "2026-02-28"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "alegra_id": "JE-2026-02-0089",
  "mensaje": "Ingreso registrado: $45.000"
}
```

---

### 8. registrar_cuota_cartera
**Descripción:** Pago de cuota (→ ingresos financieros)
**Input:**
```json
{
  "loanbook_id": "LB-2026-0012",
  "numero_cuota": 3,
  "monto": 179900,
  "fecha_pago": "2026-03-19"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "alegra_id": "JE-2026-03-0098",
  "mensaje": "Pago cuota #3 registrado: $179.900"
}
```

---

### 9. registrar_abono_socio
**Input:**
```json
{
  "socio_cedula": "80075452",
  "monto": 500000,
  "banco_origen": "BBVA"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "mensaje": "Abono registrado: $500.000 a CXC 80075452"
}
```

---

### 10. registrar_ingreso_financiero
**Input:**
```json
{
  "banco": "BBVA",
  "monto_interes": 45000,
  "periodo": "2026-02"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "alegra_id": "JE-2026-02-0087",
  "mensaje": "Intereses BBVA: $45.000 registrados"
}
```

---

### 11. registrar_ingreso_arrendamiento
**Input:**
```json
{
  "arrendatario": "Empresa XYZ S.A.S.",
  "monto_mensual": 2000000,
  "fecha_inicio": "2026-04-01"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "subarriendo_id": "60d5ec49c1234567890abcde",
  "mensaje": "Subarriendo registrado: Empresa XYZ S.A.S. $2.000.000/mes"
}
```

---

## CATEGORÍA 3: CONCILIACIÓN BANCARIA (6 Tools)

### 12. crear_causacion_desde_extracto
**Input:**
```json
{
  "extracto_path": "/uploads/BBVA_febrero_2026.xlsx",
  "banco": "BBVA",
  "mes": "febrero",
  "modo": "preview"
}
```
**Output (preview):** Muestra 100 movimientos propuestos
**Output (ejecutar):** Lanza background job

---

### 13. marcar_movimiento_clasificado
**Input:**
```json
{
  "movimiento_hash": "d7f4a8b2c9e1f3g5h7j9k",
  "cuenta_asignada": 5493
}
```
**Output:**
```json
{
  "status": "exitoso",
  "mensaje": "Movimiento d7f4a8... marcado como procesado en cuenta 5493"
}
```

---

### 14. crear_reintentos_movimientos
**Input:**
```json
{
  "movimiento_id": "mov_12345",
  "proxima_ejecucion": "2026-03-20T10:00:00Z"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "mensaje": "Movimiento mov_12345 agregado a cola de reintento para 2026-03-20T10:00:00Z"
}
```

---

### 15. auditar_movimientos_pendientes
**Input:**
```json
{
  "banco": "BBVA",
  "confianza_minima": 0.70
}
```
**Output:**
```json
{
  "status": "exitoso",
  "cantidad": 27,
  "pendientes": [...],
  "mensaje": "Encontrados 27 movimientos con confianza < 0.70"
}
```

---

### 16. sincronizar_extracto_global66
**Input:**
```json
{
  "mes": "2026-02",
  "forzar_reprocessamiento": false
}
```
**Output:** Status + cantidad sincronizados

---

### 17. resolver_duplicados_bancarios
**Input:**
```json
{
  "hashes_duplicados": ["hash1", "hash2", "hash3"],
  "accion": "mantener_primero"
}
```
**Output:**
```json
{
  "status": "exitoso",
  "mensaje": "Duplicados resueltos: acción 'mantener_primero' en 3 movimientos"
}
```

---

## CATEGORÍA 4: CONCILIACIÓN INGRESOS/EGRESOS (4 Tools)

### 18. validar_cobertura_gasto
**Input:**
```json
{
  "periodo": "2026-02",
  "tolerancia_pesos": 100000
}
```
**Output:** Diferencia entre Alegra y MongoDB

---

### 19. reportar_desfase_contable
**Input:** `{"periodo": "2026-02"}`
**Output:** P&L vs Caja real

---

### 20. sincronizar_cartera_alegra
**Input:**
```json
{
  "loanbook_id": "LB-2026-0012"
}
```
**Output:** Sincronización completada

---

### 21. auditar_balance_cierre
**Input:**
```json
{
  "mes": "febrero",
  "generar_reporte": true
}
```
**Output:** Reporte PDF

---

## CATEGORÍA 5: INVENTARIO (4 Tools)

### 22. actualizar_moto_vendida
**Input:**
```json
{
  "chasis_vin": "9FL25AF31VDB95058",
  "factura_id": "FACT-2026-0456"
}
```

---

### 23. registrar_entrega_moto
**Input:**
```json
{
  "loanbook_id": "LB-2026-0012",
  "fecha_entrega": "2026-03-17",
  "numero_placa": "ABC-123"
}
```

---

### 24. consultar_motos_disponibles
**Input:**
```json
{
  "modelo": "Raider",
  "cantidad_minima": 1
}
```

---

### 25. sincronizar_compra_auteco
**Input:**
```json
{
  "numero_factura_auteco": "E670155732",
  "mes": "febrero"
}
```

---

## CATEGORÍA 6: CONSULTAS (4 Tools)

### 26. consultar_journals_periodo
**Input:** `{"fecha_inicio": "2026-02-01", "fecha_fin": "2026-02-28"}`

---

### 27. consultar_cartera_cliente
**Input:** `{"cliente_nombre": "Manuel Ovalles"}`

---

### 28. consultar_saldo_socio
**Input:** `{"socio_cedula": "80075452"}`
**Output:**
```json
{
  "status": "exitoso",
  "saldo_pendiente": 2495333,
  "abonos_totales": 0
}
```

---

### 29. generar_reporte_auditor
**Input:** `{"periodo": "2026-Q1", "formato": "pdf"}`

---

## CATEGORÍA 7: NÓMINA E IMPUESTOS (3 Tools)

### 30. registrar_nomina_mensual
**Input:**
```json
{
  "mes": "2026-02",
  "nomina": [
    {"empleado": "Alexa Guzmán", "cedula": "1090XXX", "salario_base": 3220000},
    {"empleado": "Liz Martínez", "cedula": "1091XXX", "salario_base": 2200000}
  ]
}
```
**Output:**
```json
{
  "status": "exitoso",
  "mes": "2026-02",
  "cantidad_empleados": 2,
  "mensaje": "Nómina 2026-02 registrada para 2 empleados"
}
```
**Anti-dup:** SHA256(mes + cedula) validado

---

### 31. calcular_retenciones_payroll
**Input:**
```json
{
  "salario_base": 3220000,
  "tipo_empleado": "dependiente"
}
```
**Output:**
```json
{
  "status": "calculado",
  "salario_base": 3220000,
  "deducciones": {
    "aporte_sgsss": 128800,
    "aporte_fondo": 32200,
    "aporte_icbf": 96600,
    "upc": 16100
  },
  "total_deducciones": 273700,
  "salario_neto": 2946300
}
```

---

### 32. reportar_obligaciones_dian
**Input:**
```json
{
  "periodo_ini": "2026-01-01",
  "periodo_fin": "2026-04-30",
  "generar_anexo": true
}
```

---

## REGLAS DE ORO (INAMOVIBLES)

| Regla | Aplicación | Ejemplo |
|-------|-----------|---------|
| ROG-1: HTTP 200 verificación | Toda escritura en Alegra | `request_with_verify(POST → GET)` |
| Fallback cuenta | Gasto sin clasificar | Siempre ID 5493 (NUNCA 5495) |
| CXC socios | Retiros personales | Andrés (80075452) / Iván (80086601) |
| Auteco autoretenedor | Facturas Auteco NIT 860024781 | NUNCA ReteFuente, ReteFuente manual |
| IVA cuatrimestral | Períodos | ene-abr / may-ago / sep-dic |
| Antiduplicados | 3 capas | MongoDB + roddos_events + Alegra |
| BackgroundTasks | Lotes >10 | job_id en MongoDB, no síncrono |

---

**BUILD 24 — QUICK REFERENCE COMPLETE**
**Todos los 32 Tools documentados con ejemplos de uso**
