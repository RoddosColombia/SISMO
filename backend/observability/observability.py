"""Observabilidad: Correlation IDs, métricas, y alertas para SISMO."""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from backend.database import db
import logging

logger = logging.getLogger(__name__)

class CorrelationIdManager:
    """Gestiona correlation IDs para trazabilidad end-to-end."""
    
    _current_correlation_id: str = None
    
    @classmethod
    def generate(cls) -> str:
        """Genera nuevo correlation ID."""
        cls._current_correlation_id = str(uuid.uuid4())
        return cls._current_correlation_id
    
    @classmethod
    def get(cls) -> str:
        """Obtiene correlation ID actual."""
        if cls._current_correlation_id is None:
            cls.generate()
        return cls._current_correlation_id

class MetricsCollector:
    """Recolecta métricas de operaciones."""
    
    COLECCION = "observability_metrics"
    
    @staticmethod
    async def record_operation(
        operation_name: str,
        duration_ms: float,
        status: str,  # "success" | "failure"
        correlation_id: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Registra métrica de una operación."""
        await db[MetricsCollector.COLECCION].insert_one({
            "timestamp": datetime.utcnow(),
            "operation_name": operation_name,
            "duration_ms": duration_ms,
            "status": status,
            "correlation_id": correlation_id,
            "details": details or {}
        })
    
    @staticmethod
    async def get_p95_latency(operation_name: str, minutes: int = 60) -> float:
        """Obtiene latencia P95 de una operación."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        results = await db[MetricsCollector.COLECCION].find({
            "operation_name": operation_name,
            "timestamp": {"$gte": cutoff}
        }).sort("duration_ms", 1).to_list(None)
        
        if not results:
            return 0
        
        p95_index = int(len(results) * 0.95)
        return results[p95_index]["duration_ms"]

class AlertManager:
    """Sistema de alertas automáticas."""
    
    COLECCION = "observability_alerts"
    
    UMBRALES = {
        "circuit_breaker_open": True,  # Se alerta cuando circuit abre
        "alegra_latency_ms": 5000,      # Si tarda > 5 seg
        "error_rate": 0.15,             # Si > 15% de fallos
        "dead_letter_queue_backlog": 100 # Si hay >100 pendientes
    }
    
    @staticmethod
    async def check_and_alert() -> Dict[str, bool]:
        """Verifica umbrales y emite alertas si necesario."""
        alertas_emitidas = {}
        
        # CHECK 1: Circuit breaker
        cb_status = await db.circuit_breaker_events.find_one(
            {"state": "OPEN"},
            sort=[("timestamp", -1)]
        )
        if cb_status:
            await AlertManager._emit_alert(
                "CIRCUIT_BREAKER_OPEN",
                "Alegra no disponible — circuit breaker activado"
            )
            alertas_emitidas["circuit_breaker"] = True
        
        # CHECK 2: Dead Letter Queue backlog
        dlq_count = await db.dead_letter_queue.count_documents(
            {"status": "pendiente"}
        )
        if dlq_count > AlertManager.UMBRALES["dead_letter_queue_backlog"]:
            await AlertManager._emit_alert(
                "DLQ_BACKLOG",
                f"Dead Letter Queue tiene {dlq_count} journals pendientes"
            )
            alertas_emitidas["dlq_backlog"] = True
        
        return alertas_emitidas
    
    @staticmethod
    async def _emit_alert(alert_type: str, message: str):
        """Emite alerta a MongoDB (luego se propaga a email/WhatsApp)."""
        await db[AlertManager.COLECCION].insert_one({
            "timestamp": datetime.utcnow(),
            "alert_type": alert_type,
            "message": message,
            "status": "emitida"
        })
        logger.warning(f"ALERTA [{alert_type}]: {message}")

class RequestLogger:
    """Registra cada request HTTP con correlation ID."""
    
    COLECCION = "observability_requests"
    
    @staticmethod
    async def log_request(
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str] = None
    ):
        """Registra detalles de un request."""
        correlation_id = CorrelationIdManager.get()
        
        await db[RequestLogger.COLECCION].insert_one({
            "timestamp": datetime.utcnow(),
            "correlation_id": correlation_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id
        })
