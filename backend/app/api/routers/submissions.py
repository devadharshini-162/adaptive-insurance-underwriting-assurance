from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_user, get_current_underwriter, get_current_customer
from app.models.core import (
    Submission, User, Answer, ConsistencyCheck, UnderwritingIssue,
    Document, ExtractedField, Evidence, AuditRecord, InsuranceProduct, ApplicationProfile, AdditionalRequest
)
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.services.consistency_service import run_consistency_checks
from app.services.issue_mapper import generate_issues_for_submission
from app.services.engine import evaluate_requirements
from app.services.submission_lifecycle import (
    customer_submission_target,
    ensure_customer_can_edit,
    ensure_underwriter_transition,
)

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])

class SubmissionCreate(BaseModel):
    product_id: int

class SubmissionOut(BaseModel):
    id: int
    product_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class SubmissionListOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    applicant_name: str
    status: str
    created_at: datetime

class ApplicationProfileIn(BaseModel):
    company_name: Optional[str] = None
    business_type: Optional[str] = None
    industry: Optional[str] = None
    years_in_operation: Optional[int] = None
    business_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    annual_revenue: Optional[str] = None
    property_address: Optional[str] = None
    property_type: Optional[str] = None
    property_value: Optional[str] = None
    ownership_type: Optional[str] = None
    property_operations: Optional[str] = None
    employee_count: Optional[int] = None

class AdditionalRequestIn(BaseModel):
    request_type: str
    document_name: Optional[str] = None
    message: str
    note: Optional[str] = None

def profile_data(profile: ApplicationProfile | None) -> dict:
    if not profile:
        return {}
    return {field: getattr(profile, field) for field in ApplicationProfileIn.model_fields}

def owned_submission(submission_id: int, db: Session, current_user: User) -> Submission:
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return sub

def submission_list_item(submission: Submission) -> dict:
    return {
        "id": submission.id,
        "product_id": submission.product_id,
        "product_name": submission.product.name if submission.product else "Insurance application",
        "applicant_name": submission.user.name if submission.user else "Not available",
        "status": submission.status,
        "created_at": submission.created_at,
    }

@router.post("", response_model=SubmissionOut)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_customer)):
    """Create a new draft submission for a given product."""
    submission = Submission(user_id=current_user.id, product_id=payload.product_id, status="draft")
    db.add(submission)
    db.commit()
    db.refresh(submission)
    db.add(AuditRecord(submission_id=submission.id, action="submission_created", context_data={"actor_role": "customer"}))
    db.commit()
    return submission

@router.get("", response_model=List[SubmissionListOut])
def list_submissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    """List all submissions for the underwriter grid view."""
    submissions = db.query(Submission).order_by(Submission.created_at.desc()).all()
    return [submission_list_item(submission) for submission in submissions]

@router.get("/mine", response_model=List[SubmissionListOut])
def list_my_submissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_customer)):
    """List only submissions owned by the authenticated customer."""
    submissions = (
        db.query(Submission)
        .filter(Submission.user_id == current_user.id)
        .order_by(Submission.created_at.desc())
        .all()
    )
    return [submission_list_item(submission) for submission in submissions]

@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return owned_submission(submission_id, db, current_user)

