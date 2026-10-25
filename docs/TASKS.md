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
- [x] Set up a Python virtual environment and document compatible Python/PaddlePaddle/PaddleOCR versions.
- [x] Test PaddleOCR independently on one image.
- [x] Use PyMuPDF to extract selectable text from digital PDFs.
- [x] Render scanned PDF pages to images and run PaddleOCR.
- [x] Process JPG and PNG images.
- [x] Extract only fields needed for the selected document types.
- [x] Return the exact internal data structure in `API_CONTRACT.md`.
- [x] Preserve raw text snippets, page numbers, confidence when available, and bounding boxes when available.
- [x] Represent uncertain/missing fields explicitly; never invent values.
- [x] Handle unreadable, corrupt and unsupported documents without crashing.
- [x] Add tests using the agreed sample documents.
- [x] Tell Person 3 how to call the module and what errors it can return.

## Person 3 — FastAPI, database and validation
- [ ] Create FastAPI application and `/api` routes.
- [ ] Confirm selected application category and official checklist source.
- [ ] Define PostgreSQL tables and relationships for applications, documents, extracted fields/runs, and findings.
- [ ] Configure environment variables and `.env.example`.
- [ ] Implement application creation and retrieval.
- [ ] Implement upload validation and local file storage.
- [ ] Integrate Person 2's extraction module.
- [ ] Implement the required-document checklist.
- [ ] Implement missing-field, expiry and cross-document consistency rules.
- [ ] Generate findings in the API contract format.
- [ ] Calculate overall application status consistently.
- [ ] Implement report retrieval.
- [ ] Handle API errors without leaking stack traces.
- [ ] Add backend tests for routes and validation rules.
- [ ] Share API docs and test results with Person 1.

## Shared sample data and testing
- [ ] Confirm one application category before writing rules.
- [ ] Confirm two or three representative document types from the applicable official AICTE checklist.
- [ ] Record the official source/handbook clause and applicability for every requirement.
- [ ] Create synthetic valid sample documents.
- [ ] Create defective samples: missing document, expired date, missing field, cross-document mismatch, unreadable scan, invalid file.
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
- [ ] Application can be created.
- [ ] Document can be uploaded and stored.
- [ ] OCR/extraction result is returned or stored.

### Checkpoint 4 — Validation proof
- [ ] A valid test case passes selected checks.
- [ ] A defective test case produces the expected finding.
- [ ] Unreadable/missing values become unresolved, not pass.

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
