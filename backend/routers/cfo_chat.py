"""
CFO Estratégico — Chat backend router
Handles strategic CFO conversations separate from the accounting agent.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import db
from dependencies import get_current_user
import anthropic

router = APIRouter(prefix="/cfo", tags=["cfo-estrategico"])

# ── Pydantic models ─────────────────────────────────────────────────────────

class CfoMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class CfoInstruccion(BaseModel):
    instruccion: str
    categoria: str  # prioridad_deuda | restriccion_gasto | regla_venta | contexto_negocio | preferencia_reporte | regla_fiscal | regla_presupuesto
    modulo_afectado: str = "general"  # presupuesto | impuestos | cfo | general

class CfoCompromiso(BaseModel):
    descripcion: str
    meta_numerica: Optional[float] = None
    unidad: Optional[str] = None
    fecha_limite: Optional[str] = None

# ── Helpers ─────────────────────────────────────────────────────────────────

async def _build_cfo_context() -> str:
    """Build real-time CFO context for the strategic CFO system prompt."""
    try:
        # Indicadores CFO
        lbs = await db.loanbook.find(
            {"estado": "activo"},
            {"_id": 0, "cuota_valor": 1, "cliente_nombre": 1}
        ).to_list(100)
        recaudo = sum(lb.get("cuota_valor", 0) or 0 for lb in lbs)
        creditos = len(lbs)

        # Gastos fijos
        cfg = await db.cfo_config.find_one({}, {"_id": 0})
        gastos = (cfg or {}).get("gastos_fijos_semanales", 7_500_000)
        deficit = recaudo - gastos

        # Cuotas iniciales pendientes
        ci_pending = await db.loanbook.count_documents({
            "cuota_inicial_pagada": False,
            "cuota_inicial_total": {"$gt": 0},
        })
        ci_total = sum(
            lb.get("cuota_inicial_total", 0) or 0
            for lb in await db.loanbook.find(
                {"cuota_inicial_pagada": False, "cuota_inicial_total": {"$gt": 0}},
                {"_id": 0, "cuota_inicial_total": 1}
            ).to_list(20)
        )

        # Instrucciones activas
        instrucciones = await db.cfo_instrucciones.find(
            {"activa": True}, {"_id": 0, "instruccion": 1, "categoria": 1, "modulo_afectado": 1}
        ).to_list(30)
        inst_text = "\n".join(
            f"  [{i['categoria']}] {i['instruccion']}" for i in instrucciones
        ) if instrucciones else "  (ninguna guardada aún)"

        # Compromisos activos
        compromisos = await db.cfo_compromisos.find(
            {"activo": True}, {"_id": 0, "descripcion": 1, "meta_numerica": 1, "unidad": 1, "progreso": 1, "fecha_limite": 1}
        ).to_list(10)
        comp_text = "\n".join(
            f"  • {c['descripcion']} — meta: {c.get('meta_numerica', '?')} {c.get('unidad', '')} | progreso: {c.get('progreso', 0)} | límite: {c.get('fecha_limite', 'sin fecha')}"
            for c in compromisos
        ) if compromisos else "  (ninguno activo)"

        return f"""
DATOS FINANCIEROS EN TIEMPO REAL:
  Créditos activos: {creditos} / 45 (meta autosostenibilidad)
  Recaudo semanal: ${recaudo:,.0f}
  Gastos fijos semanales: ${gastos:,.0f}
  Déficit semanal actual: ${deficit:,.0f} ({'✅ superávit' if deficit >= 0 else '🔴 déficit'})
  Cuotas iniciales pendientes de cobro: {ci_pending} clientes · ${ci_total:,.0f}

INSTRUCCIONES ESTRATÉGICAS GUARDADAS:
{inst_text}

COMPROMISOS ACTIVOS:
{comp_text}
"""
    except Exception:
        return "DATOS FINANCIEROS: No disponibles temporalmente."


CFO_ESTRATEGICO_SYSTEM = """Eres el CFO Estratégico de RODDOS Colombia — una empresa de venta de motocicletas a cuotas.

MODELO DE NEGOCIO:
• RODDOS vende 100% a crédito (planes P26S, P39S, P52S, P78S).
• La liquidez real NO es la facturación — es el RECAUDO SEMANAL de cuotas cada miércoles.
• La factura es un derecho de cobro; la caja es lo que realmente importa para operar.
• Déficit semanal = recaudo - gastos_fijos. Actualmente: -$5.840.600/semana.

