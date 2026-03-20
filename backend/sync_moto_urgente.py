#!/usr/bin/env python3
"""
TAREA URGENTE — Sincronizar moto facturada en Alegra
Moto: 9FL25AF31VDB95190
Factura: FE456
Cliente: KEDWYNG VALLADARES
"""

import asyncio
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "roddos")

async def sincronizar_moto_urgente():
    """Sincronizar moto facturada en Alegra."""

    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DB_NAME]

    try:
        print("\n" + "="*80)
        print("TAREA URGENTE — SINCRONIZAR MOTO FACTURADA EN ALEGRA")
        print("="*80)

        chasis = "9FL25AF31VDB95190"
        factura_id = "FE456"
        cliente = "KEDWYNG VALLADARES"
        fecha_hoy = datetime.now(timezone.utc).isoformat()

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 1: Buscar moto en inventario_motos
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 1] Buscando moto en inventario_motos...")
        print(f"  Chasis: {chasis}")

        moto = await db.inventario_motos.find_one({"chasis": chasis})

        if not moto:
            print(f"  ❌ ERROR: Moto no encontrada en inventario_motos")
            return

        print(f"  ✓ Moto encontrada:")
        print(f"    - ID: {moto.get('id')}")
        print(f"    - Chasis: {moto.get('chasis')}")
        print(f"    - Estado actual: {moto.get('estado')}")
        print(f"    - Modelo: {moto.get('modelo')}")
        print(f"    - Precio: ${moto.get('precio', 'N/A'):,}")

        estado_antes = {
            "id": moto.get("id"),
            "estado": moto.get("estado"),
            "factura_alegra_id": moto.get("factura_alegra_id"),
            "propietario": moto.get("propietario"),
        }

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 2: Actualizar estado a "Vendida"
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 2] Actualizando estado a 'Vendida'...")

        if moto.get("estado") == "Vendida":
            print(f"  ⚠️  ADVERTENCIA: Moto ya está marcada como 'Vendida'")
            print(f"     Factura anterior: {moto.get('factura_alegra_id')}")
            print(f"     Propietario anterior: {moto.get('propietario')}")
            print(f"     Procediendo a actualizar con nueva información...")

        update_result = await db.inventario_motos.update_one(
            {"chasis": chasis},
            {
                "$set": {
                    "estado": "Vendida",
                    "factura_alegra_id": factura_id,
                    "fecha_venta": fecha_hoy,
                    "propietario": cliente,
                    "updated_at": fecha_hoy,
                    "updated_by": "sync_manual_urgente",
                }
            }
        )

        if update_result.modified_count == 1:
            print(f"  ✓ Inventario actualizado exitosamente")
        else:
            print(f"  ⚠️  No se realizaron cambios (documento ya tenía estos valores)")

        # Verificar estado después
        moto_updated = await db.inventario_motos.find_one({"chasis": chasis})
        estado_despues = {
            "id": moto_updated.get("id"),
            "estado": moto_updated.get("estado"),
            "factura_alegra_id": moto_updated.get("factura_alegra_id"),
            "propietario": moto_updated.get("propietario"),
            "fecha_venta": moto_updated.get("fecha_venta"),
        }

        print(f"\n  Estado después de actualización:")
        print(f"    - Estado: {estado_despues['estado']}")
        print(f"    - Factura: {estado_despues['factura_alegra_id']}")
        print(f"    - Propietario: {estado_despues['propietario']}")
        print(f"    - Fecha venta: {estado_despues['fecha_venta']}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 3: Verificar/Crear loanbook
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 3] Verificando/Creando loanbook...")

        loanbook = await db.loanbook.find_one({"moto_chasis": chasis})

        if loanbook:
            print(f"  ✓ Loanbook ya existe:")
            print(f"    - ID: {loanbook.get('id')}")
            print(f"    - Estado: {loanbook.get('estado')}")
            print(f"    - Cliente: {loanbook.get('cliente_nombre')}")
            loanbook_id = loanbook.get("id")
        else:
            print(f"  ℹ️  Loanbook no existe. Creando nuevo documento...")

            # Generar código LB-2026-XXXX
            # Buscar el número más alto existente
            ultimo = await db.loanbook.find_one(
                {"codigo": {"$regex": "^LB-2026-"}},
                sort=[("codigo", -1)]
            )

            if ultimo and ultimo.get("codigo"):
                # Extraer número y incrementar
                codigo_str = ultimo["codigo"].split("-")[-1]
                try:
                    num = int(codigo_str)
                    nuevo_num = num + 1
                except:
                    nuevo_num = 1
            else:
                nuevo_num = 1

            codigo = f"LB-2026-{nuevo_num:04d}"
            loanbook_id = str(uuid.uuid4())

            nuevo_loanbook = {
                "id": loanbook_id,
                "codigo": codigo,
                "estado": "pendiente_entrega",
                "moto_chasis": chasis,
                "factura_alegra_id": factura_id,
                "cliente_nombre": cliente,
                "created_at": fecha_hoy,
                "updated_at": fecha_hoy,
                "created_by": "sync_manual_urgente",
            }

            insert_result = await db.loanbook.insert_one(nuevo_loanbook)

            print(f"  ✓ Loanbook creado exitosamente:")
            print(f"    - ID: {loanbook_id}")
            print(f"    - Código: {codigo}")
            print(f"    - Estado: pendiente_entrega")
            print(f"    - Chasis: {chasis}")
            print(f"    - Factura: {factura_id}")
            print(f"    - Cliente: {cliente}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 4: Publicar evento en roddos_events
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 4] Publicando evento en roddos_events...")

        evento = {
            "id": str(uuid.uuid4()),
            "event_type": "factura.venta.creada",
            "source": "sync_manual",
            "chasis": chasis,
            "factura_id": factura_id,
            "cliente": cliente,
            "loanbook_id": loanbook_id,
            "timestamp": fecha_hoy,
            "processed": True,
        }

        insert_evento = await db.roddos_events.insert_one(evento)

        print(f"  ✓ Evento publicado exitosamente:")
        print(f"    - Event Type: factura.venta.creada")
        print(f"    - Source: sync_manual")
        print(f"    - Chasis: {chasis}")
        print(f"    - Factura: {factura_id}")
        print(f"    - Timestamp: {fecha_hoy}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 5: Invalidar cfo_cache
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 5] Invalidando cfo_cache...")

        cache_result = await db.cfo_cache.update_many(
            {},
            {"$set": {"invalidated_at": fecha_hoy, "is_valid": False}}
        )

        print(f"  ✓ CFO cache invalidado:")
        print(f"    - Documentos actualizados: {cache_result.modified_count}")

        # ════════════════════════════════════════════════════════════════════════════════
        # REPORTE FINAL
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("REPORTE FINAL — SINCRONIZACIÓN COMPLETADA ✓")
        print("="*80)

        print("\n📊 ESTADO INVENTARIO:")
        print("\n  ANTES:")
        print(f"    - Estado: {estado_antes['estado']}")
        print(f"    - Factura: {estado_antes.get('factura_alegra_id', 'N/A')}")
        print(f"    - Propietario: {estado_antes.get('propietario', 'N/A')}")

        print("\n  DESPUÉS:")
        print(f"    - Estado: {estado_despues['estado']}")
        print(f"    - Factura: {estado_despues['factura_alegra_id']}")
        print(f"    - Propietario: {estado_despues['propietario']}")
        print(f"    - Fecha Venta: {estado_despues['fecha_venta']}")

        print(f"\n📦 LOANBOOK:")
        print(f"    - ID: {loanbook_id}")
        print(f"    - Código: {loanbook.get('codigo') if loanbook else codigo}")
        print(f"    - Estado: pendiente_entrega")

        print(f"\n✅ SINCRONIZACIÓN EXITOSA")
        print(f"\n  Moto {chasis}")
        print(f"  Cliente: {cliente}")
        print(f"  Factura: {factura_id}")
        print(f"  Timestamp: {fecha_hoy}")

        print("\n" + "="*80 + "\n")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(sincronizar_moto_urgente())
