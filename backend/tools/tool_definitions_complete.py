# SISMO BUILD 24 - Tool Use API Complete Implementation
# Agente Contador: 32 Tools Specification
# Categories: 1-EGRESOS, 2-INGRESOS, 3-CONCILIACION_BANCARIA, 4-CONCILIACION_INGRESOS_EGRESOS,
#            5-INVENTARIO, 6-CONSULTAS, 7-NOMINA_IMPUESTOS

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# CATEGORY 1: EGRESOS (6 tools)
# ============================================================================

class CrearCausacionInput(BaseModel):
    """Tool: crear_causacion — Gasto individual por chat conversacional"""
    descripcion: str = Field(..., description="Descripción natural del gasto: 'honorarios abogado $800k', 'arriendo mes', etc.")
    monto: float = Field(..., description="Monto total en COP")
    cuenta_id: Optional[int] = Field(None, description="ID Alegra (opcional — si no, motor matricial lo detecta)")
    requiere_confirmacion: bool = Field(default=True, description="Si True, propone antes de ejecutar")


class CrearCausacionMasivaInput(BaseModel):
    """Tool: crear_causacion_masiva — Lote CSV >10 registros con BackgroundTasks"""
    csv_path: str = Field(..., description="Ruta del archivo CSV (7 columnas obligatorias)")
    modo: str = Field(default="preview", description="'preview' (mostrar propuesta) o 'ejecutar' (background job)")
    anti_dup: bool = Field(default=True, description="Activar anti-duplicados 3 capas")


class RegistrarGastoPeriodoInput(BaseModel):
    """Tool: registrar_gasto_periodico — Suscripciones/arrendamiento automático"""
    tipo_gasto: str = Field(..., description="'arriendo', 'servicios_publicos', 'suscripcion', etc.")
    monto: float = Field(..., description="Monto mensual en COP")
    proveedor: str = Field(..., description="Nombre del proveedor o concepto")
    fecha_inicio: str = Field(..., description="YYYY-MM-DD")
    frecuencia: str = Field(default="mensual", description="'semanal', 'quincenal', 'mensual'")


class CrearNotaDebitoInput(BaseModel):
    """Tool: crear_nota_debito — Corrección manual por ND"""
    numero_original: str = Field(..., description="Número del asiento a corregir")
    razon: str = Field(..., description="Motivo de la corrección")
    ajuste_monto: float = Field(..., description="Monto del ajuste (negativo si es reversión)")


class RegistrarRetencionesInput(BaseModel):
    """Tool: registrar_retenciones — Manejo manual ReteFuente/ReteICA"""
    concepto: str = Field(..., description="'arriendo', 'servicios', 'honorarios_pn', 'honorarios_pj', etc.")
    monto_base: float = Field(..., description="Monto sobre el que se calcula")
    tasa_manual: Optional[float] = Field(None, description="Si se quiere override de la tasa automática")


class CrearAsientoManualInput(BaseModel):
    """Tool: crear_asiento_manual — Acceso directo para correcciones contables urgentes"""
    descripcion: str = Field(..., description="Descripción del asiento")
    debitos: List[Dict[str, float]] = Field(..., description="Lista de {'cuenta_id': monto}")
    creditos: List[Dict[str, float]] = Field(..., description="Lista de {'cuenta_id': monto}")
    fecha: Optional[str] = Field(None, description="YYYY-MM-DD (default: hoy)")


# ============================================================================
# CATEGORY 2: INGRESOS (5 tools)
# ============================================================================

class RegistrarIngresoNoOperacionalInput(BaseModel):
    """Tool: registrar_ingreso_no_operacional — Intereses, ventas recuperadas, otros"""
    tipo: str = Field(..., description="'intereses_bancarios', 'venta_motos_recuperadas', 'otros_ingresos'")
    monto: float = Field(..., description="Monto en COP")
    descripcion: str = Field(..., description="Detalle del ingreso")
    fecha: Optional[str] = Field(None, description="YYYY-MM-DD (default: hoy)")


