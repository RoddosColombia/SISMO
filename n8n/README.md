# n8n Workflows — SISMO RODDOS

Workflows de orquestación n8n → SISMO.
URL n8n: https://roddos.app.n8n.cloud
URL SISMO backend: https://sismo-backend-40ca.onrender.com

---

## Configuración previa (una sola vez)

### 1. Crear variable n8n: SISMO_N8N_KEY

En n8n → Settings → Variables → New Variable:
- Name: `SISMO_N8N_KEY`
- Value: (valor de `N8N_API_KEY` configurado en Render para SISMO)

Esta variable es usada por los 3 workflows para autenticar requests a SISMO.

### 2. Importar cada workflow

En n8n → Workflows → Import from File → seleccionar el JSON correspondiente.
Luego activar el workflow (toggle ON).

---

## W1 — SISMO Health Monitor

**Archivo:** `W1_health_monitor.json`
**Trigger:** Cada 5 minutos, 24/7
**Qué hace:**
1. GET /api/n8n/health (sin auth)
2. Si status != "ok" O alegra_conectada == false O loanbooks_activos < 3:
   → POST /api/n8n/alerta tipo="sistema_degradado" severidad="alta"
   → La alerta aparece en el Dashboard de SISMO y en cfo_alertas

**Umbral loanbooks:** 3 (configurable en el nodo "¿SISMO degradado?")

---

## W2 — Resumen Semanal Lunes

**Archivo:** `W2_resumen_lunes.json`
**Trigger:** Lunes 8:10 AM Bogotá (CRON UTC: `10 11 * * 1`)
**Qué hace:**
1. En paralelo:
   - POST /api/n8n/scheduler/resumen_semanal_ceo → dispara job resumen CEO
   - POST /api/n8n/agente/cfo accion="resumen_semanal" → genera resumen CFO
2. GET /api/n8n/health para verificar que SISMO respondió
3. Si status != "ok": POST /api/n8n/alerta tipo="sistema_degradado"

**Nota CRON:** Colombia es UTC-5 sin cambio horario. `10 11 * * 1` = lunes 11:10 UTC = 8:10 AM Bogotá.

---

## W3 — Alerta Backlog Conciliación

**Archivo:** `W3_alerta_backlog.json`
**Trigger:** Diario 9:00 AM Bogotá (CRON UTC: `0 14 * * *`)
**Qué hace:**
1. GET /api/n8n/status/backlog (sin auth)
2. Si alertar == true (>50 pendientes O más antiguo >7 días):
   - Construye mensaje con detalle por banco (BBVA, Bancolombia, Nequi, etc.)
   - POST /api/n8n/alerta tipo="backlog_alto"
   - Severidad "alta" si total>100 o días_antiguo>14, "media" en los demás casos

**Backlog actual (5 abril 2026):** 298 movimientos (BBVA 33, Bancolombia 188, Nequi 76)

---

## Verificar que funcionan

Después de importar y activar:

1. **W1:** Ejecutar manualmente → debe retornar status "ok" o crear una alerta si SISMO está caído
2. **W2:** Ejecutar manualmente → debe ver ejecuciones en los 3 nodos HTTP sin error
3. **W3:** Ejecutar manualmente → si hay backlog activo, debe crear alerta en SISMO

Para ver alertas generadas: en SISMO → Dashboard → notificaciones, o consultar:
GET https://sismo-backend-40ca.onrender.com/api/cfo/alertas

---

## Troubleshooting

**Error 401 en nodos con auth:**
- Verificar que `SISMO_N8N_KEY` en n8n Variables coincide con `N8N_API_KEY` en Render

**Error timeout (ECONNREFUSED o similar):**
- Render free tier duerme si no hay tráfico en 15 min
- El W1 corriendo cada 5 min previene el sleep
- Si el error persiste, verificar en https://sismo-backend-40ca.onrender.com/api/health

**W2 ejecuta pero no llega WhatsApp al CEO/CGO:**
- Los mensajes de resumen van a cfo_alertas, no directo por WhatsApp
- El agente los entrega en la próxima sesión del usuario
- Para WhatsApp directo: el scheduler interno (lunes 8:05) lo maneja si mercately_config está configurado
