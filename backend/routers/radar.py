"""radar.py — RODDOS RADAR: cobranza, cola de gestión, salud de cartera."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends

from database import db
from dependencies import get_current_user
from services.shared_state import get_portfolio_health, get_daily_collection_queue

router = APIRouter(prefix="/radar", tags=["radar"])


@router.get("/portfolio-health")
async def portfolio_health(current_user=Depends(get_current_user)):
    """KPIs de salud de cartera desde shared_state (caché TTL 30 s)."""
    return await get_portfolio_health(db)


@router.get("/queue")
async def collection_queue(current_user=Depends(get_current_user)):
    """Cola de cobro del día (< 200 ms, desde caché).
    Cada ítem incluye: bucket, dpd_actual, total_a_pagar, dias_para_protocolo, whatsapp_link.
    """
    return await get_daily_collection_queue(db)


@router.get("/semana")
async def semana_stats(current_user=Depends(get_current_user)):
    """Cuotas esperadas esta semana vs pagadas vs pendientes."""
    hoy      = date.today()
    lunes    = hoy - timedelta(days=hoy.weekday())
    domingo  = lunes + timedelta(days=6)
    lunes_s  = lunes.isoformat()
    domingo_s = domingo.isoformat()

    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora", "completado"]}},
        {"_id": 0, "cuotas": 1, "codigo": 1, "cliente_nombre": 1},
    ).to_list(5000)

    esperadas: list[dict] = []
    pagadas:   list[dict] = []
    pendientes: list[dict] = []

    for loan in loans:
        for cuota in loan.get("cuotas", []):
            fv = cuota.get("fecha_vencimiento", "")
            if lunes_s <= fv <= domingo_s:
                item: dict = {
                    "codigo":            loan["codigo"],
                    "cliente_nombre":    loan.get("cliente_nombre", ""),
                    "cuota_numero":      cuota.get("numero"),
                    "fecha_vencimiento": fv,
                    "valor":             cuota.get("valor", 0),
                    "estado":            cuota.get("estado"),
                }
                esperadas.append(item)
                if cuota.get("estado") == "pagada":
                    pagadas.append(item)
                else:
                    pendientes.append(item)

    valor_esperado  = sum(e["valor"] for e in esperadas)
    valor_cobrado   = sum(p["valor"] for p in pagadas)
    valor_pendiente = sum(p["valor"] for p in pendientes)

    return {
        "semana": {"inicio": lunes_s, "fin": domingo_s},
        "totales": {
            "cuotas_esperadas":  len(esperadas),
            "cuotas_pagadas":    len(pagadas),
            "cuotas_pendientes": len(pendientes),
            "valor_esperado":    valor_esperado,
            "valor_cobrado":     valor_cobrado,
            "valor_pendiente":   valor_pendiente,
            "porcentaje_cobrado": round(valor_cobrado / valor_esperado * 100, 1)
            if valor_esperado > 0 else 0.0,
        },
        "detalle_pendiente": sorted(pendientes, key=lambda x: x["fecha_vencimiento"]),
    }


@router.get("/roll-rate")
async def roll_rate(current_user=Depends(get_current_user)):
    """% loanbooks que cambiaron a bucket peor en los últimos 7 días.
    Retorna 0 % (data_disponible=False) si no hay eventos suficientes.
    """
    BUCKET_ORDER = {"0": 0, "1-7": 1, "8-14": 2, "15-21": 3, "22+": 4}

    hace_7_dias = (date.today() - timedelta(days=7)).isoformat()

    eventos = await db.roddos_events.find(
        {
            "event_type": "loanbook.bucket_change",
            "timestamp":  {"$gte": hace_7_dias},
        },
        {"_id": 0, "entity_id": 1, "new_state": 1, "metadata": 1, "timestamp": 1},
    ).sort("timestamp", -1).to_list(2000)

    if not eventos:
        return {
            "roll_rate_pct":    0.0,
            "data_disponible":  False,
            "mensaje":          "Sin datos suficientes. Disponible tras 7 días de operación.",
            "total_changes":    0,
            "empeorados":       0,
            "mejorados":        0,
        }

    # Tomar el cambio más reciente por loanbook_id
    latest: dict = {}
    for evt in eventos:
        eid = evt.get("entity_id", "")
        if eid not in latest:
            latest[eid] = evt

    worsened = improved = 0
    for evt in latest.values():
        new_b  = evt.get("new_state", "0")
        prev_b = (evt.get("metadata") or {}).get("prev_bucket", "0")
        new_o  = BUCKET_ORDER.get(new_b, 0)
        prev_o = BUCKET_ORDER.get(prev_b, 0)
        if new_o > prev_o:
            worsened += 1
        elif new_o < prev_o:
            improved += 1

    total     = len(latest)
    roll_rate = round(worsened / total * 100, 1) if total > 0 else 0.0

    return {
        "roll_rate_pct":          roll_rate,
        "data_disponible":        True,
        "total_loans_con_cambio": total,
        "empeorados":             worsened,
        "mejorados":              improved,
        "periodo_dias":           7,
    }
