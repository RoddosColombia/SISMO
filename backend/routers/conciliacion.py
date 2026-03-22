"""conciliacion.py — Endpoints para carga de extractos bancarios y conciliación automática.

Endpoints:
  POST   /api/conciliacion/cargar-extracto  — Cargar extracto bancario
  GET    /api/conciliacion/pendientes       — Listar movimientos pendientes
  POST   /api/conciliacion/resolver/{id}    — Resolver movimiento ambiguo
  GET    /api/conciliacion/estado/{fecha}   — Estado de conciliación para una fecha
"""

import logging
import base64
import os
import httpx
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from pydantic import BaseModel

from database import db
from dependencies import get_current_user, log_action, require_admin
from services.bank_reconciliation import BankReconciliationEngine, Banco

router = APIRouter(prefix="/conciliacion", tags=["conciliacion"])
logger = logging.getLogger(__name__)

engine = BankReconciliationEngine(db)


# ── Pydantic Models ────────────────────────────────────────────────────────

class ResolverMovimientoRequest(BaseModel):
    cuenta_debito: str
    cuenta_credito: str
    observacion: str = ""


class ResumenConciliacion(BaseModel):
    fecha: str
    porcentaje_conciliado: float
    total_movimientos: int
    total_causado: float
    total_pendiente: float
    journals_creados: int
    movimientos_pendientes: int
    discrepancias: list


# ── Background Task Handler ────────────────────────────────────────────────

_jobs_estado: dict[str, dict] = {}  # In-memory cache (redundant with MongoDB)


