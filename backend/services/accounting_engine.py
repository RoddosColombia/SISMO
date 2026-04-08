"""
accounting_engine.py — Motor de Clasificación Contable RODDOS (BUILD 22)

Clasifica automáticamente transacciones bancarias a cuentas de Alegra.
- Matriz completa de IDs reales verificados
- Algoritmo de prioridad (socio > tecnología > intereses > gmf > resto)
- ClasificacionResult con confianza y requerimiento de confirmación
- Aprendizaje vía agent_memory para mejorar clasificaciones
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTOR DE PROVEEDOR — Desde descripción bancaria
# ══════════════════════════════════════════════════════════════════════════════

def extract_proveedor(descripcion: str) -> str:
    """
    Extrae nombre del proveedor desde la descripción del movimiento bancario.

    Patrones soportados:
    - "PAGO PSE COMERC NOMBRE ..." → "NOMBRE"
    - "TRANSFERENCIA A NOMBRE" → "NOMBRE"
    - "COMPRA EN NOMBRE_COMERCIO" → "NOMBRE_COMERCIO"
    - "NEQUI NOMBRE_PERSONA" → "NOMBRE_PERSONA"
    - "CARGO POR NOMBRE_SERVICIO" → "NOMBRE_SERVICIO"

    Si no se puede extraer → retorna descripcion[:30]

    Args:
        descripcion: Texto de la transacción bancaria

    Returns:
        Nombre del proveedor extraído o primeros 30 caracteres
    """
    desc = descripcion.upper().strip()

    # Patrón 1: "PAGO PSE COMERC NOMBRE ..."
    match = re.search(r'PAGO PSE COMERC\s+(\w+(?:\s+\w+)?)', desc)
    if match:
        return match.group(1).strip().lower()

    # Patrón 2: "TRANSFERENCIA A NOMBRE"
    match = re.search(r'TRANSFERENCIA A\s+(\w+(?:\s+\w+)*)', desc)
    if match:
        return match.group(1).strip().lower()

    # Patrón 3: "COMPRA EN NOMBRE_COMERCIO"
    match = re.search(r'COMPRA EN\s+(\w+(?:\s+\w+)?)', desc)
    if match:
        return match.group(1).strip().lower()

    # Patrón 4: "NEQUI NOMBRE_PERSONA"
    match = re.search(r'NEQUI\s+(\w+(?:\s+\w+)*)', desc)
    if match:
        return match.group(1).strip().lower()

    # Patrón 5: "CARGO POR NOMBRE_SERVICIO"
    match = re.search(r'CARGO POR\s+(\w+(?:\s+\w+)?)', desc)
    if match:
        return match.group(1).strip().lower()

    # Patrón 6: Palabras clave seguidas de nombre
    if "CUOTA PLAN CANAL" in desc:
        return "plan_canal_bancolombia"
    if "IVA CUOTA PLAN" in desc:
        return "iva_cuota_plan"
    if "CUOTA MANEJO TRJ" in desc:
        return "cuota_manejo_tarjeta"
    if "AJUSTE INTERES AHORROS" in desc:
        return "interes_ahorros"
    if "ABONO INTERES" in desc:
        return "abono_interes"
    if "RETIRO CAJERO" in desc:
        return "retiro_cajero"

    # Fallback: primeros 30 caracteres
    return desc[:30].lower()


# ══════════════════════════════════════════════════════════════════════════════
# MATRIZ COMPLETA DE CUENTAS ALEGRA — IDs REALES VERIFICADOS
# ══════════════════════════════════════════════════════════════════════════════

# ACTIVOS (raíz: 5307) — Solo movement
CUENTAS_ACTIVOS = {
    "caja_general": {"id": 5310, "nombre": "Caja general", "use": "movement"},
    "caja_menor": {"id": 5311, "nombre": "Caja Menor RODDOS (cód.PUC 11050502)", "use": "movement"},
    "bancolombia_2029": {"id": 5314, "nombre": "Bancolombia 2029", "use": "movement"},
    "bancolombia_2540": {"id": 5315, "nombre": "Bancolombia 2540", "use": "movement"},
    "tarjeta_debito_9942": {"id": 5316, "nombre": "Tarjeta débito prepago 9942", "use": "movement"},
    "tarjeta_debito_6588": {"id": 5317, "nombre": "Tarjeta débito prepago 6588", "use": "movement"},
    "bbva_0210": {"id": 5318, "nombre": "BBVA 0210", "use": "movement"},
    "bbva_0212": {"id": 5319, "nombre": "BBVA 0212", "use": "movement"},
    "banco_bogota_047674460": {"id": 5321, "nombre": "Banco de Bogotá Ahorros 047674460", "use": "movement"},
    "davivienda_482": {"id": 5322, "nombre": "Banco Davivienda Sa cuenta ahorros 482", "use": "movement"},
    "global66": {"id": 11100507, "nombre": "Global66 Colombia", "use": "movement"},
    "cxc_clientes_nacionales": {"id": 5326, "nombre": "Cuentas por cobrar clientes nacionales", "use": "movement"},
    "creditos_directos_roddos": {"id": 5327, "nombre": "Créditos Directos Roddos (CXC cartera)", "use": "movement"},
    "cxc_socios_accionistas": {"id": 5329, "nombre": "Cuentas por cobrar a socios y accionistas", "use": "movement"},
    "anticipos_proveedores": {"id": 5331, "nombre": "Avances y anticipos a proveedores", "use": "movement"},
    "anticipos_empleados": {"id": 5332, "nombre": "Avances y anticipos a empleados", "use": "movement"},
    "retencion_fuente_favor": {"id": 5340, "nombre": "Retención en la fuente a favor", "use": "movement"},
    "inventario_motos": {"id": 5348, "nombre": "Inventario Motos", "use": "movement"},
    "inventario_repuestos": {"id": 5349, "nombre": "Inventario Repuestos", "use": "movement"},
}

# PASIVOS (raíz: 5367) — Solo movement
CUENTAS_PASIVOS = {
    "pagares": {"id": 5372, "nombre": "Pagarés", "use": "movement"},
    "cxp_proveedores": {"id": 5376, "nombre": "Cuentas por pagar a proveedores nacionales", "use": "movement"},
    "otros_pasivos": {"id": 5378, "nombre": "Otros pasivos", "use": "movement"},
    "retencion_honorarios_10": {"id": 5381, "nombre": "Retenciones honorarios 10%", "use": "movement"},
    "retencion_honorarios_11": {"id": 5382, "nombre": "Retenciones honorarios 11%", "use": "movement"},
    "retencion_servicios_4": {"id": 5383, "nombre": "Retenciones servicios 4%", "use": "movement"},
    "retencion_arriendo_3_5": {"id": 5386, "nombre": "Retenciones arriendo 3.5%", "use": "movement"},
    "retencion_compra_2_5": {"id": 5388, "nombre": "Retenciones compra 2.5%", "use": "movement"},
    "reteica_11_04": {"id": 5392, "nombre": "RteICA 11.04", "use": "movement"},
    "iva_generado": {"id": 5404, "nombre": "IVA Generado 19%", "use": "movement"},
    "iva_descontable_compras": {"id": 5406, "nombre": "IVA Descontable Compras 19%", "use": "movement"},
    "iva_descontable_servicios": {"id": 5408, "nombre": "IVA Descontable Servicios", "use": "movement"},
    "ica_por_pagar": {"id": 5410, "nombre": "ICA por pagar", "use": "movement"},
    "salarios_por_pagar": {"id": 5413, "nombre": "Salarios por pagar", "use": "movement"},
}

# INGRESOS (raíz: 5435) — Solo movement
CUENTAS_INGRESOS = {
    "ventas_vehiculos": {"id": 5438, "nombre": "Ventas de Vehículos Automotores", "use": "movement"},
    "motos_ingreso": {"id": 5442, "nombre": "Motos (ingreso)", "use": "movement"},
    "repuestos_ingreso": {"id": 5444, "nombre": "Repuestos (ingreso)", "use": "movement"},
    "membresia_gps": {"id": 5447, "nombre": "Membresía GPS", "use": "movement"},
    "instalacion_gps": {"id": 5448, "nombre": "Instalación GPS", "use": "movement"},
    "intereses_cobrados": {"id": 5456, "nombre": "Créditos Directos Roddos (intereses cobrados)", "use": "movement"},
}

# GASTOS (raíz: 5458) — Solo movement
CUENTAS_GASTOS = {
    "sueldos_salarios": {"id": 5462, "nombre": "Sueldos y salarios", "use": "movement"},
    "auxilio_transporte": {"id": 5465, "nombre": "Auxilio de transporte", "use": "movement"},
    "cesantias": {"id": 5466, "nombre": "Cesantías", "use": "movement"},
    "prima_servicios": {"id": 5468, "nombre": "Prima de servicios", "use": "movement"},
    "vacaciones": {"id": 5469, "nombre": "Vacaciones", "use": "movement"},
    "dotacion_trabajadores": {"id": 5470, "nombre": "Dotación a trabajadores", "use": "movement"},
    "aportes_pensiones": {"id": 5472, "nombre": "Aportes pensiones y cesantías", "use": "movement"},
    "asesoria_juridica": {"id": 5475, "nombre": "Asesoría jurídica (honorarios PN)", "use": "movement"},
    "asesoria_financiera": {"id": 5476, "nombre": "Asesoría financiera (honorarios PJ)", "use": "movement"},
    "industria_comercio": {"id": 5478, "nombre": "Industria y Comercio", "use": "movement"},
    "arrendamientos": {"id": 5480, "nombre": "Arrendamientos", "use": "movement"},
    "aseo_vigilancia": {"id": 5482, "nombre": "Aseo y Vigilancia", "use": "movement"},
    "asistencia_tecnica": {"id": 5483, "nombre": "Asistencia técnica / Mantenimiento", "use": "movement"},
    "procesamiento_datos": {"id": 5484, "nombre": "Procesamiento Electrónico de Datos (SOFTWARE/TECH)", "use": "movement"},
    "servicios_publicos": {"id": 5485, "nombre": "Alcantarillado / Acueducto / Servicios públicos", "use": "movement"},
    "telefono_internet": {"id": 5487, "nombre": "Teléfono / Internet", "use": "movement"},
    "publicidad": {"id": 5495, "nombre": "Gastos de representación / Publicidad", "use": "movement"},
    "aseo_cafeteria": {"id": 5496, "nombre": "Elementos de aseo y cafetería (FALLBACK GENERAL)", "use": "movement"},
    "papeleria": {"id": 5497, "nombre": "Útiles, papelería y fotocopia", "use": "movement"},
    "combustibles": {"id": 5498, "nombre": "Combustibles y lubricantes", "use": "movement"},
    "transporte": {"id": 5499, "nombre": "Taxis y buses / Transporte", "use": "movement"},
    "deprecacion_oficina": {"id": 5502, "nombre": "Depreciación equipo de oficina", "use": "movement"},
    "deprecacion_computacion": {"id": 5503, "nombre": "Depreciación equipo de computación", "use": "movement"},
    "gastos_bancarios": {"id": 5507, "nombre": "Gastos bancarios", "use": "movement"},
    "comisiones_bancarias": {"id": 5508, "nombre": "Comisiones bancarias", "use": "movement"},
    "gmf_4x1000": {"id": 5509, "nombre": "GMF - Gravamen al movimiento financiero", "use": "movement"},
}

# COSTOS (raíz: 5515) — Solo movement
CUENTAS_COSTOS = {
    "costo_motos_vendidas": {"id": 5520, "nombre": "Costo motos vendidas", "use": "movement"},
    "intereses_rentistas": {"id": 5534, "nombre": "Intereses pagados a inversores rentistas", "use": "movement"},
}

# ══════════════════════════════════════════════════════════════════════════════
# MATRIZ DE CLASIFICACIÓN — REGLAS POR TIPO DE MOVIMIENTO
# ══════════════════════════════════════════════════════════════════════════════

REGLAS_CLASIFICACION = {
    # TECNOLOGÍA → Procesamiento Electrónico (5484)
    "tecnologia": {
        "proveedores": [
            "claude", "anthropic", "microsoft", "google", "adobe",
            "apple", "aws", "elevenlabs", "eleven labs", "openai",
            "figma", "notion", "slack", "zoom", "github",
            "jotform", "superprof", "ilovepdf", "apple.com",
            "sofia cds", "confirmafy", "chatgpt"
        ],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.8,
    },

    # INTERESES A RENTISTAS → Créditos Directos Roddos (5534) — NO 5533 (acumulativa)
    "intereses_rentistas": {
        "palabras_clave": ["intereses prestamo", "pago intereses", "interes prestamo"],
        "excluir_si": ["cesantias", "nomina"],
        "cuenta_debito": 5534,
        "cuenta_credito": 5376,
        "confianza_min": 0.75,
    },

    # CARGO GMF 4x1000
    "gmf": {
        "palabras_clave": ["4x1000", "4x1.000", "impuesto 4x1000", "impuesto 4x1.000", "gravamen", "gmf"],
        "cuenta_debito": 5509,
        "cuenta_credito": 5376,  # Se toma del banco de origen
        "confianza_min": 0.9,
    },

    # COMISIONES BANCARIAS
    "comisiones": {
        "palabras_clave": ["comision", "cargo bbva cash", "cuota manejo",
                           "cuota plan canal", "iva cuota plan"],
        "cuenta_debito": 5508,
        "cuenta_credito": 5376,
        "confianza_min": 0.85,
    },

    # GASTOS BANCARIOS
    "gastos_bancarios": {
        "palabras_clave": ["costo transferencia", "traslado dinero", "iva traslado"],
        "cuenta_debito": 5507,
        "cuenta_credito": 5376,
        "confianza_min": 0.8,
    },

    # GASTO SOCIO → CXC (5329) — NUNCA gasto operativo
    "gasto_socio": {
        "proveedores": ["andres sanjuan", "ivan echeverri", "sanjuan", "echeverri"],
        "palabras_clave": ["gasto socio", "anticipo nomina socio", "gasolina vehiculo",
                           "pico y placa", "gasto personal socio"],
        "cuenta_debito": 5329,
        "cuenta_credito": 5376,  # Banco de origen
        "confianza_min": 0.9,
    },

    # ARRENDAMIENTO
    "arriendo": {
        "palabras_clave": ["arriendo", "arrendamiento", "alquiler", "calle 127"],
        "cuenta_debito": 5480,
        "cuenta_credito": 5376,
        "retencion": 5386,  # 3.5%
        "confianza_min": 0.85,
    },

    # NÓMINA
    "nomina": {
        "palabras_clave": ["nomina", "pago nomina", "salario", "sueldo"],
        "cuenta_debito": 5462,
        "cuenta_credito": 5376,
        "confianza_min": 0.85,
    },

    # SERVICIOS PÚBLICOS
    "servicios_publicos": {
        "palabras_clave": ["luz", "energia", "enel", "gas", "vanti", "acueducto",
                           "alcantarillado", "agua", "epm", "codensa"],
        "cuenta_debito": 5485,
        "cuenta_credito": 5376,
        "confianza_min": 0.8,
    },

    # TELECOMUNICACIONES
    "telecomunicaciones": {
        "palabras_clave": ["internet", "telefono", "etb", "claro", "movistar",
                           "tigo", "comunicaciones", "celular"],
        "cuenta_debito": 5487,
        "cuenta_credito": 5376,
        "confianza_min": 0.8,
    },

    # PUBLICIDAD (solo si NO es tecnología)
    "publicidad": {
        "palabras_clave": ["pauta", "publicidad", "marketing", "anuncio"],
        "cuenta_debito": 5495,
        "cuenta_credito": 5376,
        "confianza_min": 0.75,
    },

    # CAFETERÍA / ASEO (fallback general)
    "cafeteria": {
        "palabras_clave": ["cafeteria", "almuerzo", "botellones", "d1", "aseo"],
        "cuenta_debito": 5496,
        "cuenta_credito": 5376,
        "confianza_min": 0.6,
    },

    # PAPELERÍA
    "papeleria": {
        "palabras_clave": ["papeleria", "utiles", "toner", "papel", "impresion"],
        "cuenta_debito": 5497,
        "cuenta_credito": 5376,
        "confianza_min": 0.8,
    },

    # COMBUSTIBLES
    "combustibles": {
        "palabras_clave": ["gasolina", "combustible", "aceite", "lubricante"],
        "cuenta_debito": 5498,
        "cuenta_credito": 5376,
        "confianza_min": 0.8,
    },

    # TRANSPORTE
    "transporte": {
        "palabras_clave": ["taxi", "uber", "transporte", "mensajeria", "envio", "flete"],
        "cuenta_debito": 5499,
        "cuenta_credito": 5376,
        "confianza_min": 0.75,
    },

    # POLÍTICA CONTABLE OFICIAL BBVA 2026 — 12 REGLAS ESPECÍFICAS

    # 1. CXC GASTO SOCIO ANDRES — CXC socios (5329), confianza 95%
    "cxc_gasto_socio_andres": {
        "palabras_clave": ["cxc gasto socio andres", "gasto socio andres"],
        "cuenta_debito": 5329,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 2. CXC GASTO SOCIO IVAN — CXC socios (5329), confianza 95%
    "cxc_gasto_socio_ivan": {
        "palabras_clave": ["cxc gasto socio ivan", "gasto socio ivan"],
        "cuenta_debito": 5329,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 3. ANTICIPO NÓMINA ANDRES — CXC socios (5329), confianza 92%
    "anticipo_nomina_andres": {
        "palabras_clave": ["anticipo nomina andres"],
        "cuenta_debito": 5329,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 4. NÓMINA RODDOS — Sueldos y salarios (5462), confianza 92%
    "nomina_roddos": {
        "palabras_clave": ["nomina roddos"],
        "cuenta_debito": 5462,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 5. PAGO ARRIENDO — Arrendamientos (5480), confianza 90%
    "pago_arriendo": {
        "palabras_clave": ["pago arriendo", "arriendo oficina"],
        "cuenta_debito": 5480,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 6. INTERESES (ANDRES CANO / DAVID MARTINEZ) — Intereses rentistas (5534), confianza 95%
    "intereses_rentistas_especifico": {
        "palabras_clave": ["intereses andres cano", "intereses david martinez"],
        "cuenta_debito": 5534,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 7. TRASLADO CUENTAS PROPIAS O INTERNO — NO contabilizar, confianza 95%
    # REGLA CONTABLE ABSOLUTA: ningún traslado entre cuentas propias genera asiento
    "traslado_interno": {
        "palabras_clave": [
            # Patrones originales
            "traslado de la 212 a la 210", "traslado de dinero", "abono por domic traslado",
            # Patrones adicionales detectados en backlog RODDOS (abr 2026)
            "traslado bbva", "traslado bancolombia", "traslado nequi", "traslado davivienda",
            "transfer bbva", "transfer bancolombia",
            "envio entre cuentas", "abono entre cuentas",
            "consignacion propia", "traslado fondos", "fondeo cuenta",
            "transfer from", "transfer to",
            "recarga nequi", "recarga desde bancolombia", "recarga en punto red",
            "bancolombia a bbva", "bbva a bancolombia", "bbva a nequi", "nequi a bbva",
            "entre cuentas propias", "trf entre cta", "traspaso entre",
            "deposito mismo titular", "mismo titular",
            "traslado entre productos", "traslado 212", "traslado 210",
        ],
        "cuenta_debito": 5535,  # Cuenta de control — NO contabilizar
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
        "es_transferencia_interna": True,  # NO contabilizar
    },

    # 8. INGRESOS CARTERA (RDX) — Créditos Directos (5327), confianza 90%
    "ingresos_cartera_rdx": {
        "palabras_clave": ["rdx", "motos del tropico", "recibiste diner"],
        "cuenta_debito": None,  # Banco como débito
        "cuenta_credito": 5327,  # Créditos Directos Roddos (INGRESO)
        "confianza_min": 0.90,
    },

    # 9. PAGO SOFTWARE (ALEGRA / SOFÍA) — Procesamiento datos (5484), confianza 92%
    "pago_software": {
        "palabras_clave": ["pago alegra", "pago sofia sdc", "sofia sds"],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 10. REEMBOLSO MULTA — Transporte (5499), confianza 80%
    "reembolso_multa": {
        "palabras_clave": ["reembolso pago multa"],
        "cuenta_debito": 5499,
        "cuenta_credito": 5376,
        "confianza_min": 0.80,
    },

    # 11. ABONO POR INTERESES — Ingresos financieros (5456), confianza 85%
    "abono_intereses": {
        "palabras_clave": ["abono por inter", "rendimientos financieros", "abono intereses ganados"],
        "cuenta_debito": None,  # Banco como débito
        "cuenta_credito": 5456,
        "confianza_min": 0.85,
    },

    # 12. PAGO PSE RECARGA NEQUI — Traslado interno (NO contabilizar), confianza 95%
    "pago_pse_nequi": {
        "palabras_clave": ["pago pse", "pago pse comerc recarga"],
        "cuenta_debito": 5493,  # Gastos Generales � CORRECCI�N — NO contabilizar
        "cuenta_credito": 5376,
        "confianza_min": 0.85,
        "es_transferencia_interna": True,  # NO contabilizar
    },

    # 13. COMISIÓN BBVA (BBVAC) → Comisiones bancarias (5508), confianza 92%
    "bbva_comision_bbvac": {
        "palabras_clave": ["comision bbvac", "bbvac"],
        "cuenta_debito": 5508,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 14. INTERESES RAUL / PRESTAMO RAUL → Intereses rentistas (5534), confianza 95%
    "bbva_intereses_raul": {
        "palabras_clave": ["intereses raul", "prestamo raul", "int raul"],
        "cuenta_debito": 5534,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 15. LIQUIDACION LILIANA (nómina) → Sueldos y salarios (5462), confianza 92%
    "bbva_liquidacion_liliana": {
        "palabras_clave": ["liquidacion liliana", "liq liliana", "nomina liliana"],
        "cuenta_debito": 5462,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 16. ASEO MONICA (servicio de aseo) → Aseo y vigilancia (5482), confianza 92%
    "bbva_aseo_monica": {
        "palabras_clave": ["aseo monica", "pago monica aseo", "servicio aseo monica"],
        "cuenta_debito": 5482,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE BANCOLOMBIA 2026 — 18 REGLAS ESPECÍFICAS
    # ─────────────────────────────────────────────────────────────────────────────

    # 1. ABONO INTERESES AHORROS → Ingresos financieros (5456), confianza 95%
    "bc_abono_intereses_ahorros": {
        "palabras_clave": ["abono intereses ahorros"],
        "cuenta_debito": None,  # Banco como débito
        "cuenta_credito": 5456,
        "confianza_min": 0.95,
    },

    # 2. CUOTA PLAN CANAL NEGOCIOS → Comisión bancaria (5508), confianza 92%
    "bc_cuota_plan_canal": {
        "palabras_clave": ["cuota plan canal negocios"],
        "cuenta_debito": 5508,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 3. IVA CUOTA PLAN CANAL → Gasto bancario (5507), confianza 92%
    "bc_iva_cuota_plan": {
        "palabras_clave": ["iva cuota plan canal"],
        "cuenta_debito": 5507,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 4. CUOTA MANEJO TRJ DEB → Gasto bancario (5507), confianza 92%
    "bc_cuota_manejo_trj": {
        "palabras_clave": ["cuota manejo trj deb"],
        "cuenta_debito": 5507,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 5. AJUSTE INTERES AHORROS DB → Gasto financiero (5507), confianza 90%
    "bc_ajuste_interes_ahorros": {
        "palabras_clave": ["ajuste interes ahorros db"],
        "cuenta_debito": 5507,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 6. COMPRA INTL ELEVENLABS → Tecnología (5484), confianza 95%
    "bc_compra_elevenlabs": {
        "palabras_clave": ["compra intl elevenlabs"],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 7. COMPRA INTL APPLE.COM → Tecnología (5484), confianza 95%
    "bc_compra_apple": {
        "palabras_clave": ["compra intl apple.com"],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 8. COMPRA INTL GOOGLE → Tecnología (5484), confianza 90%
    "bc_compra_google": {
        "palabras_clave": ["compra intl google"],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 9. RETIRO CAJERO → Pendiente, confianza 25% (requiere contexto)
    "bc_retiro_cajero": {
        "palabras_clave": ["retiro cajero"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": 5376,
        "confianza_min": 0.25,
    },

    # 10. TRANSFERENCIA DESDE NEQUI → Pendiente, confianza 30% (puede ser cobro cartera o traslado)
    "bc_transferencia_nequi": {
        "palabras_clave": ["transferencia desde nequi"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": 5376,
        "confianza_min": 0.30,
    },

    # 11. PAGO PSE Banco Davivienda → Pendiente, confianza 25% (requiere contexto)
    "bc_pago_pse_davivienda": {
        "palabras_clave": ["pago pse banco davivienda"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": 5376,
        "confianza_min": 0.25,
    },

    # 12. CONSIGNACION CORRESPONSAL CB → Pendiente ingreso, confianza 30%
    "bc_consignacion_corresponsal": {
        "palabras_clave": ["consignacion corresponsal cb"],
        "cuenta_debito": None,  # Banco como débito
        "cuenta_credito": 5496,  # Fallback
        "confianza_min": 0.30,
    },

    # 13. COMPRA EN TIENDA D1 → CXC socio si es gasto personal, confianza 45%
    "bc_compra_d1": {
        "palabras_clave": ["compra en tienda d1"],
        "cuenta_debito": 5329,  # CXC socio
        "cuenta_credito": 5376,
        "confianza_min": 0.45,
    },

    # 14. COMPRA EN UBER / RAPPI / MC DONALD / BURGER → Gasto personal socio CXC (5329), confianza 80%
    "bc_compra_personal": {
        "palabras_clave": ["compra en uber", "compra en rappi", "compra en mc donald", "compra en burger"],
        "cuenta_debito": 5329,  # CXC socio
        "cuenta_credito": 5376,
        "confianza_min": 0.80,
    },

    # 15. COMPRA EN FONTANAR / OPTICA / CASA D BTA → Gasto personal socio CXC (5329), confianza 75%
    "bc_compra_personal_otros": {
        "palabras_clave": ["compra en fontanar", "compra en optica", "compra en casa d bta"],
        "cuenta_debito": 5329,  # CXC socio
        "cuenta_credito": 5376,
        "confianza_min": 0.75,
    },

    # 16. TRANSFERENCIA CTA SUC VIRTUAL → Transferencia interna (5535), NO contabilizar, confianza 90%
    "bc_transferencia_cta_virtual": {
        "palabras_clave": ["transferencia cta suc virtual"],
        "cuenta_debito": 5535,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
        "es_transferencia_interna": True,
    },

    # 17. PAGO PSE EMPRESA DE TELECOMUN → Telecomunicaciones (5487), confianza 85%
    "bc_pago_telecom": {
        "palabras_clave": ["pago pse empresa de telecomun"],
        "cuenta_debito": 5487,
        "cuenta_credito": 5376,
        "confianza_min": 0.85,
    },

    # 18. PAGO PSE GOU PAYMENTS → Pendiente, confianza 30%
    "bc_pago_gou": {
        "palabras_clave": ["pago pse gou payments"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": 5376,
        "confianza_min": 0.30,
    },

    # ── FASE 3: FRAMEWORK COMPENSACIÓN DIFERIDA ───────────────────────────────
    # Salario Base Diferido: $8.500.000/mes/fundador → accrual en 5413
    # Límite gastos personales: $3.500.000/mes/fundador
    # Fundadores: Andrés Sanjuan CC 80075452 / Iván Echeverri CC 80086601

    # GASTOS PERSONALES FUNDADORES → 5413 Salarios por pagar (NO afectan P&L)
    "bc_gasto_personal_fundador": {
        "palabras_clave": [
            "compra en rappi", "compra en mc donald", "compra en burger",
            "compra en home burge", "compra en carulla", "compra en juan valde",
            "compra en farmatodo", "compra en fontanar", "compra en optica ale",
            "compra en casa d bta", "compra en arbol de v", "compra en sporty cit",
            "compra en patrimo au", "compra en jeronimo m", "compra en sto 688",
            "compra en tisan", "compra en bold*cevic",
            "compra intl disney plus", "compra intl spotify", "compra en prime vide",
            "compra intl feenko", "compra en amazon pri",
            # Bancolombia abrevia "GASTO" como "GAST" en extractos
            "cxc gast socio andres", "cxc gast socio ivan",
        ],
        "cuenta_debito": 5413,   # Salarios por pagar — reduce saldo diferido
        "cuenta_credito": 5376,  # banco_origen como fallback
        "confianza_min": 0.85,
    },

    # K TRONIX → Equipos tecnología empleados → 5484
    "bc_ktronix_tech": {
        "palabras_clave": ["compra en k tronix"],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # COMBUSTIBLE → 5498
    "bc_combustible": {
        "palabras_clave": ["compra en eds norman", "compra en eds amborc", "compra en texaco eds"],
        "cuenta_debito": 5498,
        "cuenta_credito": 5376,  # banco_origen como fallback
        "confianza_min": 0.85,
    },

    # PARQUEADERO → 5499
    "bc_parqueadero": {
        "palabras_clave": ["compra en parqueader"],
        "cuenta_debito": 5499,
        "cuenta_credito": 5376,  # banco_origen como fallback
        "confianza_min": 0.85,
    },

    # MERCATELY → 5484 Tech
    "bc_mercately": {
        "palabras_clave": ["compra intl mercately"],
        "cuenta_debito": 5484,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # COBROS DE CARTERA via Nequi (reemplaza bc_transferencia_nequi pendiente)
    "bc_cobro_cartera_nequi": {
        "palabras_clave": ["transferencia desde nequi"],
        "cuenta_debito": None,   # banco_origen como fallback
        "cuenta_credito": 5327,  # Créditos Directos Roddos
        "confianza_min": 0.80,
    },

    # COBROS DE CARTERA via Pago Llave
    "bc_cobro_cartera_pago_llave": {
        "palabras_clave": ["pago llave"],
        "cuenta_debito": None,   # banco_origen como fallback
        "cuenta_credito": 5327,
        "confianza_min": 0.85,
    },

    # COBROS DE CARTERA via Corresponsal (reemplaza bc_consignacion_corresponsal pendiente)
    "bc_cobro_cartera_corresponsal": {
        "palabras_clave": ["consignacion corresponsal cb"],
        "cuenta_debito": None,   # banco_origen como fallback
        "cuenta_credito": 5327,
        "confianza_min": 0.80,
    },

    # GASTOS BANCARIOS VARIOS → 5507
    "bc_servicios_bancarios": {
        "palabras_clave": [
            "servicio pago a otros bancos", "servicio pago a proveedores",
            "servicio e-mails enviados", "cobro iva pagos automaticos",
            "transf de mary suarez", "ajuste compra intl confirmaf",
        ],
        "cuenta_debito": 5507,
        "cuenta_credito": 5376,  # banco_origen como fallback
        "confianza_min": 0.85,
    },

    # CAMARA DE COMERCIO → 5478 Industria y Comercio
    "bc_camara_comercio": {
        "palabras_clave": ["pago pse camara de comercio"],
        "cuenta_debito": 5478,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # PRÉSTAMO EMPLEADA MARY ALEXANDRA SUÁREZ → 5332 CXC empleados
    # Préstamo original $17.000.000 (oct 2025), abono reduce saldo
    "bc_prestamo_empleada_mary": {
        "palabras_clave": ["pago a prov mary alexandra"],
        "cuenta_debito": 5332,   # Avances y anticipos a empleados
        "cuenta_credito": 5376,  # banco_origen como fallback
        "confianza_min": 0.95,
    },

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE NEQUI (ANDRÉS SANJUAN) — 15 REGLAS + 1 INGRESO LIZBETH
    # Nequi es cuenta personal de Andrés. banco_origen = 5310
    # ─────────────────────────────────────────────────────────────────────────────

    # 1. RODDOS SAS egreso → traslado interno (Andrés envía de Nequi a empresa)
    "nequi_traslado_roddos_sas": {
        "palabras_clave": ["roddos sas"],
        "cuenta_debito": 5535,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
        "es_transferencia_interna": True,
    },

    # 2. Envio a otros bancos a RODDOS → traslado interno
    "nequi_envio_banco_roddos": {
        "palabras_clave": ["envio a otros bancos a roddos"],
        "cuenta_debito": 5535,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
        "es_transferencia_interna": True,
    },

    # 3. Recargas propias → traslado interno (desde Bancolombia, PSE, Punto Red)
    "nequi_recarga_propia": {
        "palabras_clave": [
            "recarga desde bancolombia",
            "recarga nequi pse",
            "recarga en punto red",
        ],
        "cuenta_debito": 5535,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
        "es_transferencia_interna": True,
    },

    # 4. Cobros de cartera — clientes que pagan por Nequi (INGRESOS)
    "nequi_cobro_cartera_cliente": {
        "palabras_clave": [
            "de chirly mariana mateus",
            "de andres felipe aldana",
            "de nicolas reyes gonzalez",
            "de yenifer andreina medina",
            "de leinys gonzalez",
            "de nazareth dugarte",
            "de jair domico",
            "de trinidad gutierrez",
            "de william arturo suarez",
            "de sebastian ubaque silva",
            "de rodrigo jose camacho",
            "de jhon fredy hinestroza",
        ],
        "cuenta_debito": None,   # banco_origen como débito (ingreso)
        "cuenta_credito": 5327,  # Créditos Directos Roddos
        "confianza_min": 0.90,
    },

    # 4b. Ingreso de Lizbeth Rincón — origen sin confirmar → backlog
    "nequi_ingreso_lizbeth": {
        "palabras_clave": ["de lizbeth rincon rojas"],
        "cuenta_debito": None,
        "cuenta_credito": 5496,
        "confianza_min": 0.35,
    },

    # 5. RECIBI POR BRE-B DE: DIANA → esposa Andrés → recuperación → reduce 5413
    "nequi_recibo_diana": {
        "palabras_clave": ["recibi por bre-b de: diana"],
        "cuenta_debito": None,
        "cuenta_credito": 5413,
        "confianza_min": 0.90,
    },

    # 6. F2X SAS = Flypass peajes → Transporte (5499)
    "nequi_flypass_peajes": {
        "palabras_clave": ["compra pse en f2x sas", "f2x sas"],
        "cuenta_debito": 5499,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 7. Pagos a personas (cafetería, restaurante, parqueadero) → 5413 Andrés
    "nequi_pagos_personales_para": {
        "palabras_clave": [
            "para jenniffer alexandra",
            "para kevin cano",
            "para arnol perdomo",
            "para mariana alexandra",
            "para lina montes del valle",
        ],
        "cuenta_debito": 5413,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 8. COMPRA PSE EN Beneficencia → lotería/personal Andrés → 5413
    "nequi_compra_beneficiencia": {
        "palabras_clave": ["compra pse en beneficiencia de", "beneficiencia de"],
        "cuenta_debito": 5413,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 9. ENVIO CON BRE-B A: ANDRES → gasto personal Andrés → 5413
    "nequi_envio_andres": {
        "palabras_clave": ["envio con bre-b a: andres"],
        "cuenta_debito": 5413,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 10. ENVIO CON BRE-B A: Diana → esposa Andrés → a nombre Andrés → 5413
    "nequi_envio_diana": {
        "palabras_clave": ["envio con bre-b a: diana"],
        "cuenta_debito": 5413,
        "cuenta_credito": 5376,
        "confianza_min": 0.90,
    },

    # 11. Para IVAN ECHEVERRI GOMEZ → compensación diferida socio → 5413
    "nequi_para_ivan": {
        "palabras_clave": ["para ivan echeverri gomez"],
        "cuenta_debito": 5413,
        "cuenta_credito": 5376,
        "confianza_min": 0.95,
    },

    # 12. Para LIZBETH RINCON ROJAS → nómina/anticipo empleada → 5462
    "nequi_pago_lizbeth": {
        "palabras_clave": ["para lizbeth rincon rojas"],
        "cuenta_debito": 5462,
        "cuenta_credito": 5376,
        "confianza_min": 0.92,
    },

    # 13. Pago de Intereses (Nequi) → Ingresos financieros → 5456
    "nequi_intereses_propios": {
        "palabras_clave": ["pago de intereses"],
        "cuenta_debito": None,
        "cuenta_credito": 5456,
        "confianza_min": 0.85,
    },

    # 14. ENVIO CON BRE-B A: NELSON → backlog (pendiente identificar)
    "nequi_envio_nelson": {
        "palabras_clave": ["envio con bre-b a: nelson"],
        "cuenta_debito": 5496,
        "cuenta_credito": 5376,
        "confianza_min": 0.30,
    },

    # 15. VITAL TREE, QR BRE-B no identificados → backlog
    "nequi_no_identificado": {
        "palabras_clave": ["vital tree", "pago en qr bre-b"],
        "cuenta_debito": 5496,
        "cuenta_credito": 5376,
        "confianza_min": 0.25,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# DATACLASS DE RESULTADO
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ClasificacionResult:
    """Resultado de la clasificación automática de un movimiento."""
    cuenta_debito: int
    cuenta_credito: Optional[int]
    confianza: float  # 0-1
    requiere_confirmacion: bool
    razon: str
    tipo_retencion: Optional[str] = None
    categoria: str = ""
    es_transferencia_interna: bool = False  # True = no contabilizar en Alegra


# ══════════════════════════════════════════════════════════════════════════════
# ALGORITMO DE CLASIFICACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def clasificar_movimiento(
    descripcion: str,
    proveedor: str = "",
    monto: float = 0,
    banco_origen: int = 5314,  # Bancolombia por defecto
) -> ClasificacionResult:
    """
    Clasifica un movimiento bancario a cuentas de Alegra.

    Orden de prioridad:
    1. Socio (NUNCA gasto) → CXC 5329
    2. Tecnología (antes que publicidad) → 5484
    3. Intereses rentistas (antes que gastos generales) → 5534
    4. GMF 4x1000 → 5509
    5. Comisiones/Gastos bancarios → 5508/5507
    6. Resto según descripción

    Args:
        descripcion: Texto de la transacción
        proveedor: Nombre del proveedor/beneficiario
        monto: Monto de la transacción
        banco_origen: ID de cuenta bancaria de origen

    Returns:
        ClasificacionResult con clasificación y confianza
    """
    desc_lower = re.sub(r'\s+', ' ', descripcion.lower().strip())
    prov_lower = re.sub(r'\s+', ' ', (proveedor or "").lower().strip())
    texto_combinado = f"{desc_lower} {prov_lower}"
    desc_check = texto_combinado  # alias usado por todos los bloques de reglas

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE NEQUI — 15 REGLAS + 1 INGRESO LIZBETH (PRIORIDAD MÁXIMA)
    # banco_origen=5310 cuando viene de NequiParser
    # ─────────────────────────────────────────────────────────────────────────────

    # NQ-1. RODDOS SAS → traslado interno, NO contabilizar
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_traslado_roddos_sas"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535, cuenta_credito=banco_origen,
            confianza=0.95, requiere_confirmacion=False,
            razon="RODDOS SAS en Nequi → Traslado interno Andrés→empresa, NO contabilizar",
            categoria="NEQUI_TRASLADO", es_transferencia_interna=True
        )

    # NQ-2. Envio a otros bancos a RODDOS → traslado interno
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_envio_banco_roddos"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535, cuenta_credito=banco_origen,
            confianza=0.95, requiere_confirmacion=False,
            razon="Envio a RODDOS → Traslado interno Nequi→empresa, NO contabilizar",
            categoria="NEQUI_TRASLADO", es_transferencia_interna=True
        )

    # NQ-3. Recargas propias → traslado interno
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_recarga_propia"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535, cuenta_credito=banco_origen,
            confianza=0.95, requiere_confirmacion=False,
            razon="Recarga Nequi (Bancolombia/PSE/Punto Red) → Traslado interno, NO contabilizar",
            categoria="NEQUI_TRASLADO", es_transferencia_interna=True
        )

    # NQ-4a. Ingreso de Lizbeth Rincón — origen sin confirmar → backlog (ANTES del cobro cartera)
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_ingreso_lizbeth"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen, cuenta_credito=5496,
            confianza=0.35, requiere_confirmacion=True,
            razon="Ingreso de Lizbeth Rincón (empleada) → origen sin confirmar, backlog",
            categoria="NEQUI_PENDIENTE"
        )

    # NQ-4. Cobros de cartera (De NOMBRE cliente)
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_cobro_cartera_cliente"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen, cuenta_credito=5327,
            confianza=0.90, requiere_confirmacion=False,
            razon="Cobro cartera cliente por Nequi → Créditos Directos Roddos",
            categoria="NEQUI_COBRO_CARTERA"
        )

    # NQ-5. Recibo de Diana (esposa Andrés) → recuperación préstamo → reduce 5413
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_recibo_diana"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen, cuenta_credito=5413,
            confianza=0.90, requiere_confirmacion=False,
            razon="Recibo de Diana (esposa Andrés) → Recuperación préstamo → reduce 5413",
            categoria="NEQUI_DIANA"
        )

    # NQ-6. F2X SAS = Flypass peajes → 5499
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_flypass_peajes"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5499, cuenta_credito=banco_origen,
            confianza=0.92, requiere_confirmacion=False,
            razon="Flypass F2X SAS → Peajes (Transporte) → 5499",
            categoria="NEQUI_TRANSPORTE"
        )

    # NQ-7. Pagos personales (cafetería, restaurante, parqueadero) → 5413
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_pagos_personales_para"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5413, cuenta_credito=banco_origen,
            confianza=0.90, requiere_confirmacion=False,
            razon="Gasto personal Andrés (cafetería/restaurante/parqueadero) → 5413",
            categoria="NEQUI_GASTO_PERSONAL"
        )

    # NQ-8. Beneficencia → gasto personal Andrés → 5413
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_compra_beneficiencia"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5413, cuenta_credito=banco_origen,
            confianza=0.90, requiere_confirmacion=False,
            razon="Beneficencia (lotería/sorteo personal Andrés) → 5413",
            categoria="NEQUI_GASTO_PERSONAL"
        )

    # NQ-9. Envio BRE-B a Andrés → gasto personal → 5413
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_envio_andres"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5413, cuenta_credito=banco_origen,
            confianza=0.90, requiere_confirmacion=False,
            razon="Envio BRE-B a Andrés → Gasto personal compensación diferida → 5413",
            categoria="NEQUI_GASTO_PERSONAL"
        )

    # NQ-10. Envio a Diana (esposa) → a nombre Andrés → 5413
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_envio_diana"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5413, cuenta_credito=banco_origen,
            confianza=0.90, requiere_confirmacion=False,
            razon="Envio a Diana (esposa Andrés) → a nombre Andrés → 5413",
            categoria="NEQUI_DIANA"
        )

    # NQ-11. Para IVAN ECHEVERRI GOMEZ → 5413 socio
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_para_ivan"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5413, cuenta_credito=banco_origen,
            confianza=0.95, requiere_confirmacion=False,
            razon="Pago a Iván Echeverri (socio) → compensación diferida → 5413",
            categoria="NEQUI_SOCIO"
        )

    # NQ-12. Para LIZBETH RINCON ROJAS → nómina empleada → 5462
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_pago_lizbeth"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5462, cuenta_credito=banco_origen,
            confianza=0.92, requiere_confirmacion=False,
            razon="Pago Lizbeth Rincón (empleada) → Sueldos y salarios → 5462",
            categoria="NEQUI_NOMINA"
        )

    # NQ-13. Pago de Intereses Nequi → ingresos financieros → 5456
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_intereses_propios"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen, cuenta_credito=5456,
            confianza=0.85, requiere_confirmacion=False,
            razon="Intereses Nequi → Ingresos financieros → 5456",
            categoria="NEQUI_INTERES"
        )

    # NQ-14. ENVIO A NELSON → backlog
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_envio_nelson"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5496, cuenta_credito=banco_origen,
            confianza=0.30, requiere_confirmacion=True,
            razon="Envio a Nelson (Nequi) → Sin identificar, backlog",
            categoria="NEQUI_PENDIENTE"
        )

    # NQ-15. Vital Tree, QR BRE-B no identificado → backlog
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nequi_no_identificado"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5496, cuenta_credito=banco_origen,
            confianza=0.25, requiere_confirmacion=True,
            razon="Pago QR/Nequi no identificado → backlog",
            categoria="NEQUI_PENDIENTE"
        )

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE OFICIAL BBVA 2026 — REGLAS ESPECÍFICAS (MÁXIMA PRIORIDAD)
    # ─────────────────────────────────────────────────────────────────────────────

    # 0a. CXC GASTO SOCIO ANDRES — confianza 95%
    if any(kw in texto_combinado for kw in REGLAS_CLASIFICACION["cxc_gasto_socio_andres"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="CXC Gasto Socio Andres → NUNCA P&L",
            categoria="CXC_GASTO_ANDRES"
        )

    # 0b. CXC GASTO SOCIO IVAN — confianza 95%
    if any(kw in texto_combinado for kw in REGLAS_CLASIFICACION["cxc_gasto_socio_ivan"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="CXC Gasto Socio Ivan → NUNCA P&L",
            categoria="CXC_GASTO_IVAN"
        )

    # 0c. ANTICIPO NÓMINA ANDRES — confianza 92%
    if any(kw in texto_combinado for kw in REGLAS_CLASIFICACION["anticipo_nomina_andres"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Anticipo Nómina Andres → CXC socios",
            categoria="ANTICIPO_ANDRES"
        )

    # 0d. NÓMINA RODDOS — confianza 92%
    if any(kw in texto_combinado for kw in REGLAS_CLASIFICACION["nomina_roddos"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5462,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Nómina RODDOS → Sueldos y salarios",
            categoria="NOMINA_RODDOS"
        )

    # 0e. TRASLADO INTERNO (212→210 o dinero entre cuentas) — confianza 95%, NO CONTABILIZAR
    if any(kw in texto_combinado for kw in REGLAS_CLASIFICACION["traslado_interno"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Traslado interno RODDOS → NO contabilizar",
            categoria="TRASLADO_INTERNO",
            es_transferencia_interna=True
        )

    # 1. GASTO SOCIO GENÉRICO — SIEMPRE CXC, nunca gasto operativo (fallback)
    for socio in REGLAS_CLASIFICACION["gasto_socio"]["proveedores"]:
        if socio in prov_lower:
            return ClasificacionResult(
                cuenta_debito=5329,
                cuenta_credito=banco_origen,
                confianza=0.95,
                requiere_confirmacion=False,
                razon=f"Gasto de socio '{proveedor}' → CXC socios (nunca P&L)",
                categoria="CXC_SOCIO"
            )

    for palabra in REGLAS_CLASIFICACION["gasto_socio"]["palabras_clave"]:
        if palabra in texto_combinado:
            return ClasificacionResult(
                cuenta_debito=5329,
                cuenta_credito=banco_origen,
                confianza=0.85,
                requiere_confirmacion=True,
                razon=f"Posible gasto socio — requiere confirmación ({palabra})",
                categoria="CXC_SOCIO"
            )

    # 2. TECNOLOGÍA — antes que publicidad
    for tech_prov in REGLAS_CLASIFICACION["tecnologia"]["proveedores"]:
        if tech_prov in prov_lower or tech_prov in desc_lower:
            return ClasificacionResult(
                cuenta_debito=5484,
                cuenta_credito=5376,
                confianza=0.92,
                requiere_confirmacion=False,
                razon=f"Software/Tecnología identificado: {tech_prov}",
                categoria="TECNOLOGIA"
            )

    # 3. INTERESES A RENTISTAS — antes que gastos generales
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["intereses_rentistas"]["palabras_clave"]):
        if not any(exc in desc_check for exc in REGLAS_CLASIFICACION["intereses_rentistas"]["excluir_si"]):
            return ClasificacionResult(
                cuenta_debito=5534,
                cuenta_credito=5376,
                confianza=0.88,
                requiere_confirmacion=False,
                razon="Intereses pagados a rentistas → 5534 (NO 5533 acumulativa)",
                categoria="INTERES_RENTISTA"
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE BBVA FEBRERO 2026 — 5 REGLAS NUEVAS
    # ─────────────────────────────────────────────────────────────────────────────

    # FEB-1. EMBARGO CUENTA CORRIENTE → ICA por pagar (5410) confianza 85%
    # Embargo judicial Hacienda Bogotá por ICA adeudado — reduce pasivo 5410
    if "embargo cuenta corriente" in desc_check or "embargo cuenta ahorros" in desc_check:
        return ClasificacionResult(
            cuenta_debito=5410,
            cuenta_credito=banco_origen,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Embargo judicial Hacienda Bogotá (ICA) → reduce ICA por pagar (5410)",
            categoria="EMBARGO_ICA"
        )

    # FEB-2. ABONO DOMI. → Ingreso cartera (5327) confianza 88%
    # Pagos en efectivo de clientes consignados en cuenta bancaria
    if "abono domi." in desc_check or "abono domi " in desc_check:
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5327,
            confianza=0.88,
            requiere_confirmacion=False,
            razon="ABONO DOMI → Pago efectivo cliente consignado → Créditos Directos RODDOS (5327)",
            categoria="INGRESO_CARTERA"
        )

    # FEB-3. COBRO POR GIRO AL BANCO AGRARIO → Comisión bancaria (5508) confianza 90%
    if "cobro por giro al banco agrario" in desc_check:
        return ClasificacionResult(
            cuenta_debito=5508,
            cuenta_credito=banco_origen,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Cobro giro Banco Agrario → Comisión bancaria (5508)",
            categoria="COMISION_BANCARIA"
        )

    # FEB-4. PAGO POR PSE A [BANCO] → Backlog (sin contexto) confianza 20%
    if "pago por pse a banco" in desc_check or "pago por pse a bancolombia" in desc_check:
        return ClasificacionResult(
            cuenta_debito=5496,
            cuenta_credito=banco_origen,
            confianza=0.20,
            requiere_confirmacion=True,
            razon="Pago PSE a banco externo → requiere contexto (¿pago a quién?)",
            categoria="PENDIENTE"
        )

    # FEB-5. ABONO DOMI. TRANS DAVP-ACH → Ingreso cartera (5327) confianza 80%
    if "davp-ach" in desc_check or "trans davp" in desc_check:
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5327,
            confianza=0.80,
            requiere_confirmacion=False,
            razon="Transferencia ACH Davivienda → Ingreso cartera (5327)",
            categoria="INGRESO_CARTERA"
        )

    # 4. GMF 4x1000
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["gmf"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5509,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Gravamen al movimiento financiero 4x1000",
            categoria="GMF"
        )

    # 5. COMISIONES BANCARIAS
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["comisiones"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5508,
            cuenta_credito=banco_origen,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Comisión bancaria automática",
            categoria="COMISION_BANCARIA"
        )

    # 6. GASTOS BANCARIOS
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["gastos_bancarios"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5507,
            cuenta_credito=banco_origen,
            confianza=0.88,
            requiere_confirmacion=False,
            razon="Gasto bancario (transferencia, traslado)",
            categoria="GASTO_BANCARIO"
        )

    # 7. ARRENDAMIENTO
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["arriendo"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5480,
            cuenta_credito=5376,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Arrendamiento de oficina — aplica retención 3.5% (5386)",
            tipo_retencion="5386",
            categoria="ARRIENDO"
        )

    # 8. NÓMINA
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nomina"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5462,
            cuenta_credito=banco_origen,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Pago de nómina/sueldos",
            categoria="NOMINA"
        )

    # 9. SERVICIOS PÚBLICOS — excluir si es gasto socio (cxc/socio en descripción)
    if (any(kw in desc_check for kw in REGLAS_CLASIFICACION["servicios_publicos"]["palabras_clave"])
            and not ("cxc" in desc_check or "socio" in desc_check)):
        return ClasificacionResult(
            cuenta_debito=5485,
            cuenta_credito=5376,
            confianza=0.88,
            requiere_confirmacion=False,
            razon="Servicios públicos (luz, agua, gas, etc.)",
            categoria="SERVICIOS_PUBLICOS"
        )

    # 10. TELECOMUNICACIONES
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["telecomunicaciones"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5487,
            cuenta_credito=5376,
            confianza=0.88,
            requiere_confirmacion=False,
            razon="Telecomunicaciones (internet, teléfono)",
            categoria="TELECOMUNICACIONES"
        )

    # 11. PUBLICIDAD
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["publicidad"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5495,
            cuenta_credito=5376,
            confianza=0.75,
            requiere_confirmacion=True,
            razon="Publicidad/Marketing identificada — revisar",
            categoria="PUBLICIDAD"
        )

    # 12. PAPELERÍA
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["papeleria"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5497,
            cuenta_credito=5376,
            confianza=0.82,
            requiere_confirmacion=False,
            razon="Papelería/útiles de oficina",
            categoria="PAPELERIA"
        )

    # 13. COMBUSTIBLES
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["combustibles"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5498,
            cuenta_credito=5376,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Combustibles y lubricantes",
            categoria="COMBUSTIBLES"
        )

    # 14. TRANSPORTE
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["transporte"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5499,
            cuenta_credito=5376,
            confianza=0.78,
            requiere_confirmacion=True,
            razon="Transporte/Mensajería — revisar si aplica retención",
            categoria="TRANSPORTE"
        )

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE OFICIAL BBVA 2026 — 12 REGLAS ORDENADAS POR PRIORIDAD
    # ─────────────────────────────────────────────────────────────────────────────

    # 1. CXC GASTO SOCIO ANDRES — confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["cxc_gasto_socio_andres"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="CXC Gasto Socio Andres → NUNCA P&L",
            categoria="CXC_GASTO_ANDRES"
        )

    # 2. CXC GASTO SOCIO IVAN — confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["cxc_gasto_socio_ivan"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="CXC Gasto Socio Ivan → NUNCA P&L",
            categoria="CXC_GASTO_IVAN"
        )

    # 3. ANTICIPO NÓMINA ANDRES — confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["anticipo_nomina_andres"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Anticipo Nómina Andres → CXC socios",
            categoria="ANTICIPO_ANDRES"
        )

    # 4. NÓMINA RODDOS — confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["nomina_roddos"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5462,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Nómina RODDOS → Sueldos y salarios",
            categoria="NOMINA_RODDOS"
        )

    # 5. PAGO ARRIENDO — confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["pago_arriendo"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5480,
            cuenta_credito=5376,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Pago Arriendo Oficina → Arrendamientos",
            categoria="ARRIENDO"
        )

    # 6. INTERESES RENTISTAS ESPECÍFICOS — confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["intereses_rentistas_especifico"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5534,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Intereses Rentistas → 5534",
            categoria="INTERES_RENTISTA"
        )

    # 7. TRASLADO INTERNO (212→210 o dinero entre cuentas) — confianza 95%, NO CONTABILIZAR
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["traslado_interno"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Traslado interno RODDOS → NO contabilizar",
            categoria="TRASLADO_INTERNO",
            es_transferencia_interna=True
        )

    # 8. INGRESOS CARTERA (RDX) — confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["ingresos_cartera_rdx"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5327,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Ingreso Cartera (RDX) → Créditos Directos",
            categoria="INGRESO_CARTERA"
        )

    # 9. PAGO SOFTWARE (ALEGRA / SOFÍA) — confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["pago_software"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=5376,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Pago Software → Procesamiento Electrónico",
            categoria="PAGO_SOFTWARE"
        )

    # 10. REEMBOLSO MULTA — confianza 80%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["reembolso_multa"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5499,
            cuenta_credito=5376,
            confianza=0.80,
            requiere_confirmacion=False,
            razon="Reembolso Multa → Transporte",
            categoria="MULTA"
        )

    # 11. ABONO POR INTERESES — confianza 85%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["abono_intereses"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5456,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Abono Intereses → Ingresos Financieros",
            categoria="ABONO_INTERES"
        )

    # 12. PAGO PSE RECARGA NEQUI — confianza 25%, REQUIERE CONTEXTO
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["pago_pse_nequi"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535,
            cuenta_credito=5376,
            confianza=0.25,
            requiere_confirmacion=True,
            razon="Recarga NEQUI → Esperando contexto vía WhatsApp",
            categoria="RECARGA_NEQUI"
        )

    # 13. COMISIÓN BBVA (BBVAC) — confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bbva_comision_bbvac"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5508,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Comisión BBVA → Comisiones Bancarias",
            categoria="BBVA_COMISION"
        )

    # 14. INTERESES RAUL → Intereses rentistas (5534) — confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bbva_intereses_raul"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5534,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Intereses Raúl → Intereses Rentistas",
            categoria="BBVA_INTERES_RENTISTA"
        )

    # 15. LIQUIDACION LILIANA → Sueldos y salarios (5462) — confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bbva_liquidacion_liliana"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5462,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Liquidación Liliana → Sueldos y Salarios",
            categoria="BBVA_NOMINA"
        )

    # 16. ASEO MONICA → Aseo y vigilancia (5482) — confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bbva_aseo_monica"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5482,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Aseo Mónica → Aseo y Vigilancia",
            categoria="BBVA_ASEO"
        )

    # ─────────────────────────────────────────────────────────────────────────────
    # POLÍTICA CONTABLE BANCOLOMBIA 2026 — 18 REGLAS ESPECÍFICAS
    # ─────────────────────────────────────────────────────────────────────────────

    # BC-1. ABONO INTERESES AHORROS → Ingresos financieros (5456), confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_abono_intereses_ahorros"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5456,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Abono Intereses Ahorros → Ingresos Financieros",
            categoria="BC_ABONO_INTERES"
        )

    # BC-2. CUOTA PLAN CANAL NEGOCIOS → Comisión bancaria (5508), confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_cuota_plan_canal"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5508,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Cuota Plan Canal Negocios → Comisión Bancaria",
            categoria="BC_COMISION"
        )

    # BC-3. IVA CUOTA PLAN CANAL → Gasto bancario (5507), confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_iva_cuota_plan"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5507,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="IVA Cuota Plan Canal → Gasto Bancario",
            categoria="BC_GASTO_BANCARIO"
        )

    # BC-4. CUOTA MANEJO TRJ DEB → Gasto bancario (5507), confianza 92%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_cuota_manejo_trj"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5507,
            cuenta_credito=banco_origen,
            confianza=0.92,
            requiere_confirmacion=False,
            razon="Cuota Manejo TRJ DEB → Gasto Bancario",
            categoria="BC_GASTO_BANCARIO"
        )

    # BC-5. AJUSTE INTERES AHORROS DB → Gasto financiero (5507), confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_ajuste_interes_ahorros"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5507,
            cuenta_credito=banco_origen,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Ajuste Interes Ahorros DB → Gasto Bancario",
            categoria="BC_GASTO_BANCARIO"
        )

    # BC-6. COMPRA INTL ELEVENLABS → Tecnología (5484), confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_compra_elevenlabs"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=5376,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Compra INTL ElevenLabs → Tecnología",
            categoria="BC_TECNOLOGIA"
        )

    # BC-7. COMPRA INTL APPLE.COM → Tecnología (5484), confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_compra_apple"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=5376,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Compra INTL Apple → Tecnología",
            categoria="BC_TECNOLOGIA"
        )

    # BC-8. COMPRA INTL GOOGLE → Tecnología (5484), confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_compra_google"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=5376,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Compra INTL Google → Tecnología",
            categoria="BC_TECNOLOGIA"
        )

    # BC-9. RETIRO CAJERO → Pendiente, confianza 25%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_retiro_cajero"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5496,
            cuenta_credito=banco_origen,
            confianza=0.25,
            requiere_confirmacion=True,
            razon="Retiro Cajero → Requiere contexto (gasto personal o cobro)",
            categoria="BC_PENDIENTE"
        )

    # BC-F3-1. TRANSFERENCIA DESDE NEQUI → Cobro cartera (5327), confianza 80%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_cobro_cartera_nequi"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5327,
            confianza=0.80,
            requiere_confirmacion=False,
            razon="Transferencia desde Nequi → Cobro cartera (Créditos Directos Roddos)",
            categoria="BC_COBRO_CARTERA"
        )

    # BC-10. TRANSFERENCIA DESDE NEQUI → Pendiente, confianza 30% (dead code — interceptado por BC-F3-1)
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_transferencia_nequi"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5496,
            cuenta_credito=banco_origen,
            confianza=0.30,
            requiere_confirmacion=True,
            razon="Transferencia desde Nequi → Puede ser cobro cartera o traslado",
            categoria="BC_PENDIENTE"
        )

    # BC-11. PAGO PSE Banco Davivienda → Pendiente, confianza 25%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_pago_pse_davivienda"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5496,
            cuenta_credito=banco_origen,
            confianza=0.25,
            requiere_confirmacion=True,
            razon="Pago PSE Davivienda → Requiere contexto (pago a quién)",
            categoria="BC_PENDIENTE"
        )

    # BC-F3-2. CONSIGNACION CORRESPONSAL CB → Cobro cartera (5327), confianza 80%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_cobro_cartera_corresponsal"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5327,
            confianza=0.80,
            requiere_confirmacion=False,
            razon="Consignación Corresponsal CB → Cobro cartera (Créditos Directos Roddos)",
            categoria="BC_COBRO_CARTERA"
        )

    # BC-12. CONSIGNACION CORRESPONSAL CB → Pendiente ingreso, confianza 30% (dead code — interceptado por BC-F3-2)
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_consignacion_corresponsal"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5496,
            confianza=0.30,
            requiere_confirmacion=True,
            razon="Consignación Corresponsal CB → Requiere identificación del origen",
            categoria="BC_PENDIENTE"
        )

    # ── FASE 3: NUEVAS REGLAS MATRICIALES ────────────────────────────────────────

    # BC-F3-3. PAGO LLAVE → Cobro cartera (5327), confianza 85%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_cobro_cartera_pago_llave"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5327,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Pago Llave → Cobro cartera (Créditos Directos Roddos)",
            categoria="BC_COBRO_CARTERA"
        )

    # BC-F3-4. K TRONIX → Tecnología (5484), confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_ktronix_tech"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=5376,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Compra K Tronix → Tecnología (equipo empleados)",
            categoria="BC_TECNOLOGIA"
        )

    # BC-F3-5. COMBUSTIBLE EDS → 5498, confianza 85%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_combustible"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5498,
            cuenta_credito=banco_origen,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Combustible EDS → Combustibles y lubricantes",
            categoria="BC_COMBUSTIBLE"
        )

    # BC-F3-6. PARQUEADERO → 5499, confianza 85%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_parqueadero"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5499,
            cuenta_credito=banco_origen,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Parqueadero → Transporte",
            categoria="BC_TRANSPORTE"
        )

    # BC-F3-7. MERCATELY → Tecnología (5484), confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_mercately"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=5376,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Mercately → Tecnología (plataforma WhatsApp)",
            categoria="BC_TECNOLOGIA"
        )

    # BC-F3-8. SERVICIOS BANCARIOS VARIOS → 5507, confianza 85%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_servicios_bancarios"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5507,
            cuenta_credito=banco_origen,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Servicios bancarios varios → Gastos bancarios",
            categoria="BC_GASTO_BANCARIO"
        )

    # BC-F3-9. CÁMARA DE COMERCIO → I&C (5478), confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_camara_comercio"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5478,
            cuenta_credito=5376,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Pago PSE Cámara de Comercio → Industria y Comercio",
            categoria="BC_ICA"
        )

    # BC-F3-10. PRÉSTAMO EMPLEADA MARY ALEXANDRA → CXC empleados (5332), confianza 95%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_prestamo_empleada_mary"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5332,
            cuenta_credito=banco_origen,
            confianza=0.95,
            requiere_confirmacion=False,
            razon="Abono préstamo Mary Suárez → CXC empleados (reduce saldo $17M)",
            categoria="BC_CXC_EMPLEADO"
        )

    # BC-F3-11. GASTOS PERSONALES FUNDADORES → 5413 Salarios por pagar (máxima prioridad vs BC-14/15)
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_gasto_personal_fundador"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5413,
            cuenta_credito=banco_origen,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Gasto personal fundador → 5413 Salarios por pagar (NO P&L)",
            categoria="BC_COMPENSACION_DIFERIDA"
        )

    # BC-13. COMPRA EN TIENDA D1 → CXC socio si es gasto personal, confianza 45%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_compra_d1"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.45,
            requiere_confirmacion=True,
            razon="Compra D1 → Posible gasto personal socio (requiere confirmación)",
            categoria="BC_CXC_SOCIO"
        )

    # BC-14. COMPRA EN UBER / RAPPI / MC DONALD / BURGER → Gasto personal socio CXC (5329), confianza 80%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_compra_personal"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.80,
            requiere_confirmacion=False,
            razon="Compra personal (Uber/Rappi/MC/Burger) → CXC Socio",
            categoria="BC_CXC_SOCIO"
        )

    # BC-15. COMPRA EN FONTANAR / OPTICA / CASA D BTA → Gasto personal socio CXC (5329), confianza 75%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_compra_personal_otros"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5329,
            cuenta_credito=banco_origen,
            confianza=0.75,
            requiere_confirmacion=False,
            razon="Compra personal (Fontanar/Optica/Casa) → CXC Socio",
            categoria="BC_CXC_SOCIO"
        )

    # BC-16. TRANSFERENCIA CTA SUC VIRTUAL — lógica condicional por monto
    # Si monto < $3.000.000 → cobro cartera (5327)
    # Si monto >= $5.000.000 → préstamo socio a RODDOS (5413)
    # Zona gris $3M-$5M → requiere confirmación
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_transferencia_cta_virtual"]["palabras_clave"]):
        if monto < 3_000_000:
            return ClasificacionResult(
                cuenta_debito=banco_origen,
                cuenta_credito=5327,
                confianza=0.80,
                requiere_confirmacion=False,
                razon=f"Transferencia CTA Suc Virtual (${monto:,.0f} < $3M) → Cobro cartera",
                categoria="BC_COBRO_CARTERA"
            )
        elif monto >= 5_000_000:
            return ClasificacionResult(
                cuenta_debito=banco_origen,
                cuenta_credito=5413,
                confianza=0.80,
                requiere_confirmacion=True,
                razon=f"Transferencia CTA Suc Virtual (${monto:,.0f} >= $5M) → Préstamo socio a RODDOS",
                categoria="BC_PRESTAMO_SOCIO"
            )
        else:
            return ClasificacionResult(
                cuenta_debito=banco_origen,
                cuenta_credito=5496,
                confianza=0.40,
                requiere_confirmacion=True,
                razon=f"Transferencia CTA Suc Virtual (${monto:,.0f} zona gris $3M-$5M) → Requiere confirmación",
                categoria="BC_PENDIENTE"
            )

    # BC-17. PAGO PSE EMPRESA DE TELECOMUN → Telecomunicaciones (5487), confianza 85%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_pago_telecom"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5487,
            cuenta_credito=5376,
            confianza=0.85,
            requiere_confirmacion=False,
            razon="Pago PSE Empresa de Telecomunicaciones → Telecomunicaciones",
            categoria="BC_TELECOM"
        )

    # BC-18. PAGO PSE GOU PAYMENTS → Pendiente, confianza 30%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_pago_gou"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5496,
            cuenta_credito=banco_origen,
            confianza=0.30,
            requiere_confirmacion=True,
            razon="Pago PSE Gou Payments → Por definir, requiere contexto",
            categoria="BC_PENDIENTE"
        )

    # 15. FALLBACK — ASEO/CAFETERÍA (cuenta genérica)
    return ClasificacionResult(
        cuenta_debito=5496,
        cuenta_credito=5376,
        confianza=0.35,
        requiere_confirmacion=True,
        razon="No clasificado — usar fallback genérico (aseo/cafetería)",
        categoria="PENDIENTE"
    )


def validar_cuentas_alegra(cuenta_id: int) -> bool:
    """Valida que la cuenta existe y es de tipo movement."""
    todas_cuentas = {
        **CUENTAS_ACTIVOS,
        **CUENTAS_PASIVOS,
        **CUENTAS_INGRESOS,
        **CUENTAS_GASTOS,
        **CUENTAS_COSTOS,
    }
    return cuenta_id in [c["id"] for c in todas_cuentas.values()]


def obtener_nombre_cuenta(cuenta_id: int) -> str:
    """Retorna el nombre de una cuenta Alegra por su ID."""
    todas_cuentas = {
        **CUENTAS_ACTIVOS,
        **CUENTAS_PASIVOS,
        **CUENTAS_INGRESOS,
        **CUENTAS_GASTOS,
        **CUENTAS_COSTOS,
    }
    for cuenta in todas_cuentas.values():
        if cuenta["id"] == cuenta_id:
            return cuenta["nombre"]
    return f"Cuenta {cuenta_id} (desconocida)"


# ══════════════════════════════════════════════════════════════════════════════
# AmbiguousMovementHandler — Resolución Conversacional vía Mercately WhatsApp
# ══════════════════════════════════════════════════════════════════════════════

from enum import Enum
from typing import List


class EstadoResolucion(Enum):
    """Estados posibles de una transacción ambigua."""
    PENDIENTE = "pendiente"           # Esperando respuesta de usuario
    CONFIRMADA = "confirmada"         # Usuario confirmó clasificación
    RECHAZADA = "rechazada"          # Usuario rechazó, necesita reclasificación
    RESUELTA = "resuelta"            # Clasificación final enviada a Alegra
    ABANDONADA = "abandonada"        # Timeout o error en conversación


@dataclass
class MovimientoAmbiguo:
    """Movimiento bancario que requiere confirmación manual."""
    id: str                           # UUID único
    monto: float
    descripcion: str
    proveedor: str
    banco_origen: int
    fecha_movimiento: str             # ISO format

    # Clasificaciones propuestas
    cuenta_debito_sugerida: int
    cuenta_credito_sugerida: Optional[int]
    confianza: float
    razon_ambiguedad: str

    # Estado de resolución
    estado: EstadoResolucion = EstadoResolucion.PENDIENTE
    telefono_usuario: Optional[str] = None
    conversation_id: Optional[str] = None  # Mercately conversation ID

    # Historial de intentos
    intentos_whatsapp: int = 0
    fecha_creacion: str = ""
    fecha_ultimo_intento: Optional[str] = None
    fecha_resolucion: Optional[str] = None

    # Clasificaciones alternativas consideradas
    alternativas: List[dict] = None   # [{"cuenta_debito": 5X, "confianza": 0.X, "razon": "..."}, ...]

    # Resolución final
    cuenta_debito_final: Optional[int] = None
    cuenta_credito_final: Optional[int] = None
    notas_resolucion: str = ""


class AmbiguousMovementHandler:
    """
    Maneja la resolución de transacciones contables ambiguas mediante:
    1. Detección de clasificaciones de baja confianza
    2. Almacenamiento en contabilidad_pendientes (MongoDB)
    3. Iniciación de conversaciones WhatsApp vía Mercately
    4. Procesamiento de respuestas de usuario
    5. Escalamiento a manual si necesario
    """

    def __init__(self, db_instance):
        """
        Args:
            db_instance: Instancia de MongoDB client (del módulo database.py)
        """
        self.db = db_instance
        self.logger = logging.getLogger(f"{__name__}.AmbiguousMovementHandler")
        self.CONFIANZA_MIN_AUTOMATICO = 0.70  # Debajo de esto requiere confirmación
        self.TIMEOUT_HORAS = 24
        self.MAX_INTENTOS = 3

    async def detectar_y_procesar(
        self,
        movimiento_id: str,
        monto: float,
        descripcion: str,
        proveedor: str,
        banco_origen: int,
        clasificacion: ClasificacionResult,
        telefono_usuario: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Detecta si una clasificación es ambigua y la procesa.

        Returns:
            (es_ambigua, movement_tracking_id)
            - Si es_ambigua=True, necesita confirmación del usuario
            - Si es_ambigua=False, se puede enviar directamente a Alegra
        """
        es_ambigua = (
            clasificacion.confianza < self.CONFIANZA_MIN_AUTOMATICO
            or clasificacion.requiere_confirmacion
        )

        if not es_ambigua:
            return False, None

        # Almacenar como movimiento pendiente
        movimiento_ambiguo = MovimientoAmbiguo(
            id=movimiento_id,
            monto=monto,
            descripcion=descripcion,
            proveedor=proveedor,
            banco_origen=banco_origen,
            fecha_movimiento=datetime.now(timezone.utc).isoformat(),
            cuenta_debito_sugerida=clasificacion.cuenta_debito,
            cuenta_credito_sugerida=clasificacion.cuenta_credito,
            confianza=clasificacion.confianza,
            razon_ambiguedad=clasificacion.razon,
            telefono_usuario=telefono_usuario,
            fecha_creacion=datetime.now(timezone.utc).isoformat(),
            alternativas=[],  # Will be populated if multiple options
        )

        try:
            await self.db.contabilidad_pendientes.insert_one(
                self._to_dict(movimiento_ambiguo)
            )
            self.logger.info(f"Movimiento ambiguo almacenado: {movimiento_id} (confianza: {clasificacion.confianza})")

            # Intentar enviar WhatsApp si hay teléfono disponible
            if telefono_usuario:
                success = await self.enviar_solicitud_whatsapp(movimiento_ambiguo)
                if success:
                    return True, movimiento_id
                else:
                    self.logger.warning(f"No se pudo enviar WhatsApp para {movimiento_id}")
            else:
                self.logger.info(f"Sin teléfono de usuario para {movimiento_id}, pendiente de contacto manual")

            return True, movimiento_id

        except Exception as e:
            self.logger.error(f"Error al procesar movimiento ambiguo {movimiento_id}: {e}")
            return False, None

    async def enviar_solicitud_whatsapp(self, movimiento: MovimientoAmbiguo) -> bool:
        """
        Envía un mensaje WhatsApp vía Mercately solicitando confirmación.

        Usa credenciales desde MongoDB (mercately_config.api_key y .phone_number).
        Si no hay teléfono configurado, retorna False sin intentar.

        Formato del mensaje:
        ---
        📊 CONFIRMACIÓN DE CLASIFICACIÓN CONTABLE

        Transacción:
        • Monto: $X,XXX,XXX
        • Descripción: [descripción]
        • Proveedor: [nombre]

        Clasificación Sugerida:
        • Cuenta: [cuenta_debito_nombre]
        • Confianza: XX%

        ¿Confirmas esta clasificación?
        Responde: SI o NO
        ---
        """
        try:
            # Leer configuración desde MongoDB (no hardcodeado)
            cfg = await self.db.mercately_config.find_one({}, {"_id": 0})
            if not cfg or not cfg.get("api_key"):
                self.logger.warning(f"No hay API key Mercately configurada — no se envía WhatsApp para {movimiento.id}")
                return False

            api_key = cfg.get("api_key")
            # Usar número de usuario si está disponible, sino el número base
            phone_to = movimiento.telefono_usuario or cfg.get("phone_number")
            if not phone_to:
                self.logger.warning(f"No hay número de teléfono configurado para {movimiento.id}")
                return False

            nombre_cuenta = obtener_nombre_cuenta(movimiento.cuenta_debito_sugerida)
            confianza_pct = int(movimiento.confianza * 100)

            mensaje = f"""📊 CONFIRMACIÓN DE CLASIFICACIÓN CONTABLE

Transacción:
• Monto: ${movimiento.monto:,.0f}
• Descripción: {movimiento.descripcion}
• Proveedor: {movimiento.proveedor or 'N/A'}

Clasificación Sugerida:
• Cuenta: {nombre_cuenta}
• Confianza: {confianza_pct}%

¿Confirmas esta clasificación?
Responde: SI o NO"""

            # Enviar via Mercately API
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.mercately.com/api/v1/customers/send_message",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"phone": phone_to, "message": mensaje},
                )

            if resp.status_code not in (200, 201, 202):
                self.logger.error(
                    f"Mercately error enviando WhatsApp para {movimiento.id}: HTTP {resp.status_code}"
                )
                return False

            movimiento.intentos_whatsapp += 1
            movimiento.fecha_ultimo_intento = datetime.now(timezone.utc).isoformat()

            # Actualizar registro en MongoDB
            await self.db.contabilidad_pendientes.update_one(
                {"id": movimiento.id},
                {
                    "$set": {
                        "intentos_whatsapp": movimiento.intentos_whatsapp,
                        "fecha_ultimo_intento": movimiento.fecha_ultimo_intento,
                        "estado": EstadoResolucion.PENDIENTE.value,
                    }
                },
            )

            self.logger.info(
                f"WhatsApp enviado via Mercately para {movimiento.id} "
                f"(intento {movimiento.intentos_whatsapp}) a {phone_to[-4:]}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error al enviar WhatsApp para {movimiento.id}: {str(e)[:100]}")
            return False

    async def procesar_respuesta_whatsapp(
        self,
        movimiento_id: str,
        respuesta_usuario: str,
        telefono_usuario: str,
    ) -> bool:
        """
        Procesa la respuesta del usuario al mensaje WhatsApp de confirmación.

        Args:
            movimiento_id: ID del movimiento ambiguo
            respuesta_usuario: Texto de la respuesta ("SI", "NO", etc.)
            telefono_usuario: Teléfono desde el que respondió

        Returns:
            True si se procesó exitosamente
        """
        movimiento = await self.db.contabilidad_pendientes.find_one(
            {"id": movimiento_id},
            {"_id": 0}
        )

        if not movimiento:
            self.logger.warning(f"Movimiento no encontrado: {movimiento_id}")
            return False

        # Normalizar respuesta
        respuesta_normalizada = respuesta_usuario.lower().strip()
        es_confirmacion = any(
            palabra in respuesta_normalizada
            for palabra in ["si", "sí", "yes", "confirmar", "confirm", "ok", "dale"]
        )
        es_rechazo = any(
            palabra in respuesta_normalizada
            for palabra in ["no", "cancelar", "cancel", "rechazar"]
        )

        ahora = datetime.now(timezone.utc).isoformat()

        if es_confirmacion:
            # Marcar como confirmada
            await self.db.contabilidad_pendientes.update_one(
                {"id": movimiento_id},
                {
                    "$set": {
                        "estado": EstadoResolucion.CONFIRMADA.value,
                        "cuenta_debito_final": movimiento.get("cuenta_debito_sugerida"),
                        "cuenta_credito_final": movimiento.get("cuenta_credito_sugerida"),
                        "notas_resolucion": f"Confirmado por usuario vía WhatsApp",
                        "fecha_resolucion": ahora,
                    }
                },
            )
            self.logger.info(f"Movimiento {movimiento_id} confirmado por usuario")
            return True

        elif es_rechazo:
            # Marcar como rechazada, escalar a manual
            await self.db.contabilidad_pendientes.update_one(
                {"id": movimiento_id},
                {
                    "$set": {
                        "estado": EstadoResolucion.RECHAZADA.value,
                        "notas_resolucion": f"Rechazado por usuario. Respuesta: {respuesta_usuario}",
                        "fecha_resolucion": ahora,
                    }
                },
            )
            self.logger.info(f"Movimiento {movimiento_id} rechazado por usuario — Escalando a manual")
            return True

        else:
            # Respuesta no clara, intentar nuevamente
            if movimiento.get("intentos_whatsapp", 0) < self.MAX_INTENTOS:
                await self.db.contabilidad_pendientes.update_one(
                    {"id": movimiento_id},
                    {
                        "$set": {
                            "fecha_ultimo_intento": ahora,
                        }
                    },
                )
                self.logger.info(f"Respuesta no clara para {movimiento_id}, pendiente de aclaración")
            else:
                await self.db.contabilidad_pendientes.update_one(
                    {"id": movimiento_id},
                    {
                        "$set": {
                            "estado": EstadoResolucion.ABANDONADA.value,
                            "notas_resolucion": f"Timeout: {self.MAX_INTENTOS} intentos sin confirmación clara",
                            "fecha_resolucion": ahora,
                        }
                    },
                )
                self.logger.warning(f"Movimiento {movimiento_id} abandonado después de {self.MAX_INTENTOS} intentos")

            return False

    async def obtener_pendientes(
        self,
        estado: Optional[EstadoResolucion] = None,
    ) -> List[dict]:
        """
        Obtiene lista de movimientos pendientes con estado opcional.

        Args:
            estado: Filtrar por EstadoResolucion (None = todos)

        Returns:
            Lista de movimientos pendientes
        """
        query = {}
        if estado:
            query["estado"] = estado.value

        movimientos = await self.db.contabilidad_pendientes.find(
            query,
            {"_id": 0}
        ).to_list(None)

        return movimientos or []

    async def obtener_movimiento(self, movimiento_id: str) -> Optional[dict]:
        """Obtiene detalles de un movimiento ambiguo específico."""
        return await self.db.contabilidad_pendientes.find_one(
            {"id": movimiento_id},
            {"_id": 0}
        )

    async def marcar_resuelto(
        self,
        movimiento_id: str,
        cuenta_debito_final: int,
        cuenta_credito_final: Optional[int],
        notas: str = "",
    ) -> bool:
        """
        Marca un movimiento como resuelto después de ser enviado a Alegra.

        Args:
            movimiento_id: ID del movimiento
            cuenta_debito_final: Cuenta débito final usada
            cuenta_credito_final: Cuenta crédito final usada
            notas: Notas sobre la resolución

        Returns:
            True si se actualizó exitosamente
        """
        try:
            result = await self.db.contabilidad_pendientes.update_one(
                {"id": movimiento_id},
                {
                    "$set": {
                        "estado": EstadoResolucion.RESUELTA.value,
                        "cuenta_debito_final": cuenta_debito_final,
                        "cuenta_credito_final": cuenta_credito_final,
                        "fecha_resolucion": datetime.now(timezone.utc).isoformat(),
                        "notas_resolucion": notas,
                    }
                },
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Error al marcar resuelto {movimiento_id}: {e}")
            return False

    async def limpiar_antiguos(self, horas: int = None) -> int:
        """
        Elimina movimientos pendientes expirados (sin resolver después de N horas).

        Args:
            horas: Horas de expiración (default: TIMEOUT_HORAS)

        Returns:
            Número de registros eliminados
        """
        horas = horas or self.TIMEOUT_HORAS
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=horas)
        cutoff_iso = cutoff_time.isoformat()

        result = await self.db.contabilidad_pendientes.delete_many(
            {
                "estado": EstadoResolucion.PENDIENTE.value,
                "fecha_creacion": {"$lt": cutoff_iso},
            }
        )

        if result.deleted_count > 0:
            self.logger.info(f"Limpiados {result.deleted_count} movimientos expirados (>{horas} horas)")

        return result.deleted_count

    def _to_dict(self, movimiento: MovimientoAmbiguo) -> dict:
        """Convierte MovimientoAmbiguo a diccionario para MongoDB."""
        return {
            "id": movimiento.id,
            "monto": movimiento.monto,
            "descripcion": movimiento.descripcion,
            "proveedor": movimiento.proveedor,
            "banco_origen": movimiento.banco_origen,
            "fecha_movimiento": movimiento.fecha_movimiento,
            "cuenta_debito_sugerida": movimiento.cuenta_debito_sugerida,
            "cuenta_credito_sugerida": movimiento.cuenta_credito_sugerida,
            "confianza": movimiento.confianza,
            "razon_ambiguedad": movimiento.razon_ambiguedad,
            "estado": movimiento.estado.value,
            "telefono_usuario": movimiento.telefono_usuario,
            "conversation_id": movimiento.conversation_id,
            "intentos_whatsapp": movimiento.intentos_whatsapp,
            "fecha_creacion": movimiento.fecha_creacion,
            "fecha_ultimo_intento": movimiento.fecha_ultimo_intento,
            "fecha_resolucion": movimiento.fecha_resolucion,
            "alternativas": movimiento.alternativas or [],
            "cuenta_debito_final": movimiento.cuenta_debito_final,
            "cuenta_credito_final": movimiento.cuenta_credito_final,
            "notas_resolucion": movimiento.notas_resolucion,
        }


