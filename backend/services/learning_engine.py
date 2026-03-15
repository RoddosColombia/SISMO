"""learning_engine.py — BUILD 9: Capa de Aprendizaje RODDOS.

Observa gestiones de cobranza, detecta patrones de comportamiento por cliente
y segmento, y genera recomendaciones que mejoran con el tiempo.

Colecciones usadas:
  learning_outcomes  — 1 doc por gestión registrada
  learning_patterns  — patrones aprendidos (contactabilidad / template / deterioro / contable)
"""
import uuid
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta, date

logger = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

SCORE_BASE: dict[str, float] = {
    "A+": 0.05, "A": 0.10, "B": 0.25, "C": 0.45, "D": 0.65, "E": 0.90,
}

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Plantillas default por bucket (fallback cuando no hay patrón aprendido)
DEFAULT_TEMPLATES: dict[str, str] = {
    "AL_DIA":      "Hola {nombre}, te recordamos que tu cuota #{num_cuota} por {valor} vence {fecha}. ¡Gracias por tu puntualidad!",
    "HOY":         "Hola {nombre}, hoy {fecha} vence tu cuota #{num_cuota} por {valor}. Recuerda enviarnos el comprobante 📸.",
    "ACTIVO":      "Hola {nombre}, tu cuota #{num_cuota} por {valor} venció el {fecha}. Por favor contáctanos hoy para ponerte al día.",
    "URGENTE":     "Hola {nombre}, llevas {dpd} días con tu cuota #{num_cuota} vencida ({valor}). Contáctanos urgente para evitar cargos adicionales.",
    "CRITICO":     "Atención {nombre}: adeudas {valor} ({dpd} días en mora). Tienes 7 días para regularizar antes de iniciar el proceso de recuperación.",
    "RECUPERACION":"Proceso activo: {nombre} adeuda {valor} ({dpd}d mora). Se requiere contacto inmediato con RODDOS.",
}

RESULTADOS_POSITIVOS = frozenset({
    "contestó_pagará_hoy", "contestó_prometió_fecha",
    "respondió_pagará", "respondió_prometió_fecha",
    "acuerdo_de_pago_firmado",
})


# ── TAREA 2 — Crear outcome ────────────────────────────────────────────────────

async def crear_outcome(db, gestion_data: dict) -> str:
    """Crea learning_outcome al registrar una gestión. No bloquea la respuesta."""
    try:
        loanbook_id = gestion_data.get("loanbook_id", "")
        now_dt = datetime.now(timezone.utc)
        created_at_raw = gestion_data.get("created_at", now_dt.isoformat())

        # Parsear hora/día de semana desde created_at
        try:
            if isinstance(created_at_raw, str):
                dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            else:
                dt = created_at_raw
        except Exception:
            dt = now_dt

        # Enriquecer con datos del loanbook
        dpd = 0
        bucket = "AL_DIA"
        score = "C"
        cliente_id = ""
        try:
            loan = await db.loanbook.find_one(
                {"id": loanbook_id},
                {"_id": 0, "dpd_actual": 1, "dpd_bucket": 1, "score_pago": 1, "cliente_id": 1},
            )
            if loan:
                dpd = loan.get("dpd_actual", 0)
                raw_bucket = loan.get("dpd_bucket", "0")
                # Normalizar dpd_bucket a bucket label
                bucket = _bucket_label(raw_bucket, dpd)
                score = loan.get("score_pago", "C") or "C"
                cliente_id = loan.get("cliente_id", "")
        except Exception as e:
            logger.warning("[LearningEngine] crear_outcome loan lookup: %s", e)

        outcome_id = str(uuid.uuid4())
        doc = {
            "outcome_id":           outcome_id,
            "loanbook_id":          loanbook_id,
            "cliente_id":           cliente_id,
            "gestion_fecha":        gestion_data.get("created_at", now_dt.isoformat()),
            "gestion_canal":        gestion_data.get("canal", ""),
            "gestion_dia_semana":   dt.weekday(),      # 0=Lunes, 6=Domingo
            "gestion_hora":         dt.hour,
            "dpd_al_gestionar":     dpd,
            "bucket_al_gestionar":  bucket,
            "score_al_gestionar":   score,
            "template_usado":       gestion_data.get("template_usado", None),
            "resultado_gestion":    gestion_data.get("resultado", ""),
            "ptp_fecha_acordada":   gestion_data.get("ptp_fecha", None),
            "ptp_monto_acordado":   gestion_data.get("ptp_monto", None),
            "pago_ocurrido":        None,   # se resuelve en 3 días
            "pago_fecha":           None,
            "dias_hasta_pago":      None,
            "ptp_cumplido":         None,
            "dpd_post_gestion":     None,
            "tendencia_pago":       None,
            "procesado":            False,
            "creado_en":            now_dt.isoformat(),
        }
        await db.learning_outcomes.insert_one(doc)
        doc.pop("_id", None)
        logger.debug("[LearningEngine] outcome creado: %s → %s", outcome_id, loanbook_id)
        return outcome_id

    except Exception as e:
        logger.error("[LearningEngine] crear_outcome error: %s", e)
        return ""


