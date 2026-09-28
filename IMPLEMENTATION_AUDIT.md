# Implementation Audit — Initial Findings

This checklist records the state observed in the repository on 28 September
2026. “Complete” means code and automated coverage were found; it does not
mean a manual browser walkthrough was performed.

| Status | Requirement | Evidence / finding |
|---|---|---|
| ✅ COMPLETE | Product is chosen before risk answers | `NewSubmission` creates a draft only after `getProducts` selection. |
| ✅ COMPLETE | Multiple insurance types | Sixteen seeded categories include commercial and separate personal product paths. |
| ✅ COMPLETE | Motor / Home / Travel / Construction / Marine Cargo | Each now has its own product data, adaptive questions and document requirements. |
| ✅ COMPLETE | Commercial Property, Cyber and Workers’ Compensation paths | Seed data and engine tests contain product-specific rules. |
| ✅ COMPLETE | Product-specific and conditional questions | Question `condition_logic` is evaluated by the deterministic engine; UI renders only `applicable_questions`. |
| ✅ COMPLETE | Product-specific intake fields | Motor, Home, Travel, Personal Cyber, Personal Valuables & Marine and Personal Liability show an applicant step rather than business/property fields; Commercial Property retains its property step. |
| ✅ COMPLETE | Answers persist through navigation and draft reopening | Answers save on change; `getApplication` restores profile, answers and product ID. |
| ⚠️ PARTIAL | Progress indicator | The stepper represents current steps but does not include selection, documents, review, or submission. |
| ✅ COMPLETE | Insurance-company selection and persistence | A first-class model, migration, protected catalogue API and application selector persist the insurer. |
| ✅ COMPLETE | Insurer-filtered underwriter selection / assignment | Demonstration underwriters have company, title, products, specialty, experience, availability and description; compatible choices are persisted. |
| ✅ COMPLETE | Customer create/save/reopen/continue flow | Authenticated customer endpoints and dashboard actions are present. |
| ✅ COMPLETE | Product-specific requirements, upload and review | Requirements are evaluated per product and shown with explanations; documents are persisted and displayed. |
| ✅ COMPLETE | Draft delete control / confirmation / ownership | Dashboard calls authenticated `DELETE /api/submissions/{id}` after confirmation; API permits only the owner’s `draft`. |
| ✅ COMPLETE | Draft deletion feedback | Confirmation, error feedback and a successful-deletion message are displayed. |
| ✅ COMPLETE | Draft isolation from underwriting queue | `GET /api/submissions` excludes `draft`; lifecycle tests cover draft exclusion and submitted visibility. |
| ✅ COMPLETE | Submission lifecycle states | `draft`, `under_review`, `info_requested`, `approved`, and `declined` transitions are enforced by the lifecycle service. |
| ✅ COMPLETE | Underwriter relevance filtering | Seeded-catalogue applications require compatible insurer/underwriter selection and assigned submissions are restricted to that user. |
| ⚠️ PARTIAL | Queue information and filtering | Queue now adds insurer and assignee; search, issue-count and last-updated filtering are still absent. |
| ✅ COMPLETE | Underwriter detail, document access and audit history | Protected dashboard aggregates application data, documents, evidence, requirements, issues and audit events. |
| ✅ COMPLETE | Issue explanation | Primary issue cards separate the issue, why it matters, evidence sources and recommended action without raw document IDs. |
| ✅ COMPLETE | No raw model scores in primary issue UI | Issue generation is deterministic and UI has no ML probability/model-score display. |
| ✅ COMPLETE | Requirement explanations and conditional requirements | Engine returns plain-language requirement explanations and applicable conditional requirements. |
| ⚠️ PARTIAL | Optional-document distinction | The model supports required/conditional rules only; no optional requirement type exists. |
| ✅ COMPLETE | Document/extraction/consistency access boundaries | Document and submission endpoints use JWT ownership/RBAC checks; test suite covers unauthorized access. |
| ✅ COMPLETE | Customer/underwriter loading, empty and error states | Main dashboard, application flow, review and detail pages contain basic states. |
| ⚠️ PARTIAL | Success feedback / responsive UX | Draft deletion now confirms success; no manual browser/responsive walkthrough has been performed. |

## Initial scenario status

| Status | Scenario | Evidence / finding |
|---|---|---|
| ✅ COMPLETE | Motor draft / reopen / delete | Motor is seeded; generic persistence/delete behavior is automated, though browser walkthrough remains outstanding. |
| ✅ COMPLETE | Motor submission with insurer / underwriter | Compatible insurer/underwriter selection is validated and persisted before a draft is created. |
| ✅ COMPLETE | Draft visibility lifecycle | Automated lifecycle tests show drafts excluded and submitted applications included in the queue. |
| ⚠️ PARTIAL | Cyber product pathway | Cyber questions and requirements exist; browser-level pathway has not been manually run. |
| ✅ COMPLETE | Insurer and underwriter filtering | Focused API test verifies compatible options, assignment visibility and cross-underwriter denial. |
| ✅ COMPLETE | Human-readable underwriting issue | Primary issue presentation now uses structured human-readable explanation. |
| ✅ COMPLETE | Draft deletion backend path | Focused automated test passes for owner, non-owner and list refresh semantics. |

## Final audit conclusion

The core adaptive workflow now includes product-specific intake, persisted demo
insurer/underwriter assignment, draft persistence/deletion and submitted-only
assigned queue visibility. Remaining partial items are intentionally limited to
queue search/metrics, optional document categories, and manual responsive /
browser verification.