# ══════════════════════════════════════════════════════════════════════════════
# BUILD 23 — F2 CHAT TRANSACCIONAL: FUNCIONES HELPER PARA GENERACIÓN DE ASIENTOS
# ══════════════════════════════════════════════════════════════════════════════

def calcular_retenciones(
    tipo_proveedor: str = "PN",        # PN | PJ
    tipo_gasto: str = "servicios",     # arrendamiento | honorarios | servicios | compras | transporte
    monto_bruto: float = 0,
    es_autoretenedor: bool = False,
    aplica_iva: bool = False,
    aplica_reteica: bool = False,
) -> dict:
    """
    Calcula automáticamente ReteFuente y ReteICA según el tipo de gasto.

    Args:
        tipo_proveedor: "PN" (Persona Natural) | "PJ" (Persona Jurídica)
        tipo_gasto: tipo de gasto a clasificar
        monto_bruto: monto sin retenciones
        es_autoretenedor: si el proveedor es autoretenedor (ej: Auteco)
        aplica_iva: si aplica IVA sobre el monto
        aplica_reteica: si aplica ReteICA en Bogotá

    Returns:
        dict con estructura:
        {
            "base": float,
            "iva_valor": float,
            "retefuente_valor": float,
            "retefuente_pct": float,
            "retefuente_tipo": str,
            "reteica_valor": float,
            "reteica_pct": float,
            "total_retenciones": float,
            "neto_a_pagar": float,
            "advertencias": list
        }
    """
    UVT_2025 = 49799
    UMBRAL_SERVICIOS = 4 * UVT_2025  # $199.196
    UMBRAL_COMPRAS = 27 * UVT_2025   # $1.344.573
    RETEICA_INDUSTRIA = 0.00414       # 0.414% para comercio de motos (RODDOS)

    # Inicializar valores
    base = monto_bruto
    iva_valor = 0
    retefuente_valor = 0
    retefuente_pct = 0
    retefuente_tipo = ""
    reteica_valor = 0
    reteica_pct = 0
    advertencias = []

    # Calcular IVA si aplica
    if aplica_iva:
        iva_valor = monto_bruto * 0.19
        base = monto_bruto + iva_valor

    # Determinar ReteFuente según tipo de gasto
    if not es_autoretenedor:
        if tipo_gasto == "honorarios":
            retefuente_pct = 0.11 if tipo_proveedor == "PJ" else 0.10
            retefuente_tipo = f"honorarios_{tipo_proveedor.lower()}"
            retefuente_valor = monto_bruto * retefuente_pct

        elif tipo_gasto == "arrendamiento":
            retefuente_pct = 0.035
            retefuente_tipo = "arrendamiento"
            retefuente_valor = monto_bruto * retefuente_pct

        elif tipo_gasto == "servicios":
            if monto_bruto >= UMBRAL_SERVICIOS:
                retefuente_pct = 0.04
                retefuente_tipo = "servicios"
                retefuente_valor = monto_bruto * retefuente_pct
            else:
                advertencias.append(f"⚠️ Servicios < ${UMBRAL_SERVICIOS:,.0f}: ReteFuente no aplica")

        elif tipo_gasto == "compras":
            if monto_bruto >= UMBRAL_COMPRAS:
                retefuente_pct = 0.025
                retefuente_tipo = "compras"
                retefuente_valor = monto_bruto * retefuente_pct
            else:
                advertencias.append(f"⚠️ Compras < ${UMBRAL_COMPRAS:,.0f}: ReteFuente no aplica")

        elif tipo_gasto == "transporte":
            if monto_bruto >= UMBRAL_SERVICIOS:
                retefuente_pct = 0.035
                retefuente_tipo = "transporte"
                retefuente_valor = monto_bruto * retefuente_pct
    else:
        advertencias.append("⚠️ Proveedor es autoretenedor: ReteFuente no aplica")

    # Calcular ReteICA si aplica (0.414% en Bogotá)
    if aplica_reteica:
        reteica_valor = monto_bruto * RETEICA_INDUSTRIA
        reteica_pct = RETEICA_INDUSTRIA

    total_retenciones = retefuente_valor + reteica_valor
    neto_a_pagar = monto_bruto - total_retenciones

    return {
        "base": base,
        "iva_valor": iva_valor,
        "retefuente_valor": retefuente_valor,
        "retefuente_pct": retefuente_pct,
        "retefuente_tipo": retefuente_tipo,
        "reteica_valor": reteica_valor,
        "reteica_pct": reteica_pct,
        "total_retenciones": total_retenciones,
        "neto_a_pagar": neto_a_pagar,
        "advertencias": advertencias,
    }