# ── TAREA 2 — Resolver outcomes pendientes ────────────────────────────────────

async def resolver_outcomes_pendientes(db) -> int:
    """Verifica outcomes de 3+ días atrás y determina si se produjo un pago."""
    try:
        hace_3_dias = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        pending = await db.learning_outcomes.find(
            {
                "pago_ocurrido": None,
                "gestion_fecha": {"$lt": hace_3_dias},
            },
            {"_id": 0},
        ).to_list(2000)

        resueltos = 0
        for outcome in pending:
            loanbook_id = outcome.get("loanbook_id", "")
            gestion_fecha = outcome.get("gestion_fecha", "")

            try:
                loan = await db.loanbook.find_one(
                    {"id": loanbook_id},
                    {"_id": 0, "cuotas": 1, "dpd_actual": 1},
                )
                if not loan:
                    continue

                cuotas = loan.get("cuotas", [])
                pago_ocurrido = False
                pago_fecha = None
                dias_hasta_pago = None
                ptp_cumplido = None

                # Buscar cuota pagada DESPUÉS de la gestión
                for cuota in cuotas:
                    if cuota.get("estado") == "pagada":
                        fecha_pago = cuota.get("fecha_pago") or cuota.get("fecha_vencimiento", "")
                        if fecha_pago > gestion_fecha[:10]:
                            pago_ocurrido = True
                            pago_fecha = fecha_pago
                            try:
                                g_date = date.fromisoformat(gestion_fecha[:10])
                                p_date = date.fromisoformat(fecha_pago[:10])
                                dias_hasta_pago = (p_date - g_date).days
                            except Exception:
                                dias_hasta_pago = None
                            break

                # Verificar PTP cumplido
                ptp_fecha_acordada = outcome.get("ptp_fecha_acordada")
                if ptp_fecha_acordada and pago_ocurrido and pago_fecha:
                    try:
                        ptp_dt  = date.fromisoformat(ptp_fecha_acordada[:10])
                        pago_dt = date.fromisoformat(pago_fecha[:10])
                        ptp_cumplido = pago_dt <= ptp_dt + timedelta(days=1)
                    except Exception:
                        ptp_cumplido = None

                dpd_post = loan.get("dpd_actual", 0)

                await db.learning_outcomes.update_one(
                    {"outcome_id": outcome["outcome_id"]},
                    {"$set": {
                        "pago_ocurrido":    pago_ocurrido,
                        "pago_fecha":       pago_fecha,
                        "dias_hasta_pago":  dias_hasta_pago,
                        "ptp_cumplido":     ptp_cumplido,
                        "dpd_post_gestion": dpd_post,
                        "procesado":        False,   # listo para el motor de patrones
                    }},
                )
                resueltos += 1

            except Exception as ex:
                logger.warning("[LearningEngine] resolver outcome %s: %s",
                               outcome.get("outcome_id"), ex)

        logger.info("[LearningEngine] resolver_outcomes_pendientes: %d resueltos", resueltos)
        return resueltos

    except Exception as e:
        logger.error("[LearningEngine] resolver_outcomes_pendientes error: %s", e)
        return 0


