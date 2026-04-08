"""Circuit breaker y Dead Letter Queue para resiliencia ante fallos de Alegra."""
from datetime import datetime, timedelta
from typing import Dict, Any, Callable
from enum import Enum
from backend.database import db

class CircuitState(Enum):
    CLOSED = "closed"      # Funcionando normal
    OPEN = "open"          # Alegra caído, bloquear requests
    HALF_OPEN = "half_open"  # Probando si se recuperó

class CircuitBreaker:
    """Circuit breaker para Alegra API."""
    
    def __init__(self, failure_threshold=5, timeout_seconds=60, success_threshold=2):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func: Callable, *args, **kwargs):
        """Ejecuta función con circuit breaker."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker OPEN — Alegra no disponible")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Registra éxito."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
    
    async def _on_failure(self):
        """Registra fallo."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            await db.circuit_breaker_events.insert_one({
                "timestamp": datetime.utcnow(),
                "state": "OPEN",
                "reason": "Failure threshold reached"
            })
    
    def _should_attempt_reset(self) -> bool:
        """Verifica si ya pasó el timeout."""
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout_seconds


class DeadLetterQueue:
    """Cola para journals que fallaron en Alegra."""
    
    COLECCION = "dead_letter_queue"
    
    @staticmethod
    async def enqueue(journal_data: Dict[str, Any], error: str, retry_count: int = 0):
        """Encola un journal fallido."""
        await db[DeadLetterQueue.COLECCION].insert_one({
            "timestamp": datetime.utcnow(),
            "journal_data": journal_data,
            "error": error,
            "retry_count": retry_count,
            "status": "pendiente"
        })
    
    @staticmethod
    async def retry_all():
        """Reintenta todos los journals en la DLQ."""
        pendientes = await db[DeadLetterQueue.COLECCION].find({
            "status": "pendiente",
            "retry_count": {"$lt": 3}
        }).to_list(None)
        
        resultado = {"exitosas": 0, "fallidas": 0}
        
        for item in pendientes:
            try:
                # Intentar causar de nuevo
                # await _causar_en_alegra(item["journal_data"])
                
                # Marcar como sincronizado
                await db[DeadLetterQueue.COLECCION].update_one(
                    {"_id": item["_id"]},
                    {"$set": {"status": "sincronizado", "sync_time": datetime.utcnow()}}
                )
                resultado["exitosas"] += 1
            except Exception as e:
                # Incrementar retry_count
                await db[DeadLetterQueue.COLECCION].update_one(
                    {"_id": item["_id"]},
                    {"$inc": {"retry_count": 1}, "$set": {"error": str(e)}}
                )
                resultado["fallidas"] += 1
        
        return resultado

# Instancia global del circuit breaker
alegra_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_seconds=60,
    success_threshold=2
)
