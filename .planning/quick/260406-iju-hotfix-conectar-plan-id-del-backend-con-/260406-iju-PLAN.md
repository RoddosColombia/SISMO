---
phase: quick
plan: 260406-iju
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/routers/chat.py
  - frontend/src/pages/AgentChatPage.tsx
autonomous: true
requirements: []
must_haves:
  truths:
    - "Cuando el backend retorna plan_id en la respuesta de /chat/message, el ExecutionCard se muestra con los datos del plan"
    - "Al confirmar el ExecutionCard de un plan, se llama POST /api/chat/approve-plan con {plan_id, session_id, confirmed: true}"
    - "Al cancelar el ExecutionCard de un plan, se llama POST /api/chat/approve-plan con {plan_id, session_id, confirmed: false}"
    - "El flujo existente de crear_causacion via execute-action sigue funcionando sin cambios"
  artifacts:
    - path: "backend/routers/chat.py"
      provides: "POST /api/chat/approve-plan endpoint"
      contains: "approve-plan"
    - path: "frontend/src/pages/AgentChatPage.tsx"
      provides: "Plan ID detection + approve-plan wiring"
      contains: "approve-plan"
  key_links:
    - from: "frontend/src/pages/AgentChatPage.tsx"
      to: "/api/chat/approve-plan"
      via: "api.post in handleExecute"
      pattern: "approve-plan"
---

<objective>
Conectar el plan_id que retorna el backend (cuando el agente crea un plan de ejecucion
como crear_factura_venta, registrar_nomina, etc.) con el ExecutionCard existente en
AgentChatPage.tsx. Actualmente la description del plan se muestra como texto plano
pero el ExecutionCard no aparece y no hay forma de confirmar/cancelar.

Purpose: Habilitar el flujo completo de aprobacion de planes del agente — el usuario
ve la tarjeta de confirmacion y puede aprobar o rechazar antes de ejecutar en Alegra.

Output: Backend endpoint approve-plan + frontend wiring plan_id -> ExecutionCard -> approve-plan
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@backend/routers/chat.py
@backend/tool_executor.py (confirm_pending_action ya existe — reutilizar)
@frontend/src/pages/AgentChatPage.tsx (lineas 44-49 PendingAction, 232-400 ExecutionCard, 1461-1468 handler POST /chat/message, 1533-1560 handleExecute/handleCancelAction)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Backend — POST /api/chat/approve-plan endpoint</name>
  <files>backend/routers/chat.py</files>
  <action>
Agregar endpoint POST /api/chat/approve-plan en routers/chat.py que:

1. Defina modelo Pydantic `ApprovePlanRequest`:
   - plan_id: str
   - session_id: str
   - confirmed: bool

2. El endpoint:
   - Recibe ApprovePlanRequest + current_user via Depends(get_current_user)
   - Si confirmed=True: llama confirm_pending_action(session_id, True, db, current_user)
     desde tool_executor.py (que ya existe y ejecuta via execute_chat_action internamente)
   - Si confirmed=False: llama confirm_pending_action(session_id, False, db, current_user)
     que retorna {"cancelled": True, "message": "..."}
   - Retorna el resultado directamente
   - Maneja ValueError como 400 y Exception generica como 500

3. Import: `from tool_executor import confirm_pending_action`

NO tocar: ninguno de los endpoints existentes (message, execute-action, history, tarea, pendientes).
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/.claude/worktrees/nostalgic-boyd && python -c "import ast; tree = ast.parse(open('backend/routers/chat.py').read()); funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]; assert 'chat_approve_plan' in funcs or 'approve_plan' in funcs, f'approve-plan endpoint not found, funcs: {funcs}'"</automated>
  </verify>
  <done>Endpoint POST /api/chat/approve-plan existe, acepta {plan_id, session_id, confirmed}, delega a confirm_pending_action</done>
</task>

<task type="auto">
  <name>Task 2: Frontend — Detectar plan_id y wiring a ExecutionCard + approve-plan</name>
  <files>frontend/src/pages/AgentChatPage.tsx</files>
  <action>
Modificar AgentChatPage.tsx en 3 puntos:

**A) En el handler de respuesta de POST /chat/message (~linea 1462):**
Despues de destructurar resp.data, ANTES del chain de else-if que verifica
document_proposal/gastos/cuotas/export_card/pending_action, agregar deteccion de plan_id:

