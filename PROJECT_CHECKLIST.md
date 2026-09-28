# Project Implementation Checklist

## Phase 0 – Environment & Prerequisites
- [x] Install system dependencies (git, Node.js 20+, Python 3.11, PostgreSQL)
- [x] Clone repository and initialize git
- [x] Set up Python virtual environment

## 1. Project skeleton + dependencies
- [x] Initialize monorepo structure (frontend, backend, docs/artifacts). *Acceptance Criteria (AC): Directories exist.*
- [x] Install backend (`pip install -r requirements.txt`) and frontend (`npm ci`) dependencies. *AC: Installations complete without errors.*
- [x] Create `.env` files for backend and frontend. *AC: Env files have required placeholder variables.*
- [x] Set up FastAPI app skeleton (`app/main.py`) with initial health check. *AC: Endpoint returns 200 OK.*
- [x] Set up Vite + React + TypeScript skeleton (`src/main.tsx`). *AC: Dev server runs successfully.*

## 2. PostgreSQL database + core models
- [x] Configure PostgreSQL database and create user. *AC: Can connect via `psql` using app user.*
- [x] Implement core SQLAlchemy models (User, Submission, Product, Document, Evidence, Inconsistency). *AC: Models map correctly to DB tables.*
- [x] Create and run Alembic migrations for initial schema. *AC: Tables are visible in database.*

## 3. Insurance product + adaptive requirement engine
- [x] Define data structures for mock product limits and underwriting rules. *AC: Config file/mock DB entries exist.*
- [x] Implement backend endpoint returning adaptive questionnaire metadata based on product. *AC: JSON matches schema.*
- [x] Implement engine logic evaluating conditional required documents. *AC: Unit tests pass for required-doc logic.*

## 4. Submission/questionnaire UI
- [x] Build React forms for core fields (Applicant info, Basic risk info). *AC: State updates correctly on input.*
- [x] Build Adaptive Questionnaire UI interpreting backend metadata. *AC: Questions appear/hide based on answers.*
- [x] Wire UI to submission endpoints (save draft, submit). *AC: Payload successfully reaches backend and gets saved.*

## 5. Document upload + OCR/extraction
- [x] Build Document Upload UI component. *AC: Users can browse/drag PDFs or images.*
- [x] Create FastAPI endpoint for accepting binary files. *AC: File is saved locally or parsed in memory.*
- [x] Integrate local Tesseract OCR to extract raw text. *AC: Text is accurately pulled from sample image/PDF.*

## 6. Evidence normalization
- [x] Implement standard regex/heuristic extraction (Currency, Dates, Names). *AC: Test cases correctly extract entities.*
- [x] Structure extracted inputs against canonical model (e.g., standardizing formats). *AC: Outputs are consistent JSON.*
- [x] Associate normalized evidence to specific Submission ID. *AC: Database reflects evidence-document relationships.*

## 7. Cross-document consistency checks
- [x] Implement logic to compare Application answers vs Extracted Evidence. *AC: Engine flags matches and mismatches.*
- [x] Implement numeric tolerance rules for minor discrepancies. *AC: Discrepancies within threshold are marked valid/warning.*
- [x] Expose consistency state per submission via API. *AC: API returns grouped consistency results.*

## 8. Explainable requirement/issue reasoning
- [x] Implement rule mapper linking inconsistencies to human-readable text. *AC: Output maps directly to reason (e.g. "Values differ").*
- [x] Link rule triggers back to source document/field (Auditability). *AC: Result contains reference to origin document.*

## 9. Underwriter dashboard
- [x] Build Underwriter grid/list view of submissions. *AC: Displays status tiles (✓, ⚠, ✕).*
- [x] Build detail view showing Document trail, Extracted fields, and Conflicts. *AC: Underwriter can visually locate issues.*
- [x] Implement action buttons (Request Info, Complete Assessment). *AC: Status updates in DB.*

## 10. End-to-end integration
- [x] Connect React frontend directly to all processing endpoints. *AC: Complete flow from new submission to underwriter review without manual DB edits.*
- [x] Ensure requirement feedback loops back to the broker UI. *AC: Agent dashboard shows pending fixes.*

## 11. Testing + real-document validation
- [x] Populate dev DB with realistic mock insurance products. *AC: Field patterns from ACORD 25, NFIP, IRDAI, FCA validated; extraction works on all pattern variants.*
- [x] Run full E2E flow using actual sample PDFs/Images. *AC: 64 real-document validation tests pass; USD/INR/bare-number extraction all verified.*
- [x] Fix identified critical path bugs. *AC: Fixed USD-prefix extraction regression; extended risk vocab (negligible/minimal/critical); extended hazmat vocab (N/A, not applicable).*

## 12. Demo/report preparation
- [x] Write simplified developer README.md. *AC: README.md covers prerequisites, backend/frontend setup, env vars, migrations, test commands, and limitations.*
- [x] Archive code state for delivery. *AC: Initial git commit 671dc74 — 68 files, 7202 insertions, no secrets, no build artifacts, no uploads.*
- [x] Prepare localized architecture data flow diagram (Mermaid). *AC: Diagram in walkthrough.md and README.md accurately reflects the implemented system.*

