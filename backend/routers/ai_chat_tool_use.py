# SISMO BUILD 24 - ai_chat_tool_use.py
# Router de agentes con Anthropic Tool Use API
# Reemplaza el legacy ACTION_MAP de BUILD 23
# Usa los 32 Tools del Agente Contador (tool_definitions_complete.py)

import os
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import anthropic
from motor.motor_asyncio import AsyncIOMotorDatabase

from tool_definitions_complete import TOOL_DEFS, get_tool_schema
from tool_executor_complete import execute_tool, ToolExecutor

logger = logging.getLogger(__name__)

# Feature flag: TOOL_USE_ENABLED=true en Render para activar
TOOL_USE_ENABLED = os.environ.get("TOOL_USE_ENABLED", "").lower() == "true"

# System prompts diferenciados por agente (BUILD 24)
SYSTEM_PROMPTS = {
    "contador": """
Eres el Agente Contador de SISMO (Sistema Inteligente de Soporte y Monitoreo Operativo).
Tu dominio exclusivo es la contabilidad operativa de RODDOS S.A.S.

IDENTIDAD Y RESTRICCIONES:
- Nivel 1 Operativo: ejecutas exactamente lo que te ordenan. No evalúas conveniencia estratégica.
- Eres el ÚNICO agente que puede escribir en Alegra (API REST).
- NUNCA reportas éxito sin verificar HTTP 200 en Alegra (ROG-1).
- Tienes acceso a 32 Tools para todas las operaciones contables.

HERRAMIENTAS PERMITIDAS (6 categorías):
1. EGRESOS: crear_causacion, crear_causacion_masiva, registrar_gasto_periodico, crear_nota_debito, registrar_retenciones, crear_asiento_manual
2. INGRESOS: registrar_ingreso_no_operacional, registrar_cuota_cartera, registrar_abono_socio, registrar_ingreso_financiero, registrar_ingreso_arrendamiento
3. CONCILIACIÓN BANCARIA: crear_causacion_desde_extracto, marcar_movimiento_clasificado, crear_reintentos_movimientos, auditar_movimientos_pendientes, sincronizar_extracto_global66, resolver_duplicados_bancarios
4. CONCILIACIÓN INGRESOS/EGRESOS: validar_cobertura_gasto, reportar_desfase_contable, sincronizar_cartera_alegra, auditar_balance_cierre
5. INVENTARIO: actualizar_moto_vendida, registrar_entrega_moto, consultar_motos_disponibles, sincronizar_compra_auteco
6. NÓMINA E IMPUESTOS: registrar_nomina_mensual, calcular_retenciones_payroll, reportar_obligaciones_dian

PROHIBIDO ABSOLUTAMENTE:
- Escritura en cfo_informes, cfo_alertas, crm_clientes, gestiones_cobranza
- POST a /accounts de Alegra (da 403 — usar /categories)
- POST a /journal-entries de Alegra (da 403 — usar /journals)
- Operaciones síncronas masivas >10 registros (usar BackgroundTasks + job_id)

REGLAS PERMANENTES (INAMOVIBLES):
- Plan de cuentas desde plan_cuentas_roddos: fallback ID 5493 (NUNCA 5495)
- Gasto socio (Andrés 80075452 / Iván 80086601) = CXC socios, NUNCA gasto operativo
- Auteco NIT 860024781 = autoretenedor (NUNCA ReteFuente)
- Retenciones: Arriendo 3.5%, Servicios 4%, Hon.PN 10%, Hon.PJ 11%, Compras 2.5%
- IVA cuatrimestral: ene-abr / may-ago / sep-dic
- request_with_verify() SIEMPRE: POST + GET de verificación en Alegra

TU FLUJO:
1. Usuario describe operación en lenguaje natural
2. Detectas el tool requerido de los 32 disponibles
3. Si requiere confirmación, propones el asiento ANTES de ejecutar
4. Ejecutas con request_with_verify() (POST + GET)
5. Publicas evento en roddos_events
6. Invalidas CFO caché si aplica
7. Reportas con ID Alegra como evidencia

MÁXIMO UNA PREGUNTA POR TURNO.
Si falta info crítica → preguntas qué banco, qué cliente, qué monto.
Sin info → propones valor por defecto documentado en CLAUDE.md.
""",
    
    "cfo": """
Eres el CFO Estratégico de SISMO.
Tu dominio exclusivo es la salud financiera global de RODDOS S.A.S.

IDENTIDAD Y RESTRICCIONES:
- Nivel 3 Estratégico: analizas, alertas, puedes vetar acciones del Contador (Nivel 1).
- NUNCA escribes en Alegra ni en colecciones operativas (inventario, cartera, loanbook).
- Solo LECTURA de todos los dominios simultáneamente.
- Puedes escribir SOLO en: cfo_informes, cfo_alertas.

DOMINIO EXCLUSIVO:
- P&L mensual y comparativo desde Alegra
- Balance General NIIF (activos, pasivos, patrimonio)
- Flujo de caja proyectado 90 días
- Semáforo financiero: caja · cartera · inventario · deuda · margen
- Alertas cuando métricas superan thresholds
- Roll rate: A→B→C→D→E (cartera en riesgo)

PROHIBIDO:
- POST a Alegra
- Crear/modificar loanbooks, motos, gastos
- Ejecutar operaciones contables directamente

TU FLUJO:
1. Lees datos de Alegra + MongoDB simultáneamente
2. Separa DEVENGADO (Alegra) de CAJA (bancos)
3. Detectas anomalías, mora, presupuesto roto, concentración
4. Publicas alertas en roddos_events → el Contador/RADAR reaccionan
5. Reportas siempre en pesos colombianos con impacto cuantificado

SIEMPRE CUANTIFICA: "Cartera en riesgo: $4.5M (5.2% del total). Acción recomendada: X."
""",
    
    "radar": """
Eres RADAR de Cartera: Gestor de cobranza 100% remota.
Nivel 2 Coordinador: tu trabajo es DECIDIR, no EJECUTAR.

IDENTIDAD:
- Gestor táctico de cobranza
- 100% REMOTO: llamadas + WhatsApp Mercately SOLAMENTE
- NUNCA visitas en campo ni geolocalización
- Dominio exclusivo: cola de cobro, DPD, gestiones, PTP (promesas)

FLUJO:
1. Cada miércoles 06:00: Loanbook publica dpd_actual + scores
2. Tú construyes cola priorizada: críticos primero, regulares después
3. Decides template WhatsApp, timing, escalación
4. Registras GESTIÓN (llamada, respuesta, PTP) en CRM
5. Si pago → ordenas al Contador registrar_cuota_cartera
6. Si mora crítica → alertas al CFO

PROHIBIDO:
- Escribir en Alegra
- Modificar loanbook directamente (solo lee estado)
- Crear facturas, asientos contables
- Sugerir visitas

SIEMPRE LEE: perfil_360 del cliente ANTES de actuar (score, etapa, historial gestión).
""",
    
    "loanbook": """
Eres el Agente Loanbook: Gestor del ciclo de vida del crédito.
Nivel 2 Coordinador: owns inventario_motos + loanbook, ordena al Contador.

IDENTIDAD:
- Dueño exclusivo del estado: factura (pendiente) → entrega (activo) → cobro (pagado) → cierre (saldado)
- Cálculo 1° cuota: primer miércoles >= (entrega + 7 días)
- Mutex anti-doble venta: NUNCA dos creditos en misma moto
- Cronograma inviolable: 52/78 cuotas semanales calculadas en Momento 2

3 MOMENTOS:
1. FACTURA: evento factura.venta.creada → loanbook pendiente_entrega
2. ENTREGA: usuario confirma fecha → calcula cronograma → activa loanbook
3. COBRO: cada miércoles → procesa pagos → actualiza cuotas, DPD, scores

PROHIBIDO:
- Escribir en Alegra directamente
- Modificar cartera_pagos (el Contador lo hace)
- Cambiar cronograma después de activación (solo admin)

CRONOGRAMA SAGRADO: Ningún cliente paga antes del primer miércoles >= (entrega + 7 días).
MADRE DE DIOS, ESTO NO CAMBIA. Si cliente quiere pagar antes, Contador lo registra pero no reduce la deuda hasta la próxima cuota.
"""
}


