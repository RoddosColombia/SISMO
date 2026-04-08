"""Webhook receiver para eventos de Alegra."""
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from typing import Dict, Any
import hmac
import hashlib
from datetime import datetime
from backend.database import db

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

@router.post("/alegra/receive")
async def receive_alegra_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recibe webhooks de Alegra y los procesa en background."""
    try:
        body = await request.json()
        
        # Verificar webhook secret (configurar en Alegra)
        webhook_id = request.headers.get("X-Alegra-Webhook-ID")
        signature = request.headers.get("X-Alegra-Webhook-Signature")
        
        # Log del webhook recibido
        await db.sismo_webhooks.insert_one({
            "timestamp": datetime.utcnow(),
            "source": "alegra",
            "webhook_id": webhook_id,
            "evento_type": body.get("event"),
            "status": "recibido",
            "payload": body
        })
        
        # Procesar en background
        background_tasks.add_task(process_alegra_webhook, body, webhook_id)
        
        return {"status": "recibido", "webhook_id": webhook_id}
    
    except Exception as e:
        await db.sismo_webhook_errors.insert_one({
            "timestamp": datetime.utcnow(),
            "error": str(e),
            "request_ip": request.client.host
        })
        raise HTTPException(status_code=400, detail=str(e))

async def process_alegra_webhook(body: Dict[str, Any], webhook_id: str):
    """Procesa webhook de Alegra en background."""
    evento_type = body.get("event")
    
    # Mapeo de eventos
    if evento_type == "invoice.created":
        await handle_invoice_created(body)
    elif evento_type == "invoice.updated":
        await handle_invoice_updated(body)
    elif evento_type == "payment.created":
        await handle_payment_created(body)
    
    # Marcar como procesado
    await db.sismo_webhooks.update_one(
        {"webhook_id": webhook_id},
        {"$set": {"status": "procesado", "processed_at": datetime.utcnow()}}
    )

async def handle_invoice_created(body: Dict):
    """Maneja invoice.created — sincroniza con inventario y loanbook."""
    pass

async def handle_invoice_updated(body: Dict):
    """Maneja invoice.updated."""
    pass

async def handle_payment_created(body: Dict):
    """Maneja payment.created."""
    pass
