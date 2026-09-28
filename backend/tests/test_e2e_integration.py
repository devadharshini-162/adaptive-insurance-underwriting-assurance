import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
import app.models.core  # register all models
from app.main import app
from app.db.database import get_db
from app.models.core import User, InsuranceProduct, Question, Requirement
from sqlalchemy.pool import StaticPool

@pytest.fixture(scope="module")
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
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

@pytest.fixture(scope="function")
def setup_base_data(db_session):
    u = User(email="e2e@test.com", name="E2E Agent", role="agent")
    db_session.add(u)
    db_session.commit()

    p = InsuranceProduct(name="E2E Product", description="Test flow")
    db_session.add(p)
    db_session.commit()

    # Create questions for critical fields mapping to the mock testing pdf
    # We must match IDs from normalization.py QUESTION_KEY_MAP:
    # 2: annual_revenue, 3: hazardous_materials, 5: risk_level
    q_dummy1 = Question(id=1, product_id=p.id, text="Entity?", field_type="text", is_required=False)
    q1 = Question(id=2, product_id=p.id, text="Revenue?", field_type="number", is_required=True)
    q2 = Question(id=3, product_id=p.id, text="Hazmat?", field_type="yesno", is_required=True)
    q_dummy4 = Question(id=4, product_id=p.id, text="Property value?", field_type="number", is_required=False)
    q3 = Question(id=5, product_id=p.id, text="Risk level?", field_type="text", is_required=False)
    db_session.add_all([q_dummy1, q1, q2, q_dummy4, q3])
    db_session.commit()

    # Give a requirement so we can test document upload
    req1 = Requirement(
        product_id=p.id,
        name="Financial Statement",
        description="Verify revenue and hazmat",
        # Unconditional
    )
    db_session.add(req1)
    db_session.commit()

    return p, q1, q2, q3, req1

def test_full_e2e_integration_flow(client, setup_base_data):
    p, q_rev, q_haz, q_risk, req1 = setup_base_data

    # 1. Create Submission
    res = client.post("/api/submissions", json={"product_id": p.id})
    assert res.status_code == 200
    sub_id = res.json()["id"]

    # 2. Save Initial Answers
    ans_payload = {
        str(q_rev.id): "15000000",   # 1.5 Cr
        str(q_haz.id): "no",
        str(q_risk.id): "moderate"
    }
    res = client.put(f"/api/submissions/{sub_id}/answers", json=ans_payload)
    assert res.status_code == 200
    assert res.json()["saved_count"] == 3

    # Wait, testing idempotency + back navigation: User edits answer
    ans_payload[str(q_haz.id)] = "yes"
    res = client.put(f"/api/submissions/{sub_id}/answers", json=ans_payload)
    assert res.status_code == 200
    assert res.json()["saved_count"] == 3

    # 3. Upload Document
    import fitz 
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "FINANCIAL STATEMENT\nAnnual Revenue: 1.8 crore\nHazardous materials: yes\nRisk classification: moderate"
    )
    pdf_bytes = doc.write()
    doc.close()

    res = client.post(
        "/api/documents/upload",
        data={"submission_id": sub_id, "requirement_id": req1.id},
        files={"file": ("test_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "processed"
    
    # 4. Generate Issues
    res = client.post(f"/api/submissions/{sub_id}/issues/generate")
    assert res.status_code == 200

    # 5. Dashboard Summary
    res = client.get(f"/api/submissions/{sub_id}/dashboard")
    assert res.status_code == 200
    data = res.json()
    
    # Assert Answers persisted
    assert len(data["answers"]) == 3
    # Assert Document extracted
    assert len(data["documents"]) == 1
    doc_data = data["documents"][0]
    extracted_keys = {f["key"] for f in doc_data["extracted_fields"]}
    assert "annual_revenue" in extracted_keys

    # Assert Consistencies
    assert len(data["consistency_checks"]) > 0

    # Assert Issues generated appropriately
    # We answered 15M for revenue, but doc said 1.8 crore (18M) -> CONFLICT -> HIGH 
    # Hazmat: yes vs yes -> CONSISTENT
    # Risk: moderate vs moderate -> CONSISTENT
    assert data["severity_counts"]["HIGH"] == 1
    issues = data["issues"]
    assert len(issues) == 1
    issue = issues[0]
    assert issue["details"]["triggering_field"] == "annual_revenue"
    assert issue["details"]["comparison_result"] == "CONFLICT"
    
    # Assert requirements fulfilled
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["fulfilled"] is True

    # 6. Underwriter Action
    res = client.put(f"/api/submissions/{sub_id}/status", json={
        "status": "info_requested",
        "note": "Please explain revenue discrepancy"
    })
    assert res.status_code == 200
    assert res.json()["submission_status"] == "info_requested"

    # Refresh dashboard to verify audit trail
    res2 = client.get(f"/api/submissions/{sub_id}/dashboard")
    assert res2.json()["submission"]["status"] == "info_requested"
    assert len(res2.json()["audit_trail"]) >= 1
