from pydantic import BaseModel
from typing import Dict, Any, List

class EvaluateRequest(BaseModel):
    product_id: int
    current_answers: Dict[str, str]

class QuestionView(BaseModel):
    id: int
    text: str
    field_type: str
    is_required: bool

class RequirementView(BaseModel):
    requirement_id: int
    name: str
    explanation: str
    is_conditional: bool
    status: str

class EvaluateResponse(BaseModel):
    applicable_questions: List[QuestionView]
    requirements: List[RequirementView]