def formatear_retenciones_para_prompt(retenciones: dict) -> str:
    """
    Formatea el dict de retenciones en texto legible para mostrar al usuario.
    """
    lines = []

    if retenciones.get("iva_valor", 0) > 0:
        lines.append(f"  • IVA (19%): ${retenciones['iva_valor']:,.2f}")

    if retenciones.get("retefuente_valor", 0) > 0:
        tipo = retenciones.get("retefuente_tipo", "ReteFuente")
        pct = retenciones.get("retefuente_pct", 0) * 100
        lines.append(f"  • {tipo.title()} ({pct:.1f}%): ${retenciones['retefuente_valor']:,.2f}")

    if retenciones.get("reteica_valor", 0) > 0:
        pct = retenciones.get("reteica_pct", 0) * 1000
        lines.append(f"  • ReteICA ({pct:.2f}‰): ${retenciones['reteica_valor']:,.2f}")

    for adv in retenciones.get("advertencias", []):
        lines.append(f"  • {adv}")

    base_section = f"Base: ${retenciones.get('base', 0):,.2f}\n"
    retenciones_section = "Retenciones:\n" + "\n".join(lines) if lines else ""
    total_section = f"\nTotal Retenciones: ${retenciones.get('total_retenciones', 0):,.2f}"
    neto_section = f"Neto a Pagar: ${retenciones.get('neto_a_pagar', 0):,.2f}"

    return base_section + retenciones_section + total_section + "\n" + neto_section


