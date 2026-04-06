---
phase: quick
plan: 260406-iju
subsystem: chat
tags: [frontend, backend, approve-plan, plan-execution, agent]
tech-stack:
  added: []
  patterns: [approve-plan endpoint, plan_id detection, async cancel handler]
key-files:
  created: []
  modified:
    - backend/routers/chat.py
    - frontend/src/pages/AgentChatPage.tsx
decisions:
  - "confirm_pending_action importado directo desde tool_executor (no circular)"
  - "plan_id detection ANTES de document_proposal en el chain de else-if para prioridad correcta"
  - "handleCancelAction cambiado a async para notificar backend en cancelacion de planes"
metrics:
  duration: "3 min"
  completed_date: "2026-04-06"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 260406-iju: Hotfix — Conectar plan_id del backend con ExecutionCard

**One-liner:** Endpoint POST /approve-plan + wiring frontend plan_id -> ExecutionCard para flujo completo de aprobacion de planes del agente.

## What Was Built

Conecta el plan_id que retorna el backend cuando el agente crea un plan de ejecucion con el ExecutionCard existente en AgentChatPage.tsx, habilitando el flujo completo de aprobacion/cancelacion antes de ejecutar en Alegra.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Backend POST /api/chat/approve-plan | a60c945 | backend/routers/chat.py |
| 2 | Frontend plan_id detection + approve-plan wiring | b7b50da | frontend/src/pages/AgentChatPage.tsx |

## Changes Made

### backend/routers/chat.py

- Import `confirm_pending_action` desde `tool_executor`
- Nuevo modelo Pydantic `ApprovePlanRequest` (plan_id, session_id, confirmed)
- Nuevo endpoint `POST /api/chat/approve-plan` que delega a `confirm_pending_action`
- Error handling: ValueError -> 400, Exception -> 500

### frontend/src/pages/AgentChatPage.tsx

- `PendingAction` interface: campo opcional `plan_id?: string`
- Handler de `/chat/message`: destructura `plan_id, description, total_steps` de `resp.data`; si `plan_id` existe, llama `setPendingAction` con `plan_id` incluido antes del chain de `document_proposal`
- `handleExecute`: si `action.plan_id` existe -> POST `/chat/approve-plan` con `confirmed:true`; sino -> flujo legacy `/chat/execute-action`
- `handleCancelAction`: cambiado a `async`; si `pendingAction.plan_id` existe, notifica backend con `confirmed:false` antes de limpiar UI

## Deviations from Plan

None - plan ejecutado exactamente como estaba especificado.

## Verification

- [x] `grep "approve-plan" backend/routers/chat.py` — aparece en @router.post("/approve-plan")
- [x] `grep -c "approve-plan" frontend/src/pages/AgentChatPage.tsx` — 3 ocurrencias (handleExecute x2, handleCancelAction x1)
- [x] `grep -c "plan_id" frontend/src/pages/AgentChatPage.tsx` — 10 ocurrencias (interface, detection, handlers)
- [x] `grep -c "execute-action" frontend/src/pages/AgentChatPage.tsx` — 3 ocurrencias (flujo legacy intacto)

## Known Stubs

None.

## Self-Check: PASSED

- backend/routers/chat.py: FOUND (modified, 292 lines)
- frontend/src/pages/AgentChatPage.tsx: FOUND (modified, 1971 lines)
- Commit a60c945: FOUND
- Commit b7b50da: FOUND