class RegistrarCuotaCarteraInput(BaseModel):
    """Tool: registrar_cuota_cartera — Pago de cuota (diferente a egresos)"""
    loanbook_id: str = Field(..., description="ID del loanbook: 'LB-2026-0012'")
    numero_cuota: int = Field(..., description="Cuota número")
    monto: float = Field(..., description="Monto pagado en COP")
    fecha_pago: Optional[str] = Field(None, description="YYYY-MM-DD (default: hoy)")


class RegistrarAbonoSocioInput(BaseModel):
    """Tool: registrar_abono_socio — Abono a CXC socios (Andrés/Iván)"""
    socio_cedula: str = Field(..., description="'80075452' (Andrés) o '80086601' (Iván)")
    monto: float = Field(..., description="Monto del abono en COP")
    banco_origen: Optional[str] = Field(None, description="BBVA/Bancolombia/Davivienda")


class RegistrarIngresoFinancieroInput(BaseModel):
    """Tool: registrar_ingreso_financiero — Intereses bancarios específicos"""
    banco: str = Field(..., description="BBVA / Bancolombia / Davivienda / Nequi")
    monto_interes: float = Field(..., description="Monto en COP")
    periodo: str = Field(..., description="'enero', 'febrero', etc. o YYYY-MM")


class RegistrarIngresoArrendamientoInput(BaseModel):
    """Tool: registrar_ingreso_arrendamiento — Subarriendo de espacio"""
    arrendatario: str = Field(..., description="Nombre del subarrendatario")
    monto_mensual: float = Field(..., description="Canon mensual en COP")
    fecha_inicio: str = Field(..., description="YYYY-MM-DD")


# ============================================================================
# CATEGORY 3: CONCILIACIÓN BANCARIA (6 tools)
# ============================================================================

class CrearCausacionDesdeExtratoInput(BaseModel):
    """Tool: crear_causacion_desde_extracto — Parsea BBVA/Bancolombia/Davivienda/Nequi"""
    extracto_path: str = Field(..., description="Ruta archivo .xlsx (formatos oficiales)")
    banco: str = Field(..., description="'BBVA' / 'Bancolombia' / 'Davivienda' / 'Nequi'")
    mes: str = Field(..., description="'enero' / 'febrero' / ... o YYYY-MM")
    modo: str = Field(default="preview", description="'preview' o 'ejecutar'")


class MarcarMovimientoClasificadoInput(BaseModel):
    """Tool: marcar_movimiento_clasificado — Anti-dup 3 capas"""
    movimiento_hash: str = Field(..., description="Hash MD5 del movimiento")
    cuenta_asignada: int = Field(..., description="ID Alegra de la cuenta")


class CrearReintentosMov ientosInput(BaseModel):
    """Tool: crear_reintentos_movimientos — Cola de reintentos cuando Alegra está caído"""
    movimiento_id: str = Field(..., description="ID del movimiento a reintentar")
    proxima_ejecucion: str = Field(..., description="ISO datetime: cuando reintentar")


class AuditarMovimientosPendientesInput(BaseModel):
    """Tool: auditar_movimientos_pendientes — Backlog modal 'Causar'"""
    banco: str = Field(..., description="Filtrar por banco (opcional)")
    confianza_minima: float = Field(default=0.70, description="Umbral de confianza (0-1)")


class SincronizarExtratoGlobal66Input(BaseModel):
    """Tool: sincronizar_extracto_global66 — Cron nocturno Global66"""
    mes: str = Field(..., description="Mes a sincronizar: YYYY-MM")
    forzar_reprocessamiento: bool = Field(default=False, description="Si True, ignora duplicados")


class ResolverDuplicadosBancariosInput(BaseModel):
    """Tool: resolver_duplicados_bancarios — Manual cuando motor falla"""
    hashes_duplicados: List[str] = Field(..., description="Lista de hashes a resolver")
    accion: str = Field(default="mantener_primero", description="'mantener_primero' / 'mantener_segundo' / 'eliminar_ambos'")


# ============================================================================
# CATEGORY 4: CONCILIACIÓN INGRESOS/EGRESOS (4 tools)
# ============================================================================

class ValidarCoberturGastoInput(BaseModel):
    """Tool: validar_cobertura_gasto — Verifica Alegra = MongoDB"""
    periodo: str = Field(..., description="'enero' / 'febrero' / ... o YYYY-MM")
    tolerancia_pesos: float = Field(default=100000.0, description="Diferencia máxima permitida")


