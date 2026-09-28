import operator

def evaluate_condition(node, answers_dict):
    """
    Evaluates a single rule node recursively against the provided answers map.
    Answers map should map question_id (as string) to the string value provided.
    Missing answers and invalid types return False to safely fail conditions.
    """
    # 1. Group Node
    if "conditions" in node:
        op = node.get("operator", "AND").upper()
        results = [evaluate_condition(cond, answers_dict) for cond in node.get("conditions", [])]
        if op == "AND":
            return all(results)
        elif op == "OR":
            return any(results)
        return False
        
    # 2. Leaf Node
    question_id = str(node.get("question_id"))
    op_str = node.get("operator", "==")
    target_val = node.get("value")
    
    # Missing answer yields False implicitly
    if question_id not in answers_dict:
        return False
        
    actual_val = answers_dict[question_id]
    
    # Try parsing both as floats if numeric comparison is implied
    # Fallback to string comparison if parsing fails
    def coerce_types(actual, target):
        try:
            return float(actual), float(target)
        except (ValueError, TypeError):
            return str(actual), str(target)
            
    a, t = coerce_types(actual_val, target_val)
    
    ops = {
        "==": operator.eq,
        "!=": operator.ne,
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le
    }
    
    fn = ops.get(op_str)
    if not fn:
        return False
        
    try:
        return fn(a, t)
    except TypeError:
        return False

def evaluate_requirements(db_session, product_id: int, current_answers_dict: dict):
    from app.models.core import Requirement, Question
    
    # Fetch all questions and requirements for this product
    questions = db_session.query(Question).filter(Question.product_id == product_id).all()
    requirements = db_session.query(Requirement).filter(Requirement.product_id == product_id).all()
    
    applicable_questions = [
        {"id": q.id, "text": q.text, "field_type": q.field_type, "is_required": q.is_required}
        for q in questions
    ]
    
    triggered_reqs = []
    
    for req in requirements:
        if req.rule_logic is None:
            # Unconditional requirement
            triggered_reqs.append({
                "requirement_id": req.id,
                "name": req.name,
                "explanation": req.description or "This is a standard mandatory requirement.",
                "is_conditional": False,
                "status": "missing" # Simplification: assumes missing until docs matched
            })
        else:
            # Conditional requirement
            is_triggered = evaluate_condition(req.rule_logic, current_answers_dict)
            if is_triggered:
                explanation = req.rule_logic.get("explanation", "Requirement activated based on provided answers.")
                triggered_reqs.append({
                    "requirement_id": req.id,
                    "name": req.name,
                    "explanation": explanation,
                    "is_conditional": True,
                    "status": "missing"
                })
                
    return {
        "applicable_questions": applicable_questions,
        "requirements": triggered_reqs
    }
