"""
Document ingestion service.
Pipeline:
  1. Validate file (type, size)
  2. Save to secure local storage
  3. Extract text (embedded PDF text, then Tesseract OCR for images/scanned PDFs)
  4. Extract canonical insurance fields deterministically
  5. Normalize values
  6. Persist ExtractedField records
"""
import os
import re
import uuid
import shutil
from pathlib import Path
from typing import IO

import fitz          # PyMuPDF
import pytesseract
from PIL import Image

from app.db.database import SessionLocal
from app.models.core import Document as DocumentModel, ExtractedField, Evidence
from app.services.normalization import normalize_value

# ── Configuration ────────────────────────────────────────────────────────────

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(Path(__file__).parents[3] / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/bmp",
}

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp"}

# ── Validation ───────────────────────────────────────────────────────────────

class DocumentValidationError(Exception):
    pass

def validate_upload(filename: str, content_type: str, file_size: int):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if content_type not in ALLOWED_MIME_TYPES:
        raise DocumentValidationError(
            f"Unsupported content type '{content_type}'."
        )
    if file_size > MAX_SIZE_BYTES:
        raise DocumentValidationError(
            f"File exceeds maximum allowed size of {MAX_SIZE_BYTES // (1024*1024)} MB."
        )

# ── Storage ──────────────────────────────────────────────────────────────────

def save_file(file_obj: IO[bytes], original_filename: str) -> Path:
    ext = Path(original_filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / unique_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file_obj, f)
    return dest

# ── Text Extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(path: Path) -> str:
    """Extract embedded text from a PDF page-by-page; fall back to Tesseract for image-only pages."""
    doc = fitz.open(str(path))
    all_text = []
    for page in doc:
        page_text = page.get_text("text").strip()
        if page_text:
            all_text.append(page_text)
        else:
            # Image-only page → render and OCR
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
            if ocr_text:
                all_text.append(ocr_text)
    doc.close()
    return "\n".join(all_text)


def extract_text_from_image(path: Path) -> str:
    img = Image.open(str(path))
    return pytesseract.image_to_string(img, lang="eng").strip()


