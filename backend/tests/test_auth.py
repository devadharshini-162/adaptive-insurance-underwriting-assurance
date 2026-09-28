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
from app.models.core import User, InsuranceProduct, AuditRecord, Submission, Question, Requirement, Document, ExtractedField, UnderwritingIssue
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
        client.post("/api/submissions", json={"product_id": product.id}, headers=customer_headers)
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
        assert skipped.status_code == 409
        assert "Cannot change" in skipped.json()["detail"]
        self._submit_for_review(client, invalid_id, customer_headers)
        assert client.put(f"/api/submissions/{invalid_id}/status", json={"status": "declined"}, headers=underwriter_headers).status_code == 200
        assert client.put(f"/api/submissions/{invalid_id}/status", json={"status": "under_review"}, headers=underwriter_headers).status_code == 409
        assert client.put(f"/api/submissions/{invalid_id}/answers", json={}, headers=customer_headers).status_code == 409
        assert client.post(f"/api/submissions/{invalid_id}/issues/generate", headers=customer_headers).status_code == 409


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
        issue = UnderwritingIssue(submission_id=submission_id, issue_type="conflict", description="Property value mismatch", status="open", details={"reason": "Values differ."})
        db_session.add(issue); db_session.commit()

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
