import pytest
from app.services.issue_mapper import generate_issues_for_submission
from app.models.core import Submission, User, InsuranceProduct, ConsistencyCheck, UnderwritingIssue, Question, Requirement, Answer, Document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture(scope="function")
def setup_data(db_session):
    user = User(email="tce@test.com", name="TestAgent", role="agent")
    db_session.add(user)
    
    prod = InsuranceProduct(name="Test", description="Test")
    db_session.add(prod)
    db_session.flush()

    sub = Submission(user_id=user.id, product_id=prod.id, status="draft")
    db_session.add(sub)
    db_session.flush()

    # Create dummy question that maps to a requirement
    q = Question(product_id=prod.id, text="Hazardous?", field_type="text")
    db_session.add(q)
    db_session.flush()

    req = Requirement(
        product_id=prod.id,
        name="Hazmat Declaration",
        description="Proof of hazmat protocol",
        rule_logic={
            "operator": "==",
            "question_id": q.id,
            "value": "yes"
        }
    )
    db_session.add(req)
    db_session.flush()
    return user, prod, sub, q, req

def test_missing_critical_requirement(db_session, setup_data):
    _, _, sub, q, _ = setup_data
    # Trigger requirement by answering yes
    ans = Answer(submission_id=sub.id, question_id=q.id, value="yes")
    db_session.add(ans)
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    assert len(issues) == 1
    assert issues[0].issue_type == "MISSING_EVIDENCE"
    assert issues[0].details["severity"] == "HIGH"
    assert issues[0].details["comparison_result"] == "MISSING"

def test_critical_conflict(db_session, setup_data):
    _, _, sub, _, _ = setup_data
    # annual_revenue is in CRITICAL_FIELDS
    check = ConsistencyCheck(
        submission_id=sub.id,
        status="CONFLICT",
        details={"canonical_key": "annual_revenue", "reason": "Discrepancy"}
    )
    db_session.add(check)
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    assert len(issues) == 1
    assert issues[0].details["severity"] == "HIGH"

def test_normal_conflict(db_session, setup_data):
    _, _, sub, _, _ = setup_data
    check = ConsistencyCheck(
        submission_id=sub.id,
        status="CONFLICT",
        details={"canonical_key": "some_other_field", "reason": "Diff"}
    )
    db_session.add(check)
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    assert len(issues) == 1
    assert issues[0].details["severity"] == "MEDIUM"

def test_not_comparable_behavior(db_session, setup_data):
    _, _, sub, _, _ = setup_data
    
    # Critical field -> MEDIUM
    check1 = ConsistencyCheck(
        submission_id=sub.id,
        status="NOT_COMPARABLE",
        details={"canonical_key": "annual_revenue"}
    )
    # Non-critical field -> LOW (informational)
    check2 = ConsistencyCheck(
        submission_id=sub.id,
        status="NOT_COMPARABLE",
        details={"canonical_key": "unknown_date"}
    )
    db_session.add_all([check1, check2])
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    issues.sort(key=lambda i: i.details["severity"]) # Sort LOW, MEDIUM
    assert len(issues) == 2
    assert issues[0].details["severity"] == "LOW"
    assert issues[1].details["severity"] == "MEDIUM"

def test_consistent_produces_no_issues(db_session, setup_data):
    _, _, sub, q, req = setup_data

    # Add a document to satisfy the requirement
    ans = Answer(submission_id=sub.id, question_id=q.id, value="yes")
    doc = Document(submission_id=sub.id, requirement_id=req.id, status="processed")
    db_session.add_all([ans, doc])
    
    # Add a consistent check
    check = ConsistencyCheck(
        submission_id=sub.id,
        status="CONSISTENT",
        details={"canonical_key": "annual_revenue"}
    )
    db_session.add(check)
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    assert len(issues) == 0

def test_idempotency_repeated_generation(db_session, setup_data):
    _, _, sub, q, _ = setup_data
    ans = Answer(submission_id=sub.id, question_id=q.id, value="yes")
    db_session.add(ans)
    db_session.commit()

    # First run
    issues1 = generate_issues_for_submission(db_session, sub.id)
    assert len(issues1) == 1
    
    # Second run should clear and regenerate exactly 1
    issues2 = generate_issues_for_submission(db_session, sub.id)
    assert len(issues2) == 1
    
    all_issues = db_session.query(UnderwritingIssue).all()
    assert len(all_issues) == 1


def test_explainability_payload(db_session, setup_data):
    """Every issue must contain the full explainability trail."""
    _, _, sub, _, _ = setup_data
    check = ConsistencyCheck(
        submission_id=sub.id,
        status="CONFLICT",
        details={
            "canonical_key": "annual_revenue",
            "reason": "Numeric discrepancy exceeds 5.0% tolerance.",
            "values": [
                {"raw_value": "1.5 crore", "norm_value": "15000000", "source": "answer"},
                {"raw_value": "1,80,00,000", "norm_value": "18000000", "source": "document_1"},
            ],
        },
    )
    db_session.add(check)
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    assert len(issues) == 1
    d = issues[0].details
    # Verify every required explainability key is present
    for key in (
        "source_rule", "triggering_field", "sources", "raw_values",
        "normalized_values", "comparison_result", "reason", "severity",
        "recommended_action",
    ):
        assert key in d, f"Missing key: {key}"
    assert d["triggering_field"] == "annual_revenue"
    assert d["sources"] == ["answer", "document_1"]
    assert d["raw_values"] == ["1.5 crore", "1,80,00,000"]
    assert d["normalized_values"] == ["15000000", "18000000"]
    assert d["comparison_result"] == "CONFLICT"
    assert d["severity"] == "HIGH"


def test_multiple_simultaneous_issues(db_session, setup_data):
    """A submission can have conflicts AND missing requirements at the same time."""
    _, _, sub, q, _ = setup_data

    # Trigger missing-evidence by answering "yes" (activates the hazmat requirement)
    ans = Answer(submission_id=sub.id, question_id=q.id, value="yes")
    db_session.add(ans)

    # Add two distinct conflicts
    c1 = ConsistencyCheck(
        submission_id=sub.id, status="CONFLICT",
        details={"canonical_key": "annual_revenue", "reason": "Revenue mismatch"},
    )
    c2 = ConsistencyCheck(
        submission_id=sub.id, status="CONFLICT",
        details={"canonical_key": "risk_level", "reason": "Risk level mismatch"},
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    issues = generate_issues_for_submission(db_session, sub.id)
    # 2 conflicts + 1 missing requirement = 3
    assert len(issues) == 3
    types = {i.issue_type for i in issues}
    assert types == {"DISCREPANCY", "MISSING_EVIDENCE"}

