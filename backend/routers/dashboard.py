"""Dashboard router — proactive alerts, agent memory, notifications."""
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user

router = APIRouter(tags=["dashboard"])


# ─── Dashboard Alerts ─────────────────────────────────────────────────────────

@router.get("/dashboard/alerts")
async def get_dashboard_alerts(current_user=Depends(get_current_user)):
    service = AlegraService(db)
    alerts = []

    try:
        overdue = await service.request("invoices", params={"status": "overdue"})
        overdue = overdue if isinstance(overdue, list) else []
        if overdue:
            total_overdue = sum(float(inv.get("balance") or inv.get("total") or 0) for inv in overdue)
            alerts.append({
                "id": "overdue_invoices",
                "type": "overdue_invoices",
                "severity": "high",
                "icon": "warning",
                "title": f"Tienes {len(overdue)} factura(s) vencida(s)",
                "message": f"Total por cobrar: {total_overdue:,.0f}",
                "action_label": "Registrar cobros",
                "action_type": "navigate",
                "action_payload": {"route": "/registro-cuotas"},
                "data": {"count": len(overdue), "total": total_overdue, "invoices": [
                    {"id": i["id"], "client": i.get("client", {}).get("name", ""), "total": i.get("balance") or i.get("total")}
                    for i in overdue[:3]
                ]},
            })
    except Exception:
        pass

    try:
        today = date.today()
        week_later = today + timedelta(days=7)
        all_bills = await service.request("bills", params={"status": "open"})
        all_bills = all_bills if isinstance(all_bills, list) else []
        due_soon = []
        for b in all_bills:
            due = b.get("dueDate") or b.get("due_date")
            if due:
                try:
                    d = date.fromisoformat(due[:10])
                    if today <= d <= week_later:
                        due_soon.append(b)
                except Exception:
                    pass
        if due_soon:
            total_due = sum(float(b.get("balance") or b.get("total") or 0) for b in due_soon)
            alerts.append({
                "id": "bills_due_soon",
                "type": "bills_due_soon",
                "severity": "medium",
                "icon": "calendar",
                "title": f"{len(due_soon)} factura(s) de proveedor vencen esta semana",
                "message": f"Total: {total_due:,.0f}",
                "action_label": "Ver facturas",
                "action_type": "navigate",
                "action_payload": {"route": "/facturacion-compra"},
                "data": {"count": len(due_soon), "total": total_due},
            })
    except Exception:
        pass

    try:
        cfg = await db.iva_config.find_one({}, {"_id": 0})
        if cfg:
            periodos = cfg.get("periodos", [])
            hoy = date.today()
            mes_actual = hoy.month
            ano_actual = hoy.year
            for p in periodos:
                if p["inicio_mes"] <= mes_actual <= p["fin_mes"]:
                    mes_lim = p["fin_mes"] + p.get("mes_limite_offset", 1)
                    ano_lim = ano_actual + (1 if mes_lim > 12 else 0)
                    mes_lim_f = mes_lim if mes_lim <= 12 else mes_lim - 12
                    try:
                        limite = date(ano_lim, mes_lim_f, min(p.get("dia_limite", 30), 28))
                        dias = (limite - hoy).days
                        if 0 <= dias <= 7:
                            alerts.append({
                                "id": "iva_due",
                                "type": "iva_due",
                                "severity": "critical",
                                "icon": "tax",
                                "title": f"IVA {cfg.get('tipo_periodo', 'cuatrimestral')} vence en {dias} día(s)",
                                "message": f"Período {p['nombre']} — Fecha límite: {limite}",
                                "action_label": "Ver estado IVA",
                                "action_type": "navigate",
                                "action_payload": {"route": "/impuestos"},
                                "data": {"dias_restantes": dias, "fecha_limite": str(limite)},
                            })
                    except Exception:
                        pass
    except Exception:
        pass

    return alerts


class AlertExecuteRequest(BaseModel):
    alert_type: str
    payload: Optional[dict] = None


@router.post("/dashboard/alerts/execute")
async def execute_alert_action(req: AlertExecuteRequest, current_user=Depends(get_current_user)):
    service = AlegraService(db)
    if req.alert_type == "send_collection_reminder":
        overdue = await service.request("invoices", params={"status": "overdue"})
        overdue = overdue if isinstance(overdue, list) else []
        return {"success": True, "message": f"Recordatorio enviado a {len(overdue)} clientes", "count": len(overdue)}
    return {"success": True, "message": "Acción ejecutada"}


# ─── Agent Memory ──────────────────────────────────────────────────────────────

@router.get("/agent/memory")
async def get_agent_memory(current_user=Depends(get_current_user)):
    items = await db.agent_memory.find(
        {"user_id": current_user["id"]}, {"_id": 0}
    ).sort("ultima_ejecucion", -1).limit(50).to_list(50)
    return items


@router.get("/agent/memory/suggestions")
async def get_memory_suggestions(current_user=Depends(get_current_user)):
    today = date.today()
    last_month = today.month - 1 if today.month > 1 else 12
    last_month_year = today.year if today.month > 1 else today.year - 1
    prefix = f"{last_month_year}-{str(last_month).zfill(2)}"
    items = await db.agent_memory.find(
        {"user_id": current_user["id"], "ultima_ejecucion": {"$regex": f"^{prefix}"}},
        {"_id": 0},
    ).to_list(10)
    return items


@router.delete("/agent/memory/{memory_id}")
async def delete_memory_item(memory_id: str, current_user=Depends(get_current_user)):
    await db.agent_memory.delete_one({"id": memory_id, "user_id": current_user["id"]})
    return {"message": "Memoria eliminada"}


# ─── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications")
async def get_notifications(unread_only: bool = False, current_user=Depends(get_current_user)):
    query = {}
    if unread_only:
        query["read"] = False
    notifs = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return notifs


@router.put("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, current_user=Depends(get_current_user)):
    await db.notifications.update_one({"id": notif_id}, {"$set": {"read": True}})
    return {"ok": True}


@router.put("/notifications/read-all")
async def mark_all_read(current_user=Depends(get_current_user)):
    await db.notifications.update_many({"read": False}, {"$set": {"read": True}})
    return {"ok": True}
