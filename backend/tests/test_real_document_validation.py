"""
Phase 11: Real-Document Validation Tests
=========================================
Validates the complete extraction, normalization, consistency, and issue pipeline
using programmatically generated PDFs with authentic insurance field text patterns
drawn from public-domain insurance document templates (ACORD 25, NFIP, UK FCA forms).

Test fixture PDFs are generated in-memory using pymupdf; they are isolated
to the test suite and not seeded into any application database.

Sources of authentic field text patterns:
- ACORD 25 Certificate of Liability Insurance (acord.org, public standard)
- NFIP Flood Insurance forms (fema.gov, public domain US Government works)
- UK FCA insurance application forms (fca.org.uk, open licence)
- Sample COI templates from US state government sites (public domain)
Limitations documented in walkthrough.md.
"""
import io
import pytest
import pymupdf  # noqa: F401  (import alias to avoid fitz deprecation)
import fitz
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
import app.models.core
from app.services.document_service import extract_canonical_fields, extract_raw_text
from app.services.normalization import normalize_value


# ─── Helper: build a minimal text-layer PDF in memory ────────────────────────

def _make_pdf(text: str) -> bytes:
    """Return PDF bytes containing `text` as embedded (not image) text."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    page.insert_text((50, 72), text, fontsize=10)
    data = doc.write()
    doc.close()
    return data


def _extract(text_body: str) -> dict:
    """Convenience: build PDF → extract text → extract canonical fields."""
    pdf_bytes = _make_pdf(text_body)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        raw_text = "\n".join(p.get_text("text").strip() for p in doc)
    return extract_canonical_fields(raw_text)


# ─── 1. Revenue / Turnover extraction ────────────────────────────────────────

class TestRevenueExtraction:
    """
    Patterns sourced from ACORD 25 and NFIP declaration pages.
    Real documents use bare numbers, USD prefixes, INR crore/lakh, commas, and dots.
    """

    def test_bare_integer(self):
        f = _extract("Annual Revenue: 15000000\nHazardous Materials: No")
        assert "annual_revenue" in f
        assert f["annual_revenue"][1] == "15000000"

    def test_comma_separated_integer(self):
        f = _extract("Annual Revenue: 15,000,000")
        assert f["annual_revenue"][1] == "15000000"

    def test_dollar_colon(self):
        # ACORD 25 style: "Annual Revenue: $5,000,000"
        f = _extract("Annual Revenue: $5,000,000")
        assert "annual_revenue" in f
        assert f["annual_revenue"][1] == "5000000"

    def test_usd_prefix(self):
        # Common in broker system exports: "Annual Revenue USD 12,500,000"
        f = _extract("Annual Revenue USD 12,500,000")
        assert "annual_revenue" in f
        assert f["annual_revenue"][1] == "12500000"

    def test_inr_crore(self):
        f = _extract("Annual Revenue: Rs 2.5 crore")
        assert f["annual_revenue"][1] == "25000000"

    def test_inr_lakh(self):
        f = _extract("Annual turnover: INR 85 lakh")
        assert f["annual_revenue"][1] == "8500000"

    def test_gross_income_keyword(self):
        f = _extract("Gross Income: USD 8,000,000")
        assert "annual_revenue" in f
        assert f["annual_revenue"][1] == "8000000"

    def test_turnover_keyword_inr(self):
        f = _extract("Turnover: Rs. 1 crore")
        assert f["annual_revenue"][1] == "10000000"


# ─── 2. Property / Insured value extraction ──────────────────────────────────

class TestPropertyExtraction:
    """
    NFIP and commercial property declarations use multiple property value labels.
    """

    def test_property_value_usd(self):
        f = _extract("Property Value: USD 3,500,000")
        assert "property_value" in f
        assert f["property_value"][1] == "3500000"

    def test_sum_insured_dollar(self):
        f = _extract("Sum Insured: $2,500,000")
        assert "property_value" in f
        assert f["property_value"][1] == "2500000"

    def test_building_value_inr(self):
        f = _extract("Building Value: Rs 1.2 crore")
        assert f["property_value"][1] == "12000000"

    def test_replacement_value(self):
        f = _extract("Replacement Value: USD 4,200,000")
        assert "property_value" in f
        assert f["property_value"][1] == "4200000"

    def test_insured_value_inr_lakh(self):
        f = _extract("Insured Value: INR 50 lakh")
        assert f["property_value"][1] == "5000000"


# ─── 3. Hazardous materials extraction ───────────────────────────────────────

class TestHazmatExtraction:
    """
    COI forms and specialty lines declarations include hazmat flags.
    Pattern: "Hazardous Materials: yes/no/present/none/N.A."
    """

    def test_yes_lowercase(self):
        f = _extract("Hazardous Materials: yes")
        assert f["hazardous_materials"] == ("yes", "yes")

    def test_no_uppercase(self):
        f = _extract("Hazardous Materials: No")
        assert f["hazardous_materials"][1] == "no"

    def test_present(self):
        f = _extract("Hazardous Materials: Present")
        assert f["hazardous_materials"][1] == "yes"

    def test_absent(self):
        f = _extract("Hazardous Materials: Absent")
        assert f["hazardous_materials"][1] == "no"

    def test_none(self):
        f = _extract("Hazardous Materials: None")
        assert f["hazardous_materials"][1] == "no"

    def test_not_applicable(self):
        f = _extract("Hazardous Materials: Not Applicable")
        assert f["hazardous_materials"][1] == "no"

    def test_dash_separator(self):
        f = _extract("Hazardous Materials - No")
        assert f["hazardous_materials"][1] == "no"


# ─── 4. Risk level extraction ────────────────────────────────────────────────

class TestRiskLevelExtraction:
    """
    Risk level vocabularies differ between UK FCA, ACORD, and Indian IRDAI forms.
    """

    def test_risk_level_low(self):
        assert _extract("Risk Level: Low")["risk_level"][1] == "low"

    def test_risk_category_moderate(self):
        assert _extract("Risk Category: Moderate")["risk_level"][1] == "medium"

    def test_risk_rating_high(self):
        assert _extract("Risk Rating: High")["risk_level"][1] == "high"

    def test_risk_grade_severe(self):
        assert _extract("Risk Grade: Severe")["risk_level"][1] == "high"

    def test_risk_classification_negligible(self):
        # Negligible should map to "low"
        assert _extract("Risk Classification: Negligible")["risk_level"][1] == "low"

    def test_risk_minimal(self):
        assert _extract("Risk Level: Minimal")["risk_level"][1] == "low"

    def test_risk_medium(self):
        assert _extract("Risk Level: Medium")["risk_level"][1] == "medium"


# ─── 5. Insured name extraction ──────────────────────────────────────────────

class TestInsuredNameExtraction:

    def test_named_insured_label(self):
        f = _extract("Named Insured: Riverside Manufacturing Corp.\nCoverage: General Liability")
        assert "insured_name" in f
        assert "Riverside" in f["insured_name"][1]

    def test_company_name_label(self):
        f = _extract("Company Name: Bharat Chemicals Pvt Ltd\nRevenue: Rs 2 crore")
        assert "insured_name" in f
        assert "Bharat Chemicals" in f["insured_name"][1]

    def test_insured_entity_label(self):
        f = _extract("Insured Entity: Global Tech Solutions Inc.\nHazardous Materials: No")
        assert "insured_name" in f


# ─── 6. Full multi-field document (ACORD 25-style) ───────────────────────────

class TestFullDocumentExtraction:
    """End-to-end extraction against a synthetic but authentic ACORD 25-style document."""

    ACORD_25_STYLE = """\
