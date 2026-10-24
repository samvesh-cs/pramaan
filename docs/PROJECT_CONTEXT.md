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
- Create one sample institutional application.
- Upload PDF and image documents.
- Required-document checklist and missing-document detection.
- OCR/text extraction using PaddleOCR when needed.
- Basic field extraction for selected supported document types.
- Expiry and completeness checks where applicable.
- Cross-document consistency checks.
- Validation report with finding, reason, affected document, evidence, and next action.
- One basic reviewer view.
- Overall validation status showing missing documents, discrepancies, and unresolved checks.
- Basic error handling for invalid uploads, unsupported types, and failed OCR.
- Synthetic test data with known expected outcomes and recorded evaluation results.

## 5. Application category and checklist
The team must confirm and record the selected application category before implementing regulatory rules. Extension of Approval (EoA) for an existing institution is a candidate because it is a recurring workflow, but the choice must be confirmed against the relevant current official AICTE handbook and notices.

The required-document checklist must come from the applicable official AICTE requirement for the chosen category and route. A requirement may be:
- `required`
- `required_if_applicable`
- `not_applicable`

Do not treat every document mentioned in general research as universally mandatory. Applicability can depend on category, institution type, circumstances, and current official instructions. Record the handbook year/clause or official source for each configured requirement.

Use synthetic names and values in the demo. Clearly label them as synthetic.

## 6. Recommended technology stack
- Frontend: React, Vite, Tailwind CSS.
- Backend: Python, FastAPI.
- OCR: PaddleOCR.
- PDF processing: PyMuPDF.
- Database: PostgreSQL (selected project stack).
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
- Authentication/role-based access unless explicitly required by the demo environment.
- Duplicate detection, OCR evidence highlighting, configurable-rules UI, audit history, PDF report export, email alerts, or resubmission workflow. These are optional future features and must not delay the core workflow.

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