def extract_raw_text(path: Path) -> str:
    """Route to the right extractor based on extension."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    return extract_text_from_image(path)

# ── Canonical Field Extraction ────────────────────────────────────────────────

# Canonical keys we care about for Commercial Property
CANONICAL_KEYS = [
    "annual_revenue",
    "property_value",
    "hazardous_materials",
    "risk_level",
    "insured_name",
]

# Broad currency prefix: ₹, $, Rs., INR, USD, US$, EUR—optional, stripped before number
_CURRENCY_PREFIX_RE = re.compile(
    r"(?:₹|\$|Rs\.?|INR|USD|US\$|EUR|GBP)\s*", re.IGNORECASE
)

# Keywords that introduce revenue/turnover
_REV_KW = re.compile(
    r"(?:(?:annual\s+)?(?:revenue|turnover)|gross\s+income)\s*[:\-]?\s*",
    re.IGNORECASE,
)
# Keywords that introduce property/insured value
_PROP_KW = re.compile(
    r"(?:property\s+value|insured\s+value|sum\s+insured|building\s+value|replacement\s+value)\s*[:\-]?\s*",
    re.IGNORECASE,
)
# After keyword, match optional currency symbol, then the amount
_AMOUNT_RE = re.compile(
    r"(?:(?:₹|\$|Rs\.?|INR|USD|US\$|EUR|GBP)\s*)?([\d,]+(?:\.\d+)?\s*(?:lakh|crore|cr|lac|l|million|mn|billion|k|thousand)?)",
    re.IGNORECASE,
)

_HAZMAT_PATTERN = re.compile(
    r"hazardous\s+material[s]?[\s:\-/]+(?:(?:storage|handling|disposal)[\s,]*)?\s*(yes|no|present|absent|none|not\s+applicable|n\.?a\.?)",
    re.IGNORECASE,
)
_RISK_PATTERN = re.compile(
    r"risk\s+(?:class(?:ification)?|category|level|rating|grade)[^\w]*(low|medium|high|moderate|severe|negligible|minimal)",
    re.IGNORECASE,
)
_NAME_PATTERN = re.compile(
    r"(?:insured\s+(?:name|party|entity|organization)|company\s+name|applicant\s+name|business\s+name|named\s+insured)[^\w]*([A-Za-z][A-Za-z0-9\s&,.'\-]+?)(?:\n|,|\.|\||Ltd\.|Inc\.|LLC|Pvt|$)",
    re.IGNORECASE,
)


def _extract_amount_after_keyword(kw_pattern: re.Pattern, text: str) -> str | None:
    """Find a currency amount that immediately follows a keyword match."""
    m_kw = kw_pattern.search(text)
    if not m_kw:
        return None
    remainder = text[m_kw.end():].lstrip()
    m_amt = _AMOUNT_RE.match(remainder)
    if m_amt and m_amt.group(1).strip():
        return m_amt.group(1).strip()
    return None




def extract_canonical_fields(text: str) -> dict[str, tuple[str, str]]:
    """
    Returns {canonical_key: (raw_value, normalized_value)}.
    Only keys found in the text are included.
    We use the central normalize_value layer here.
    """
    results: dict[str, tuple[str, str]] = {}

    raw = _extract_amount_after_keyword(_REV_KW, text)
    if raw:
        nv = normalize_value("annual_revenue", raw, "document")
        results["annual_revenue"] = (raw, nv.norm_value if nv.ok else raw)

    raw = _extract_amount_after_keyword(_PROP_KW, text)
    if raw:
        nv = normalize_value("property_value", raw, "document")
        results["property_value"] = (raw, nv.norm_value if nv.ok else raw)

    m = _HAZMAT_PATTERN.search(text)
    if m:
        raw = m.group(1).strip()
        nv = normalize_value("hazardous_materials", raw, "document")
        results["hazardous_materials"] = (raw, nv.norm_value if nv.ok else raw)

    m = _RISK_PATTERN.search(text)
    if m:
        raw = m.group(1).strip()
        nv = normalize_value("risk_level", raw, "document")
        results["risk_level"] = (raw, nv.norm_value if nv.ok else raw)

    m = _NAME_PATTERN.search(text)
    if m:
        raw = m.group(1).strip()
        nv = normalize_value("insured_name", raw, "document")
        results["insured_name"] = (raw, nv.norm_value if nv.ok else raw)

    return results

# ── Persistence ───────────────────────────────────────────────────────────────

def persist_extracted_fields(db, document: DocumentModel, fields: dict[str, tuple[str, str]]):
    for key, (raw, norm) in fields.items():
        ef = ExtractedField(
            document_id=document.id,
            key=key,
            raw_value=raw,
            normalized_value=norm,
        )
        db.add(ef)
        db.flush() # Need flush to get ef.id for Evidence
        
        # Link to Evidence table for Phase 6
        ev = Evidence(
            submission_id=document.submission_id,
            extracted_field_id=ef.id,
            canonical_key=key
        )
        db.add(ev)
    db.commit()

# ── Full pipeline ─────────────────────────────────────────────────────────────

def ingest_document(
    db,
    submission_id: int,
    requirement_id: int | None,
    file_obj: IO[bytes],
    filename: str,
    content_type: str,
    file_size: int,
) -> dict:
    """
    Full ingestion pipeline. Returns a summary dict.
    Raises DocumentValidationError on invalid input.
    """
    validate_upload(filename, content_type, file_size)

    saved_path = save_file(file_obj, filename)

    doc = DocumentModel(
        submission_id=submission_id,
        requirement_id=requirement_id,
        file_path=str(saved_path),
        status="processing",
    )
    db.add(doc)
    db.flush()

    try:
        raw_text = extract_raw_text(saved_path)
        canonical = extract_canonical_fields(raw_text)
        persist_extracted_fields(db, doc, canonical)
        doc.status = "processed"
    except Exception as e:
        doc.status = "error"
        db.commit()
        return {
            "document_id": doc.id,
            "status": "error",
            "error": str(e),
            "extracted_fields": {},
        }

    db.commit()
    return {
        "document_id": doc.id,
        "status": "processed",
        "raw_text_length": len(raw_text),
        "extracted_fields": {k: {"raw": r, "normalized": n} for k, (r, n) in canonical.items()},
    }
