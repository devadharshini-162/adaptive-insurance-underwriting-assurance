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
from app.models.core import User, InsuranceCompany, InsuranceProduct, AuditRecord, Submission, Question, Requirement, Document, ExtractedField, UnderwritingIssue, ConsistencyCheck
from app.db.seed import DEMO_COMPANIES, DEMO_CUSTOMERS, DEMO_PASSWORD, DEMO_SUBMISSIONS, DEMO_UNDERWRITERS, seed
from app.db.product_catalog import CATALOG
from app.services.consistency_service import run_consistency_checks
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

    def test_public_registration_can_create_selected_prototype_role(self, client):
        res = client.post("/api/auth/register", json={
            "email": "sneaky@example.com",
            "password": "Pass1!",
            "name": "Underwriter Account",
            "role": "underwriter",
            "organization": "Prototype Insurance",
            "job_title": "Underwriter",
        })
        assert res.status_code == 201
        assert res.json()["role"] == "underwriter"
        assert res.json()["organization"] == "Prototype Insurance"

    def test_authenticated_user_can_update_profile_and_password(self, client):
        headers = register_and_login(client, "profile_edit@example.com", "OriginalPass1!", "Original Name")
        updated = client.put("/api/auth/me", json={"name": "Updated Name", "phone": "+91 98765 43210", "organization": "Harbor Trading", "job_title": "Risk Manager"}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated Name"
        changed = client.put("/api/auth/me", json={"current_password": "OriginalPass1!", "new_password": "UpdatedPass1!"}, headers=headers)
        assert changed.status_code == 200
        assert client.post("/api/auth/login", data={"username": "profile_edit@example.com", "password": "UpdatedPass1!"}).status_code == 200


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
    def test_customer_can_list_only_own_submissions(self, client, db_session):
        product = make_product(db_session)
        headers_a = register_and_login(client, "my_apps_a@example.com", "PassA0!", "Customer A")
        headers_b = register_and_login(client, "my_apps_b@example.com", "PassB0!", "Customer B")

        own = client.post("/api/submissions", json={"product_id": product.id}, headers=headers_a)
        other = client.post("/api/submissions", json={"product_id": product.id}, headers=headers_b)
        assert own.status_code == 200
        assert other.status_code == 200

        response = client.get("/api/submissions/mine", headers=headers_a)
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body] == [own.json()["id"]]
        assert body[0]["product_name"] == "Auth Test Product"
        assert body[0]["applicant_name"] == "Customer A"

    def test_underwriter_cannot_use_customer_submissions_endpoint(self, client, db_session):
        headers = provision_underwriter(db_session, client, "mine_underwriter@example.com", "UWPass0!")
        response = client.get("/api/submissions/mine", headers=headers)
        assert response.status_code == 403

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
        product = make_product(db_session)
        customer_headers = register_and_login(client, "queue_customer@example.com", "CustPass0!", "Queue Customer")
        created = client.post("/api/submissions", json={"product_id": product.id}, headers=customer_headers)
        assert created.status_code == 200
        submitted = client.post(f"/api/submissions/{created.json()['id']}/issues/generate", headers=customer_headers)
        assert submitted.status_code == 200
        uw_hdrs = provision_underwriter(db_session, client, "uw_list@example.com", "UWPass1!")
        res = client.get("/api/submissions", headers=uw_hdrs)
        assert res.status_code == 200
        assert isinstance(res.json(), list)
        queue_item = next(item for item in res.json() if item["applicant_name"] == "Queue Customer")
        assert queue_item["product_name"] == "Auth Test Product"

    def test_underwriter_can_read_any_submission(self, client, db_session):
        p = make_product(db_session)
        cust_hdrs = register_and_login(client, "uw_readsub_cust@example.com", "CustPass1!", "Cust")
        uw_hdrs = provision_underwriter(db_session, client, "uw_readsub@example.com", "UWPass1!")

        res = client.post("/api/submissions", json={"product_id": p.id}, headers=cust_hdrs)
        sub_id = res.json()["id"]
        assert client.post(f"/api/submissions/{sub_id}/issues/generate", headers=cust_hdrs).status_code == 200

        res = client.get(f"/api/submissions/{sub_id}", headers=uw_hdrs)
        assert res.status_code == 200

    def test_underwriter_can_update_submission_status(self, client, db_session):
        p = make_product(db_session)
        cust_hdrs = register_and_login(client, "uw_status_cust@example.com", "CustPass1!", "Cust")
        uw_hdrs = provision_underwriter(db_session, client, "uw_status@example.com", "UWPass1!")

        res = client.post("/api/submissions", json={"product_id": p.id}, headers=cust_hdrs)
        sub_id = res.json()["id"]
        submitted = client.post(f"/api/submissions/{sub_id}/issues/generate", headers=cust_hdrs)
        assert submitted.status_code == 200

        res = client.put(
            f"/api/submissions/{sub_id}/status",
            json={"status": "approved", "note": "All good"},
            headers=uw_hdrs,
        )
        assert res.status_code == 200
        assert res.json()["submission_status"] == "approved"


