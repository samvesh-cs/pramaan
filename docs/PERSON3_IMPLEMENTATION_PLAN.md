# Person 3 — Implementation Plan: FastAPI, Database & Validation Engine

> **Role:** Person 3 — Backend and Validation
> **Owner:** Jay (jay-backend branch)
> **Date:** 2026-10-25
> **Category:** Extension of Approval (EoA) — Self-Disclosure
> **Source:** AICTE Approval Process Handbook 2024-2027, Annexure-2 §2.1

---

## Current Status Assessment

### What Exists
- ✅ Documentation complete: `PROJECT_CONTEXT.md`, `API_CONTRACT.md`, `TASKS.md`, `DECISIONS.md`, `AGENTS.md`
- ✅ Repository structure: `backend/`, `frontend/`, `ocr/`, `docs/`
- ✅ API contract with endpoints, schemas, and status values defined
- ✅ AICTE rulebook reference extracted (`docs/AICTE_RULEBOOK_REFERENCE.md`)
- ✅ `.gitignore` updated

### Person 2 (Aditya) — `remotes/origin/aditya-work` Status
- ✅ **Delivered** in commit `ffb519e` ("Extraction")
- ✅ **OCR module implemented** in `backend/app/ocr/` (PyMuPDF + PaddleOCR 3.x wrapper, field extraction, synthetic samples)
- ✅ **Integrated by Person 3** into `backend/app/services/ocr_service.py`
- ✅ **Verified with real synthetic samples** via `test_ocr_integration.py`

### Open Questions Resolved by This Plan
- **Q-001:** Category confirmed → **EoA (Self-Disclosure)**
- **Q-002:** Document types selected → **fire_safety_certificate, building_completion_certificate, affidavit_2**
- **Q-003:** Field matrix defined → See `AICTE_RULEBOOK_REFERENCE.md` §3
- **Q-004:** Proposed limits → **10 MB file size, 20 pages max per PDF**

---

## Phase 1: Foundation (Day 1-2)

### Task 1.1 — FastAPI Project Scaffold
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, CORS, lifespan
│   ├── config.py             # Settings from .env
│   ├── database.py           # SQLAlchemy async engine + session
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── application.py
│   │   ├── document.py
│   │   ├── extraction.py
│   │   └── finding.py
│   ├── schemas/              # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── application.py
│   │   ├── document.py
│   │   ├── extraction.py
│   │   ├── finding.py
│   │   └── report.py
│   ├── routes/               # API route handlers
│   │   ├── __init__.py
│   │   ├── applications.py
│   │   └── documents.py
│   ├── services/             # Business logic
│   │   ├── __init__.py
│   │   ├── application_service.py
│   │   ├── document_service.py
│   │   ├── validation_engine.py
│   │   └── ocr_service.py    # Person 2 owns internals; Person 3 owns interface
│   ├── rules/                # Validation rule implementations
│   │   ├── __init__.py
│   │   ├── base.py           # BaseRule abstract class
│   │   ├── presence_check.py
│   │   ├── field_completeness.py
│   │   ├── expiry_check.py
│   │   └── cross_document_check.py
│   ├── checklist/            # EoA document requirements config
│   │   ├── __init__.py
│   │   └── eoa_checklist.py
│   └── utils/
│       ├── __init__.py
│       ├── file_validation.py
│       └── id_generator.py
├── uploads/                  # Git-ignored
├── tests/
│   ├── __init__.py
│   ├── test_applications.py
│   ├── test_documents.py
│   ├── test_validation.py
│   └── conftest.py
├── alembic/                  # DB migrations
│   └── ...
├── alembic.ini
├── requirements.txt
├── .env.example
└── README.md
```

### Task 1.2 — Environment Configuration
Create `.env.example`:
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sih_prototype
# Or for sync: postgresql://user:password@localhost:5432/sih_prototype

# File uploads
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=10
MAX_PAGES=20

# API
API_PREFIX=/api
DEBUG=true

# CORS (frontend origin)
CORS_ORIGINS=http://localhost:5173
```

### Task 1.3 — PostgreSQL Database Schema