```typescript
// Detectar plan_id del backend (flujo de planes del agente)
const { plan_id, description, total_steps } = resp.data;
if (plan_id) {
  // El backend creo un plan — mostrarlo como ExecutionCard para confirmacion
  setPendingAction({
    type: pending_action?.type || "execute_plan",
    title: description || "Plan de ejecucion",
    payload: { ...(pending_action?.payload || {}), plan_id, total_steps },
    summary: pending_action?.summary,
    plan_id,  // campo extra para distinguir flujo approve-plan vs execute-action
  } as any);
}
```

Esto va ANTES del `if (document_proposal)` existente. Si plan_id existe, NO caer
en el else-if de pending_action (ya fue seteado arriba).

**B) Agregar campo plan_id a PendingAction interface (~linea 44):**
```typescript
interface PendingAction {
  type: string;
  title: string;
  summary?: Array<{ label: string; value: string }>;
  payload?: Record<string, any>;
  plan_id?: string;  // Presente cuando viene del flujo de planes del agente
}
```

**C) En handleExecute (~linea 1533) y handleCancelAction (~linea 1557):**

Modificar handleExecute para detectar si la action tiene plan_id:
```typescript
const handleExecute = async (action) => {
  setExecuting(true);
  try {
    let resp;
    if (action.plan_id) {
      // Flujo approve-plan: confirmar plan del agente
      resp = await api.post("/chat/approve-plan", {
        plan_id: action.plan_id,
        session_id: sessionId,
        confirmed: true,
      });
    } else {
      // Flujo legacy execute-action (crear_causacion, etc.)
      resp = await api.post("/chat/execute-action", {
        action: action.type,
        payload: action.payload,
      });
    }
    // ... resto del handler identico (docId, syncMsgs, etc.)
```

Modificar handleCancelAction para notificar al backend si hay plan_id:
```typescript
const handleCancelAction = async () => {
  if (pendingAction?.plan_id) {
    try {
      await api.post("/chat/approve-plan", {
        plan_id: pendingAction.plan_id,
        session_id: sessionId,
        confirmed: false,
      });
    } catch { /* silent — UI cancellation always succeeds */ }
  }
  setPendingAction(null);
  setMessages((prev) => [...prev, {
    role: "assistant",
    content: "Accion cancelada. En que mas te puedo ayudar?",
    timestamp: new Date().toISOString(),
  }]);
};
```

IMPORTANTE:
- handleCancelAction cambia de sync a async (agregar async)
- NO tocar el flujo de crear_causacion que usa execute-action
- NO tocar DocumentProposal, TerceroCard, ni los demas cards
- NO tocar el flujo de handleConfirmProposal
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/.claude/worktrees/nostalgic-boyd/frontend && grep -c "approve-plan" src/pages/AgentChatPage.tsx | xargs -I{} test {} -ge 2 && echo "OK: approve-plan found in 2+ places" || echo "FAIL"</automated>
  </verify>
  <done>
- Si resp.data.plan_id existe en respuesta de /chat/message, ExecutionCard se muestra
- Confirmar llama POST /chat/approve-plan con confirmed:true
- Cancelar llama POST /chat/approve-plan con confirmed:false
- Flujo existente execute-action sin cambios para acciones sin plan_id
  </done>
</task>

</tasks>

<verification>
1. grep "approve-plan" backend/routers/chat.py — debe aparecer en endpoint
2. grep "approve-plan" frontend/src/pages/AgentChatPage.tsx — debe aparecer en handleExecute y handleCancelAction
3. grep "plan_id" frontend/src/pages/AgentChatPage.tsx — debe aparecer en PendingAction interface y en deteccion de respuesta
4. grep "execute-action" frontend/src/pages/AgentChatPage.tsx — debe seguir existente (flujo legacy no roto)
</verification>

<success_criteria>
- POST /api/chat/approve-plan endpoint existe y delega a confirm_pending_action
- Frontend detecta plan_id en respuesta y muestra ExecutionCard
- Confirmar plan llama approve-plan (no execute-action)
- Cancelar plan llama approve-plan con confirmed:false
- Flujo existente de execute-action para acciones sin plan_id sigue intacto
</success_criteria>

<output>
After completion, create `.planning/quick/260406-iju-hotfix-conectar-plan-id-del-backend-con-/260406-iju-SUMMARY.md`
</output>
