"""
Consistency Engine (Phase 7)
============================
Compares canonical evidence from various sources (Answers, Documents)
and flags discrepancies.
"""

from typing import Any, Dict, List
from sqlalchemy.orm import Session
from ..models.core import Answer, Evidence, ConsistencyCheck, Submission, ExtractedField, UnderwritingIssue
from .normalization import normalize_answers, NormalizedValue

CONSISTENT = "CONSISTENT"
CONFLICT = "CONFLICT"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
NOT_COMPARABLE = "NOT_COMPARABLE"

# Tolerances for numeric fields (proportional difference allowed).
# e.g. 0.05 means documents can vary by +/- 5% from each other and still match.
TOLERANCE_MAP = {
    "annual_revenue": 0.05,
    "property_value": 0.05,
}

def compare_values(canon_key: str, nv1: NormalizedValue, nv2: NormalizedValue) -> tuple[str, str]:
    """
    Returns (status, reason) comparing two NormalizedValues.
    """
    if not nv1.ok or not nv2.ok:
        return NOT_COMPARABLE, "One or more values failed standard normalization."
    
    if nv1.data_type != nv2.data_type:
        return NOT_COMPARABLE, f"Mismatched data types ({nv1.data_type} vs {nv2.data_type})."

    val1, val2 = nv1.norm_value, nv2.norm_value

    if val1 == val2:
        return CONSISTENT, "Values match exactly."

    if nv1.data_type == "number":
        try:
            num1 = float(val1)
            num2 = float(val2)
        except ValueError:
            return NOT_COMPARABLE, "Numeric values could not be parsed to floats."

        # Exact match failed, check tolerance
        tol = TOLERANCE_MAP.get(canon_key, 0.0) # Default 0 tolerance for unknown numbers
        
        if tol > 0:
            if num1 == 0 and num2 == 0:
                return CONSISTENT, "Values match exactly (zero)."
            # Tolerance is typically calculated against the max value to be safe, 
            # but simple diff / max is standard
            diff = abs(num1 - num2)
            max_val = max(abs(num1), abs(num2))
            if max_val == 0:
                return CONSISTENT, "Values match exactly."
                
            if diff / max_val <= tol:
                return CONSISTENT, f"Values match within {tol*100}% tolerance."
            else:
                return CONFLICT, f"Numeric discrepancy exceeds {tol*100}% tolerance."
        else:
            return CONFLICT, "Values conflict and no tolerance is permitted."

    # For text, boolean, date, etc (exact match required)
    return CONFLICT, "Values strongly conflict."


def run_consistency_checks(db: Session, submission_id: int) -> List[ConsistencyCheck]:
    """
    Groups all evidence by canonical key and compares them combinatorially.
    Creates or replaces ConsistencyCheck records for the submission.
    """
    sub = db.query(Submission).filter(Submission.id == submission_id).first()
    if not sub:
        raise ValueError(f"Submission {submission_id} not found.")

    # 1. Clear existing consistency checks for a fresh run.  Issues reference
    # checks for traceability, so detach them before the checks are replaced;
    # the issue mapper subsequently recreates the current issue set.
    db.query(UnderwritingIssue).filter(
        UnderwritingIssue.submission_id == submission_id,
        UnderwritingIssue.consistency_check_id.isnot(None),
    ).update({UnderwritingIssue.consistency_check_id: None}, synchronize_session=False)
    db.query(ConsistencyCheck).filter(ConsistencyCheck.submission_id == submission_id).delete()

    # 2. Extract Answers -> NormalizedValues
    answers = db.query(Answer).filter(Answer.submission_id == submission_id).all()
    ans_dict = {str(a.question_id): a.value for a in answers}
    answer_norms = normalize_answers(ans_dict)  # Returns dict[canonical_key, NormalizedValue]

    # 3. Extract Document Evidences -> NormalizedValues
    # Join Evidence with ExtractedField
    evidences = (
        db.query(Evidence, ExtractedField)
        .join(ExtractedField, Evidence.extracted_field_id == ExtractedField.id)
        .filter(Evidence.submission_id == submission_id)
        .all()
    )
    
    # 4. Group by canonical key
    # grouping: dict[canonical_key, list[NormalizedValue]]
    grouped: Dict[str, List[NormalizedValue]] = {}
    
    # Add answers
    for c_key, nv in answer_norms.items():
        if nv.ok: # If we can't normalize an answer, maybe skip or record as NOT_COMPARABLE? Let's keep it.
            grouped.setdefault(c_key, []).append(nv)
    
    # Add doc fields
    for ev_record, ef_record in evidences:
        c_key = ev_record.canonical_key
        # We manually construct a NormalizedValue since normalization happens at doc ingest,
        # but to be uniform, we can re-wrap or just use the ExtractedField data
        # Actually, ExtractedField has raw_value and normalized_value. 
        # But data_type and ok/error status are computed by normalize_value.
        # It's safest to re-run normalize_value to get the rich object.
        from .normalization import normalize_value
        nv = normalize_value(c_key, ef_record.raw_value, source=f"document_{ef_record.document_id}")
        grouped.setdefault(c_key, []).append(nv)

    checks_to_insert = []

    # 5. Compare within groups
    for c_key, nvs in grouped.items():
        if len(nvs) < 2:
            checks_to_insert.append(
                ConsistencyCheck(
                    submission_id=submission_id,
                    status=INSUFFICIENT_EVIDENCE,
                    details={
                        "canonical_key": c_key,
                        "reason": "Only one source of evidence found; nothing to compare.",
                        "values": [nv.to_dict() for nv in nvs]
                    }
                )
            )
            continue
        
        # Compare all pairs (e.g. if 3 sources, A<>B, B<>C, A<>C)
        # If ANY pair conflicts, the group is flagged as CONFLICT
        # If ALL pairs are CONSISTENT, it's CONSISTENT
        # If any pair is NOT_COMPARABLE, and no conflicts, it's NOT_COMPARABLE
        group_status = CONSISTENT
        reasons = []

        for i in range(len(nvs)):
            for j in range(i + 1, len(nvs)):
                nv1, nv2 = nvs[i], nvs[j]
                pair_status, reason = compare_values(c_key, nv1, nv2)
                
                if pair_status == CONFLICT:
                    group_status = CONFLICT
                    reasons.append(f"{nv1.source} vs {nv2.source}: {reason}")
                elif pair_status == NOT_COMPARABLE and group_status == CONSISTENT:
                    group_status = NOT_COMPARABLE
                    reasons.append(f"{nv1.source} vs {nv2.source}: {reason}")

        if group_status == CONSISTENT:
            reasons = ["All evidence sources align."]
            
        checks_to_insert.append(
            ConsistencyCheck(
                submission_id=submission_id,
                status=group_status,
                details={
                    "canonical_key": c_key,
                    "reason": " | ".join(reasons),
                    "values": [nv.to_dict() for nv in nvs],
                    "tolerance_used": TOLERANCE_MAP.get(c_key)
                }
            )
        )

    for c in checks_to_insert:
        db.add(c)
        
    db.commit()
    return checks_to_insert
