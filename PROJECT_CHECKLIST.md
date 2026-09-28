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
- [x] Customer dashboard *AC: Broker can view own submissions; backend tests pass (151 total backend tests, 0 failures).*
- [x] Underwriter dashboard/submission queue *AC: Underwriters see queue based on role; 151 total backend tests pass.*
- [x] Submission status lifecycle *AC: State transitions enforced; 152 backend tests pass.*
- [x] Backend authorization boundaries *AC: Endpoints protected by role permissions — ownership isolation 3 tests pass.*
- [x] Authentication/authorization tests *AC: test_auth.py — 22 tests all pass (149 total backend tests, 0 failures).*
- [ ] Manual browser verification *AC: Verified in browser manually.*

## Phase 14 — Customer Insurance Application & Adaptive Requirements
- [x] Meaningful insurance/product selection *AC: Selection restricts subsequent options.*
- [x] Applicant/business details *AC: Information captured in normalized schema.*
- [x] Property/asset details *AC: Asset properties appropriately captured.*
- [x] Risk information *AC: Risk responses recorded and persisted.*
- [x] Human-friendly questionnaire UI *AC: UI layout accessible and intuitive.*
- [x] Truly conditional/adaptive questions *AC: Questionnaire pathways dynamically adapt.*
- [x] Dynamic document requirements *AC: Document requests trigger automatically.*
- [x] Requirement explanations *AC: Plain-english reasons provided for doc requests.*
- [x] Back/edit navigation *AC: Bidirectional navigation works safely.*
- [x] Persistence across navigation and refresh *AC: Local/server state preserved across refresh.*
- [x] Remove developer-facing field names, JSON, file paths and internal IDs from customer UI *AC: UI components display correctly formatted labels.*
- [ ] Tests + manual browser verification *AC: Automated tests pass and browser validated.*

## Phase 15 — Evidence & Underwriter Review Workflow
- [x] Customer document upload, replacement and viewing *AC: Support replacing stale docs; authorization tests pass.*
- [x] Human-readable document status *AC: Distinct customer-facing processing tags are displayed.*
- [x] Document viewer for underwriter *AC: Authorized document content endpoint is available from review workspace.*
- [x] Extracted information presentation *AC: Evidence uses human-readable labels.*
- [x] Cross-document evidence consistency findings *AC: Deterministic conflicts and insufficient evidence are displayed.*
- [x] Underwriter submission review workspace *AC: Applicant, evidence, requirements, findings, issues and history aggregate in the review page.*
- [x] Review suggestions with explanations *AC: Existing deterministic issue rationale and recommended action are shown.*
- [x] Accept/dismiss suggestions *AC: Underwriter actions persist and are audited.*
- [x] Underwriter review notes *AC: Optional review notes persist with actions.*
- [x] Submission history *AC: Creation, document, status and review events are recorded and displayed.*
- [ ] Tests + manual browser verification *AC: Automated tests pass and browser validated.*

## Phase 16 — Two-Way Review, Additional Documents & Final Decision
- [x] Underwriter-created additional document requests *AC: Underwriter forms can dispatch ad-hoc requests.*
- [x] Dynamic customer-side upload fields for requested documents *AC: Broker sees new file inputs based on requests.*
- [x] Newly uploaded documents enter the existing extraction/verification pipeline *AC: Re-evaluation pipeline triggered successfully.*
- [x] Customer ↔ underwriter review loop *AC: State loop behaves cyclically without deadlock.*
- [x] Approve workflow *AC: Terminal successful state handled gracefully.*
- [x] Decline workflow *AC: Terminal failure state handled gracefully.*
- [x] Request-information workflow *AC: Broker notified of pending information requested.*
- [x] Customer-visible decision/review messages *AC: Resolution notes provided to broker view.*
- [x] Audit trail improvements *AC: End-to-end events accurately time-stamped and logged.*
- [x] End-to-end integration testing *AC: Test environments run complete simulated interactions.*
- [x] Final UX/security/error-handling/reproducibility cleanup *AC: Authorization and lifecycle barriers enforced; customer error/navigation paths verified by tests and build checks.*
- [ ] Final manual browser walkthrough *AC: Final walkthrough complete.*

## OPTIONAL / AFTER CORE
- [ ] CI/CD workflows and automated GitHub actions
- [ ] Docker containerization and Helm charts for local/cloud deployment
- [ ] Complex JWT / Role-based auth (using simple mockup/bypasses for 2-day prototype)
- [ ] Premium glassmorphism animations and cosmetic UI polishes
- [ ] Advanced performance profiling and queuing systems (Celery, etc.)
- [ ] Demo video production
