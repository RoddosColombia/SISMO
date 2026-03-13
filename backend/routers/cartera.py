"""Cartera router — weekly/monthly collection views and client behavior."""
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends

from database import db
from dependencies import get_current_user
from routers.loanbook import _update_overdue

router = APIRouter(prefix="/cartera", tags=["cartera"])


def _week_range(semana: Optional[str]) -> tuple:
    """Given 'YYYY-Www' or None (= current week), return (start, end) as date objects."""
    if semana:
        # e.g. "2026-W05"
        try:
            parts = semana.split("-W")
            year, week = int(parts[0]), int(parts[1])
            d = date.fromisocalendar(year, week, 1)
            return d, d + timedelta(days=6)
        except Exception:
            pass
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


@router.get("/semanal")
async def get_cartera_semanal(semana: Optional[str] = None, current_user=Depends(get_current_user)):
    """Return all installments due in the given week across all active loans."""
    start, end = _week_range(semana)
    start_s, end_s = start.isoformat(), end.isoformat()

    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora", "pendiente_entrega"]}}, {"_id": 0}
    ).to_list(2000)

    cuotas_semana = []
    for loan in loans:
        cuotas = _update_overdue(loan.get("cuotas", []))
        for c in cuotas:
            fv = c.get("fecha_vencimiento", "")
            if start_s <= fv <= end_s:
                cuotas_semana.append({
                    "loanbook_id": loan["id"],
                    "codigo": loan["codigo"],
                    "cliente_id": loan["cliente_id"],
                    "cliente_nombre": loan["cliente_nombre"],
                    "moto": loan.get("moto_descripcion", ""),
                    "plan": loan["plan"],
                    "cuota_numero": c["numero"],
                    "fecha_vencimiento": fv,
                    "valor": c["valor"],
                    "estado": c["estado"],
                    "fecha_pago": c.get("fecha_pago"),
                    "valor_pagado": c.get("valor_pagado", 0),
                    "comprobante": c.get("comprobante"),
                    "total_cuotas": loan["num_cuotas"],
                })

    cuotas_semana.sort(key=lambda x: (x["fecha_vencimiento"], x["cliente_nombre"]))

    # Totals
    total_esperado = sum(c["valor"] for c in cuotas_semana)
    total_cobrado = sum(c["valor_pagado"] for c in cuotas_semana if c["estado"] == "pagada")
    total_pendiente = sum(c["valor"] for c in cuotas_semana if c["estado"] == "pendiente")
    total_vencido = sum(c["valor"] for c in cuotas_semana if c["estado"] == "vencida")
    tasa_cobro = round((total_cobrado / total_esperado * 100) if total_esperado > 0 else 0, 1)

    return {
        "semana": semana or f"{start.isocalendar()[0]}-W{str(start.isocalendar()[1]).zfill(2)}",
        "semana_label": f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}",
        "start": start_s,
        "end": end_s,
        "cuotas": cuotas_semana,
        "resumen": {
            "total_cuotas": len(cuotas_semana),
            "total_esperado": total_esperado,
            "total_cobrado": total_cobrado,
            "total_pendiente": total_pendiente,
            "total_vencido": total_vencido,
            "tasa_cobro_pct": tasa_cobro,
            "cuotas_pagadas": sum(1 for c in cuotas_semana if c["estado"] == "pagada"),
            "cuotas_pendientes": sum(1 for c in cuotas_semana if c["estado"] == "pendiente"),
            "cuotas_vencidas": sum(1 for c in cuotas_semana if c["estado"] == "vencida"),
        },
    }


