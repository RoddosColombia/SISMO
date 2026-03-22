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
    "caja_menor": {"id": 5311, "nombre": "Caja menor", "use": "movement"},
    "bancolombia_2029": {"id": 5314, "nombre": "Bancolombia 2029", "use": "movement"},
    "bancolombia_2540": {"id": 5315, "nombre": "Bancolombia 2540", "use": "movement"},
    "tarjeta_debito_9942": {"id": 5316, "nombre": "Tarjeta débito prepago 9942", "use": "movement"},
    "tarjeta_debito_6588": {"id": 5317, "nombre": "Tarjeta débito prepago 6588", "use": "movement"},
    "bbva_0210": {"id": 5318, "nombre": "BBVA 0210", "use": "movement"},
    "bbva_0212": {"id": 5319, "nombre": "BBVA 0212", "use": "movement"},
    "banco_bogota_047674460": {"id": 5321, "nombre": "Banco de Bogotá Ahorros 047674460", "use": "movement"},
    "davivienda_482": {"id": 5322, "nombre": "Banco Davivienda Sa cuenta ahorros 482", "use": "movement"},
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
        "palabras_clave": ["4x1000", "impuesto 4x1000", "gravamen", "gmf"],
        "cuenta_debito": 5509,
        "cuenta_credito": None,  # Se toma del banco de origen
        "confianza_min": 0.9,
    },

    # COMISIONES BANCARIAS
    "comisiones": {
        "palabras_clave": ["comision", "cargo bbva cash", "cuota manejo",
                           "cuota plan canal", "iva cuota plan"],
        "cuenta_debito": 5508,
        "cuenta_credito": None,
        "confianza_min": 0.85,
    },

    # GASTOS BANCARIOS
    "gastos_bancarios": {
        "palabras_clave": ["costo transferencia", "traslado dinero", "iva traslado"],
        "cuenta_debito": 5507,
        "cuenta_credito": None,
        "confianza_min": 0.8,
    },

    # GASTO SOCIO → CXC (5329) — NUNCA gasto operativo
    "gasto_socio": {
        "proveedores": ["andres sanjuan", "ivan echeverri", "sanjuan", "echeverri"],
        "palabras_clave": ["gasto socio", "anticipo nomina socio", "gasolina vehiculo",
                           "pico y placa", "gasto personal socio"],
        "cuenta_debito": 5329,
        "cuenta_credito": None,  # Banco de origen
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
        "cuenta_credito": None,
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
        "cuenta_credito": None,
        "confianza_min": 0.95,
    },

    # 2. CXC GASTO SOCIO IVAN — CXC socios (5329), confianza 95%
    "cxc_gasto_socio_ivan": {
        "palabras_clave": ["cxc gasto socio ivan", "gasto socio ivan"],
        "cuenta_debito": 5329,
        "cuenta_credito": None,
        "confianza_min": 0.95,
    },

    # 3. ANTICIPO NÓMINA ANDRES — CXC socios (5329), confianza 92%
    "anticipo_nomina_andres": {
        "palabras_clave": ["anticipo nomina andres"],
        "cuenta_debito": 5329,
        "cuenta_credito": None,
        "confianza_min": 0.92,
    },

    # 4. NÓMINA RODDOS — Sueldos y salarios (5462), confianza 92%
    "nomina_roddos": {
        "palabras_clave": ["nomina roddos"],
        "cuenta_debito": 5462,
        "cuenta_credito": None,
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
        "cuenta_credito": None,
        "confianza_min": 0.95,
    },

    # 7. TRASLADO CUENTAS PROPIAS O INTERNO — NO contabilizar, confianza 95%
    "traslado_interno": {
        "palabras_clave": ["traslado de la 212 a la 210", "traslado de dinero", "abono por domic traslado"],
        "cuenta_debito": 5535,  # Cuenta de control
        "cuenta_credito": None,
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
        "palabras_clave": ["abono por inter", "rendimientos financieros"],
        "cuenta_debito": None,  # Banco como débito
        "cuenta_credito": 5456,
        "confianza_min": 0.85,
    },

    # 12. PAGO PSE RECARGA NEQUI — Baja confianza, requiere contexto
    "pago_pse_nequi": {
        "palabras_clave": ["pago pse comerc recarga nequi"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": None,
        "confianza_min": 0.25,  # MUY baja confianza
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
        "cuenta_credito": None,
        "confianza_min": 0.92,
    },

    # 3. IVA CUOTA PLAN CANAL → Gasto bancario (5507), confianza 92%
    "bc_iva_cuota_plan": {
        "palabras_clave": ["iva cuota plan canal"],
        "cuenta_debito": 5507,
        "cuenta_credito": None,
        "confianza_min": 0.92,
    },

    # 4. CUOTA MANEJO TRJ DEB → Gasto bancario (5507), confianza 92%
    "bc_cuota_manejo_trj": {
        "palabras_clave": ["cuota manejo trj deb"],
        "cuenta_debito": 5507,
        "cuenta_credito": None,
        "confianza_min": 0.92,
    },

    # 5. AJUSTE INTERES AHORROS DB → Gasto financiero (5507), confianza 90%
    "bc_ajuste_interes_ahorros": {
        "palabras_clave": ["ajuste interes ahorros db"],
        "cuenta_debito": 5507,
        "cuenta_credito": None,
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
        "cuenta_credito": None,
        "confianza_min": 0.25,
    },

    # 10. TRANSFERENCIA DESDE NEQUI → Pendiente, confianza 30% (puede ser cobro cartera o traslado)
    "bc_transferencia_nequi": {
        "palabras_clave": ["transferencia desde nequi"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": None,
        "confianza_min": 0.30,
    },

    # 11. PAGO PSE Banco Davivienda → Pendiente, confianza 25% (requiere contexto)
    "bc_pago_pse_davivienda": {
        "palabras_clave": ["pago pse banco davivienda"],
        "cuenta_debito": 5496,  # Fallback
        "cuenta_credito": None,
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
        "cuenta_credito": None,
        "confianza_min": 0.45,
    },

    # 14. COMPRA EN UBER / RAPPI / MC DONALD / BURGER → Gasto personal socio CXC (5329), confianza 80%
    "bc_compra_personal": {
        "palabras_clave": ["compra en uber", "compra en rappi", "compra en mc donald", "compra en burger"],
        "cuenta_debito": 5329,  # CXC socio
        "cuenta_credito": None,
        "confianza_min": 0.80,
    },

    # 15. COMPRA EN FONTANAR / OPTICA / CASA D BTA → Gasto personal socio CXC (5329), confianza 75%
    "bc_compra_personal_otros": {
        "palabras_clave": ["compra en fontanar", "compra en optica", "compra en casa d bta"],
        "cuenta_debito": 5329,  # CXC socio
        "cuenta_credito": None,
        "confianza_min": 0.75,
    },

    # 16. TRANSFERENCIA CTA SUC VIRTUAL → Transferencia interna (5535), NO contabilizar, confianza 90%
    "bc_transferencia_cta_virtual": {
        "palabras_clave": ["transferencia cta suc virtual"],
        "cuenta_debito": 5535,
        "cuenta_credito": None,
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
        "cuenta_credito": None,
        "confianza_min": 0.30,
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
    desc_lower = descripcion.lower()
    prov_lower = (proveedor or "").lower()
    texto_combinado = f"{desc_lower} {prov_lower}"

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
            cuenta_credito=None,
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
    desc_check = texto_combinado
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

    # 9. SERVICIOS PÚBLICOS
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["servicios_publicos"]["palabras_clave"]):
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
            cuenta_credito=None,
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
            cuenta_debito=5496,
            cuenta_credito=5376,
            confianza=0.25,
            requiere_confirmacion=True,
            razon="Recarga NEQUI → Esperando contexto vía WhatsApp",
            categoria="RECARGA_NEQUI"
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

    # BC-10. TRANSFERENCIA DESDE NEQUI → Pendiente, confianza 30%
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

    # BC-12. CONSIGNACION CORRESPONSAL CB → Pendiente ingreso, confianza 30%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_consignacion_corresponsal"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=banco_origen,
            cuenta_credito=5496,
            confianza=0.30,
            requiere_confirmacion=True,
            razon="Consignación Corresponsal CB → Requiere identificación del origen",
            categoria="BC_PENDIENTE"
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

    # BC-16. TRANSFERENCIA CTA SUC VIRTUAL → Transferencia interna (5535), NO contabilizar, confianza 90%
    if any(kw in desc_check for kw in REGLAS_CLASIFICACION["bc_transferencia_cta_virtual"]["palabras_clave"]):
        return ClasificacionResult(
            cuenta_debito=5535,
            cuenta_credito=None,
            confianza=0.90,
            requiere_confirmacion=False,
            razon="Transferencia CTA Suc Virtual → NO contabilizar",
            categoria="BC_TRASLADO_INTERNO",
            es_transferencia_interna=True
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