class AgenteCountadorRouter:
    """Router principal de Tool Use API para el Agente Contador (BUILD 24)"""
    
    def __init__(self, db: AsyncIOMotorDatabase, alegra_client):
        self.db = db
        self.alegra = alegra_client
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    
    def _build_tool_definitions(self) -> List[Dict[str, Any]]:
        """Construye la lista de tool definitions para Anthropic API (JSON Schema format)"""
        tools = []
        for tool_name in TOOL_DEFS.keys():
            schema = get_tool_schema(tool_name)
            tools.append({
                "name": tool_name,
                "description": TOOL_DEFS[tool_name].__doc__ or f"Tool: {tool_name}",
                "input_schema": schema
            })
        return tools
    
    
    async def process_chat(
        self,
        message: str,
        session_id: str,
        user_id: str,
        conversation_history: List[Dict[str, str]] = None,
        agent_type: str = "contador"
    ) -> Dict[str, Any]:
        """
        Procesa mensaje del usuario con Tool Use API.
        Retorna respuesta + acciones ejecutadas.
        ROG-1: NUNCA reportar éxito sin verificar en Alegra.
        """
        
        if conversation_history is None:
            conversation_history = []
        
        # Validar que TOOL_USE_ENABLED está activo
        if not TOOL_USE_ENABLED:
            logger.warning("TOOL_USE_ENABLED no está seteada en Render. Usando fallback legacy.")
            return {
                "status": "warning",
                "mensaje": "Tool Use API no está activada. Por favor, seta TOOL_USE_ENABLED=true en Render.",
                "fallback": "legacy_action_map"
            }
        
        # Paso 1: Build system prompt for agent
        system_prompt = SYSTEM_PROMPTS.get(agent_type, SYSTEM_PROMPTS["contador"])
        
        # Paso 2: Agregar historial de sesión (últimas 72h)
        agent_session = await self.db.agent_sessions.find_one({
            "_id": f"{user_id}_{agent_type}",
            "expire_at": {"$gt": datetime.now()}  # TTL 72h
        })
        
        if agent_session:
            # Cargar últimos mensajes del historial
            prior_messages = agent_session.get("messages", [])[-5:]  # últimos 5 mensajes
            conversation_history = prior_messages + conversation_history
        
        # Paso 3: Agregar mensaje nuevo al historial
        conversation_history.append({"role": "user", "content": message})
        
        # Paso 4: Llamar Claude con Tool Use API
        logger.info(f"[Tool Use] Agent: {agent_type}, Message: {message[:50]}...")
        
        response = self.client.messages.create(
            model="claude-opus-4-6",  # Model para Tool Use
            max_tokens=2048,
            system=system_prompt,
            tools=self._build_tool_definitions(),
            messages=conversation_history
        )
        
        # Paso 5: Procesar respuesta (texto + tool calls)
        result_message = {"role": "assistant", "content": response.content}
        conversation_history.append(result_message)
        
        # Separar texto de tool calls
        text_responses = []
        tool_calls = []
        
        for block in response.content:
            if hasattr(block, "text"):
                text_responses.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        
        # Paso 6: Ejecutar tool calls en secuencia
        tool_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["input"]
            tool_id = tool_call["id"]
            
            logger.info(f"[Tool Use] Executing: {tool_name}")
            
            try:
                # Ejecutar el tool
                result = await execute_tool(
                    tool_name=tool_name,
                    input_data=tool_input,
                    db=self.db,
                    alegra_client=self.alegra
                )
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result)
                })
                
                logger.info(f"[Tool Use] Result: {result.get('status', 'unknown')}")
            
            except Exception as e:
                logger.error(f"[Tool Use] Error ejecutando {tool_name}: {e}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps({
                        "status": "error",
                        "mensaje": str(e)
                    }),
                    "is_error": True
                })
        
        # Paso 7: Si hubo tool calls, agregar resultados al historial y llamar a Claude nuevamente para resumen
        if tool_calls:
            # Agregar tool results al historial
            for result in tool_results:
                conversation_history.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": result["tool_use_id"],
                        "content": result["content"],
                        "is_error": result.get("is_error", False)
                    }]
                })
            
            # Segunda llamada a Claude para generar resumen narrativo
            response_summary = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=system_prompt,
                tools=self._build_tool_definitions(),
                messages=conversation_history
            )
            
            # Extraer texto final
            for block in response_summary.content:
                if hasattr(block, "text"):
                    text_responses.append(block.text)
        
        # Paso 8: Guardar sesión actualizada en MongoDB (TTL 72h)
        await self.db.agent_sessions.update_one(
            {"_id": f"{user_id}_{agent_type}"},
            {
                "$set": {
                    "messages": conversation_history[-10:],  # últimos 10 mensajes
                    "agent_type": agent_type,
                    "user_id": user_id,
                    "updated_at": datetime.now(),
                    "expire_at": datetime.now() + __import__("datetime").timedelta(hours=72)
                }
            },
            upsert=True
        )
        
        # Paso 9: Retornar respuesta completa
        return {
            "status": "exitoso",
            "agent": agent_type,
            "mensaje": "\n".join(text_responses),
            "tool_calls_ejecutadas": len(tool_calls),
            "tokens_used": response.usage.output_tokens + response.usage.input_tokens if hasattr(response, "usage") else 0,
            "conversation_id": session_id,
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# FastAPI Router Integration (para reemplazar en main.py)
# ============================================================================

async def chat_endpoint(
    db: AsyncIOMotorDatabase,
    alegra_client,
    request: Dict[str, Any]
) -> Dict[str, Any]:
    """
    POST /api/chat endpoint con Tool Use API
    Body: { "message": str, "session_id": str, "user_id": str, "agent_type": str }
    """
    
    message = request.get("message")
    session_id = request.get("session_id")
    user_id = request.get("user_id")
    agent_type = request.get("agent_type", "contador")
    
    if not message or not user_id:
        return {"status": "error", "mensaje": "message y user_id son requeridos"}
    
    router = AgenteCountadorRouter(db=db, alegra_client=alegra_client)
    
    result = await router.process_chat(
        message=message,
        session_id=session_id,
        user_id=user_id,
        agent_type=agent_type
    )
    
    return result


# ============================================================================
# Backward compatibility: fallback a legacy ACTION_MAP si TOOL_USE_ENABLED=false
# ============================================================================

LEGACY_ACTION_MAP = {
    # Legacy handlers para B23 (si TOOL_USE_ENABLED no está seteada)
    "registrar_gasto": "crear_causacion",
    "registrar_pago": "registrar_cuota_cartera",
    "crear_factura_venta": "crear_causacion",  # placeholder
    "consultar_cartera": "consultar_cartera_cliente",
    # ... más mappings legacy
}

async def process_chat_legacy(message: str, db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """Fallback a ACTION_MAP legacy si Tool Use API no está disponible"""
    logger.warning("Usando fallback ACTION_MAP legacy (BUILD 23)")
    return {
        "status": "warning",
        "mensaje": "Tool Use API no activada. Fallback a legacy ACTION_MAP.",
        "agente_respuesta": "Activar TOOL_USE_ENABLED=true en Render para Tool Use API completo."
    }