async def _procesar_extracto_background(
    job_id: str,
    banco: str,
    fecha: str,
    archivo_bytes: bytes,
    usuario_id: str,
    hash_extracto: str,
):
    """Procesa extracto en background para lotes grandes."""
    import os

    # LOGS INICIALES PARA DIAGNÓSTICO
    logger.info(f"[BG-START] Job {job_id} iniciado")
    logger.info(f"[BG-START] Banco: {banco}, Fecha: {fecha}")
    logger.info(f"[BG-START] Archivo bytes: {len(archivo_bytes)}")
    logger.info(f"[BG-START] Alegra email configurado: {bool(os.environ.get('ALEGRA_EMAIL'))}")
    logger.info(f"[BG-START] Alegra token configurado: {bool(os.environ.get('ALEGRA_TOKEN'))}")

    # Inicializar estado
    job_state = {
        "job_id": job_id,
        "status": "processing",
        "banco": banco,
        "fecha": fecha,
        "usuario_id": usuario_id,
        "causados": 0,
        "pendientes": 0,
        "errores": 0,
        "ultimo_error": None,  # ← NUEVO: Capturar último error para diagnóstico
        "timestamp_inicio": datetime.now(timezone.utc).isoformat(),
    }

    # Guardar en MongoDB (persistente)
    await db.conciliacion_jobs.insert_one(job_state)

    # Guardar en memoria (para acceso rápido)
    _jobs_estado[job_id] = job_state

    try:
        # Parsear
        logger.info(f"[📄 Job {job_id}] Parseando extracto {banco}...")
        movimientos = await engine.parsear_extracto(banco, archivo_bytes)
        _jobs_estado[job_id]["total_movimientos"] = len(movimientos)
        await db.conciliacion_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"total_movimientos": len(movimientos)}}
        )
        logger.info(f"[📄 Job {job_id}] ✅ {len(movimientos)} movimientos parseados")
        logger.info(f"[BG-START] Total movimientos recibidos: {len(movimientos)}")

        # Clasificar
        logger.info(f"[🏷️  Job {job_id}] Clasificando movimientos...")
        causables, pendientes = await engine.clasificar_movimientos(movimientos)
        logger.info(f"[🏷️  Job {job_id}] ✅ {len(causables)} causables, {len(pendientes)} pendientes")

        # LOG DE DETALLE POR MOVIMIENTO
        for idx, mov in enumerate(movimientos, 1):
            logger.info(
                f"[BG-MOV] [{idx}] {mov.descripcion[:40]:<40} | "
                f"proveedor={mov.proveedor:<20} | "
                f"confianza={mov.confianza:.0%} | "
                f"cuenta_d={mov.cuenta_debito_sugerida} | "
                f"cuenta_c={mov.cuenta_credito_sugerida} | "
                f"transferencia={mov.es_transferencia_interna} | "
                f"razon={mov.razon_clasificacion[:30]}"
            )
        await db.conciliacion_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "causables_total": len(causables),
                "pendientes_total": len(pendientes)
            }}
        )

        # Causar en Alegra
        logger.info(f"[💰 Job {job_id}] Causando {len(causables)} movimientos en Alegra...")
        logger.info(f"[BG] Movimientos causables a procesar: {len(causables)}")
        for idx, mov in enumerate(causables, 1):
            logger.debug(f"[💰 Job {job_id}] [{idx}/{len(causables)}] Causando: {mov.descripcion} ${mov.monto:,.0f}")

            # ╔═══════════════════════════════════════════════════════════════════════════════╗
            # ║ ENVOLTORIO DE EXCEPCIÓN POR MOVIMIENTO — Atrapar cualquier error individual ║
            # ╚═══════════════════════════════════════════════════════════════════════════════╝
            try:
                # ─────────────────────────────────────────────────────────────────────────────
                # CAPA 2: ANTI-DUPLICADOS — Hash por movimiento individual
                # ─────────────────────────────────────────────────────────────────────────────
                hash_movimiento = hashlib.md5(
                    f"{banco}{mov.fecha}{mov.descripcion}{str(mov.monto)}".encode()
                ).hexdigest()

                movimiento_duplicado = await db.conciliacion_movimientos_procesados.find_one({
                    "hash": hash_movimiento
                })

                if movimiento_duplicado:
                    logger.warning(f"[⚠️  DUPLICADO Job {job_id}] Movimiento {mov.descripcion} ya procesado, skipping")
                    continue

                # ✅ LLAMADA A CREAR JOURNAL — Resultado retorna (exitoso, journal_id, error)
                exitoso, journal_id, error = await engine.crear_journal_alegra(mov)

                if exitoso:
                    _jobs_estado[job_id]["causados"] += 1
                    logger.info(f"[✅ Job {job_id}] Journal {journal_id} creado para {mov.descripcion}")
                    # Guardar hash del movimiento como procesado (upsert para evitar duplicados)
                    await db.conciliacion_movimientos_procesados.update_one(
                        {"hash": hash_movimiento},
                        {"$set": {
                            "hash": hash_movimiento,
                            "banco": banco,
                            "fecha": mov.fecha,
                            "descripcion": mov.descripcion,
                            "monto": mov.monto,
                            "journal_id": journal_id,
                            "procesado_at": datetime.now(timezone.utc).isoformat(),
                        }},
                        upsert=True
                    )
                    # Guardar en roddos_events
                    await db.roddos_events.insert_one({
                        "event_type": "extracto_bancario.causado",
                        "banco": banco,
                        "fecha_movimiento": mov.fecha,
                        "descripcion": mov.descripcion,
                        "monto": mov.monto,
                        "journal_id": journal_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "job_id": job_id,
                    })
                    # Actualizar estado en MongoDB
                    await db.conciliacion_jobs.update_one(
                        {"job_id": job_id},
                        {"$inc": {"causados": 1}}
                    )
                else:
                    # ❌ crear_journal_alegra retornó False pero sin excepción
                    _jobs_estado[job_id]["errores"] += 1
                    _jobs_estado[job_id]["ultimo_error"] = f"[{mov.descripcion}] {error}"
                    logger.error(f"[❌ Job {job_id}] Error causando {mov.descripcion}: {error}")
                    # Actualizar errores en MongoDB
                    await db.conciliacion_jobs.update_one(
                        {"job_id": job_id},
                        {
                            "$inc": {"errores": 1},
                            "$set": {"ultimo_error": f"[{mov.descripcion}] {error}"}
                        }
                    )

            except Exception as e:
                # ❌ EXCEPCIÓN NO PREVISTA EN CREAR JOURNAL O BD
                _jobs_estado[job_id]["errores"] += 1
                error_msg = f"{type(e).__name__}: {str(e)}"
                _jobs_estado[job_id]["ultimo_error"] = f"[{mov.descripcion}] {error_msg}"
                logger.error(
                    f"[❌ EXCEPCIÓN Job {job_id}] Movimiento {mov.descripcion}: {error_msg}",
                    exc_info=True
                )
                # Actualizar estado en MongoDB
                await db.conciliacion_jobs.update_one(
                    {"job_id": job_id},
                    {
                        "$inc": {"errores": 1},
                        "$set": {"ultimo_error": f"[{mov.descripcion}] {error_msg}"}
                    }
                )
                # Continuar con el siguiente movimiento en lugar de fallar todo el job
                continue

        # Guardar pendientes
        logger.info(f"[⏳ Job {job_id}] Guardando {len(pendientes)} movimientos pendientes...")
        for idx, mov in enumerate(pendientes, 1):
            mov_id = await engine.guardar_movimiento_pendiente(mov)
            _jobs_estado[job_id]["pendientes"] += 1
            logger.debug(f"[⏳ Job {job_id}] [{idx}/{len(pendientes)}] Pendiente guardado: {mov.descripcion} (confianza: {mov.confianza:.0%})")
            await db.roddos_events.insert_one({
                "event_type": "extracto_bancario.pendiente",
                "banco": banco,
                "fecha_movimiento": mov.fecha,
                "descripcion": mov.descripcion,
                "monto": mov.monto,
                "movimiento_id": mov_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_id": job_id,
            })
            # Actualizar estado en MongoDB
            await db.conciliacion_jobs.update_one(
                {"job_id": job_id},
                {"$inc": {"pendientes": 1}}
            )

        # LOG FINAL DE RESUMEN
        logger.info(
            f"[BG-END] causables={len(causables)} pendientes={len(pendientes)} "
            f"causados={_jobs_estado[job_id]['causados']} "
            f"pendientes_guardados={_jobs_estado[job_id]['pendientes']} "
            f"errores={_jobs_estado[job_id]['errores']}"
        )

        # ─────────────────────────────────────────────────────────────────────────────
        # ANTI-DUPLICADOS: Solo guardar hash si se crearon journals (causados > 0)
        # Si causados == 0, NO marcar como procesado para permitir reintento
        # ─────────────────────────────────────────────────────────────────────────────
        if _jobs_estado[job_id]["causados"] > 0:
            await db.conciliacion_extractos_procesados.update_one(
                {"hash": hash_extracto},
                {"$set": {
                    "hash": hash_extracto,
                    "banco": banco.lower(),
                    "fecha": fecha,
                    "procesado_at": datetime.now(timezone.utc).isoformat(),
                    "journals_creados": _jobs_estado[job_id]["causados"],
                    "movimientos_pendientes": _jobs_estado[job_id]["pendientes"],
                    "usuario": usuario_id,
                    "job_id": job_id,
                }},
                upsert=True
            )
            logger.info(
                f"[✅ PROCESADO] Job {job_id}: Extracto {banco} "
                f"({_jobs_estado[job_id]['causados']} journals creados)"
            )
        else:
            logger.warning(
                f"[⚠️  NO PROCESADO] Job {job_id}: Extracto {banco} sin journals "
                f"(causados=0). Hash NO guardado — permitiendo reintento"
            )

        # Finalización exitosa
        _jobs_estado[job_id]["status"] = "completed"
        _jobs_estado[job_id]["timestamp_fin"] = datetime.now(timezone.utc).isoformat()
        await db.conciliacion_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "completed",
                "timestamp_fin": _jobs_estado[job_id]["timestamp_fin"]
            }}
        )
        logger.info(f"[✅ Job {job_id}] COMPLETADO: "
                   f"✅ {_jobs_estado[job_id]['causados']} causados | "
                   f"⏳ {_jobs_estado[job_id]['pendientes']} pendientes | "
                   f"❌ {_jobs_estado[job_id]['errores']} errores")

    except Exception as e:
        logger.error(f"[❌ Job {job_id}] ERROR CRÍTICO: {str(e)}", exc_info=True)
        _jobs_estado[job_id]["status"] = "failed"
        _jobs_estado[job_id]["error"] = str(e)
        _jobs_estado[job_id]["ultimo_error"] = f"[ERROR_CRÍTICO] {type(e).__name__}: {str(e)}"
        _jobs_estado[job_id]["timestamp_fin"] = datetime.now(timezone.utc).isoformat()
        # Guardar error en MongoDB
        await db.conciliacion_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "error": str(e),
                "ultimo_error": _jobs_estado[job_id]["ultimo_error"],
                "timestamp_fin": _jobs_estado[job_id]["timestamp_fin"]
            }}
        )


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/cargar-extracto")
async def cargar_extracto(
    banco: str = Form(...),
    fecha: str = Form(...),
    archivo: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user=Depends(get_current_user),
):
    """
    Carga un extracto bancario, parsea movimientos, clasifica y causa en Alegra.

    Para lotes > 10 movimientos, retorna job_id inmediatamente (procesa en background).
    """
    try:
        # Validar banco
        try:
            Banco[banco.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Banco no soportado: {banco}")

        # Leer archivo
        archivo_bytes = await archivo.read()

        # ─────────────────────────────────────────────────────────────────────────────
        # CAPA 1: ANTI-DUPLICADOS — Hash del extracto completo
        # ─────────────────────────────────────────────────────────────────────────────
        hash_extracto = hashlib.md5(archivo_bytes).hexdigest()

        # Diagnostic: mostrar documentos del banco en MongoDB
        if banco.lower() == "bancolombia":
            docs_banco = await db.conciliacion_extractos_procesados.find({
                "banco": banco.lower()
            }).to_list(100)
            logger.info(f"[DIAG] Documentos Bancolombia en BD: {len(docs_banco)} encontrados")
            for doc in docs_banco:
                logger.info(
                    f"  → Hash {doc.get('hash', 'N/A')[:16]}... : "
                    f"{doc.get('journals_creados', 0)} journals "
                    f"| {doc.get('procesado_at', 'N/A')}"
                )

        extracto_existente = await db.conciliacion_extractos_procesados.find_one({
            "hash": hash_extracto,
            "banco": banco.lower(),
        })

        if extracto_existente:
            logger.warning(
                f"[DUPLICADO] Extracto {banco} del {fecha} ya fue procesado "
                f"({extracto_existente.get('journals_creados', 0)} journals)"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Este extracto ya fue procesado el {extracto_existente.get('procesado_at', 'fecha desconocida')}. "
                        f"Journals creados: {extracto_existente.get('journals_creados', 0)}"
            )

        # Parsear extracto
        movimientos = await engine.parsear_extracto(banco, archivo_bytes)

        if not movimientos:
            raise HTTPException(status_code=400, detail="No se encontraron movimientos en el extracto")

        # Clasificar
        causables, pendientes = await engine.clasificar_movimientos(movimientos)

        # Si lote > 10, usar background task
        if len(movimientos) > 10:
            import uuid
            job_id = str(uuid.uuid4())
            background_tasks.add_task(
                _procesar_extracto_background,
                job_id, banco, fecha, archivo_bytes, current_user, hash_extracto,
            )

            await log_action(
                current_user,
                "/conciliacion/cargar-extracto",
                "POST",
                {"banco": banco, "fecha": fecha, "total_movimientos": len(movimientos), "job_id": job_id},
            )

            return {
                "job_id": job_id,
                "status": "processing",
                "total_movimientos": len(movimientos),
                "mensaje": "Procesando en background...",
            }

        # Lote pequeño: procesar inmediatamente
        causados = 0
        pendientes_count = 0
        monto_causado = 0.0

        for mov in causables:
            exitoso, journal_id, error = await engine.crear_journal_alegra(mov)
            if exitoso:
                causados += 1
                monto_causado += mov.monto
                await db.roddos_events.insert_one({
                    "event_type": "extracto_bancario.causado",
                    "banco": banco,
                    "fecha_movimiento": mov.fecha,
                    "descripcion": mov.descripcion,
                    "monto": mov.monto,
                    "journal_id": journal_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                logger.error(f"Error causando {mov.descripcion}: {error}")

        for mov in pendientes:
            mov_id = await engine.guardar_movimiento_pendiente(mov)
            pendientes_count += 1
            await db.roddos_events.insert_one({
                "event_type": "extracto_bancario.pendiente",
                "banco": banco,
                "fecha_movimiento": mov.fecha,
                "descripcion": mov.descripcion,
                "monto": mov.monto,
                "movimiento_id": mov_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        await log_action(
            current_user,
            "/conciliacion/cargar-extracto",
            "POST",
            {
                "banco": banco,
                "fecha": fecha,
                "total": len(movimientos),
                "causados": causados,
                "pendientes": pendientes_count,
            },
        )

        # ─────────────────────────────────────────────────────────────────────────────
        # ANTI-DUPLICADOS: Solo guardar hash si se crearon journals (causados > 0)
        # Si causados == 0, NO marcar como procesado para permitir reintento
        # ─────────────────────────────────────────────────────────────────────────────
        if causados > 0:
            await db.conciliacion_extractos_procesados.update_one(
                {"hash": hash_extracto},
                {"$set": {
                    "hash": hash_extracto,
                    "banco": banco.lower(),
                    "fecha": fecha,
                    "procesado_at": datetime.now(timezone.utc).isoformat(),
                    "journals_creados": causados,
                    "movimientos_pendientes": pendientes_count,
                    "usuario": current_user,
                }},
                upsert=True
            )
            logger.info(f"[✅ PROCESADO] Extracto {banco} ({causados} journals creados)")
        else:
            logger.warning(
                f"[⚠️  NO PROCESADO] Extracto {banco} sin journals creados (causados=0). "
                f"Hash NO guardado — permitiendo reintento"
            )

        return {
            "causados": causados,
            "pendientes": pendientes_count,
            "total_movimientos": len(movimientos),
            "monto_causado": monto_causado,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cargando extracto: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/job-status/{job_id}")
async def obtener_estado_job(
    job_id: str,
    current_user=Depends(get_current_user),
):
    """Obtiene el estado de un background job de conciliación."""
    # Intentar obtener del MongoDB (persistente)
    job = await db.conciliacion_jobs.find_one(
        {"job_id": job_id},
        {"_id": 0}
    )

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")

    return job


@router.get("/test-alegra")
async def test_alegra(
    current_user=Depends(get_current_user),
):
    """
    TEST DIRECTO: Lee ALEGRA_EMAIL/TOKEN del entorno y hace un GET real a Alegra.
    SIN MOCKS, SIN DEMOS, SIN FALLBACKS.

    Retorna:
    - http_status: HTTP status de la respuesta
    - email_usado: Email de credenciales (parte de la prueba)
    - tiene_token: True si token fue leído
    - primer_journal: Primer comprobante encontrado en Alegra (si hay)
    - error: Mensaje de error (si falla)
    """

    # Leer credenciales directamente del entorno (sin caché, sin fallbacks)
    email = os.environ.get("ALEGRA_EMAIL", "")
    token = os.environ.get("ALEGRA_TOKEN", "")

    logger.info(f"[TEST-ALEGRA] Email desde env: {email[:10]}..." if email else "[TEST-ALEGRA] Email: NO CONFIGURADO")
    logger.info(f"[TEST-ALEGRA] Token presente: {bool(token)}")

    # Validar credenciales
    if not email or not token:
        return {
            "error": "CREDENCIALES NO CONFIGURADAS",
            "email_usado": email,
            "tiene_token": bool(token),
            "http_status": None,
            "primer_journal": None,
            "detalles": "Configure ALEGRA_EMAIL y ALEGRA_TOKEN en variables de entorno de Render"
        }

    # Construir header Basic Auth (sin servicio, directo)
    try:
        creds_str = f"{email}:{token}"
        creds_b64 = base64.b64encode(creds_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {creds_b64}",
            "Content-Type": "application/json",
        }

        logger.info(f"[TEST-ALEGRA] Construyendo header: Basic {creds_b64[:20]}...")

        # GET DIRECTO a Alegra sin pasar por AlegraService
        url = "https://api.alegra.com/api/v1/journals?limit=1"
        logger.info(f"[TEST-ALEGRA] Llamando GET {url}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)

        logger.info(f"[TEST-ALEGRA] ✅ HTTP {response.status_code}")

        # Intentar parsear respuesta
        try:
            data = response.json()
        except:
            data = None

        # Extraer primer journal si está disponible
        primer_journal = None
        if isinstance(data, list) and len(data) > 0:
            primer_journal = data[0]
        elif isinstance(data, dict) and "results" in data and len(data["results"]) > 0:
            primer_journal = data["results"][0]

        return {
            "http_status": response.status_code,
            "email_usado": email,
            "tiene_token": True,
            "primer_journal": primer_journal,
            "response_headers": dict(response.headers),
            "response_body_keys": list(data.keys()) if isinstance(data, dict) else "lista",
            "detalles": "✅ Conexión exitosa a Alegra API"
        }

    except Exception as e:
        logger.error(f"[TEST-ALEGRA] ❌ Error: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "email_usado": email,
            "tiene_token": bool(token),
            "http_status": None,
            "primer_journal": None,
            "detalles": f"Error conectando a Alegra: {str(e)}"
        }


@router.get("/reintentos")
async def listar_reintentos(
    estado: str = "pendiente_reintento",
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    """
    Lista movimientos pendientes reintento (cuando Alegra estuvo caído).

    estados posibles:
    - pendiente_reintento: esperando siguiente intento
    - fallo_permanente: agotó 5 intentos sin éxito
    """
    try:
        query = {}
        if estado:
            query["estado"] = estado

        reintentos = await db.conciliacion_reintentos.find(
            query,
            {"_id": 0}
        ).sort("proximo_intento", 1).to_list(limit)

        ahora = datetime.now(timezone.utc)
        total_listos = 0
        for r in reintentos:
            if r.get("proximo_intento", datetime.max) <= ahora:
                total_listos += 1

        return {
            "total": len(reintentos),
            "listos_para_reintento": total_listos,
            "ahora": ahora.isoformat(),
            "reintentos": reintentos,
        }

    except Exception as e:
        logger.error(f"Error listando reintentos: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/pendientes")
async def listar_pendientes(
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    """Lista movimientos pendientes en contabilidad_pendientes."""
    movimientos = await db.contabilidad_pendientes.find(
        {
            "$or": [
                {"estado": "esperando_contexto"},
                {"estado": "pendiente"},
            ]
        },
        {"_id": 0},
    ).sort("monto", -1).to_list(limit)

    return {
        "total": len(movimientos),
        "movimientos": movimientos,
    }


@router.get("/procesados")
async def listar_procesados(
    limit: int = 50,
    current_user=Depends(get_current_user),
):
    """
    Lista los últimos movimientos procesados (journals creados en Alegra).

    Retorna: fecha, descripcion, monto, banco, journal_id, procesado_at
    Ordenado por procesado_at descendente (más recientes primero)
    """
    movimientos = await db.conciliacion_movimientos_procesados.find(
        {},
        {"_id": 0, "hash": 0}  # Excluir ID y hash
    ).sort("procesado_at", -1).to_list(limit)

    return {
        "total": len(movimientos),
        "limit": limit,
        "campos": ["fecha", "descripcion", "monto", "banco", "journal_id", "procesado_at"],
        "movimientos": movimientos,
    }


@router.post("/resolver/{movimiento_id}")
async def resolver_movimiento(
    movimiento_id: str,
    req: ResolverMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Resuelve un movimiento ambiguo creando journal en Alegra."""
    try:
        movimiento = await db.contabilidad_pendientes.find_one(
            {"id": movimiento_id},
            {"_id": 0},
        )

        if not movimiento:
            raise HTTPException(status_code=404, detail="Movimiento no encontrado")

        # Crear journal en Alegra
        from alegra_service import AlegraService
        service = AlegraService(db)

        payload = {
            "date": movimiento["fecha"],
            "observations": f"{movimiento['descripcion']} - {req.observacion}",
            "entries": [
                {"id": req.cuenta_debito, "debit": int(movimiento["monto"]), "credit": 0},
                {"id": req.cuenta_credito, "debit": 0, "credit": int(movimiento["monto"])},
            ],
        }

        response = await service.request("journals", "POST", payload)
        if not response or not response.get("id"):
            raise ValueError(f"Alegra error: {response}")

        journal_id = str(response["id"])

        # Actualizar estado
        await db.contabilidad_pendientes.update_one(
            {"id": movimiento_id},
            {
                "$set": {
                    "estado": "resuelto",
                    "journal_id": journal_id,
                    "cuenta_debito_final": req.cuenta_debito,
                    "cuenta_credito_final": req.cuenta_credito,
                    "observacion_usuario": req.observacion,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        # Guardar en agent_memory para aprendizaje
        await db.agent_memory.insert_one({
            "tipo": "clasificacion_aprendida",
            "descripcion": movimiento["descripcion"],
            "cuenta_debito": req.cuenta_debito,
            "cuenta_credito": req.cuenta_credito,
            "banco": movimiento.get("banco", ""),
            "confianza_original": movimiento.get("confianza", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Evento
        await db.roddos_events.insert_one({
            "event_type": "extracto_bancario.resuelto",
            "movimiento_id": movimiento_id,
            "journal_id": journal_id,
            "usuario": current_user,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        await log_action(
            current_user,
            f"/conciliacion/resolver/{movimiento_id}",
            "POST",
            {"journal_id": journal_id},
        )

        return {
            "ok": True,
            "movimiento_id": movimiento_id,
            "journal_id": journal_id,
            "mensaje": f"Movimiento resuelto y journal {journal_id} creado en Alegra",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolviendo movimiento: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/estado/{fecha}")
async def obtener_estado_conciliacion(
    fecha: str,  # YYYY-MM-DD
    current_user=Depends(get_current_user),
):
    """
    Retorna estado de conciliación para una fecha.
    Incluye: % conciliado, totales, journals creados, discrepancias.
    """
    try:
        # Eventos de ese día
        eventos = await db.roddos_events.find(
            {
                "event_type": {"$in": [
                    "extracto_bancario.causado",
                    "extracto_bancario.pendiente",
                    "extracto_bancario.resuelto",
                ]},
                "fecha_movimiento": {"$gte": fecha, "$lt": f"{fecha}T23:59:59"},
            },
            {"_id": 0},
        ).to_list(None)

        causados = len([e for e in eventos if e.get("event_type") == "extracto_bancario.causado"])
        pendientes = len([e for e in eventos if e.get("event_type") == "extracto_bancario.pendiente"])
        resueltos = len([e for e in eventos if e.get("event_type") == "extracto_bancario.resuelto"])

        total = causados + pendientes + resueltos
        monto_causado = sum(e.get("monto", 0) for e in eventos if e.get("event_type") in [
            "extracto_bancario.causado", "extracto_bancario.resuelto"
        ])
        monto_pendiente = sum(e.get("monto", 0) for e in eventos if e.get("event_type") == "extracto_bancario.pendiente")

        porcentaje = (causados + resueltos) / total * 100 if total > 0 else 0

        # Discrepancias: movimientos con errores
        discrepancias = []
        eventos_error = await db.roddos_events.find(
            {"event_type": "extracto_bancario.error", "fecha_movimiento": {"$gte": fecha}},
            {"_id": 0},
        ).to_list(None)

        for evt in eventos_error:
            discrepancias.append({
                "tipo": "error_alegra",
                "descripcion": evt.get("descripcion", "Unknown"),
                "error": evt.get("error_msg", ""),
            })

        return {
            "fecha": fecha,
            "porcentaje_conciliado": round(porcentaje, 2),
            "total_movimientos": total,
            "total_causado": causados + resueltos,
            "total_pendiente": pendientes,
            "monto_causado": monto_causado,
            "monto_pendiente": monto_pendiente,
            "journals_creados": causados + resueltos,
            "movimientos_pendientes": pendientes,
            "discrepancias": discrepancias,
        }

    except Exception as e:
        logger.error(f"Error obteniendo estado: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/diagnostico/causados-hoy")
async def diagnostico_causados_hoy(
    current_user=Depends(get_current_user),
):
    """Diagnóstico: Cuántos journals se crearon hoy en roddos_events."""
    try:
        today = datetime.now(timezone.utc).date().isoformat()

        # Contar todos los causados de hoy
        count = await db.roddos_events.count_documents({
            "event_type": "extracto_bancario.causado",
            "timestamp": {
                "$gte": f"{today}T00:00:00",
                "$lt": f"{today}T23:59:59"
            }
        })

        # Primeros 5
        eventos = await db.roddos_events.find({
            "event_type": "extracto_bancario.causado",
            "timestamp": {
                "$gte": f"{today}T00:00:00",
                "$lt": f"{today}T23:59:59"
            }
        }).sort("timestamp", -1).limit(5).to_list(5)

        primeros_5 = []
        for evt in eventos:
            primeros_5.append({
                "journal_id": evt.get("journal_id", "N/A"),
                "monto": evt.get("monto", 0),
                "descripcion": evt.get("descripcion", "N/A")[:80],
                "timestamp": evt.get("timestamp", "N/A"),
            })

        return {
            "fecha": today,
            "total_causados": count,
            "primeros_5": primeros_5,
        }

    except Exception as e:
        logger.error(f"Error en diagnostico causados: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/limpiar-bancolombia-parcial")
async def limpiar_bancolombia_parcial(current_user=Depends(require_admin)):
    """
    Endpoint administrativo para limpiar documentos parciales de Bancolombia.

    Elimina:
    1. Documentos en conciliacion_extractos_procesados con journals_creados < 10
    2. Movimientos en conciliacion_movimientos_procesados de enero 2026

    Permite que el extracto Bancolombia se reprocesse correctamente.

    REQUIERE: Admin
    """
    try:
        logger.warning("[ADMIN] Iniciando limpieza de documentos parciales Bancolombia")

        # ─────────────────────────────────────────────────────────────────────────────
        # PASO 1: Eliminar extractos parciales
        # ─────────────────────────────────────────────────────────────────────────────

        # Buscar documentos parciales ANTES de eliminar
        parciales = await db.conciliacion_extractos_procesados.find({
            "banco": "bancolombia",
            "journals_creados": {"$lt": 10}
        }).to_list(100)

        parciales_info = []
        if parciales:
            logger.warning(f"[CLEANUP] Encontrados {len(parciales)} documentos parciales Bancolombia")
            for doc in parciales:
                info = {
                    "hash": doc.get("hash", "N/A")[:20],
                    "journals_creados": doc.get("journals_creados", 0),
                    "fecha": doc.get("fecha", "N/A"),
                    "procesado_at": doc.get("procesado_at", "N/A"),
                }
                parciales_info.append(info)
                logger.warning(
                    f"  → Eliminando: Hash {info['hash']}... "
                    f"({info['journals_creados']} journals | {info['fecha']})"
                )

            # Eliminar documentos
            result_extractos = await db.conciliacion_extractos_procesados.delete_many({
                "banco": "bancolombia",
                "journals_creados": {"$lt": 10}
            })
            logger.info(f"[CLEANUP] Eliminados {result_extractos.deleted_count} extractos parciales")
        else:
            result_extractos = None
            logger.info("[CLEANUP] No hay extractos parciales (journals_creados < 10)")

        # ─────────────────────────────────────────────────────────────────────────────
        # PASO 2: Eliminar movimientos de enero 2026
        # ─────────────────────────────────────────────────────────────────────────────

        # Buscar movimientos ANTES de eliminar
        enero_movimientos = await db.conciliacion_movimientos_procesados.find({
            "banco": "bancolombia",
            "fecha": {"$regex": "^2026-01"}
        }).to_list(100)

        enero_info = []
        if enero_movimientos:
            logger.warning(f"[CLEANUP] Encontrados {len(enero_movimientos)} movimientos Bancolombia enero 2026")
            for mov in enero_movimientos:
                info = {
                    "hash": mov.get("hash", "N/A")[:20],
                    "descripcion": mov.get("descripcion", "N/A")[:50],
                    "monto": mov.get("monto", 0),
                    "fecha": mov.get("fecha", "N/A"),
                }
                enero_info.append(info)
                logger.warning(
                    f"  → Eliminando: {info['descripcion']} "
                    f"(${info['monto']:,.0f} | {info['fecha']})"
                )

            # Eliminar movimientos
            result_movimientos = await db.conciliacion_movimientos_procesados.delete_many({
                "banco": "bancolombia",
                "fecha": {"$regex": "^2026-01"}
            })
            logger.info(f"[CLEANUP] Eliminados {result_movimientos.deleted_count} movimientos enero 2026")
        else:
            result_movimientos = None
            logger.info("[CLEANUP] No hay movimientos bloqueantes de Bancolombia enero 2026")

        # ─────────────────────────────────────────────────────────────────────────────
        # PASO 3: Verificación Final
        # ─────────────────────────────────────────────────────────────────────────────

        extractos_restantes = await db.conciliacion_extractos_procesados.count_documents({
            "banco": "bancolombia"
        })
        movimientos_restantes = await db.conciliacion_movimientos_procesados.count_documents({
            "banco": "bancolombia",
            "fecha": {"$regex": "^2026-01"}
        })

        limpieza_exitosa = (extractos_restantes == 0 and movimientos_restantes == 0)

        if limpieza_exitosa:
            logger.info("[CLEANUP] Coleccion limpia - lista para reprocesar Bancolombia")
        else:
            logger.warning(f"[CLEANUP] Aun existen documentos: {extractos_restantes} extractos, {movimientos_restantes} movimientos")

        return {
            "exitoso": True,
            "limpieza_completa": limpieza_exitosa,
            "paso_1_extractos": {
                "encontrados": len(parciales) if parciales else 0,
                "eliminados": result_extractos.deleted_count if result_extractos else 0,
                "detalles": parciales_info,
            },
            "paso_2_movimientos": {
                "encontrados": len(enero_movimientos) if enero_movimientos else 0,
                "eliminados": result_movimientos.deleted_count if result_movimientos else 0,
                "detalles": enero_info,
            },
            "estado_final": {
                "extractos_restantes": extractos_restantes,
                "movimientos_restantes": movimientos_restantes,
                "mensaje": "Coleccion limpia - lista para reprocesar" if limpieza_exitosa else "Aun hay documentos"
            }
        }

    except Exception as e:
        logger.error(f"[CLEANUP] Error durante limpieza: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/journals-banco")
async def get_journals_by_banco(
    banco: str = None,
    mes: str = None,
    limit: int = 500,
    current_user=Depends(get_current_user),
):
    """
    Endpoint de auditoría: Consulta movimientos procesados en MongoDB.

    Permite auditar qué movimientos fueron causados en Alegra sin depender
    de la API de Alegra. Útil para reconciliación y validación.

    Parámetros:
    - banco: "bancolombia", "bbva", "davivienda", "nequi" (requerido)
    - mes: "2026-01", "2026-02" (YYYY-MM, requerido)
    - limit: máximo de registros (default 500)

    Ejemplo:
    GET /api/conciliacion/journals-banco?banco=bancolombia&mes=2026-01
    GET /api/conciliacion/journals-banco?banco=bbva&mes=2026-02

    Retorna:
    {
      "banco": "bancolombia",
      "mes": "2026-01",
      "total": 15,
      "monto_total": 1234567.89,
      "journals": [
        {
          "fecha": "2026-01-15",
          "descripcion": "PAGO PSE TIGO",
          "monto": 450000.0,
          "journal_id": "341",
          "hash": "abc123...",
          "procesado_at": "2026-03-21T10:30:00Z"
        },
        ...
      ]
    }
    """
    # Validar parámetros
    if not banco:
        raise HTTPException(status_code=400, detail="Parámetro 'banco' requerido")
    if not mes:
        raise HTTPException(status_code=400, detail="Parámetro 'mes' requerido (formato YYYY-MM)")

    banco_lower = banco.lower()

    # Validar que mes tiene formato YYYY-MM
    if not mes or len(mes) != 7 or mes[4] != "-":
        raise HTTPException(status_code=400, detail="Mes debe estar en formato YYYY-MM (ej: 2026-01)")

    try:
        # Buscar movimientos procesados del banco y mes especificado
        # La fecha en MongoDB está en formato ISO (YYYY-MM-DD)
        # Buscamos con regex ^2026-01 para enero, ^2026-02 para febrero, etc.
        mes_prefix = mes  # "2026-01" → "2026-01"

        movimientos = await db.conciliacion_movimientos_procesados.find({
            "banco": banco_lower,
            "fecha": {"$regex": f"^{mes_prefix}"}
        }).sort("fecha", 1).to_list(limit)

        if not movimientos:
            return {
                "banco": banco_lower,
                "mes": mes,
                "total": 0,
                "monto_total": 0.0,
                "journals": [],
                "mensaje": f"No hay movimientos procesados de {banco_lower} en {mes}"
            }

        # Procesar resultados
        total_monto = 0.0
        journals_list = []

        for mov in movimientos:
            monto = mov.get("monto", 0)
            total_monto += monto

            journals_list.append({
                "fecha": mov.get("fecha", "N/A"),
                "descripcion": mov.get("descripcion", "N/A"),
                "monto": monto,
                "journal_id": mov.get("journal_id", "N/A"),
                "hash": mov.get("hash", "N/A")[:16] + "...",
                "procesado_at": mov.get("procesado_at", "N/A"),
            })

        logger.info(
            f"[AUDIT] Consulta journals: {banco_lower}/{mes} → "
            f"{len(journals_list)} movimientos, ${total_monto:,.0f}"
        )

        return {
            "banco": banco_lower,
            "mes": mes,
            "total": len(journals_list),
            "monto_total": total_monto,
            "journals": journals_list,
        }

    except Exception as e:
        logger.error(f"[AUDIT] Error consultando journals: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ── Backfill desde Alegra ─────────────────────────────────────────────────────

class BackfillRequest(BaseModel):
    banco: str  # "bbva" o "bancolombia"
    mes: str    # "YYYY-MM"


@router.post("/backfill-desde-alegra")
async def backfill_desde_alegra(req: BackfillRequest, current_user=Depends(require_admin)):
    """
    Reconstruye conciliacion_movimientos_procesados consultando journals en Alegra.

    Lógica:
    1. Consulta GET /journals filtrando por fecha (mes-01 a mes-31)
    2. Para cada journal con "(bbva)" o "(bancolombia)" en observations:
       - Extrae banco del texto
       - Calcula hash: MD5(banco + fecha + observations + monto)
       - Inserta en conciliacion_movimientos_procesados si no existe (upsert)
    3. Retorna: total en Alegra, insertados en MongoDB, ya existían

    Uso: POST /api/conciliacion/backfill-desde-alegra
    Body: {"banco": "bbva", "mes": "2026-01"}
    """
    import re
    import base64

    try:
        # Validar formato mes
        if not re.match(r"^\d{4}-\d{2}$", req.mes):
            raise ValueError("Formato mes debe ser YYYY-MM")

        year, month = req.mes.split("-")
        fecha_inicio = f"{year}-{month}-01"
        fecha_fin = f"{year}-{month}-31"

        banco_normalized = req.banco.lower()
        if banco_normalized not in ("bbva", "bancolombia"):
            raise ValueError("banco debe ser 'bbva' o 'bancolombia'")

        logger.info(f"[BACKFILL] Iniciando: {banco_normalized}/{req.mes}")

        # Leer credenciales directamente del entorno (sin AlegraService)
        email = os.environ.get("ALEGRA_EMAIL", "")
        token = os.environ.get("ALEGRA_TOKEN", "")

        if not email or not token:
            raise ValueError(
                "Credenciales de Alegra no configuradas. "
                "Configura ALEGRA_EMAIL y ALEGRA_TOKEN en variables de entorno de Render."
            )

        # Construir header Basic Auth
        creds_str = f"{email}:{token}"
        creds_b64 = base64.b64encode(creds_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {creds_b64}",
            "Content-Type": "application/json",
        }

        logger.info(f"[BACKFILL] Consultando Alegra con credenciales: {email[:10]}...")

        # Consultar journals en Alegra directamente (sin AlegraService)
        url = "https://api.alegra.com/api/v1/journals"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise ValueError(
                f"Alegra retornó HTTP {response.status_code}: {response.text[:200]}"
            )

        journals_response = response.json()

        # Parsear respuesta (puede ser lista o dict con "results")
        if isinstance(journals_response, list):
            journals_list = journals_response
        elif isinstance(journals_response, dict) and "results" in journals_response:
            journals_list = journals_response["results"]
        else:
            journals_list = []

        logger.info(f"[BACKFILL] Total journals en Alegra: {len(journals_list)}")

        total_procesados = 0
        total_insertados = 0
        total_existentes = 0

        # Procesar cada journal
        for journal in journals_list:
            fecha_journal = journal.get("date", "")
            observations = journal.get("observations", "").lower()
            journal_id = journal.get("id")
            entries = journal.get("entries", [])

            # Filtrar por rango de fecha
            if not (fecha_inicio <= fecha_journal <= fecha_fin):
                continue

            # Buscar banco en observations
            banco_encontrado = None
            if "bbva" in observations:
                banco_encontrado = "bbva"
            elif "bancolombia" in observations:
                banco_encontrado = "bancolombia"

            # Si el banco no coincide con el solicitado, skip
            if banco_encontrado != banco_normalized:
                continue

            total_procesados += 1

            # Calcular monto total del journal (sum of debits)
            monto_total = sum(int(e.get("debit", 0)) for e in entries)

            # Calcular hash: MD5(banco + fecha + observations + monto)
            hash_str = f"{banco_encontrado}{fecha_journal}{observations}{monto_total}"
            hash_movimiento = hashlib.md5(hash_str.encode()).hexdigest()

            # Upsert en MongoDB
            result = await db.conciliacion_movimientos_procesados.update_one(
                {"hash": hash_movimiento},
                {
                    "$set": {
                        "hash": hash_movimiento,
                        "banco": banco_encontrado,
                        "fecha": fecha_journal,
                        "descripcion": observations[:100],  # Truncar a 100 chars
                        "monto": monto_total,
                        "journal_id": str(journal_id),
                        "procesado_at": datetime.now(timezone.utc).isoformat(),
                        "backfill_source": "alegra",
                    }
                },
                upsert=True,
            )

            if result.upserted_id:
                total_insertados += 1
                logger.info(f"[BACKFILL] Insertado: journal {journal_id} → hash {hash_movimiento[:8]}")
            else:
                total_existentes += 1
                logger.info(f"[BACKFILL] Ya existía: journal {journal_id} → hash {hash_movimiento[:8]}")

        logger.info(
            f"[BACKFILL] Completado: {total_procesados} journals procesados, "
            f"{total_insertados} insertados, {total_existentes} ya existían"
        )

        return {
            "status": "success",
            "banco": banco_normalized,
            "mes": req.mes,
            "total_journals_alegra": total_procesados,
            "total_insertados": total_insertados,
            "total_existentes": total_existentes,
            "mensaje": f"Backfill completado: {total_insertados} nuevos + {total_existentes} existentes",
        }

    except ValueError as e:
        logger.error(f"[BACKFILL] Error validación: {e}")
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")
    except Exception as e:
        logger.error(f"[BACKFILL] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# DIAGNÓSTICO: Obtener logs de un job para debugging desde SISMO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/job/{job_id}/logs", tags=["diagnóstico"])
async def get_job_logs(
    job_id: str,
    current_user=Depends(get_current_user),
):
    """
    Retorna los últimos 50 eventos/logs de un job para debugging.

    Útil para ver qué pasó en el background task sin acceder al servidor.
    """
    try:
        # Obtener estado del job
        job_state = _jobs_estado.get(job_id)
        if not job_state:
            job_state = await db.conciliacion_jobs.find_one({"job_id": job_id})

        if not job_state:
            raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado")

        # Obtener eventos relacionados con el job (últimos 50)
        events = await db.roddos_events.find({
            "job_id": job_id
        }).sort("_id", -1).limit(50).to_list(50)

        # Obtener movimientos procesados (últimos 20)
        movimientos_causados = await db.conciliacion_movimientos_procesados.find({
            "job_id": job_id
        }).sort("_id", -1).limit(20).to_list(20)

        # Obtener movimientos pendientes (últimos 20)
        movimientos_pendientes = await db.contabilidad_pendientes.find({
            "estado": "pendiente_whatsapp"
        }).sort("creado_at", -1).limit(20).to_list(20)

        return {
            "job_id": job_id,
            "estado_actual": {
                "status": job_state.get("status", "unknown"),
                "banco": job_state.get("banco"),
                "fecha": job_state.get("fecha"),
                "causados": job_state.get("causados", 0),
                "pendientes": job_state.get("pendientes", 0),
                "errores": job_state.get("errores", 0),
                "total_movimientos": job_state.get("total_movimientos", 0),
                "ultimo_error": job_state.get("ultimo_error"),  # ← NUEVO
                "timestamp_inicio": job_state.get("timestamp_inicio"),
                "timestamp_fin": job_state.get("timestamp_fin"),
            },
            "eventos_recientes": [
                {
                    "timestamp": str(evt.get("timestamp", "N/A")),
                    "tipo": evt.get("event_type", "N/A"),
                    "banco": evt.get("banco"),
                    "descripcion": evt.get("descripcion", ""),
                    "confianza": evt.get("confianza"),
                    "monto": evt.get("monto"),
                    "journal_id": evt.get("journal_id"),
                    "movimiento_id": evt.get("movimiento_id"),
                }
                for evt in events
            ],
            "movimientos_causados": [
                {
                    "journal_id": m.get("journal_id"),
                    "fecha": m.get("fecha"),
                    "descripcion": m.get("descripcion"),
                    "monto": m.get("monto"),
                    "banco": m.get("banco"),
                    "procesado_at": m.get("procesado_at"),
                }
                for m in movimientos_causados
            ],
            "movimientos_pendientes": [
                {
                    "fecha": m.get("fecha"),
                    "descripcion": m.get("descripcion"),
                    "monto": m.get("monto"),
                    "banco": m.get("banco"),
                    "proveedor_extraido": m.get("proveedor_extraido"),
                    "confianza_sugerida": m.get("confianza_sugerida"),
                    "estado": m.get("estado"),
                    "creado_at": m.get("creado_at"),
                }
                for m in movimientos_pendientes
            ],
            "total_eventos": len(events),
            "total_causados_en_bd": len(movimientos_causados),
            "total_pendientes_en_bd": len(movimientos_pendientes),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LOGS] Error obteniendo logs del job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
