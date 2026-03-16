"""ventas.py — Dashboard de ventas del mes para RODDOS."""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from database import db
from dependencies import get_current_user

router = APIRouter(prefix="/ventas", tags=["ventas"])
logger = logging.getLogger(__name__)

META_MENSUAL = 45  # motos objetivo por mes


@router.get("/dashboard")
async def get_ventas_dashboard(
    mes: Optional[str] = None,   # YYYY-MM, defaults to current month
    current_user=Depends(get_current_user),
):
    """Sales dashboard for a given month. Returns KPIs + por-model breakdown + detail table."""
    # Default to current month (Bogotá timezone offset ~ -5h)
    if not mes:
        now_bogota = datetime.now(timezone.utc)
        mes = now_bogota.strftime("%Y-%m")

    try:
        year, month = int(mes[:4]), int(mes[5:7])
    except (ValueError, IndexError):
        year, month = datetime.now(timezone.utc).year, datetime.now(timezone.utc).month
        mes = f"{year}-{str(month).zfill(2)}"

    fecha_inicio = f"{mes}-01"
    # Last day of month
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    fecha_fin = f"{mes}-{str(last_day).zfill(2)}"

    # Previous month
    if month == 1:
        prev_mes = f"{year - 1}-12"
    else:
        prev_mes = f"{year}-{str(month - 1).zfill(2)}"

    # ── Motos vendidas en el mes ──────────────────────────────────────────────
    # Source: inventario_motos where fecha_venta in [fecha_inicio, fecha_fin]
    motos_mes = await db.inventario_motos.find(
        {
            "estado": {"$in": ["Vendida", "Entregada"]},
            "fecha_venta": {"$gte": fecha_inicio, "$lte": fecha_fin},
        },
        {"_id": 0, "chasis": 1, "motor": 1, "modelo": 1, "version": 1, "color": 1,
         "propietario": 1, "factura_alegra_id": 1, "fecha_venta": 1, "estado": 1,
         "costo_compra": 1},
    ).to_list(200)

    # ── Match loanbooks para más datos ────────────────────────────────────────
    # Loanbooks are matched by moto_chasis (primary) since fecha_factura may be null for older records
    chasis_list = [m.get("chasis") for m in motos_mes if m.get("chasis")]
    loanbooks_for_motos = await db.loanbook.find(
        {"moto_chasis": {"$in": chasis_list}},
        {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "plan": 1,
         "valor_cuota": 1, "cuota_inicial": 1, "precio_venta": 1,
         "estado": 1, "moto_chasis": 1, "factura_alegra_id": 1, "cuotas": 1},
    ).to_list(200)
    # Also grab loanbooks by fecha_factura range (for newer records like LB-2026-0022)
    loanbooks_by_date = await db.loanbook.find(
        {"fecha_factura": {"$gte": fecha_inicio, "$lte": fecha_fin}},
        {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1, "plan": 1,
         "valor_cuota": 1, "cuota_inicial": 1, "precio_venta": 1,
         "estado": 1, "moto_chasis": 1, "factura_alegra_id": 1, "cuotas": 1},
    ).to_list(200)
    # Merge deduplicating by codigo
    seen_ids = {lb["id"] for lb in loanbooks_for_motos}
    loanbooks_mes = loanbooks_for_motos + [lb for lb in loanbooks_by_date if lb["id"] not in seen_ids]

    lb_by_chasis = {lb.get("moto_chasis"): lb for lb in loanbooks_mes if lb.get("moto_chasis")}
    lb_by_factura = {lb.get("factura_alegra_id"): lb for lb in loanbooks_mes if lb.get("factura_alegra_id")}

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total_motos = len(motos_mes)
    valor_facturado = sum(
        lb_by_chasis.get(m.get("chasis"), lb_by_factura.get(m.get("factura_alegra_id"), {})).get("precio_venta", 0) or 0
        for m in motos_mes
    )
    cuotas_iniciales_cobradas = sum(
        lb.get("cuota_inicial", 0) or 0
        for lb in loanbooks_mes
        if any(c.get("estado") == "pagada" and c.get("tipo") == "inicial"
               for c in lb.get("cuotas", []))
    )
    cuotas_iniciales_pendientes = sum(
        lb.get("cuota_inicial", 0) or 0
        for lb in loanbooks_mes
        if not any(c.get("estado") == "pagada" and c.get("tipo") == "inicial"
                   for c in lb.get("cuotas", []))
    )

    pct_meta = round(total_motos / META_MENSUAL * 100, 1) if META_MENSUAL else 0

    # ── Por modelo ────────────────────────────────────────────────────────────
    from collections import Counter
    modelos_counter: Counter = Counter()
    for m in motos_mes:
        modelo = (m.get("modelo") or "").upper()
        version = (m.get("version") or "").upper()
        color = (m.get("color") or "").strip()
        combined = f"{modelo} {version} {color}".upper()

        if "SPORT" in combined:
            label = "TVS Sport 100 ELS"
        elif "RAIDER" in combined:
            if "SLATE" in combined or "VERDE" in combined or "GREEN" in combined:
                label = "TVS Raider 125 Slate Green"
            elif "NEGRO" in combined or "NEBULOSA" in combined:
                label = "TVS Raider 125 Negro Nebulosa"
            else:
                label = f"TVS Raider 125 {color}".strip()
        else:
            label = f"{m.get('version') or m.get('modelo') or 'Otro'} {color}".strip()
        modelos_counter[label] += 1

    por_modelo = []
    for label, count in modelos_counter.most_common():
        pct = round(count / total_motos * 100, 1) if total_motos else 0
        por_modelo.append({"referencia": label, "unidades": count, "pct": pct})

    # Add zeros for models in catalog not yet sold
    known_refs = {p["referencia"] for p in por_modelo}
    catalogo_defaults = ["TVS Raider 125 Negro Nebulosa", "TVS Raider 125 Slate Green", "TVS Sport 100 ELS"]
    for ref in catalogo_defaults:
        if ref not in known_refs:
            por_modelo.append({"referencia": ref, "unidades": 0, "pct": 0.0})

    # ── Detalle de ventas ─────────────────────────────────────────────────────
    detalle = []
    for moto in motos_mes:
        chasis = moto.get("chasis", "")
        lb = lb_by_chasis.get(chasis) or lb_by_factura.get(moto.get("factura_alegra_id", "")) or {}
        version = (moto.get("version") or moto.get("modelo") or "").strip()
        color = (moto.get("color") or "").strip()
        ref_label = f"{version} {color}".strip() if color else version
        detalle.append({
            "cliente_nombre": lb.get("cliente_nombre") or moto.get("propietario", ""),
            "referencia": ref_label or "TVS",
            "vin": chasis,
            "plan": lb.get("plan"),
            "valor_cuota": lb.get("valor_cuota", 0),
            "estado_entrega": moto.get("estado", ""),
            "fecha_venta": moto.get("fecha_venta", ""),
            "loanbook_codigo": lb.get("codigo"),
            "loanbook_estado": lb.get("estado"),
        })

    # Sort by fecha_venta DESC
    detalle.sort(key=lambda x: x.get("fecha_venta", ""), reverse=True)

    # ── Mes anterior (comparativo) ────────────────────────────────────────────
    try:
        prev_year, prev_month = int(prev_mes[:4]), int(prev_mes[5:7])
        prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
        motos_mes_anterior = await db.inventario_motos.count_documents({
            "estado": {"$in": ["Vendida", "Entregada"]},
            "fecha_venta": {"$gte": f"{prev_mes}-01", "$lte": f"{prev_mes}-{str(prev_last_day).zfill(2)}"},
        })
    except Exception:
        motos_mes_anterior = 0

    mes_labels = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
    }
    mes_actual_label = f"{mes_labels[str(month).zfill(2)]} {year}"
    prev_month_label = f"{mes_labels[str((month - 1) or 12).zfill(2)]} {year if month > 1 else year - 1}"

    delta = total_motos - motos_mes_anterior

    return {
        "mes": mes,
        "mes_label": mes_actual_label,
        "kpis": {
            "total_motos": total_motos,
            "meta_mensual": META_MENSUAL,
            "pct_meta": pct_meta,
            "valor_facturado": valor_facturado,
            "cuotas_iniciales_cobradas": cuotas_iniciales_cobradas,
            "cuotas_iniciales_pendientes": cuotas_iniciales_pendientes,
            "creditos_nuevos": len(loanbooks_mes),
        },
        "por_modelo": por_modelo,
        "detalle": detalle,
        "comparativo": {
            "mes_actual": {"mes": mes_actual_label, "ventas": total_motos},
            "mes_anterior": {"mes": prev_month_label, "ventas": motos_mes_anterior},
            "delta": delta,
            "tendencia": "sube" if delta > 0 else "baja" if delta < 0 else "igual",
        },
    }
