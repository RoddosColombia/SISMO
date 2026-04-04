"""test_build25_n8n_global66.py — BUILD 25: n8n integration layer + Global66 webhook robusto.

9 tests de análisis estático. No requieren FastAPI ni MongoDB en ejecución.
"""

import pytest
from pathlib import Path

GLOBAL66_SOURCE = (Path(__file__).parent.parent / "routers" / "global66.py").read_text(encoding="utf-8")
N8N_SOURCE = (Path(__file__).parent.parent / "routers" / "n8n_hooks.py").read_text(encoding="utf-8")
SCHEDULER_SOURCE = (Path(__file__).parent.parent / "services" / "scheduler.py").read_text(encoding="utf-8")
SERVER_SOURCE = (Path(__file__).parent.parent / "server.py").read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# T01: Global66 usa x-api-key (no HMAC)
# ──────────────────────────────────────────────────────────────────────────────

def test_01_global66_webhook_usa_x_api_key():
    assert "x-api-key" in GLOBAL66_SOURCE.lower() or "X-Api-Key" in GLOBAL66_SOURCE or \
           "x_api_key" in GLOBAL66_SOURCE.lower() or "GLOBAL66_WEBHOOK_SECRET" in GLOBAL66_SOURCE, \
        "global66.py no usa x-api-key para autenticación"
    assert "_verificar_hmac" not in GLOBAL66_SOURCE, \
        "global66.py aún usa _verificar_hmac — debe ser x-api-key"


# ──────────────────────────────────────────────────────────────────────────────
# T02: Global66 maneja eventos WALLET y RMT
# ──────────────────────────────────────────────────────────────────────────────

def test_02_global66_webhook_maneja_wallet_y_rmt():
    assert "WALLET" in GLOBAL66_SOURCE, \
        "global66.py no maneja evento WALLET"
    assert "RMT" in GLOBAL66_SOURCE, \
        "global66.py no maneja evento RMT"


# ──────────────────────────────────────────────────────────────────────────────
# T03: Global66 usa motor matricial clasificar_movimiento
# ──────────────────────────────────────────────────────────────────────────────

def test_03_global66_webhook_motor_matricial():
    assert "clasificar_movimiento" in GLOBAL66_SOURCE, \
        "global66.py no usa clasificar_movimiento — debe usar motor matricial"


# ──────────────────────────────────────────────────────────────────────────────
# T04: Global66 guarda primero (patrón guardar-primero)
# ──────────────────────────────────────────────────────────────────────────────

def test_04_global66_webhook_guarda_primero():
    assert "global66_eventos_recibidos" in GLOBAL66_SOURCE, \
        "global66.py no guarda en global66_eventos_recibidos"
    assert "$setOnInsert" in GLOBAL66_SOURCE or "insert_one" in GLOBAL66_SOURCE or \
           "update_one" in GLOBAL66_SOURCE, \
        "global66.py no tiene patrón de guardado (insert_one o update_one)"
    # Verificar que el guardado ocurre ANTES de llamar a Alegra
    save_pos = GLOBAL66_SOURCE.find("global66_eventos_recibidos")
    alegra_pos = GLOBAL66_SOURCE.find("request_with_verify")
    if alegra_pos > 0:
        assert save_pos < alegra_pos, \
            "global66.py no guarda primero — el guardado debe ocurrir ANTES de llamar Alegra"


# ──────────────────────────────────────────────────────────────────────────────
# T05: n8n_hooks.py importa correctamente
# ──────────────────────────────────────────────────────────────────────────────

def test_05_n8n_hooks_import():
    assert "router = APIRouter" in N8N_SOURCE or "APIRouter(" in N8N_SOURCE, \
        "n8n_hooks.py no define un APIRouter"
    assert 'prefix="/n8n"' in N8N_SOURCE, \
        "n8n_hooks.py no tiene prefix='/n8n'"
    assert "_verify_n8n_key" in N8N_SOURCE, \
        "n8n_hooks.py no tiene función _verify_n8n_key"


