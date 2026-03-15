"""
shared_state.py — Capa central de estado compartido con caché TTL de 30 segundos.

Expone exactamente 6 funciones asíncronas:
  get_loanbook_snapshot(db, loanbook_id)     -> dict
  get_client_360(db, telefono)               -> dict | None
  get_moto_status(db, chasis)                -> dict
  get_portfolio_health(db)                   -> dict
  get_daily_collection_queue(db)             -> list[dict]
  emit_state_change(db, event_type, entity_id, new_state, actor, metadata={})
    -> actualiza DB + inserta roddos_events(estado='processed') + invalida caché
"""
import time
import uuid
import logging
from datetime import datetime, timezone, date, timedelta

logger = logging.getLogger(__name__)

# ─── Caché TTL en memoria (single-process, asyncio-safe) ─────────────────────
CACHE_TTL: float = 30.0  # segundos, fijo para TODAS las keys
_cache: dict[str, tuple] = {}  # key → (value, monotonic_timestamp)


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[1]) < CACHE_TTL:
        return entry[0]
    return None


def _cache_set(key: str, value) -> None:
    _cache[key] = (value, time.monotonic())


def _invalidate_keys(keys_or_prefixes: list[str]) -> None:
    """Invalida keys exactas (sin ':' al final) o prefijos (con ':' al final)."""
    for pattern in keys_or_prefixes:
        if pattern.endswith(":"):
            to_delete = [k for k in list(_cache.keys()) if k.startswith(pattern)]
        else:
            to_delete = [pattern] if pattern in _cache else []
        for k in to_delete:
            _cache.pop(k, None)


# ─── Reglas por event_type: qué colección actualizar y qué caché invalidar ───
# col=None → solo registrar evento, sin actualización de estado en MongoDB
_STATE_RULES: dict[str, dict] = {
    "cuota_pagada": {
        "col": "loanbook",
        "id_field": "id",
        "state_field": "estado",
        "invalidate": ["loanbook:", "portfolio_health", "daily_queue:"],
    },
    "loanbook.bucket_change": {
        "col": "loanbook",
        "id_field": "id",
        "state_field": "dpd_bucket",
        "invalidate": ["loanbook:", "portfolio_health", "daily_queue:"],
    },
    "protocolo_recuperacion": {
        "col": "loanbook",
        "id_field": "id",
        "state_field": "estado",
        "invalidate": ["loanbook:", "portfolio_health", "daily_queue:"],
    },
    "ptp.registrado": {
        "col": None,
        "invalidate": ["loanbook:", "daily_queue:"],
    },
    "factura.venta.creada": {
        "col": "inventario_motos",
        "id_field": "chasis",
        "state_field": "estado",
        "invalidate": ["moto:", "portfolio_health", "daily_queue:"],
    },
    "factura.venta.anulada": {
        "col": "inventario_motos",
        "id_field": "chasis",
        "state_field": "estado",
        "invalidate": ["moto:", "portfolio_health"],
    },
    "loanbook.activado": {
        "col": "loanbook",
        "id_field": "id",
        "state_field": "estado",
        "invalidate": ["loanbook:", "portfolio_health", "daily_queue:"],
    },
    "pago.cuota.registrado": {
        "col": "loanbook",
        "id_field": "id",
        "state_field": "estado",
        "invalidate": ["loanbook:", "portfolio_health", "daily_queue:"],
    },
    "cliente.mora.detectada": {
        "col": "loanbook",
        "id_field": "id",
        "state_field": "estado",
        "invalidate": ["loanbook:", "portfolio_health", "daily_queue:"],
    },
    "inventario.moto.baja": {
        "col": "inventario_motos",
        "id_field": "id",
        "state_field": "estado",
        "invalidate": ["moto:", "portfolio_health"],
    },
    "inventario.moto.entrada": {
        "col": None,
        "invalidate": ["portfolio_health"],
    },
    "asiento.contable.creado": {
        "col": None,
        "invalidate": ["portfolio_health"],
    },
    "factura.compra.creada": {
        "col": None,
        "invalidate": ["portfolio_health"],
    },
    "agente_ia.accion.ejecutada": {
        "col": None,
        "invalidate": [],
    },
    "repuesto.vendido": {
        "col": None,
        "invalidate": [],
    },
}

_EVENT_LABELS: dict[str, str] = {
    "factura.venta.creada":       "Factura de venta creada",
    "factura.venta.anulada":      "Factura de venta anulada",
    "pago.cuota.registrado":      "Pago de cuota registrado",
    "loanbook.activado":          "Loanbook activado — fechas de cuota asignadas",
    "loanbook.bucket_change":     "Loanbook — cambio de bucket DPD",
    "protocolo_recuperacion":     "Protocolo de recuperación activado (DPD ≥ 22)",
    "ptp.registrado":             "Compromiso de pago (PTP) registrado",
    "inventario.moto.entrada":    "Moto ingresada al inventario",
    "inventario.moto.baja":       "Moto dada de baja",
    "cliente.mora.detectada":     "Cliente en mora detectado",
    "asiento.contable.creado":    "Asiento contable creado",
    "agente_ia.accion.ejecutada": "Agente IA ejecutó acción",
    "factura.compra.creada":      "Factura de compra creada",
    "repuesto.vendido":           "Repuesto vendido",
}