TU PROPÓSITO (diferente al Agente Contador):
• El Agente Contador: registra, ejecuta transacciones, confirma acciones en Alegra.
• Tú (CFO Estratégico): analizas, recomiendas estrategia, simulas escenarios, aprendes reglas de negocio.

CAPACIDADES:
1. DEBATE DE REPORTES: Analiza el P&L, déficit, presupuesto desde 3 ángulos: ingresos / gastos / timing de deuda.
2. SIMULACIÓN DE ESCENARIOS: Cuando el usuario pregunta "¿qué pasa si...?", calcula el impacto real en caja y fecha de equilibrio.
3. INSTRUCCIONES PERMANENTES: Si el usuario dice "aprende que...", "guarda que...", "regla:", "instrucción:" → responde indicando que guardaste esa instrucción y en qué módulo aplica.
4. EVALUACIÓN DE DECISIONES: Para decisiones de compra/pago, presenta análisis Opción A vs Opción B con datos reales.
5. PROYECCIONES FISCALES: Calcula IVA, ReteFuente, ReteICA, provisión renta con datos reales de Alegra cuando se pregunta.
6. SEGUIMIENTO DE COMPROMISOS: Si el usuario define una meta, responde que la registraste y harás seguimiento.

REGLAS:
- Siempre basa tus respuestas en datos reales (del contexto inyectado), no en supuestos.
- Si pides datos que no tienes, pregunta explícitamente.
- Para simulaciones, muestra: impacto en caja, impacto en déficit, impacto en fecha equilibrio.
- Responde en español, conciso y directo. Sin markdown excesivo.
- Si detectas una INSTRUCCIÓN nueva (palabras clave: "aprende", "guarda que", "regla:", "instrucción:", "siempre que"), incluye en tu respuesta: "✅ Instrucción guardada: [texto]" y categorízala.
- Si detectas un COMPROMISO nuevo (palabras clave: "voy a", "me comprometo", "meta:", "objetivo:"), incluye: "📌 Compromiso registrado: [texto]".