# ===========================================================================
# 7. Submission status lifecycle
# ===========================================================================

class TestSubmissionStatusLifecycle:
    def _new_application(self, client, db_session, email="lifecycle_customer@example.com"):
        product = make_product(db_session)
        customer_headers = register_and_login(client, email, "CustPass1!", "Lifecycle Customer")
        underwriter_headers = provision_underwriter(db_session, client, f"uw_{email}", "UWPass1!")
        created = client.post("/api/submissions", json={"product_id": product.id}, headers=customer_headers)
        assert created.status_code == 200
        return customer_headers, underwriter_headers, created.json()["id"]

    def _submit_for_review(self, client, submission_id, customer_headers):
        response = client.post(f"/api/submissions/{submission_id}/issues/generate", headers=customer_headers)
        assert response.status_code == 200, response.text

    def test_lifecycle_enforces_all_transitions_and_audits(self, client, db_session):
        customer_headers, underwriter_headers, submission_id = self._new_application(client, db_session)

        # draft → under_review → info_requested → under_review → approved
        self._submit_for_review(client, submission_id, customer_headers)
        assert db_session.get(Submission, submission_id).status == "under_review"
        requested = client.put(f"/api/submissions/{submission_id}/status", json={"status": "info_requested"}, headers=underwriter_headers)
        assert requested.status_code == 200
        self._submit_for_review(client, submission_id, customer_headers)
        approved = client.put(f"/api/submissions/{submission_id}/status", json={"status": "approved", "note": "Lifecycle test"}, headers=underwriter_headers)
        assert approved.status_code == 200
        audit = db_session.query(AuditRecord).filter(AuditRecord.submission_id == submission_id).order_by(AuditRecord.id.desc()).first()
        assert audit.context_data == {"from_status": "under_review", "to_status": "approved", "actor_role": "underwriter", "note": "Lifecycle test"}

        # A separate reviewed application covers the declined terminal branch.
        created = client.post("/api/submissions", json={"product_id": 1}, headers=customer_headers)
        assert created.status_code == 200
        declined_id = created.json()["id"]
        self._submit_for_review(client, declined_id, customer_headers)
        assert client.put(f"/api/submissions/{declined_id}/status", json={"status": "declined"}, headers=underwriter_headers).status_code == 200

        # Direct underwriter approval from draft, reopening terminal states, and customer edits/resubmissions of terminal states are rejected.
        created = client.post("/api/submissions", json={"product_id": 1}, headers=customer_headers)
        invalid_id = created.json()["id"]
        skipped = client.put(f"/api/submissions/{invalid_id}/status", json={"status": "approved"}, headers=underwriter_headers)
        assert skipped.status_code == 404
        assert "Draft" in skipped.json()["detail"]
        self._submit_for_review(client, invalid_id, customer_headers)
        assert client.put(f"/api/submissions/{invalid_id}/status", json={"status": "declined"}, headers=underwriter_headers).status_code == 200
        assert client.put(f"/api/submissions/{invalid_id}/status", json={"status": "under_review"}, headers=underwriter_headers).status_code == 409
        assert client.put(f"/api/submissions/{invalid_id}/answers", json={}, headers=customer_headers).status_code == 409
        assert client.post(f"/api/submissions/{invalid_id}/issues/generate", headers=customer_headers).status_code == 409

    def test_customer_can_delete_only_own_draft_and_underwriter_queue_excludes_drafts(self, client, db_session):
        customer_headers, underwriter_headers, draft_id = self._new_application(client, db_session, "delete_draft@example.com")
        saved = client.put(f"/api/submissions/{draft_id}/application", json={"company_name": "Saved draft business", "city": "Chennai"}, headers=customer_headers)
        assert saved.status_code == 200
        assert client.get(f"/api/submissions/{draft_id}/application", headers=customer_headers).json()["profile"]["company_name"] == "Saved draft business"
        other_headers = register_and_login(client, "delete_other@example.com", "CustPass1!")
        assert client.delete(f"/api/submissions/{draft_id}", headers=other_headers).status_code == 403
        queue = client.get("/api/submissions", headers=underwriter_headers)
        assert draft_id not in {item["id"] for item in queue.json()}
        assert client.get(f"/api/submissions/{draft_id}", headers=underwriter_headers).status_code == 404
        assert client.get(f"/api/submissions/{draft_id}/application", headers=underwriter_headers).status_code == 404
        assert client.delete(f"/api/submissions/{draft_id}", headers=customer_headers).status_code == 204
        assert client.get(f"/api/submissions/{draft_id}", headers=customer_headers).status_code == 404

    def test_submitted_application_appears_in_underwriter_queue(self, client, db_session):
        customer_headers, underwriter_headers, submission_id = self._new_application(client, db_session, "queue_submitted@example.com")
        self._submit_for_review(client, submission_id, customer_headers)
        queue = client.get("/api/submissions", headers=underwriter_headers)
        assert submission_id in {item["id"] for item in queue.json()}


