from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps import get_current_user, get_current_customer
from app.models.core import Document as DocumentModel, ExtractedField, Submission, User, AuditRecord, AdditionalRequest
from app.services.document_service import ingest_document, DocumentValidationError
from app.services.submission_lifecycle import ensure_customer_can_edit

router = APIRouter(prefix="/api/documents", tags=["Documents"])


class ExtractedFieldOut(BaseModel):
    id: int
    key: str
    raw_value: str
    normalized_value: Optional[str]
    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    submission_id: int
    requirement_id: Optional[int]
    name: str
    status: str
    replaced: bool = False
    model_config = {"from_attributes": True}

def check_document_access(doc: DocumentModel, db: Session, current_user: User) -> Submission:
    sub = db.query(Submission).filter(Submission.id == doc.submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return sub

def document_out(doc: DocumentModel) -> dict:
    return {"id": doc.id, "submission_id": doc.submission_id, "requirement_id": doc.requirement_id,
            "name": doc.original_filename or Path(doc.file_path).name, "status": doc.status,
            "replaced": doc.replaced_by_document_id is not None}


@router.post("/upload")
async def upload_document(
    submission_id: int = Form(...),
    requirement_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_customer),
):
    """
    Upload a document for a submission and run the extraction pipeline.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    ensure_customer_can_edit(sub.status)

    # Read file bytes to determine size
    file_bytes = await file.read()
    file_size = len(file_bytes)

    import io
    file_obj = io.BytesIO(file_bytes)

    try:
        result = ingest_document(
            db=db,
            submission_id=submission_id,
            requirement_id=requirement_id,
            file_obj=file_obj,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
        )
    except DocumentValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    db.add(AuditRecord(submission_id=submission_id, action="document_uploaded",
                       context_data={"document_name": Path(file.filename or "document").name, "actor_role": current_user.role}))
    db.commit()
    return result

@router.post("/requested/{submission_id}/{request_id}")
async def upload_requested_document(submission_id: int, request_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_customer)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    request = db.query(AdditionalRequest).filter(AdditionalRequest.id == request_id, AdditionalRequest.submission_id == submission_id, AdditionalRequest.request_type == "document", AdditionalRequest.status == "open").first()
    if not sub or not request:
        raise HTTPException(status_code=404, detail="Requested document not found")
    if sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    ensure_customer_can_edit(sub.status)
    contents = await file.read()
    try:
        result = ingest_document(db, submission_id, None, __import__("io").BytesIO(contents), file.filename or request.document_name or "document", file.content_type or "application/octet-stream", len(contents))
    except DocumentValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    request.status = "satisfied"; request.response_document_id = result["document_id"]
    db.add(AuditRecord(submission_id=submission_id, action="requested_document_uploaded", context_data={"actor_role": "customer", "document_name": request.document_name}))
    db.commit()
    return result


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    check_document_access(doc, db, current_user)
    return document_out(doc)


@router.get("/{document_id}/fields", response_model=List[ExtractedFieldOut])
def get_extracted_fields(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    check_document_access(doc, db, current_user)
    return db.query(ExtractedField).filter(ExtractedField.document_id == document_id).all()

@router.get("/{document_id}/content")
def view_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    check_document_access(doc, db, current_user)
    path = Path(doc.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document file is unavailable")
    return FileResponse(path, filename=doc.original_filename or path.name)

@router.post("/{document_id}/replace")
async def replace_document(
    document_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: User = Depends(get_current_customer),
):
    old = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Document not found")
    sub = check_document_access(old, db, current_user)
    ensure_customer_can_edit(sub.status)
    file_bytes = await file.read()
    try:
        result = ingest_document(db, sub.id, old.requirement_id, __import__("io").BytesIO(file_bytes),
                                 file.filename or "replacement", file.content_type or "application/octet-stream", len(file_bytes))
    except DocumentValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    old.replaced_by_document_id = result["document_id"]
    old.status = "replaced"
    db.add(AuditRecord(submission_id=sub.id, action="document_replaced",
                       context_data={"document_name": old.original_filename or "document", "actor_role": "customer"}))
    db.commit()
    return result


@router.get("/submission/{submission_id}", response_model=List[DocumentOut])
def list_submission_documents(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return [document_out(doc) for doc in db.query(DocumentModel).filter(DocumentModel.submission_id == submission_id).all()]
