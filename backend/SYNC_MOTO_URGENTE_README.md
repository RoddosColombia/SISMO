# SINCRONIZACIÓN URGENTE — MOTO FACTURADA EN ALEGRA

**Fecha**: 2026-03-20
**Moto**: 9FL25AF31VDB95190
**Factura Alegra**: FE456
**Cliente**: KEDWYNG VALLADARES

---

## PROBLEMA

Moto fue facturada directamente en Alegra sin haber sido registrada en SISMO. Necesario sincronizar:
- Estado inventario: Disponible → Vendida
- Crear/Actualizar loanbook
- Registrar evento
- Invalidar caché

---

## SOLUCIONES DISPONIBLES

### OPCIÓN 1: Endpoint REST (Recomendado)

**Requisitos**:
- Servidor FastAPI corriendo en `http://localhost:8000`
- Usuario autenticado

**Ejecución**:

```bash
cd backend
python test_sync_moto.py
```

**Output esperado**:
```
================================================================================
✅ SINCRONIZACIÓN COMPLETADA EXITOSAMENTE
================================================================================

📊 ESTADO INVENTARIO_MOTOS:

  ANTES:
    id: moto_13
    estado: Disponible
    factura_alegra_id: None
    propietario: None

  DESPUÉS:
    id: moto_13
    estado: Vendida
    factura_alegra_id: FE456
    propietario: KEDWYNG VALLADARES
    fecha_venta: 2026-03-20T...

📦 LOANBOOK:
    ID: [uuid]
    Código: LB-2026-0001
    Estado: pendiente_entrega

================================================================================
```

---

### OPCIÓN 2: Script Python Directo

**Requisitos**:
- Motor instalado: `pip install motor`
- MongoDB accesible (local o remota)
- Variables de entorno configuradas

**Ejecución**:

```bash
cd backend
python sync_moto_manual.py
```

**Variables de entorno**:
```
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/roddos?retryWrites=true
DB_NAME=roddos
```

---

### OPCIÓN 3: Script Asincrónico Puro

```bash
cd backend
python sync_moto_urgente.py
```

---

## API ENDPOINT (Opción 1)

### Endpoint

```
POST /api/sync/moto/urgente
```

### Request

```json
{
  "chasis": "9FL25AF31VDB95190",
  "factura_id": "FE456",
  "cliente": "KEDWYNG VALLADARES"
}
```

### Response (HTTP 200)

```json
{
  "ok": true,
  "moto_id": "moto_13",
  "estado_antes": {
    "id": "moto_13",
    "estado": "Disponible",
    "factura_alegra_id": null,
    "propietario": null
  },
  "estado_despues": {
    "id": "moto_13",
    "estado": "Vendida",
    "factura_alegra_id": "FE456",
    "propietario": "KEDWYNG VALLADARES",
    "fecha_venta": "2026-03-20T14:30:00Z"
  },
  "loanbook_id": "uuid-1234",
  "loanbook_codigo": "LB-2026-0001",
  "timestamp": "2026-03-20T14:30:00Z"
}
```

### Con curl

```bash
curl -X POST http://localhost:8000/api/sync/moto/urgente \
  -H "Content-Type: application/json" \
  -d '{
    "chasis": "9FL25AF31VDB95190",
    "factura_id": "FE456",
    "cliente": "KEDWYNG VALLADARES"
  }'
```

---

## QUÉ HACE LA SINCRONIZACIÓN

### PASO 1: Buscar Moto

```
SELECT * FROM inventario_motos
WHERE chasis = '9FL25AF31VDB95190'
```

**Resultado**: Documento encontrado con estado "Disponible"

### PASO 2: Actualizar Estado

```
UPDATE inventario_motos
SET estado = 'Vendida',
    factura_alegra_id = 'FE456',
    fecha_venta = '2026-03-20T...',
    propietario = 'KEDWYNG VALLADARES'
WHERE chasis = '9FL25AF31VDB95190'
```

