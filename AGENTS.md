# AGENTS.md — SIH 2026 PS 26261 — Application Validation & Document Compliance Verification

## 1. Project purpose
Build a small, reliable prototype for SIH 2026 Problem Statement 26261: preliminary validation of institutional application documents. The prototype supports reviewers by extracting selected information, running explicit validation rules, and presenting evidence-linked findings. It does **not** make final AICTE approval decisions and does not prove that a document is authentic.

Read `docs/PROJECT_CONTEXT.md`, `docs/API_CONTRACT.md`, `docs/TASKS.md`, and `docs/DECISIONS.md` before making changes. If using an AI coding tool that does not automatically load this file, explicitly instruct it: “Read AGENTS.md and the relevant docs files before editing.”

## 2. Agreed stack
- Frontend: React + Vite + Tailwind CSS.
- Backend: Python + FastAPI.
- OCR: PaddleOCR.
- PDF processing: PyMuPDF (`fitz`) for extracting selectable PDF text and rendering pages when OCR is needed.
- Database: PostgreSQL (selected project stack).
- Data validation: Pydantic for API schemas; custom Python rules for compliance checks.
- File storage for the prototype: local `backend/uploads/` directory, excluded from Git.
- Version control: Git + GitHub.

Do not replace these technologies without discussing the change with the team and recording the decision in `docs/DECISIONS.md`.

## 3. Workstream ownership
The team is divided into three workstreams. These are ownership boundaries, not permission to ignore integration.

### Person 1 — Frontend (`frontend/`)
Owns:
- React screens and reusable UI components.
- Application creation form and document upload interface.
- Required-document checklist, extracted-field display, validation findings, overall status.
- API calls and loading/error/empty states.
- Frontend styling and responsive layout.

Do not implement compliance rules in the frontend. Display results returned by the backend; do not hardcode final findings as if they came from real validation.

### Person 2 — OCR and extraction (`backend/app/services/ocr_service.py`, `pdf_processor.py`, `field_extractor.py`)
Owns:
- PaddleOCR integration and model initialization.
- Digital-PDF text extraction and scanned-PDF rendering.
- Image preprocessing only when necessary.
- Extraction of the selected fields for supported document types.
- OCR/extraction failure handling and tests.

Return structured data using the schema in `docs/API_CONTRACT.md`. Do not invent extracted values. Missing or uncertain values must be represented explicitly.

### Person 3 — Backend and validation (`backend/app/`, excluding the OCR/extraction modules owned by Person 2)
Owns:
- FastAPI routes and application workflow.
- PostgreSQL schema and persistence.
- File upload validation and local file storage.
- Required-document checklist and custom Python validation engine.
- Cross-document checks, validation status, report responses and backend error handling.
- Integration of Person 2's extraction module.

## 4. Shared responsibilities
- All people must agree on API/schema changes before implementing them.
- All people help with integration and end-to-end testing.
- Every person must test their module independently before merging.
- Use synthetic institutional data for the demo.
- Use official, applicable AICTE requirements as the source for the selected checklist. Do not invent regulatory requirements.
- Flag uncertainty for human review rather than treating it as proof of fraud.
- Keep the MVP small. Optional features are not allowed to delay the core workflow.

## 5. Git and collaboration rules
- Create a branch for each task or workstream, for example `feat/frontend-upload`, `feat/paddleocr-extraction`, or `feat/validation-rules`.
- Use descriptive commit messages, e.g. `feat: add document upload endpoint`.
- Do not commit `.env`, secrets, database credentials, real personal/institutional documents, model caches, virtual environments, `node_modules/`, build output, or uploaded files.
- Keep `.env.example` updated with variable names only; never put real secrets in it.
- Do not rewrite shared history or force-push to the shared branch unless the team explicitly agrees.
- Open a pull request or ask for a review before merging shared changes.
- If changing a shared schema, update `docs/API_CONTRACT.md` in the same change and tell all affected owners.
- Avoid editing another person's owned module without coordinating first.
- Keep commits small enough to review.

## 6. Integration rules
- The API contract in `docs/API_CONTRACT.md` is the source of truth for JSON field names and status values.
- Frontend must use the contract's field names exactly; do not independently rename fields.
- OCR/extraction code must return the agreed structure even when fields are missing.
- Backend must not report a check as passed if it could not run.
- Distinguish `missing`, `flagged`, `unresolved`, `pass`, and `not_applicable`.
- Store the document type explicitly; do not infer it only from a filename.
- Dates must use ISO format (`YYYY-MM-DD`) when represented as structured date values. Preserve the original extracted text as evidence.
- A report must be generated from actual processing/validation results. Mock data is allowed only during isolated frontend development and must be clearly identified as mock data.

## 7. Definition of done
A change is done when:
1. It implements only the agreed scope.
2. It follows the API contract and naming conventions.
3. It handles expected failure cases.
4. It has been tested locally (or has documented reason why not).
5. It does not expose secrets or commit uploaded documents.
6. Relevant docs are updated.
7. The owner explains any integration impact to the team.

## 8. Scope guardrails
Do not add these to the Basic MVP unless the core workflow is complete and the team agrees:
- User authentication or role-based permissions.
- Multiple application categories.
- Real AICTE/issuing-authority integrations or restricted database access.
- Automated final approval/rejection.
- AI-based forgery detection or claims that a document is authentic.
- Complex analytics, predictive risk scoring, email alerts, or configurable rules UI.
- PDF report export, duplicate detection, audit history, or evidence highlighting.

## 9. When blocked
First reproduce the problem with a small test. Check the relevant docs and current code. Share the exact error, expected behavior, actual behavior, and steps to reproduce with the owner of the affected module. Do not silently change a shared interface to work around a mismatch.