# ── TAREA 2 — Procesar patrones semanales ─────────────────────────────────────

async def procesar_patrones_semanales(db) -> dict:
    """Extrae patrones de contactabilidad, template y señal de deterioro."""
    try:
        unprocessed = await db.learning_outcomes.find(
            {"procesado": False, "pago_ocurrido": {"$ne": None}},
            {"_id": 0},
        ).to_list(5000)

        if not unprocessed:
            logger.info("[LearningEngine] procesar_patrones: sin outcomes nuevos")
            return {"nuevos": 0, "actualizados": 0}

        # ── Agrupar por loanbook_id ───────────────────────────────────────────
        by_loan: dict[str, list] = defaultdict(list)
        for o in unprocessed:
            by_loan[o["loanbook_id"]].append(o)

        nuevos = actualizados = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        # ── PATRÓN CONTACTABILIDAD (individual, muestra_n >= 5) ──────────────
        for loanbook_id, outcomes in by_loan.items():
            resueltos = [o for o in outcomes if o.get("pago_ocurrido") is not None]
            if len(resueltos) < 5:
                continue

            # Mejor canal
            canal_pagos: Counter = Counter()
            canal_total: Counter = Counter()
            dia_pagos:   Counter = Counter()
            hora_pagos:  Counter = Counter()
            pagos_total = 0

            for o in resueltos:
                canal = o.get("gestion_canal", "")
                dia   = o.get("gestion_dia_semana", 0)
                hora  = o.get("gestion_hora", 9)
                pagado = o.get("pago_ocurrido", False)

                canal_total[canal] += 1
                dia_pagos[dia] += (1 if pagado else 0)
                hora_pagos[hora] += (1 if pagado else 0)

                if pagado:
                    canal_pagos[canal] += 1
                    pagos_total += 1

            tasa_respuesta = round(pagos_total / max(len(resueltos), 1), 3)
            mejor_canal = canal_pagos.most_common(1)[0][0] if canal_pagos else "whatsapp"
            mejor_dia_semana = dia_pagos.most_common(1)[0][0] if dia_pagos else 2
            mejor_hora = hora_pagos.most_common(1)[0][0] if hora_pagos else 9
            confianza = min(0.99, len(resueltos) / 20)  # crece con muestra

            pattern_data = {
                "mejor_canal":        mejor_canal,
                "mejor_dia_semana":   mejor_dia_semana,
                "mejor_dia_nombre":   DIAS_ES[mejor_dia_semana],
                "mejor_hora":         mejor_hora,
                "mejor_hora_rango":   f"{mejor_hora:02d}:00-{(mejor_hora+3)%24:02d}:00",
                "tasa_respuesta":     tasa_respuesta,
                "total_outcomes":     len(resueltos),
            }

            result = await db.learning_patterns.find_one_and_update(
                {"tipo": "contactabilidad_cliente", "entidad_id": loanbook_id},
                {"$set": {
                    "tipo":                 "contactabilidad_cliente",
                    "entidad_id":           loanbook_id,
                    "scope":                "individual",
                    "datos":                pattern_data,
                    "muestra_n":            len(resueltos),
                    "confianza":            confianza,
                    "ultima_actualizacion": now_iso,
                    "activo":               True,
                }},
                upsert=True, return_document=True,
            )
            if result is None:
                nuevos += 1
            else:
                actualizados += 1

        # ── PATRÓN TEMPLATE (segmento bucket+score, muestra_n >= 10) ─────────
        by_segment: dict[str, list] = defaultdict(list)
        for o in unprocessed:
            key = f"{o.get('bucket_al_gestionar','?')}::{o.get('score_al_gestionar','?')}"
            tmpl = o.get("template_usado")
            if tmpl:
                by_segment[key].append(o)

        for seg_key, outcomes in by_segment.items():
            if len(outcomes) < 10:
                continue
            bucket_seg, score_seg = seg_key.split("::", 1)
            tmpl_pagos:  Counter = Counter()
            tmpl_total: Counter = Counter()
            for o in outcomes:
                tmpl = o.get("template_usado", "default")
                tmpl_total[tmpl] += 1
                if o.get("pago_ocurrido"):
                    tmpl_pagos[tmpl] += 1

            tasas = {t: round(tmpl_pagos[t] / max(tmpl_total[t], 1), 3)
                     for t in tmpl_total}
            mejor_template = max(tasas, key=lambda t: tasas[t])
            confianza = min(0.99, len(outcomes) / 30)

            await db.learning_patterns.find_one_and_update(
                {"tipo": "template_efectividad",
                 "entidad_id": seg_key},
                {"$set": {
                    "tipo":                 "template_efectividad",
                    "entidad_id":           seg_key,
                    "scope":                "segmento",
                    "datos": {
                        "bucket": bucket_seg, "score": score_seg,
                        "tasas_por_template": tasas,
                        "mejor_template": mejor_template,
                    },
                    "muestra_n":            len(outcomes),
                    "confianza":            confianza,
                    "ultima_actualizacion": now_iso,
                    "activo":               True,
                }},
                upsert=True, return_document=True,
            )
            nuevos += 1

        # ── SEÑAL DETERIORO (individual, >= 3 pagos en historial) ────────────
        for loanbook_id, outcomes in by_loan.items():
            resueltos = [o for o in outcomes if o.get("pago_ocurrido") is not None]
            if len(resueltos) < 3:
                continue

            # Obtener datos del loanbook para tendencia
            try:
                loan = await db.loanbook.find_one(
                    {"id": loanbook_id},
                    {"_id": 0, "cuotas": 1, "score_pago": 1, "dpd_actual": 1, "gestiones": 1},
                )
                if not loan:
                    continue

                cuotas = loan.get("cuotas", [])
                gestiones_loan = loan.get("gestiones", [])
                score_actual = loan.get("score_pago", "C") or "C"
                dpd_actual = loan.get("dpd_actual", 0)

                # Cuotas pagadas con DPD al pagar — últimas 4
                pagadas_con_dpd = sorted(
                    [c for c in cuotas if c.get("estado") == "pagada" and c.get("dpd_al_pagar") is not None],
                    key=lambda c: c.get("fecha_vencimiento", ""),
                )[-4:]

                tendencia = "estable"
                if len(pagadas_con_dpd) >= 3:
                    dpd_vals = [c.get("dpd_al_pagar", 0) for c in pagadas_con_dpd]
                    if dpd_vals[-1] > dpd_vals[0] and all(
                        dpd_vals[i] <= dpd_vals[i + 1] for i in range(len(dpd_vals) - 1)
                    ):
                        tendencia = "deteriorando"
                    elif dpd_vals[-1] < dpd_vals[0]:
                        tendencia = "mejorando"

                # Preventivos ignorados (visto_sin_respuesta en gestiones recientes)
                preventivos_ignorados = sum(
                    1 for g in gestiones_loan[-10:]
                    if g.get("resultado") == "visto_sin_respuesta"
                )

                # PTP incumplido reciente
                ptp_incumplido = any(
                    o.get("ptp_fecha_acordada") and o.get("ptp_cumplido") is False
                    for o in resueltos[-5:]
                )

                # Fórmula probabilidad_mora
                prob = SCORE_BASE.get(score_actual, 0.45)
                if tendencia == "deteriorando":
                    prob += 0.20
                if preventivos_ignorados >= 2:
                    prob += 0.15
                if ptp_incumplido:
                    prob += 0.15
                prob = min(0.99, round(prob, 3))

                señales = []
                if tendencia == "deteriorando":
                    señales.append("Pagos cada vez más tardíos")
                if preventivos_ignorados >= 2:
                    señales.append(f"{preventivos_ignorados} recordatorios ignorados")
                if ptp_incumplido:
                    señales.append("PTP incumplido reciente")

                accion = (
                    "Contactar HOY por llamada directa" if prob >= 0.75
                    else "Enviar WhatsApp personalizado esta semana"
                )

                confianza_det = min(0.99, len(resueltos) / 15)

                await db.learning_patterns.find_one_and_update(
                    {"tipo": "señal_deterioro", "entidad_id": loanbook_id},
                    {"$set": {
                        "tipo":        "señal_deterioro",
                        "entidad_id":  loanbook_id,
                        "scope":       "individual",
                        "datos": {
                            "probabilidad_mora":   prob,
                            "tendencia":           tendencia,
                            "preventivos_ignorados": preventivos_ignorados,
                            "ptp_incumplido":      ptp_incumplido,
                            "señales":             señales,
                            "accion_sugerida":     accion,
                            "dpd_actual":          dpd_actual,
                        },
                        "muestra_n":            len(resueltos),
                        "confianza":            confianza_det,
                        "ultima_actualizacion": now_iso,
                        "activo":               True,
                    }},
                    upsert=True, return_document=True,
                )
                nuevos += 1

            except Exception as ex:
                logger.warning("[LearningEngine] señal_deterioro %s: %s", loanbook_id, ex)

        # Marcar todos como procesados
        outcome_ids = [o["outcome_id"] for o in unprocessed]
        if outcome_ids:
            await db.learning_outcomes.update_many(
                {"outcome_id": {"$in": outcome_ids}},
                {"$set": {"procesado": True}},
            )

        logger.info("[LearningEngine] procesar_patrones: %d nuevos, %d actualizados", nuevos, actualizados)
        return {"nuevos": nuevos, "actualizados": actualizados}

    except Exception as e:
        logger.error("[LearningEngine] procesar_patrones_semanales error: %s", e)
        return {"nuevos": 0, "actualizados": 0}


