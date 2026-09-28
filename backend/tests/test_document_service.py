"""
Tests for Phase 5: Document ingestion service.
Tests validation, text extraction, field extraction, normalization, and DB persistence.
Uses pytest fixtures with a temporary SQLite DB to avoid touching the real production DB.
"""
import io
import os
import tempfile
from pathlib import Path
import pytest

# ── Minimal DB fixture using SQLite in-memory ───────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
import app.models.core  # registers all models on Base

@pytest.fixture(scope="function")
def db_session(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Point upload dir to temp directory for tests
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    # Re-resolve UPLOAD_DIR after env patch
    import app.services.document_service as ds
    ds.UPLOAD_DIR = tmp_path

    yield session
    session.close()
    engine.dispose()


# ── Helpers ──────────────────────────────────────────────────────────────────

from app.services.document_service import (
    validate_upload,
    extract_canonical_fields,
    extract_raw_text,
    persist_extracted_fields,
    ingest_document,
    DocumentValidationError,
    MAX_SIZE_BYTES,
    ALLOWED_EXTENSIONS,
)
from app.models.core import ExtractedField


def make_file(content: bytes, filename: str, content_type: str):
    return io.BytesIO(content), filename, content_type, len(content)


# ────────────────────────────────────────────────────────────────────────────
# 1. Valid upload / validation passes
# ────────────────────────────────────────────────────────────────────────────

def test_valid_pdf_validation_passes():
    validate_upload("doc.pdf", "application/pdf", 1024)  # should not raise


def test_valid_jpeg_validation_passes():
    validate_upload("photo.jpg", "image/jpeg", 500_000)


def test_valid_png_validation_passes():
    validate_upload("screenshot.png", "image/png", 200_000)


# ────────────────────────────────────────────────────────────────────────────
# 2. Unsupported file type rejection
# ────────────────────────────────────────────────────────────────────────────

def test_unsupported_extension_rejected():
    with pytest.raises(DocumentValidationError, match="Unsupported file extension"):
        validate_upload("spreadsheet.xlsx", "application/pdf", 1024)


def test_unsupported_mime_rejected():
    with pytest.raises(DocumentValidationError, match="Unsupported content type"):
        validate_upload("file.pdf", "application/octet-stream", 1024)


def test_exe_rejected():
    with pytest.raises(DocumentValidationError, match="Unsupported file extension"):
        validate_upload("malware.exe", "application/octet-stream", 100)


# ────────────────────────────────────────────────────────────────────────────
# 3. Oversized file rejection
# ────────────────────────────────────────────────────────────────────────────

def test_oversized_file_rejected():
    with pytest.raises(DocumentValidationError, match="exceeds maximum"):
        validate_upload("big.pdf", "application/pdf", MAX_SIZE_BYTES + 1)


def test_max_size_boundary_accepted():
    validate_upload("ok.pdf", "application/pdf", MAX_SIZE_BYTES)  # exact limit: accepted


# ────────────────────────────────────────────────────────────────────────────
# 4. Canonical field extraction from text
# ────────────────────────────────────────────────────────────────────────────

def test_extract_annual_revenue_plain_number():
    text = "Annual Revenue: 15000000"
    fields = extract_canonical_fields(text)
    assert "annual_revenue" in fields
    assert fields["annual_revenue"][1] == "15000000"


def test_extract_revenue_with_crore_unit():
    text = "Revenue: 1.5 crore"
    fields = extract_canonical_fields(text)
    assert "annual_revenue" in fields
    assert int(fields["annual_revenue"][1]) == 15_000_000


def test_extract_revenue_with_lakh_unit():
    text = "Annual turnover: 80 lakh"
    fields = extract_canonical_fields(text)
    assert "annual_revenue" in fields
    assert int(fields["annual_revenue"][1]) == 8_000_000


def test_extract_property_value():
    text = "Property value: 5,00,00,000"
    fields = extract_canonical_fields(text)
    assert "property_value" in fields
    assert fields["property_value"][1] == "50000000"


def test_extract_hazmat_yes():
    text = "Hazardous materials: Yes"
    fields = extract_canonical_fields(text)
    assert fields["hazardous_materials"] == ("Yes", "yes")


def test_extract_hazmat_no():
    text = "Hazardous materials: No"
    fields = extract_canonical_fields(text)
    assert fields["hazardous_materials"] == ("No", "no")


def test_extract_risk_level_high():
    text = "Risk classification: High"
    fields = extract_canonical_fields(text)
    assert fields["risk_level"] == ("High", "high")


def test_extract_risk_level_moderate_normalised():
    text = "Risk rating: moderate"
    fields = extract_canonical_fields(text)
    assert fields["risk_level"][1] == "medium"


def test_extract_insured_name():
    text = "Insured Name: Acme Manufacturing Ltd"
    fields = extract_canonical_fields(text)
    assert "insured_name" in fields
    assert "Acme" in fields["insured_name"][1]


def test_no_fields_extracted_from_empty_text():
    fields = extract_canonical_fields("")
    assert fields == {}


def test_partial_fields_extracted():
    text = "Risk classification: low"
    fields = extract_canonical_fields(text)
    assert "risk_level" in fields
    assert "annual_revenue" not in fields


# ────────────────────────────────────────────────────────────────────────────
# 6. Text extraction from a real in-memory text-based PDF
# ────────────────────────────────────────────────────────────────────────────

def test_extract_text_from_text_pdf(tmp_path):
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Annual Revenue: 20000000\nHazardous materials: No")
    doc.save(str(pdf_path))
    doc.close()

    text = extract_raw_text(pdf_path)
    assert "Annual Revenue" in text
    assert "20000000" in text


# ────────────────────────────────────────────────────────────────────────────
# 7. DB persistence of extracted fields
# ────────────────────────────────────────────────────────────────────────────

def test_persist_extracted_fields(db_session):
    from app.models.core import Document as DocumentModel, InsuranceProduct, Submission, User
    user = User(email="test@x.com", name="Test", role="agent")
    db_session.add(user)
    product = InsuranceProduct(name="Test Product", description="Test")
    db_session.add(product)
    db_session.flush()
    submission = Submission(user_id=user.id, product_id=product.id, status="draft")
    db_session.add(submission)
    db_session.flush()
    doc = DocumentModel(submission_id=submission.id, file_path="/tmp/fake.pdf", status="processing")
    db_session.add(doc)
    db_session.flush()

    fields = {
        "annual_revenue": ("15000000", "15000000"),
        "hazardous_materials": ("No", "no"),
    }
    persist_extracted_fields(db_session, doc, fields)

    stored = db_session.query(ExtractedField).filter(ExtractedField.document_id == doc.id).all()
    assert len(stored) == 2
    keys = {ef.key for ef in stored}
    assert "annual_revenue" in keys
    assert "hazardous_materials" in keys


# ────────────────────────────────────────────────────────────────────────────
# 8. Full ingest pipeline (happy path) with synthetic text-based PDF
# ────────────────────────────────────────────────────────────────────────────

def test_full_ingest_pipeline(db_session, tmp_path, monkeypatch):
    import fitz
    from app.models.core import InsuranceProduct, Submission, User

    user = User(email="agent2@x.com", name="Agent", role="agent")
    db_session.add(user)
    product = InsuranceProduct(name="Commercial Property", description="Test")
    db_session.add(product)
    db_session.flush()
    submission = Submission(user_id=user.id, product_id=product.id, status="draft")
    db_session.add(submission)
    db_session.flush()

    # Build a real text PDF
    buf = io.BytesIO()
    pdf_doc = fitz.open()
    page = pdf_doc.new_page()
    page.insert_text((50, 72), (
        "Insured Name: Test Corp Ltd\n"
        "Annual Revenue: 25000000\n"
        "Property value: 60000000\n"
        "Hazardous materials: Yes\n"
        "Risk classification: High"
    ))
    pdf_doc.save(buf)
    pdf_doc.close()
    buf.seek(0)

    result = ingest_document(
        db=db_session,
        submission_id=submission.id,
        requirement_id=None,
        file_obj=buf,
        filename="financial_statement.pdf",
        content_type="application/pdf",
        file_size=buf.getbuffer().nbytes,
    )

    assert result["status"] == "processed"
    fields = result["extracted_fields"]
    assert "annual_revenue" in fields
    assert fields["annual_revenue"]["normalized"] == "25000000"
    assert "hazardous_materials" in fields
    assert fields["hazardous_materials"]["normalized"] == "yes"
    assert fields["risk_level"]["normalized"] == "high"
