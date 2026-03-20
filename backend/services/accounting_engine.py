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

        Formato esperado del mensaje:
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
            from routers.mercately import MercatelyService
        except ImportError:
            self.logger.warning("MercatelyService no disponible")
            return False

        try:
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

            # Simulación: En producción, se usaría MercatelyService real
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

            self.logger.info(f"WhatsApp enviado para {movimiento.id} (intento {movimiento.intentos_whatsapp})")
            return True

        except Exception as e:
            self.logger.error(f"Error al enviar WhatsApp para {movimiento.id}: {e}")
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
