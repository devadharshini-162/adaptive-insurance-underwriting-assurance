from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import get_current_customer
from app.models.core import InsuranceCompany, InsuranceProduct, Question, User
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/products", tags=["Products"])

class ProductOut(BaseModel):
    id: int
    name: str
    description: str

    model_config = {"from_attributes": True}

class QuestionOut(BaseModel):
    id: int
    text: str
    field_type: str
    is_required: bool

    model_config = {"from_attributes": True}

class InsuranceCompanyOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_demo: bool

    model_config = {"from_attributes": True}

class UnderwriterOut(BaseModel):
    id: int
    name: str
    company_id: int
    company_name: str
    role_title: str | None = None
    supported_product_ids: List[int] = []
    specialization: str | None = None
    years_experience: int | None = None
    availability_status: str | None = None
    professional_description: str | None = None

@router.get("", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(InsuranceProduct).all()

@router.get("/companies", response_model=List[InsuranceCompanyOut])
def list_companies(db: Session = Depends(get_db), current_user=Depends(get_current_customer)):
    """List clearly-labelled demonstration insurers available for a new application."""
    return db.query(InsuranceCompany).order_by(InsuranceCompany.name).all()

@router.get("/underwriters", response_model=List[UnderwriterOut])
def list_underwriters(company_id: int, product_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_customer)):
    if not db.query(InsuranceCompany).filter(InsuranceCompany.id == company_id).first():
        raise HTTPException(status_code=404, detail="Insurance company not found")
    result = []
    for underwriter in db.query(User).filter(User.role == "underwriter", User.insurance_company_id == company_id).order_by(User.name).all():
        supported = underwriter.supported_product_ids or []
        if product_id not in supported or underwriter.availability_status != "available":
            continue
        result.append({
            "id": underwriter.id, "name": underwriter.name, "company_id": company_id,
            "company_name": underwriter.insurance_company.name if underwriter.insurance_company else "Insurance company",
            "role_title": underwriter.job_title, "supported_product_ids": supported,
            "specialization": underwriter.specialization, "years_experience": underwriter.years_experience,
            "availability_status": underwriter.availability_status,
            "professional_description": underwriter.professional_description,
        })
    return result

@router.get("/{product_id}/questions", response_model=List[QuestionOut])
def get_product_questions(product_id: int, db: Session = Depends(get_db)):
    return db.query(Question).filter(Question.product_id == product_id).all()