@router.get("/{submission_id}/application")
def get_application(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = owned_submission(submission_id, db, current_user)
    answers = db.query(Answer).filter(Answer.submission_id == submission_id).all()
    requests = db.query(AdditionalRequest).filter(AdditionalRequest.submission_id == submission_id).order_by(AdditionalRequest.created_at.desc()).all()
    decision = db.query(AuditRecord).filter(AuditRecord.submission_id == submission_id, AuditRecord.action.in_(["status_change_to_approved", "status_change_to_declined"])).order_by(AuditRecord.timestamp.desc()).first()
    return {"submission": {"id": sub.id, "product_id": sub.product_id, "status": sub.status},
            "profile": profile_data(sub.application_profile),
            "answers": {str(answer.question_id): answer.value for answer in answers},
            "decision_message": (decision.context_data or {}).get("note") if decision else None,
            "requests": [{"id": r.id, "type": r.request_type, "document_name": r.document_name, "message": r.message, "note": r.note, "status": r.status} for r in requests]}

@router.post("/{submission_id}/requests")
def create_additional_request(submission_id: int, payload: AdditionalRequestIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if payload.request_type not in {"information", "document"} or not payload.message.strip() or (payload.request_type == "document" and not (payload.document_name or "").strip()):
        raise HTTPException(status_code=422, detail="Provide a request type, message, and document name when requesting a document.")
    ensure_underwriter_transition(sub.status, "info_requested")
    request = AdditionalRequest(submission_id=submission_id, request_type=payload.request_type, document_name=payload.document_name, message=payload.message, note=payload.note)
    sub.status = "info_requested"; db.add(request)
    db.add(AuditRecord(submission_id=submission_id, action=f"additional_{payload.request_type}_requested", context_data={"actor_role": "underwriter", "message": payload.message, "document_name": payload.document_name, "note": payload.note}))
    db.commit()
    return {"status": "ok"}

@router.put("/{submission_id}/application")
def save_application_profile(submission_id: int, payload: ApplicationProfileIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_customer)):
    sub = owned_submission(submission_id, db, current_user)
    ensure_customer_can_edit(sub.status)
    profile = sub.application_profile or ApplicationProfile(submission_id=submission_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile_data(profile)

@router.put("/{submission_id}/answers")
def save_answers(submission_id: int, payload: Dict[str, str], db: Session = Depends(get_db), current_user: User = Depends(get_current_customer)):
    sub = owned_submission(submission_id, db, current_user)
    ensure_customer_can_edit(sub.status)
    
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
    if current_user.role == "customer":
        target_status = customer_submission_target(sub.status)
    else:
        target_status = None
        
    try:
        run_consistency_checks(db, submission_id)
        issues = generate_issues_for_submission(db, submission_id)
        if target_status:
            previous_status = sub.status
            sub.status = target_status
            if previous_status == "info_requested":
                db.add(AuditRecord(submission_id=submission_id, action="submission_resubmitted", context_data={"actor_role": "customer"}))
            db.add(AuditRecord(
                submission_id=submission_id,
                action=f"status_change_to_{target_status}",
                context_data={"from_status": previous_status, "to_status": target_status, "actor_role": "customer"},
            ))
            db.commit()
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
    answers_list = [{"label": a.question.text if a.question else "Application response", "value": a.value} for a in answers]

    # Documents + extracted fields
    docs = db.query(Document).filter(Document.submission_id == submission_id).all()
    docs_list = []
    for d in docs:
        fields = db.query(ExtractedField).filter(ExtractedField.document_id == d.id).all()
        docs_list.append({
            "id": d.id,
            "requirement_id": d.requirement_id,
            "name": d.original_filename or "Uploaded document",
            "status": d.status,
            "content_url": f"/api/documents/{d.id}/content",
            "replaced": d.replaced_by_document_id is not None,
            "extracted_fields": [
                {"key": f.key, "label": {"annual_revenue": "Annual revenue", "property_value": "Property value", "hazardous_materials": "Hazardous materials", "risk_level": "Risk level", "insured_name": "Insured name"}.get(f.key, "Extracted information"), "value": f.normalized_value or f.raw_value,
                 "raw_value": f.raw_value, "normalized_value": f.normalized_value}
                for f in fields
            ]
        })

    # Consistency checks
    checks = db.query(ConsistencyCheck).filter(ConsistencyCheck.submission_id == submission_id).all()
    checks_list = [{"status": c.status, "details": c.details} for c in checks]

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
        reqs_data = evaluate_requirements(db, sub.product_id, ans_dict, profile_data(sub.application_profile))
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
    requests_list = [{"id": r.id, "type": r.request_type, "document_name": r.document_name, "message": r.message, "note": r.note, "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None} for r in db.query(AdditionalRequest).filter(AdditionalRequest.submission_id == submission_id).all()]

    return {
        "submission": {
            "id": sub.id,
            "product_id": sub.product_id,
            "product_name": product.name if product else "Unknown",
            "applicant": user.name if user else "Unknown",
            "status": sub.status,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
        },
        "application_profile": profile_data(sub.application_profile),
        "answers": answers_list,
        "documents": docs_list,
        "consistency_checks": checks_list,
        "issues": issues_list,
        "severity_counts": severity_counts,
        "requirements": reqs_list,
        "audit_trail": audits_list,
        "additional_requests": requests_list,
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
    status: str  # "info_requested", "approved", "declined"
    note: Optional[str] = None

@router.put("/{submission_id}/status")
def update_submission_status(submission_id: int, payload: StatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_underwriter)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    ensure_underwriter_transition(sub.status, payload.status)

    previous_status = sub.status
    sub.status = payload.status
    
    audit = AuditRecord(
        submission_id=submission_id,
        action=f"status_change_to_{payload.status}",
        context_data={"from_status": previous_status, "to_status": payload.status, "actor_role": "underwriter", "note": payload.note}
    )
    db.add(audit)
    db.commit()
    return {"status": "ok", "submission_status": sub.status}
