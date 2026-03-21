#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico de loanbooks en estado pendiente_entrega vs inventario_motos.
Se conecta a MongoDB Atlas sismo-prod usando variables de entorno.

Ejecución:
  cd backend
  python diagnostico_loanbooks_simple.py

Requiere variables de entorno:
  MONGO_URL: URI de conexión a MongoDB (mongodb+srv://...)
  DB_NAME: Nombre de la base de datos (default: sismo)
"""

import os
import sys
from typing import List, Dict, Any
from pymongo import MongoClient

def conectar_mongodb():
    """Conecta a MongoDB usando variables de entorno."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "sismo")

    if not mongo_url:
        print("ERROR: Variable MONGO_URL no configurada")
        print("\nPara ejecutar este diagnóstico:")
        print("  1. Ir a https://cloud.mongodb.com/")
        print("  2. Obtener connection string de la base de datos sismo-prod")
        print("  3. Ejecutar: export MONGO_URL='mongodb+srv://...'")
        print("  4. Ejecutar: python diagnostico_loanbooks_simple.py")
        sys.exit(1)

    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000, retryWrites=False)
        # Verificar conexión
        client.admin.command("ping")
        print("[+] Conectado a MongoDB Atlas — Base de datos: " + db_name)
        return client[db_name], client
    except Exception as e:
        print("[!] Error conectando a MongoDB: " + str(e)[:100])
        sys.exit(1)


def diagnosticar_loanbooks(db):
    """Ejecuta diagnóstico completo de loanbooks pendiente_entrega."""

    print("\n" + "="*80)
    print("DIAGNOSTICO: LOANBOOKS EN ESTADO PENDIENTE_ENTREGA")
    print("="*80)

    # 1. Consultar loanbooks pendiente_entrega
    print("\n[1/3] Consultando loanbooks en estado 'pendiente_entrega'...")
    loanbooks = list(db.loanbook.find(
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
    ))

    print("    Encontrados: " + str(len(loanbooks)) + " loanbooks pendiente_entrega\n")

    if not loanbooks:
        print("    INFO: No hay loanbooks en estado pendiente_entrega")
        return

    # 2. Consultar motos Vendidas
    print("[2/3] Consultando motos en estado 'Vendida' o 'vendida'...")
    motos = list(db.inventario_motos.find(
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
    ))

    print("    Encontradas: " + str(len(motos)) + " motos vendidas\n")

    # 3. Crear mapa de motos por chasis
    motos_por_chasis = {m.get("chasis"): m for m in motos}

    # 4. Analizar cada loanbook
    print("[3/3] Analizando loanbooks y cruzando con motos...\n")
    print("-" * 80)

    problemas_encontrados = []

    for i, lb in enumerate(loanbooks, 1):
        print("\nLOANBOOK #" + str(i))
        print("   Codigo: " + str(lb.get('codigo', 'N/A')))
        print("   ID: " + str(lb.get('id', 'N/A')))
        print("   Cliente: " + str(lb.get('cliente_nombre', 'N/A')))
        print("   Fecha creacion: " + str(lb.get('created_at', 'N/A')[:10] if lb.get('created_at') else 'N/A'))

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
                campos_faltantes.append("    [X] " + campo.ljust(20) + " -> " + descripcion.ljust(25) + " [FALTA]")
            else:
                campos_faltantes.append("    [OK] " + campo.ljust(20) + " -> " + str(valor))

        print("\n    Campos requeridos:")
        for campo_info in campos_faltantes:
            print(campo_info)

        # Verificar moto
        chasis = valores.get('moto_chasis')
        print("\n    Verificacion de moto:")
        if not chasis:
            print("    [X] No hay chasis registrado — No se puede verificar moto")
            problemas_encontrados.append({
                'codigo': lb.get('codigo'),
                'problema': 'Chasis no registrado',
                'resolucion': 'Ingresar chasis de la moto'
            })
        else:
            moto = motos_por_chasis.get(chasis)
            if moto:
                print("    [OK] Moto encontrada en inventario")
                print("        - Modelo: " + str(moto.get('modelo', 'N/A')))
                print("        - Estado: " + str(moto.get('estado', 'N/A')))
                print("        - Factura Alegra: " + str(moto.get('factura_alegra_id', 'N/A')))
            else:
                print("    [X] Moto NO encontrada con chasis: " + str(chasis))
                problemas_encontrados.append({
                    'codigo': lb.get('codigo'),
                    'problema': 'Moto con chasis ' + str(chasis) + ' no existe en inventario',
                    'resolucion': 'Verificar chasis o crear moto en inventario'
                })

        # Resumen de obstáculos para entrega
        print("\n    Estado para entrega:")
        obstaculos = []

        for campo in ['cliente_nit', 'moto_chasis', 'plan', 'valor_cuota']:
            if not valores.get(campo):
                obstaculos.append(campo)

        if obstaculos:
            print("    [X] Tiene " + str(len(obstaculos)) + " campos faltantes — NO PUEDE ENTREGARSE")
            problemas_encontrados.append({
                'codigo': lb.get('codigo'),
                'problema': 'Campos faltantes: ' + ", ".join(obstaculos),
                'resolucion': 'Completar informacion antes de entregar'
            })
        elif not motos_por_chasis.get(chasis):
            print("    [X] Moto no existe en inventario — NO PUEDE ENTREGARSE")
        else:
            print("    [OK] Todos los campos completos — LISTO PARA ENTREGAR")

        print("-" * 80)

    # 5. Resumen de problemas
    print("\n\n" + "="*80)
    print("RESUMEN DE PROBLEMAS")
    print("="*80)

    if problemas_encontrados:
        print("\n[!] Total de problemas encontrados: " + str(len(problemas_encontrados)) + "\n")
        for i, p in enumerate(problemas_encontrados, 1):
            print(str(i) + ". " + str(p['codigo']))
            print("   Problema: " + str(p['problema']))
            print("   Resolucion: " + str(p['resolucion']))
            print()
    else:
        print("\n[+] No hay problemas — Todos los loanbooks estan listos para entregar\n")

    # 6. Estadísticas
    print("="*80)
    print("ESTADISTICAS")
    print("="*80)

    listos = len(loanbooks) - len([p for p in problemas_encontrados])
    print("\nLoanbooks por estado:")
    print("  - Total pendiente_entrega: " + str(len(loanbooks)))
    print("  - Listos para entregar: " + str(listos))
    print("  - Con problemas: " + str(len(problemas_encontrados)))

    # Problemas más frecuentes
    if problemas_encontrados:
        print("\nProblemas mas frecuentes:")
        problemas_tipos = {}
        for p in problemas_encontrados:
            tipo = p['problema'].split(':')[0]
            problemas_tipos[tipo] = problemas_tipos.get(tipo, 0) + 1

        for tipo, count in sorted(problemas_tipos.items(), key=lambda x: -x[1]):
            print("  - " + str(tipo) + ": " + str(count) + " loanbook(s)")

    print("\n" + "="*80)


def main():
    """Punto de entrada."""
    db, client = conectar_mongodb()
    try:
        diagnosticar_loanbooks(db)
    finally:
        # Cerrar conexión
        client.close()
        print("\n[+] Conexion cerrada")


if __name__ == "__main__":
    main()
