"""post_action_sync — syncs internal modules after every AI action in Alegra.

Flow: AI confirms action → execute_chat_action calls Alegra → calls this function
→ updates MongoDB (loanbook, cartera_pagos, inventario) → emit_state_change (último paso)
→ returns sync_messages list for the AI to report to the user.

Supports metadata dict (passed from execute_chat_action after stripping _metadata from payload).
"""
import uuid
from datetime import datetime, timezone, date, timedelta
from math import ceil

from services.shared_state import emit_state_change


# ─── Loanbook stat recompute ──────────────────────────────────────────────────

def _recompute_loan_stats(loan: dict, cuotas: list) -> dict:
    pagadas  = sum(1 for c in cuotas if c["estado"] == "pagada")
    vencidas = sum(1 for c in cuotas if c["estado"] == "vencida")
    cobrado  = sum(c.get("valor_pagado", 0) for c in cuotas if c["estado"] == "pagada")
    deuda    = sum(c["valor"] for c in cuotas if c["estado"] in ("pendiente", "vencida", "parcial"))
    total_q  = loan.get("num_cuotas", 0) + 1  # +1 cuota inicial

    if pagadas >= total_q:
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
        "total_cobrado": cobrado,
        "saldo_pendiente": deuda,
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
    metadata: dict = None,
) -> dict:
    """
    Called immediately after execute_chat_action.
    1. Emits event to roddos_events
    2. Updates MongoDB collections
    3. Returns sync_messages for the AI to show the user
    """
    meta        = metadata or {}
    alegra_id   = str(alegra_response.get("id", "")) if isinstance(alegra_response, dict) else ""
    sync_msgs:  list[str] = []
    modules:    list[str] = ["audit_log"]
    now_iso     = datetime.now(timezone.utc).isoformat()
    today_s     = date.today().isoformat()

    # ── CASO 1: Factura de Venta de Moto ─────────────────────────────────────
    if action_type == "crear_factura_venta":
        numero = ""
        is_draft = False
        if isinstance(alegra_response, dict):
            numero = (
                alegra_response.get("numberTemplate", {}).get("fullNumber", "")
                or str(alegra_id)
            )
            is_draft = alegra_response.get("status", "") == "draft"
        total = float(alegra_response.get("total", 0)) if isinstance(alegra_response, dict) else 0.0

        # Extract metadata fields
        moto_id         = meta.get("moto_id", "")
        moto_chasis     = meta.get("moto_chasis", "")
        moto_desc       = meta.get("moto_descripcion", "")
        cliente_id      = meta.get("cliente_id", "")
        cliente_nombre  = meta.get("cliente_nombre", "")
        cliente_nit     = meta.get("cliente_nit", "")
        cliente_tel     = meta.get("cliente_telefono", "")
        plan            = meta.get("plan", "")
        num_cuotas      = int(meta.get("num_cuotas", 0))
        cuota_valor     = float(meta.get("cuota_valor", 0))
        cuota_inicial   = float(meta.get("cuota_inicial", 0))
        precio_venta    = float(meta.get("precio_venta", 0))

        # 1a. Update moto status → Vendida
        moto_found = None
        if moto_id:
            moto_found = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
            if moto_found:
                await db.inventario_motos.update_one({"id": moto_id}, {"$set": {
                    "estado": "Vendida",
                    "factura_alegra_id": alegra_id,
                    "factura_numero": numero,
                    "fecha_venta": today_s,
                    "cliente_nombre": cliente_nombre,
                }})
                sync_msgs.append(f"✅ **Inventario**: {moto_found.get('marca','')} {moto_found.get('version','')} → Vendida (Factura {numero})")
                modules.append("inventario")
        elif moto_chasis:
            moto_found = await db.inventario_motos.find_one({"chasis": moto_chasis}, {"_id": 0})
            if moto_found:
                moto_id = moto_found.get("id", "")
                await db.inventario_motos.update_one({"chasis": moto_chasis}, {"$set": {
                    "estado": "Vendida",
                    "factura_alegra_id": alegra_id,
                    "factura_numero": numero,
                    "fecha_venta": today_s,
                    "cliente_nombre": cliente_nombre,
                }})
                moto_desc = moto_desc or f"{moto_found.get('marca','')} {moto_found.get('version','')} — Chasis: {moto_chasis}"
                sync_msgs.append(f"✅ **Inventario**: Chasis {moto_chasis} → Vendida (Factura {numero})")
                modules.append("inventario")

        sync_msgs.append(f"✅ **Factura** {numero} creada en Alegra (total: ${total:,.0f})")
        if is_draft:
            sync_msgs.append(
                "⚠️ La factura quedó en **BORRADOR** — La resolución DIAN de RODDOS está vencida "
                "(venció 2026-03-06). Para activarla ve a **Alegra → Configuración → Numeraciones** "
                "y renueva la resolución con la DIAN. La factura se activará automáticamente."
            )

        # 1b. Create Loanbook (only for financed plans)
        if plan and plan != "Contado" and num_cuotas > 0 and cuota_valor > 0:
            existing_count = await db.loanbook.count_documents({})
            codigo = f"LB-{date.today().year}-{str(existing_count + 1).zfill(4)}"
            loan_id = str(uuid.uuid4())
            valor_financiado = max(0.0, precio_venta - cuota_inicial)

            # Cuota inicial (cuota 0) — already collected at sale
            cuotas_lb = [{
                "numero": 0,
                "tipo": "inicial",
                "fecha_vencimiento": today_s,
                "valor": cuota_inicial,
                "estado": "pagada",
                "fecha_pago": today_s,
                "valor_pagado": cuota_inicial,
                "alegra_payment_id": None,
                "comprobante": f"INICIAL-{codigo}",
                "notas": "Cuota inicial recibida al momento de la venta",
            }]
            # Weekly cuotas (no dates yet — assigned at delivery)
            for i in range(1, num_cuotas + 1):
                cuotas_lb.append({
                    "numero": i,
                    "tipo": "semanal",
                    "fecha_vencimiento": "",     # assigned at delivery
                    "valor": cuota_valor,
                    "estado": "sin_fecha",        # pending delivery
                    "fecha_pago": None,
                    "valor_pagado": 0.0,
                    "alegra_payment_id": None,
                    "comprobante": None,
                    "notas": "",
                })

            loan_doc = {
                "id": loan_id,
                "codigo": codigo,
                "factura_alegra_id": alegra_id,
                "factura_numero": numero,
                "moto_id": moto_id,
                "moto_descripcion": moto_desc,
                "cliente_id": cliente_id,
                "cliente_nombre": cliente_nombre,
                "cliente_nit": cliente_nit,
                "cliente_telefono": cliente_tel,
                "plan": plan,
                "fecha_factura": today_s,
                "fecha_entrega": None,
                "fecha_primer_pago": None,
                "precio_venta": precio_venta,
                "cuota_inicial": cuota_inicial,
                "valor_financiado": valor_financiado,
                "num_cuotas": num_cuotas,
                "valor_cuota": cuota_valor,
                "cuotas": cuotas_lb,
                "estado": "pendiente_entrega",
                "num_cuotas_pagadas": 1,          # cuota inicial
                "num_cuotas_vencidas": 0,
                "total_cobrado": cuota_inicial,
                "saldo_pendiente": valor_financiado,
                "ai_suggested": True,
                "created_at": now_iso,
                "updated_at": now_iso,
                "created_by": user.get("email"),
            }
            await db.loanbook.insert_one(loan_doc)
            loan_doc.pop("_id", None)

            sync_msgs.append(
                f"✅ **Loanbook {codigo}** creado — Plan {plan}, {num_cuotas} cuotas de ${cuota_valor:,.0f} c/u · "
                f"Estado: PENDIENTE ENTREGA (fechas asignadas al registrar entrega)"
            )
            modules += ["loanbook", "dashboard"]

        elif plan == "Contado":
            sync_msgs.append("✅ Venta al contado — no se genera Loanbook")
        else:
            sync_msgs.append("ℹ️ Factura creada. Si es crédito, asegúrate de incluir _metadata con plan, cuotas y valor.")

        # emit_state_change — ÚLTIMO PASO CASO 1
        await emit_state_change(
            db,
            "factura.venta.creada",
            moto_chasis or alegra_id,
            "Vendida",
            user.get("email", ""),
            {"alegra_id": alegra_id, "factura_numero": numero,
             "cliente_nombre": cliente_nombre, "plan": plan, "total": total},
        )

    # ── CASO 2: Pago de Cuota ─────────────────────────────────────────────────
    elif action_type == "registrar_pago":
        invoice_ids: list[str] = []
        monto = 0.0
        if isinstance(payload.get("invoices"), list):
            for inv in payload["invoices"]:
                if isinstance(inv, dict):
                    invoice_ids.append(str(inv.get("id", "")))
                    monto += float(inv.get("amount", 0) or 0)

        metodo = payload.get("paymentMethod", "efectivo")
        sync_msgs.append(f"✅ **Pago** de ${monto:,.0f} registrado en Alegra (ref: {alegra_id})")

        # Sync internal loanbook / cartera
        for inv_id in invoice_ids:
            if not inv_id:
                continue
            loan = await db.loanbook.find_one({"factura_alegra_id": inv_id}, {"_id": 0})
            if not loan:
                continue
            cuotas = loan.get("cuotas", [])
            cuota_paid = None
            for c in cuotas:
                if c["estado"] in ("pendiente", "vencida"):
                    comprobante = f"COMP-{loan['codigo']}-IA-{str(c['numero']).zfill(3)}"
                    c.update({
                        "estado": "pagada",
                        "fecha_pago": today_s,
                        "valor_pagado": monto if monto > 0 else c["valor"],
                        "alegra_payment_id": alegra_id,
                        "comprobante": comprobante,
                        "notas": f"Registrado via Agente IA — {user.get('email','')}",
                    })
                    cuota_paid = c
                    break

            if not cuota_paid:
                continue

            new_stats = _recompute_loan_stats(loan, cuotas)
            await db.loanbook.update_one({"id": loan["id"]}, {"$set": new_stats})
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
            sync_msgs.append(
                f"✅ **Loanbook actualizado** — {loan['cliente_nombre']} · "
                f"Cuota {cuota_paid['numero']}/{loan['num_cuotas']} → Pagada · "
                f"Comprobante: {cuota_paid['comprobante']}"
            )
            if new_stats["estado"] == "completado":
                sync_msgs.append(f"🎉 ¡Crédito **{loan['codigo']}** COMPLETADO!")
            modules += ["cartera", "loanbook", "dashboard"]

        # emit_state_change — ÚLTIMO PASO CASO 2
        await emit_state_change(
            db,
            "pago.cuota.registrado",
            alegra_id,
            "pagada",
            user.get("email", ""),
            {"monto": monto, "metodo": metodo, "invoice_ids": invoice_ids},
        )

    # ── CASO 3 y 5: Causación contable ───────────────────────────────────────
    elif action_type == "crear_causacion":
        descripcion = payload.get("description", "Asiento contable")
        modules.append("dashboard")
        sync_msgs.append(f"✅ **Asiento contable** '{descripcion}' creado en Alegra (ID: {alegra_id})")
        sync_msgs.append("✅ Dashboard notificado")
        # emit_state_change — ÚLTIMO PASO CASO 3
        await emit_state_change(
            db,
            "asiento.contable.creado",
            alegra_id,
            "creado",
            user.get("email", ""),
            {"descripcion": descripcion},
        )

    # ── CASO 4: Factura de Compra → Inventario ────────────────────────────────
    elif action_type == "registrar_factura_compra":
        proveedor = ""
        if isinstance(payload.get("vendor"), dict):
            proveedor = payload["vendor"].get("name", "")
        total = float(payload.get("total", 0)) if payload.get("total") else 0.0
        plazo_dias = int(meta.get("plazo_dias", 0))

        sync_msgs.append(
            f"✅ **Factura de compra** registrada — Proveedor: {proveedor} · Total: ${total:,.0f}"
        )

        # Add moto units to inventory if metadata has them
        motos_a_agregar = meta.get("motos_a_agregar", [])
        for m in motos_a_agregar:
            marca       = m.get("marca", "")
            version     = m.get("version", "")
            cantidad    = int(m.get("cantidad", 1))
            costo_unit  = float(m.get("precio_unitario", 0))
            for _ in range(cantidad):
                await db.inventario_motos.insert_one({
                    "id": str(uuid.uuid4()),
                    "marca": marca,
                    "version": version,
                    "estado": "Disponible",
                    "costo": costo_unit,
                    "total": costo_unit,
                    "factura_compra_alegra_id": alegra_id,
                    "proveedor": proveedor,
                    "created_at": now_iso,
                    "chasis": "",
                    "motor": "",
                })
            sync_msgs.append(f"✅ **Inventario**: {cantidad} unidad(es) {marca} {version} agregadas (Disponible)")
            modules.append("inventario")

        if plazo_dias > 0:
            vencimiento = (date.today() + timedelta(days=plazo_dias)).isoformat()
            sync_msgs.append(f"✅ Plazo de pago: {plazo_dias} días — vence **{vencimiento}**")

        modules.append("dashboard")
        # emit_state_change — ÚLTIMO PASO CASO 4
        await emit_state_change(
            db,
            "factura.compra.creada",
            alegra_id,
            "creada",
            user.get("email", ""),
            {"proveedor": proveedor, "total": total},
        )

    # ── CASO 6 (entrega interna — no Alegra) ──────────────────────────────────
    elif action_type == "registrar_entrega":
        primera_cuota = alegra_response.get("primera_cuota_fecha", "") if isinstance(alegra_response, dict) else ""
        codigo = alegra_response.get("codigo", "") if isinstance(alegra_response, dict) else ""
        cliente = alegra_response.get("cliente_nombre", "") if isinstance(alegra_response, dict) else ""

        sync_msgs.append(f"✅ **Loanbook {codigo}** activado — Primera cuota: **{primera_cuota}** (miércoles)")
        sync_msgs.append("✅ Cliente ahora visible en la Cola de Gestión Remota")
        modules += ["loanbook", "cartera", "dashboard"]
        # emit_state_change — ÚLTIMO PASO CASO 6
        await emit_state_change(
            db,
            "loanbook.activado",
            payload.get("loanbook_id", ""),
            "activo",
            user.get("email", ""),
            {"codigo": codigo, "cliente_nombre": cliente, "primera_cuota": primera_cuota},
        )

    elif action_type == "crear_contacto":
        nombre = payload.get("name", "")
        sync_msgs.append(f"✅ Contacto **{nombre}** creado en Alegra (ID: {alegra_id})")

    # ── Audit log (siempre) ───────────────────────────────────────────────────
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
        "modules_updated": modules,
    })
    sync_msgs.append("✅ Log de auditoría actualizado")

    return {
        "alegra_id": alegra_id,
        "modules_updated": modules,
        "sync_messages": sync_msgs,
    }
