"""post_action_sync — syncs internal modules after every AI action in Alegra.

Flow: AI confirms action → execute_chat_action calls Alegra → calls this function
→ updates MongoDB collections (loanbook, cartera_pagos, inventario) → emits events
→ returns sync_messages list for the IA to report to the user.
"""
import uuid
from datetime import datetime, timezone, date

from event_bus import emit_event


# ─── Internal helper: recompute loanbook stats ────────────────────────────────

def _recompute_loan_stats(loan: dict, cuotas: list) -> dict:
    """Recompute loanbook aggregate fields from cuotas list."""
    pagadas = sum(1 for c in cuotas if c["estado"] == "pagada")
    vencidas = sum(1 for c in cuotas if c["estado"] == "vencida")
    total_cobrado = sum(c.get("valor_pagado", 0) for c in cuotas if c["estado"] == "pagada")
    total_deuda = sum(c["valor"] for c in cuotas if c["estado"] in ("pendiente", "vencida", "parcial"))
    num_cuotas = loan.get("num_cuotas", 0)
    total_cuotas_count = num_cuotas + 1  # +1 for cuota inicial

    if pagadas >= total_cuotas_count:
        estado = "completado"
    elif vencidas > 0:
        estado = "mora"
    elif not loan.get("fecha_entrega") and loan.get("plan") != "Contado":
        estado = "pendiente_entrega"
    else:
        estado = "activo"

    return {
        "cuotas": cuotas,
        "num_cuotas_pagadas": pagadas,
        "num_cuotas_vencidas": vencidas,
        "total_cobrado": total_cobrado,
        "saldo_pendiente": total_deuda,
        "estado": estado,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Main sync function ───────────────────────────────────────────────────────

async def post_action_sync(
    action_type: str,
    alegra_response: dict,
    payload: dict,
    db,
    user: dict,
) -> dict:
    """
    Called immediately after execute_chat_action succeeds.
    Performs:
      1. Emits internal event to roddos_events
      2. Updates MongoDB collections (loanbook cuotas, cartera_pagos, inventario)
      3. Returns sync_messages list for the IA to show to the user
    """
    alegra_id = str(alegra_response.get("id", "")) if isinstance(alegra_response, dict) else ""
    sync_messages: list[str] = []
    modules_updated: list[str] = ["audit_log"]
    now_iso = datetime.now(timezone.utc).isoformat()
    today_s = date.today().isoformat()

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
        total = float(alegra_response.get("total", 0)) if isinstance(alegra_response, dict) else 0.0

        await emit_event(db, "agente_ia", "factura.venta.creada", {
            "alegra_id": alegra_id,
            "factura_numero": numero,
            "cliente_nombre": client_name,
            "total": total,
            "user": user.get("email"),
        }, alegra_synced=True)

        modules_updated += ["dashboard", "inventario"]
        sync_messages.append(f"✅ Factura **{numero}** creada en Alegra (total: ${total:,.0f})")
        sync_messages.append("✅ Evento registrado — Dashboard y módulos notificados")

    # ── Pago registrado ───────────────────────────────────────────────────────
    elif action_type == "registrar_pago":
        invoice_ids: list[str] = []
        monto = 0.0
        if isinstance(payload.get("invoices"), list):
            for inv in payload["invoices"]:
                if isinstance(inv, dict):
                    invoice_ids.append(str(inv.get("id", "")))
                    monto += float(inv.get("amount", 0) or 0)

        metodo = payload.get("paymentMethod", "efectivo")

        await emit_event(db, "agente_ia", "pago.cuota.registrado", {
            "alegra_id": alegra_id,
            "monto": monto,
            "metodo": metodo,
            "invoice_ids": invoice_ids,
            "user": user.get("email"),
        }, alegra_synced=True)

        sync_messages.append(f"✅ Pago de **${monto:,.0f}** registrado en Alegra (ref: {alegra_id})")

        # ── Sync internal loanbook / cartera ──────────────────────────────────
        loans_synced: list[dict] = []
        for inv_id in invoice_ids:
            if not inv_id:
                continue
            loan = await db.loanbook.find_one({"factura_alegra_id": inv_id}, {"_id": 0})
            if not loan:
                continue

            cuotas = loan.get("cuotas", [])
            # Find the first unpaid cuota (pendiente or vencida)
            cuota_paid = None
            for c in cuotas:
                if c["estado"] in ("pendiente", "vencida"):
                    comprobante = f"COMP-{loan['codigo']}-IA-{str(c['numero']).zfill(3)}"
                    c["estado"] = "pagada"
                    c["fecha_pago"] = today_s
                    c["valor_pagado"] = monto if monto > 0 else c["valor"]
                    c["alegra_payment_id"] = alegra_id
                    c["comprobante"] = comprobante
                    c["notas"] = f"Registrado via Agente IA — {user.get('email', '')}"
                    cuota_paid = c
                    break

            if not cuota_paid:
                continue

            # Recompute and persist loanbook stats
            new_stats = _recompute_loan_stats(loan, cuotas)
            await db.loanbook.update_one({"id": loan["id"]}, {"$set": new_stats})

            # Persist to cartera_pagos
            await db.cartera_pagos.insert_one({
                "id": str(uuid.uuid4()),
                "loanbook_id": loan["id"],
                "codigo_loan": loan["codigo"],
                "cuota_numero": cuota_paid["numero"],
                "cliente_id": loan.get("cliente_id", ""),
                "cliente_nombre": loan["cliente_nombre"],
                "plan": loan["plan"],
                "fecha_pago": today_s,
                "valor_pagado": cuota_paid["valor_pagado"],
                "metodo_pago": metodo,
                "registrado_por": user.get("email", ""),
                "alegra_payment_id": alegra_id,
                "comprobante": cuota_paid["comprobante"],
                "notas": "Registrado via Agente IA",
                "created_at": now_iso,
                "fuente": "agente_ia",
            })

            loans_synced.append({
                "loan_codigo": loan["codigo"],
                "cliente": loan["cliente_nombre"],
                "cuota_num": cuota_paid["numero"],
                "total_cuotas": loan["num_cuotas"],
                "comprobante": cuota_paid["comprobante"],
                "nuevo_estado_loan": new_stats["estado"],
            })

        if loans_synced:
            for ls in loans_synced:
                sync_messages.append(
                    f"✅ **Loanbook actualizado** — {ls['cliente']} · "
                    f"Cuota {ls['cuota_num']}/{ls['total_cuotas']} marcada como pagada · "
                    f"Comprobante: {ls['comprobante']}"
                )
                if ls["nuevo_estado_loan"] == "completado":
                    sync_messages.append(f"🎉 ¡Crédito **{ls['loan_codigo']}** COMPLETADO!")
            modules_updated += ["cartera", "loanbook", "dashboard"]
        else:
            modules_updated += ["cartera", "dashboard"]
            if invoice_ids:
                sync_messages.append(
                    "⚠️ Pago registrado en Alegra. No se encontró crédito interno vinculado "
                    f"a la(s) factura(s): {', '.join(invoice_ids)}"
                )
            else:
                sync_messages.append("✅ Cartera y Loanbook notificados")

    # ── Causación / Asiento contable ──────────────────────────────────────────
    elif action_type == "crear_causacion":
        descripcion = payload.get("description", "Asiento contable")
        await emit_event(db, "agente_ia", "asiento.contable.creado", {
            "alegra_id": alegra_id,
            "descripcion": descripcion,
            "user": user.get("email"),
        }, alegra_synced=True)

        modules_updated.append("dashboard")
        sync_messages.append(f"✅ Asiento **{descripcion}** creado en Alegra (ID: {alegra_id})")
        sync_messages.append("✅ Dashboard notificado")

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
        sync_messages.append(
            f"✅ Factura de compra registrada en Alegra — "
            f"Proveedor: **{proveedor}** · Total: ${total:,.0f}"
        )

    # ── Contacto creado ───────────────────────────────────────────────────────
    elif action_type == "crear_contacto":
        nombre = payload.get("name", "")
        sync_messages.append(f"✅ Contacto **{nombre}** creado en Alegra (ID: {alegra_id})")

    # ── Siempre: audit log con fuente agente_ia ───────────────────────────────
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "endpoint": f"/agente_ia/{action_type}",
        "method": "AI_ACTION",
        "request_body": payload,
        "response_status": 200,
        "timestamp": now_iso,
        "alegra_id": alegra_id,
        "source": "agente_ia",
        "modules_updated": modules_updated,
    })
    sync_messages.append("✅ Log de auditoría actualizado")

    return {
        "alegra_id": alegra_id,
        "modules_updated": modules_updated,
        "sync_messages": sync_messages,
    }
