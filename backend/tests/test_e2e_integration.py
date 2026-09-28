"""
End-to-end integration test: full submission lifecycle authenticated as a customer.
Underwriter-only actions (dashboard, status update) are performed by a separately
provisioned underwriter user (inserted directly into DB to avoid public API).
"""
import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
import app.models.core  # register all models
from app.main import app
from app.db.database import get_db
from app.models.core import User, InsuranceProduct, Question, Requirement
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
def client(db_session, engine):
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
# Seed base catalogue data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def setup_base_data(db_session):
    p = InsuranceProduct(name="E2E Product", description="Test flow")
    db_session.add(p)
    db_session.commit()

    # IDs must match normalization.py QUESTION_KEY_MAP: 2=annual_revenue, 3=hazardous_materials, 5=risk_level
    q_dummy1 = Question(id=1, product_id=p.id, text="Entity?", field_type="text", is_required=False)
    q1 = Question(id=2, product_id=p.id, text="Revenue?", field_type="number", is_required=True)
    q2 = Question(id=3, product_id=p.id, text="Hazmat?", field_type="yesno", is_required=True)
    q_dummy4 = Question(id=4, product_id=p.id, text="Property value?", field_type="number", is_required=False)
    q3 = Question(id=5, product_id=p.id, text="Risk level?", field_type="text", is_required=False)
    db_session.add_all([q_dummy1, q1, q2, q_dummy4, q3])
    db_session.commit()

    req1 = Requirement(
        product_id=p.id,
        name="Financial Statement",
        description="Verify revenue and hazmat",
    )
    db_session.add(req1)
    db_session.commit()

    return p, q1, q2, q3, req1


# ---------------------------------------------------------------------------
# Helper: register a customer and return an auth header dict
# ---------------------------------------------------------------------------

def _customer_token(client: TestClient, email: str, password: str, name: str) -> dict:
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    res = client.post("/api/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helper: provision an underwriter directly (public API cannot create underwriters)
# ---------------------------------------------------------------------------

def _underwriter_token(client: TestClient, db_session, email: str, password: str) -> dict:
    uw = User(
        email=email,
        password_hash=get_password_hash(password),
        name="Test Underwriter",
        role="underwriter",
    )
    db_session.add(uw)
    db_session.commit()

    res = client.post("/api/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, f"UW login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Full E2E flow
# ---------------------------------------------------------------------------

def test_full_e2e_integration_flow(client, setup_base_data, db_session):
    p, q_rev, q_haz, q_risk, req1 = setup_base_data

    cust_hdrs = _customer_token(client, "e2e_customer@test.com", "Password123!", "E2E Customer")
    uw_hdrs = _underwriter_token(client, db_session, "e2e_uw@test.com", "UWPass456!")

    # 1. Create Submission (customer)
    res = client.post("/api/submissions", json={"product_id": p.id}, headers=cust_hdrs)
    assert res.status_code == 200, res.text
    sub_id = res.json()["id"]

    # 2. Save initial answers (customer)
    ans_payload = {
        str(q_rev.id): "15000000",   # 1.5 Cr
        str(q_haz.id): "no",
        str(q_risk.id): "moderate",
    }
    res = client.put(f"/api/submissions/{sub_id}/answers", json=ans_payload, headers=cust_hdrs)
    assert res.status_code == 200
    assert res.json()["saved_count"] == 3

    # Idempotency + back-navigation: customer edits an answer
    ans_payload[str(q_haz.id)] = "yes"
    res = client.put(f"/api/submissions/{sub_id}/answers", json=ans_payload, headers=cust_hdrs)
    assert res.status_code == 200
    assert res.json()["saved_count"] == 3

    # 3. Upload document (customer)
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "FINANCIAL STATEMENT\nAnnual Revenue: 1.8 crore\nHazardous materials: yes\nRisk classification: moderate",
    )
    pdf_bytes = doc.write()
    doc.close()

    res = client.post(
        "/api/documents/upload",
        data={"submission_id": sub_id, "requirement_id": req1.id},
        files={"file": ("test_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=cust_hdrs,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "processed"

    # 4. Generate issues (customer, owns submission)
    res = client.post(f"/api/submissions/{sub_id}/issues/generate", headers=cust_hdrs)
    assert res.status_code == 200

    # 5. Dashboard summary (underwriter only)
    res = client.get(f"/api/submissions/{sub_id}/dashboard", headers=uw_hdrs)
    assert res.status_code == 200
    data = res.json()

    assert len(data["answers"]) == 3
    assert len(data["documents"]) == 1
    extracted_keys = {f["key"] for f in data["documents"][0]["extracted_fields"]}
    assert "annual_revenue" in extracted_keys
    assert len(data["consistency_checks"]) > 0
    assert data["severity_counts"]["HIGH"] == 1
    assert len(data["issues"]) == 1
    issue = data["issues"][0]
    assert issue["details"]["triggering_field"] == "annual_revenue"
    assert issue["details"]["comparison_result"] == "CONFLICT"
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["fulfilled"] is True

    # 6. Underwriter action: update status
    res = client.put(
        f"/api/submissions/{sub_id}/status",
        json={"status": "info_requested", "note": "Please explain revenue discrepancy"},
        headers=uw_hdrs,
    )
    assert res.status_code == 200
    assert res.json()["submission_status"] == "info_requested"

    # 7. Verify audit trail on dashboard
    res2 = client.get(f"/api/submissions/{sub_id}/dashboard", headers=uw_hdrs)
    assert res2.json()["submission"]["status"] == "info_requested"
    assert len(res2.json()["audit_trail"]) >= 1
