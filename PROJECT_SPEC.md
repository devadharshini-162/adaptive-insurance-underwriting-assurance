# Project Specification

## 1. Problem Statement
Commercial insurance submissions require different information, documents, validations, and underwriting checks depending on the insurance product and the characteristics of the applicant and risk.

A fixed questionnaire and document checklist can therefore lead to **unnecessary information collection, missing requirements, repeated follow-ups, and inconsistent information across submitted documents**.

The problem is to prepare an insurance submission so that the underwriter can determine whether the available information and supporting evidence are **complete, consistent, and sufficient for underwriting**.

## 2. Solution
A **full-stack adaptive insurance submission and underwriting assurance system**, designed around the PolicyCenter/Guidewire insurance workflow.

The system:
1. Identifies the insurance product and risk characteristics.
2. Dynamically determines the relevant questions and required documents.
3. Collects information and documents from the agent/broker.
4. Extracts structured information from uploaded documents.
5. Compares information across the submission and documents.
6. Detects missing, conflicting, invalid, or insufficient evidence.
7. Explains **why** additional information/documents are required.
8. Gives the underwriter an **Underwriting Assurance Dashboard** showing what is verified, missing, conflicting, or requires review.

## 3. Core Workflow
```text
Insurance Product
       ↓
Adaptive Questions
       ↓
Required Documents
       ↓
Information + Document Submission
       ↓
Document Extraction
       ↓
Evidence Normalization
       ↓
Cross-Document Consistency
       ↓
Requirement & Evidence Evaluation
       ↓
Underwriting Assurance
       ↓
Underwriter Review
```

## 4. Pages / Modules

### Agent / Broker Side
1. **Login / User Access**
2. **Dashboard**: Existing submissions, Draft submissions, Submission status, Pending actions
3. **Create New Submission**: Select insurance product, Applicant/business information, Basic risk information
4. **Adaptive Questionnaire**: Questions change according to previous answers/risk characteristics, Required/optional indicators
5. **Document Requirements**: Required/Conditional/Optional documents, Reason for each requirement
6. **Document Upload**: Upload documents, Document classification, Upload status, Missing-document indication
7. **Submission Verification**: Extracted information, Detected mismatches, Missing information, Document validity, User corrections/confirmation
8. **Submission Review & Submit**: Overall readiness, Outstanding issues, Final submission

### Underwriter Side
9. **Underwriter Dashboard**: Submission overview, Completeness, Evidence status, Conflicts, Pending verification, Underwriting issues
10. **Submission Details**: Applicant/risk information, All submitted documents, Extracted fields, Cross-document comparisons, Evidence trail
11. **Requirement / Issue Review**: Missing requirement, Conflict, Reason, Supporting documents, Resolve / request additional information
12. **Underwriting Decision / Workflow**: Continue, Request information, Refer/review, Complete underwriting assessment

## 5. Features
- **Adaptive Intake**: Product-specific questions, conditional questions, conditional document requirements, requirement status tracking.
- **Document Intelligence**: Document upload, classification, OCR/text extraction, field extraction, structured representation of extracted information.
- **Evidence Verification**: Field normalization, entity matching, cross-document comparison, missing evidence detection, conflicting information detection, expired/invalid document detection.
- **Requirement Reasoning**: Explainable logic for required documents (e.g., "Additional financial statement required because the declared business revenue exceeds the configured threshold.").
- **Underwriting Assurance Dashboard**: Status of Information, Documents, Consistency, Requirements, Overall readiness.
- **Auditability**: Traceability from finding to source document/field to rule/reasoning to result and recommended action.

## 6. Novelty / Improvement
The key innovation is the combination of **Cross-document Evidence Consistency + Explainable Requirement Reasoning**. 

The system provides an explainable evidence-assurance layer that continuously evaluates whether an evolving insurance submission contains consistent and sufficient evidence, tracing conflicting data across applications and submitted documents and explicitly explaining the reasoning behind required evidence.

## 7. Architecture
- Frontend: Single Page Application communicating with Backend via REST APIs.
- Backend: API server handling logic, document processing, and consistency checks.
- Database: Relational database to track user sessions, submission state, domain entities, and audit records.
- Document Processing Pipeline: Offline or async processing of documents for OCR, text extraction, and entity matching.

## 8. Tech Stack
* **Frontend**: React + Vite + TypeScript, React Router, Tailwind CSS
* **Backend**: Python + FastAPI
* **Database**: PostgreSQL
* **AI / Document Processing**: Python ecosystem (OCR, NLP for structured extraction, potentially LLM for reasoning)
* **Authentication**: JWT-based authentication

## 9. External APIs / Dependencies
* **LLM API**: Chosen LLM provider (e.g., Gemini API, OpenAI API) for document information extraction and reasoning (only where deterministic extraction is insufficient).
* **OCR**: Prefer local/free OCR library (e.g., Tesseract). Cloud OCR service only if local is insufficient.
* **Database**: PostgreSQL (requires local or cloud hosted database).

No external insurance system API is inherently required. Guidewire API integration is optional and deferred pending access.
