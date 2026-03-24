# Testing Patterns

**Analysis Date:** 2026-03-24

## Test Framework

**Runner:**
- Backend: pytest
- Frontend: React Scripts / Create React App (no explicit test runner config, not actively tested)

**Assertion Library:**
- Backend: pytest assertions (standard `assert` statements)
- Frontend: Not detected (no test files found in src/)

**Run Commands:**
```bash
# Backend — typical pytest commands (tests/ directory structure)
pytest tests/test_roddos_backend.py           # Run specific test file
pytest tests/ -k "TestAuth"                   # Run tests matching pattern
pytest tests/test_build21_integration.py      # Run BUILD-specific tests

# Frontend — via package.json
npm test                                      # Run tests via craco
yarn test                                     # Run tests via yarn (package manager)
# Note: No active test suite found in frontend/src/ directory
```

**Test File Location:**
- Backend: `/c/Users/AndresSanJuan/roddos-workspace/SISMO/backend/tests/` directory (50+ test files)
- Frontend: No test files in `src/` — integration/e2e tests exist in `/c/Users/AndresSanJuan/roddos-workspace/SISMO/tests/`
- Smoke tests: Dedicated files like `smoke_test_build23.py` in project root for integration/regression testing

## Test File Organization

**Location:**
- Backend: Separate directory (`backend/tests/`) per pytest convention
- Frontend: Not tested with unit tests; only smoke/integration tests at project level
- Smoke tests: Root level scripts (`smoke_test_*.py`) for end-to-end validation

**Naming:**
- Pattern: `test_<feature>_<build|scope>.py`
- Examples:
  - `test_build21_integration.py` — BUILD 21 feature tests
  - `test_roddos_backend.py` — Core backend functionality
  - `test_mercately.py` — Mercately integration
  - `smoke_test_build23.py` — BUILD 23 end-to-end validation

**Structure:**
```
backend/tests/
├── test_roddos_backend.py                    # Core API tests (Auth, Alegra, Settings, Chat)
├── test_build21_integration.py               # BUILD 21 feature tests
├── test_build23_f2_chat_transactional.py     # BUILD 23 phase 2 tests
├── test_build23_f4_nomina_mensual.py         # BUILD 23 phase 4 tests
├── test_mercately.py                         # Mercately service tests
└── ... (40+ more test files per build/feature)

Project root:
├── smoke_test_build23.py                     # End-to-end smoke tests
└── run_smoke_test.py                         # Test runner script
```

## Test Structure

**Suite Organization:**
```python
# Backend pattern from test_build21_integration.py
class TestDiagnosticarContabilidadAction:
    """Verifica que la acción diagnosticar_contabilidad está disponible en execute_chat_action"""

    def test_action_exists_in_ai_chat(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        assert "diagnosticar_contabilidad" in source, "Action not found"

    def test_guardar_pendiente_exists(self):
        import ai_chat
        import inspect
        source = inspect.getsource(ai_chat.execute_chat_action)
        assert "guardar_pendiente" in source


# Async test pattern
class TestPendingTopicsTTL:
    """Verifica que la colección agent_pending_topics tiene índice TTL"""

    def test_ttl_index_exists(self):
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
        from motor.motor_asyncio import AsyncIOMotorClient

        async def check():
            client = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = client[os.environ['DB_NAME']]
            indexes = await db['agent_pending_topics'].index_information()
            return indexes

        indexes = asyncio.get_event_loop().run_until_complete(check())
        ttl_found = any(
            info.get('expireAfterSeconds') is not None
            for info in indexes.values()
        )
        assert ttl_found, f"No TTL index found"
```

**Patterns:**
- Setup: Load environment via `load_dotenv()`, import modules under test
- Teardown: None explicit; MongoDB/Motor cleanup handled by connection close
- Assertion: Direct `assert` statements with custom error messages
- Fixtures: Not used; inline setup or class-level methods for shared state
- Skip markers: Not observed

## Mocking

**Framework:**
- `unittest.mock`: `MagicMock`, `AsyncMock`, `patch` for mocking imports and functions
- No pytest fixtures for fixtures/factories

**Patterns:**
```python
from unittest.mock import MagicMock, AsyncMock, patch

# Mock imports
@patch('ai_chat.execute_chat_action')
def test_something(mock_action):
    mock_action.return_value = "expected_result"
    # test code

# Async mocks
mock_async = AsyncMock(return_value={"key": "value"})
result = asyncio.get_event_loop().run_until_complete(mock_async())
```

**What to Mock:**
- External services: Alegra API calls (when testing without real credentials)
- Database: MongoDB operations when testing application logic in isolation
- File I/O: When testing CSV parsing or upload logic
- HTTP calls: httpx requests to external APIs

**What NOT to Mock:**
- Core application logic: Execute full business logic paths
- Authentication: Test actual token generation/verification
- Database schema: Test with real MongoDB when possible (integration tests)
- Alegra integration: Use real API calls or comprehensive mock data (see `mock_data.py`)

