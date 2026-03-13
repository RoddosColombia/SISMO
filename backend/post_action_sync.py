"""post_action_sync — synchronises all internal modules after every AI action in Alegra."""
import uuid
from datetime import datetime, timezone
from event_bus import emit_event


async def post_action_sync(
    action_type: str,
    alegra_response: dict,
    payload: dict,
    db,
    user: dict,
) -> dict:
    """
    Called immediately after execute_chat_action succeeds.
    Returns sync_messages list for the IA to show to the user.
    """
    alegra_id = str(alegra_response.get("id", "")) if isinstance(alegra_response, dict) else ""
    sync_messages: list[str] = []
    modules_updated: list[str] = ["audit_log"]

    # ── Factura de venta ──────────────────────────────────────────────────────
    if action_type == "crear_factura_venta":
        numero = ""
        if isinstance(alegra_response, dict):
            numero = (
                alegra_response.get("numberTemplate", {}).get("fullNumber", "")
                or str(alegra_id)
            )
        client_name = ""
        if isinstance(payload.get("client"), dict):
            client_name = payload["client"].get("name", "")

        await emit_event(db, "agente_ia", "factura.venta.creada", {
            "alegra_id": alegra_id,
            "factura_numero": numero,
            "cliente_nombre": client_name,
            "total": float(alegra_response.get("total", 0)) if isinstance(alegra_response, dict) else 0,
            "user": user.get("email"),
        }, alegra_synced=True)

        modules_updated += ["dashboard", "inventario"]
        sync_messages.append(f"✅ Factura **{numero}** creada en Alegra")
        sync_messages.append("✅ Evento registrado — Dashboard y módulos notificados")

    # ── Pago de cuota ─────────────────────────────────────────────────────────
    elif action_type == "registrar_pago":
        monto = 0.0
        if isinstance(payload.get("invoices"), list) and payload["invoices"]:
            monto = float(payload["invoices"][0].get("amount", 0))

        await emit_event(db, "agente_ia", "pago.cuota.registrado", {
            "alegra_id": alegra_id,
            "monto": monto,
            "metodo": payload.get("paymentMethod", ""),
            "user": user.get("email"),
        }, alegra_synced=True)

        modules_updated += ["cartera", "loanbook", "dashboard"]
        sync_messages.append(f"✅ Pago de **${monto:,.0f}** registrado en Alegra")
        sync_messages.append("✅ Cartera y Loanbook actualizados automáticamente")

    # ── Causación / Asiento contable ─────────────────────────────────────────
    elif action_type == "crear_causacion":
        descripcion = payload.get("description", "Asiento contable")
        await emit_event(db, "agente_ia", "asiento.contable.creado", {
            "alegra_id": alegra_id,
            "descripcion": descripcion,
            "user": user.get("email"),
        }, alegra_synced=True)

        modules_updated.append("dashboard")
        sync_messages.append(f"✅ Asiento **{descripcion}** creado en Alegra")

    # ── Factura de compra ─────────────────────────────────────────────────────
    elif action_type == "registrar_factura_compra":
        proveedor = ""
        if isinstance(payload.get("vendor"), dict):
            proveedor = payload["vendor"].get("name", "")
        total = float(payload.get("total", 0)) if payload.get("total") else 0.0

        await emit_event(db, "agente_ia", "factura.compra.creada", {
            "alegra_id": alegra_id,
            "proveedor": proveedor,
            "total": total,
            "user": user.get("email"),
        }, alegra_synced=True)

        modules_updated.append("dashboard")
        sync_messages.append(f"✅ Factura de compra registrada en Alegra — Proveedor: {proveedor}")

    # ── Contacto creado ───────────────────────────────────────────────────────
    elif action_type == "crear_contacto":
        nombre = payload.get("name", "")
        sync_messages.append(f"✅ Contacto **{nombre}** creado en Alegra")

    # ── Siempre: audit log ────────────────────────────────────────────────────
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "endpoint": f"/agente_ia/{action_type}",
        "method": "AI_ACTION",
        "request_body": payload,
        "response_status": 200,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alegra_id": alegra_id,
        "source": "agente_ia",
    })
    sync_messages.append("✅ Log de auditoría actualizado")

    return {
        "alegra_id": alegra_id,
        "modules_updated": modules_updated,
        "sync_messages": sync_messages,
    }