# ─── 1. get_loanbook_snapshot ─────────────────────────────────────────────────

async def get_loanbook_snapshot(db, loanbook_id: str) -> dict:
    """Snapshot del loanbook con cuotas-stats calculadas. TTL 30s."""
    key = f"loanbook:{loanbook_id}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    loan = await db.loanbook.find_one(
        {"$or": [{"id": loanbook_id}, {"codigo": loanbook_id}]},
        {"_id": 0},
    )
    if not loan:
        result: dict = {}
    else:
        cuotas = loan.get("cuotas", [])
        pendientes = [
            c for c in cuotas
            if c.get("estado") in ("pendiente", "vencida") and c.get("fecha_vencimiento")
        ]
        proxima = (
            min(pendientes, key=lambda c: c.get("fecha_vencimiento", "9999"))
            if pendientes else None
        )
        result = {
            "id":                   loan.get("id"),
            "codigo":               loan.get("codigo"),
            "cliente_nombre":       loan.get("cliente_nombre"),
            "cliente_telefono":     loan.get("cliente_telefono"),
            "plan":                 loan.get("plan"),
            "estado":               loan.get("estado"),
            "saldo_pendiente":      loan.get("saldo_pendiente", 0),
            "total_cobrado":        loan.get("total_cobrado", 0),
            "num_cuotas":           loan.get("num_cuotas", 0),
            "num_cuotas_pagadas":   loan.get("num_cuotas_pagadas", 0),
            "num_cuotas_vencidas":  loan.get("num_cuotas_vencidas", 0),
            "fecha_entrega":        loan.get("fecha_entrega"),
            "proxima_cuota":        proxima,
            "cuotas_pendientes_count": len(pendientes),
            # BUILD 3 — DPD y Score
            "dpd_actual":              loan.get("dpd_actual", 0),
            "dpd_bucket":              loan.get("dpd_bucket", "0"),
            "dpd_maximo_historico":    loan.get("dpd_maximo_historico", 0),
            "score_pago":              loan.get("score_pago", "A+"),
            "estrella_nivel":          loan.get("estrella_nivel", 5),
            "interes_mora_acumulado":  loan.get("interes_mora_acumulado", 0.0),
        }

    _cache_set(key, result)
    return result


# ─── 2. get_client_360 ────────────────────────────────────────────────────────

async def get_client_360(db, telefono: str) -> dict | None:
    """Vista 360° del cliente: CRM + historial loanbooks + resumen mora. TTL 30s."""
    key = f"client360:{telefono}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    # 1. Buscar en CRM
    cliente = await db.crm_clientes.find_one(
        {"$or": [{"telefono_principal": telefono}, {"telefono": telefono}]},
        {"_id": 0},
    )

    # 2. Buscar loanbooks asociados
    if cliente:
        cid = cliente.get("id", "")
        loan_filter: dict = {
            "$or": [{"cliente_telefono": telefono}, {"cliente_id": cid}]
        }
    else:
        loan_filter = {"cliente_telefono": telefono}

    loans = await db.loanbook.find(loan_filter, {"_id": 0}).sort("created_at", -1).to_list(10)

    if not loans and not cliente:
        _cache_set(key, None)
        return None

    activos  = sum(1 for ln in loans if ln.get("estado") in ("activo", "mora", "pendiente_entrega"))
    en_mora  = sum(1 for ln in loans if ln.get("estado") == "mora")
    deuda    = sum(ln.get("saldo_pendiente", 0) for ln in loans if ln.get("estado") in ("activo", "mora"))

    result = {
        "cliente": cliente or {
            "nombre":   loans[0].get("cliente_nombre", "") if loans else "",
            "telefono": telefono,
            "nit":      loans[0].get("cliente_nit", "")    if loans else "",
        },
        "resumen": {
            "total_loans":       len(loans),
            "activos":           activos,
            "en_mora":           en_mora,
            "total_deuda_activa": deuda,
        },
        "loans": [
            {
                "codigo":          ln.get("codigo"),
                "estado":          ln.get("estado"),
                "plan":            ln.get("plan"),
                "moto":            ln.get("moto_descripcion", ""),
                "saldo_pendiente": ln.get("saldo_pendiente", 0),
                "fecha_entrega":   ln.get("fecha_entrega"),
            }
            for ln in loans
        ],
    }

    _cache_set(key, result)
    return result


