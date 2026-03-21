"""
Endpoints para diagnóstico de datos de loanbooks y motos.
Útil para identificar problemas con entregas pendientes.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

from database import db
from dependencies import require_admin

router = APIRouter(prefix="/diagnostico", tags=["diagnostico"])
logger = logging.getLogger(__name__)


class DiagnosticoLoanbook(BaseModel):
    """Resultado del diagnóstico de un loanbook."""
    codigo: str
    id: str
    cliente_nombre: str
    moto_chasis: str | None
    campos_completos: bool
    campos_faltantes: List[str]
    moto_encontrada: bool
    problemas: List[str]


@router.get("/loanbooks-pendiente-entrega")
async def diagnostico_loanbooks_pendiente(current_user=Depends(require_admin)):
    """
    Diagnóstico de loanbooks en estado pendiente_entrega.

    Retorna para cada loanbook:
    - Información básica (código, cliente, chasis)
    - Campos faltantes o nulos
    - Verificación de moto en inventario
    - Qué falta para poder procesar la entrega
    """
    try:
        # 1. Consultar loanbooks pendiente_entrega
        loanbooks = await db.loanbook.find(
            {"estado": "pendiente_entrega"},
            {
                "_id": 0,
                "id": 1,
                "codigo": 1,
                "cliente_nombre": 1,
                "cliente_nit": 1,
                "moto_chasis": 1,
                "motor": 1,
                "plan": 1,
                "cuota_inicial": 1,
                "valor_cuota": 1,
                "cuota_base": 1,
                "precio_venta": 1,
                "factura_alegra_id": 1,
                "moto_id": 1,
                "created_at": 1,
            }
        ).to_list(None)

        # 2. Consultar motos Vendidas
        motos = await db.inventario_motos.find(
            {"estado": {"$in": ["Vendida", "vendida"]}},
            {
                "_id": 0,
                "id": 1,
                "chasis": 1,
                "modelo": 1,
                "estado": 1,
                "factura_alegra_id": 1,
            }
        ).to_list(None)

        # 3. Crear mapa de motos por chasis
        motos_por_chasis = {m.get("chasis"): m for m in motos}

        # 4. Analizar cada loanbook
        resultados = []
        problemas_globales = []

        campos_requeridos = {
            'cliente_nit': 'NIT del cliente',
            'moto_chasis': 'Chasis de la moto',
            'motor': 'Motor',
            'plan': 'Plan de cuotas',
            'cuota_inicial': 'Cuota inicial',
            'valor_cuota': 'Valor de cuota',
            'precio_venta': 'Precio de venta',
        }

        for lb in loanbooks:
            campos_faltantes = []
            problemas = []
            chasis = lb.get('moto_chasis')

            # Verificar campos requeridos
            for campo, descripcion in campos_requeridos.items():
                valor = lb.get(campo)
                if valor is None or valor == "" or valor == 0:
                    campos_faltantes.append(f"{campo} ({descripcion})")

            # Verificar moto
            moto_encontrada = False
            if not chasis:
                problemas.append("Chasis no registrado — No se puede verificar moto")
            else:
                moto = motos_por_chasis.get(chasis)
                if moto:
                    moto_encontrada = True
                else:
                    problemas.append(f"Moto con chasis {chasis} no existe en inventario")

            # Verificar si está listo para entrega
            if campos_faltantes:
                problemas.append(f"Campos incompletos: {len(campos_faltantes)} faltantes")
            if not moto_encontrada and chasis:
                problemas.append("No puede entregarse sin moto validada")

            resultado = {
                "codigo": lb.get('codigo'),
                "id": lb.get('id'),
                "cliente_nombre": lb.get('cliente_nombre'),
                "moto_chasis": chasis,
                "motor": lb.get('motor'),
                "plan": lb.get('plan'),
                "cuota_inicial": lb.get('cuota_inicial'),
                "valor_cuota": lb.get('valor_cuota'),
                "precio_venta": lb.get('precio_venta'),
                "cliente_nit": lb.get('cliente_nit'),
                "factura_alegra_id": lb.get('factura_alegra_id'),
                "campos_completos": len(campos_faltantes) == 0,
                "campos_faltantes": campos_faltantes,
                "moto_encontrada": moto_encontrada,
                "problemas": problemas,
                "listo_para_entrega": len(campos_faltantes) == 0 and moto_encontrada,
            }

            resultados.append(resultado)

            if problemas:
                problemas_globales.append({
                    "codigo": lb.get('codigo'),
                    "problemas": problemas
                })

        # Retornar resultados
        return {
            "total_pendiente_entrega": len(loanbooks),
            "total_motos_vendidas": len(motos),
            "loanbooks_listos": sum(1 for r in resultados if r["listo_para_entrega"]),
            "loanbooks_con_problemas": len(problemas_globales),
            "detalles": resultados,
            "resumen_problemas": problemas_globales,
        }

    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/inventario-vendidas")
async def diagnostico_inventario_vendidas(current_user=Depends(require_admin)):
    """
    Lista todas las motos con estado "Vendida" o "vendida" en inventario.
    Útil para cruzar con loanbooks.
    """
    try:
        motos = await db.inventario_motos.find(
            {"estado": {"$in": ["Vendida", "vendida"]}},
            {
                "_id": 0,
                "id": 1,
                "chasis": 1,
                "modelo": 1,
                "marca": 1,
                "estado": 1,
                "factura_alegra_id": 1,
                "VIN": 1,
                "motor": 1,
                "valor_compra": 1,
                "valor_venta": 1,
            }
        ).to_list(None)

        return {
            "total_vendidas": len(motos),
            "motos": motos,
        }

    except Exception as e:
        logger.error(f"Error listando motos vendidas: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/cartera-gestiones")
async def diagnostico_cartera_gestiones(current_user=Depends(require_admin)):
    """
    Diagnostico de la colección cartera_gestiones.
    Muestra si hay gestiones registradas (necesarias para RADAR).
    """
    try:
        total_gestiones = await db.cartera_gestiones.count_documents({})

        # Agrupar por loanbook_id para ver cobertura
        gestiones_por_loanbook = await db.cartera_gestiones.aggregate([
            {
                "$group": {
                    "_id": "$loanbook_id",
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}}
        ]).to_list(None)

        # Obtener loanbooks activos
        loanbooks_activos = await db.loanbook.count_documents(
            {"estado": {"$in": ["activo", "mora"]}}
        )

        loanbooks_con_gestiones = len(gestiones_por_loanbook)

        return {
            "total_gestiones": total_gestiones,
            "loanbooks_activos": loanbooks_activos,
            "loanbooks_con_gestiones": loanbooks_con_gestiones,
            "cobertura": f"{round(loanbooks_con_gestiones / loanbooks_activos * 100, 1)}%" if loanbooks_activos > 0 else "N/A",
            "gesiones_por_loanbook": gestiones_por_loanbook[:10],  # Top 10
            "estado": "OK" if total_gestiones > 0 else "SIN DATOS - RADAR VACIO"
        }

    except Exception as e:
        logger.error(f"Error en diagnóstico de gestiones: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
