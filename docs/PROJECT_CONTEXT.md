# PROJECT_CONTEXT.md — SIH 2026 PS 26261

## 1. Project summary
**Project:** AI-powered Application Validation and Document Compliance Verification — SIH 2026 Problem Statement 26261  
**Purpose:** AI-powered preliminary institutional application validation and document compliance verification.  
**MVP scope:** A preliminary document-scrutiny prototype for one institutional application category and two or three representative document types, using synthetic institutional data.

The prototype accepts an institutional application and its supporting documents, extracts selected information, runs explicit checks, and produces an evidence-linked report for a human reviewer.

**Important limitation:** The prototype supports preliminary scrutiny only. It does not make final AICTE approval decisions, establish legal authenticity, or claim to detect forgery reliably.

## 2. Problem being addressed
Institutional applications may include multiple documents whose presence, required fields, dates, and identifying details need to be reviewed. Manual scrutiny can be time-consuming. The prototype helps a reviewer identify potential deficiencies consistently and understand why each issue was raised.

## 3. Intended demo flow
1. Create one sample institutional application under the chosen category.
2. Upload two or three supported PDF/image documents.
3. Compare uploaded document types with the category's required-document checklist.
4. Process files:
   - For a digital PDF, try extracting selectable text with PyMuPDF.
   - For scanned PDFs, render pages to images and use PaddleOCR.
   - For JPG/PNG, use PaddleOCR directly.
5. Extract only the selected fields for the supported document types, such as institution name, document number, and applicable issue/expiry dates.
6. Run validation checks:
   - Missing required document.
   - Missing required field.
   - Expired document, where expiry applies.
   - Cross-document institution-name or identifier mismatch.
   - Unresolved check when extraction is missing or too uncertain to support a reliable result.
7. Show the reviewer a report containing each finding, reason, affected document, supporting evidence, and suggested next action.
8. Show the overall status and handle invalid files or processing failures without crashing.
9. Demonstrate the same workflow on valid and deliberately defective synthetic test cases.

## 4. Basic MVP features — in scope
- Authentication and role-based access control with two roles: `INSTITUTION` and `REVIEWER`.
- Create institutional applications linked to authenticated institution accounts (1:1 institution mapping).
- Application lifecycle state management: `draft` (institution uploads/validates) -> `submitted` (locked for AICTE committee review).
- Resubmission workflow: institutions can spawn a new application revision prefilled from prior report findings.
- Upload PDF and image documents (with server-side MIME and magic-byte checks).
- Required-document checklist and missing-document detection.
- OCR/text extraction using PaddleOCR when needed.
- Basic field extraction for selected supported document types.
- Expiry and completeness checks where applicable.
- Cross-document consistency checks.
- Validation report with finding, reason, affected document, evidence, and next action.
- Scrutiny queue and human-in-the-loop audit verification decisions for AICTE reviewers.
- Overall validation status showing missing documents, discrepancies, and unresolved checks.
- Basic error handling for invalid uploads, unsupported types, and failed OCR.
- Synthetic test data with known expected outcomes and recorded evaluation results.

## 5. Application category and checklist
The selected category is Extension of Approval (EoA) — Self-Disclosure for existing institutions, recorded in `docs/DECISIONS.md` and referenced in `docs/AICTE_RULEBOOK_REFERENCE.md`.

The prototype configures three representative EoA document types from the recorded APH 2024-2027 clauses: Fire Safety Certificate, Building Completion/Occupancy Certificate, and Affidavit-2. This is an MVP subset, not a complete EoA checklist. A requirement may be:
- `required`
- `required_if_applicable`
- `not_applicable`

Do not treat every document mentioned in general research as universally mandatory. Applicability can depend on category, institution type, circumstances, and current official instructions. Record the handbook year/clause or official source for each configured requirement.

Use synthetic names and values in the demo. Clearly label them as synthetic.

## 6. Recommended technology stack
- Frontend: React, Vite, Tailwind CSS.
- Backend: Python, FastAPI.
- Authentication: JWT (HS256) access tokens + HTTP-only rotating refresh tokens + bcrypt password hashing.
- OCR: PaddleOCR.
- PDF processing: PyMuPDF.
- Database: PostgreSQL (with SQLite compatibility for local/test environments via Alembic).
- API/data schemas: Pydantic.
- Validation: custom Python rule functions using standard libraries such as `re` and `datetime`.
- File storage: local files under `backend/uploads/` for the prototype.
- Version control: Git + GitHub.

Avoid adding extra services unless a demonstrated requirement justifies them.

## 7. Out of scope for the Basic MVP
- Multiple application categories or support for every AICTE route.
- Real integration with restricted AICTE databases or issuing authorities.
- Automated approval/rejection decisions.
- Claims that OCR or visual checks prove authenticity or forgery.
- Advanced AI-based forgery detection.
- Complex analytics, predictive risk scoring, or large infrastructure image/video analysis.
- Multi-factor authentication (MFA) or SSO/DigiLocker integration.

## 7a. Authentication, Roles & Scrutiny Security Model
- **Two Defined Roles:**
  - `INSTITUTION`: Educational college user. Self-registers, creates and manages only their own applications, uploads documents to draft applications, runs preliminary validation on drafts, submits applications to AICTE, and views their validation reports.
  - `REVIEWER`: Official AICTE scrutiny committee member. Read-only access to all *submitted* applications, documents, extracted fields, and reports. Reviews findings, records human-in-the-loop decisions (`verified`, `confirmed_discrepancy`, `requested_resubmission`, `escalated`). Reviewers cannot self-register.
- **Provisioning Reviewers:** Reviewers are provisioned via the idempotent CLI seed script (`scripts/seed_reviewer.py`) or via the one-time admin setup endpoint (`POST /api/auth/admin/setup`) authenticated with `X-Admin-Setup-Token`.
- **Session Architecture:** Short-lived access tokens (60 min default for demo UX) with rotating refresh tokens stored in secure, HTTP-only cookies with token family reuse detection.
- **Application Locking & Resubmission:** Once submitted to AICTE, an application is locked (`status = 'submitted'`). Uploads (`POST .../documents`) and re-validation (`POST .../validate`) reject with 409 `APPLICATION_LOCKED`. Based on the scrutiny report, institutions can initiate a new application prefilled from the previous report.
- **IDOR Protection:** Cross-tenant access to draft applications or unowned applications returns HTTP 404 (not 403) to prevent resource enumeration.
- **Fail-Fast Security:** In non-debug mode (`DEBUG=false`), the application strictly refuses to start if `JWT_SECRET_KEY` is using the development default.

## 8. Accuracy and reviewer principles
- OCR output is not guaranteed to be correct.
- Preserve extracted text snippets as evidence and keep the source document/page reference where available.
- An OCR failure or uncertain field must become `unresolved`, not a pass.
- A mismatch is a discrepancy to review, not proof of fraud.
- A signature-looking mark is not proof of valid digital signature or signer identity.
- Do not claim tested accuracy percentages without actual labelled test results.
- The system assists a human reviewer; it does not replace official scrutiny.

## 9. MVP completion criteria
The MVP is demonstrable when:
- A reviewer can create an application and upload supported documents.
- The required-document checklist identifies missing types.
- Supported documents are processed and selected fields are extracted.
- The selected rules produce correct findings on labelled valid and defective test cases.
- Every finding includes a reason, affected document, evidence when available, and suggested next action.
- The overall status is consistent with the individual findings.
- Invalid files and processing failures are handled without crashing.
- The team can explain the limitations and show actual results rather than hardcoded findings.