@router.get("/mensual")
async def get_cartera_mensual(ano: int = None, current_user=Depends(get_current_user)):
    """Return monthly collection summary for the given year."""
    ano = ano or datetime.now(timezone.utc).year
    loans = await db.loanbook.find({}, {"_id": 0}).to_list(2000)

    monthly: dict = {str(m).zfill(2): {
        "esperado": 0.0, "cobrado": 0.0, "pendiente": 0.0,
        "vencido": 0.0, "num_cuotas": 0, "num_pagadas": 0,
    } for m in range(1, 13)}

    for loan in loans:
        for c in loan.get("cuotas", []):
            fv = c.get("fecha_vencimiento", "")
            if not fv.startswith(str(ano)):
                continue
            mes = fv[5:7]
            monthly[mes]["num_cuotas"] += 1
            monthly[mes]["esperado"] += c["valor"]
            if c["estado"] == "pagada":
                monthly[mes]["cobrado"] += c.get("valor_pagado", c["valor"])
                monthly[mes]["num_pagadas"] += 1
            elif c["estado"] == "vencida":
                monthly[mes]["vencido"] += c["valor"]
            else:
                monthly[mes]["pendiente"] += c["valor"]

    MONTH_NAMES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    result = []
    for i, (mes, data) in enumerate(sorted(monthly.items())):
        result.append({
            "mes": mes,
            "mes_nombre": MONTH_NAMES[i],
            "tasa_cobro_pct": round((data["cobrado"] / data["esperado"] * 100) if data["esperado"] > 0 else 0, 1),
            **data,
        })
    return {"ano": ano, "meses": result}


@router.get("/clientes")
async def get_comportamiento_clientes(current_user=Depends(get_current_user)):
    """Return payment behavior record per client."""
    loans = await db.loanbook.find({}, {"_id": 0}).to_list(2000)
    today_s = date.today().isoformat()

    clientes: dict = {}
    for loan in loans:
        cid = loan.get("cliente_id") or loan["cliente_nombre"]
        if cid not in clientes:
            clientes[cid] = {
                "cliente_id": loan["cliente_id"],
                "cliente_nombre": loan["cliente_nombre"],
                "cliente_nit": loan.get("cliente_nit", ""),
                "num_creditos": 0,
                "total_cuotas": 0,
                "pagadas_tiempo": 0,
                "pagadas_tarde": 0,
                "vencidas": 0,
                "pendientes": 0,
                "total_cobrado": 0.0,
                "saldo_pendiente": 0.0,
                "creditos": [],
            }

        c_data = clientes[cid]
        c_data["num_creditos"] += 1
        c_data["creditos"].append({
            "codigo": loan["codigo"],
            "plan": loan["plan"],
            "estado": loan["estado"],
            "moto": loan.get("moto_descripcion", ""),
            "precio_venta": loan["precio_venta"],
        })
        c_data["total_cobrado"] += loan.get("total_cobrado", 0)
        c_data["saldo_pendiente"] += loan.get("saldo_pendiente", 0)

        for c in loan.get("cuotas", []):
            c_data["total_cuotas"] += 1
            if c["estado"] == "pagada":
                fv = c.get("fecha_vencimiento", "")
                fp = c.get("fecha_pago", "")
                if fp and fp <= fv:
                    c_data["pagadas_tiempo"] += 1
                else:
                    c_data["pagadas_tarde"] += 1
            elif c["estado"] == "vencida":
                c_data["vencidas"] += 1
            else:
                c_data["pendientes"] += 1

    result = []
    for c_data in clientes.values():
        base = c_data["pagadas_tiempo"] + c_data["pagadas_tarde"] + c_data["vencidas"]
        score = round((c_data["pagadas_tiempo"] / base * 100) if base > 0 else 0, 1)
        if score >= 90:
            categoria = "Excelente"
            color = "green"
        elif score >= 70:
            categoria = "Bueno"
            color = "yellow"
        elif score >= 50:
            categoria = "Regular"
            color = "orange"
        else:
            categoria = "Malo"
            color = "red"
        result.append({**c_data, "score_pago": score, "categoria_pago": categoria, "score_color": color})

    result.sort(key=lambda x: x["score_pago"])
    return result


@router.get("/clientes/{cliente_id}")
async def get_cliente_record(cliente_id: str, current_user=Depends(get_current_user)):
    """Full payment history for a specific client."""
    loans = await db.loanbook.find({"cliente_id": cliente_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    if not loans:
        loans = await db.loanbook.find({"cliente_nombre": {"$regex": cliente_id, "$options": "i"}}, {"_id": 0}).to_list(100)

    pagos = await db.cartera_pagos.find({"cliente_id": cliente_id}, {"_id": 0}).sort("fecha_pago", -1).to_list(500)
    if not pagos:
        pagos = await db.cartera_pagos.find(
            {"cliente_nombre": {"$regex": cliente_id, "$options": "i"}}, {"_id": 0}
        ).sort("fecha_pago", -1).to_list(500)

    return {"loans": loans, "historial_pagos": pagos}
