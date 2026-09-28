from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.core import InsuranceProduct, Question
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

@router.get("", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(InsuranceProduct).all()

@router.get("/{product_id}/questions", response_model=List[QuestionOut])
def get_product_questions(product_id: int, db: Session = Depends(get_db)):
    return db.query(Question).filter(Question.product_id == product_id).all()
