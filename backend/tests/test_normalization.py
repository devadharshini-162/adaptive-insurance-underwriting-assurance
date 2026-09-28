import pytest
from app.services.normalization import (
    normalize_value,
    normalize_answers,
    normalize_extracted_fields,
    NormalizedValue
)

def test_norm_currency():
    res = normalize_value("annual_revenue", "₹1.5 crore")
    assert res.ok
    assert res.norm_value == "15000000"

    res = normalize_value("annual_revenue", "INR 50 lakh")
    assert res.ok
    assert res.norm_value == "5000000"

    res = normalize_value("property_value", "10,00,000")
    assert res.ok
    assert res.norm_value == "1000000"
    
    # Error case
    res = normalize_value("annual_revenue", "abc")
    assert not res.ok
    assert "abc" in res.error

def test_norm_boolean():
    assert normalize_value("hazardous_materials", "Yes").norm_value == "yes"
    assert normalize_value("hazardous_materials", "present").norm_value == "yes"
    assert normalize_value("hazardous_materials", "No").norm_value == "no"
    assert normalize_value("hazardous_materials", "absent").norm_value == "no"
    
    res = normalize_value("hazardous_materials", "maybe")
    assert not res.ok

def test_norm_risk():
    assert normalize_value("risk_level", "Moderate ").norm_value == "medium"
    assert normalize_value("risk_level", "High").norm_value == "high"
    assert normalize_value("risk_level", "low").norm_value == "low"
    
    res = normalize_value("risk_level", "unknown")
    assert not res.ok

def test_norm_date():
    assert normalize_value("policy_date", "15/08/2026").norm_value == "2026-08-15"
    assert normalize_value("policy_date", "2026-08-15").norm_value == "2026-08-15"
    assert normalize_value("policy_date", "15 Aug 2026").norm_value == "2026-08-15"
    
    res = normalize_value("policy_date", "next week")
    assert not res.ok

def test_norm_email_phone():
    assert normalize_value("contact_email", " TEST@Example.com ").norm_value == "test@example.com"
    assert not normalize_value("contact_email", "invalid").ok

    assert normalize_value("contact_phone", "+91 98765 43210").norm_value == "9876543210"
    assert normalize_value("contact_phone", "09876543210").norm_value == "9876543210"

def test_norm_text_entities():
    res = normalize_value("insured_name", " acme   corp ")
    assert res.norm_value == "Acme Corp"
    
    res = normalize_value("business_entity_type", "Private Limited")
    assert res.norm_value == "private limited"

def test_normalize_answers_mapping():
    raw_answers = {
        "1": " private limited ",
        "2": " 2 crore ",
        "3": "Yes",
        "4": "₹5,00,00,000",
        "5": "High",
        "99": "some unknown question"
    }
    norms = normalize_answers(raw_answers)
    
    # 1 -> business_entity_type
    assert norms["business_entity_type"].norm_value == "private limited"
    assert norms["annual_revenue"].norm_value == "20000000"
    assert norms["hazardous_materials"].norm_value == "yes"
    assert norms["property_value"].norm_value == "50000000"
    assert norms["risk_level"].norm_value == "high"
    
    # Unknown gets passed as generic text
    assert norms["question_99"].norm_value == "some unknown question"

def test_normalize_extracted_fields():
    raw_fields = {
        "annual_revenue": "1.5 cr",
        "insured_name": "JOHN DOE"
    }
    norms = normalize_extracted_fields(raw_fields)
    assert norms["annual_revenue"].norm_value == "15000000"
    assert norms["annual_revenue"].source == "document"
    assert norms["insured_name"].norm_value == "John Doe"