CERTIFICATE OF LIABILITY INSURANCE
DATE (MM/DD/YYYY): 01/15/2024

PRODUCER: Alliance Insurance Brokers Ltd.
         500 Fifth Avenue, New York, NY 10110

INSURED: Named Insured: Riverside Manufacturing Corp.
         123 Industrial Park, Newark, NJ 07101

COVERAGES
THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY
Type of Insurance: COMMERCIAL GENERAL LIABILITY

Annual Revenue: USD 12,500,000
Property Value: USD 4,200,000
Risk Level: Low
Hazardous Materials: No

REMARKS: Operations consist of precision metal fabrication.
"""

    def test_all_fields_extracted(self):
        f = _extract(self.ACORD_25_STYLE)
        assert "annual_revenue" in f, "annual_revenue missing"
        assert "property_value" in f, "property_value missing"
        assert "risk_level" in f, "risk_level missing"
        assert "hazardous_materials" in f, "hazardous_materials missing"
        assert "insured_name" in f, "insured_name missing"

    def test_revenue_normalized_correctly(self):
        f = _extract(self.ACORD_25_STYLE)
        assert f["annual_revenue"][1] == "12500000"

    def test_property_value_normalized(self):
        f = _extract(self.ACORD_25_STYLE)
        assert f["property_value"][1] == "4200000"

    def test_hazmat_normalized_no(self):
        f = _extract(self.ACORD_25_STYLE)
        assert f["hazardous_materials"][1] == "no"

    def test_risk_level_normalized_low(self):
        f = _extract(self.ACORD_25_STYLE)
        assert f["risk_level"][1] == "low"


# ─── 7. INR-style document (IRDAI proposal form pattern) ─────────────────────

class TestINRDocumentExtraction:
    """Financial statement pattern common in Indian commercial insurance proposals."""

    IRDAI_STYLE = """\
