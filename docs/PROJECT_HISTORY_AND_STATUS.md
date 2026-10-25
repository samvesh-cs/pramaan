# PROJECT_HISTORY_AND_STATUS.md — SIH 2026 PS 26261

> **Document Purpose:**  
> This file is an exhaustive, self-contained project history and status report. It is designed to be passed directly to another AI assistant or incoming engineer so they can immediately understand what has been completed, how modules are architected, what tests have run, and what remains to be built next.

---

## 1. Project Background & Core Guardrails

- **Problem Statement:** SIH 2026 Problem Statement 26261 — *AI-powered Institutional Application Validation and Document Compliance Verification*.
- **Domain:** AICTE (All India Council for Technical Education) institutional approval scrutiny (e.g., Extension of Approval — EoA).
- **Core Purpose:** Automated preliminary document scrutiny for human reviewers. The system ingests institutional application packages (PDFs and scanned images), extracts key compliance metadata, executes explicit rule-based validation checks, and presents evidence-backed findings to a reviewer.
- **Strict Guardrails (from [AGENTS.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/AGENTS.md)):**
  1. **Preliminary Scrutiny Only:** The tool assists reviewers. It does **not** make final approval/rejection decisions and does **not** claim to prove document authenticity or forgery.
  2. **Rule-Based Validation:** Validation rules are written in deterministic Python logic (Pydantic + explicit checks); no unexplainable LLM hallucinations for compliance rules.
  3. **Explicit Uncertainty:** Any unreadable, corrupt, missing, or low-confidence values are flagged as `unresolved` or `flagged` for human review, never silently passed or invented.
  4. **Strict Technology Stack:**
     - **Frontend:** React + Vite + Tailwind CSS.
     - **Backend:** Python + FastAPI.
     - **OCR & Document Processing:** PaddleOCR 3.x + PyMuPDF (`fitz`).
     - **Database:** PostgreSQL.
     - **Validation:** Pydantic API schemas + custom Python rules engine.
     - **Storage:** Local filesystem under `backend/uploads/` (excluded from git).

---

## 2. Git History & Current Repository State

- **Active Branch:** `aditya-work`
- **Current Commit History:**
  1. `34c498d` — **Architecture**: Initialized repository structure, established `.gitignore`, defined team ownership boundaries in [AGENTS.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/AGENTS.md), authored comprehensive specifications:
     - [docs/PROJECT_CONTEXT.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/docs/PROJECT_CONTEXT.md): Scope, problem statement, demo flow, in-scope MVP features.
     - [docs/API_CONTRACT.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/docs/API_CONTRACT.md): Contract source of truth for endpoints, JSON schemas, status codes, and data structures.
     - [docs/DECISIONS.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/docs/DECISIONS.md): Architectural Decision Records (ADRs D-001 through D-012) and open questions.
     - [docs/TASKS.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/docs/TASKS.md): Workstream assignments and integration checkpoints.
  2. `ffb519e` — **Extraction**: Fully implemented the OCR & Document Extraction Pipeline (Person 2 workstream), synthetic sample generators, ground truth datasets, and evaluation harnesses.
- **Git Tree State:** Working directory is clean, 1 commit ahead of `origin/aditya-work`.

---

## 3. Workstream Division & Progress Matrix

| Workstream | Owner | Scope | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Workstream 2: OCR & Document Extraction** | Person 2 | PaddleOCR, PyMuPDF, field extractors, robust error handling, test evaluation | **100% COMPLETE** | Fully implemented, tested on Windows CPU, achieves 100% test pass rate across 8 test conditions. |
| **Workstream 3: Backend & Validation** | Person 3 | FastAPI REST API, PostgreSQL schema & migrations, upload handler, rule engine, report generator | **PENDING** | Integration ready. Person 2 module is packaged with a clean, single-function facade `process_document()`. |
| **Workstream 1: Frontend Reviewer Portal** | Person 1 | React + Vite + Tailwind CSS dashboard, application wizard, document uploader, evidence findings viewer | **PENDING** | UI contract defined in `API_CONTRACT.md`. Ready for scaffold & implementation. |

---

## 4. Completed Workstream 2 (OCR & Extraction) Deep Dive

All extraction code is located in [`backend/app/ocr/`](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/backend/app/ocr/):

### 4.1 Data Models (`backend/app/ocr/models.py`)
Compliant 1:1 with Section 5 of [docs/API_CONTRACT.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/docs/API_CONTRACT.md):
- `Region`: Holds `text: str`, optional `confidence: Optional[float]`, and bounding box `bbox: Optional[List[float]]` (`[x1, y1, x2, y2]`).
- `PageResult`: Holds `page_number: int`, full page `text: str`, and `regions: List[Region]`.
- `ExtractedField`: Holds extracted `value: Optional[Any]`, `normalized_value: Optional[Any]`, `raw_text: Optional[str]` (original unparsed snippet for reviewer audit trail), `confidence: Optional[float]`, `page_number: Optional[int]`, and `bbox: Optional[List[float]]`.
- `ExtractionResult`: Root object with `document_id`, `document_type`, `processing_status` (`"processed"` | `"processing_failed"`), `pages: List[PageResult]`, `fields: Dict[str, ExtractedField]`, and `error: Optional[str]`.