# ── TAREA 2 — Recomendación de contacto ───────────────────────────────────────

async def get_recomendacion_contacto(db, loanbook_id: str) -> dict:
    """Retorna recomendación de cuándo/cómo contactar al cliente."""
    try:
        # 1. Buscar patrón individual
        patron = await db.learning_patterns.find_one(
            {"tipo": "contactabilidad_cliente",
             "entidad_id": loanbook_id,
             "activo": True},
            {"_id": 0},
        )

        if patron and patron.get("confianza", 0) >= 0.6:
            d = patron["datos"]
            dia_nombre = DIAS_ES[d.get("mejor_dia_semana", 2)]
            return {
                "tiene_patron":    True,
                "scope":           "individual",
                "recomendacion":   (
                    f"Contactar el {dia_nombre} entre {d.get('mejor_hora_rango','09:00-12:00')} "
                    f"por {d.get('mejor_canal','whatsapp')}"
                ),
                "canal":           d.get("mejor_canal", "whatsapp"),
                "dia_sugerido":    dia_nombre,
                "hora_sugerida":   d.get("mejor_hora_rango", "09:00-12:00"),
                "tasa_exito":      round(d.get("tasa_respuesta", 0) * 100, 1),
                "confianza":       patron.get("confianza", 0),
            }

        # 2. Sin patrón individual — buscar por segmento si hay bucket+score en loan
        loan = await db.loanbook.find_one(
            {"id": loanbook_id},
            {"_id": 0, "dpd_actual": 1, "dpd_bucket": 1, "score_pago": 1},
        )
        if loan:
            bucket = _bucket_label(loan.get("dpd_bucket", "0"), loan.get("dpd_actual", 0))
            score  = loan.get("score_pago", "C") or "C"
            seg_key = f"{bucket}::{score}"
            seg_patron = await db.learning_patterns.find_one(
                {"tipo": "contactabilidad_cliente",
                 "scope": "segmento",
                 "entidad_id": seg_key,
                 "activo": True},
                {"_id": 0},
            )
            if seg_patron and seg_patron.get("confianza", 0) >= 0.5:
                d = seg_patron["datos"]
                dia_nombre = DIAS_ES[d.get("mejor_dia_semana", 2)]
                return {
                    "tiene_patron":  True,
                    "scope":         "segmento",
                    "recomendacion": (
                        f"Clientes similares ({bucket}/{score}) responden mejor el "
                        f"{dia_nombre} por {d.get('mejor_canal','whatsapp')}"
                    ),
                    "canal":         d.get("mejor_canal", "whatsapp"),
                    "dia_sugerido":  dia_nombre,
                    "hora_sugerida": d.get("mejor_hora_rango", "09:00-12:00"),
                    "tasa_exito":    round(d.get("tasa_respuesta", 0) * 100, 1),
                    "confianza":     seg_patron.get("confianza", 0),
                }

        # 3. Recomendación genérica por bucket
        return _recomendacion_generica(loan)

    except Exception as e:
        logger.error("[LearningEngine] get_recomendacion_contacto: %s", e)
        return {"tiene_patron": False, "recomendacion": "Contactar miércoles o jueves por WhatsApp",
                "canal": "whatsapp", "dia_sugerido": "Miércoles",
                "hora_sugerida": "09:00-12:00", "tasa_exito": 0.0, "confianza": 0.0}