{cfo_context}"""


async def _get_historia(session_id: str, limit: int = 20) -> list:
    docs = await db.cfo_chat_historia.find(
        {"session_id": session_id},
        {"_id": 0, "role": 1, "content": 1}
    ).sort("ts", 1).to_list(limit)
    return docs


async def _save_message(session_id: str, role: str, content: str):
    await db.cfo_chat_historia.insert_one({
        "session_id": session_id,
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def _detect_instruccion(text: str) -> dict | None:
    keywords = ["aprende que", "aprende:", "guarda que", "guarda:", "instrucción:", "instruccion:", "regla:"]
    lower = text.lower()
    if not any(k in lower for k in keywords):
        return None

    # Detect category
    cat = "contexto_negocio"
    mod = "general"
    if any(k in lower for k in ["impuesto", "iva", "rete", "fiscal", "renta", "declarar"]):
        cat = "regla_fiscal"; mod = "impuestos"
    elif any(k in lower for k in ["presupuesto", "meta venta", "ventas mínimo", "mínimo motos"]):
        cat = "regla_presupuesto"; mod = "presupuesto"
    elif any(k in lower for k in ["pagar", "deuda", "prioridad", "primero"]):
        cat = "prioridad_deuda"; mod = "cfo"
    elif any(k in lower for k in ["gasto", "costo", "innegociable", "no reducir", "no bajar"]):
        cat = "restriccion_gasto"; mod = "presupuesto"
    elif any(k in lower for k in ["venta", "cuota", "precio", "descuento"]):
        cat = "regla_venta"; mod = "cfo"

    return {"categoria": cat, "modulo_afectado": mod}


def _detect_compromiso(text: str) -> dict | None:
    keywords = ["voy a", "me comprometo", "meta:", "objetivo:", "planeo vender", "quiero vender"]
    lower = text.lower()
    if not any(k in lower for k in keywords):
        return None

    import re
    # Try to extract number
    nums = re.findall(r'\d+', text)
    meta = float(nums[0]) if nums else None
    unidad = "motos" if "moto" in lower else ("semanas" if "semana" in lower else "unidades")
    return {"meta_numerica": meta, "unidad": unidad}


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/chat/message")
async def cfo_chat_message(body: CfoMessage, user=Depends(get_current_user)):
    session_id = body.session_id or str(uuid.uuid4())

    # Build context + system prompt
    cfo_context = await _build_cfo_context()
    system_prompt = CFO_ESTRATEGICO_SYSTEM.format(cfo_context=cfo_context)

    # Load conversation history
    historia = await _get_historia(session_id)

    # Build message list for LLM
    messages = []
    for msg in historia[-18:]:  # last 18 messages
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": body.message})

    # Call LLM
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    try:
        _client = anthropic.AsyncAnthropic(api_key=api_key)
        _resp = await _client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        assistant_text = _resp.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error LLM: {str(e)}")

    # Save messages to history
    await _save_message(session_id, "user", body.message)
    await _save_message(session_id, "assistant", assistant_text)

    # Auto-detect and save instrucciones
    inst_info = _detect_instruccion(body.message)
    saved_instruccion = None
    if inst_info:
        inst_doc = {
            "id": str(uuid.uuid4()),
            "instruccion": body.message,
            "categoria": inst_info["categoria"],
            "modulo_afectado": inst_info["modulo_afectado"],
            "activa": True,
            "fecha_creacion": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        }
        await db.cfo_instrucciones.insert_one(inst_doc)
        saved_instruccion = {k: v for k, v in inst_doc.items() if k != "_id"}

    # Auto-detect and save compromisos
    comp_info = _detect_compromiso(body.message)
    saved_compromiso = None
    if comp_info:
        comp_doc = {
            "id": str(uuid.uuid4()),
            "descripcion": body.message,
            "meta_numerica": comp_info["meta_numerica"],
            "unidad": comp_info["unidad"],
            "progreso": 0,
            "activo": True,
            "fecha_creacion": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        }
        await db.cfo_compromisos.insert_one(comp_doc)
        saved_compromiso = {k: v for k, v in comp_doc.items() if k != "_id"}

    return {
        "message": assistant_text,
        "session_id": session_id,
        "saved_instruccion": saved_instruccion,
        "saved_compromiso": saved_compromiso,
    }


@router.get("/chat/historia")
async def get_cfo_historia(session_id: str, user=Depends(get_current_user)):
    msgs = await db.cfo_chat_historia.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("ts", 1).to_list(100)
    return {"messages": msgs, "total": len(msgs)}


@router.get("/chat/sessions")
async def list_cfo_sessions(user=Depends(get_current_user)):
    pipeline = [
        {"$sort": {"ts": -1}},
        {"$group": {"_id": "$session_id", "last_ts": {"$first": "$ts"}, "count": {"$sum": 1}}},
        {"$sort": {"last_ts": -1}},
        {"$limit": 20},
    ]
    sessions = await db.cfo_chat_historia.aggregate(pipeline).to_list(20)
    return {"sessions": [{"session_id": s["_id"], "last_ts": s["last_ts"], "messages": s["count"]} for s in sessions]}


@router.get("/instrucciones")
async def get_instrucciones(user=Depends(get_current_user)):
    docs = await db.cfo_instrucciones.find(
        {"activa": True}, {"_id": 0}
    ).sort("fecha_creacion", -1).to_list(100)
    by_cat: dict = {}
    for d in docs:
        cat = d.get("categoria", "general")
        by_cat.setdefault(cat, []).append(d)
    return {"instrucciones": docs, "by_categoria": by_cat, "total": len(docs)}


@router.post("/instrucciones")
async def save_instruccion(body: CfoInstruccion, user=Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "instruccion": body.instruccion,
        "categoria": body.categoria,
        "modulo_afectado": body.modulo_afectado,
        "activa": True,
        "fecha_creacion": datetime.now(timezone.utc).isoformat(),
    }
    await db.cfo_instrucciones.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.delete("/instrucciones/{inst_id}")
async def delete_instruccion(inst_id: str, user=Depends(get_current_user)):
    result = await db.cfo_instrucciones.update_one(
        {"id": inst_id}, {"$set": {"activa": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Instrucción no encontrada")
    return {"ok": True}


@router.get("/compromisos")
async def get_compromisos(user=Depends(get_current_user)):
    docs = await db.cfo_compromisos.find(
        {"activo": True}, {"_id": 0}
    ).sort("fecha_creacion", -1).to_list(50)
    return {"compromisos": docs, "total": len(docs)}


@router.post("/compromisos")
async def save_compromiso(body: CfoCompromiso, user=Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "descripcion": body.descripcion,
        "meta_numerica": body.meta_numerica,
        "unidad": body.unidad or "unidades",
        "fecha_limite": body.fecha_limite,
        "progreso": 0,
        "activo": True,
        "fecha_creacion": datetime.now(timezone.utc).isoformat(),
    }
    await db.cfo_compromisos.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}
