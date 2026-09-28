"""Submission lifecycle rules shared by customer and underwriting endpoints."""

from fastapi import HTTPException

DRAFT = "draft"
UNDER_REVIEW = "under_review"
INFO_REQUESTED = "info_requested"
APPROVED = "approved"
DECLINED = "declined"

CUSTOMER_EDITABLE_STATES = {DRAFT, INFO_REQUESTED}
CUSTOMER_SUBMIT_TRANSITIONS = {
    DRAFT: UNDER_REVIEW,
    INFO_REQUESTED: UNDER_REVIEW,
}
UNDERWRITER_TRANSITIONS = {
    UNDER_REVIEW: {INFO_REQUESTED, APPROVED, DECLINED},
}


def ensure_customer_can_edit(status: str) -> None:
    if status not in CUSTOMER_EDITABLE_STATES:
        raise HTTPException(
            status_code=409,
            detail="This application cannot be changed in its current status.",
        )


def customer_submission_target(status: str) -> str:
    target = CUSTOMER_SUBMIT_TRANSITIONS.get(status)
    if target is None:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit an application from status '{status}'.",
        )
    return target


def ensure_underwriter_transition(current_status: str, target_status: str) -> None:
    allowed_targets = UNDERWRITER_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        allowed_text = ", ".join(sorted(allowed_targets)) or "none"
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot change an application from '{current_status}' to "
                f"'{target_status}'. Allowed transitions: {allowed_text}."
            ),
        )