class TestApplicationInformation:
    def test_customer_profile_persists_and_remains_owned(self, client, db_session):
        product = make_product(db_session)
        owner = register_and_login(client, "profile_owner@example.com", "CustPass1!", "Profile Owner")
        other = register_and_login(client, "profile_other@example.com", "CustPass2!", "Profile Other")
        submission = client.post("/api/submissions", json={"product_id": product.id}, headers=owner).json()
        payload = {"company_name": "Acme Trading", "industry": "Retail", "annual_revenue": "12000000", "property_address": "1 Market Road", "property_value": "55000000", "employee_count": 24}
        saved = client.put(f"/api/submissions/{submission['id']}/application", json=payload, headers=owner)
        assert saved.status_code == 200
        assert saved.json()["company_name"] == "Acme Trading"
        state = client.get(f"/api/submissions/{submission['id']}/application", headers=owner)
        assert state.status_code == 200
        assert state.json()["profile"]["employee_count"] == 24
        assert client.put(f"/api/submissions/{submission['id']}/application", json=payload, headers=other).status_code == 403

    def test_adaptive_questions_and_requirements_use_persisted_context(self, client, db_session):
        product = make_product(db_session)
        manufacturing = Question(product_id=product.id, text="Manufacturing", field_type="yesno", is_required=True, section="risk")
        db_session.add(manufacturing); db_session.flush()
        conditional = Question(product_id=product.id, text="Fire protection", field_type="text", is_required=True, section="risk", condition_logic={"question_id": manufacturing.id, "operator": "==", "value": "yes"})
        requirement = Requirement(product_id=product.id, name="Financial statement", description="Required for larger businesses", rule_logic={"field": "annual_revenue", "operator": ">", "value": 10000000, "explanation": "Required because annual revenue exceeds the configured threshold."})
        db_session.add_all([conditional, requirement]); db_session.commit()
        owner = register_and_login(client, "adaptive_owner@example.com", "CustPass1!", "Adaptive Owner")
        submission = client.post("/api/submissions", json={"product_id": product.id}, headers=owner).json()
        assert client.put(f"/api/submissions/{submission['id']}/application", json={"annual_revenue": "12000000"}, headers=owner).status_code == 200
        visible = client.post("/api/engine/evaluate", json={"product_id": product.id, "current_answers": {str(manufacturing.id): "yes"}, "context_data": {"annual_revenue": "12000000"}}, headers=owner)
        assert visible.status_code == 200
        assert conditional.id in {question["id"] for question in visible.json()["applicable_questions"]}
        assert visible.json()["requirements"][0]["explanation"] == "Required because annual revenue exceeds the configured threshold."


