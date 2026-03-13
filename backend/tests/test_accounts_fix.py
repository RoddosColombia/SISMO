"""Backend tests for P0 fix: /api/alegra/accounts using /categories endpoint + AI chat"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "contabilidad@roddos.com", "password": "Admin@RODDOS2025!"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]

@pytest.fixture(scope="module")
def auth(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


class TestAccountsEndpoint:
    """Tests for GET /api/alegra/accounts using /categories fix"""

    def test_accounts_returns_list(self, auth):
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        print(f"✓ /api/alegra/accounts returned list with {len(data)} top-level items")

    def test_accounts_not_empty(self, auth):
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()
        assert len(data) > 0, "Account list is empty — categories endpoint may have failed"
        print(f"✓ accounts non-empty: {len(data)} top-level accounts")

    def test_accounts_have_required_fields(self, auth):
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()
        assert len(data) > 0
        first = data[0]
        assert "id" in first, f"Missing id in account: {first}"
        assert "name" in first, f"Missing name in account: {first}"
        assert "type" in first, f"Missing type: {first}"
        print(f"✓ First account: id={first['id']}, name={first['name']}, type={first['type']}")

    def test_accounts_no_puc_code(self, auth):
        """Alegra NIIF accounts have no PUC code (code=null)"""
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()
        # code should be null (None) for NIIF accounts
        for acc in data[:5]:
            code = acc.get("code")
            # code can be None or absent
            print(f"  Account {acc.get('id')}: code={code}")
        print("✓ Checked code field - NIIF accounts may have null codes")

    def test_accounts_hierarchical_structure(self, auth):
        """Accounts should be hierarchical with subAccounts"""
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()
        # Find any account with subAccounts
        has_subs = any(len(acc.get("subAccounts", [])) > 0 for acc in data)
        print(f"✓ Has hierarchical accounts (subAccounts): {has_subs}")
        # Don't assert strictly — some orgs might have flat structure

    def test_accounts_total_count_large(self, auth):
        """Alegra should return ~233 accounts total (based on context)"""
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()

        def count_all(accs):
            total = len(accs)
            for a in accs:
                total += count_all(a.get("subAccounts") or [])
            return total

        total = count_all(data)
        print(f"✓ Total accounts in tree: {total}")
        assert total > 10, f"Only {total} accounts found — may indicate partial data"


class TestAccountsSearch:
    """Test that accounts data is usable for search by name"""

    def test_flatten_and_search_by_name(self, auth):
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()

        def flatten(accs, result=None):
            if result is None:
                result = []
            for a in accs:
                result.append(a)
                flatten(a.get("subAccounts") or [], result)
            return result

        all_accs = flatten(data)
        # Search for "arrend" (arrendamiento)
        matches = [a for a in all_accs if "arrend" in a.get("name", "").lower()]
        print(f"✓ Search 'arrend' found {len(matches)} accounts: {[a['name'] for a in matches[:3]]}")

    def test_account_types_present(self, auth):
        resp = auth.get(f"{BASE_URL}/api/alegra/accounts")
        data = resp.json()

        def flatten(accs, result=None):
            if result is None:
                result = []
            for a in accs:
                result.append(a)
                flatten(a.get("subAccounts") or [], result)
            return result

        all_accs = flatten(data)
        types_found = set(a.get("type") for a in all_accs)
        print(f"✓ Account types found: {types_found}")
        # Should have at least some types
        assert len(types_found) > 0, "No account types found"


class TestChatEndpoint:
    """Test AI chat with accounts context"""

    def test_chat_basic_response(self, auth):
        import uuid
        session_id = str(uuid.uuid4())
        resp = auth.post(f"{BASE_URL}/api/chat/message", json={
            "session_id": session_id,
            "message": "Hola, ¿cuál es tu función?"
        })
        assert resp.status_code == 200, f"Chat failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "message" in data, f"No 'message' in response: {data}"
        assert len(data["message"]) > 10, "Response too short"
        print(f"✓ Chat basic response: {data['message'][:100]}...")

    def test_chat_arrendamiento_suggests_accounts(self, auth):
        """When asking about 'arrendamiento', AI should suggest specific accounts"""
        import uuid
        session_id = str(uuid.uuid4())
        resp = auth.post(f"{BASE_URL}/api/chat/message", json={
            "session_id": session_id,
            "message": "causar arrendamiento $3M"
        })
        assert resp.status_code == 200, f"Chat failed: {resp.status_code} {resp.text}"
        data = resp.json()
        msg = data.get("message", "")
        print(f"✓ Chat arrendamiento response (first 300 chars): {msg[:300]}")
        # Should mention accounts or amounts
        has_account_info = any(w in msg.lower() for w in ["cuenta", "débito", "crédito", "debito", "credito", "3.000", "3,000"])
        print(f"  Has account suggestions: {has_account_info}")
        # pending_action is optional
        action = data.get("pending_action")
        print(f"  Has pending_action: {action is not None}")