```sql
-- applications table
CREATE TABLE applications (
    id VARCHAR(36) PRIMARY KEY,           -- UUID or prefixed ID like "app_001"
    institution_name VARCHAR(500) NOT NULL,
    application_category VARCHAR(50) NOT NULL DEFAULT 'eoa',
    academic_year VARCHAR(10) NOT NULL,    -- e.g. "2026-27"
    overall_status VARCHAR(50) NOT NULL DEFAULT 'processing_incomplete',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- documents table
CREATE TABLE documents (
    id VARCHAR(36) PRIMARY KEY,
    application_id VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL,   -- e.g. "fire_safety_certificate"
    original_filename VARCHAR(500) NOT NULL,
    stored_filename VARCHAR(500) NOT NULL, -- UUID-based name in uploads/
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    processing_status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- extraction_runs table (stores OCR/extraction output per document)
CREATE TABLE extraction_runs (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    processing_status VARCHAR(50) NOT NULL,  -- processed | processing_failed
    pages JSONB,                             -- array of {page_number, text, regions[]}
    fields JSONB,                            -- {field_name: {value, normalized_value, raw_text, confidence, page_number, bbox}}
    error TEXT,                              -- error message if failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- findings table
CREATE TABLE findings (
    id VARCHAR(36) PRIMARY KEY,
    application_id VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_id VARCHAR(36) REFERENCES documents(id) ON DELETE SET NULL,  -- NULL for app-level findings
    rule_id VARCHAR(100) NOT NULL,           -- e.g. "PRESENCE_001", "EXPIRY_001"
    status VARCHAR(50) NOT NULL,             -- pass | flagged | missing | unresolved | not_applicable
    title VARCHAR(500) NOT NULL,
    reason TEXT NOT NULL,
    document_name VARCHAR(500),
    evidence JSONB,                          -- {page_number, text, field, value, bbox}
    next_action TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- indexes
CREATE INDEX idx_documents_application_id ON documents(application_id);
CREATE INDEX idx_extraction_runs_document_id ON extraction_runs(document_id);
CREATE INDEX idx_findings_application_id ON findings(application_id);
CREATE INDEX idx_findings_document_id ON findings(document_id);
```

---

## Phase 2: Core API Endpoints (Day 2-3)

### Task 2.1 — Application CRUD
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/applications` | POST | Create application |
| `/api/applications/{id}` | GET | Get application with documents and findings |

### Task 2.2 — Document Upload & Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/applications/{id}/documents` | POST | Upload document (multipart/form-data) |
| `/api/applications/{id}/documents` | GET | List documents for application |

**Upload validation logic:**
1. Check `application_id` exists → 404 if not
2. Validate `document_type` is in allowed types for `eoa` category
3. Validate file extension (`.pdf`, `.jpg`, `.jpeg`, `.png`)
4. Validate MIME type matches extension
5. Validate file size ≤ MAX_FILE_SIZE_MB
6. Generate UUID-based `stored_filename` (never expose original to FS path traversal)
7. Save to `uploads/` directory
8. Create DB record with `processing_status: "uploaded"`

### Task 2.3 — Validation Trigger & Report
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/applications/{id}/validate` | POST | Run validation pipeline |
| `/api/applications/{id}/report` | GET | Get validation report |

---

## Phase 3: EoA Checklist & Validation Engine (Day 3-5)

### Task 3.1 — EoA Document Checklist Configuration

```python
# backend/app/checklist/eoa_checklist.py

EOA_DOCUMENT_CHECKLIST = {
    "fire_safety_certificate": {
        "display_name": "Fire Safety Certificate",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(v)",
        "has_expiry": True,
        "required_fields": ["institution_name", "document_number", "issue_date", "expiry_date", "issuing_authority"],
        "description": "Valid Fire Safety Certificate issued by the Competent Authority"
    },
    "building_completion_certificate": {
        "display_name": "Occupancy/Completion Certificate/Building License/Form D",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(iii), Clause 7.17",
        "has_expiry": False,
        "required_fields": ["institution_name", "certificate_number", "issue_date", "issuing_authority"],
        "description": "Valid Occupancy/Completion Certificate/Building License/Form D issued by the Competent Authority"
    },
    "affidavit_2": {
        "display_name": "Affidavit-2",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(i)",
        "has_expiry": False,
        "required_fields": ["institution_name", "signatory_name", "notary_date"],
        "description": "Sworn Affidavit with digital signature of Chairman/Secretary on e-stamp paper"
    }
}