### 4.2 OCR Engine Wrapper (`backend/app/ocr/ocr_service.py`)
- **Library:** PaddleOCR 3.7.0 with PaddlePaddle 3.3.1 (CPU mode on Windows).
- **Critical Stability Fix:** Addressed a critical crash on Windows CPU where PaddlePaddle 3.3.x fails with a PIR-to-oneDNN conversion error (`ConvertPirAttribute2RuntimeAttribute`). Resolved by initializing `PaddleOCR(..., enable_mkldnn=False)`.
- **API Modernization:** Updated to PaddleOCR 3.x patterns: replaced deprecated `ocr()` calls with `predict()` generator yielding `rec_texts`, `rec_scores`, and `rec_polys`.
- **Input Flexibility:** Accepts image filepaths (`str`) as well as in-memory raw PNG bytes rendered from PDFs (auto-converted to NumPy RGB ndarrays via Pillow).
- **Coordinates:** Converts 4-point polygon coordinates (`rec_polys`) to clean axis-aligned `[x1, y1, x2, y2]` bounding boxes.

### 4.3 PDF & Image Processing (`backend/app/ocr/pdf_processor.py`)
- **Hybrid Extraction Architecture:**
  1. Opens PDF pages using PyMuPDF (`fitz`).
  2. Extracts digital text blocks with exact coordinate bounding boxes (`extract_selectable_text`). Following contract rules, `confidence` is explicitly set to `None` for native digital text to prevent fabricating artificial confidence scores.
  3. **Scanned Page Detection:** Computes alphanumeric character density (`sum(c.isalnum() for c in text)`). If text is sparse (< 50 characters), the page is detected as a scan or image-based PDF.
  4. Automatically renders the page pixmap at 150 DPI and invokes `run_ocr_on_image()` as an automatic fallback.
- **Direct Image Processing:** Processes standalone `.png`, `.jpg`, and `.jpeg` images via `process_image_file()`.

### 4.4 Rule-Based Field Extraction (`backend/app/ocr/field_extractor.py`)
Extracts compliance metadata for the three supported representative institutional document types:
1. `fire_safety_certificate`:
   - `institution_name`
   - `document_number` (NOC / Certificate number)
   - `issue_date`
   - `expiry_date`
2. `structural_stability_certificate`:
   - `institution_name`
   - `document_number`
   - `engineer_license_number`
   - `issue_date`
   - `expiry_date`
3. `land_title_deed`:
   - `institution_name`
   - `document_number` (Deed / Registration / Khasra number)
   - `land_area` (parsed with units, e.g., "10.5 Acres", "Square Meters")
   - `issue_date`
4. **Fallback Generic Document:** Extracts basic document number, issue date, and expiry date.
- **Date Normalization:** Robust multi-format parsing converting varied formats (e.g., `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`, `DD Month YYYY`) into standardized ISO `YYYY-MM-DD`, while preserving the exact `raw_text` snippet for human audit.
- **Evidence Linking:** `find_region_for_text()` matches extracted field tokens back to page regions to retrieve accurate bounding boxes and confidence scores.

### 4.5 Orchestrator Facade (`backend/app/ocr/processor.py`)
Provides the unified, crash-proof entry point:
```python
def process_document(
    file_path: Union[str, Path],
    document_type: Optional[str] = None,
    document_id: Optional[str] = None
) -> ExtractionResult
```
- **Resilience Guarantees:** Never crashes or raises unhandled exceptions. If given a non-existent path, corrupt PDF, unsupported filetype (e.g., `.docx`), empty file, or password-protected PDF, it returns `processing_status="processing_failed"` accompanied by a clear, human-readable error string in `error`.
- **Automatic Document Inference:** Uses keyword heuristics if `document_type` is omitted or unselected.

---

## 5. Synthetic Datasets & Evaluation Results

All testing scripts, samples, and results are located in [`backend/tests/`](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/backend/tests/):

### 5.1 Test Suite Structure
- `generate_synthetic_test_set.py`: Programmatically generates clean PDFs, scanned image simulations, low-quality noisy/rotated images, multi-page PDFs, and edge-case defective files.
- `ground_truth.json`: Defines expected processing statuses, document types, categories, and field key-value pairs for 8 test cases.
- `evaluate_synthetic_set.py`: Automated test runner that executes `process_document()` across all test cases and writes detailed comparative results to `evaluation_results.json`.

### 5.2 Evaluation Scorecard (100% Pass Rate)