## Phase 13 — Identity, Roles & Application Foundation
- [x] Customer/broker authentication *AC: Integration tests confirm broker can login.*
- [x] Underwriter authentication *AC: Integration tests confirm underwriter can login.*
- [x] Role-based routing and protected access *AC: UI/API rejects unauthorized routes — 5 unauth tests + 4 RBAC tests pass.*
- [x] Replace hardcoded user/submission ownership *AC: Submissions tied to authenticated user ID — hardcoded user_id=1 removed.*
- [ ] Customer dashboard *AC: Broker can view own submissions; backend tests pass.*
- [ ] Underwriter dashboard/submission queue *AC: Underwriters see queue based on role.*
- [ ] Submission status lifecycle *AC: State transitions enforced.*
- [x] Backend authorization boundaries *AC: Endpoints protected by role permissions — ownership isolation 3 tests pass.*
- [x] Authentication/authorization tests *AC: test_auth.py — 22 tests all pass (149 total backend tests, 0 failures).*
- [ ] Manual browser verification *AC: Verified in browser manually.*

## Phase 14 — Customer Insurance Application & Adaptive Requirements
- [ ] Meaningful insurance/product selection *AC: Selection restricts subsequent options.*
- [ ] Applicant/business details *AC: Information captured in normalized schema.*
- [ ] Property/asset details *AC: Asset properties appropriately captured.*
- [ ] Risk information *AC: Risk responses recorded and persisted.*
- [ ] Human-friendly questionnaire UI *AC: UI layout accessible and intuitive.*
- [ ] Truly conditional/adaptive questions *AC: Questionnaire pathways dynamically adapt.*
- [ ] Dynamic document requirements *AC: Document requests trigger automatically.*
- [ ] Requirement explanations *AC: Plain-english reasons provided for doc requests.*
- [ ] Back/edit navigation *AC: Bidirectional navigation works safely.*
- [ ] Persistence across navigation and refresh *AC: Local/server state preserved across refresh.*
- [ ] Remove developer-facing field names, JSON, file paths and internal IDs from customer UI *AC: UI components display correctly formatted labels.*
- [ ] Tests + manual browser verification *AC: Automated tests pass and browser validated.*

## Phase 15 — Evidence & Underwriter Review Workflow
- [ ] Customer document upload, replacement and viewing *AC: Support replacing stale docs.*
- [ ] Human-readable document status *AC: Distinct tags for extraction stages.*
- [ ] Document viewer for underwriter *AC: Original file available alongside extracted data.*
- [ ] Extracted information presentation *AC: Sourced facts intuitively organized.*
- [ ] Cross-document evidence consistency findings *AC: Conflicting answers highlighted visually.*
- [ ] Underwriter submission review workspace *AC: Dashboard aggregates review requirements.*
- [ ] Review suggestions with explanations *AC: Underwriter suggestions contain rationale.*
- [ ] Accept/dismiss suggestions *AC: State handles acceptance/dismissal appropriately.*
- [ ] Underwriter review notes *AC: Analysts can append text observations.*
- [ ] Submission history *AC: History captures state and notes accurately.*
- [ ] Tests + manual browser verification *AC: Automated tests pass and browser validated.*

## Phase 16 — Two-Way Review, Additional Documents & Final Decision
- [ ] Underwriter-created additional document requests *AC: Underwriter forms can dispatch ad-hoc requests.*
- [ ] Dynamic customer-side upload fields for requested documents *AC: Broker sees new file inputs based on requests.*
- [ ] Newly uploaded documents enter the existing extraction/verification pipeline *AC: Re-evaluation pipeline triggered successfully.*
- [ ] Customer ↔ underwriter review loop *AC: State loop behaves cyclically without deadlock.*
- [ ] Approve workflow *AC: Terminal successful state handled gracefully.*
- [ ] Decline workflow *AC: Terminal failure state handled gracefully.*
- [ ] Request-information workflow *AC: Broker notified of pending information requested.*
- [ ] Customer-visible decision/review messages *AC: Resolution notes provided to broker view.*
- [ ] Audit trail improvements *AC: End-to-end events accurately time-stamped and logged.*
- [ ] End-to-end integration testing *AC: Test environments run complete simulated interactions.*
- [ ] Final UX/security/error-handling/reproducibility cleanup *AC: Validation barriers implemented completely.*
- [ ] Final manual browser walkthrough *AC: Final walkthrough complete.*

## OPTIONAL / AFTER CORE
- [ ] CI/CD workflows and automated GitHub actions
- [ ] Docker containerization and Helm charts for local/cloud deployment
- [ ] Complex JWT / Role-based auth (using simple mockup/bypasses for 2-day prototype)
- [ ] Premium glassmorphism animations and cosmetic UI polishes
- [ ] Advanced performance profiling and queuing systems (Celery, etc.)
- [ ] Demo video production
