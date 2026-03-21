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
from dependencies import get_current_user, log_action
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
    logger.info(f"[🔄 Job {job_id}] INICIANDO procesamiento de extracto {banco}")

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

        # Clasificar
        logger.info(f"[🏷️  Job {job_id}] Clasificando movimientos...")
        causables, pendientes = await engine.clasificar_movimientos(movimientos)
        logger.info(f"[🏷️  Job {job_id}] ✅ {len(causables)} causables, {len(pendientes)} pendientes")
        await db.conciliacion_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "causables_total": len(causables),
                "pendientes_total": len(pendientes)
            }}
        )

        # Causar en Alegra
        logger.info(f"[💰 Job {job_id}] Causando {len(causables)} movimientos en Alegra...")
        for idx, mov in enumerate(causables, 1):
            logger.debug(f"[💰 Job {job_id}] [{idx}/{len(causables)}] Causando: {mov.descripcion} ${mov.monto:,.0f}")

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

            exitoso, journal_id, error = await engine.crear_journal_alegra(mov)
            if exitoso:
                _jobs_estado[job_id]["causados"] += 1
                logger.info(f"[✅ Job {job_id}] Journal {journal_id} creado para {mov.descripcion}")
                # Guardar hash del movimiento como procesado
                await db.conciliacion_movimientos_procesados.insert_one({
                    "hash": hash_movimiento,
                    "banco": banco,
                    "fecha": mov.fecha,
                    "descripcion": mov.descripcion,
                    "monto": mov.monto,
                    "journal_id": journal_id,
                    "procesado_at": datetime.now(timezone.utc).isoformat(),
                })
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
                _jobs_estado[job_id]["errores"] += 1
                logger.error(f"[❌ Job {job_id}] Error causando {mov.descripcion}: {error}")
                # Actualizar errores en MongoDB
                await db.conciliacion_jobs.update_one(
                    {"job_id": job_id},
                    {"$inc": {"errores": 1}}
                )

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

        # Guardar hash del extracto como procesado
        await db.conciliacion_extractos_procesados.insert_one({
            "hash": hash_extracto,
            "banco": banco.lower(),
            "fecha": fecha,
            "procesado_at": datetime.now(timezone.utc).isoformat(),
            "journals_creados": _jobs_estado[job_id]["causados"],
            "movimientos_pendientes": _jobs_estado[job_id]["pendientes"],
            "usuario": usuario_id,
            "job_id": job_id,
        })

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
        _jobs_estado[job_id]["timestamp_fin"] = datetime.now(timezone.utc).isoformat()
        # Guardar error en MongoDB
        await db.conciliacion_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "error": str(e),
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
        extracto_existente = await db.conciliacion_extractos_procesados.find_one({
            "hash": hash_extracto,
            "banco": banco.lower(),
        })

        if extracto_existente:
            logger.warning(f"[DUPLICADO] Extracto {banco} del {fecha} ya fue procesado")
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

        # Guardar hash del extracto como procesado
        await db.conciliacion_extractos_procesados.insert_one({
            "hash": hash_extracto,
            "banco": banco.lower(),
            "fecha": fecha,
            "procesado_at": datetime.now(timezone.utc).isoformat(),
            "journals_creados": causados,
            "movimientos_pendientes": pendientes_count,
            "usuario": current_user,
        })

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
