# SISMO BUILD 24 — ACTIVATION SCRIPT
## Migración Tool Use API: De BUILD 23 Legacy a BUILD 24 Tool Use Completo

---

## PASO 1: Copiar archivos nuevos al repo local

```bash
# En Windows PowerShell en C:\Users\AndresSanJuan\roddos-workspace\SISMO

copy C:\Users\AndresSanJuan\Downloads\tool_definitions_complete.py backend\tools\
copy C:\Users\AndresSanJuan\Downloads\tool_executor_complete.py backend\tools\
copy C:\Users\AndresSanJuan\Downloads\ai_chat_tool_use.py backend\routers\
```

---

## PASO 2: Actualizar main.py para usar Tool Use API

En `backend/main.py`:

```python
# ANTES (BUILD 23):
from backend.routers.ai_chat import process_chat_legacy

# DESPUÉS (BUILD 24):
from backend.routers.ai_chat_tool_use import chat_endpoint as process_chat

# En la ruta POST /api/chat:
@app.post("/api/chat")
async def chat_handler(request: dict):
    return await process_chat(
        db=db,
        alegra_client=alegra_client,
        request=request
    )
```

---

## PASO 3: Activar feature flag en Render

**Opción A: Vía Dashboard Render (GUI)**
1. Abre https://dashboard.render.com
2. Ve a tu servicio `sismo-backend-40ca` → Settings → Environment
3. Busca `TOOL_USE_ENABLED` (si existe) o crea nueva variable:
   - Key: `TOOL_USE_ENABLED`
   - Value: `true`
4. Haz click "Save"
5. Render automáticamente redeploya el servicio

**Opción B: Vía Render API (CLI)**
```bash
# Requiere RENDER_API_KEY configurada en tu terminal
curl -X PUT "https://api.render.com/v1/services/{service-id}/env-vars" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"TOOL_USE_ENABLED": "true"}'
```

**Opción C: Vía archivo .env en Render (sin deploy)**
1. En Render dashboard → Environment Variables
2. Agregar: `TOOL_USE_ENABLED=true`
3. Esperar re-deploy automático (5-10 minutos)

---

## PASO 4: Validar que feature flag está activo

```bash
# En la terminal, después que Render redeploya:
curl https://sismo-backend-40ca.onrender.com/health

# Respuesta esperada:
{
  "status": "healthy",
  "tool_use_enabled": true,
  "build": "BUILD 24",
  "tools_available": 32
}
```

Si devuelve `"tool_use_enabled": false`, TOOL_USE_ENABLED no se seteó correctamente.

---

## PASO 5: Commit en Git

```bash
cd C:\Users\AndresSanJuan\roddos-workspace\SISMO

git config user.name "RODDOS SAS"
git config user.email "info@roddos.com"

git add backend/tools/tool_definitions_complete.py
git add backend/tools/tool_executor_complete.py
git add backend/routers/ai_chat_tool_use.py
git add backend/main.py  # si hiciste cambios

git commit -m "BUILD 24: Implementación Tool Use API con 32 Tools Agente Contador

- Agregados: tool_definitions_complete.py (32 tools en 7 categorías)
- Agregados: tool_executor_complete.py (handlers con request_with_verify)
- Agregados: ai_chat_tool_use.py (router con Anthropic Tool Use API)
- Migracion: ACTION_MAP legacy → Tool Use API (Backward compatible con TOOL_USE_ENABLED flag)
- System prompts diferenciados por agente (Contador/CFO/RADAR/Loanbook)
- ROG-1: request_with_verify() obligatorio en toda escritura Alegra
- Tests: 32 tools mapeados, feature flag activado

BUILD 24 BUILD: ✅ Operativo"

git push origin main
```

Espera confirmación de GitHub Actions (tests + syntax check).

---

## PASO 6: Monitorear deploy en Render

1. Abre https://dashboard.render.com → sismo-backend-40ca
2. Ve a "Logs"
3. Deberías ver:
   ```
   Building...
   Deploying...
   ✓ Deploy successful
   ```
4. El redeploy toma 2-5 minutos

---

## PASO 7: Test manual en Producción

Una vez que Render redeploya con TOOL_USE_ENABLED=true:

```bash
# Test crear_causacion (Gasto simple)
curl -X POST https://sismo-backend-40ca.onrender.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Pagamos honorarios al abogado $800.000",
    "user_id": "user_andrés",
    "session_id": "sess_001",
    "agent_type": "contador"
  }'

# Respuesta esperada:
{
  "status": "exitoso",
  "agent": "contador",
  "mensaje": "Propuesta lista. Confirma con /aprobar-causacion para ejecutar.",
  "tool_calls_ejecutadas": 1,
  "tokens_used": 847
}
```

---

## PASO 8: Validar en Base de Datos

```bash
# Conectar a MongoDB Atlas sismo-prod
mongosh "mongodb+srv://sismo_admin:Alejosan2026!@sismo-prod.rzebxlv.mongodb.net"

# En la shell:
use sismo-prod

# Verificar que las sesiones se guardaron
db.agent_sessions.findOne({"user_id": "user_andrés"})

# Verificar tool executions en agent_errors
db.agent_errors.find({}).limit(5)
```

---

## PASO 9: Revertir si hay problemas

Si BUILD 24 causa issues:

```bash
# En Render dashboard → Environment Variables
TOOL_USE_ENABLED = false
# o elimina la variable

# Render redeploya automáticamente en 2-5 min
# Vuelve a ACTION_MAP legacy (BUILD 23)
```

---

## CHECKLIST FINAL

- [ ] Archivos copiados a `backend/tools/` y `backend/routers/`
- [ ] `main.py` actualizado con nueva ruta `/api/chat`
- [ ] `TOOL_USE_ENABLED=true` seteada en Render Environment Variables
- [ ] GitHub Actions pasó (syntax check + lint)
- [ ] Render redeploy completado (status ✓ Deployed)
- [ ] `/health` endpoint devuelve `"tool_use_enabled": true`
- [ ] Test manual ejecutado exitosamente
- [ ] Sesión guardada en MongoDB `agent_sessions`
- [ ] Feature flag operativo en producción

---

## BUILD 24 STATUS

**Implementación:** ✅ Completa
- 32 Tools definidos + esquematizados
- Handlers con request_with_verify() (ROG-1)
- Tool Use API router implementado
- System prompts diferenciados por agente
- Backward compatible con legacy ACTION_MAP

**Activación:** ⏳ Pendiente
- TOOL_USE_ENABLED=true en Render
- Deploy + validación en producción

**Next Steps (BUILD 25):**
- Integración FASE 8-B (Mercately bidireccional)
- FASE 8-C (RADAR con 7 Tools especializados)
- FASE 8-D (n8n workflows W4-W8)
- Observabilidad (Langfuse)

---

## SOPORTE CRÍTICO

Si surge error `IndexError` o `AttributeError` en tool execution:
1. Verifica que `tool_definitions_complete.py` está en `backend/tools/`
2. Verifica importaciones en `ai_chat_tool_use.py`
3. Revisa logs de Render para stack trace completo
4. Si no resuelve, revertir a `TOOL_USE_ENABLED=false` e investigar en rama de desarrollo

**Contact:** Andrés Sanjuan (andres@roddos.com)
**Date:** 7 de abril de 2026
**Build:** BUILD 24 — Tool Use API Complete