### PASO 3: Crear/Verificar Loanbook

```
SELECT * FROM loanbook
WHERE moto_chasis = '9FL25AF31VDB95190'
```

Si no existe:
```
INSERT INTO loanbook {
  id: uuid(),
  codigo: 'LB-2026-XXXX' (auto-incrementado),
  estado: 'pendiente_entrega',
  moto_chasis: '9FL25AF31VDB95190',
  factura_alegra_id: 'FE456',
  cliente_nombre: 'KEDWYNG VALLADARES'
}
```

### PASO 4: Registrar Evento

```
INSERT INTO roddos_events {
  event_type: 'factura.venta.creada',
  source: 'sync_manual',
  chasis: '9FL25AF31VDB95190',
  factura_id: 'FE456',
  cliente: 'KEDWYNG VALLADARES',
  loanbook_id: 'uuid',
  timestamp: '2026-03-20T...'
}
```

### PASO 5: Invalidar Caché

```
UPDATE cfo_cache
SET invalidated_at = '2026-03-20T...',
    is_valid = false
```

---

## VERIFICACIÓN MANUAL EN MONGODB

Después de ejecutar, verificar:

### Inventario Actualizado

```javascript
db.inventario_motos.findOne({
  chasis: "9FL25AF31VDB95190"
})
// Esperado: estado="Vendida", factura_alegra_id="FE456"
```

### Loanbook Creado

```javascript
db.loanbook.findOne({
  moto_chasis: "9FL25AF31VDB95190"
})
// Esperado: codigo="LB-2026-XXXX", estado="pendiente_entrega"
```

### Evento Registrado

```javascript
db.roddos_events.findOne({
  event_type: "factura.venta.creada",
  chasis: "9FL25AF31VDB95190"
})
// Esperado: documento con todos los datos de sincronización
```

---

## TROUBLESHOOTING

### Error: "Moto no encontrada"

**Solución**: Verificar que el chasis existe en inventario_motos
```javascript
db.inventario_motos.findOne({ chasis: "9FL25AF31VDB95190" })
```

### Error: "Connection refused"

**Solución**: Verificar que MongoDB está corriendo
```bash
# Mostrar status de MongoDB
mongosh --eval "db.adminCommand('ping')"
```

### Error: "Motor no instalado"

**Solución**:
```bash
pip install motor
```

### Error: "Cannot connect to MongoDB"

**Solución**: Configurar MONGODB_URL correctamente
```bash
export MONGODB_URL="mongodb+srv://user:pass@cluster.mongodb.net/roddos"
```

---

## ARCHIVOS RELACIONADOS

- `sync_moto_urgente.py` — Script Python puro (Opción 3)
- `sync_moto_manual.py` — Script con detección de conexión (Opción 2)
- `routers/sync_manual.py` — Endpoint REST (Opción 1)
- `test_sync_moto.py` — Cliente HTTP para pruebas
- `server.py` — Registro del endpoint

---

## LOGS

Los logs se guardan con prefijo `[SYNC]`:

```
[SYNC] Iniciando sincronización de moto: 9FL25AF31VDB95190
[SYNC] Loanbook ya existe: LB-2026-0001
[SYNC] Evento publicado: factura.venta.creada
[SYNC] CFO cache invalidado
[SYNC] Sincronización completada: 9FL25AF31VDB95190 → FE456
```

---

## PRÓXIMOS PASOS

Después de sincronizar:

1. ✓ Inventario actualizado
2. ✓ Loanbook creado/verificado
3. ✓ Evento registrado
4. ✓ Caché invalidado
5. ⏳ Revisar loanbook en panel de operaciones
6. ⏳ Notificar al cliente sobre entrega pendiente

---

**Última actualización**: 2026-03-20
**Status**: ✅ IMPLEMENTADO Y LISTO PARA USAR

