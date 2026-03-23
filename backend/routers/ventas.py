"""ventas.py — Dashboard de ventas del mes para RODDOS."""
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from database import db
from dependencies import get_current_user
from alegra_service import AlegraService
from post_action_sync import post_action_sync
from routers.cfo import invalidar_cache_cfo

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


# ══════════════════════════════════════════════════════════════════════════════
# BUILD 23 — F6: FACTURACIÓN VENTA MOTOS
# ══════════════════════════════════════════════════════════════════════════════


class CrearFacturaVentaRequest(BaseModel):
    """Request schema for creating motorcycle sales invoice."""
    cliente_nombre: str
    cliente_nit: str
    cliente_telefono: str
    moto_chasis: str
    moto_motor: str
    plan: str  # P39S | P52S | P78S | Contado
    precio_venta: float
    cuota_inicial: float
    valor_cuota: float
    modo_pago: str  # semanal | quincenal | mensual
    fecha_venta: Optional[str] = None
    tipo_identificacion: Optional[str] = None  # CC | CE | PPT | PP; defaults to CC


@router.post("/crear-factura")
async def crear_factura_venta(
    payload: CrearFacturaVentaRequest,
    current_user=Depends(get_current_user),
):
    """
    CREATE motorcycle sales invoice → Alegra + inventory update + loanbook creation.

    Mandatory validations:
    - VIN and motor REQUIRED (HTTP 400 if missing)
    - Mutex: moto must be "Disponible" (HTTP 400 if already sold)
    - Client creation/lookup in Alegra
    - Product creation/lookup in Alegra
    - Invoice creation via POST /invoices with request_with_verify()
    - Inventory update: estado → "Vendida"
    - Loanbook creation: LB-{año}-{n:04d} in "pendiente_entrega"
    - roddos_events publication
    - post_action_sync() + invalidar_cache_cfo()
    """
    try:
        # ── VALIDATIONS ───────────────────────────────────────────────────────────
        # Mandatory: VIN and motor
        if not payload.moto_chasis or not payload.moto_chasis.strip():
            raise HTTPException(status_code=400, detail="VIN obligatorio para crear factura")
        if not payload.moto_motor or not payload.moto_motor.strip():
            raise HTTPException(status_code=400, detail="Motor obligatorio para crear factura")

        # Mandatory: client info
        if not payload.cliente_nombre or not payload.cliente_nombre.strip():
            raise HTTPException(status_code=400, detail="Nombre del cliente obligatorio")
        if not payload.cliente_nit or not payload.cliente_nit.strip():
            raise HTTPException(status_code=400, detail="NIT del cliente obligatorio")
        if not payload.cliente_telefono or not payload.cliente_telefono.strip():
            raise HTTPException(status_code=400, detail="Teléfono del cliente obligatorio")

        # Plan validation
        valid_plans = ["P39S", "P52S", "P78S", "Contado"]
        if payload.plan not in valid_plans:
            raise HTTPException(status_code=400, detail=f"Plan debe ser uno de: {valid_plans}")

        # Price validations
        if payload.precio_venta <= 0:
            raise HTTPException(status_code=400, detail="Precio de venta debe ser > 0")
        if payload.cuota_inicial < 0 or payload.cuota_inicial > payload.precio_venta:
            raise HTTPException(status_code=400, detail="Cuota inicial inválida")

        # ── MUTEX: Check moto exists and is Disponible ─────────────────────────────
        moto = await db.inventario_motos.find_one({"chasis": payload.moto_chasis.strip()})
        if not moto:
            raise HTTPException(status_code=400, detail=f"Moto VIN {payload.moto_chasis} no encontrada en inventario")

        if moto.get("estado") != "Disponible":
            raise HTTPException(
                status_code=400,
                detail=f"Moto en estado '{moto.get('estado')}' — no se puede vender. Debe estar Disponible."
            )

        # ── Set up Alegra service ─────────────────────────────────────────────────
        service = AlegraService(db)

        # ── Determine identification type ────────────────────────────────────────────
        tipo_id_map = {
            "colombiano": "CC",
            "extranjero_venezolano": "PPT",
            "extranjero_otro": "CE",
            "pasaporte": "PP"
        }

        # Use provided tipo_identificacion, map if needed, default to CC
        tipo_id_alegra = "CC"  # Default
        if payload.tipo_identificacion:
            # Check if it's a mapping key or direct Alegra type
            if payload.tipo_identificacion.lower() in tipo_id_map:
                tipo_id_alegra = tipo_id_map[payload.tipo_identificacion.lower()]
            elif payload.tipo_identificacion.upper() in ["CC", "CE", "PPT", "PP"]:
                tipo_id_alegra = payload.tipo_identificacion.upper()
            else:
                # Invalid type, log warning and use default
                logger.warning(f"[F6] Tipo de ID no reconocido: {payload.tipo_identificacion}, usando CC por defecto")
                tipo_id_alegra = "CC"

        logger.info(f"[F6] Tipo de identificación: {tipo_id_alegra}")

        # ── CREATE/LOOKUP CLIENT in Alegra ───────────────────────────────────────
        logger.info(f"[F6] Buscando cliente NIT {payload.cliente_nit} en Alegra...")
        try:
            client_lookup = await service.request(f"contacts/{payload.cliente_nit}", "GET")
            client_id = client_lookup.get("id")
            logger.info(f"[F6] Cliente encontrado en Alegra: ID {client_id}")
        except Exception as e:
            logger.info(f"[F6] Cliente no existe en Alegra, creando... ({str(e)[:50]})")
            client_payload = {
                "name": payload.cliente_nombre,
                "identification": payload.cliente_nit,
                "tipo_identificacion": tipo_id_alegra,
                "phone": payload.cliente_telefono,
                "type": "person"
            }
            client_response = await service.request("contacts", "POST", client_payload)
            client_id = client_response.get("id")
            if not client_id:
                raise HTTPException(status_code=500, detail="No se pudo crear cliente en Alegra")
            logger.info(f"[F6] Cliente creado en Alegra: ID {client_id}")

        # ── GET TAX ID (19% IVA) ──────────────────────────────────────────────────
        logger.info("[F6] Obteniendo Tax ID para IVA 19%...")
        tax_id = None
        try:
            taxes_response = await service.request("taxes", "GET")
            taxes = taxes_response if isinstance(taxes_response, list) else taxes_response.get("taxes", [])
            # Filter for 19% tax
            iva_19_taxes = [t for t in taxes if t.get("percentage") == 19 or t.get("name", "").lower().find("19") >= 0]
            if iva_19_taxes:
                tax_id = iva_19_taxes[0].get("id")
                logger.info(f"[F6] Tax ID encontrado: {tax_id}")
            else:
                logger.warning("[F6] No se encontró tax ID 19%, omitiendo de ítem")
        except Exception as e:
            logger.warning(f"[F6] Error obteniendo taxes: {str(e)[:100]}, continuando sin tax_id")

        # ── CREATE/LOOKUP PRODUCT in Alegra ───────────────────────────────────────
        modelo = moto.get("modelo", "Moto").upper()
        version = moto.get("version", "").upper()
        color = moto.get("color", "").strip()

        # Product name: "[Modelo] [Color]"
        product_name = f"{modelo} {version} {color}".strip() if version and color else f"{modelo} {color}".strip()

        # Product description: "[Modelo] [Color] - VIN: [chasis] / Motor: [motor]"
        product_description = f"[{modelo}] [{color}] - VIN: {payload.moto_chasis.strip()} / Motor: {payload.moto_motor.strip()}"

        logger.info(f"[F6] Buscando producto '{product_name}' en Alegra...")
        product_id = None
        try:
            products_response = await service.request("products", "GET")
            products = products_response if isinstance(products_response, list) else products_response.get("products", [])
            # Search for product by name
            matching_products = [p for p in products if p.get("name", "").lower() == product_name.lower()]
            if matching_products:
                product_id = matching_products[0].get("id")
                logger.info(f"[F6] Producto encontrado en Alegra: ID {product_id}")
        except Exception as e:
            logger.info(f"[F6] Error buscando productos: {str(e)[:50]}")

        # Create product if not found
        if not product_id:
            logger.info(f"[F6] Producto no existe, creando...")
            product_payload = {
                "name": product_name,
                "description": product_description,
                "price": payload.precio_venta
            }
            product_response = await service.request("products", "POST", product_payload)
            product_id = product_response.get("id")
            if not product_id:
                raise HTTPException(status_code=500, detail="No se pudo crear producto en Alegra")
            logger.info(f"[F6] Producto creado en Alegra: ID {product_id}")

        # ── CREATE INVOICE in Alegra ──────────────────────────────────────────────
        fecha_venta = payload.fecha_venta or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Build item with tax
        item = {
            "id": product_id,
            "name": product_name,
            "description": product_description,
            "price": payload.precio_venta,
            "quantity": 1
        }
        if tax_id:
            item["tax"] = [{"id": tax_id, "percentage": 19}]

        # Determine due date and payment form
        if payload.plan == "Contado":
            due_date = fecha_venta
            payment_form = "CASH"
        else:
            # For credit plans, set due date 30 days from now
            from datetime import timedelta
            future_date = datetime.fromisoformat(fecha_venta) + timedelta(days=30)
            due_date = future_date.strftime("%Y-%m-%d")
            payment_form = "CREDIT"

        invoice_payload = {
            "date": fecha_venta,
            "dueDate": due_date,
            "client": {"id": client_id},
            "items": [item],
            "paymentForm": payment_form,
            "observations": f"Venta a {payload.cliente_nombre}. Plan {payload.plan} - VIN: {payload.moto_chasis}"
        }

        logger.info(f"[F6] Creando factura en Alegra para cliente {client_id}...")
        invoice_response = await service.request_with_verify("invoices", "POST", invoice_payload)

        if not invoice_response.get("id"):
            raise HTTPException(status_code=500, detail="No se pudo crear factura en Alegra")

        invoice_id = invoice_response.get("id")
        invoice_number = invoice_response.get("number", invoice_id)
        logger.info(f"[F6] Factura creada en Alegra: {invoice_number} (ID: {invoice_id})")

        # ── UPDATE INVENTORY: moto estado → "Vendida" ─────────────────────────────
        logger.info(f"[F6] Actualizando inventario: VIN {payload.moto_chasis} → Vendida")
        await db.inventario_motos.update_one(
            {"chasis": payload.moto_chasis.strip()},
            {
                "$set": {
                    "estado": "Vendida",
                    "fecha_venta": fecha_venta,
                    "propietario": payload.cliente_nombre,
                    "factura_alegra_id": invoice_id,
                    "factura_numero": invoice_number,
                }
            }
        )

        # ── CREATE LOANBOOK ───────────────────────────────────────────────────────
        logger.info("[F6] Creando loanbook...")

        # Sequential numbering: count documents + 1, format LB-{año}-{n:04d}
        num_loanbooks = await db.loanbook.count_documents({})
        loanbook_num = num_loanbooks + 1
        current_year = datetime.now(timezone.utc).year
        loanbook_id = f"LB-{current_year}-{loanbook_num:04d}"
        loanbook_codigo = f"LB{loanbook_num:04d}"

        # Generate cuotas
        cuotas = []

        # Cuota inicial
        cuota_inicial = {
            "numero": 0,
            "valor": payload.cuota_inicial,
            "tipo": "inicial",
            "estado": "pendiente",
            "fecha_vencimiento": fecha_venta,
            "metodo_pago": payload.modo_pago
        }
        cuotas.append(cuota_inicial)

        # Cuotas ordinarias (if plan != Contado)
        if payload.plan != "Contado":
            plan_num_cuotas = {
                "P39S": 39,
                "P52S": 52,
                "P78S": 78,
            }
            num_cuotas = plan_num_cuotas.get(payload.plan, 0)

            if num_cuotas > 0 and payload.valor_cuota > 0:
                for i in range(1, num_cuotas + 1):
                    cuota = {
                        "numero": i,
                        "valor": payload.valor_cuota,
                        "tipo": "ordinaria",
                        "estado": "pendiente",
                        "fecha_vencimiento": None,  # Will be set during delivery registration
                        "metodo_pago": payload.modo_pago
                    }
                    cuotas.append(cuota)

        # Create loanbook document
        loanbook_doc = {
            "id": loanbook_id,
            "codigo": loanbook_codigo,
            "cliente_nombre": payload.cliente_nombre,
            "cliente_nit": payload.cliente_nit,
            "cliente_telefono": payload.cliente_telefono,
            "moto_chasis": payload.moto_chasis.strip(),
            "moto_motor": payload.moto_motor.strip(),
            "moto_descripcion": product_name,
            "plan": payload.plan,
            "fecha_factura": fecha_venta,
            "fecha_entrega": None,  # Set only during physical delivery registration
            "precio_venta": payload.precio_venta,
            "cuota_inicial": payload.cuota_inicial,
            "valor_cuota": payload.valor_cuota,
            "modo_pago": payload.modo_pago,
            "factura_alegra_id": invoice_id,
            "factura_numero": invoice_number,
            "estado": "pendiente_entrega",
            "datos_completos": True,
            "cuotas": cuotas,
            "dpd_actual": 0,
            "gestiones": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.loanbook.insert_one(loanbook_doc)
        logger.info(f"[F6] Loanbook creado: {loanbook_id}")

        # ── PUBLISH EVENT ─────────────────────────────────────────────────────────
        logger.info("[F6] Publicando evento factura.venta.creada...")
        event_doc = {
            "event_type": "factura.venta.creada",
            "factura_alegra_id": invoice_id,
            "factura_numero": invoice_number,
            "loanbook_id": loanbook_id,
            "cliente_nombre": payload.cliente_nombre,
            "cliente_nit": payload.cliente_nit,
            "moto_chasis": payload.moto_chasis.strip(),
            "moto_motor": payload.moto_motor.strip(),
            "precio_venta": payload.precio_venta,
            "plan": payload.plan,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }
        await db.roddos_events.insert_one(event_doc)

        # ── POST-ACTION SYNC & CACHE INVALIDATION ─────────────────────────────────
        logger.info("[F6] Sincronizando con post_action_sync()...")
        await post_action_sync(
            "crear_factura_venta",
            {"id": invoice_id, "number": invoice_number, "loanbook_id": loanbook_id},
            invoice_payload,
            db,
            current_user,
            metadata={"loanbook_id": loanbook_id, "moto_chasis": payload.moto_chasis}
        )

        logger.info("[F6] Invalidando CFO cache...")
        try:
            await invalidar_cache_cfo()
        except Exception as e:
            logger.warning(f"[F6] Error invalidando CFO cache: {str(e)[:100]}")

        # ── RESPONSE ──────────────────────────────────────────────────────────────
        logger.info(f"[F6] ✅ Factura creada exitosamente: {invoice_number}")

        return {
            "success": True,
            "factura_alegra_id": invoice_id,
            "factura_numero": invoice_number,
            "loanbook_id": loanbook_id,
            "mensaje": f"✅ Factura creada en Alegra: {invoice_number}. Loanbook: {loanbook_id}",
            "datos": {
                "cliente_nombre": payload.cliente_nombre,
                "moto_chasis": payload.moto_chasis,
                "precio_venta": payload.precio_venta,
                "plan": payload.plan,
                "cuota_inicial": payload.cuota_inicial,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[F6] Error creando factura: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creando factura: {str(e)[:200]}")
