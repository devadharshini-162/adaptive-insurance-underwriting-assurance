"""
Issue Mapper (Phase 8)
=====================================
Translates discrepancies and missing requirements into Underwriting Issues.
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..models.core import Submission, ConsistencyCheck, UnderwritingIssue, Requirement, Document, Answer
from .engine import evaluate_requirements
from .normalization import normalize_answers

CRITICAL_FIELDS = ["annual_revenue", "property_value", "hazardous_materials", "risk_level"]
FIELD_LABELS = {"annual_revenue": "Annual revenue", "property_value": "Property value", "hazardous_materials": "Hazardous materials", "risk_level": "Risk classification"}

def generate_issues_for_submission(db: Session, submission_id: int) -> List[UnderwritingIssue]:
    """
    Idempotent service. Deletes existing issues and reconstructs them based on:
    1. Phase 7 ConsistencyCheck results.
    2. Phase 3 Requirement evaluation vs Document fulfillment.
    """
    # 1. Clear existing open issues (idempotency)
    db.query(UnderwritingIssue).filter(UnderwritingIssue.submission_id == submission_id).delete()
    
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        return []

    issues = []

    # 2. Process inconsistency conflicts
    checks = db.query(ConsistencyCheck).filter(ConsistencyCheck.submission_id == submission_id).all()
    for check in checks:
        if check.status == "CONSISTENT" or check.status == "INSUFFICIENT_EVIDENCE":
            continue
            
        c_key = check.details.get("canonical_key", "unknown")
        field_label = FIELD_LABELS.get(c_key, "Submitted information")
        
        # Determine Severity based on rule-driven configuration
        severity = "MEDIUM"
        if c_key in CRITICAL_FIELDS:
            severity = "HIGH"
            
        if check.status == "NOT_COMPARABLE":
            # Only elevate to an issue if it is a critical field that requires verification
            if c_key in CRITICAL_FIELDS:
                severity = "MEDIUM"
                action = f"Review the {field_label.lower()} in the application and supporting evidence."
            else:
                # Informational for non-critical NOT_COMPARABLE
                severity = "LOW"
                action = f"Verify the {field_label.lower()} during review."
            category = "Requires manual review"
            description = f"Unable to verify {field_label.lower()}"
        else: # CONFLICT
            category = "Document mismatch"
            description = f"{field_label} does not match supporting evidence"
            action = f"Confirm the correct {field_label.lower()} with the applicant."
            if severity == "HIGH":
                action = f"Confirm the correct {field_label.lower()} before making a final decision."

        ui = UnderwritingIssue(
            submission_id=submission_id,
            consistency_check_id=check.id,
            issue_type="REQUIRES_MANUAL_REVIEW" if check.status == "NOT_COMPARABLE" else "DOCUMENT_MISMATCH",
            description=description,
            status="open",
            details={
                "source_rule": f"Consistency check for {c_key}",
                "triggering_field": c_key,
                "sources": [v.get("source") for v in check.details.get("values", [])],
                "raw_values": [v.get("raw_value") for v in check.details.get("values", [])],
                "normalized_values": [v.get("norm_value") for v in check.details.get("values", [])],
                "comparison_result": check.status,
                "display_category": category,
                "summary": description,
                "reason": f"The {field_label.lower()} recorded in the application differs from the available supporting evidence." if check.status == "CONFLICT" else f"The available evidence is not sufficient to verify the {field_label.lower()} automatically.",
                "severity": severity,
                "recommended_action": action
            }
        )
        issues.append(ui)

    # 3. Evaluate Phase 3 conditional requirements against current answers
    answers = db.query(Answer).filter(Answer.submission_id == submission_id).all()
    ans_dict = {str(a.question_id): a.value for a in answers}
    
    # Requirement engine runs logic
    requirements_data = evaluate_requirements(db, sub.product_id, ans_dict)
    
    # We must see if these requirements have fullfilling Documents uploaded
    # The Document table maps to requirement_id.
    fulfilled_req_ids = {
        d.requirement_id for d in db.query(Document).filter(
            Document.submission_id == submission_id,
            Document.requirement_id.isnot(None),
            Document.status == "processed"
        ).all()
    }

    for req in requirements_data.get("requirements", []):
        req_id = req["requirement_id"]
        if req_id not in fulfilled_req_ids:
            # We have an unfulfilled required document
            # Missing critical component is a HIGH severity issue
            ui = UnderwritingIssue(
                submission_id=submission_id,
                consistency_check_id=None,
                issue_type="REQUIREMENT_NOT_MET",
                description=f"Required document missing: {req['name']}",
                status="open",
                details={
                    "source_rule": "Conditional Requirement Engine",
                    "triggering_field": None,
                    "sources": [],
                    "raw_values": [],
                    "normalized_values": [],
                    "comparison_result": "MISSING",
                    "display_category": "Requirement not met",
                    "summary": f"Required document missing: {req['name']}",
                    "reason": f"{req['name']} is required for this application based on the information provided.",
                    "severity": "HIGH",
                    "recommended_action": f"Request upload of {req['name']} from the applicant."
                }
            )
            issues.append(ui)

    db.add_all(issues)
    db.commit()
    return issues
