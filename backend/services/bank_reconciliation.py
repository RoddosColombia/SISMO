"""
bank_reconciliation.py — Parser para extractos bancarios de 4 bancos + clasificación automática.

Soporta:
  - Bancolombia (Excel, formato específico)
  - BBVA (Excel, diferentes columnas)
  - Davivienda (Excel, naturaleza C/D)
  - Nequi (Excel, tipo ingreso/egreso)

Flujo:
  1. Parsear extracto según banco
  2. Clasificar cada movimiento con accounting_engine
  3. Movimientos de confianza >= 0.7 → Crear journals en Alegra
  4. Movimientos de confianza < 0.7 → Guardar en contabilidad_pendientes
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from enum import Enum

import pandas as pd
from io import BytesIO
from alegra_service import AlegraService

logger = logging.getLogger(__name__)


class TipoMovimiento(Enum):
    """Tipos de movimiento bancario."""
    INGRESO = "ingreso"
    EGRESO = "egreso"


class Banco(Enum):
    """Bancos soportados."""
    BANCOLOMBIA = "bancolombia"
    BBVA = "bbva"
    DAVIVIENDA = "davivienda"
    NEQUI = "nequi"
    GLOBAL66 = "global66"


@dataclass
class MovimientoBancario:
    """Movimiento bancario parseado."""
    fecha: str                    # YYYY-MM-DD
    descripcion: str
    monto: float                 # Siempre positivo
    tipo: TipoMovimiento        # ingreso | egreso
    banco: Banco
    cuenta_banco_id: int         # ID de Alegra de la cuenta del banco
    referencia_original: str    # Campo original del extracto (para auditoría)
    proveedor: str = ""         # Nombre del proveedor/comercio (extraído de descripción)

    # Clasificación (se llena después)
    cuenta_debito_sugerida: Optional[int] = None
    cuenta_credito_sugerida: Optional[int] = None
    confianza: float = 0.0
    razon_clasificacion: str = ""
    requiere_confirmacion: bool = False
    es_transferencia_interna: bool = False  # Si es True, no contabilizar (traslado entre cuentas)


def _extraer_proveedor(descripcion: str) -> str:
    """Helper consolidado — unica fuente de verdad para extraccion de proveedor.

    Llama a accounting_engine.extract_proveedor y filtra el fallback.
    Retorna el nombre del proveedor o string vacio si no se identifica.
    NUNCA retorna desc[:30] truncado — eso interfiere con reglas de clasificacion.
    """
    from services.accounting_engine import extract_proveedor
    resultado = extract_proveedor(descripcion)
    # Si el resultado es simplemente la descripcion truncada (fallback),
    # retornar string vacio para que las reglas de clasificacion no hagan
    # match contra basura
    if resultado == descripcion.upper().strip()[:30].lower():
        logger.info(f"Proveedor no identificado en: '{descripcion[:50]}' (fallback filtrado)")
        return ""
    logger.info(f"Proveedor extraido: '{resultado}' de descripcion: '{descripcion[:50]}'")
    return resultado


class BancolombiParser:
    """Parser para extractos Bancolombia.

    Estructura:
    - Hoja: "Extracto"
    - Headers en fila índice 14
    - Datos desde fila índice 15
    - Columnas: FECHA (d/m), DESCRIPCIÓN, SUCURSAL, DCTO., VALOR, SALDO
    - FECHA formato: "1/01", "2/01" (sin año, agregar 2026)
    - VALOR: positivo=abono(ingreso), negativo=cargo(egreso)
    """
    HEADER_ROW = 14
    COL_FECHA = "FECHA"
    COL_DESCRIPCION = "DESCRIPCIÓN"
    COL_VALOR = "VALOR"
    CUENTA_ALEGRA = 5314  # Bancolombia 2029

    @staticmethod
    async def parsear(archivo_bytes: bytes) -> List[MovimientoBancario]:
        """Parsea extracto Bancolombia."""
        try:
            df = pd.read_excel(
                BytesIO(archivo_bytes),
                sheet_name="Extracto",
                header=BancolombiParser.HEADER_ROW,
            )

            movimientos = []
            for _, row in df.iterrows():
                try:
                    # Parseo robusto de fecha: soporta "1/01", "01/01", "15/01", etc.
                    fecha_raw = str(row[BancolombiParser.COL_FECHA]).strip()
                    try:
                        partes = fecha_raw.split("/")
                        if len(partes) == 2:
                            dia = partes[0].zfill(2)  # Rellenar con cero si es necesario
                            mes = partes[1].zfill(2)
                            fecha_str = f"2026-{mes}-{dia}"
                            # Validar la fecha
                            pd.to_datetime(fecha_str, format="%Y-%m-%d")
                        else:
                            fecha_str = "2026-01-01"
                            logger.warning(f"[Bancolombia] Formato de fecha inválido '{fecha_raw}', usando fallback 2026-01-01")
                    except:
                        fecha_str = "2026-01-01"
                        logger.warning(f"[Bancolombia] No se pudo parsear fecha '{fecha_raw}', usando fallback 2026-01-01")

                    descripcion = str(row[BancolombiParser.COL_DESCRIPCION]).strip().upper()
                    monto_raw = float(row[BancolombiParser.COL_VALOR])

                    # Positivo = abono (ingreso), negativo = cargo (egreso)
                    tipo = TipoMovimiento.INGRESO if monto_raw > 0 else TipoMovimiento.EGRESO
                    monto = abs(monto_raw)

                    # Extraer proveedor (helper consolidado — CONT-01)
                    proveedor = _extraer_proveedor(descripcion)

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=monto,
                        tipo=tipo,
                        banco=Banco.BANCOLOMBIA,
                        cuenta_banco_id=BancolombiParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto_raw}",
                        proveedor=proveedor,
                    ))
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"[Bancolombia] Error parseando fila: {e}")
                    continue

            logger.info(f"[Bancolombia] Parseados {len(movimientos)} movimientos (59 abonos, 128 cargos esperados)")
            return movimientos

        except Exception as e:
            logger.error(f"[Bancolombia] Error general: {e}")
            raise


class BBVAParser:
    """Parser para extractos BBVA."""
    SKIP_ROWS = 13  # Headers en fila 14 (índice 13)
    COL_FECHA = "FECHA DE OPERACIÓN"
    COL_DESCRIPCION = "CONCEPTO"
    COL_VALOR = "IMPORTE (COP)"
    CUENTA_ALEGRA = 5318  # BBVA 0210

    @staticmethod
    async def parsear(archivo_bytes: bytes) -> List[MovimientoBancario]:
        """Parsea extracto BBVA. Positivo=ingreso, negativo=egreso.

        Formato de fecha robusta: maneja "01-01-2026" y "1-01-2026" correctamente.
        """
        try:
            df = pd.read_excel(
                BytesIO(archivo_bytes),
                header=13,
            )

            movimientos = []
            for _, row in df.iterrows():
                try:
                    # Parseo robusto de fecha: soporta DD-MM-YYYY y D-MM-YYYY
                    fecha_raw = str(row[BBVAParser.COL_FECHA]).strip()
                    try:
                        fecha_dt = pd.to_datetime(fecha_raw, dayfirst=True)
                        fecha_str = fecha_dt.strftime("%Y-%m-%d")

                        # Validar que el año sea 2026
                        if not fecha_str.startswith("2026"):
                            partes = fecha_raw.split("-")
                            if len(partes) == 3:
                                fecha_str = f"2026-{partes[1].zfill(2)}-{partes[0].zfill(2)}"
                            else:
                                fecha_str = "2026-01-01"
                    except:
                        # Fallback: asumir 2026-01-01
                        fecha_str = "2026-01-01"
                        logger.warning(f"[BBVA] No se pudo parsear fecha '{fecha_raw}', usando fallback 2026-01-01")

                    descripcion = str(row[BBVAParser.COL_DESCRIPCION]).strip()
                    monto_raw = float(row[BBVAParser.COL_VALOR])

                    # Positivo = ingreso, negativo = egreso
                    tipo = TipoMovimiento.INGRESO if monto_raw > 0 else TipoMovimiento.EGRESO
                    monto = abs(monto_raw)

                    # Extraer proveedor (helper consolidado — CONT-01)
                    proveedor = _extraer_proveedor(descripcion)

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=monto,
                        tipo=tipo,
                        banco=Banco.BBVA,
                        cuenta_banco_id=BBVAParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto_raw}",
                        proveedor=proveedor,
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"[BBVA] Error parseando fila: {e}")
                    continue

            logger.info(f"[BBVA] Parseados {len(movimientos)} movimientos")
            return movimientos

        except Exception as e:
            logger.error(f"[BBVA] Error general: {e}")
            raise


class DaviviendaParser:
    """Parser para extractos Davivienda."""
    SKIP_ROWS = 4
    COL_FECHA = "Fecha"
    COL_DESCRIPCION = "Descripción"
    COL_VALOR = "Valor"
    COL_TIPO = "Naturaleza"  # C = ingreso, D = egreso
    CUENTA_ALEGRA = 5322  # Davivienda 482

    @staticmethod
    async def parsear(archivo_bytes: bytes) -> List[MovimientoBancario]:
        """Parsea extracto Davivienda."""
        try:
            df = pd.read_excel(
                BytesIO(archivo_bytes),
                skiprows=DaviviendaParser.SKIP_ROWS,
            )

            movimientos = []
            for _, row in df.iterrows():
                try:
                    fecha_str = pd.to_datetime(row[DaviviendaParser.COL_FECHA]).strftime("%Y-%m-%d")
                    descripcion = str(row[DaviviendaParser.COL_DESCRIPCION]).strip()
                    monto = float(row[DaviviendaParser.COL_VALOR])
                    tipo_orig = str(row[DaviviendaParser.COL_TIPO]).strip().upper()

                    # Mapear tipo
                    tipo = TipoMovimiento.INGRESO if tipo_orig == "C" else TipoMovimiento.EGRESO

                    # Extraer proveedor (helper consolidado — CONT-01)
                    proveedor = _extraer_proveedor(descripcion)

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=abs(monto),
                        tipo=tipo,
                        banco=Banco.DAVIVIENDA,
                        cuenta_banco_id=DaviviendaParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto}|{tipo_orig}",
                        proveedor=proveedor,
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"[Davivienda] Error parseando fila: {e}")
                    continue

            logger.info(f"[Davivienda] Parseados {len(movimientos)} movimientos")
            return movimientos

        except Exception as e:
            logger.error(f"[Davivienda] Error general: {e}")
            raise


class NequiParser:
    """Parser para extractos Nequi."""
    SKIP_ROWS = 1
    COL_FECHA = "Fecha"
    COL_DESCRIPCION = "Descripción"
    COL_VALOR = "Monto"
    COL_TIPO = "Tipo"  # ingreso | egreso
    CUENTA_ALEGRA = 5310  # Caja general

    @staticmethod
    async def parsear(archivo_bytes: bytes) -> List[MovimientoBancario]:
        """Parsea extracto Nequi."""
        try:
            df = pd.read_excel(
                BytesIO(archivo_bytes),
                skiprows=NequiParser.SKIP_ROWS,
                sheet_name='Extracto Nequi',
            )

            movimientos = []
            for _, row in df.iterrows():
                try:
                    fecha_str = pd.to_datetime(row[NequiParser.COL_FECHA]).strftime("%Y-%m-%d")
                    descripcion = str(row[NequiParser.COL_DESCRIPCION]).strip()
                    monto = float(row[NequiParser.COL_VALOR])
                    tipo_orig = str(row[NequiParser.COL_TIPO]).strip().lower()

                    # Mapear tipo
                    tipo = TipoMovimiento.INGRESO if "ingreso" in tipo_orig else TipoMovimiento.EGRESO

                    # Extraer proveedor (helper consolidado — CONT-01)
                    proveedor = _extraer_proveedor(descripcion)

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=abs(monto),
                        tipo=tipo,
                        banco=Banco.NEQUI,
                        cuenta_banco_id=NequiParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto}|{tipo_orig}",
                        proveedor=proveedor,
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"[Nequi] Error parseando fila: {e}")
                    continue

            logger.info(f"[Nequi] Parseados {len(movimientos)} movimientos")
            return movimientos

        except Exception as e:
            logger.error(f"[Nequi] Error general: {e}")
            raise


class BankReconciliationEngine:
    """Motor de conciliación bancaria. Parsea, clasifica y causa movimientos."""

    PARSERS = {
        Banco.BANCOLOMBIA: BancolombiParser,
        Banco.BBVA: BBVAParser,
        Banco.DAVIVIENDA: DaviviendaParser,
        Banco.NEQUI: NequiParser,
    }

    def __init__(self, db_instance):
        """Inicializa con instancia de MongoDB."""
        self.db = db_instance
        self.logger = logging.getLogger(f"{__name__}.BankReconciliationEngine")

    async def parsear_extracto(self, banco: str, archivo_bytes: bytes) -> List[MovimientoBancario]:
        """Parsea extracto según banco."""
        try:
            banco_enum = Banco[banco.upper()]
        except KeyError:
            raise ValueError(f"Banco no soportado: {banco}")

        parser = self.PARSERS.get(banco_enum)
        if not parser:
            raise ValueError(f"Parser no encontrado para {banco}")

        return await parser.parsear(archivo_bytes)

    async def clasificar_movimientos(
        self,
        movimientos: List[MovimientoBancario],
    ) -> Tuple[List[MovimientoBancario], List[MovimientoBancario]]:
        """
        Clasifica movimientos usando accounting_engine.
        Retorna: (movimientos_causables, movimientos_pendientes)
        """
        from services.accounting_engine import clasificar_movimiento

        causables = []
        pendientes = []

        for mov in movimientos:
            # Determinar cuenta crédito según tipo
            # Egreso: crédito es el banco (débito es el gasto)
            # Ingreso: débito es el banco (crédito es el ingreso)

            if mov.tipo == TipoMovimiento.EGRESO:
                # Egreso: clasificar el gasto
                clasificacion = clasificar_movimiento(
                    descripcion=mov.descripcion,
                    proveedor=mov.proveedor,
                    monto=mov.monto,
                    banco_origen=mov.cuenta_banco_id,
                )
                mov.cuenta_debito_sugerida = clasificacion.cuenta_debito
                mov.cuenta_credito_sugerida = mov.cuenta_banco_id  # El banco es crédito
            else:
                # Ingreso: clasificar el ingreso
                clasificacion = clasificar_movimiento(
                    descripcion=mov.descripcion,
                    proveedor=mov.proveedor,
                    monto=mov.monto,
                    banco_origen=mov.cuenta_banco_id,
                )
                mov.cuenta_debito_sugerida = mov.cuenta_banco_id  # El banco es débito
                mov.cuenta_credito_sugerida = clasificacion.cuenta_credito

            mov.confianza = clasificacion.confianza
            mov.razon_clasificacion = clasificacion.razon
            mov.requiere_confirmacion = clasificacion.requiere_confirmacion
            mov.es_transferencia_interna = clasificacion.es_transferencia_interna

            # Separar por confianza
            # REGLA: si alguna cuenta es None → backlog siempre (evita error Alegra 400)
            cuentas_validas = (
                mov.cuenta_debito_sugerida is not None and
                mov.cuenta_credito_sugerida is not None
            )

            if mov.es_transferencia_interna:
                pendientes.append(mov)  # Registrar como traslado sin contabilizar
            elif cuentas_validas and mov.confianza >= 0.70 and not mov.requiere_confirmacion:
                causables.append(mov)  # Causable automático
            else:
                if not cuentas_validas:
                    mov.razon_clasificacion = (
                        f"Cuenta {'débito' if mov.cuenta_debito_sugerida is None else 'crédito'} "
                        f"sin clasificar — {mov.razon_clasificacion}"
                    )
                pendientes.append(mov)  # Requiere confirmación manual vía backlog

            self.logger.info(
                f"[Clasificar] {mov.banco.value} {mov.descripcion[:30]} "
                f"→ confianza={mov.confianza:.0%}"
            )

        return causables, pendientes

    async def crear_journal_alegra(
        self,
        movimiento: MovimientoBancario,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Crea journal en Alegra para movimiento causable via AlegraService.

        Usa request_with_verify() para garantizar POST+GET verificacion.
        Si Alegra retorna 429/503, guarda en conciliacion_reintentos
        para reintentarlo en el scheduler (cada 5 min).
        """
        import hashlib
        from datetime import timedelta

        try:
            # VALIDACION DE CUENTAS: Verificar que no sean None antes de crear payload
            if movimiento.cuenta_debito_sugerida is None or movimiento.cuenta_credito_sugerida is None:
                self.logger.error(
                    f"[Alegra] VALIDACION FALLIDA: "
                    f"cuenta_debito={movimiento.cuenta_debito_sugerida}, "
                    f"cuenta_credito={movimiento.cuenta_credito_sugerida}. "
                    f"No se puede crear journal sin cuentas sugeridas."
                )
                return False, None, f"Cuentas sugeridas invalidas (debit={movimiento.cuenta_debito_sugerida}, credit={movimiento.cuenta_credito_sugerida})"

            # Payload del journal
            payload = {
                "date": movimiento.fecha,
                "observations": f"{movimiento.descripcion} ({movimiento.banco.value})",
                "entries": [
                    {
                        "id": str(movimiento.cuenta_debito_sugerida),
                        "debit": int(movimiento.monto),
                        "credit": 0,
                    },
                    {
                        "id": str(movimiento.cuenta_credito_sugerida),
                        "debit": 0,
                        "credit": int(movimiento.monto),
                    },
                ],
            }

            self.logger.info(f"[BG] Creando journal para {movimiento.descripcion} (monto={movimiento.monto})")

            # Usar AlegraService con self.db (ya disponible en __init__)
            alegra = AlegraService(self.db)

            # Verificar que no estamos en demo mode
            if await alegra.is_demo_mode():
                self.logger.warning("[BG] Alegra en modo demo — journal no creado")
                return False, None, "Alegra en modo demo"

            try:
                result = await alegra.request_with_verify("journals", "POST", body=payload)
            except Exception as e:
                # Si es 429/503, guardar para reintento (logica de resiliencia preservada)
                error_str = str(e)
                if "429" in error_str or "503" in error_str or "no disponible" in error_str.lower():
                    self.logger.warning(f"[Alegra] Temporal — guardando en reintentos: {error_str}")
                    hash_movimiento = hashlib.md5(
                        f"{movimiento.banco.value}{movimiento.fecha}{movimiento.descripcion}{str(movimiento.monto)}".encode()
                    ).hexdigest()
                    ahora = datetime.now(timezone.utc)
                    proximo_intento = ahora + timedelta(minutes=5)
                    await self.db.conciliacion_reintentos.update_one(
                        {"movimiento_hash": hash_movimiento},
                        {
                            "$set": {
                                "movimiento_hash": hash_movimiento,
                                "banco": movimiento.banco.value,
                                "fecha": movimiento.fecha,
                                "descripcion": movimiento.descripcion,
                                "monto": movimiento.monto,
                                "cuenta_debito": movimiento.cuenta_debito_sugerida,
                                "cuenta_credito": movimiento.cuenta_credito_sugerida,
                                "proximo_intento": proximo_intento,
                                "estado": "pendiente_reintento",
                                "timestamp_ultimo_intento": ahora,
                            },
                            "$inc": {"intentos": 1}
                        },
                        upsert=True,
                    )
                    return False, None, f"Almacenado en reintentos ({error_str[:100]})"
                raise

            # Extraer journal_id del resultado
            journal_id = str(result.get("id", ""))
            verificado = result.get("_verificado", False)

            if not journal_id:
                self.logger.error(f"Alegra no retorno ID valido: {result}")
                return False, None, str(result)

            self.logger.info(f"[BG] Journal {journal_id} creado (verificado={verificado})")

            # Guardar en MongoDB despues de creacion exitosa (upsert para evitar duplicados)
            hash_movimiento = hashlib.md5(
                f"{movimiento.banco.value}{movimiento.fecha}{movimiento.descripcion}{str(movimiento.monto)}".encode()
            ).hexdigest()

            await self.db.conciliacion_movimientos_procesados.update_one(
                {"hash": hash_movimiento},
                {"$set": {
                    "hash": hash_movimiento,
                    "banco": movimiento.banco.value,
                    "fecha": movimiento.fecha,
                    "descripcion": movimiento.descripcion,
                    "monto": movimiento.monto,
                    "journal_id": journal_id,
                    "procesado_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            self.logger.info(f"[MONGO] Movimiento guardado en BD: journal_id {journal_id}")

            return True, journal_id, None

        except Exception as e:
            self.logger.error(f"[Alegra] Error creando journal: {type(e).__name__}: {str(e)}")
            return False, None, str(e)

    async def guardar_movimiento_pendiente(
        self,
        movimiento: MovimientoBancario,
    ) -> str:
        """
        Guarda movimiento en contabilidad_pendientes para revisión manual vía WhatsApp.

        Estructura completa para que el Agente Contador pueda clasificar con contexto.
        """
        import hashlib as _hashlib
        backlog_hash = _hashlib.md5(
            f"{movimiento.banco.value}{movimiento.fecha}{movimiento.descripcion}{str(movimiento.monto)}".encode()
        ).hexdigest()

        doc = {
            "id": f"mov_{movimiento.banco.value}_{datetime.now(timezone.utc).timestamp()}",
            # Campo requerido por /backlog/stats y BacklogPage
            "backlog_hash": backlog_hash,
            "extracto": f"{movimiento.banco.value}_{movimiento.fecha[:7].replace('-', '_')}",
            "fecha": movimiento.fecha,
            "descripcion": movimiento.descripcion,
            "monto": movimiento.monto,
            "tipo": movimiento.tipo.value.upper(),
            "banco": movimiento.banco.value,
            "cuenta_banco_id": movimiento.cuenta_banco_id,
            "referencia_original": movimiento.referencia_original,

            # Información del proveedor extraído
            "proveedor_extraido": movimiento.proveedor,

            # Sugerencia del motor matricial
            "cuenta_debito_sugerida": movimiento.cuenta_debito_sugerida,
            "cuenta_credito_sugerida": movimiento.cuenta_credito_sugerida,
            "confianza_motor": movimiento.confianza,
            "razon_baja_confianza": movimiento.razon_clasificacion,

            # Campos de control
            "requiere_confirmacion": movimiento.requiere_confirmacion,
            "es_transferencia_interna": getattr(movimiento, 'es_transferencia_interna', False),
            # estado="pendiente" para que /backlog/stats lo cuente correctamente
            "estado": "pendiente",
            "journal_alegra_id": None,
            "resuelto_por": None,
            "resuelto_at": None,
            "creado_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await self.db.contabilidad_pendientes.insert_one(doc)
        mov_id = result.inserted_id

        self.logger.info(
            f"[Pendientes WhatsApp] {movimiento.banco.value} {movimiento.descripcion[:30]} "
            f"→ confianza={movimiento.confianza:.0%} (< 0.70)"
        )
        return str(mov_id)