class ReportarDesfaseContableInput(BaseModel):
    """Tool: reportar_desfase_contable — P&L vs caja"""
    periodo: str = Field(..., description="YYYY-MM")


class SincronizarCarteraAlegraInput(BaseModel):
    """Tool: sincronizar_cartera_alegra — Loanbook ↔ Alegra"""
    loanbook_id: Optional[str] = Field(None, description="Si None, sincroniza todos")


class AuditarBalanceCierreInput(BaseModel):
    """Tool: auditar_balance_cierre — Cierre mensual automático"""
    mes: str = Field(..., description="'enero' / 'febrero' / ... o YYYY-MM")
    generar_reporte: bool = Field(default=True, description="Si True, devuelve reporte en PDF")


# ============================================================================
# CATEGORY 5: INVENTARIO (4 tools)
# ============================================================================

class ActualizarMotoVendidaInput(BaseModel):
    """Tool: actualizar_moto_vendida — Cambio estado en inventario post-factura"""
    chasis_vin: str = Field(..., description="VIN del chasis")
    factura_id: str = Field(..., description="ID de factura de venta en Alegra")


class RegistrarEntregaMotoInput(BaseModel):
    """Tool: registrar_entrega_moto — Sync loanbook + estado"""
    loanbook_id: str = Field(..., description="LB-2026-XXXX")
    fecha_entrega: str = Field(..., description="YYYY-MM-DD")
    numero_placa: Optional[str] = Field(None, description="Si está disponible")


class ConsultarMotosDisponiblesInput(BaseModel):
    """Tool: consultar_motos_disponibles — Lectura"""
    modelo: Optional[str] = Field(None, description="Filtrar por modelo (p.ej. 'Raider')·")
    cantidad_minima: int = Field(default=1, description="Motos con stock >= este valor")


class SincronizarCompraAutecoInput(BaseModel):
    """Tool: sincronizar_compra_auteco — Bill → inventario_motos"""
    numero_factura_auteco: str = Field(..., description="Número factura Auteco")
    mes: str = Field(..., description="'enero' / 'febrero' / ...")


# ============================================================================
# CATEGORY 6: CONSULTAS (4 tools)
# ============================================================================

class ConsultarJournalsPeriodoInput(BaseModel):
    """Tool: consultar_journals_periodo — GET Alegra"""
    fecha_inicio: str = Field(..., description="YYYY-MM-DD")
    fecha_fin: str = Field(..., description="YYYY-MM-DD")
    cuenta_id: Optional[int] = Field(None, description="Filtrar por cuenta (opcional)")


class ConsultarCarteraClienteInput(BaseModel):
    """Tool: consultar_cartera_cliente — MongoDB loanbook"""
    cliente_nombre: Optional[str] = Field(None, description="Nombre del cliente")
    loanbook_id: Optional[str] = Field(None, description="O ID del loanbook")


class ConsultarSaldoSocioInput(BaseModel):
    """Tool: consultar_saldo_socio — CXC socios lectura"""
    socio_cedula: str = Field(..., description="'80075452' o '80086601'")


class GenerarReporteAuditorInput(BaseModel):
    """Tool: generar_reporte_auditor — Contabilidad auditada"""
    periodo: str = Field(..., description="YYYY-MM o 'trimestre-Q' p.ej. '2026-Q1'")
    formato: str = Field(default="pdf", description="'pdf' / 'xlsx'")


# ============================================================================
# CATEGORY 7: NÓMINA E IMPUESTOS (3 tools)
# ============================================================================

class RegistrarNominaInputMensual(BaseModel):
    """Tool: registrar_nomina_mensual — Anti-dup SHA256 mes+empleado"""
    mes: str = Field(..., description="YYYY-MM, p.ej. '2026-02'")
    nomina: List[Dict[str, Any]] = Field(..., description="Lista con {empleado, cedula, salario_base, extras, retenciones}")
    forzar_reprocess: bool = Field(default=False, description="Si True, ignora duplicados anteriores")


