"""Taxes / IVA router — period configuration, IVA status, presets."""
from datetime import datetime, timezone, date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user, require_admin

router = APIRouter(prefix="/impuestos", tags=["taxes"])

DEFAULT_IVA_CONFIG = {
    "tipo_periodo": "cuatrimestral",
    "periodos": [
        {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
    ],
    "saldo_favor_dian": 0,
    "fecha_saldo_favor": None,
    "nota_saldo_favor": "",
}

PERIODO_PRESETS = {
    "bimestral": [
        {"nombre": "Ene–Feb", "inicio_mes": 1, "fin_mes": 2, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Mar–Abr", "inicio_mes": 3, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "May–Jun", "inicio_mes": 5, "fin_mes": 6, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Jul–Ago", "inicio_mes": 7, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Sep–Oct", "inicio_mes": 9, "fin_mes": 10, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Nov–Dic", "inicio_mes": 11, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
    ],
    "cuatrimestral": [
        {"nombre": "Ene–Abr", "inicio_mes": 1, "fin_mes": 4, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "May–Ago", "inicio_mes": 5, "fin_mes": 8, "dia_limite": 30, "mes_limite_offset": 1},
        {"nombre": "Sep–Dic", "inicio_mes": 9, "fin_mes": 12, "dia_limite": 30, "mes_limite_offset": 1},
    ],
    "anual": [
        {"nombre": "Ene–Dic", "inicio_mes": 1, "fin_mes": 12, "dia_limite": 31, "mes_limite_offset": 3},
    ],
}


@router.get("/config")
async def get_iva_config(current_user=Depends(get_current_user)):
    cfg = await db.iva_config.find_one({}, {"_id": 0})
    return cfg or DEFAULT_IVA_CONFIG


class IvaConfigRequest(BaseModel):
    tipo_periodo: str
    periodos: List[Any]
    saldo_favor_dian: float = 0
    fecha_saldo_favor: Optional[str] = None
    nota_saldo_favor: Optional[str] = ""


@router.post("/config")
async def save_iva_config(req: IvaConfigRequest, current_user=Depends(require_admin)):
    d = req.model_dump()
    d["updated_at"] = datetime.now(timezone.utc).isoformat()
    d["updated_by"] = current_user.get("email")
    await db.iva_config.update_one({}, {"$set": d}, upsert=True)
    return {"message": "Configuración IVA guardada"}


@router.get("/periodos-preset")
async def get_periodos_preset(current_user=Depends(get_current_user)):
    return PERIODO_PRESETS


@router.get("/iva-status")
async def get_iva_status(ano: int = None, current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    ano = ano or now.year
    mes_actual = now.month

    cfg = await db.iva_config.find_one({}, {"_id": 0}) or DEFAULT_IVA_CONFIG
    periodos = cfg.get("periodos", DEFAULT_IVA_CONFIG["periodos"])
    saldo_favor = float(cfg.get("saldo_favor_dian", 0))

    periodo_actual = next(
        (p for p in periodos if p["inicio_mes"] <= mes_actual <= p["fin_mes"]),
        periodos[-1],
    )

    inicio_mes = periodo_actual["inicio_mes"]
    fin_mes = periodo_actual["fin_mes"]
    date_start = f"{ano}-{str(inicio_mes).zfill(2)}-01"
    date_end = f"{ano}-{str(fin_mes).zfill(2)}-28"

    service = AlegraService(db)
    try:
        invoices = await service.request("invoices", params={"date_start": date_start, "date_end": date_end})
        bills = await service.request("bills", params={"date_start": date_start, "date_end": date_end})
    except Exception:
        invoices, bills = [], []

    invoices = invoices if isinstance(invoices, list) else []
    bills = bills if isinstance(bills, list) else []

    total_ventas = sum(float(inv.get("total") or 0) for inv in invoices)
    total_compras = sum(float(b.get("total") or 0) for b in bills)
    iva_cobrado = round(total_ventas / 1.19 * 0.19)
    iva_descontable = round(total_compras / 1.19 * 0.19)
    iva_bruto = max(0, iva_cobrado - iva_descontable)
    iva_pagar_neto = max(0, iva_bruto - saldo_favor)
    saldo_favor_restante = max(0, saldo_favor - iva_bruto)

    meses_periodo = fin_mes - inicio_mes + 1
    meses_transcurridos = max(1, mes_actual - inicio_mes + 1)
    factor = meses_periodo / meses_transcurridos
    iva_cobrado_proyectado = round(iva_cobrado * factor)
    iva_descontable_proyectado = round(iva_descontable * factor)
    iva_pagar_proyectado = max(0, round((iva_cobrado_proyectado - iva_descontable_proyectado) - saldo_favor))

    # ── ReteFuente praticada a proveedores en el período ─────────────────────
    # Aggregate retefuente from bill retentions, or estimate at 2.5% on qualifying purchases
    UVT_2025 = 49799
    BASE_MINIMA_COMPRAS = 27 * UVT_2025  # $1,344,573

    retefuente_total = 0.0
    retefuente_facturas = 0
    # Load autoretenedores to exclude them
    autoretenedores_docs = await db.proveedores_config.find(
        {"es_autoretenedor": True}, {"_id": 0, "nombre": 1, "nit": 1}
    ).to_list(100)
    autoret_names = {a["nombre"].lower() for a in autoretenedores_docs}
    autoret_nits = {a["nit"] for a in autoretenedores_docs if a.get("nit")}

    for bill in bills:
        proveedor_nombre = ""
        proveedor_nit = ""
        if isinstance(bill.get("vendor"), dict):
            proveedor_nombre = (bill["vendor"].get("name") or "").lower()
            proveedor_nit = bill["vendor"].get("identification", "")
        if proveedor_nombre in autoret_names or proveedor_nit in autoret_nits:
            continue  # skip autoretenedores

        subtotal = float(bill.get("subtotal") or bill.get("total") or 0) / 1.19  # excl IVA

        # Check if bill has retentions field (Alegra API)
        retentions = bill.get("retentions") or bill.get("taxes") or []
        bill_retefuente = 0.0
        if isinstance(retentions, list):
            for ret in retentions:
                if isinstance(ret, dict):
                    name_lower = (ret.get("name") or "").lower()
                    if "retefuente" in name_lower or "rete fuente" in name_lower or "retención en la fuente" in name_lower:
                        bill_retefuente += float(ret.get("value") or ret.get("amount") or 0)

        if bill_retefuente > 0:
            retefuente_total += bill_retefuente
            retefuente_facturas += 1
        elif subtotal >= BASE_MINIMA_COMPRAS:
            # Estimate at 2.5% if no retention data in API
            retefuente_total += round(subtotal * 0.025)
            retefuente_facturas += 1

    # ── ReteICA Bogotá (Industria y Comercio) ────────────────────────────────
    # RODDOS: comercio motos → tarifa 0.414% POR OPERACIÓN GRAVADA (no anual)
    RETICA_TARIFA = 0.00414  # 0.414% sobre el valor gravado de cada operación
    ingresos_gravables_ica = total_ventas / 1.19  # base sin IVA
    retica_acumulada = round(ingresos_gravables_ica * RETICA_TARIFA)
    # Proyección: si el período no ha terminado, estimar el total con factor proporcional
    retica_proyectada = round(ingresos_gravables_ica * RETICA_TARIFA * factor)

    mes_limite = fin_mes + periodo_actual.get("mes_limite_offset", 1)
    ano_limite = ano
    if mes_limite > 12:
        mes_limite -= 12
        ano_limite += 1
    dia_limite = periodo_actual.get("dia_limite", 30)
    fecha_limite = f"{ano_limite}-{str(mes_limite).zfill(2)}-{dia_limite}"
    try:
        hoy = date.today()
        limite = date.fromisoformat(fecha_limite)
        dias_restantes = (limite - hoy).days
    except Exception:
        dias_restantes = None

    pct_avance = round((meses_transcurridos / meses_periodo) * 100)

    return {
        "periodo": periodo_actual,
        "ano": ano,
        "date_start": date_start,
        "date_end": date_end,
        "mes_actual": mes_actual,
        "meses_transcurridos": meses_transcurridos,
        "meses_periodo": meses_periodo,
        "pct_avance": pct_avance,
        "fecha_limite": fecha_limite,
        "dias_restantes": dias_restantes,
        "facturas_venta": len(invoices),
        "facturas_compra": len(bills),
        "total_ventas": total_ventas,
        "total_compras": total_compras,
        "iva_cobrado": iva_cobrado,
        "iva_descontable": iva_descontable,
        "iva_bruto": iva_bruto,
        "saldo_favor_dian": saldo_favor,
        "iva_pagar_neto": iva_pagar_neto,
        "saldo_favor_restante": saldo_favor_restante,
        "proyeccion": {
            "iva_cobrado": iva_cobrado_proyectado,
            "iva_descontable": iva_descontable_proyectado,
            "iva_pagar": iva_pagar_proyectado,
        },
        "retefuente": {
            "acumulada": round(retefuente_total),
            "facturas_con_retencion": retefuente_facturas,
            "nota": "Retenciones practicadas a proveedores en el período (excluye autoretenedores)",
        },
        "retica": {
            "acumulada": retica_acumulada,
            "proyectada_periodo": retica_proyectada,
            "tarifa_pct": round(RETICA_TARIFA * 100, 3),
            "base_ingresos": round(ingresos_gravables_ica),
            "nota": "ReteICA Bogotá — 0.414% por operación gravada (comercio motos)",
        },
    }
