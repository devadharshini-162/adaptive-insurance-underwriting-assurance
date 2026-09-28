from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user, get_current_underwriter
from app.models.core import (
    Submission, User, Answer, ConsistencyCheck, UnderwritingIssue,
    Document, ExtractedField, Evidence, AuditRecord, InsuranceProduct
)
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.services.consistency_service import run_consistency_checks
from app.services.issue_mapper import generate_issues_for_submission
from app.services.engine import evaluate_requirements

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])

class SubmissionCreate(BaseModel):
    product_id: int

class SubmissionOut(BaseModel):
    id: int
    product_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

@router.post("", response_model=SubmissionOut)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new draft submission for a given product."""
    submission = Submission(user_id=current_user.id, product_id=payload.product_id, status="draft")
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission

@router.get("", response_model=List[SubmissionOut])
def list_submissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    """List all submissions for the underwriter grid view."""
    return db.query(Submission).order_by(Submission.created_at.desc()).all()

@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return sub

@router.put("/{submission_id}/answers")
def save_answers(submission_id: int, payload: Dict[str, str], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db.query(Answer).filter(Answer.submission_id == submission_id).delete()
    
    for q_id_str, val in payload.items():
        try:
            q_id = int(q_id_str)
        except ValueError:
            continue
        ans = Answer(submission_id=submission_id, question_id=q_id, value=val)
        db.add(ans)
        
    db.commit()
    return {"status": "ok", "saved_count": len(payload)}

@router.post("/{submission_id}/consistency/run")
def run_consistency(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    try:
        checks = run_consistency_checks(db, submission_id)
        return {"status": "ok", "checks_run": len(checks)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{submission_id}/consistency")
def get_consistency(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    checks = db.query(ConsistencyCheck).filter(ConsistencyCheck.submission_id == submission_id).all()
    result = []
    for c in checks:
        result.append({
            "id": c.id,
            "status": c.status,
            "details": c.details
        })
    return {"consistency_checks": result}

@router.post("/{submission_id}/issues/generate")
def generate_issues(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    try:
        run_consistency_checks(db, submission_id)
        issues = generate_issues_for_submission(db, submission_id)
        return {"status": "ok", "issues_generated": len(issues)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{submission_id}/issues")
def get_issues(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    issues = db.query(UnderwritingIssue).filter(UnderwritingIssue.submission_id == submission_id).all()
    result = []
    for i in issues:
        result.append({
            "id": i.id,
            "issue_type": i.issue_type,
            "description": i.description,
            "status": i.status,
            "details": i.details
        })
    return {"issues": result}

# ── Phase 9: Dashboard endpoints ─────────────────────────────────────────────

@router.get("/{submission_id}/dashboard")
def get_dashboard_summary(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    """Full dashboard payload for the underwriter detail view."""
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    product = db.query(InsuranceProduct).filter(InsuranceProduct.id == sub.product_id).first()
    user = db.query(User).filter(User.id == sub.user_id).first()

    # Answers
    answers = db.query(Answer).filter(Answer.submission_id == submission_id).all()
    answers_list = [{"question_id": a.question_id, "value": a.value} for a in answers]

    # Documents + extracted fields
    docs = db.query(Document).filter(Document.submission_id == submission_id).all()
    docs_list = []
    for d in docs:
        fields = db.query(ExtractedField).filter(ExtractedField.document_id == d.id).all()
        docs_list.append({
            "id": d.id,
            "requirement_id": d.requirement_id,
            "file_path": d.file_path,
            "status": d.status,
            "extracted_fields": [
                {"id": f.id, "key": f.key, "raw_value": f.raw_value, "normalized_value": f.normalized_value}
                for f in fields
            ]
        })

    # Consistency checks
    checks = db.query(ConsistencyCheck).filter(ConsistencyCheck.submission_id == submission_id).all()
    checks_list = [{"id": c.id, "status": c.status, "details": c.details} for c in checks]

    # Issues
    issues = db.query(UnderwritingIssue).filter(UnderwritingIssue.submission_id == submission_id).all()
    issues_list = [
        {"id": i.id, "issue_type": i.issue_type, "description": i.description,
         "status": i.status, "details": i.details}
        for i in issues
    ]

    # Issue severity counts
    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for i in issues:
        sev = (i.details or {}).get("severity", "LOW")
        if sev in severity_counts:
            severity_counts[sev] += 1

    # Requirements evaluation
    ans_dict = {str(a.question_id): a.value for a in answers}
    try:
        reqs_data = evaluate_requirements(db, sub.product_id, ans_dict)
    except Exception:
        reqs_data = {"requirements": []}

    # Enrich requirements with fulfillment status
    fulfilled_req_ids = {d.requirement_id for d in docs if d.requirement_id and d.status == "processed"}
    reqs_list = []
    for r in reqs_data.get("requirements", []):
        rid = r["requirement_id"]
        reqs_list.append({
            **r,
            "fulfilled": rid in fulfilled_req_ids,
        })

    # Audit trail
    audits = db.query(AuditRecord).filter(
        AuditRecord.submission_id == submission_id
    ).order_by(AuditRecord.timestamp.desc()).all()
    audits_list = [
        {"id": a.id, "action": a.action, "context_data": a.context_data,
         "timestamp": a.timestamp.isoformat() if a.timestamp else None}
        for a in audits
    ]

    return {
        "submission": {
            "id": sub.id,
            "product_id": sub.product_id,
            "product_name": product.name if product else "Unknown",
            "applicant": user.name if user else "Unknown",
            "status": sub.status,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
        },
        "answers": answers_list,
        "documents": docs_list,
        "consistency_checks": checks_list,
        "issues": issues_list,
        "severity_counts": severity_counts,
        "requirements": reqs_list,
        "audit_trail": audits_list,
    }


class IssueAction(BaseModel):
    action: str  # "resolve", "dismiss", "reopen"
    note: Optional[str] = None

@router.put("/{submission_id}/issues/{issue_id}")
def update_issue(submission_id: int, issue_id: int, payload: IssueAction, db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    issue = db.query(UnderwritingIssue).filter(
        UnderwritingIssue.id == issue_id,
        UnderwritingIssue.submission_id == submission_id
    ).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    action_map = {"resolve": "resolved", "dismiss": "dismissed", "reopen": "open"}
    new_status = action_map.get(payload.action)
    if not new_status:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")

    issue.status = new_status
    
    audit = AuditRecord(
        submission_id=submission_id,
        action=f"issue_{payload.action}",
        context_data={"issue_id": issue_id, "issue_type": issue.issue_type, "note": payload.note}
    )
    db.add(audit)
    db.commit()
    return {"status": "ok", "issue_status": new_status}


class StatusUpdate(BaseModel):
    status: str  # "under_review", "approved", "declined", "info_requested"
    note: Optional[str] = None

@router.put("/{submission_id}/status")
def update_submission_status(submission_id: int, payload: StatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    valid_statuses = {"draft", "under_review", "approved", "declined", "info_requested"}
    if payload.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    sub.status = payload.status
    
    audit = AuditRecord(
        submission_id=submission_id,
        action=f"status_change_to_{payload.status}",
        context_data={"note": payload.note}
    )
    db.add(audit)
    db.commit()
    return {"status": "ok", "submission_status": sub.status}
