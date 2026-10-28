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

### D-014 — Authentication and role-based access control
**Status:** Accepted  
**Decision:** Implement authentication and role-based authorization with two explicit roles:
1. `INSTITUTION`: Self-registers, manages own applications, uploads documents to draft applications, runs preliminary validation on drafts, submits applications to AICTE, and views their validation reports. 1:1 institution per user account.
2. `REVIEWER`: AICTE scrutiny committee auditor. Read-only access to all *submitted* applications, documents, and reports; can audit findings and record verification determinations. Reviewers cannot self-register; they are provisioned via CLI seed script or one-time admin setup route (`POST /api/auth/admin/setup`) protected by `X-Admin-Setup-Token`.
3. Application lifecycle locking: Once submitted to AICTE, an application is locked (`status = 'submitted'`). Uploads and re-validation reject with 409 `APPLICATION_LOCKED`. Based on the report, institutions can initiate a new application revision prefilled from prior findings.
4. Security & Tokens: Stateless JWT access tokens (60 min default for demo UX) with rotating HTTP-only refresh tokens. Cross-tenant draft access returns 404 to prevent IDOR enumeration. Fail-fast validation enforces production secrets when `DEBUG=false`.  
**Reason:** Satisfies multi-tenant security requirements, human-in-the-loop review boundaries, and seamless demo UX without requiring external SSO infrastructure.  
**Date / Owner:** 2026-10-27 / Integration

### D-015 — Hybrid unresolved handling via engine interception
**Status:** Accepted  
**Decision:** Extends D-013. Unresolved handling is a hybrid, with the scrutiny engine intercepting by default. The engine intercepts any rule whose input field has OCR confidence below 0.70 and returns a standard system `unresolved` finding, which does not count as pass or flag and routes to the reviewer queue. Rules declare their input dependencies explicitly via `depends_on_fields` rather than deriving them from templates. Rules may optionally specify `unresolved_title`, `unresolved_reason_template`, and `unresolved_next_action` overrides when custom wording is necessary. Cross-document rules (e.g. `CONSISTENCY_001`) are marked `unresolved` if either side has low confidence. A missing field is a flag (or `FIELD_001`), whereas a low-confidence field is unresolved. `null` confidence (digital PDF extraction) is exempt and evaluated directly. Boundary tests: 0.69 -> unresolved, 0.70 -> evaluated, null -> evaluated. Tested with synthetic confidences since OCR is unverified.  
**Reason:** Avoids boilerplate `unresolved_*` templates across 30+ rules while keeping threshold testing centralized in one place.  
**Date / Owner:** 2026-10-28 / Product Owner

### D-016 — Reviewer override audit via dedicated append-only table
**Status:** Accepted  
**Decision:** Reviewer overrides are stored in a dedicated append-only `finding_audits` table, rather than columns on `Finding`. Columns: `id`, `finding_id`, `application_id`, `actor_user_id`, `actor_role`, `prior_status`, `new_decision`, `reason` (NOT NULL, minimum length enforced), `internal_note` (optional, reviewer-only), `created_at`, plus an immutable snapshot of `rule_id` and clause IDs so overrides survive finding re-generation. Append-only enforcement via database triggers or revoked UPDATE/DELETE grants. Gated strictly to `REVIEWER` role on submitted applications (D-014). The original finding `status` is never mutated; the current decision is derived from the latest audit row (or cached in a nullable column). Institutions have read-only visibility of reviewer determinations and the shared `reason` on their own submitted applications; the optional `internal_note` column is restricted to reviewer visibility.  
**Reason:** Scrutiny audit trail must preserve original automated signals and maintain a complete, tamper-evident history of multiple successive reviewer determinations while supporting internal scrutiny notes.  
**Date / Owner:** 2026-10-28 / Product Owner

### D-017 — Compound condition logic for declarative rules
**Status:** Accepted  
**Decision:** Extend `RuleCondition` to support compound boolean logic via `all_of` and `any_of` lists of child `RuleCondition` objects. Requirements:
1. Nesting Depth: Maximum nesting depth capped at 3; enforced at startup during YAML loading/validation.
2. Three-Valued Logic: Follows Kleene-style three-valued logic incorporating `unresolved` (D-015):
   - `all_of`: Evaluates to `false` if any operand is false; `unresolved` if none is false and at least one operand is unresolved; `true` otherwise.
   - `any_of`: Evaluates to `true` if any operand is true; `unresolved` if none is true and at least one operand is unresolved; `false` otherwise.
3. Operators: Support conditions for document presence, field existence/comparisons, and age greater than N (`date_gt_years`).
4. Boundary Tests: Unit test all truth tables, nesting limits, and boundary conditions.
5. `STRUCTURAL_001` Target: Once compound conditions are implemented, `STRUCTURAL_001`'s pass condition becomes `any_of: [age <= 30, structural_stability_certificate present, competent_authority_letter present]`.  
**Reason:** Enables expressive, declarative rule modelling for compound statutory criteria without code duplication or hardcoded Python branching.  
**Date / Owner:** 2026-10-28 / Product Owner

### D-018 — Age and expiry reference date semantics
**Status:** Accepted  
**Decision:** Deterministic reference date evaluation for temporal scrutiny rules:
1. Scrutiny Reference Date:
   - For submitted applications: Use `application.submitted_at.date()`.
   - For draft applications: Use current calendar date at evaluation time (`date.today()`).
   - Do NOT use `application.created_at` (a draft created in January and submitted in March must not be evaluated against January dates).
2. Deterministic Injection: The reference date is computed at application context level and injected into the rule execution engine as a parameter; rules must NOT invoke `date.today()` internally.
3. Finding Transparency: Every temporal finding (including `STRUCTURAL_001` and `EXPIRY_001`) must explicitly include the reference date used for evaluation in its finding reason and evidence dictionary.
4. Application Deadline Exception: For clauses referencing AICTE application deadlines (e.g. the 50-year government building exception referencing "last date of application"), support an optional per-academic-year configuration parameter (`last_date_of_application`) without inventing placeholder dates.  
**Reason:** Prevents stale-draft false passes, eliminates time-of-day non-determinism in CI test fixtures, and provides clear audit trails for institutions and scrutiny officers.  
**Date / Owner:** 2026-10-28 / Product Owner

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
