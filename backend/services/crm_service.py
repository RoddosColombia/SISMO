"""crm_service.py — CRM operations: upsert_cliente, gestiones, PTP, notas.

All mutations are append-only on historical arrays (gestiones, notas, score_historial).
Never overwrite historical records.
"""
import re
import uuid
import asyncio
from datetime import datetime, timezone, date

from services.event_bus_service import EventBusService
from event_models import RoddosEvent
from services.shared_state import handle_state_side_effects


def normalizar_telefono(telefono: str) -> str:
    """Normaliza teléfonos colombianos al formato canónico +57XXXXXXXXXX.

    Casos manejados:
      3XXXXXXXXX      (10 dígitos móvil) → +573XXXXXXXXX
      573XXXXXXXXX    (12 dígitos sin +)  → +573XXXXXXXXX
      +573XXXXXXXXX   (ya normalizado)    → +573XXXXXXXXX
      Otros / vacío                       → devuelve tal como está
    """
    t = re.sub(r"[\s\-().]+", "", (telefono or ""))
    if not t:
        return t
    # Already correct
    if re.fullmatch(r"\+57[3]\d{9}", t):
        return t
    # 573XXXXXXXXX → +57...
    if re.fullmatch(r"57[3]\d{9}", t):
        return "+" + t
    # 3XXXXXXXXX → +57...
    if re.fullmatch(r"[3]\d{9}", t):
        return "+57" + t
    # +3XXXXXXXXX (bad prefix) → +57...
    if re.fullmatch(r"\+[3]\d{9}", t):
        return "+57" + t[1:]
    return t

RESULTADO_VALIDOS = {
    "contestó_pagará_hoy",
    "contestó_prometió_fecha",
    "contestó_no_pagará",
    "no_contestó",
    "número_equivocado",
    "respondió_pagará",
    "respondió_prometió_fecha",
    "visto_sin_respuesta",
    "no_entregado",
    "acuerdo_de_pago_firmado",
    # FASE 8-A: 6 nuevos resultados de gestión
    "sin_respuesta_72h",
    "bloqueo_detectado",
    "numero_apagado",
    "pago_parcial_reportado",
    "acuerdo_firmado",
    "disputa_deuda",
}


