# DECISIONS.md — Technical Decisions and Open Questions

Record settled choices here so the team and coding agents do not repeatedly reconsider them. Use `Proposed`, `Accepted`, or `Rejected` for open decisions and add the date/owner when the team decides.

## Accepted decisions

### D-001 — Prototype scope
**Status:** Accepted
**Decision:** Implement only the Basic MVP for one institutional application category and two or three representative document types.  
**Reason:** Keeps the prototype achievable and allows meaningful end-to-end testing.

### D-002 — User of the system
**Status:** Accepted  
**Decision:** The demo focuses on a reviewer inspecting a sample institutional application and its supporting documents.  
**Reason:** The MVP requires one basic reviewer view, not a complete multi-role portal.

### D-003 — Frontend
**Status:** Accepted  
**Decision:** React + Vite + Tailwind CSS.  
**Reason:** Suitable for a component-based reviewer dashboard and rapid UI development.

### D-004 — Backend
**Status:** Accepted  
**Decision:** Python + FastAPI.  
**Reason:** Provides a direct Python integration path for PaddleOCR, PDF processing and the validation engine.

### D-005 — OCR
**Status:** Accepted  
**Decision:** PaddleOCR.  
**Reason:** Required project choice for extracting text from scanned document pages and images. OCR is for text recognition, not proof of authenticity.

### D-006 — PDF processing
**Status:** Accepted  
**Decision:** PyMuPDF. Extract selectable text from digital PDFs where possible; render scanned pages for PaddleOCR.  
**Reason:** Avoids unnecessary OCR for PDFs with usable text and supports scanned PDFs through page rendering.

### D-007 — Database
**Status:** Accepted  
**Decision:** Use PostgreSQL for application records, document metadata, extraction runs and findings.  
**Reason:** PostgreSQL is the selected project stack and the core data has clear relationships. Avoid switching databases mid-build unless the team explicitly agrees and documents a compelling reason.

### D-008 — File storage
**Status:** Accepted for prototype  
**Decision:** Store uploaded files locally under `backend/uploads/`; store metadata and relative storage references in PostgreSQL. Exclude uploads from Git.  
**Reason:** Simple for a local/demo deployment. Production deployment may need persistent or object storage.

### D-009 — Validation approach
**Status:** Accepted  
**Decision:** Use a custom Python rule engine with explicit checks for document presence, required fields, applicable expiry dates and cross-document consistency.  
**Reason:** Rules are explainable and testable; no AI/LLM is needed for these checks.

### D-010 — Synthetic demo data
**Status:** Accepted  
**Decision:** Use synthetic institutional and document data.  
**Reason:** Safe and reproducible for the demonstration.

### D-011 — Human review and claims
**Status:** Accepted  
**Decision:** The prototype provides preliminary scrutiny only. A mismatch or anomaly is a flag for review, not proof of fraud. It does not make final AICTE approval decisions or claim real issuer verification.  
**Reason:** OCR and rule checks cannot independently establish authenticity or legal approval.

### D-012 — Shared integration contract
**Status:** Accepted  
**Decision:** `docs/API_CONTRACT.md` is the source of truth for endpoints, JSON fields and status values.  
**Reason:** Prevents inconsistent assumptions across frontend, OCR and backend workstreams.

### D-013 — Low-confidence OCR review threshold
**Status:** Accepted
**Decision:** Treat OCR-derived field confidence below `0.70` as uncertain and return `unresolved` for checks that rely on that value. Digital PDF text extraction keeps confidence `null` and is not subject to this OCR threshold.
**Reason:** Low-confidence OCR values should be confirmed by a reviewer instead of producing a pass or discrepancy finding. This is an implementation threshold, not an AICTE requirement.
**Date / Owner:** 2026-10-26 / Integration

### D-015 — Separate institute submission from completed scrutiny
**Status:** Accepted
**Decision:** Application lifecycle status moves from `draft` to `submitted` when the institution submits, then to `review_completed` only when an authenticated reviewer explicitly finalizes scrutiny. Submission does not create a final report. Institutions may retrieve the report only after `review_completed`; reviewer decisions and validation reruns are read-only after finalization. Required checklist document types must be present before submission.
**Reason:** Submission queues an application for human review; it is not itself a scrutiny decision. Persisting the distinction prevents premature report disclosure and duplicate submissions.
**Date / Owner:** 2026-10-27 / Integration