def _recomendacion_generica(loan: dict | None) -> dict:
    if not loan:
        return {"tiene_patron": False, "recomendacion": "Contactar miércoles por WhatsApp",
                "canal": "whatsapp", "dia_sugerido": "Miércoles",
                "hora_sugerida": "09:00-12:00", "tasa_exito": 0.0, "confianza": 0.0}
    dpd = loan.get("dpd_actual", 0)
    if dpd >= 15:
        return {"tiene_patron": False, "recomendacion": "Llamada directa urgente — alta mora",
                "canal": "llamada", "dia_sugerido": "Hoy",
                "hora_sugerida": "09:00-17:00", "tasa_exito": 0.0, "confianza": 0.0}
    if dpd >= 1:
        return {"tiene_patron": False, "recomendacion": "WhatsApp hoy — cliente en mora",
                "canal": "whatsapp", "dia_sugerido": "Hoy",
                "hora_sugerida": "09:00-12:00", "tasa_exito": 0.0, "confianza": 0.0}
    return {"tiene_patron": False, "recomendacion": "Recordatorio preventivo el martes por WhatsApp",
            "canal": "whatsapp", "dia_sugerido": "Martes",
            "hora_sugerida": "09:00-12:00", "tasa_exito": 0.0, "confianza": 0.0}


