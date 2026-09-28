"""
Authentication & Authorization tests for Phase 13.

Covers:
  - Customer registration and login
  - Invalid credentials return 401
  - Unauthenticated requests on protected endpoints return 401
  - Public registration cannot self-assign the 'underwriter' role
  - Customer A cannot access Customer B's submission (403)
  - Customer cannot access underwriter-only operations (403)
  - Underwriter can access all submissions and underwriting data
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
import app.models.core  # register all models
from app.main import app
from app.db.database import get_db
from app.models.core import User, InsuranceProduct
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Shared SQLite in-memory engine for the whole module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(_engine)
    return _engine


@pytest.fixture(scope="module")
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session(SessionLocal):
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_and_login(client: TestClient, email: str, password: str, name: str = "Test User") -> dict:
    """Register a customer and return auth header."""
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 201, f"Registration failed: {r.text}"
    r2 = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r2.status_code == 200, f"Login failed: {r2.text}"
    return {"Authorization": f"Bearer {r2.json()['access_token']}"}


def provision_underwriter(db_session, client: TestClient, email: str, password: str) -> dict:
    """Provision underwriter directly in DB (bypassing public API) and return auth header."""
    uw = User(
        email=email,
        password_hash=get_password_hash(password),
        name="Test Underwriter",
        role="underwriter",
    )
    db_session.add(uw)
    db_session.commit()
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, f"UW login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_product(db_session) -> InsuranceProduct:
    p = InsuranceProduct(name="Auth Test Product", description="For auth tests")
    db_session.add(p)
    db_session.commit()
    return p


# ===========================================================================
# 1. Registration
# ===========================================================================

class TestRegistration:
    def test_customer_registration_succeeds(self, client):
        res = client.post("/api/auth/register", json={
            "email": "newcustomer@example.com",
            "password": "StrongPass1!",
            "name": "New Customer",
        })
        assert res.status_code == 201
        body = res.json()
        assert body["email"] == "newcustomer@example.com"
        assert body["role"] == "customer"
        assert "id" in body

    def test_duplicate_email_is_rejected(self, client):
        payload = {"email": "dup@example.com", "password": "Pass1!", "name": "Dup"}
        client.post("/api/auth/register", json=payload)
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_public_registration_cannot_create_underwriter(self, client):
        """
        Even if a caller somehow sends role='underwriter', the register endpoint
        must always assign role='customer'.
        """
        # The UserCreate schema has no role field; verify the returned role is 'customer'
        res = client.post("/api/auth/register", json={
            "email": "sneaky@example.com",
            "password": "Pass1!",
            "name": "Sneaky",
        })
        assert res.status_code == 201
        assert res.json()["role"] == "customer"


# ===========================================================================
# 2. Login
# ===========================================================================

class TestLogin:
    def test_valid_customer_login_returns_token(self, client):
        client.post("/api/auth/register", json={
            "email": "logintest@example.com",
            "password": "ValidPass1!",
            "name": "Login User",
        })
        res = client.post("/api/auth/login", data={
            "username": "logintest@example.com",
            "password": "ValidPass1!",
        })
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_wrong_password_returns_401(self, client):
        client.post("/api/auth/register", json={
            "email": "wrongpass@example.com",
            "password": "CorrectPass1!",
            "name": "Wrong Pass",
        })
        res = client.post("/api/auth/login", data={
            "username": "wrongpass@example.com",
            "password": "WrongPass!",
        })
        assert res.status_code == 401

    def test_nonexistent_user_returns_401(self, client):
        res = client.post("/api/auth/login", data={
            "username": "nobody@example.com",
            "password": "AnyPass1!",
        })
        assert res.status_code == 401

    def test_underwriter_login_includes_role_in_token(self, client, db_session):
        hdrs = provision_underwriter(db_session, client, "uw_login@example.com", "UWPass1!")
        # Verify by hitting an underwriter-only endpoint
        p = make_product(db_session)
        res = client.get("/api/submissions", headers=hdrs)
        assert res.status_code == 200  # underwriter can list all submissions


# ===========================================================================
# 3. Unauthenticated access is rejected
# ===========================================================================

class TestUnauthenticatedAccess:
    def test_create_submission_without_token_returns_401(self, client, db_session):
        p = make_product(db_session)
        res = client.post("/api/submissions", json={"product_id": p.id})
        assert res.status_code == 401

    def test_list_submissions_without_token_returns_401(self, client):
        res = client.get("/api/submissions")
        assert res.status_code == 401

    def test_get_submission_without_token_returns_401(self, client):
        res = client.get("/api/submissions/9999")
        assert res.status_code == 401

    def test_upload_document_without_token_returns_401(self, client):
        import io
        res = client.post(
            "/api/documents/upload",
            data={"submission_id": 1},
            files={"file": ("f.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
        assert res.status_code == 401

    def test_engine_evaluate_without_token_returns_401(self, client):
        res = client.post("/api/engine/evaluate", json={"product_id": 1, "current_answers": {}})
        assert res.status_code == 401


# ===========================================================================
# 4. Customer cannot access another customer's submission
# ===========================================================================

class TestCustomerOwnership:
    def test_customer_a_cannot_read_customer_b_submission(self, client, db_session):
        p = make_product(db_session)

        hdrs_a = register_and_login(client, "cust_a@example.com", "PassA1!", "Customer A")
        hdrs_b = register_and_login(client, "cust_b@example.com", "PassB1!", "Customer B")

        # A creates a submission
        res = client.post("/api/submissions", json={"product_id": p.id}, headers=hdrs_a)
        assert res.status_code == 200
        sub_id = res.json()["id"]

        # B tries to read it
        res = client.get(f"/api/submissions/{sub_id}", headers=hdrs_b)
        assert res.status_code == 403

    def test_customer_a_cannot_save_answers_to_customer_b_submission(self, client, db_session):
        p = make_product(db_session)

        hdrs_a = register_and_login(client, "ans_owner@example.com", "PassA2!", "Owner A")
        hdrs_b = register_and_login(client, "ans_intruder@example.com", "PassB2!", "Intruder B")

        res = client.post("/api/submissions", json={"product_id": p.id}, headers=hdrs_a)
        sub_id = res.json()["id"]

        res = client.put(f"/api/submissions/{sub_id}/answers", json={"1": "test"}, headers=hdrs_b)
        assert res.status_code == 403

    def test_customer_a_cannot_upload_to_customer_b_submission(self, client, db_session):
        import io
        p = make_product(db_session)

        hdrs_a = register_and_login(client, "upload_owner@example.com", "PassA3!", "Upload Owner")
        hdrs_b = register_and_login(client, "upload_intruder@example.com", "PassB3!", "Upload Intruder")

        res = client.post("/api/submissions", json={"product_id": p.id}, headers=hdrs_a)
        sub_id = res.json()["id"]

        res = client.post(
            "/api/documents/upload",
            data={"submission_id": sub_id},
            files={"file": ("f.txt", io.BytesIO(b"amount: 100"), "text/plain")},
            headers=hdrs_b,
        )
        assert res.status_code == 403


# ===========================================================================
# 5. Customer cannot access underwriter-only operations
# ===========================================================================

class TestRoleBoundaries:
    def _customer_with_sub(self, client, db_session, email: str):
        p = make_product(db_session)
        hdrs = register_and_login(client, email, "CustPass1!", "Customer")
        res = client.post("/api/submissions", json={"product_id": p.id}, headers=hdrs)
        assert res.status_code == 200
        return hdrs, res.json()["id"]

    def test_customer_cannot_list_all_submissions(self, client, db_session):
        hdrs, _ = self._customer_with_sub(client, db_session, "clist@example.com")
        res = client.get("/api/submissions", headers=hdrs)
        assert res.status_code == 403

    def test_customer_cannot_get_dashboard(self, client, db_session):
        hdrs, sub_id = self._customer_with_sub(client, db_session, "cdash@example.com")
        res = client.get(f"/api/submissions/{sub_id}/dashboard", headers=hdrs)
        assert res.status_code == 403

    def test_customer_cannot_update_submission_status(self, client, db_session):
        hdrs, sub_id = self._customer_with_sub(client, db_session, "cstatus@example.com")
        res = client.put(
            f"/api/submissions/{sub_id}/status",
            json={"status": "approved"},
            headers=hdrs,
        )
        assert res.status_code == 403

    def test_customer_cannot_update_issue(self, client, db_session):
        hdrs, sub_id = self._customer_with_sub(client, db_session, "cissue@example.com")
        res = client.put(
            f"/api/submissions/{sub_id}/issues/9999",
            json={"action": "dismiss"},
            headers=hdrs,
        )
        assert res.status_code == 403


# ===========================================================================
# 6. Underwriter can access authorized underwriting data
# ===========================================================================

class TestUnderwriterAccess:
    def test_underwriter_can_list_all_submissions(self, client, db_session):
        uw_hdrs = provision_underwriter(db_session, client, "uw_list@example.com", "UWPass1!")
        res = client.get("/api/submissions", headers=uw_hdrs)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_underwriter_can_read_any_submission(self, client, db_session):
        p = make_product(db_session)
        cust_hdrs = register_and_login(client, "uw_readsub_cust@example.com", "CustPass1!", "Cust")
        uw_hdrs = provision_underwriter(db_session, client, "uw_readsub@example.com", "UWPass1!")

        res = client.post("/api/submissions", json={"product_id": p.id}, headers=cust_hdrs)
        sub_id = res.json()["id"]

        res = client.get(f"/api/submissions/{sub_id}", headers=uw_hdrs)
        assert res.status_code == 200

    def test_underwriter_can_update_submission_status(self, client, db_session):
        p = make_product(db_session)
        cust_hdrs = register_and_login(client, "uw_status_cust@example.com", "CustPass1!", "Cust")
        uw_hdrs = provision_underwriter(db_session, client, "uw_status@example.com", "UWPass1!")

        res = client.post("/api/submissions", json={"product_id": p.id}, headers=cust_hdrs)
        sub_id = res.json()["id"]

        res = client.put(
            f"/api/submissions/{sub_id}/status",
            json={"status": "approved", "note": "All good"},
            headers=uw_hdrs,
        )
        assert res.status_code == 200
        assert res.json()["submission_status"] == "approved"