class CalcularRetencionesPayrollInput(BaseModel):
    """Tool: calcular_retenciones_payroll — SGSSS, retenciones"""
    salario_base: float = Field(..., description="Salario bruto en COP")
    tipo_empleado: str = Field(default="dependiente", description="'dependiente' / 'contratista'")
    periodo: str = Field(default="mensual", description="'mensual' / 'semestral'")


class ReportarObligacionesDianInput(BaseModel):
    """Tool: reportar_obligaciones_dian — IVA cuatrimestral + ReteFuente"""
    periodo_ini: str = Field(..., description="YYYY-MM-DD inicio cuatrimestre")
    periodo_fin: str = Field(..., description="YYYY-MM-DD fin cuatrimestre")
    generar_anexo: bool = Field(default=True, description="Si True, genera anexo para presentación")


# ============================================================================
# REGISTRY: Mapa de todos los 32 Tools
# ============================================================================

TOOL_DEFS = {
    # EGRESOS
    "crear_causacion": CrearCausacionInput,
    "crear_causacion_masiva": CrearCausacionMasivaInput,
    "registrar_gasto_periodico": RegistrarGastoPeriodoInput,
    "crear_nota_debito": CrearNotaDebitoInput,
    "registrar_retenciones": RegistrarRetencionesInput,
    "crear_asiento_manual": CrearAsientoManualInput,
    
    # INGRESOS
    "registrar_ingreso_no_operacional": RegistrarIngresoNoOperacionalInput,
    "registrar_cuota_cartera": RegistrarCuotaCarteraInput,
    "registrar_abono_socio": RegistrarAbonoSocioInput,
    "registrar_ingreso_financiero": RegistrarIngresoFinancieroInput,
    "registrar_ingreso_arrendamiento": RegistrarIngresoArrendamientoInput,
    
    # CONCILIACIÓN BANCARIA
    "crear_causacion_desde_extracto": CrearCausacionDesdeExtratoInput,
    "marcar_movimiento_clasificado": MarcarMovimientoClasificadoInput,
    "crear_reintentos_movimientos": CrearReintentosMov ientosInput,
    "auditar_movimientos_pendientes": AuditarMovimientosPendientesInput,
    "sincronizar_extracto_global66": SincronizarExtratoGlobal66Input,
    "resolver_duplicados_bancarios": ResolverDuplicadosBancariosInput,
    
    # CONCILIACIÓN INGRESOS/EGRESOS
    "validar_cobertura_gasto": ValidarCoberturGastoInput,
    "reportar_desfase_contable": ReportarDesfaseContableInput,
    "sincronizar_cartera_alegra": SincronizarCarteraAlegraInput,
    "auditar_balance_cierre": AuditarBalanceCierreInput,
    
    # INVENTARIO
    "actualizar_moto_vendida": ActualizarMotoVendidaInput,
    "registrar_entrega_moto": RegistrarEntregaMotoInput,
    "consultar_motos_disponibles": ConsultarMotosDisponiblesInput,
    "sincronizar_compra_auteco": SincronizarCompraAutecoInput,
    
    # CONSULTAS
    "consultar_journals_periodo": ConsultarJournalsPeriodoInput,
    "consultar_cartera_cliente": ConsultarCarteraClienteInput,
    "consultar_saldo_socio": ConsultarSaldoSocioInput,
    "generar_reporte_auditor": GenerarReporteAuditorInput,
    
    # NÓMINA E IMPUESTOS
    "registrar_nomina_mensual": RegistrarNominaInputMensual,
    "calcular_retenciones_payroll": CalcularRetencionesPayrollInput,
    "reportar_obligaciones_dian": ReportarObligacionesDianInput,
}

# Validación: 32 tools
assert len(TOOL_DEFS) == 32, f"Se esperaban 32 tools, se encontraron {len(TOOL_DEFS)}"

# Función de utilidad para obtener schema de un tool
def get_tool_schema(tool_name: str) -> Dict[str, Any]:
    """Retorna el schema JSON schema 7 de un tool para Anthropic API"""
    if tool_name not in TOOL_DEFS:
        raise ValueError(f"Tool {tool_name} no encontrado. Disponibles: {list(TOOL_DEFS.keys())}")
    
    model = TOOL_DEFS[tool_name]
    return model.model_json_schema()