# ── TAREA 2 — Alerta de deterioro ─────────────────────────────────────────────

async def get_alerta_deterioro(db, loanbook_id: str) -> dict | None:
    """Retorna alerta predictiva si probabilidad_mora > 0.60 y DPD == 0."""
    try:
        loan = await db.loanbook.find_one(
            {"id": loanbook_id},
            {"_id": 0, "dpd_actual": 1},
        )
        if not loan or loan.get("dpd_actual", 0) != 0:
            return None

        patron = await db.learning_patterns.find_one(
            {"tipo": "señal_deterioro", "entidad_id": loanbook_id, "activo": True},
            {"_id": 0},
        )
        if not patron:
            return None

        d = patron.get("datos", {})
        prob = d.get("probabilidad_mora", 0)
        if prob <= 0.60:
            return None

        return {
            "alerta":           True,
            "probabilidad":     prob,
            "señales":          d.get("señales", []),
            "accion_sugerida":  d.get("accion_sugerida", "Contactar preventivamente"),
            "tendencia":        d.get("tendencia", "estable"),
            "confianza":        patron.get("confianza", 0),
        }

    except Exception as e:
        logger.error("[LearningEngine] get_alerta_deterioro: %s", e)
        return None


# ── TAREA 2 — Template óptimo ─────────────────────────────────────────────────