# ══════════════════════════════════════════════════════════════════════════════
# CLASIFICADOR DE GASTOS PARA CHAT TRANSACCIONAL (Phase 04 — CHAT-01 a CHAT-05)
# ══════════════════════════════════════════════════════════════════════════════

# Autoretenedores conocidos — NUNCA aplicar ReteFuente (CLAUDE.md)
AUTORETENEDORES_NIT = {"860024781"}  # Auteco Kawasaki

# Socios RODDOS S.A.S. — CXC socios (5329), NUNCA gasto operativo (CLAUDE.md)
SOCIOS_CC = {"80075452", "80086601"}  # Andrés San Juan, Iván Echeverri


def clasificar_gasto_chat(
    descripcion: str,
    proveedor: str = "",
    nit: str = "",
    monto: float = 0,
) -> dict:
    """
    Clasifica un gasto descrito en lenguaje natural (chat) usando la matriz REGLAS_CLASIFICACION.

    Retorna un dict con:
        tipo_gasto: str          — arrendamiento | honorarios | servicios | compras | socio | ...
        cuenta_debito: int       — ID Alegra de la cuenta de gasto
        cuenta_credito: int      — ID Alegra de la CXP (5376 default)
        es_autoretenedor: bool   — True si NIT está en AUTORETENEDORES_NIT (Auteco)
        es_socio: bool           — True si NIT/CC está en SOCIOS_CC (Andrés, Iván)
        aplica_reteica: bool     — True siempre (Bogotá), False solo para socios
        confianza: float         — 0-1
        razon: str               — Explicación de la clasificación

    REGLAS INAMOVIBLES (CLAUDE.md):
        - Fallback cuenta_debito: 5493 (Gastos Generales), NUNCA 5495
        - AUTORETENEDORES_NIT = {"860024781"} → es_autoretenedor=True, nunca ReteFuente
        - SOCIOS_CC = {"80075452", "80086601"} → es_socio=True, cuenta_debito=5329, nunca gasto operativo
    """
    desc_lower = descripcion.lower()
    prov_lower = proveedor.lower()
    nit_clean = nit.strip()

    # ── PASO 1: Verificar si es socio (mayor prioridad) ────────────────────
    es_socio = nit_clean in SOCIOS_CC
    if not es_socio:
        # También verificar por nombre del proveedor en REGLAS_CLASIFICACION["gasto_socio"]
        socio_proveedores = REGLAS_CLASIFICACION.get("gasto_socio", {}).get("proveedores", [])
        es_socio = any(sp in prov_lower for sp in socio_proveedores)

    if es_socio:
        return {
            "tipo_gasto": "socio",
            "cuenta_debito": 5329,
            "cuenta_credito": 5376,
            "es_autoretenedor": False,
            "es_socio": True,
            "aplica_reteica": False,
            "confianza": 0.95,
            "razon": f"Proveedor identificado como socio RODDOS — CXC socios (5329)",
        }

    # ── PASO 2: Verificar si es autoretenedor ─────────────────────────────
    es_autoretenedor = nit_clean in AUTORETENEDORES_NIT

    # ── PASO 3: Detectar honorarios (persona natural o jurídica) ──────────
    if "honorario" in desc_lower or "honorarios" in prov_lower:
        # Determinar PN vs PJ: jurídica si nombre tiene indicadores de empresa
        indicadores_pj = ["sas", "s.a.s", "ltda", "s.a.", "inversiones", "comercializadora",
                          "soluciones", "consultora", "grupo", "corp"]
        es_pj = any(ind in prov_lower for ind in indicadores_pj)
        # También si NIT empieza con 8 o 9 es PJ (NIT persona jurídica Colombia)
        if nit_clean and nit_clean[0] in ("8", "9"):
            es_pj = True

        cuenta_debito = 5476 if es_pj else 5475
        return {
            "tipo_gasto": "honorarios",
            "cuenta_debito": cuenta_debito,
            "cuenta_credito": 5376,
            "es_autoretenedor": es_autoretenedor,
            "es_socio": False,
            "aplica_reteica": True,
            "confianza": 0.90,
            "razon": f"Honorarios {'PJ (5476)' if es_pj else 'PN (5475)'} detectado en descripción",
        }

    # ── PASO 4: Detectar compras ──────────────────────────────────────────
    if any(kw in desc_lower for kw in ["compra", "repuesto", "compra de"]):
        return {
            "tipo_gasto": "compras",
            "cuenta_debito": 5493,
            "cuenta_credito": 5376,
            "es_autoretenedor": es_autoretenedor,
            "es_socio": False,
            "aplica_reteica": True,
            "confianza": 0.85,
            "razon": "Compra de bienes/repuestos detectada — cuenta 5493 (Gastos Generales)",
        }

    # ── PASO 5: Iterar REGLAS_CLASIFICACION por palabras_clave ────────────
    for tipo, regla in REGLAS_CLASIFICACION.items():
        if tipo in ("gasto_socio", "cxc_gasto_socio_andres", "cxc_gasto_socio_ivan",
                    "anticipo_nomina_andres"):
            continue  # Ya manejado en Paso 1

        palabras_clave = regla.get("palabras_clave", [])
        proveedores_regla = regla.get("proveedores", [])

        hit_kw = any(kw in desc_lower for kw in palabras_clave)
        hit_prov = any(p in prov_lower for p in proveedores_regla)

        if hit_kw or hit_prov:
            # Mapear tipo a tipo_gasto normalizado
            tipo_gasto_map = {
                "arriendo": "arrendamiento",
                "nomina": "nomina",
                "servicios_publicos": "servicios_publicos",
                "telecomunicaciones": "servicios",
                "tecnologia": "servicios",
                "publicidad": "publicidad",
                "cafeteria": "servicios",
                "papeleria": "servicios",
                "combustibles": "servicios",
                "transporte": "servicios",
                "intereses_rentistas": "servicios",
                "gmf": "servicios",
                "comisiones": "servicios",
                "gastos_bancarios": "servicios",
            }
            tipo_gasto = tipo_gasto_map.get(tipo, "servicios")

            return {
                "tipo_gasto": tipo_gasto,
                "cuenta_debito": regla["cuenta_debito"],
                "cuenta_credito": regla.get("cuenta_credito", 5376) or 5376,
                "es_autoretenedor": es_autoretenedor,
                "es_socio": False,
                "aplica_reteica": True,
                "confianza": regla.get("confianza_min", 0.75),
                "razon": f"Clasificado como '{tipo}' por {'palabras clave' if hit_kw else 'proveedor'}",
            }

    # ── PASO 6: Detectar servicios genéricos ──────────────────────────────
    if any(kw in desc_lower for kw in ["servicio", "asistencia", "mantenimiento", "soporte"]):
        return {
            "tipo_gasto": "servicios",
            "cuenta_debito": 5493,
            "cuenta_credito": 5376,
            "es_autoretenedor": es_autoretenedor,
            "es_socio": False,
            "aplica_reteica": True,
            "confianza": 0.70,
            "razon": "Servicio genérico — cuenta fallback 5493 (Gastos Generales)",
        }

    # ── PASO 7: Fallback — NUNCA 5495 (CLAUDE.md) ─────────────────────────
    return {
        "tipo_gasto": "servicios",
        "cuenta_debito": 5493,
        "cuenta_credito": 5376,
        "es_autoretenedor": es_autoretenedor,
        "es_socio": False,
        "aplica_reteica": True,
        "confianza": 0.50,
        "razon": "Clasificación por defecto — cuenta fallback 5493 (Gastos Generales, NUNCA 5495)",
    }