## Fixtures and Factories

**Test Data:**
```python
# From mock_data.py — comprehensive mock objects
MOCK_ACCOUNTS = [
    {"id": "...", "name": "...", "type": "..."}, ...
]
MOCK_CONTACTS = [...]
MOCK_INVOICES = [...]
MOCK_BILLS = [...]
# Used throughout tests as baseline data

# From test_roddos_backend.py — fixture pattern
@pytest.fixture
def admin_headers():
    # Login as admin, return authorization headers
    response = client.post("/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "roddos_contable_2024"
    })
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def contador_headers():
    # Login as contador, return headers
    ...
```

**Location:**
- `backend/mock_data.py`: Comprehensive mock objects for Alegra entities
- `backend/tests/`: Inline fixtures with `@pytest.fixture` decorator
- Test functions: Fixture parameters auto-injected by pytest

## Coverage

**Requirements:**
- Not enforced — no coverage thresholds detected
- Coverage reports: Not observed in CI/CD pipeline
- Test-driven approach: Selective (smoke tests cover critical paths, not 100% of code)

**View Coverage:**
```bash
# Generate coverage report
pytest --cov=. tests/

# View HTML report
pytest --cov=. --cov-report=html tests/
# Open htmlcov/index.html in browser
```

## Test Types

**Unit Tests:**
- Scope: Individual functions/methods
- Approach: Isolated logic testing with mocks for dependencies
- Example: `test_roddos_backend.py::TestAuth::test_admin_login()`
  - Tests: Password hashing, JWT creation, token validation
  - Mocks: Database calls (using fixture data)

**Integration Tests:**
- Scope: Multiple components working together (e.g., auth → chat → action execution)
- Approach: Real MongoDB, real Alegra API (or comprehensive mocks)
- Example: `test_build21_integration.py`
  - Tests: Scheduler jobs registration, pending actions TTL, action availability
  - Setup: Load .env, create async event loop, connect to MongoDB

**E2E / Smoke Tests:**
- Scope: Full user workflows from login through feature execution
- Approach: Real API endpoints, real database, comprehensive assertions
- Examples:
  - `smoke_test_build23.py`: Tests loan book recalculation, payment plans, invoice creation
  - `run_smoke_test.py`: Test runner orchestrating multiple smoke test scenarios
- Pattern:
  ```python
  class SmokeTestBuild23:
      def test_loanbook_create_and_recalculate(self):
          # 1. Login
          # 2. Create loan book
          # 3. Recalculate payment plan
          # 4. Verify results
          pass
  ```

## Common Patterns

**Async Testing:**
```python
# Pattern from test_build21_integration.py
async def check():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    # async operations
    return result

indexes = asyncio.get_event_loop().run_until_complete(check())
assert condition, "error message"
```

**HTTP Testing:**
```python
# Pattern from test_roddos_backend.py (using FastAPI test client)
from fastapi.testclient import TestClient

client = TestClient(app)

# GET request
response = client.get("/api/endpoint", headers=admin_headers)
assert response.status_code == 200
data = response.json()
assert data["key"] == "expected_value"

# POST request with body
response = client.post("/api/endpoint",
    json={"field": "value"},
    headers=admin_headers
)
assert response.status_code == 201
```

**Source Inspection Testing:**
```python
# Pattern from test_build21_integration.py
# Validates code structure without runtime execution
import inspect
source = inspect.getsource(ai_chat.execute_chat_action)
assert "action_name" in source, "Action not found in source code"
```

**Error Testing:**
```python
# Pattern — assertion on expected errors
with pytest.raises(ValueError) as exc_info:
    function_that_should_raise()
assert "error message" in str(exc_info.value)

# Pattern — try/catch for non-pytest code
try:
    result = operation()
    assert result == expected
except Exception as e:
    pytest.fail(f"Unexpected exception: {e}")
```

## Dependencies and Configuration

**Test Dependencies:**
- `pytest`: Test runner
- `unittest.mock`: Standard library mocking
- `motor`: Async MongoDB driver for integration tests
- `httpx`: HTTP client for API mocking
- `python-dotenv`: Load .env for test configuration

**Configuration Files:**
- `.env` in `backend/`: Test environment variables (MONGO_URL, DB_NAME, etc.)
- `pytest.ini` or `pyproject.toml`: Not explicitly configured, using defaults
- No `conftest.py` observed — fixtures defined inline in test files

## Test Execution

**CI/CD Integration:**
- GitHub Actions workflow (`.github/workflows/` present but not examined in detail)
- Smoke tests run as post-deployment validation
- Build-specific tests (e.g., `test_build23_*.py`) run as regression suite

**Development Workflow:**
- Local testing: `pytest tests/` before commit
- Pre-commit: None detected
- Post-merge: Smoke tests run automatically

---

*Testing analysis: 2026-03-24*
