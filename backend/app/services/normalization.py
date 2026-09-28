"""
Evidence Normalization Service  (Phase 6)
=========================================
Converts raw values from two sources into canonical, comparable forms:

  1. Questionnaire answers (user-entered, string)
  2. OCR-extracted document fields (from Phase 5 ExtractedField rows)

For each canonical key we produce a NormalizedValue:
  - raw_value  : the original string verbatim
  - norm_value : the canonical representation (may equal raw if unambiguous)
  - data_type  : "number" | "boolean" | "text" | "date" | "email" | "phone" | "address"
  - source     : "answer" | "document"
  - error      : None, or a human-readable reason if normalisation failed/ambiguous

Supported canonical keys (extensible):
  annual_revenue, property_value   → INR integer (paisa-free integer string)
  hazardous_materials              → "yes" | "no"
  risk_level                       → "low" | "medium" | "high"
  insured_name                     → Title-cased string
  business_entity_type             → lowercased text
  inspection_date / policy_date    → ISO-8601 date string YYYY-MM-DD
  contact_email                    → lowercase email
  contact_phone                    → E.164-style digits  (no country code assumed)
  address                          → stripped / title-cased single-line

Unrecognised keys are handled generically (text normalisation only).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class NormalizedValue:
    raw_value: str
    norm_value: str
    data_type: str          # number | boolean | text | date | email | phone | address
    source: str             # answer | document
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "raw_value": self.raw_value,
            "norm_value": self.norm_value,
            "data_type": self.data_type,
            "source": self.source,
            "error": self.error,
        }


# ── INR currency normalisation ────────────────────────────────────────────────

_CURRENCY_CLEANUP = re.compile(r"[₹$€£\s,]")
_UNIT_MAP = {
    "crore": 1_00_00_000,
    "cr":    1_00_00_000,
    "lakh":  1_00_000,
    "lac":   1_00_000,
    "l":     1_00_000,
    "thousand": 1_000,
    "k":     1_000,
    "million": 10_00_000,
    "mn":    10_00_000,
    "billion": 1_00_00_00_000,
}
_UNIT_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(" + "|".join(_UNIT_MAP.keys()) + r")?",
    re.IGNORECASE,
)


def _norm_currency(raw: str) -> tuple[str, Optional[str]]:
    """Return (normalised integer string, error_or_None)."""
    cleaned = _CURRENCY_CLEANUP.sub("", raw).strip().lower()
    # Remove currency prefixes: inr, rs.
    cleaned = re.sub(r"^(inr|rs\.?|₹)", "", cleaned).strip()

    m = _UNIT_RE.match(cleaned)
    if not m:
        return raw, f"Cannot parse currency value: '{raw}'"

    num_str = m.group(1).replace(",", "")
    unit    = (m.group(2) or "").lower()

    try:
        base = float(num_str)
    except ValueError:
        return raw, f"Non-numeric part in currency: '{raw}'"

    multiplier = _UNIT_MAP.get(unit, 1)
    result = int(base * multiplier)
    return str(result), None


# ── Boolean normalisation ─────────────────────────────────────────────────────

_YES_TOKENS = {"yes", "y", "true", "1", "present", "applicable", "checked"}
_NO_TOKENS  = {"no", "n", "false", "0", "absent", "none", "not applicable", "na", "n/a"}


def _norm_boolean(raw: str) -> tuple[str, Optional[str]]:
    v = raw.strip().lower()
    if v in _YES_TOKENS:
        return "yes", None
    if v in _NO_TOKENS:
        return "no", None
    return raw, f"Cannot interpret as yes/no: '{raw}'"


# ── Risk-level normalisation ──────────────────────────────────────────────────

_RISK_MAP = {
    "low":        "low",
    "l":          "low",
    "minimal":    "low",
    "negligible": "low",
    "minor":      "low",
    "medium":     "medium",
    "med":        "medium",
    "moderate":   "medium",
    "mod":        "medium",
    "high":       "high",
    "h":          "high",
    "severe":     "high",
    "critical":   "high",
    "extreme":    "high",
}


def _norm_risk(raw: str) -> tuple[str, Optional[str]]:
    v = raw.strip().lower()
    if v in _RISK_MAP:
        return _RISK_MAP[v], None
    return raw, f"Unrecognised risk level: '{raw}'. Expected low/medium/high."


# ── Date normalisation ────────────────────────────────────────────────────────

_DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%Y-%m-%d",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
    "%d/%m/%y", "%d-%m-%y",
]


def _norm_date(raw: str) -> tuple[str, Optional[str]]:
    v = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(v, fmt)
            return dt.strftime("%Y-%m-%d"), None
        except ValueError:
            continue
    return raw, f"Cannot parse date: '{raw}'. Expected formats: DD/MM/YYYY, YYYY-MM-DD, DD Mon YYYY…"


# ── Email normalisation ───────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _norm_email(raw: str) -> tuple[str, Optional[str]]:
    v = raw.strip().lower()
    if _EMAIL_RE.match(v):
        return v, None
    return raw, f"Invalid email address: '{raw}'"


# ── Phone normalisation ───────────────────────────────────────────────────────

def _norm_phone(raw: str) -> tuple[str, Optional[str]]:
    digits = re.sub(r"[^\d+]", "", raw)
    # Strip leading country codes like +91 for India to get 10-digit number
    digits_only = re.sub(r"^\+91", "", digits)
    digits_only = re.sub(r"^0", "", digits_only)
    if len(digits_only) == 10 and digits_only.isdigit():
        return digits_only, None
    if len(digits) >= 7:
        return digits, None
    return raw, f"Cannot normalise phone number: '{raw}'"


# ── Text / name normalisation ─────────────────────────────────────────────────

def _norm_text(raw: str) -> tuple[str, Optional[str]]:
    """Generic: strip whitespace, collapse internal spaces."""
    v = " ".join(raw.split())
    return v, None


def _norm_name(raw: str) -> tuple[str, Optional[str]]:
    v = " ".join(raw.split()).title()
    return v, None


def _norm_address(raw: str) -> tuple[str, Optional[str]]:
    # Collapse whitespace, title-case
    v = " ".join(raw.split()).title()
    return v, None


# ── Key → type mapping ────────────────────────────────────────────────────────

# Maps canonical key → (data_type, normaliser_function)
_KEY_TYPE: dict[str, tuple[str, callable]] = {
    "annual_revenue":       ("number",  _norm_currency),
    "property_value":       ("number",  _norm_currency),
    "hazardous_materials":  ("boolean", _norm_boolean),
    "risk_level":           ("text",    _norm_risk),
    "insured_name":         ("text",    _norm_name),
    "company_name":         ("text",    _norm_name),
    "business_entity_type": ("text",    lambda r: (" ".join(r.split()).lower(), None)),
    "inspection_date":      ("date",    _norm_date),
    "policy_date":          ("date",    _norm_date),
    "contact_email":        ("email",   _norm_email),
    "contact_phone":        ("phone",   _norm_phone),
    "address":              ("address", _norm_address),
}

_DEFAULT_TYPE = "text"
_DEFAULT_NORM = _norm_text


# ── Public API ────────────────────────────────────────────────────────────────

def normalize_value(key: str, raw: str, source: str = "answer") -> NormalizedValue:
    """
    Normalize a single value by canonical key.

    Parameters
    ----------
    key    : canonical field key (e.g. "annual_revenue")
    raw    : raw string value from answer or OCR extraction
    source : "answer" | "document"

    Returns
    -------
    NormalizedValue  – always returns an object, never raises.
    error field is set for ambiguous/invalid input instead of raising.
    """
    if not isinstance(raw, str):
        raw = str(raw)

    if not raw.strip():
        return NormalizedValue(
            raw_value=raw,
            norm_value="",
            data_type=_KEY_TYPE.get(key, (_DEFAULT_TYPE, None))[0],
            source=source,
            error=f"Empty value for key '{key}'",
        )

    data_type, fn = _KEY_TYPE.get(key, (_DEFAULT_TYPE, _DEFAULT_NORM))
    norm, error = fn(raw)

    return NormalizedValue(
        raw_value=raw,
        norm_value=norm,
        data_type=data_type,
        source=source,
        error=error,
    )


def normalize_answers(answers: dict[str, str]) -> dict[str, NormalizedValue]:
    """
    Normalize a dict of {question_id_str: raw_value} questionnaire answers.
    Questionnaire answer keys are question IDs; we map them to canonical keys
    only for known fields. Unknown IDs are normalised as generic text.
    """
    # Map question_id → canonical_key for seeded Commercial Property product
    # (extend when more products are added)
    QUESTION_KEY_MAP: dict[str, str] = {
        "1": "business_entity_type",
        "2": "annual_revenue",
        "3": "hazardous_materials",
        "4": "property_value",
        "5": "risk_level",
    }
    out: dict[str, NormalizedValue] = {}
    for qid, raw in answers.items():
        canon_key = QUESTION_KEY_MAP.get(str(qid), f"question_{qid}")
        out[canon_key] = normalize_value(canon_key, raw, source="answer")
    return out


def normalize_extracted_fields(
    fields: dict[str, str],
) -> dict[str, NormalizedValue]:
    """
    Normalize a dict of {canonical_key: raw_value} from document extraction.
    """
    return {
        key: normalize_value(key, raw, source="document")
        for key, raw in fields.items()
    }
