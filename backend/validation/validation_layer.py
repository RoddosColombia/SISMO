"""Validación Pre-Escritura: 5 checks antes de POST a Alegra."""
from typing import Optional, Dict, List
from pydantic import BaseModel, Field

class JournalEntryValidationRequest(BaseModel):
    fecha: str = Field(...)
    concepto: str = Field(...)
    cuentas: List[Dict] = Field(...)
    monto_total: float = Field(..., gt=0)
    categoria: Optional[str] = None

class ValidationResult(BaseModel):
    is_valid: bool
    errores: List[str] = []
    warnings: List[str] = []
    cuenta_debito_clasificada: Optional[str] = None
    cuenta_credito_clasificada: Optional[str] = None
    paso_reflection_loop: bool = False

class ValidationLayer:
    SPECIAL_RULES = {
        "arriendo": {"cuenta_debito": "5480", "reteFuente": 0.035},
        "honorarios_pn": {"cuenta_debito": "5470", "reteFuente": 0.10},
        "honorarios_pj": {"cuenta_debito": "5470", "reteFuente": 0.11},
        "servicios": {"cuenta_debito": "5484", "reteFuente": 0.04},
        "compras": {"cuenta_debito": "5090", "reteFuente": 0.025},
    }
    FALLBACK_CUENTA_DEBITO = "5493"
    FALLBACK_CUENTA_CREDITO = "1105"