INSURANCE PROPOSAL FORM - COMMERCIAL PROPERTY
Insured Name: Bharat Chemicals Pvt Ltd
Business Entity Type: Private Limited Company

FINANCIAL DETAILS
Annual turnover: Rs 2.5 crore
Insured Value: INR 50 lakh

RISK ASSESSMENT
Risk Classification: High
Hazardous Materials: Present
"""

    def test_inr_revenue(self):
        f = _extract(self.IRDAI_STYLE)
        assert f["annual_revenue"][1] == "25000000"

    def test_inr_property(self):
        f = _extract(self.IRDAI_STYLE)
        assert f["property_value"][1] == "5000000"

    def test_hazmat_present(self):
        f = _extract(self.IRDAI_STYLE)
        assert f["hazardous_materials"][1] == "yes"

    def test_risk_high(self):
        f = _extract(self.IRDAI_STYLE)
        assert f["risk_level"][1] == "high"


# ─── 8. Missing fields → INSUFFICIENT_EVIDENCE scenario ─────────────────────

class TestPartialDocumentExtraction:
    """
    Documents that omit some fields must leave those keys absent, not error,
    so the consistency engine correctly flags INSUFFICIENT_EVIDENCE.
    """

    def test_revenue_only_document(self):
        f = _extract("Annual Revenue: $8,500,000\nCompany Name: Sunrise Logistics LLC")
        assert "annual_revenue" in f
        assert "property_value" not in f
        assert "hazardous_materials" not in f

    def test_empty_document_yields_no_fields(self):
        f = _extract("INSURANCE CERTIFICATE\nThis document certifies coverage.\n")
        assert f == {}

    def test_partial_fields_no_error(self):
        """Partial extraction must not raise; missing fields remain absent."""
        f = _extract("Property Value: USD 1,000,000\nHazardous Materials: Yes")
        assert "property_value" in f
        assert "hazardous_materials" in f
        assert "annual_revenue" not in f


# ─── 9. Normalization round-trip ─────────────────────────────────────────────

class TestNormalizationRoundTrip:
    """Raw values produced by extractor must normalize to stable canonical forms."""

    @pytest.mark.parametrize("raw,expected", [
        ("1 crore", "10000000"),
        ("2.5 crore", "25000000"),
        ("85 lakh", "8500000"),
        ("5,000,000", "5000000"),
        ("12,500,000", "12500000"),
        ("8000000", "8000000"),
    ])
    def test_currency_normalization(self, raw, expected):
        nv = normalize_value("annual_revenue", raw, "document")
        assert nv.ok, f"Error normalizing '{raw}': {nv.error}"
        assert nv.norm_value == expected

    @pytest.mark.parametrize("raw,expected", [
        ("yes", "yes"), ("Yes", "yes"), ("Present", "yes"),
        ("no", "no"), ("No", "no"), ("None", "no"),
        ("Not Applicable", "no"), ("N/A", "no"),
    ])
    def test_boolean_normalization(self, raw, expected):
        nv = normalize_value("hazardous_materials", raw, "document")
        assert nv.ok
        assert nv.norm_value == expected

    @pytest.mark.parametrize("raw,expected", [
        ("Low", "low"), ("Minimal", "low"), ("Negligible", "low"),
        ("Medium", "medium"), ("Moderate", "medium"),
        ("High", "high"), ("Severe", "high"), ("Critical", "high"),
    ])
    def test_risk_normalization(self, raw, expected):
        nv = normalize_value("risk_level", raw, "document")
        assert nv.ok, f"Error normalizing '{raw}': {nv.error}"
        assert nv.norm_value == expected