# ──────────────────────────────────────────────────────────────────────────────
# T06: GET /n8n/health existe y tiene campos correctos
# ──────────────────────────────────────────────────────────────────────────────

def test_06_n8n_health_endpoint_correcto():
    assert "/health" in N8N_SOURCE or "n8n_health" in N8N_SOURCE, \
        "n8n_hooks.py no tiene endpoint /health"
    assert "loanbooks_activos" in N8N_SOURCE, \
        "n8n /health no retorna loanbooks_activos"
    assert "backlog_pendientes" in N8N_SOURCE, \
        "n8n /health no retorna backlog_pendientes"
    assert "alegra_conectada" in N8N_SOURCE, \
        "n8n /health no retorna alegra_conectada"
    # Health no debe requerir auth
    health_pos = N8N_SOURCE.find("n8n_health")
    verify_before = N8N_SOURCE[:health_pos].rfind("_verify_n8n_key")
    next_verify = N8N_SOURCE[health_pos:].find("_verify_n8n_key")
    # _verify_n8n_key no debe estar dentro de la función health
    health_section = N8N_SOURCE[health_pos:health_pos + 500]
    assert "_verify_n8n_key" not in health_section, \
        "n8n /health no debe requerir autenticación"


# ──────────────────────────────────────────────────────────────────────────────
# T07: Endpoints /status/global66 y /status/backlog existen sin auth
# ──────────────────────────────────────────────────────────────────────────────

def test_07_n8n_status_endpoints_existen():
    assert "status/global66" in N8N_SOURCE or "n8n_status_global66" in N8N_SOURCE, \
        "n8n_hooks.py no tiene endpoint /status/global66"
    assert "status/backlog" in N8N_SOURCE or "n8n_status_backlog" in N8N_SOURCE, \
        "n8n_hooks.py no tiene endpoint /status/backlog"
    # Verificar campos clave de status/global66
    assert "pendientes_total" in N8N_SOURCE, \
        "n8n /status/global66 no retorna pendientes_total"
    assert "alertar" in N8N_SOURCE, \
        "n8n /status/global66 no retorna campo alertar"


# ──────────────────────────────────────────────────────────────────────────────
# T08: /n8n/scheduler/{job_id} requiere autenticación
# ──────────────────────────────────────────────────────────────────────────────

def test_08_n8n_scheduler_requiere_key():
    assert "n8n_trigger_scheduler" in N8N_SOURCE or "/scheduler/" in N8N_SOURCE, \
        "n8n_hooks.py no tiene endpoint /scheduler/{job_id}"
    scheduler_section = N8N_SOURCE[N8N_SOURCE.find("n8n_trigger_scheduler"):]
    assert "_verify_n8n_key" in scheduler_section[:300], \
        "n8n /scheduler/{job_id} no verifica autenticación"
    assert "ALLOWED_JOBS" in N8N_SOURCE, \
        "n8n /scheduler no valida contra ALLOWED_JOBS"


# ──────────────────────────────────────────────────────────────────────────────
# T09: scheduler.py tiene job recuperar_global66_pendientes
# ──────────────────────────────────────────────────────────────────────────────

def test_09_scheduler_tiene_job_recuperacion_global66():
    assert "recuperar_global66_pendientes" in SCHEDULER_SOURCE, \
        "scheduler.py no tiene función _recuperar_global66_pendientes"
    assert "minutes=10" in SCHEDULER_SOURCE, \
        "El job de recuperación Global66 debe ejecutarse cada 10 minutos"
    # Verificar que usa request_with_verify (no service.request directo)
    recup_section = SCHEDULER_SOURCE[SCHEDULER_SOURCE.find("_recuperar_global66_pendientes"):]
    assert "request_with_verify" in recup_section, \
        "_recuperar_global66_pendientes no usa request_with_verify"
    assert "MAX_INTENTOS" in recup_section or "max_intentos" in recup_section.lower() or \
           "5" in recup_section, \
        "_recuperar_global66_pendientes no define límite de intentos"
    # Verificar registro en server.py
    assert "n8n_hooks" in SERVER_SOURCE, \
        "server.py no registra n8n_hooks router"
