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

    # Clasificación (se llena después)
    cuenta_debito_sugerida: Optional[int] = None
    cuenta_credito_sugerida: Optional[int] = None
    confianza: float = 0.0
    razon_clasificacion: str = ""
    requiere_confirmacion: bool = False


class BancolombiParser:
    """Parser para extractos Bancolombia."""
    SKIP_ROWS = 8
    COL_FECHA = "Fecha"
    COL_DESCRIPCION = "Descripción"
    COL_VALOR = "Valor"
    COL_TIPO = "Tipo"  # CR = ingreso, DB = egreso
    ENCODING = "utf-8"
    CUENTA_ALEGRA = 5314  # Bancolombia 2029

    @staticmethod
    async def parsear(archivo_bytes: bytes) -> List[MovimientoBancario]:
        """Parsea extracto Bancolombia."""
        try:
            df = pd.read_excel(
                BytesIO(archivo_bytes),
                skiprows=BancolombiParser.SKIP_ROWS,
            )

            movimientos = []
            for _, row in df.iterrows():
                try:
                    fecha_str = pd.to_datetime(row[BancolombiParser.COL_FECHA]).strftime("%Y-%m-%d")
                    descripcion = str(row[BancolombiParser.COL_DESCRIPCION]).strip()
                    monto = float(row[BancolombiParser.COL_VALOR])
                    tipo_orig = str(row[BancolombiParser.COL_TIPO]).strip().upper()

                    # Mapear tipo
                    tipo = TipoMovimiento.INGRESO if tipo_orig == "CR" else TipoMovimiento.EGRESO

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=abs(monto),
                        tipo=tipo,
                        banco=Banco.BANCOLOMBIA,
                        cuenta_banco_id=BancolombiParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto}|{tipo_orig}",
                    ))
                except (ValueError, KeyError) as e:
                    logger.warning(f"[Bancolombia] Error parseando fila: {e}")
                    continue

            logger.info(f"[Bancolombia] Parseados {len(movimientos)} movimientos")
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
        """Parsea extracto BBVA. Positivo=ingreso, negativo=egreso."""
        try:
            df = pd.read_excel(
                BytesIO(archivo_bytes),
                header=13,
            )

            movimientos = []
            for _, row in df.iterrows():
                try:
                    fecha_str = pd.to_datetime(row[BBVAParser.COL_FECHA]).strftime("%Y-%m-%d")
                    descripcion = str(row[BBVAParser.COL_DESCRIPCION]).strip()
                    monto_raw = float(row[BBVAParser.COL_VALOR])

                    # Positivo = ingreso, negativo = egreso
                    tipo = TipoMovimiento.INGRESO if monto_raw > 0 else TipoMovimiento.EGRESO
                    monto = abs(monto_raw)

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=monto,
                        tipo=tipo,
                        banco=Banco.BBVA,
                        cuenta_banco_id=BBVAParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto_raw}",
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

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=abs(monto),
                        tipo=tipo,
                        banco=Banco.DAVIVIENDA,
                        cuenta_banco_id=DaviviendaParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto}|{tipo_orig}",
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

                    movimientos.append(MovimientoBancario(
                        fecha=fecha_str,
                        descripcion=descripcion,
                        monto=abs(monto),
                        tipo=tipo,
                        banco=Banco.NEQUI,
                        cuenta_banco_id=NequiParser.CUENTA_ALEGRA,
                        referencia_original=f"{fecha_str}|{descripcion}|{monto}|{tipo_orig}",
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
                    proveedor="",
                    monto=mov.monto,
                    banco_origen=mov.cuenta_banco_id,
                )
                mov.cuenta_debito_sugerida = clasificacion.cuenta_debito
                mov.cuenta_credito_sugerida = mov.cuenta_banco_id  # El banco es crédito
            else:
                # Ingreso: clasificar el ingreso
                clasificacion = clasificar_movimiento(
                    descripcion=mov.descripcion,
                    proveedor="",
                    monto=mov.monto,
                    banco_origen=mov.cuenta_banco_id,
                )
                mov.cuenta_debito_sugerida = mov.cuenta_banco_id  # El banco es débito
                mov.cuenta_credito_sugerida = clasificacion.cuenta_credito

            mov.confianza = clasificacion.confianza
            mov.razon_clasificacion = clasificacion.razon
            mov.requiere_confirmacion = clasificacion.requiere_confirmacion

            # Separar por confianza
            if mov.confianza >= 0.70 and not mov.requiere_confirmacion:
                causables.append(mov)
            else:
                pendientes.append(mov)

            self.logger.info(
                f"[Clasificar] {mov.banco.value} {mov.descripcion[:30]} "
                f"→ confianza={mov.confianza:.0%}"
            )

        return causables, pendientes

    async def crear_journal_alegra(
        self,
        movimiento: MovimientoBancario,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Crea journal en Alegra para movimiento causable.
        Retorna: (exitoso, journal_id, error_msg)
        """
        from alegra_service import AlegraService

        try:
            service = AlegraService(self.db)

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

            # POST a Alegra
            response = await service.request("journals", "POST", payload)

            if not isinstance(response, dict) or not response.get("id"):
                self.logger.error(f"Alegra no retornó ID válido: {response}")
                return False, None, str(response)

            journal_id = str(response["id"])

            # GET de verificación
            verify = await service.request(f"journals/{journal_id}")
            if not verify or not verify.get("id"):
                self.logger.error(f"GET verificación falló para journal {journal_id}")
                return False, journal_id, "GET verification failed"

            self.logger.info(f"[Alegra] Journal {journal_id} creado para {movimiento.descripcion}")
            return True, journal_id, None

        except Exception as e:
            self.logger.error(f"[Alegra] Error creando journal: {e}")
            return False, None, str(e)

    async def guardar_movimiento_pendiente(
        self,
        movimiento: MovimientoBancario,
    ) -> str:
        """Guarda movimiento en contabilidad_pendientes para resolución manual."""
        doc = {
            "id": f"mov_{movimiento.banco.value}_{datetime.now(timezone.utc).timestamp()}",
            "fecha": movimiento.fecha,
            "descripcion": movimiento.descripcion,
            "monto": movimiento.monto,
            "tipo": movimiento.tipo.value,
            "banco": movimiento.banco.value,
            "cuenta_banco_id": movimiento.cuenta_banco_id,
            "referencia_original": movimiento.referencia_original,
            "cuenta_debito_sugerida": movimiento.cuenta_debito_sugerida,
            "cuenta_credito_sugerida": movimiento.cuenta_credito_sugerida,
            "confianza": movimiento.confianza,
            "razon": movimiento.razon_clasificacion,
            "requiere_confirmacion": movimiento.requiere_confirmacion,
            "estado": "esperando_contexto",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await self.db.contabilidad_pendientes.insert_one(doc)
        mov_id = result.inserted_id

        self.logger.info(f"[Pendientes] Movimiento {mov_id} guardado para resolución")
        return str(mov_id)
