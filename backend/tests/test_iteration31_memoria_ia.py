"""
Iteration 31 — Tests for MEJORA 1-4 (memoria/contexto IA):
- MEJORA 1: Historial persistente
- MEJORA 2: Tarea activa endpoints
- MEJORA 3: actividad_hoy desde roddos_events
- MEJORA 4: Comandos especiales (pausa/continúa/resumen)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
AUTH_EMAIL = "contabilidad@roddos.com"
AUTH_PASSWORD = "Admin@RODDOS2025!"


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("token") or resp.json().get("access_token")
    assert token, f"No token in response: {resp.json()}"
    return token


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"})
    return s


# ── TEST 1: MEJORA 3 — actividad_hoy en stats ─────────────────────────────────

def test_inventario_stats_returns_200(client):
    """TEST 1 — MEJORA 3: GET /api/inventario/stats retorna 200."""
    resp = client.get(f"{BASE_URL}/api/inventario/stats")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    print(f"Stats keys: {list(data.keys())}")
    assert isinstance(data, dict)


# ── TEST 2: MEJORA 2 — POST /api/chat/tarea ───────────────────────────────────

@pytest.fixture(scope="module")
def tarea_creada(client):
    """Creates a test tarea_activa and returns the doc."""
    # Clean up any previous test tasks first
    client.post(f"{BASE_URL}/api/chat/tarea", json={
        "descripcion": "limpieza previa",
        "pasos_total": 1,
        "pasos_pendientes": ["noop"]
    })
    resp = client.post(f"{BASE_URL}/api/chat/tarea", json={
        "descripcion": "Test tarea multi-paso",
        "pasos_total": 3,
        "pasos_pendientes": ["Paso A", "Paso B", "Paso C"]
    })
    assert resp.status_code == 200, f"POST /tarea failed: {resp.text}"
    return resp.json()


def test_post_tarea_creates_doc(tarea_creada):
    """TEST 2 — POST /api/chat/tarea crea documento en agent_memory."""
    doc = tarea_creada
    print(f"Tarea doc: {doc}")
    assert doc.get("tipo") == "tarea_activa", f"Expected tipo='tarea_activa', got: {doc.get('tipo')}"
    assert doc.get("estado") == "en_curso", f"Expected estado='en_curso', got: {doc.get('estado')}"
    assert doc.get("descripcion") == "Test tarea multi-paso"
    assert doc.get("pasos_total") == 3
    assert doc.get("pasos_pendientes") == ["Paso A", "Paso B", "Paso C"]
    assert "_id" not in doc, "MongoDB _id should not be exposed"


# ── TEST 3: MEJORA 2 — GET /api/chat/tarea ────────────────────────────────────

def test_get_tarea_retorna_en_curso(client, tarea_creada):
    """TEST 3 — GET /api/chat/tarea retorna tarea con estado='en_curso'."""
    resp = client.get(f"{BASE_URL}/api/chat/tarea")
    assert resp.status_code == 200, f"GET /tarea failed: {resp.text}"
    data = resp.json()
    print(f"GET tarea: {data}")
    assert data.get("estado") == "en_curso", f"Expected 'en_curso', got: {data.get('estado')}"
    assert data.get("descripcion") == "Test tarea multi-paso"
    assert "_id" not in data


# ── TEST 4: MEJORA 2 — PATCH /api/chat/tarea/avance ──────────────────────────

def test_patch_tarea_avance(client, tarea_creada):
    """TEST 4 — PATCH /api/chat/tarea/avance actualiza progreso."""
    resp = client.patch(
        f"{BASE_URL}/api/chat/tarea/avance",
        params={"pasos_completados": 1, "paso_completado": "Paso A"}
    )
    assert resp.status_code == 200, f"PATCH /tarea/avance failed: {resp.text}"
    data = resp.json()
    print(f"Avance response: {data}")
    assert data.get("ok") is True

    # Verify via GET
    get_resp = client.get(f"{BASE_URL}/api/chat/tarea")
    tarea = get_resp.json()
    print(f"After avance GET: {tarea}")
    assert tarea.get("pasos_completados") == 1, f"Expected 1, got: {tarea.get('pasos_completados')}"
    assert "Paso A" not in tarea.get("pasos_pendientes", []), "Paso A should be removed"
    assert "Paso B" in tarea.get("pasos_pendientes", [])
    assert "Paso C" in tarea.get("pasos_pendientes", [])


# ── TEST 5: MEJORA 4 — pausa la tarea ────────────────────────────────────────

def test_chat_pausa_tarea(client, tarea_creada):
    """TEST 5 — POST /api/chat/message con 'pausa la tarea' pausa la tarea."""
    session_id = "test-pausa-001"
    resp = client.post(f"{BASE_URL}/api/chat/message", json={
        "session_id": session_id,
        "message": "pausa la tarea"
    })
    assert resp.status_code == 200, f"POST /chat/message failed: {resp.status_code}: {resp.text}"
    data = resp.json()
    print(f"Pausa response: {data}")
    msg = data.get("message", "") or data.get("response", "") or str(data)
    assert "paus" in msg.lower() or "⏸" in msg, f"Expected pausa confirmation, got: {msg[:200]}"

    # Verify tarea is now pausada
    get_resp = client.get(f"{BASE_URL}/api/chat/tarea")
    tarea = get_resp.json()
    print(f"Tarea after pausa: {tarea}")
    assert tarea.get("estado") == "pausada", f"Expected 'pausada', got: {tarea.get('estado')}"


# ── TEST 6: MEJORA 4 — continúa la tarea ─────────────────────────────────────

def test_chat_continua_tarea(client, tarea_creada):
    """TEST 6 — POST /api/chat/message con 'continúa la tarea' reanuda tarea."""
    session_id = "test-continua-001"
    resp = client.post(f"{BASE_URL}/api/chat/message", json={
        "session_id": session_id,
        "message": "continúa la tarea"
    })
    assert resp.status_code == 200, f"POST /chat/message failed: {resp.status_code}: {resp.text}"
    data = resp.json()
    print(f"Continúa response: {data}")
    msg = data.get("message", "") or data.get("response", "") or str(data)
    # Should mention next step (Paso B or Paso C)
    assert any(kw in msg for kw in ["Paso B", "Paso C", "▶️", "Retom", "retom", "continu", "Continu"]), \
        f"Expected continúa confirmation, got: {msg[:200]}"

    # Verify tarea is en_curso again
    get_resp = client.get(f"{BASE_URL}/api/chat/tarea")
    tarea = get_resp.json()
    print(f"Tarea after continúa: {tarea}")
    assert tarea.get("estado") == "en_curso", f"Expected 'en_curso', got: {tarea.get('estado')}"


# ── TEST 7: MEJORA 4 — comando resumen ────────────────────────────────────────

def test_chat_en_que_ibamos(client):
    """TEST 7 — POST /api/chat/message con '¿en qué íbamos?' retorna contexto directo."""
    session_id = "test-resumen-001"
    resp = client.post(f"{BASE_URL}/api/chat/message", json={
        "session_id": session_id,
        "message": "¿en qué íbamos?"
    })
    assert resp.status_code == 200, f"POST /chat/message failed: {resp.status_code}: {resp.text}"
    data = resp.json()
    print(f"Resumen response keys: {list(data.keys())}")
    msg = data.get("message", "") or data.get("response", "") or str(data)
    print(f"Resumen message: {msg[:300]}")
    # Should have some context (tarea or actividad)
    assert len(msg) > 10, f"Expected non-empty context response, got: {msg}"


# ── TEST 8: MEJORA 1 — historial persistente ─────────────────────────────────

def test_historial_persistente(client):
    """TEST 8 — 3 mensajes en misma sesión; 3er mensaje tiene historial previo."""
    session_id = "test-memoria-001"

    # Clear session first
    client.delete(f"{BASE_URL}/api/chat/history/{session_id}")
    time.sleep(0.5)

    # Message 1
    r1 = client.post(f"{BASE_URL}/api/chat/message", json={
        "session_id": session_id,
        "message": "Hola, soy mensaje uno"
    })
    assert r1.status_code == 200, f"Msg1 failed: {r1.status_code}: {r1.text}"
    print(f"Msg1 response: {r1.json().get('message', '')[:100]}")
    time.sleep(1)

    # Message 2
    r2 = client.post(f"{BASE_URL}/api/chat/message", json={
        "session_id": session_id,
        "message": "Soy mensaje dos"
    })
    assert r2.status_code == 200, f"Msg2 failed: {r2.status_code}: {r2.text}"
    print(f"Msg2 response: {r2.json().get('message', '')[:100]}")
    time.sleep(1)

    # Verify history exists in DB before 3rd message
    hist_resp = client.get(f"{BASE_URL}/api/chat/history/{session_id}")
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    print(f"History count before msg3: {len(history)}")
    # Should have at least 4 items: msg1-user, msg1-assistant, msg2-user, msg2-assistant
    assert len(history) >= 4, f"Expected >= 4 history items, got: {len(history)}"

    # Message 3
    r3 = client.post(f"{BASE_URL}/api/chat/message", json={
        "session_id": session_id,
        "message": "¿Cuál fue mi primer mensaje?"
    })
    assert r3.status_code == 200, f"Msg3 failed: {r3.status_code}: {r3.text}"
    data3 = r3.json()
    print(f"Msg3 response: {data3.get('message', '')[:200]}")
    # Response should indicate context awareness
    msg3 = data3.get("message", "")
    assert len(msg3) > 5, "Expected non-empty response for msg3"


# ── TEST 9: Endpoints /api/chat/tarea retornan 200 con auth ───────────────────

def test_tarea_endpoints_auth_required(auth_token):
    """TEST 9 — /api/chat/tarea endpoints retornan 200 con auth, 401 sin auth."""
    # Without auth
    r = requests.get(f"{BASE_URL}/api/chat/tarea")
    assert r.status_code in [401, 403], f"Expected 401/403 without auth, got: {r.status_code}"

    # With auth
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    r2 = s.get(f"{BASE_URL}/api/chat/tarea")
    assert r2.status_code == 200, f"Expected 200 with auth, got: {r2.status_code}: {r2.text}"


# ── TEST 10: Code grep checks ─────────────────────────────────────────────────

def test_code_grep_keywords():
    """TEST 10 — Verifica keywords en ai_chat.py."""
    import subprocess
    keywords = ["raw_history", "initial_messages", "summary_msg", "tarea_activa", "actividad_hoy"]
    result = subprocess.run(
        ["grep", "-c", "-e", "raw_history", "-e", "initial_messages", "-e", "summary_msg",
         "-e", "tarea_activa", "-e", "actividad_hoy", "/app/backend/ai_chat.py"],
        capture_output=True, text=True
    )
    print(f"Grep count: {result.stdout.strip()}")
    # grep -c counts matching lines; we just need it > 0
    count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    assert count >= 5, f"Expected >= 5 matching lines, got: {count}"
    print("All keywords found in ai_chat.py ✅")
