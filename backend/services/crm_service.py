"""crm_service.py — CRM operations: upsert_cliente, gestiones, PTP, notas.

All mutations are append-only on historical arrays (gestiones, notas, score_historial).
Never overwrite historical records.
"""
import re
import uuid
import asyncio
from datetime import datetime, timezone, date

from services.shared_state import emit_state_change


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
    await emit_state_change(
        db, "ptp.registrado", loanbook_id, ptp_fecha, registrado_por,
        metadata={"monto": ptp_monto, "fecha": ptp_fecha},
    )
    return ptp_doc


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
