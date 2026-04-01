# Phase 9: Tool Use Agente Contador — Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Task Boundary

Migrar `process_chat()` y `execute_chat_action()` en `backend/ai_chat.py` de su arquitectura actual
(ACTION_MAP de string dispatch + XML `<action>` parsing) al loop nativo `tool_use` de Anthropic API.

**Archivo afectado principal:** `backend/ai_chat.py` (~5,200 líneas en producción)

**Funciones clave:**
- `process_chat()` — línea 2820: genera `pending_action` con XML parsing
- `execute_chat_action()` — línea 3861: dispatcher con ACTION_MAP de 12 entradas

**Lo que NO cambia:** Routing de intents (agent_router), CFO flow, process_document_chat,
process_tabular_chat, la UI del frontend, el mecanismo de confirmación del usuario.

</domain>

<decisions>
## Implementation Decisions

### 1. Flujo confirm → execute
- **Lecturas auto-ejecutan:** tools con `requires_confirmation: false` en su schema
  (ej: consultar_facturas, consultar_cartera) se ejecutan directamente sin pausa al usuario.
- **Escrituras piden confirmación:** tools con `requires_confirmation: true`
  (ej: crear_causacion, registrar_pago) generan `pending_action` que el backend retorna al frontend
  sin ejecutar — idéntica UX al flujo actual.
- **Mecanismo:** El campo `requires_confirmation` vive en la definición del tool (metadata adicional,
  no parte del input_schema JSON enviado a Anthropic). El backend lo lee al detectar
  `stop_reason == "tool_use"` para decidir si ejecuta o retorna pending_action.

### 2. Estrategia de migración
- **Feature flag inline** en `process_chat()`: variable de entorno `TOOL_USE_ENABLED`.
  - `TOOL_USE_ENABLED=true` → nuevo loop tool_use
  - `TOOL_USE_ENABLED=false` (o ausente) → flujo XML actual sin cambios
- **Rollback:** cambiar env var en Render → deploy automático — sin nuevo código.
- **No duplicar:** un solo `process_chat()` con branching interno. No crear `process_chat_v2()`.

### 3. Alcance de tools — MVP 6
Migrar exactamente estas 6 tools en Phase 9:

| Tool name | Acción actual | requires_confirmation |
|-----------|---------------|----------------------|
| `crear_causacion` | journals POST | true |
| `registrar_pago_cartera` | cartera/registrar-pago POST | true |
| `registrar_nomina` | nomina/registrar POST | true |
| `consultar_facturas` | invoices GET | false |
| `consultar_cartera` | loanbook MongoDB (no Alegra) | false |
| `crear_factura_venta` | invoices POST | true |

Las 6 restantes del ACTION_MAP original (`registrar_factura_compra`, `registrar_pago`,
`registrar_abono_socio`, `consultar_saldo_socio`, `registrar_ingreso_no_operacional`,
`crear_contacto`, `crear_nota_credito`, `crear_nota_debito`) quedan para Phase 10.

### 4. Fallback para tools no migradas
Cuando `TOOL_USE_ENABLED=true` y el modelo no puede resolver la solicitud con las 6 tools
disponibles, el backend detecta que no hay `stop_reason == "tool_use"` y ejecuta el XML flow
antiguo para esa solicitud. **Híbrido temporal pero sin pérdida de funcionalidad.**

### Claude's Discretion
- Estructura interna del tool_use loop (máx iteraciones, manejo de errores de tool_result)
- Cómo construir el `tool_result` content block de respuesta tras ejecución
- TDD: qué tests escribir primero (RED) antes de implementar (GREEN)
- Organización de las tool definitions (¿un dict global TOOLS = [...] arriba en ai_chat.py?)

</decisions>

<specifics>
## Specific References

- `backend/ai_chat.py` línea 2820: `process_chat()` — punto de entrada principal
- `backend/ai_chat.py` línea 3814: llamada a `_chat_client.messages.create()` — aquí entra `tools=`
- `backend/ai_chat.py` línea 3831: bloque XML parse `<action>` — reemplazar con tool_use detection
- `backend/ai_chat.py` línea 3861: `execute_chat_action()` — el dispatcher ACTION_MAP
- `backend/ai_chat.py` línea 3903: `ACTION_MAP = {...}` — los 12 entries actuales
- `backend/ai_chat.py` línea 3800: prompt caching con `cache_control: ephemeral` — PRESERVAR
- `backend/alegra_service.py` línea 274: `request_with_verify()` — sigue siendo el executor final
- `backend/routers/cartera.py`: patrón anti-dup que tool `registrar_pago_cartera` ya tiene

**Anthropic Tool Use API pattern a implementar:**
```python
response = await client.messages.create(
    model="claude-opus-4-6",
    tools=[...],  # 6 tool definitions con input_schema JSON Schema
    messages=messages,
    system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}]
)

if response.stop_reason == "tool_use":
    tool_block = next(b for b in response.content if b.type == "tool_use")
    tool_name = tool_block.name
    tool_input = tool_block.input
    tool_def = TOOL_DEFS[tool_name]
    if tool_def["requires_confirmation"]:
        return {"message": ..., "pending_action": {"type": tool_name, "payload": tool_input}}
    else:
        result = await execute_tool(tool_name, tool_input, db, user)
        # Loop: send tool_result back to model
```
</specifics>

<canonical_refs>
## Canonical References

- `backend/ai_chat.py` — archivo principal afectado (leer antes de planear)
- `backend/alegra_service.py` línea 274-314 — request_with_verify() que los tools invocan
- `backend/routers/cartera.py` — patrón de tool `registrar_pago_cartera`
- `backend/routers/nomina.py` — patrón de tool `registrar_nomina`
- Anthropic Tool Use docs: https://docs.anthropic.com/en/docs/tool-use (referencia externa)

</canonical_refs>