# ─── 3. get_moto_status ───────────────────────────────────────────────────────

async def get_moto_status(db, chasis: str) -> dict:
    """Estado actual de la moto por número de chasis. TTL 30s."""
    key = f"moto:{chasis}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    moto = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0})
    if not moto:
        result: dict = {"chasis": chasis, "found": False}
    else:
        loan = None
        if moto.get("estado") in ("Vendida", "Entregada"):
            loan = await db.loanbook.find_one(
                {"$or": [{"moto_id": moto.get("id")}, {"moto_chasis": chasis}]},
                {"_id": 0, "codigo": 1, "cliente_nombre": 1, "estado": 1},
            )
        result = {
            "chasis":           chasis,
            "found":            True,
            "marca":            moto.get("marca"),
            "version":          moto.get("version"),
            "color":            moto.get("color"),
            "estado":           moto.get("estado"),
            "costo":            moto.get("costo"),
            "factura_alegra_id": moto.get("factura_alegra_id"),
            "fecha_venta":      moto.get("fecha_venta"),
            "cliente_nombre":   moto.get("cliente_nombre"),
            "loan_activo": {
                "codigo":         loan.get("codigo"),
                "cliente_nombre": loan.get("cliente_nombre"),
                "estado":         loan.get("estado"),
            } if loan else None,
        }

    _cache_set(key, result)
    return result


# ─── 4. get_portfolio_health ──────────────────────────────────────────────────

async def get_portfolio_health(db) -> dict:
    """Salud general de la cartera: conteos, saldos, tasa mora. TTL 30s."""
    key = "portfolio_health"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    pipeline = [
        {"$group": {
            "_id":           "$estado",
            "count":         {"$sum": 1},
            "saldo_total":   {"$sum": "$saldo_pendiente"},
            "cobrado_total": {"$sum": "$total_cobrado"},
        }}
    ]
    rows = await db.loanbook.aggregate(pipeline).to_list(20)

    by_state: dict = {}
    total_count = total_saldo = total_cobrado = 0

    for row in rows:
        s = row["_id"] or "desconocido"
        by_state[s] = {
            "count":         row["count"],
            "saldo_total":   row.get("saldo_total", 0) or 0,
            "cobrado_total": row.get("cobrado_total", 0) or 0,
        }
        total_count   += row["count"]
        total_saldo   += row.get("saldo_total", 0) or 0
        total_cobrado += row.get("cobrado_total", 0) or 0

    activos   = by_state.get("activo",            {}).get("count", 0)
    en_mora   = by_state.get("mora",              {}).get("count", 0)
    completados       = by_state.get("completado",       {}).get("count", 0)
    pendiente_entrega = by_state.get("pendiente_entrega",{}).get("count", 0)

    result = {
        "generado_en":             datetime.now(timezone.utc).isoformat(),
        "total_loans":             total_count,
        "activos":                 activos,
        "en_mora":                 en_mora,
        "completados":             completados,
        "pendiente_entrega":       pendiente_entrega,
        "tasa_mora":               round(en_mora / activos * 100, 1) if activos > 0 else 0.0,
        "saldo_cartera_total":     total_saldo,
        "total_cobrado_historico": total_cobrado,
        "por_estado":              by_state,
    }

    _cache_set(key, result)
    return result


# ─── 5. get_daily_collection_queue ────────────────────────────────────────────

