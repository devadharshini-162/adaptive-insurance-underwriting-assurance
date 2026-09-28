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
        
        # Determine Severity based on rule-driven configuration
        severity = "MEDIUM"
        if c_key in CRITICAL_FIELDS:
            severity = "HIGH"
            
        if check.status == "NOT_COMPARABLE":
            # Only elevate to an issue if it is a critical field that requires verification
            if c_key in CRITICAL_FIELDS:
                severity = "MEDIUM"
                action = f"Review unparseable values for {c_key}."
            else:
                # Informational for non-critical NOT_COMPARABLE
                severity = "LOW"
                action = f"Verify {c_key} manually during manual review."
        else: # CONFLICT
            action = f"Clarify discrepancies in {c_key} between application and documents."
            if severity == "HIGH":
                action = f"Resolve critical discrepancy in {c_key} before proceeding."

        ui = UnderwritingIssue(
            submission_id=submission_id,
            consistency_check_id=check.id,
            issue_type="DISCREPANCY",
            description=f"Discrepancy detected in {c_key}: {check.details.get('reason')}",
            status="open",
            details={
                "source_rule": f"Consistency check for {c_key}",
                "triggering_field": c_key,
                "sources": [v.get("source") for v in check.details.get("values", [])],
                "raw_values": [v.get("raw_value") for v in check.details.get("values", [])],
                "normalized_values": [v.get("norm_value") for v in check.details.get("values", [])],
                "comparison_result": check.status,
                "reason": check.details.get("reason"),
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
                issue_type="MISSING_EVIDENCE",
                description=f"Missing required document: {req['name']}",
                status="open",
                details={
                    "source_rule": "Conditional Requirement Engine",
                    "triggering_field": None,
                    "sources": [],
                    "raw_values": [],
                    "normalized_values": [],
                    "comparison_result": "MISSING",
                    "reason": f"System determined {req['name']} is required based on submitted answers.",
                    "severity": "HIGH",
                    "recommended_action": f"Request upload of {req['name']} from the applicant."
                }
            )
            issues.append(ui)

    db.add_all(issues)
    db.commit()
    return issues