class TestEvidenceReview:
    def test_document_access_and_underwriter_review_actions_are_authorized(self, client, db_session):
        product = make_product(db_session)
        owner = register_and_login(client, "evidence_owner@example.com", "CustPass1!", "Evidence Owner")
        other = register_and_login(client, "evidence_other@example.com", "CustPass2!", "Evidence Other")
        underwriter = provision_underwriter(db_session, client, "evidence_uw@example.com", "UWPass1!")
        submission_id = client.post("/api/submissions", json={"product_id": product.id}, headers=owner).json()["id"]
        import io
        import fitz
        pdf = fitz.open(); page = pdf.new_page(); page.insert_text((50, 72), "Property Value: 1000000")
        uploaded = client.post("/api/documents/upload", data={"submission_id": submission_id},
                               files={"file": ("Property schedule.pdf", io.BytesIO(pdf.write()), "application/pdf")}, headers=owner)
        pdf.close()
        assert uploaded.status_code == 200
        document = db_session.get(Document, uploaded.json()["document_id"])
        assert client.post("/api/documents/upload", data={"submission_id": submission_id},
                           files={"file": ("unauthorized.pdf", io.BytesIO(b"%PDF-1.4\n"), "application/pdf")}, headers=underwriter).status_code == 403
        listed = client.get(f"/api/documents/submission/{submission_id}", headers=owner)
        assert listed.status_code == 200 and listed.json()[0]["name"] == "Property schedule.pdf"
        assert "file_path" not in listed.json()[0]
        assert client.get(f"/api/documents/{document.id}/fields", headers=other).status_code == 403
        assert client.get(f"/api/documents/{document.id}/content", headers=other).status_code == 403
        replacement = client.post(f"/api/documents/{document.id}/replace", files={"file": ("Updated schedule.pdf", io.BytesIO(b"%PDF-1.4\n"), "application/pdf")}, headers=owner)
        assert replacement.status_code == 200
        db_session.refresh(document)
        assert document.status == "replaced"
        assert client.get(f"/api/submissions/{submission_id}/dashboard", headers=owner).status_code == 403
        # A draft cannot be opened by underwriting. Submit it through the
        # normal customer workflow before exercising the review workspace.
        assert client.post(f"/api/submissions/{submission_id}/issues/generate", headers=owner).status_code == 200
        issue = UnderwritingIssue(submission_id=submission_id, issue_type="conflict", description="Property value mismatch", status="open", details={"reason": "Values differ."})
        db_session.add(issue); db_session.commit()

        review = client.get(f"/api/submissions/{submission_id}/dashboard", headers=underwriter)
        assert review.status_code == 200
        assert review.json()["documents"][0]["extracted_fields"][0]["label"] == "Property value"
        updated = client.put(f"/api/submissions/{submission_id}/issues/{issue.id}", json={"action": "dismiss", "note": "Reviewed supporting schedule."}, headers=underwriter)
        assert updated.status_code == 200 and updated.json()["issue_status"] == "dismissed"
        audit = db_session.query(AuditRecord).filter(AuditRecord.submission_id == submission_id, AuditRecord.action == "issue_dismiss").one()
        assert audit.context_data["note"] == "Reviewed supporting schedule."