async def get_daily_collection_queue(db) -> list[dict]:
    """Cola de cobro del día: cuotas vencidas o con vencimiento hoy. TTL 30s.
    Cada item incluye: bucket, dpd_actual, total_a_pagar, dias_para_protocolo, whatsapp_link.
    """
    today = date.today().isoformat()
    key   = f"daily_queue:{today}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora"]}},
        {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "cliente_telefono": 1,
         "plan": 1, "cuotas": 1, "saldo_pendiente": 1, "estado": 1,
         "gestiones": 1, "score_pago": 1, "estrella_nivel": 1},
    ).to_list(500)

    queue: list[dict] = []
    for loan in loans:
        for cuota in loan.get("cuotas", []):
            fv           = cuota.get("fecha_vencimiento", "")
            estado_cuota = cuota.get("estado", "")
            if not fv or estado_cuota not in ("pendiente", "vencida"):
                continue

            manana_s = (date.today() + timedelta(days=1)).isoformat()

            if fv <= today:
                dpd_actual = (date.today() - date.fromisoformat(fv)).days
                # Granular bucket mapping aligned with BUILD 6 RADAR
                bucket = (
                    "RECUPERACION" if dpd_actual >= 22 else
                    "CRITICO"      if dpd_actual >= 15 else
                    "URGENTE"      if dpd_actual >= 8  else
                    "ACTIVO"       if dpd_actual >= 1  else
                    "HOY"
                )
                dias_para_protocolo = max(0, 22 - dpd_actual)
            elif fv == manana_s:
                dpd_actual = -1
                bucket = "MAÑANA"
                dias_para_protocolo = 23
            else:
                continue  # future cuota — not actionable

            # Compute score from cuota history
            all_pagadas = [c for c in loan.get("cuotas", []) if c.get("estado") == "pagada"]
            a_tiempo = sum(
                1 for c in all_pagadas
                if c.get("fecha_pago", "9999") <= c.get("fecha_vencimiento", "9999")
            )
            score_pct = round(a_tiempo / len(all_pagadas) * 100) if all_pagadas else 100
            score_letra = (
                "A" if score_pct >= 90 else
                "B" if score_pct >= 70 else
                "C" if score_pct >= 50 else "F"
            )

            # WhatsApp link con código país Colombia (57)
            telefono = loan.get("cliente_telefono", "")
            wa_phone = telefono.replace(" ", "").replace("+", "").replace("-", "")
            if wa_phone and not wa_phone.startswith("57") and len(wa_phone) == 10:
                wa_phone = f"57{wa_phone}"
            valor_fmt = str(int(cuota.get("valor", 0)))
            whatsapp_link = (
                f"https://wa.me/{wa_phone}?text=RODDOS%3A+Cuota+vencida+%24{valor_fmt}"
                if wa_phone else ""
            )

            # Última gestión (BUILD 8 Ajuste 3 — último contacto en RadarCard)
            gestiones = loan.get("gestiones", [])
            ultima_g = gestiones[-1] if gestiones else None

            queue.append({
                "loanbook_id":               loan["id"],
                "codigo":                    loan["codigo"],
                "cliente_nombre":            loan["cliente_nombre"],
                "cliente_telefono":          telefono,
                "cuota_numero":              cuota["numero"],
                "fecha_vencimiento":         fv,
                "bucket":                    bucket,
                "dpd_actual":                dpd_actual,
                "total_a_pagar":             cuota.get("valor", 0),
                "mora":                      cuota.get("mora", 0),
                "dias_para_protocolo":       dias_para_protocolo,
                "whatsapp_link":             whatsapp_link,
                "saldo_total":               loan.get("saldo_pendiente", 0),
                "score_pct":                 score_pct,
                "score_letra":               score_letra,
                "estrella_nivel":            loan.get("estrella_nivel", 5),
                "score_pago":                loan.get("score_pago", score_letra),
                "ultima_gestion_fecha":      ultima_g.get("fecha", "")[:10] if ultima_g else None,
                "ultima_gestion_resultado":  ultima_g.get("resultado", "") if ultima_g else None,
            })
            break  # solo primera cuota vencida/urgente por loan

    queue.sort(key=lambda x: (-x["dpd_actual"], x["fecha_vencimiento"]))
    _cache_set(key, queue)
    return queue


# ─── 6. emit_state_change ─────────────────────────────────────────────────────

async def emit_state_change(
    db,
    event_type: str,
    entity_id: str,
    new_state: str,
    actor: str,
    metadata: dict | None = None,
) -> None:
    """
    Acción atómica que realiza 3 pasos:
      1. Actualiza el campo de estado en MongoDB según event_type.
      2. Inserta el evento en roddos_events con estado='processed'.
      3. Invalida las keys de caché afectadas.
    """
    meta    = metadata or {}
    rule    = _STATE_RULES.get(event_type, {"col": None, "invalidate": []})
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── Paso 1: actualizar MongoDB ────────────────────────────────────────────
    col_name = rule.get("col")
    if col_name and entity_id and new_state:
        id_field    = rule.get("id_field", "id")
        state_field = rule.get("state_field", "estado")
        collection  = getattr(db, col_name)
        try:
            await collection.update_one(
                {id_field: entity_id},
                {"$set": {state_field: new_state, "updated_at": now_iso}},
            )
        except Exception as e:
            logger.error(
                f"[shared_state] emit_state_change: fallo DB update "
                f"{event_type}/{entity_id}: {e}"
            )

    # ── Paso 2: insertar en roddos_events (ya procesado) ─────────────────────
    try:
        await db.roddos_events.insert_one({
            "event_id":   str(uuid.uuid4()),
            "timestamp":  now_iso,
            "source":     actor,
            "event_type": event_type,
            "label":      _EVENT_LABELS.get(event_type, event_type),
            "entity_id":  entity_id,
            "new_state":  new_state,
            "actor":      actor,
            "metadata":   meta,
            "estado":     "processed",
        })
    except Exception as e:
        logger.error(f"[shared_state] emit_state_change: fallo roddos_events insert: {e}")

    # ── Paso 3: invalidar caché ───────────────────────────────────────────────
    _invalidate_keys(rule.get("invalidate", []))