async def upsert_cliente(db, telefono: str, datos: dict) -> dict:
    """Update or create a crm_clientes document identified by telefono_principal."""
    telefono = normalizar_telefono(telefono)
    # Also normalize alternate phone if provided
    if datos.get("telefono_alternativo"):
        datos["telefono_alternativo"] = normalizar_telefono(datos["telefono_alternativo"])
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.crm_clientes.find_one(
        {"telefono_principal": telefono}, {"_id": 0}
    )
    if existing:
        safe_update = {
            k: v for k, v in datos.items()
            if k not in ("gestiones", "notas", "score_historial", "alertas", "id")
        }
        safe_update["updated_at"] = now
        await db.crm_clientes.update_one(
            {"telefono_principal": telefono},
            {"$set": safe_update},
        )
        return {**existing, **safe_update}

    new_doc = {
        "id": str(uuid.uuid4()),
        "telefono_principal": telefono,
        "nombre_completo": datos.get("nombre_completo", ""),
        "cedula": datos.get("cedula", ""),
        "telefono_alternativo": datos.get("telefono_alternativo", ""),
        "direccion": datos.get("direccion", ""),
        "barrio": datos.get("barrio", ""),
        "ciudad": datos.get("ciudad", "Bogotá"),
        "email": datos.get("email", ""),
        "fecha_nacimiento": datos.get("fecha_nacimiento", ""),
        "ocupacion": datos.get("ocupacion", ""),
        "referencia_1": datos.get("referencia_1", {"nombre": "", "telefono": "", "parentesco": ""}),
        "referencia_2": datos.get("referencia_2", {"nombre": "", "telefono": "", "parentesco": ""}),
        "score_pago": datos.get("score_pago", ""),
        "estrella_nivel": datos.get("estrella_nivel", 0),
        "score_historial": [],
        "dpd_actual": 0,
        "bucket_actual": "AL_DIA",
        "gestiones": [],
        "wa_ultimo_mensaje": None,
        "wa_ultimo_comprobante": None,
        "notas": [],
        "alertas": [],
        "ptp_activo": None,
        "ultima_interaccion": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.crm_clientes.insert_one(new_doc)
    del new_doc["_id"]
    return new_doc


async def registrar_gestion(
    db,
    loanbook_id: str,
    canal: str,
    resultado: str,
    nota: str,
    autor: str,
    ptp_fecha: str | None = None,
) -> dict:
    """Append a contact attempt to gestiones_cartera, loanbook.gestiones[], and crm_clientes.gestiones[].
    Also updates crm_clientes.ultima_interaccion.
    """
    if resultado not in RESULTADO_VALIDOS:
        raise ValueError(f"resultado '{resultado}' no válido. Opciones: {sorted(RESULTADO_VALIDOS)}")

    now = datetime.now(timezone.utc).isoformat()
    today = date.today().isoformat()
    tiene_ptp = "prometió" in resultado or resultado == "acuerdo_de_pago_firmado"

    gestion = {
        "id": str(uuid.uuid4()),
        "loanbook_id": loanbook_id,
        "fecha": today,
        "canal": canal,
        "resultado": resultado,
        "nota": nota or "",
        "ptp_fecha": ptp_fecha if tiene_ptp else None,
        "ptp_fue_cumplido": None,
        "registrado_por": autor,
        "created_at": now,
    }

    # 1. Insert into gestiones_cartera collection
    await db.gestiones_cartera.insert_one({**gestion})
    gestion.pop("_id", None)

    # 2. Append to loanbook.gestiones[]
    await db.loanbook.update_one(
        {"id": loanbook_id},
        {
            "$push": {"gestiones": gestion},
            "$set": {
                "ultimo_contacto_fecha": today,
                "ultimo_contacto_resultado": resultado,
                "updated_at": now,
            },
        },
    )

    # 3. Find associated crm_clientes and append
    loan = await db.loanbook.find_one({"id": loanbook_id}, {"_id": 0, "cliente_id": 1, "cliente_telefono": 1})
    if loan:
        crm_query = {"$or": [
            {"id": loan.get("cliente_id", "")},
            {"telefono_principal": loan.get("cliente_telefono", "")},
        ]}
        await db.crm_clientes.update_one(
            crm_query,
            {
                "$push": {"gestiones": gestion},
                "$set": {"ultima_interaccion": now, "updated_at": now},
            },
        )
        # If PTP, also store ptp_activo on crm_clientes
        if ptp_fecha and tiene_ptp:
            await db.crm_clientes.update_one(
                crm_query,
                {"$set": {"ptp_activo": {"fecha": ptp_fecha, "loanbook_id": loanbook_id, "registrado_en": today}}},
            )

    # BUILD 9 — registrar outcome de aprendizaje (no bloqueante)
    try:
        from services import learning_engine
        asyncio.create_task(learning_engine.crear_outcome(db, gestion))
    except Exception:
        pass  # nunca bloquear la gestión principal

    return gestion


async def registrar_ptp(db, loanbook_id: str, ptp_fecha: str, ptp_monto: float, registrado_por: str) -> dict:
    """Set a promise-to-pay on both loanbook and crm_clientes, then emit event."""
    now = datetime.now(timezone.utc).isoformat()
    ptp_doc = {
        "fecha": ptp_fecha,
        "monto": ptp_monto,
        "registrado_por": registrado_por,
        "registrado_en": now,
        "cumplido": None,
    }
    await db.loanbook.update_one(
        {"id": loanbook_id},
        {"$set": {"ptp_fecha": ptp_fecha, "ptp_monto": ptp_monto, "ptp_activo": ptp_doc, "updated_at": now}},
    )
    loan = await db.loanbook.find_one({"id": loanbook_id}, {"_id": 0, "cliente_id": 1, "cliente_telefono": 1})
    if loan:
        await db.crm_clientes.update_one(
            {"$or": [
                {"id": loan.get("cliente_id", "")},
                {"telefono_principal": loan.get("cliente_telefono", "")},
            ]},
            {"$set": {"ptp_activo": ptp_doc, "updated_at": now}},
        )
    bus = EventBusService(db)
    await bus.emit(RoddosEvent(
        source_agent="crm",
        event_type="ptp.registrado",
        actor=registrado_por,
        target_entity=loanbook_id,
        payload={"new_state": ptp_fecha, "monto": ptp_monto, "fecha": ptp_fecha},
    ))
    await handle_state_side_effects(db, "ptp.registrado", loanbook_id, ptp_fecha)
    return ptp_doc


# ── FASE 8-A: Score Multidimensional ─────────────────────────────────────────

def calcular_score_roddos(loanbook_doc: dict, gestiones: list, pagos: list) -> dict:
    """Calcula score_roddos multidimensional (4 dimensiones, pesos exactos del PRD).

    Fórmula:
      score_roddos = (dim_dpd * 0.40) + (dim_gestion * 0.30) + (dim_velocidad * 0.20) + (dim_trayectoria * 0.10)

    Returns dict con score_roddos (float), etiqueta_roddos (str), y las 4 dimensiones.
    """
    dpd_actual = loanbook_doc.get("dpd_actual", 0) or 0
    dpd_max = loanbook_doc.get("dpd_maximo_historico", 0) or 0
    cuotas = loanbook_doc.get("cuotas", [])
    score_historial = loanbook_doc.get("score_historial", [])

    # ── dimension_dpd ──────────────────────────────────────────────────────────
    if dpd_actual == 0 and dpd_max < 7:
        dimension_dpd = 100.0
    elif dpd_actual == 0 and dpd_max < 15:
        dimension_dpd = 80.0
    elif dpd_actual <= 7:
        dimension_dpd = 60.0
    elif dpd_actual <= 14:
        dimension_dpd = 40.0
    elif dpd_actual <= 21:
        dimension_dpd = 20.0
    else:
        dimension_dpd = 0.0

    # ── dimension_gestion ─────────────────────────────────────────────────────
    intentos_gestion = len(gestiones)
    veces_contactado = sum(
        1 for g in gestiones
        if g.get("resultado", "").startswith("contestó") or g.get("resultado", "").startswith("respondió")
    )
    ptps_prometidos = sum(
        1 for g in gestiones
        if "prometió" in g.get("resultado", "") or g.get("resultado") in ("acuerdo_de_pago_firmado", "acuerdo_firmado")
    )
    ptps_cumplidos = sum(1 for g in gestiones if g.get("ptp_fue_cumplido") is True)
    ratio_ptp = ptps_cumplidos / max(ptps_prometidos, 1)
    contactabilidad = veces_contactado / max(intentos_gestion, 1)
    dimension_gestion = round((ratio_ptp * 0.6 + contactabilidad * 0.4) * 100)

    # ── dimension_velocidad ───────────────────────────────────────────────────
    # Promedio de las últimas 5 cuotas pagadas (días de retraso al pagar)
    cuotas_pagadas = [c for c in cuotas if c.get("estado") == "pagada"]
    cuotas_pagadas_sorted = sorted(cuotas_pagadas, key=lambda c: c.get("fecha_pago") or "", reverse=True)[:5]

    velocidad_scores = []
    for c in cuotas_pagadas_sorted:
        fecha_pago = c.get("fecha_pago", "")
        fecha_vcto = c.get("fecha_vencimiento", "")
        if fecha_pago and fecha_vcto:
            try:
                dias_retraso = (date.fromisoformat(fecha_pago[:10]) - date.fromisoformat(fecha_vcto[:10])).days
                if dias_retraso <= 0:
                    velocidad_scores.append(100)
                elif dias_retraso <= 2:
                    velocidad_scores.append(85)
                elif dias_retraso <= 7:
                    velocidad_scores.append(65)
                elif dias_retraso <= 14:
                    velocidad_scores.append(40)
                else:
                    velocidad_scores.append(15)
            except (ValueError, TypeError):
                pass

    dimension_velocidad = sum(velocidad_scores) / len(velocidad_scores) if velocidad_scores else 60.0

    # ── dimension_trayectoria ─────────────────────────────────────────────────
    # Compara dpd_actual con dpd hace ~28 días (busca en score_historial)
    dimension_trayectoria = 60.0  # neutro por defecto / sin historial
    if score_historial:
        hoy = date.today()
        hace_28 = (hoy.toordinal() - 28)
        entrada_pasada = None
        for entrada in reversed(score_historial):
            fecha_entrada = entrada.get("fecha", "")
            if fecha_entrada:
                try:
                    ord_entrada = date.fromisoformat(fecha_entrada[:10]).toordinal()
                    diff = abs(hoy.toordinal() - ord_entrada)
                    if 21 <= diff <= 35:  # ventana ~4 semanas
                        entrada_pasada = entrada
                        break
                except (ValueError, TypeError):
                    pass
        if entrada_pasada:
            dpd_pasado = entrada_pasada.get("dpd_actual", dpd_actual)
            delta_dpd = dpd_pasado - dpd_actual  # positivo = mejoró (dpd bajó)
            if delta_dpd > 3:
                dimension_trayectoria = 100.0
            elif abs(delta_dpd) <= 3:
                dimension_trayectoria = 60.0
            else:
                dimension_trayectoria = 20.0

    # ── Score final ───────────────────────────────────────────────────────────
    score_roddos = round(
        (dimension_dpd * 0.40) +
        (dimension_gestion * 0.30) +
        (dimension_velocidad * 0.20) +
        (dimension_trayectoria * 0.10)
    , 1)

    # ── Etiqueta ──────────────────────────────────────────────────────────────
    if score_roddos >= 85:
        etiqueta = "A+"
    elif score_roddos >= 70:
        etiqueta = "A"
    elif score_roddos >= 55:
        etiqueta = "B"
    elif score_roddos >= 40:
        etiqueta = "C"
    elif score_roddos >= 25:
        etiqueta = "D"
    else:
        etiqueta = "E"

    return {
        "score_roddos": score_roddos,
        "etiqueta_roddos": etiqueta,
        "dimension_dpd": dimension_dpd,
        "dimension_gestion": dimension_gestion,
        "dimension_velocidad": round(dimension_velocidad, 1),
        "dimension_trayectoria": dimension_trayectoria,
    }


async def upsert_cliente_desde_loanbook(db, loan: dict) -> dict:
    """Crea o actualiza crm_clientes a partir de un loanbook activado.

    Score neutro de inicio: score_roddos=70, etapa_cobro='preventivo', ptp_activo=null.
    Identifica al cliente por teléfono principal o cliente_id.
    """
    now = datetime.now(timezone.utc).isoformat()
    telefono = normalizar_telefono(loan.get("cliente_telefono", ""))
    cliente_id = loan.get("cliente_id", "")
    loanbook_id = loan.get("id", "")

    query = {"$or": []}
    if cliente_id:
        query["$or"].append({"id": cliente_id})
    if telefono:
        query["$or"].append({"telefono_principal": telefono})

    if not query["$or"]:
        return {}

    existing = await db.crm_clientes.find_one(query, {"_id": 0})
    if existing:
        # Solo actualiza campos que pueden haber cambiado, preserva historial
        safe_fields = {
            "nombre_completo": loan.get("cliente_nombre", existing.get("nombre_completo", "")),
            "cedula": loan.get("cliente_nit", existing.get("cedula", "")),
            "loanbook_id_activo": loanbook_id,
            "updated_at": now,
        }
        await db.crm_clientes.update_one(query, {"$set": safe_fields})
        return {**existing, **safe_fields}

    new_doc = {
        "id": cliente_id or str(uuid.uuid4()),
        "telefono_principal": telefono,
        "nombre_completo": loan.get("cliente_nombre", ""),
        "cedula": loan.get("cliente_nit", ""),
        "telefono_alternativo": "",
        "direccion": "",
        "barrio": "",
        "ciudad": "Bogotá",
        "email": "",
        "fecha_nacimiento": "",
        "ocupacion": "",
        "referencia_1": {"nombre": "", "telefono": "", "parentesco": ""},
        "referencia_2": {"nombre": "", "telefono": "", "parentesco": ""},
        "loanbook_id_activo": loanbook_id,
        # Score neutro inicial FASE 8-A
        "score_roddos": 70,
        "etiqueta_roddos": "B",
        "etapa_cobro": "preventivo",
        "score_pago": "",
        "estrella_nivel": 0,
        "score_historial": [],
        "dpd_actual": 0,
        "bucket_actual": "AL_DIA",
        "gestiones": [],
        "wa_ultimo_mensaje": None,
        "wa_ultimo_comprobante": None,
        "notas": [],
        "alertas": [],
        "ptp_activo": None,
        "ultima_interaccion": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.crm_clientes.insert_one(new_doc)
    new_doc.pop("_id", None)
    return new_doc


async def crear_acuerdo(db, loanbook_id: str, datos: dict, autor: str = "sistema") -> dict:
    """Crea un acuerdo de pago formal en la colección acuerdos_pago.

    También registra gestión 'acuerdo_firmado' y actualiza etapa_cobro en crm_clientes.
    """
    now = datetime.now(timezone.utc).isoformat()
    acuerdo_id = str(uuid.uuid4())

    loan = await db.loanbook.find_one({"id": loanbook_id}, {"_id": 0, "cliente_nombre": 1})
    cliente_nombre = (loan or {}).get("cliente_nombre", "") if loan else datos.get("cliente_nombre", "")

    acuerdo = {
        "id": acuerdo_id,
        "loanbook_id": loanbook_id,
        "cliente_nombre": cliente_nombre,
        "tipo": datos.get("tipo", "acuerdo_total"),
        "condiciones": datos.get("condiciones", ""),
        "monto_acordado": datos.get("monto_acordado", 0),
        "fecha_inicio": datos.get("fecha_inicio", date.today().isoformat()),
        "fecha_limite": datos.get("fecha_limite", ""),
        "cuotas_acuerdo": datos.get("cuotas_acuerdo", []),
        "estado": "activo",
        "creado_por": autor,
        "created_at": now,
        "updated_at": now,
    }
    await db.acuerdos_pago.insert_one({**acuerdo})
    acuerdo.pop("_id", None)

    # Registrar gestión acuerdo_firmado
    try:
        await registrar_gestion(
            db,
            loanbook_id=loanbook_id,
            canal="sistema",
            resultado="acuerdo_firmado",
            nota=f"Acuerdo creado. Tipo: {acuerdo['tipo']}. Monto: {acuerdo['monto_acordado']}",
            autor=autor,
            ptp_fecha=datos.get("fecha_limite"),
        )
    except Exception:
        pass  # gestión no bloquea creación del acuerdo

    return acuerdo


async def actualizar_estado_acuerdo(db, acuerdo_id: str, estado: str) -> dict:
    """Actualiza el estado de un acuerdo de pago (cumplido|incumplido|cancelado|activo)."""
    ESTADOS_VALIDOS = {"activo", "cumplido", "incumplido", "cancelado"}
    if estado not in ESTADOS_VALIDOS:
        raise ValueError(f"Estado '{estado}' no válido. Opciones: {sorted(ESTADOS_VALIDOS)}")

    now = datetime.now(timezone.utc).isoformat()
    await db.acuerdos_pago.update_one(
        {"id": acuerdo_id},
        {"$set": {"estado": estado, "updated_at": now}},
    )
    acuerdo = await db.acuerdos_pago.find_one({"id": acuerdo_id}, {"_id": 0})
    return acuerdo or {}


async def agregar_nota(db, cliente_id: str, nota: str, autor: str) -> dict:
    """Append a cobrador note to crm_clientes.notas[] (immutable history)."""
    now = datetime.now(timezone.utc).isoformat()
    nota_doc = {
        "id": str(uuid.uuid4()),
        "texto": nota,
        "autor": autor,
        "created_at": now,
    }
    await db.crm_clientes.update_one(
        {"id": cliente_id},
        {"$push": {"notas": nota_doc}, "$set": {"updated_at": now}},
    )
    return nota_doc
