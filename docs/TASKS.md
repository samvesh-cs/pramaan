# TASKS.md — Workstreams and Integration Checklist

## Team structure
Use three workstreams. Replace Person 1/2/3 with actual names in the team copy if useful.

## Person 1 — Frontend
- [ ] Create React + Vite + Tailwind project.
- [ ] Build application creation form.
- [ ] Build document upload UI with selected document type.
- [ ] Show required-document checklist and missing types.
- [ ] Show document processing state and useful error messages.
- [ ] Show extracted fields and evidence snippets.
- [ ] Show validation findings, reasons and next actions.
- [ ] Show overall status using the API contract's status values.
- [ ] Connect frontend to the agreed API endpoints.
- [ ] Use mock data only until APIs are ready; label mock mode clearly and remove it for the final demo.
- [ ] Test loading, empty, error and success states.
- [ ] Verify the frontend works with actual backend responses.

## Person 2 — PaddleOCR and document extraction
- [ ] Set up a Python virtual environment and document compatible Python/PaddlePaddle/PaddleOCR versions.
- [ ] Test PaddleOCR independently on one image.
- [ ] Use PyMuPDF to extract selectable text from digital PDFs.
- [ ] Render scanned PDF pages to images and run PaddleOCR.
- [ ] Process JPG and PNG images.
- [ ] Extract only fields needed for the selected document types.
- [ ] Return the exact internal data structure in `API_CONTRACT.md`.
- [ ] Preserve raw text snippets, page numbers, confidence when available, and bounding boxes when available.
- [ ] Represent uncertain/missing fields explicitly; never invent values.
- [ ] Handle unreadable, corrupt and unsupported documents without crashing.
- [ ] Add tests using the agreed sample documents.
- [ ] Tell Person 3 how to call the module and what errors it can return.

## Person 3 — FastAPI, database and validation
- [x] Create FastAPI application and `/api` routes.
- [x] Confirm selected application category and official checklist source.
- [x] Define PostgreSQL tables and relationships for applications, documents, extracted fields/runs, and findings.
- [x] Configure environment variables and `.env.example`.
- [x] Implement application creation and retrieval.
- [x] Implement upload validation and local file storage.
- [x] Integrate Person 2's extraction module. (Integrated app.ocr with PyMuPDF selectable text + PaddleOCR 3.x into app.services.ocr_service; real synthetic samples tested).
- [x] Implement the required-document checklist.
- [x] Implement missing-field, expiry and cross-document consistency rules.
- [x] Generate findings in the API contract format.
- [x] Calculate overall application status consistently.
- [x] Implement report retrieval.
- [x] Handle API errors without leaking stack traces.
- [x] Add backend tests for routes and validation rules (14 tests passing).
- [x] Share API docs and test results with Person 1.

## Shared sample data and testing
- [x] Confirm one application category before writing rules. (EoA Self-Disclosure confirmed)
- [x] Confirm two or three representative document types from the applicable official AICTE checklist. (Fire Safety, Building Completion, Affidavit-2)
- [x] Record the official source/handbook clause and applicability for every requirement. (docs/AICTE_RULEBOOK_REFERENCE.md)
- [x] Create synthetic valid sample documents. (backend/tests/samples/ and backend/tests/test_samples/)
- [x] Create defective samples: missing document, expired date, missing field, cross-document mismatch, unreadable scan, invalid file. (corrupt_doc.pdf, empty_doc.pdf, password_protected.pdf, etc.)
- [ ] Write expected outcomes before running the system.
- [ ] Compare actual findings against expected outcomes and record mistakes.
- [ ] Test a complete application through the real frontend and backend.
- [ ] Test repeat validation and ensure results do not mix across applications.
- [ ] Rehearse the demo and keep a backup recording.

## Integration checkpoints
### Checkpoint 1 — Contract agreed
- [x] Category, document types, fields, status values and API shapes agreed.
- [x] `API_CONTRACT.md` reviewed by all owners.

### Checkpoint 2 — OCR proof
- [x] At least one representative image and one representative PDF processed.
- [x] Extracted field format matches the contract.

### Checkpoint 3 — Backend API proof
- [x] Application can be created.
- [x] Document can be uploaded and stored.
- [x] OCR/extraction result is returned or stored.

### Checkpoint 4 — Validation proof
- [x] A valid test case passes selected checks.
- [x] A defective test case produces the expected finding.
- [x] Unreadable/missing values become unresolved, not pass.

### Checkpoint 5 — End-to-end demo
- [ ] Frontend uses real API responses.
- [ ] Checklist, extracted fields, findings and overall status agree.
- [ ] Invalid uploads and OCR failures show understandable messages.
- [ ] No final result depends on hardcoded findings.

## Daily team update
Each owner reports:
1. Done since the last update.
2. Next concrete deliverable.
3. Blocker and exact error (if any).
4. Whether any shared API/schema change is needed.
