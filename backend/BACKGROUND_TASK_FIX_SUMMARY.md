# Background Task Fix: Bank Extract Journal Creation

## Problem Identified
The bank extract upload module was successfully:
- ✅ Parsing movements from bank statements
- ✅ Classifying movements (98 Bancolombia, 136 BBVA detected)
- ✅ Identifying causables (movements with confidence >= 0.7)

But FAILING to create journals in Alegra:
- ❌ causados = 0 always
- ❌ `crear_journal_alegra()` never returned success

## Root Cause
The function `crear_journal_alegra()` in `backend/services/bank_reconciliation.py` (line 406) was using:
```python
service = AlegraService(self.db)
response = await service.request("journals", "POST", payload)
```

**Problem**: `AlegraService` requires the FastAPI `request` context object to authenticate with Alegra. But BackgroundTasks have NO request context.

## Solution Implemented

### 1. Direct httpx.AsyncClient Usage
Replaced AlegraService dependency with direct HTTP calls:

```python
# BEFORE (broken in background tasks)
service = AlegraService(self.db)
response = await service.request("journals", "POST", payload)

# AFTER (works in background tasks)
import base64
import httpx
from datetime import timedelta

# Read credentials directly from environment
alegra_email = os.environ.get("ALEGRA_EMAIL", "")
alegra_token = os.environ.get("ALEGRA_TOKEN", "")

# Build auth header directly
creds = base64.b64encode(f"{alegra_email}:{alegra_token}".encode()).decode()
headers = {"Authorization": f"Basic {creds}", ...}

# Make direct HTTP call
async with httpx.AsyncClient(timeout=30) as client:
    response = await client.post(f"{base_url}/journals", headers=headers, json=payload)
```

### 2. Key Changes
- ✅ Added `import os` at file top (line 18)
- ✅ Read `ALEGRA_EMAIL` and `ALEGRA_TOKEN` from environment variables
- ✅ Create Basic Auth header directly (no request context needed)
- ✅ Use `httpx.AsyncClient` for all API calls (POST, GET)
- ✅ Comprehensive logging with `[BG]` prefix for diagnostics

### 3. Error Handling Preserved
- ✅ 503/429 temporary errors stored in `conciliacion_reintentos` for retry
- ✅ Invalid responses caught and logged
- ✅ MongoDB persistence of processed movements

### 4. Logging Added
Background task now logs:
```
[BG] Credenciales Alegra cargadas: email=...
[BG] POST https://api.alegra.com/api/v1/journals
[BG] Journal {id} creado en Alegra
[BG] ✅ Journal {id} verificado en Alegra
[MONGO] Movimiento guardado en BD: journal_id {id}
```

## Testing
Expected behavior after fix:

1. Upload bank extract from sismo-bice.vercel.app
2. Frontend shows:
   - `totalMovimientos` = detected count (e.g., 98)
   - `causados` = successfully created journals (should be > 0 now)
   - `pendientes` = lower confidence movements

3. Backend logs show:
   ```
   [BG] Movimientos causables a procesar: {count}
   [BG] Journal {id} creado en Alegra
   [BG] ✅ Journal {id} verificado en Alegra
   [MONGO] Movimiento guardado en BD: journal_id {id}
   ```

## Deployment
No additional dependencies needed - `httpx==0.27.0` already in requirements.txt

Requires environment variables (should already be set):
- `ALEGRA_EMAIL` = email for Alegra API auth
- `ALEGRA_TOKEN` = token for Alegra API auth

## Files Modified
- `backend/services/bank_reconciliation.py` - Rewrote `crear_journal_alegra()` method
- `backend/routers/conciliacion.py` - Added diagnostic logs (already present)

## Commit
```
Fix: Replace AlegraService with direct httpx calls in background task
c2c96ef (2026-03-21)
```
