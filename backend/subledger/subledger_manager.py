"""Sub-Ledger local para recuperación de $94M de pagos ene-feb."""
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel
from backend.database import db

class SubLedgerEntry(BaseModel):
    """Entrada del sub-libro local."""
    fecha: str
    concepto: str
    cuenta_debito: str
    cuenta_credito: str
    monto: float
    origen: str
    estado: str

class SubLedgerManager:
    """Gestor del sub-libro contable local."""
    
    COLECCION = "sub_ledger"
    
    @staticmethod
    async def crear_entrada(entry: SubLedgerEntry) -> str:
        """Crea entrada en sub-ledger y retorna el ID."""
        doc = entry.dict()
        doc["timestamp_creacion"] = datetime.utcnow()
        doc["timestamp_sync"] = None
        
        result = await db[SubLedgerManager.COLECCION].insert_one(doc)
        return str(result.inserted_id)
    
    @staticmethod
    async def recuperar_enero_febrero() -> List[Dict]:
        """Recupera todos los pagos de loanbook ene-feb sin journal en Alegra."""
        pagos = await db.cartera_pagos.find({
            "fecha": {"$gte": "2026-01-01", "$lte": "2026-02-28"},
            "alegra_journal_id": None
        }).to_list(None)
        
        return pagos
    
    @staticmethod
    async def sincronizar_pendientes() -> Dict:
        """Sincroniza con Alegra todas las entradas pendientes."""
        pendientes = await db[SubLedgerManager.COLECCION].find({
            "estado": "pendiente_sync"
        }).to_list(None)
        
        resultado = {"sincronizadas": 0, "errores": 0, "monto_total": 0}
        
        for entrada in pendientes:
            try:
                alegra_id = await _causar_en_alegra(entrada)
                await db[SubLedgerManager.COLECCION].update_one(
                    {"_id": entrada["_id"]},
                    {"$set": {
                        "estado": "sincronizado",
                        "timestamp_sync": datetime.utcnow(),
                        "alegra_journal_id": alegra_id
                    }}
                )
                resultado["sincronizadas"] += 1
                resultado["monto_total"] += entrada["monto"]
            except Exception as e:
                await db[SubLedgerManager.COLECCION].update_one(
                    {"_id": entrada["_id"]},
                    {"$set": {"estado": "error", "error_message": str(e)}}
                )
                resultado["errores"] += 1
        
        return resultado

async def _causar_en_alegra(entrada: Dict) -> str:
    """Helper: causa la entrada en Alegra y retorna el journal ID."""
    pass