class TestTwoWayReviewWorkflow:
    def test_request_upload_resubmit_and_terminal_enforcement(self, client, db_session):
        import io
        product = make_product(db_session)
        customer = register_and_login(client, "loop_customer@example.com", "CustPass1!", "Loop Customer")
        underwriter = provision_underwriter(db_session, client, "loop_uw@example.com", "UWPass1!")
        submission_id = client.post("/api/submissions", json={"product_id": product.id}, headers=customer).json()["id"]
        assert client.post(f"/api/submissions/{submission_id}/issues/generate", headers=customer).status_code == 200
        requested = client.post(f"/api/submissions/{submission_id}/requests", json={"request_type": "document", "document_name": "Updated property schedule", "message": "Please provide the latest property schedule.", "note": "Needed for review."}, headers=underwriter)
        assert requested.status_code == 200
        state = client.get(f"/api/submissions/{submission_id}/application", headers=customer).json()
        assert state["submission"]["status"] == "info_requested"
        request_id = state["requests"][0]["id"]
        uploaded = client.post(f"/api/documents/requested/{submission_id}/{request_id}", files={"file": ("schedule.pdf", io.BytesIO(b"%PDF-1.4\n"), "application/pdf")}, headers=customer)
        assert uploaded.status_code == 200
        assert client.post(f"/api/submissions/{submission_id}/issues/generate", headers=customer).status_code == 200
        assert client.put(f"/api/submissions/{submission_id}/status", json={"status": "approved", "note": "Evidence accepted."}, headers=underwriter).status_code == 200
        assert client.put(f"/api/submissions/{submission_id}/answers", json={}, headers=customer).status_code == 409
        assert client.post(f"/api/submissions/{submission_id}/issues/generate", headers=customer).status_code == 409
        assert client.put(f"/api/submissions/{submission_id}/status", json={"status": "declined"}, headers=underwriter).status_code == 409
        actions = {row.action for row in db_session.query(AuditRecord).filter(AuditRecord.submission_id == submission_id).all()}
        assert {"additional_document_requested", "requested_document_uploaded", "submission_resubmitted"}.issubset(actions)


class TestPrototypeProductCatalogue:
    @pytest.mark.parametrize("catalogue_entry", CATALOG, ids=[entry["name"] for entry in CATALOG])
    def test_each_product_has_product_specific_adaptive_pathway(self, client, db_session, catalogue_entry):
        seed(db_session)
        email_slug = catalogue_entry["name"].lower().replace(" ", "_").replace("/", "_").replace("'", "")
        headers = register_and_login(client, f"catalogue_{email_slug}@example.com", "CustPass1!")
        product = db_session.query(InsuranceProduct).filter_by(name=catalogue_entry["name"]).one()
        baseline = client.post("/api/engine/evaluate", json={"product_id": product.id, "current_answers": {}, "context_data": {}}, headers=headers)
        assert baseline.status_code == 200
        visible = {question["text"]: question for question in baseline.json()["applicable_questions"]}
        first_key, first_text, _, _ = catalogue_entry["questions"][0]
        assert first_text in visible
        # A product's standard requirement is present; another product's
        # questions are naturally excluded by product_id.
        assert baseline.json()["requirements"][0]["name"] == catalogue_entry["requirements"][0][0]
        if catalogue_entry["name"] != "Commercial Property":
            assert "Are hazardous materials present on the premises?" not in visible

        conditional_question = next((item for item in catalogue_entry["questions"] if item[3] and item[3][0]), None)
        if conditional_question:
            trigger_key, trigger_value, _ = conditional_question[3]
            trigger_text = next(text for key, text, _, _ in catalogue_entry["questions"] if key == trigger_key)
            triggered = client.post("/api/engine/evaluate", json={"product_id": product.id, "current_answers": {str(visible[trigger_text]["id"]): "2" if str(trigger_value).startswith(">") else trigger_value}, "context_data": {}}, headers=headers)
            assert triggered.status_code == 200
            assert conditional_question[1] in {question["text"] for question in triggered.json()["applicable_questions"]}

        conditional_requirement = next((item for item in catalogue_entry["requirements"] if item[2]), None)
        if conditional_requirement:
            trigger_key, trigger_value = conditional_requirement[2]
            trigger_text = next(text for key, text, _, _ in catalogue_entry["questions"] if key == trigger_key)
            trigger_id = visible[trigger_text]["id"]
            evaluated = client.post("/api/engine/evaluate", json={"product_id": product.id, "current_answers": {str(trigger_id): trigger_value[1:] if trigger_value.startswith(">") else trigger_value}, "context_data": {}}, headers=headers)
            assert evaluated.status_code == 200
            names = {requirement["name"] for requirement in evaluated.json()["requirements"]}
            # Numeric threshold requirements need an above-threshold answer.
            if trigger_value.startswith(">"):
                evaluated = client.post("/api/engine/evaluate", json={"product_id": product.id, "current_answers": {str(trigger_id): "6000000"}, "context_data": {}}, headers=headers)
                names = {requirement["name"] for requirement in evaluated.json()["requirements"]}
            assert conditional_requirement[0] in names

    def test_consistency_checks_can_be_regenerated_when_issues_reference_old_checks(self, db_session):
        product = make_product(db_session)
        customer = User(email="consistency_regenerate@example.com", password_hash="x", name="Consistency", role="customer")
        db_session.add(customer); db_session.flush()
        submission = Submission(user_id=customer.id, product_id=product.id, status="draft")
        db_session.add(submission); db_session.flush()
        check = ConsistencyCheck(submission_id=submission.id, status="CONFLICT", details={})
        db_session.add(check); db_session.flush()
        db_session.add(UnderwritingIssue(submission_id=submission.id, consistency_check_id=check.id, issue_type="conflict", description="Old issue", status="open", details={}))
        db_session.commit()
        run_consistency_checks(db_session, submission.id)
        assert db_session.query(ConsistencyCheck).filter_by(submission_id=submission.id).count() == 0

    @pytest.mark.parametrize("product_name, expected_question, excluded_question, email", [
        ("Personal Cyber Protection", "Is multi-factor authentication enabled on your main email account?", "Do you use cloud systems for critical business operations?", "personal_cyber_path@example.com"),
        ("Personal Valuables & Marine", "What valuables or personal items need cover?", "What goods are being transported?", "personal_valuables_path@example.com"),
        ("Personal Liability Protection", "Do you own or care for pets?", "Do you manufacture or sell products?", "personal_liability_path@example.com"),
    ])
    def test_personal_products_have_individual_risk_questions(self, client, db_session, product_name, expected_question, excluded_question, email):
        seed(db_session)
        headers = register_and_login(client, email, "CustPass1!")
        product = db_session.query(InsuranceProduct).filter_by(name=product_name).one()
        response = client.post("/api/engine/evaluate", json={"product_id": product.id, "current_answers": {}, "context_data": {}}, headers=headers)
        assert response.status_code == 200
        questions = {question["text"] for question in response.json()["applicable_questions"]}
        assert expected_question in questions
        assert excluded_question not in questions


