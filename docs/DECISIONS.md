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

## Open questions — resolve before implementing rules

### Q-001 — Application category
**Status:** Open  
**Question:** Are we selecting Extension of Approval (EoA) for an existing institution, or another category?  
**Next action:** Confirm with the team and verify the current official AICTE handbook and applicable notice.

### Q-002 — Document types
**Status:** Open  
**Question:** Which two or three document types will be supported?  
**Next action:** Select them from the chosen category's applicable official checklist. Record conditional applicability and the source clause.

### Q-003 — Required fields per document
**Status:** Open  
**Question:** Which fields will be extracted for each chosen document type?  
**Next action:** Make a small field matrix; do not extract fields that are not used by a rule or report.

### Q-004 — File size and page limits
**Status:** Open  
**Question:** What maximum file size and page count should be accepted for the demo?  
**Next action:** Set limits that fit the development machine and test documents; document them in the README.

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
