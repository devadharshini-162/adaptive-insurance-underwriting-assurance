from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.engine_schemas import EvaluateRequest, EvaluateResponse
from app.api.deps import get_current_user
from app.models.core import User
from app.services.engine import evaluate_requirements

router = APIRouter(prefix="/api/engine", tags=["Rule Engine"])

@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_submission_state(req: EvaluateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Evaluates current answers for an insurance product and returns the required
    questions and dynamic document requirements along with explanations.
    """
    result = evaluate_requirements(db, req.product_id, req.current_answers, req.context_data)
    return result