### D-016 — Require reviewer actions only for open findings
**Status:** Accepted
**Decision:** `flagged`, `missing`, and `unresolved` findings require a recorded reviewer action before scrutiny can be finalized. `pass` and `not_applicable` findings do not. Resubmission requests and escalations require action-specific notes; those decisions do not turn the underlying validation outcome into a pass. A recorded finding decision cannot be overwritten, and scrutiny cannot be rerun after a reviewer action because a rerun replaces findings.
**Reason:** Informational checks should not create false pending work. The API exposes the requirement on each finding and the finalization endpoint enforces the same rule.
**Date / Owner:** 2026-10-28 / Integration

### D-014 — Authentication and role-based access control
**Status:** Accepted  
**Decision:** Implement authentication and role-based authorization with two explicit roles:
1. `INSTITUTION`: Self-registers, manages own applications, uploads documents to draft applications, runs preliminary validation on drafts, submits applications to AICTE, and views the completed scrutiny report after reviewer finalization. 1:1 institution per user account.
2. `REVIEWER`: AICTE scrutiny committee auditor. Can access submitted applications, inspect documents, run checks, record finding decisions, and finalize scrutiny. Completed applications are read-only. Reviewers cannot self-register; they are provisioned via CLI seed script or one-time admin setup route (`POST /api/auth/admin/setup`) protected by `X-Admin-Setup-Token`.
3. Application lifecycle locking: Once submitted to AICTE, an application is locked (`status = 'submitted'`). Uploads and institution re-validation reject with 409 `APPLICATION_LOCKED`. Finalization changes the lifecycle status to `review_completed`; the institution can then view the report. Based on the report, institutions can initiate a new application revision prefilled from prior findings.
4. Security & Tokens: Stateless JWT access tokens (60 min default for demo UX) with rotating HTTP-only refresh tokens. Cross-tenant draft access returns 404 to prevent IDOR enumeration. Fail-fast validation enforces production secrets when `DEBUG=false`.  
**Reason:** Satisfies multi-tenant security requirements, human-in-the-loop review boundaries, and seamless demo UX without requiring external SSO infrastructure.  
**Date / Owner:** 2026-10-27 / Integration

## Open questions — resolve before implementing rules

### Q-001 — Application category
**Status:** Resolved  
**Decision:** Extension of Approval (EoA) — Self-Disclosure for existing institutions, as defined in AICTE APH 2024-2027 Chapter II and Annexure-2, Section 2.1.  
**Resolved Date / Owner:** 2026-10-25 / Person 3 (Approved)

### Q-002 — Document types
**Status:** Resolved  
**Decision:** Three representative document types selected:
1. `fire_safety_certificate` (Fire Safety Certificate / NOC — Annexure-2 §2.1.v)
2. `building_completion_certificate` (Building Completion Certificate / Occupancy — Annexure-2 §2.1.iii)
3. `affidavit_2` (Affidavit on Non-Judicial Stamp Paper — Annexure-2 §2.1.i & Format 2)  
**Resolved Date / Owner:** 2026-10-25 / Person 3 (Approved)

### Q-003 — Required fields per document
**Status:** Resolved  
**Decision:** Standard field matrix defined and documented in `docs/AICTE_RULEBOOK_REFERENCE.md` and `docs/PERSON3_IMPLEMENTATION_PLAN.md`:
- `fire_safety_certificate`: `certificate_number`, `issuing_authority`, `issue_date`, `expiry_date`, `institution_name`, `institution_address`
- `building_completion_certificate`: `certificate_number`, `issuing_authority`, `issue_date`, `institution_name`, `institution_address`, `approved_built_up_area_sqm`
- `affidavit_2`: `affidavit_date`, `stamp_paper_value_inr`, `notary_registration_number`, `deponent_name`, `deponent_designation`, `institution_name`, `academic_year`  
**Resolved Date / Owner:** 2026-10-25 / Person 3 (Approved)

### Q-004 — File size and page limits
**Status:** Resolved  
**Decision:** Maximum file size: 10 MB per file. Maximum page count: 20 pages per document. Accepted formats: PDF, PNG, JPG/JPEG.  
**Resolved Date / Owner:** 2026-10-25 / Person 3 (Approved)

### Q-005 — Database confirmation
**Status:** Resolved  
**Decision:** PostgreSQL is the selected database for this project.  
**Next action:** Proceed with PostgreSQL; coordinate any proposed change before implementation.

### Q-006 — Deployment target
**Status:** Open  
**Question:** Will the final demo run locally, on one hosted server, or with separately hosted frontend/backend?  
**Next action:** Decide before deployment; ensure uploaded files and database storage persist where required.

## Change process
When a decision changes:
1. Mark the old decision as superseded rather than silently deleting its history.
2. Add the new decision, reason, date and person approving it.
3. Update affected project/API docs.
4. Notify every affected workstream before merging code.
