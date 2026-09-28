from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.core import Document as DocumentModel, ExtractedField, Submission, User
from app.services.document_service import ingest_document, DocumentValidationError

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
    file_path: str
    status: str
    model_config = {"from_attributes": True}


@router.post("/upload")
async def upload_document(
    submission_id: int = Form(...),
    requirement_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document for a submission and run the extraction pipeline.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

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

    return result


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    sub = db.query(Submission).filter(Submission.id == doc.submission_id).first()
    if current_user.role != "underwriter" and (not sub or sub.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    return doc


@router.get("/{document_id}/fields", response_model=List[ExtractedFieldOut])
def get_extracted_fields(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    sub = db.query(Submission).filter(Submission.id == doc.submission_id).first()
    if current_user.role != "underwriter" and (not sub or sub.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    return db.query(ExtractedField).filter(ExtractedField.document_id == document_id).all()


@router.get("/submission/{submission_id}", response_model=List[DocumentOut])
def list_submission_documents(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role != "underwriter" and sub.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    return db.query(DocumentModel).filter(DocumentModel.submission_id == submission_id).all()
