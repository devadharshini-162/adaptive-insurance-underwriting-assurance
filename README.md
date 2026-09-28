# Adaptive Insurance Submission & Underwriting Assurance System

A monorepo prototype of an end-to-end adaptive insurance submission workflow with deterministic underwriting intelligence. Built with FastAPI (Python) and React (TypeScript).

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Data Flow](#data-flow)
4. [Prerequisites](#prerequisites)
5. [Backend Setup](#backend-setup)
6. [Frontend Setup](#frontend-setup)
7. [Environment Variables](#environment-variables)
8. [Database & Migrations](#database--migrations)
9. [Running the Application](#running-the-application)
10. [Running Tests](#running-tests)
11. [Current Limitations](#current-limitations)

---

## Project Overview

This system enables insurance brokers/agents to:
- Create submissions against configurable insurance products
- Complete adaptive questionnaires where requirements update in real-time
- Upload supporting documents for OCR extraction and evidence normalization
- Receive deterministic cross-document consistency checks (no LLM involved)
- Have underwriting issues and explainability generated automatically

Underwriters then use a dashboard to:
- Review all evidence side-by-side
- See conflicts between declared values and extracted document evidence
- Resolve or dismiss issues with a full audit trail
- Approve, decline, or request more information

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                       │
│  (Vite + TypeScript · src/pages · src/services/api.ts)   │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP/JSON (REST)
┌───────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend                        │
│  app/api/routers/  (submissions, documents, products,    │
│                     engine, documents)                   │
│  app/services/     (engine, document_service,            │
│                     normalization, consistency_service,  │
│                     issue_mapper)                        │
│  app/models/       (SQLAlchemy ORM)                      │
└───────────────────────┬──────────────────────────────────┘
                        │ SQLAlchemy / psycopg2
┌───────────────────────▼──────────────────────────────────┐
│                   PostgreSQL Database                     │
│  Tables: users, insurance_products, questions,           │
│          requirements, condition_groups, conditions,     │
│          submissions, answers, documents,                │
│          extracted_fields, evidence,                     │
│          consistency_checks, underwriting_issues,        │
│          audit_records                                   │
└──────────────────────────────────────────────────────────┘
```

### Key Services

| Service | File | Purpose |
|---------|------|---------|
| Requirement Engine | `app/services/engine.py` | Evaluates conditional requirements from a rule tree against live answers |
| Document Ingestion | `app/services/document_service.py` | Validates, stores, OCR-extracts, and persists documents |
| Evidence Normalization | `app/services/normalization.py` | Converts raw OCR/answer values to canonical comparable forms |
| Consistency Engine | `app/services/consistency_service.py` | Pairwise comparison of answer vs. document evidence per canonical field |
| Issue Mapper | `app/services/issue_mapper.py` | Translates consistency conflicts and missing requirements into underwriting issues with explainability |

---

## Data Flow

```
User/Broker                React UI                   FastAPI                        PostgreSQL
    │                          │                          │                               │
    │── select product ────────► POST /api/submissions ──► create Submission ────────────►│
    │                          │                          │                               │
    │── answer questions ──────► PUT  /answers ───────────► persist Answers ─────────────►│
    │   (live requirements)    │ POST /engine/evaluate ──► evaluate rule tree             │
    │                          │                          │                               │
    │── upload document ───────► POST /api/documents/upload                               │
    │                          │                          ├─ validate + save file         │
    │                          │                          ├─ extract text (PyMuPDF/OCR)   │
    │                          │                          ├─ extract canonical fields     │
    │                          │                          ├─ normalize values ────────────►│
    │                          │                          └─ persist ExtractedField/Evidence
    │                          │                          │                               │
    │── submit ────────────────► POST /issues/generate ──► run_consistency_checks ───────►│
    │                          │                          ├─ generate_issues_for_submission
    │                          │                          └─ persist ConsistencyCheck     │
    │                          │                             + UnderwritingIssue ─────────►│
    │                          │                          │                               │
    │── view dashboard ────────► GET /dashboard ──────────► aggregate all data ───────────►│
    │                          │                          │                               │
    │── resolve issue ─────────► PUT /issues/{id} ────────► update status + AuditRecord ──►│
    │── change status ─────────► PUT /status ─────────────► update Submission + AuditRecord►│
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | ≥ 3.11 | 3.14 tested |
| Node.js | ≥ 18 | 20 LTS recommended |
| PostgreSQL | ≥ 14 | Must be running locally |
| Tesseract OCR | ≥ 4.1 | Required for image/scanned PDF OCR |
| `psycopg2` native libs | — | Usually satisfied by `psycopg2-binary` |

### Install Tesseract (Manjaro / Arch)
```bash
sudo pacman -S tesseract tesseract-data-eng
```

### Install Tesseract (Ubuntu/Debian)
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

---

## Backend Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Set environment variables (see below)
cp backend/.env.example backend/.env
# Edit backend/.env

# 4. Apply database migrations
cd backend
alembic upgrade head

# 5. Seed initial data (products, questions, requirements)
python scripts/seed.py   # if present, or use the API after startup
```

---

## Frontend Setup

```bash
cd frontend
npm install
```

---

## Environment Variables

Create `backend/.env` (never commit this file):

```env
# PostgreSQL connection string
DATABASE_URL=postgresql+psycopg2://postgres:yourpassword@localhost:5432/assurance_db

# Directory where uploaded documents are stored (absolute path recommended)
UPLOAD_DIR=/absolute/path/to/gw-project/uploads
```

An `.env.example` template:

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/assurance_db
UPLOAD_DIR=./uploads
```

The frontend uses a single env variable (optional, defaults to `http://localhost:8000`):

```env
# frontend/.env.local
VITE_BACKEND_URL=http://localhost:8000
```

---

## Database & Migrations

Migrations are managed with **Alembic** from inside the `backend/` directory.

```bash
cd backend

# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1
```

The initial schema migration (`954caae8332b`) creates all tables.  
The second migration (`d545bc9dd84b`) adds the `details` JSON column to `underwriting_issues`.

---

## Running the Application

### Backend (FastAPI)

```bash
# From project root, with venv active:
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### Frontend (Vite dev server)

```bash
cd frontend
npm run dev
# Opens at http://localhost:5173
```

### Production frontend build

```bash
cd frontend
npm run build
# Output in frontend/dist/
```

---

## Running Tests

All tests use **pytest** with isolated in-memory SQLite databases (no PostgreSQL required for tests).

```bash
# From project root, with venv active:
cd backend
../venv/bin/pytest -v
```

### Test suites

| File | Tests | What it covers |
|------|-------|---------------|
| `test_engine.py` | 21 | Requirement rule tree evaluation |
| `test_document_service.py` | 27 | File validation, OCR extraction, field persistence |
| `test_normalization.py` | 8 | Currency/boolean/date/risk normalisation |
| `test_consistency_engine.py` | 5 | Pairwise consistency comparison, tolerances |
| `test_issue_mapper.py` | 8 | Issue generation, severity, explainability, idempotency |
| `test_e2e_integration.py` | 1 | Full lifecycle: create → answers → upload → issues → dashboard → action |
| `test_real_document_validation.py` | 64 | Real-world field pattern extraction (ACORD 25, NFIP, IRDAI, FCA) |
| **Total** | **127** | All pass |

---

## Current Limitations

| Area | Limitation |
|------|-----------|
| **Authentication** | No real auth; all requests use a stub `user_id=1`. JWT/RBAC is in the optional backlog. |
| **OCR quality** | Depends on Tesseract installation and scan resolution. Embedded-text PDFs work reliably. |
| **Currency cross-comparison** | Revenue amounts in USD and INR are stored as raw integers without a currency flag; the consistency engine treats them as the same unit. Cross-currency comparison is out of scope. |
| **question_id → canonical key mapping** | Hardcoded in `normalization.py` for the seeded Commercial Property product (IDs 1–5). Additional products need their own mapping entry. |
| **Table-structured PDFs** | Fields inside complex PDF tables may not match the regex patterns if label and value appear in separate text fragments. |
| **Multi-page field priority** | First-occurrence wins when the same label appears on multiple pages. |
| **Concurrency** | No row-level locking; concurrent issue generation for the same submission could produce duplicates if called in rapid parallel. |