class TestInsurerAndUnderwriterAssignment:
    def test_customer_can_select_only_compatible_demo_underwriter_and_queue_is_assigned(self, client, db_session):
        seed(db_session)
        customer = register_and_login(client, "assignment_customer@example.com", "CustPass1!", "Assignment Customer")
        products = client.get("/api/products").json()
        motor = next(product for product in products if product["name"] == "Motor Insurance")
        companies = client.get("/api/products/companies", headers=customer)
        assert companies.status_code == 200
        harbor = next(company for company in companies.json() if company["name"] == "Harbor Mutual")
        compatible = client.get(f"/api/products/underwriters?company_id={harbor['id']}&product_id={motor['id']}", headers=customer)
        assert compatible.status_code == 200
        maya = next(underwriter for underwriter in compatible.json() if underwriter["name"] == "Maya Chen")
        assert motor["id"] in maya["supported_product_ids"]

        created = client.post("/api/submissions", json={"product_id": motor["id"], "insurance_company_id": harbor["id"], "assigned_underwriter_id": maya["id"]}, headers=customer)
        assert created.status_code == 200
        submission_id = created.json()["id"]
        assert client.post(f"/api/submissions/{submission_id}/issues/generate", headers=customer).status_code == 200

        maya_login = client.post("/api/auth/login", data={"username": "maya.chen@demo.insurance", "password": "DemoUnderwriter2026!"})
        assert maya_login.status_code == 200
        maya_headers = {"Authorization": f"Bearer {maya_login.json()['access_token']}"}
        queue = client.get("/api/submissions", headers=maya_headers)
        assert submission_id in {item["id"] for item in queue.json()}

        rohan_login = client.post("/api/auth/login", data={"username": "rohan.mehta@demo.insurance", "password": "DemoUnderwriter2026!"})
        rohan_headers = {"Authorization": f"Bearer {rohan_login.json()['access_token']}"}
        other_queue = client.get("/api/submissions", headers=rohan_headers)
        assert submission_id not in {item["id"] for item in other_queue.json()}
        assert client.get(f"/api/submissions/{submission_id}/dashboard", headers=rohan_headers).status_code == 403

    def test_rejects_underwriter_from_wrong_company_or_product(self, client, db_session):
        seed(db_session)
        customer = register_and_login(client, "invalid_assignment@example.com", "CustPass1!")
        motor = next(product for product in client.get("/api/products").json() if product["name"] == "Motor Insurance")
        meridian = db_session.query(InsuranceCompany).filter_by(name="Meridian Commercial").one()
        rohan = db_session.query(User).filter_by(email="rohan.mehta@demo.insurance").one()
        response = client.post("/api/submissions", json={"product_id": motor["id"], "insurance_company_id": meridian.id, "assigned_underwriter_id": rohan.id}, headers=customer)
        assert response.status_code == 422