# Full EoA checklist (for reference — only 3 selected for MVP)
EOA_FULL_CHECKLIST = {
    **EOA_DOCUMENT_CHECKLIST,
    "ter_payment_receipt": {
        "display_name": "TER Payment Receipt",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(ii)"
    },
    "structural_stability_certificate": {
        "display_name": "Structural Stability Certificate",
        "applicability": "required_if_applicable",
        "source": "APH 2024-2027, Annexure-2, §2.1(iv)",
        "condition": "Building > 30 years from Completion Certificate issue"
    },
    "satellite_map": {
        "display_name": "Satellite Map with Lat/Long",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(vi)"
    },
    "audited_accounts": {
        "display_name": "Audited Statement of Accounts",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(vii)"
    }
}
```

### Task 3.2 — Validation Rule Engine

```python
# backend/app/rules/base.py
from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.finding import FindingCreate

class BaseRule(ABC):
    rule_id: str
    title: str

    @abstractmethod
    def evaluate(self, context: dict) -> FindingCreate:
        """Evaluate the rule and return a finding."""
        pass
```

**Rules to implement:**

| Rule ID | Class | Logic |
|---------|-------|-------|
| `PRESENCE_001` - `PRESENCE_003` | `DocumentPresenceRule` | Check if each required doc type is uploaded |
| `FIELD_001` - `FIELD_N` | `FieldCompletenessRule` | Check if required fields are extracted for each doc type |
| `EXPIRY_001` | `ExpiryDateRule` | Check if `fire_safety_certificate.expiry_date` < today |
| `CONSISTENCY_001` | `InstitutionNameConsistencyRule` | Cross-check `institution_name` across all docs vs application |

### Task 3.3 — Overall Status Calculation

```python
def calculate_overall_status(findings: list[Finding], documents: list[Document]) -> str:
    """
    Priority: processing_incomplete > missing_documents > discrepancies_found
              > unresolved_checks > checks_passed
    """
    # Check if any document still not processed
    if any(d.processing_status != "processed" for d in documents):
        return "processing_incomplete"

    statuses = [f.status for f in findings]

    if "missing" in statuses:
        return "missing_documents"
    if "flagged" in statuses:
        return "discrepancies_found"
    if "unresolved" in statuses:
        return "unresolved_checks"
    if all(s in ("pass", "not_applicable") for s in statuses):
        return "checks_passed"

    return "processing_incomplete"