| Test File | Category | Expected Status | Actual Status | Field Extraction Accuracy | Error Handling | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `clean_fire_safety.pdf` | Clean digital PDF | `processed` | `processed` | 4/4 exact matches (`institution_name`, `document_number`, `issue_date`, `expiry_date`) | N/A | **PASS** |
| `scanned_structural_stability.png` | Scanned-style image | `processed` | `processed` | 5/5 exact matches (avg confidence > 0.99) | N/A | **PASS** |
| `low_quality_land_deed.png` | Low-quality noisy/rotated image | `processed` | `processed` | 4/4 exact matches (`land_area: 10.5 Acres`, avg conf > 0.99) | N/A | **PASS** |
| `multipage_structural_stability.pdf` | Multi-page PDF | `processed` | `processed` | 5/5 exact matches across pages | N/A | **PASS** |
| `corrupt_doc.pdf` | Corrupt header/bytes | `processing_failed` | `processing_failed` | 0 fields expected | `Document parsing error: cannot open broken document` | **PASS** |
| `empty_doc.pdf` | 0-byte file | `processing_failed` | `processing_failed` | 0 fields expected | `Document parsing error: cannot open broken document` | **PASS** |
| `unsupported_format.docx` | Unsupported extension | `processing_failed` | `processing_failed` | 0 fields expected | `Unsupported file type '.docx'. Supported types: .jpeg, .jpg, .pdf, .png` | **PASS** |
| `password_protected.pdf` | Encrypted PDF | `processing_failed` | `processing_failed` | 0 fields expected | `Document parsing error: document is password-protected` | **PASS** |

---

## 6. Guide for the Next AI / Developer: How to Continue

### 6.1 Integrating the OCR Module (For Person 3 / Backend)
Person 3 does **not** need to touch internal PaddleOCR details. Simply import and call the high-level processor:

```python
from app.ocr import process_document

# Call during document upload or validation trigger:
result = process_document(
    file_path="uploads/app_001/doc_001_fire_safety.pdf",
    document_type="fire_safety_certificate",
    document_id="doc_001"
)

if result.processing_status == "processing_failed":
    # Record failed extraction run and flag check as 'unresolved'
    print(f"Extraction failed: {result.error}")
else:
    # Access structured fields
    inst_name = result.fields["institution_name"].value
    exp_date = result.fields["expiry_date"].value  # ISO 'YYYY-MM-DD'
    raw_evidence = result.fields["expiry_date"].raw_text
    confidence = result.fields["expiry_date"].confidence
```

### 6.2 What Person 3 (Backend & Validation) Must Implement Next
1. **FastAPI Application (`backend/app/main.py`):**
   - Endpoints specified in [docs/API_CONTRACT.md](file:///c:/Users/admin/Desktop/sih-prototype-main/sih-prototype-main/docs/API_CONTRACT.md):
     - `POST /api/applications` (create institutional application)
     - `GET /api/applications/{id}` (fetch application status and checklist)
     - `POST /api/applications/{id}/documents` (`multipart/form-data` upload with type validation and local disk saving)
     - `POST /api/applications/{id}/validate` (run compliance rules engine)
     - `GET /api/applications/{id}/report` (fetch structured validation report)
2. **PostgreSQL Database Schema:**
   - Tables: `applications`, `documents`, `extraction_runs`, `extracted_fields`, `findings`.
3. **Deterministic Python Validation Engine:**
   - **Document Presence Rule:** Check uploaded document types against required checklist for the application category.
   - **Completeness Rule:** Check if mandatory fields (e.g. `document_number`, `expiry_date`) exist in extraction results; if missing/unreadable, emit finding with status `unresolved`.
   - **Expiry Date Rule:** Compare `expiry_date` against application cutoff/review date.
   - **Cross-Document Consistency Rule:** Compare `institution_name` across all uploaded documents for spelling discrepancies or trust name divergence.

### 6.3 What Person 1 (Frontend) Must Implement Next
1. Initialize React + Vite + Tailwind CSS under `frontend/`.
2. Application setup screen (Institution Name, Category, Application Year).
3. Document upload view (drag & drop / file picker with document type selector).
4. Required-document checklist view with status badges (`uploaded`, `missing`, `processing_failed`).
5. Validation findings report view: Displays pass/flagged/unresolved findings, reason, affected document, and highlighted text snippet evidence.

---

## 7. Configuration & Environment Reference

- **Python Version:** Python 3.10–3.13 supported.
- **Dependencies Installed in Workstream:**
  - `paddlepaddle==3.3.1`
  - `paddleocr==3.7.0`
  - `pymupdf` (PyMuPDF `fitz`)
  - `pydantic>=2.0`
  - `pillow`
  - `numpy`
- **Configuration Note:** Keep `enable_mkldnn=False` when initializing PaddleOCR on Windows CPU to avoid Intel oneDNN runtime attribute conversion crashes.