class TestDemonstrationData:
    def test_seeded_demo_accounts_submissions_and_relationships_are_real(self, client, db_session):
        seed(db_session)
        customer_emails = {entry[0] for entry in DEMO_CUSTOMERS}
        underwriter_emails = {entry[0] for entry in DEMO_UNDERWRITERS}
        assert db_session.query(User).filter(User.email.in_(customer_emails), User.role == "customer").count() == 5
        assert db_session.query(User).filter(User.email.in_(underwriter_emails), User.role == "underwriter").count() == 8
        assert db_session.query(InsuranceCompany).filter(InsuranceCompany.name.in_({entry[0] for entry in DEMO_COMPANIES})).count() == 4

        for email in customer_emails | underwriter_emails:
            login = client.post("/api/auth/login", data={"username": email, "password": DEMO_PASSWORD})
            assert login.status_code == 200, email

        seeded = [audit.submission for audit in db_session.query(AuditRecord).filter(AuditRecord.action == "demo_submission_seeded").all()]
        assert len(seeded) == len(DEMO_SUBMISSIONS)
        assert sum(sub.status == "draft" for sub in seeded) == 2
        assert sum(sub.status == "under_review" for sub in seeded) == 4
        assert sum(sub.status == "info_requested" for sub in seeded) == 2
        assert sum(sub.status == "approved" for sub in seeded) == 2
        for submission in seeded:
            assert submission.user_id and submission.insurance_company_id and submission.assigned_underwriter_id
            assert submission.assigned_underwriter.insurance_company_id == submission.insurance_company_id
            assert submission.product_id in (submission.assigned_underwriter.supported_product_ids or [])

    def test_demo_draft_persists_assignment_and_is_hidden_from_its_underwriter(self, client, db_session):
        seed(db_session)
        customer_login = client.post("/api/auth/login", data={"username": "customer1@example.com", "password": DEMO_PASSWORD})
        customer_headers = {"Authorization": f"Bearer {customer_login.json()['access_token']}"}
        draft = next(audit.submission for audit in db_session.query(AuditRecord).filter(AuditRecord.action == "demo_submission_seeded").all() if (audit.context_data or {}).get("label") == "motor-draft")
        state = client.get(f"/api/submissions/{draft.id}/application", headers=customer_headers)
        assert state.status_code == 200
        assert state.json()["submission"]["assigned_underwriter_name"] == "Ananya Rao"
        assert state.json()["profile"]["city"] == "Pune"

        underwriter_login = client.post("/api/auth/login", data={"username": "ananya.rao@demo.insurance", "password": DEMO_PASSWORD})
        underwriter_headers = {"Authorization": f"Bearer {underwriter_login.json()['access_token']}"}
        queue = client.get("/api/submissions", headers=underwriter_headers)
        assert draft.id not in {row["id"] for row in queue.json()}

        submitted = next(audit.submission for audit in db_session.query(AuditRecord).filter(AuditRecord.action == "demo_submission_seeded").all() if (audit.context_data or {}).get("label") == "cyber-review")
        priya_login = client.post("/api/auth/login", data={"username": "priya.nair@demo.insurance", "password": DEMO_PASSWORD})
        priya_headers = {"Authorization": f"Bearer {priya_login.json()['access_token']}"}
        assert submitted.id in {row["id"] for row in client.get("/api/submissions", headers=priya_headers).json()}
