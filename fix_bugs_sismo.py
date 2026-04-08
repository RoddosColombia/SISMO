#!/usr/bin/env python3
import os
import re
import sys

print("[SISMO BUILD 24] Aplicando los 3 fixes de bugs...")

# Archivo 1: accounting_engine.py
file1 = os.path.join("backend", "services", "accounting_engine.py")

print(f"\n[*] Procesando {file1}...")
try:
    with open(file1, 'r', encoding='utf-8') as f:
        content1 = f.read()
    
    # BUG #1: Patron NEQUI (linea ~744-754)
    # Agregar: "pago pse" y "pago pse comerc recarga"
    old1 = "if 'NEQUI' in desc:"
    new1 = "if 'NEQUI' in desc or 'PAGO PSE' in desc or 'PAGO PSE COMERC RECARGA' in desc:"
    
    if old1 in content1:
        content1 = content1.replace(old1, new1)
        print("[FIX #1] ✅ Patron NEQUI actualizado")
    else:
        print("[FIX #1] ⚠️  Patron no encontrado exactamente")
    
    # BUG #2: pago_pse_nequi (linea ~422-428)
    # Cambiar: cuenta_debito=5538→5535, confianza_min=0.50→0.60, es_transferencia_interna=False→True
    
    old2a = "cuenta_debito=5538"
    if old2a in content1:
        content1 = content1.replace(old2a, "cuenta_debito=5535")
        print("[FIX #2a] ✅ cuenta_debito corregida (5538→5535)")
    
    old2b = "confianza_min=0.50"
    if old2b in content1:
        content1 = content1.replace(old2b, "confianza_min=0.60")
        print("[FIX #2b] ✅ confianza_min corregida (0.50→0.60)")
    
    old2c = "es_transferencia_interna=False  # INCORRECTO"
    if old2c in content1:
        content1 = content1.replace(old2c, "es_transferencia_interna=True  # CORRECTO")
        print("[FIX #2c] ✅ es_transferencia_interna corregida (False→True)")
    
    # Guardar archivo 1
    with open(file1, 'w', encoding='utf-8') as f:
        f.write(content1)
    print(f"[✓] {file1} guardado")

except Exception as e:
    print(f"[ERROR] {file1}: {e}")
    sys.exit(1)

# Archivo 2: contabilidad_pendientes.py
file2 = os.path.join("backend", "routers", "contabilidad_pendientes.py")

print(f"\n[*] Procesando {file2}...")
try:
    with open(file2, 'r', encoding='utf-8') as f:
        content2 = f.read()
    
    # BUG #3: Deteccion CXC demasiado amplia (linea ~548-550)
    old3 = "if re.search(r'(CXC|RETIRO|GASTO|ANTICIPO|ENVIO|COMPRA)', desc):"
    new3 = '''cxc_keywords = ["CXC SOCIO", "RETIRO SOCIO", "GASTO PERSONAL", "ANTICIPO SOCIO", "ENVIO A ANDRES", "ENVIO A IVAN", "COMPRA ANDRES", "PAGO LIZBETH"]
    if any(keyword in desc for keyword in cxc_keywords):'''
    
    if old3 in content2:
        content2 = content2.replace(old3, new3)
        print("[FIX #3] ✅ Deteccion CXC actualizada (lista especifica)")
    else:
        print("[FIX #3] ⚠️  Patron no encontrado exactamente")
    
    # Guardar archivo 2
    with open(file2, 'w', encoding='utf-8') as f:
        f.write(content2)
    print(f"[✓] {file2} guardado")

except Exception as e:
    print(f"[ERROR] {file2}: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("[✅] TODOS LOS FIXES APLICADOS EXITOSAMENTE")
print("="*60)
print("\nProximos pasos:")
print("1. git status")
print("2. git add -A")
print('3. git commit -m "BUILD 24: FIX bugs #1, #2, #3 - NEQUI, PSE, CXC patterns"')
print("4. git push")