async def get_template_optimo(db, bucket: str, score: str) -> str:
    """Retorna el ID del template con mayor tasa de pago para el segmento dado.
    Si no hay patrón suficiente → retorna 'default' para usar el template fijo del bucket.
    """
    try:
        seg_key = f"{bucket}::{score}"
        patron = await db.learning_patterns.find_one(
            {"tipo": "template_efectividad",
             "entidad_id": seg_key,
             "activo": True,
             "confianza": {"$gte": 0.5}},
            {"_id": 0},
        )
        if patron:
            d = patron.get("datos", {})
            mejor = d.get("mejor_template", "default")
            logger.debug("[LearningEngine] template_optimo %s → %s (confianza=%.2f)",
                         seg_key, mejor, patron.get("confianza", 0))
            return mejor
    except Exception as e:
        logger.warning("[LearningEngine] get_template_optimo: %s", e)

    return "default"


# ── Métricas para CFO ─────────────────────────────────────────────────────────

async def get_metricas_predictivas(db) -> dict:
    """Métricas de aprendizaje para el agente CFO."""
    try:
        hace_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        # Efectividad por canal (últimos 30 días)
        outcomes_30d = await db.learning_outcomes.find(
            {"creado_en": {"$gte": hace_30d}, "pago_ocurrido": {"$ne": None}},
            {"_id": 0, "gestion_canal": 1, "pago_ocurrido": 1},
        ).to_list(5000)

        canal_total: Counter = Counter()
        canal_pagos: Counter = Counter()
        for o in outcomes_30d:
            c = o.get("gestion_canal", "otro")
            canal_total[c] += 1
            if o.get("pago_ocurrido"):
                canal_pagos[c] += 1

        efectividad_canal = {
            c: round(canal_pagos[c] / max(canal_total[c], 1) * 100, 1)
            for c in canal_total
        }

        # Clientes en riesgo predictivo (prob > 0.70, DPD=0)
        patrones_riesgo = await db.learning_patterns.count_documents(
            {"tipo": "señal_deterioro",
             "activo": True,
             "datos.probabilidad_mora": {"$gt": 0.70},
             "datos.dpd_actual": 0}
        )

        # Tendencia mora (roll_rate últimas 4 semanas)
        # Para simplicidad: comparar conteo en_mora hace 2 semanas vs ahora
        tendencia_mora = "estable"
        try:
            hace_2s = (datetime.now(timezone.utc) - timedelta(weeks=2)).isoformat()
            count_actual = await db.loanbook.count_documents({"estado": "mora"})
            snaps = await db.roddos_events.find(
                {"event_type": "loanbook.bucket_change",
                 "new_state": "22+",
                 "timestamp": {"$gte": hace_2s}},
                {"_id": 0},
            ).to_list(500)
            if len(snaps) > 3:
                tendencia_mora = "deteriorando"
            elif count_actual == 0:
                tendencia_mora = "mejorando"
        except Exception:
            pass

        return {
            "efectividad_canal":           efectividad_canal,
            "clientes_en_riesgo_predictivo": patrones_riesgo,
            "tendencia_mora":              tendencia_mora,
            "outcomes_last_30d":           len(outcomes_30d),
        }

    except Exception as e:
        logger.error("[LearningEngine] get_metricas_predictivas: %s", e)
        return {"efectividad_canal": {}, "clientes_en_riesgo_predictivo": 0,
                "tendencia_mora": "estable", "outcomes_last_30d": 0}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bucket_label(dpd_bucket: str, dpd: int) -> str:
    """Convierte dpd_bucket string a label de bucket UI."""
    if dpd == 0:
        return "AL_DIA"
    if dpd_bucket in ("1-7",):
        return "ACTIVO"
    if dpd_bucket in ("8-14",):
        return "URGENTE"
    if dpd_bucket in ("15-21",):
        return "CRITICO"
    if dpd_bucket in ("22+",):
        return "RECUPERACION"
    # Fallback por DPD
    if dpd <= 7:
        return "ACTIVO"
    if dpd <= 14:
        return "URGENTE"
    if dpd <= 21:
        return "CRITICO"
    return "RECUPERACION"