```

---

## Phase 4: OCR Integration (Day 4-6) — Completed ✅

### Task 4.1 — OCR Extraction Service Integration
- Integrated `app.ocr.process_document` from Aditya's deliverable directly into `backend/app/services/ocr_service.py`.
- Supports dual processing: fast selectable text extraction via PyMuPDF v2.0, with automatic fallback to PaddleOCR 3.x on scanned pages/images.
- Conforms 100% to `API_CONTRACT.md §5` schema (`pages`, `regions`, `fields`, `confidence`, `bbox`).

### Task 4.2 — Field Extractor Enhancements for EoA
- Sourced from AICTE APH 2024-2027 Annexure-2 §2.1.
- Extended `backend/app/ocr/field_extractor.py` to extract all required fields across all 3 MVP document types:
  1. `fire_safety_certificate`: `institution_name`, `document_number`, `certificate_number`, `issuing_authority`, `issue_date`, `expiry_date`.
  2. `building_completion_certificate`: `institution_name`, `document_number`, `certificate_number`, `issuing_authority`, `issue_date`.
  3. `affidavit_2`: `institution_name`, `deponent_name`, `affidavit_date`, `issue_date`, `notary_registration_number`.
- Added end-to-end test verification in `backend/tests/test_ocr_integration.py`.

---

## Phase 5: Testing & Polish (Day 5-7)

### Task 5.1 — Synthetic Test Data

Create test documents (synthetic PDFs/images):
1. **Valid case:** All 3 docs present, valid dates, matching institution names
2. **Missing doc:** Only 2 of 3 docs uploaded
3. **Expired doc:** Fire Safety Certificate with past expiry date
4. **Missing field:** Building certificate with no institution name
5. **Name mismatch:** Different institution names across documents
6. **Unreadable:** Corrupt/blank image file

### Task 5.2 — Backend Tests

```python
# tests/test_applications.py — Create/retrieve applications
# tests/test_documents.py — Upload validation, file handling
# tests/test_validation.py — Each rule produces correct finding
# tests/test_report.py — Overall status calculation
```

### Task 5.3 — Error Handling
- All API errors use the standard error response format
- No stack traces in responses
- Invalid uploads return appropriate error codes
- OCR failures don't crash the server

---

## Execution Order for Gemini Flash

> This is the step-by-step order for an AI coding agent to execute.

### Step 1: Project Setup
1. `cd backend && python -m venv venv`
2. Create `requirements.txt` with: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `python-multipart`, `aiofiles`, `python-dotenv`, `pytest`, `pytest-asyncio`, `httpx`
3. `pip install -r requirements.txt`
4. Create `app/main.py` with FastAPI app, CORS middleware, router includes
5. Create `.env.example`

### Step 2: Database Layer
1. Create `app/config.py` with Pydantic Settings
2. Create `app/database.py` with SQLAlchemy async engine
3. Create all models in `app/models/`
4. Setup Alembic and run initial migration
5. Create `app/schemas/` Pydantic models matching API_CONTRACT.md

### Step 3: Core Routes
1. Implement `POST /api/applications` and `GET /api/applications/{id}`
2. Implement `POST /api/applications/{id}/documents` with file validation
3. Implement `GET /api/applications/{id}/documents`
4. Test with `uvicorn app.main:app --reload` and Swagger UI

### Step 4: Validation Engine
1. Create `app/checklist/eoa_checklist.py`
2. Create `app/rules/base.py` abstract rule
3. Implement `DocumentPresenceRule`
4. Implement `FieldCompletenessRule`
5. Implement `ExpiryDateRule`
6. Implement `InstitutionNameConsistencyRule`
7. Create `app/services/validation_engine.py` to orchestrate rules
8. Implement `POST /api/applications/{id}/validate`
9. Implement `GET /api/applications/{id}/report`

### Step 5: Integration
1. Create mock extraction service
2. Wire validation pipeline: upload → extract → validate → report
3. Test end-to-end with synthetic data
4. Replace mock extraction when Person 2 delivers

### Step 6: Tests & Documentation
1. Write pytest tests for each route
2. Write pytest tests for each validation rule
3. Update README with setup instructions
4. Share API docs (Swagger) URL with Person 1

---

## Dependencies & Blockers

| Dependency | From | Status | Impact |
|-----------|------|--------|--------|
| Extraction module | Person 2 (Aditya) | ✅ Delivered & Integrated | Fully connected via `app.ocr.process_document` with PyMuPDF and PaddleOCR 3.x |
| Frontend API consumption | Person 1 | ⏳ In Progress | No blocker for Person 3; Swagger docs live at `http://localhost:8000/docs` |
| Category confirmation | Team | ✅ Resolved by this plan | EoA Self-Disclosure confirmed |
| Document types | Team | ✅ Resolved by this plan | 3 types selected with AICTE source |

---

## Timeline Summary

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | Project scaffold, DB schema, config | Running FastAPI + DB |
| 2 | Application CRUD, Document upload | Checkpoint 3 ready |
| 3 | EoA checklist, validation rules | Rule engine working |
| 4 | Validate endpoint, report endpoint, mock OCR | Checkpoint 4 ready |
| 5 | Integration with Person 2, synthetic test data | Working pipeline |
| 6 | Tests, error handling, polish | Backend complete |
| 7 | End-to-end with frontend, demo rehearsal | Checkpoint 5 |
