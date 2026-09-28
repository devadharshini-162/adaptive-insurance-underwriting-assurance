import pytest
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

from app.services.consistency_service import compare_values, run_consistency_checks
from app.services.normalization import NormalizedValue
from app.models.core import Answer, Evidence, Document, Submission, ExtractedField

def test_compare_values_exact_match():
    # Identical numbers
    nv1 = NormalizedValue(raw_value="15 crore", norm_value="15000000", data_type="number", source="answer")
    nv2 = NormalizedValue(raw_value="1,50,00,000", norm_value="15000000", data_type="number", source="document")
    status, reason = compare_values("annual_revenue", nv1, nv2)
    assert status == "CONSISTENT"

def test_compare_values_numeric_tolerance():
    # Document has 15,000,000. Answer is 15,200,000. Difference is 200k. Max is 15.2m. 
    # 200,000 / 15,200,000 = ~1.3% (within 5% tolerance map for annual_revenue)
    nv1 = NormalizedValue(raw_value="15.2M", norm_value="15200000", data_type="number", source="answer")
    nv2 = NormalizedValue(raw_value="1,50,00,000", norm_value="15000000", data_type="number", source="document")
    status, reason = compare_values("annual_revenue", nv1, nv2)
    assert status == "CONSISTENT"

    # Beyond tolerance: Document: 10,000,000, Answer: 15,000,000. Diff = 5m. 5/15 = ~33% (>5%)
    nv1_far = NormalizedValue(raw_value="15M", norm_value="15000000", data_type="number", source="answer")
    nv2_far = NormalizedValue(raw_value="1,00,00,000", norm_value="10000000", data_type="number", source="document")
    status, reason = compare_values("annual_revenue", nv1_far, nv2_far)
    assert status == "CONFLICT"

def test_compare_values_booleans():
    nv1 = NormalizedValue(raw_value="yes", norm_value="yes", data_type="boolean", source="answer")
    nv2 = NormalizedValue(raw_value="present", norm_value="yes", data_type="boolean", source="document")
    status, reason = compare_values("hazardous_materials", nv1, nv2)
    assert status == "CONSISTENT"

    nv1_no = NormalizedValue(raw_value="no", norm_value="no", data_type="boolean", source="answer")
    status, reason = compare_values("hazardous_materials", nv1_no, nv2)
    assert status == "CONFLICT"

def test_compare_values_unparseable_fails():
    nv1 = NormalizedValue(raw_value="n/a", norm_value="", data_type="number", source="answer", error="Bad num")
    nv2 = NormalizedValue(raw_value="1,50,00,000", norm_value="15000000", data_type="number", source="document")
    status, reason = compare_values("annual_revenue", nv1, nv2)
    assert status == "NOT_COMPARABLE"


def test_run_consistency_checks_integration(db_session):
    # Setup test seed data
    from app.models.core import User, InsuranceProduct
    user = User(email="tce@test.com", name="TestAgent", role="agent")
    db_session.add(user)
    prod = InsuranceProduct(name="Test", description="Test")
    db_session.add(prod)
    db_session.flush()

    sub = Submission(user_id=user.id, product_id=prod.id, status="draft")
    db_session.add(sub)
    db_session.flush()

    # Answer: annual_revenue = 10,000,000 (question_id 2 maps to annual_revenue natively in normalize)
    # Question mapping in normalize_answers: "2": "annual_revenue"
    ans1 = Answer(submission_id=sub.id, question_id=2, value="10000000")
    # Answer: hazardous_materials = yes (question_id 3)
    ans2 = Answer(submission_id=sub.id, question_id=3, value="yes")
    db_session.add_all([ans1, ans2])
    db_session.flush()

    doc = Document(submission_id=sub.id, file_path="/fake", status="processed")
    db_session.add(doc)
    db_session.flush()

    # Document Extraction
    # Revenue is exactly same -> CONSISTENT
    ef1 = ExtractedField(document_id=doc.id, key="annual_revenue", raw_value="1,00,00,000", normalized_value="10000000")
    db_session.add(ef1)
    db_session.flush()
    ev1 = Evidence(submission_id=sub.id, extracted_field_id=ef1.id, canonical_key="annual_revenue")
    
    # Hazmat is 'no' -> CONFLICT
    ef2 = ExtractedField(document_id=doc.id, key="hazardous_materials", raw_value="No", normalized_value="no")
    db_session.add(ef2)
    db_session.flush()
    ev2 = Evidence(submission_id=sub.id, extracted_field_id=ef2.id, canonical_key="hazardous_materials")
    db_session.add_all([ev1, ev2])

    # Extracted field with NO corresponding answer -> INSUFFICIENT_EVIDENCE
    ef3 = ExtractedField(document_id=doc.id, key="property_value", raw_value="5.0 cr", normalized_value="50000000")
    db_session.add(ef3)
    db_session.flush()
    ev3 = Evidence(submission_id=sub.id, extracted_field_id=ef3.id, canonical_key="property_value")
    db_session.add(ev3)
    
    db_session.commit()

    checks = run_consistency_checks(db_session, sub.id)

    # 3 canonical keys checked (annual_revenue, hazardous_materials, property_value)
    assert len(checks) == 3

    statuses = {c.details["canonical_key"]: c.status for c in checks}
    assert statuses["annual_revenue"] == "CONSISTENT"
    assert statuses["hazardous_materials"] == "CONFLICT"
    assert statuses["property_value"] == "INSUFFICIENT_EVIDENCE"
