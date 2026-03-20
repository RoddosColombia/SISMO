#!/usr/bin/env python3
"""
TAREA URGENTE — Sincronizar moto facturada en Alegra
Ejecutar contra base de datos remota en Render o local
"""

import asyncio
import uuid
from datetime import datetime, timezone
import os
import sys

# Intenta diferentes formas de obtener MongoDB
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    print("❌ Motor no está instalado. Instalando...")
    os.system("pip install motor")
    from motor.motor_asyncio import AsyncIOMotorClient

async def sincronizar_moto():
    """Sincronizar moto facturada en Alegra."""

    # Valores fijos para esta tarea
    chasis = "9FL25AF31VDB95190"
    factura_id = "FE456"
    cliente = "KEDWYNG VALLADARES"
    fecha_hoy = datetime.now(timezone.utc).isoformat()

    # Intentar conectar a MongoDB remota (Render)
    # Si la URL no está disponible, usar local
    mongodb_urls = [
        os.environ.get("MONGODB_URL"),
        os.environ.get("DB_URI"),
        "mongodb+srv://user:pass@cluster.mongodb.net/roddos",  # Placeholder
        "mongodb://localhost:27017",
    ]

    client = None
    db = None

    for url in mongodb_urls:
        if not url or url.startswith("mongodb+srv"):
            continue
        try:
            print(f"Intentando conectar a: {url[:40]}...")
            client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
            # Intentar conectar
            await client.admin.command("ping")
            db = client["roddos"]
            print(f"✓ Conectado exitosamente\n")
            break
        except Exception as e:
            print(f"✗ Conexión fallida: {str(e)[:60]}")
            continue

    if not db:
        print("\n" + "="*80)
        print("❌ NO SE PUDO CONECTAR A MONGODB")
        print("="*80)
        print("\nPara ejecutar esta sincronización, necesitas:")
        print("1. MongoDB corriendo localmente en localhost:27017, O")
        print("2. Configurar MONGODB_URL en variables de entorno")
        print("\nAlternativa: Usar la API REST directamente")
        print("POST http://localhost:8000/api/conciliacion/sync-manual")
        sys.exit(1)

    try:
        print("="*80)
        print("TAREA URGENTE — SINCRONIZAR MOTO FACTURADA EN ALEGRA")
        print("="*80)

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 1: Buscar moto
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 1] Buscando moto en inventario_motos...")
        print(f"  Chasis: {chasis}")

        moto = await db.inventario_motos.find_one({"chasis": chasis})

        if not moto:
            print(f"\n  ❌ ERROR: Moto no encontrada")
            print(f"  Buscando en MongoDB:")
            count = await db.inventario_motos.count_documents({})
            print(f"  Total de motos en inventario: {count}")

            # Listar las primeras 5 motos para debugging
            motos = await db.inventario_motos.find({}).limit(5).to_list(5)
            if motos:
                print(f"\n  Primeras motos registradas:")
                for m in motos:
                    print(f"    - {m.get('id')}: {m.get('modelo')} (chasis: {m.get('chasis', 'N/A')})")
            return

        print(f"  ✓ Moto encontrada:")
        print(f"    - ID: {moto.get('id')}")
        print(f"    - Chasis: {moto.get('chasis')}")
        print(f"    - Modelo: {moto.get('modelo')}")
        print(f"    - Estado actual: {moto.get('estado')}")
        print(f"    - Precio: ${moto.get('precio', 'N/A')}")

        estado_antes = {
            "id": moto.get("id"),
            "estado": moto.get("estado"),
            "factura_alegra_id": moto.get("factura_alegra_id"),
            "propietario": moto.get("propietario"),
        }

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 2: Actualizar estado
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 2] Actualizando estado a 'Vendida'...")

        if moto.get("estado") == "Vendida":
            print(f"  ⚠️  Ya estaba marcada como Vendida")
            print(f"     Factura anterior: {moto.get('factura_alegra_id')}")
            print(f"     Actualizar con nueva información...")

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

        print(f"  ✓ Documentos modificados: {update_result.modified_count}")

        moto_updated = await db.inventario_motos.find_one({"chasis": chasis})
        estado_despues = {
            "id": moto_updated.get("id"),
            "estado": moto_updated.get("estado"),
            "factura_alegra_id": moto_updated.get("factura_alegra_id"),
            "propietario": moto_updated.get("propietario"),
            "fecha_venta": moto_updated.get("fecha_venta"),
        }

        print(f"\n  Estado después:")
        print(f"    - Estado: {estado_despues['estado']}")
        print(f"    - Factura: {estado_despues['factura_alegra_id']}")
        print(f"    - Propietario: {estado_despues['propietario']}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 3: Crear/Verificar loanbook
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 3] Verificando/Creando loanbook...")

        loanbook = await db.loanbook.find_one({"moto_chasis": chasis})
        loanbook_id = None
        codigo_lb = None

        if loanbook:
            print(f"  ✓ Loanbook ya existe")
            print(f"    - ID: {loanbook.get('id')}")
            print(f"    - Código: {loanbook.get('codigo')}")
            loanbook_id = loanbook.get("id")
            codigo_lb = loanbook.get("codigo")
        else:
            print(f"  Creando nuevo loanbook...")

            # Generar código LB-2026-XXXX
            ultimo = await db.loanbook.find_one(
                {"codigo": {"$regex": "^LB-2026-"}},
                sort=[("codigo", -1)]
            )

            if ultimo and ultimo.get("codigo"):
                codigo_str = ultimo["codigo"].split("-")[-1]
                try:
                    num = int(codigo_str)
                    nuevo_num = num + 1
                except:
                    nuevo_num = 1
            else:
                nuevo_num = 1

            codigo_lb = f"LB-2026-{nuevo_num:04d}"
            loanbook_id = str(uuid.uuid4())

            nuevo_loanbook = {
                "id": loanbook_id,
                "codigo": codigo_lb,
                "estado": "pendiente_entrega",
                "moto_chasis": chasis,
                "factura_alegra_id": factura_id,
                "cliente_nombre": cliente,
                "created_at": fecha_hoy,
                "updated_at": fecha_hoy,
                "created_by": "sync_manual_urgente",
            }

            await db.loanbook.insert_one(nuevo_loanbook)

            print(f"  ✓ Loanbook creado")
            print(f"    - ID: {loanbook_id}")
            print(f"    - Código: {codigo_lb}")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 4: Publicar evento
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

        await db.roddos_events.insert_one(evento)
        print(f"  ✓ Evento publicado")

        # ════════════════════════════════════════════════════════════════════════════════
        # PASO 5: Invalidar caché
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n[PASO 5] Invalidando cfo_cache...")

        cache_result = await db.cfo_cache.update_many(
            {},
            {"$set": {"invalidated_at": fecha_hoy, "is_valid": False}}
        )

        print(f"  ✓ Cache invalidado ({cache_result.modified_count} documentos)")

        # ════════════════════════════════════════════════════════════════════════════════
        # REPORTE FINAL
        # ════════════════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("✅ SINCRONIZACIÓN COMPLETADA EXITOSAMENTE")
        print("="*80)

        print("\n📊 ESTADO INVENTARIO_MOTOS:")
        print("\n  ANTES:")
        print(f"    Estado: {estado_antes['estado']}")
        print(f"    Factura: {estado_antes.get('factura_alegra_id', 'Sin asignar')}")
        print(f"    Propietario: {estado_antes.get('propietario', 'Sin asignar')}")

        print("\n  DESPUÉS:")
        print(f"    Estado: {estado_despues['estado']}")
        print(f"    Factura: {estado_despues['factura_alegra_id']}")
        print(f"    Propietario: {estado_despues['propietario']}")
        print(f"    Fecha Venta: {estado_despues['fecha_venta']}")

        print(f"\n📦 LOANBOOK CREADO/VERIFICADO:")
        print(f"    ID: {loanbook_id}")
        print(f"    Código: {codigo_lb}")
        print(f"    Estado: pendiente_entrega")

        print(f"\n🎯 INFORMACIÓN SINCRONIZADA:")
        print(f"    Chasis: {chasis}")
        print(f"    Cliente: {cliente}")
        print(f"    Factura Alegra: {factura_id}")
        print(f"    Timestamp: {fecha_hoy}")

        print("\n" + "="*80 + "\n")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    asyncio.run(sincronizar_moto())
