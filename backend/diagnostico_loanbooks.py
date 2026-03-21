#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico de loanbooks en estado pendiente_entrega vs inventario_motos.
Se conecta a MongoDB Atlas sismo-prod usando variables de entorno.
"""

import os
import sys
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Configurar encoding UTF-8 para Windows
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cargar variables de entorno
backend_dir = Path(__file__).parent
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)

async def diagnosticar_loanbooks(db) -> None:
    """Ejecuta diagnóstico completo de loanbooks pendiente_entrega."""

    print("\n" + "="*80)
    print("DIAGNÓSTICO: LOANBOOKS EN ESTADO PENDIENTE_ENTREGA")
    print("="*80)

    # 1. Consultar loanbooks pendiente_entrega
    print("\n[1/3] Consultando loanbooks en estado 'pendiente_entrega'...")
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

    print(f"   ✓ Encontrados: {len(loanbooks)} loanbooks pendiente_entrega\n")

    if not loanbooks:
        print("   ℹ️  No hay loanbooks en estado pendiente_entrega")
        return

    # 2. Consultar motos Vendidas
    print("[2/3] Consultando motos en estado 'Vendida' o 'vendida'...")
    motos = await db.inventario_motos.find(
        {"estado": {"$in": ["Vendida", "vendida"]}},
        {
            "_id": 0,
            "id": 1,
            "chasis": 1,
            "modelo": 1,
            "estado": 1,
            "factura_alegra_id": 1,
            "VIN": 1,
        }
    ).to_list(None)

    print(f"   ✓ Encontradas: {len(motos)} motos vendidas\n")

    # 3. Crear mapa de motos por chasis
    motos_por_chasis = {m.get("chasis"): m for m in motos}

    # 4. Analizar cada loanbook
    print("[3/3] Analizando loanbooks y cruzando con motos...\n")
    print("-" * 80)

    problemas_encontrados = []

    for i, lb in enumerate(loanbooks, 1):
        print(f"\n📋 LOANBOOK #{i}")
        print(f"   Código: {lb.get('codigo', 'N/A')}")
        print(f"   ID: {lb.get('id', 'N/A')}")
        print(f"   Cliente: {lb.get('cliente_nombre', 'N/A')}")
        print(f"   Fecha creación: {lb.get('created_at', 'N/A')[:10] if lb.get('created_at') else 'N/A'}")

        campos_requeridos = {
            'cliente_nit': 'NIT del cliente',
            'moto_chasis': 'Chasis de la moto',
            'motor': 'Motor',
            'plan': 'Plan de cuotas',
            'cuota_inicial': 'Cuota inicial',
            'valor_cuota': 'Valor de cuota',
            'precio_venta': 'Precio de venta',
        }

        campos_faltantes = []
        valores = {}

        for campo, descripcion in campos_requeridos.items():
            valor = lb.get(campo)
            valores[campo] = valor

            # Verificar si está faltando o es null/vacío
            if valor is None or valor == "" or valor == 0:
                campos_faltantes.append(f"  ❌ {campo:20} → {descripcion:25} [FALTA]")
            else:
                campos_faltantes.append(f"  ✅ {campo:20} → {valor}")

        print("\n   Campos requeridos:")
        for campo_info in campos_faltantes:
            print(campo_info)

        # Verificar moto
        chasis = valores.get('moto_chasis')
        print(f"\n   Verificación de moto:")
        if not chasis:
            print(f"  ❌ No hay chasis registrado — No se puede verificar moto")
            problemas_encontrados.append({
                'codigo': lb.get('codigo'),
                'problema': 'Chasis no registrado',
                'resolucion': 'Ingresar chasis de la moto'
            })
        else:
            moto = motos_por_chasis.get(chasis)
            if moto:
                print(f"  ✅ Moto encontrada en inventario")
                print(f"     • Modelo: {moto.get('modelo', 'N/A')}")
                print(f"     • Estado: {moto.get('estado', 'N/A')}")
                print(f"     • Factura Alegra: {moto.get('factura_alegra_id', 'N/A')}")
            else:
                print(f"  ❌ Moto NO encontrada con chasis: {chasis}")
                problemas_encontrados.append({
                    'codigo': lb.get('codigo'),
                    'problema': f'Moto con chasis {chasis} no existe en inventario',
                    'resolucion': 'Verificar chasis o crear moto en inventario'
                })

        # Resumen de obstáculos para entrega
        print(f"\n   Estado para entrega:")
        obstaculos = []

        for campo in ['cliente_nit', 'moto_chasis', 'plan', 'valor_cuota']:
            if not valores.get(campo):
                obstaculos.append(campo)

        if obstaculos:
            print(f"  ❌ Tiene {len(obstaculos)} campos faltantes — NO PUEDE ENTREGARSE")
            problemas_encontrados.append({
                'codigo': lb.get('codigo'),
                'problema': f'Campos faltantes: {", ".join(obstaculos)}',
                'resolucion': 'Completar información antes de entregar'
            })
        elif not motos_por_chasis.get(chasis):
            print(f"  ❌ Moto no existe en inventario — NO PUEDE ENTREGARSE")
        else:
            print(f"  ✅ Todos los campos completos — LISTO PARA ENTREGAR")

        print("-" * 80)

    # 5. Resumen de problemas
    print("\n\n" + "="*80)
    print("RESUMEN DE PROBLEMAS")
    print("="*80)

    if problemas_encontrados:
        print(f"\n🔴 Total de problemas encontrados: {len(problemas_encontrados)}\n")
        for i, p in enumerate(problemas_encontrados, 1):
            print(f"{i}. {p['codigo']}")
            print(f"   Problema: {p['problema']}")
            print(f"   Resolución: {p['resolucion']}")
            print()
    else:
        print("\n✅ No hay problemas — Todos los loanbooks están listos para entregar\n")

    # 6. Estadísticas
    print("="*80)
    print("ESTADÍSTICAS")
    print("="*80)

    listos = len(loanbooks) - len([p for p in problemas_encontrados])
    print(f"\nLoanbooks por estado:")
    print(f"  • Total pendiente_entrega: {len(loanbooks)}")
    print(f"  • Listos para entregar: {listos}")
    print(f"  • Con problemas: {len(problemas_encontrados)}")

    # Problemas más frecuentes
    if problemas_encontrados:
        print(f"\nProblemas más frecuentes:")
        problemas_tipos = {}
        for p in problemas_encontrados:
            tipo = p['problema'].split(':')[0]
            problemas_tipos[tipo] = problemas_tipos.get(tipo, 0) + 1

        for tipo, count in sorted(problemas_tipos.items(), key=lambda x: -x[1]):
            print(f"  • {tipo}: {count} loanbook(s)")

    print("\n" + "="*80)


async def main():
    """Punto de entrada."""
    client = None
    try:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "sismo")

        if not mongo_url:
            print("❌ ERROR: Variable MONGO_URL no configurada")
            sys.exit(1)

        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        await client.admin.command("ping")
        print(f"✅ Conectado a MongoDB Atlas — Base de datos: {db_name}")

        db = client[db_name]
        await diagnosticar_loanbooks(db)
    finally:
        # Cerrar conexión
        if client:
            client.close()
            print("\n✓ Conexión cerrada")


if __name__ == "__main__":
    asyncio.run(main())
