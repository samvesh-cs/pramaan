# AGENT_INTEGRATION_GUIDE.md — Pramaan Scrutiny Engine
**SIH 2026 — Problem Statement 26261: Preliminary Document Scrutiny & Compliance Verification**  
*Unified Baseline: Commit `156d358` (Integrated `main` + `aditya-backend`)*

---

## 1. System Overview & Integrated Architecture

Pramaan is an AI-assisted decision-support prototype built to aid scrutiny committees in preliminary verification of institutional documents against the AICTE Approval Process Handbook (APH 2024–2027). It extracts structured fields, applies statutory rule checks, highlights visual evidence, and flags discrepancies for human reviewer determination.

### 1.1 Technology Stack
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (Asyncio), Pydantic v2.
- **Frontend:** React 18, Vite, Tailwind CSS, custom UI components.
- **OCR & Document Processing:** PyMuPDF (`fitz`) for digital selectable text and high-res page rendering; PaddleOCR for scanned raster fallback.
- **Database:** PostgreSQL (primary production stack) & SQLite (local test/dev environment), managed via Alembic migrations.
- **Authenticity Signals:** Perceptual image hashing (`dHash`/`pHash`), local QR code parameter decoding, and PDF metadata forensics.

---

## 2. Complete API Endpoints Catalog

All API endpoints are prefixed with `/api`. Authentication is passed via HTTP-only cookie or `Authorization: Bearer <access_token>`.

### 2.1 Authentication (`/api/auth`)
| Method | Path | Auth / Role | Description | Request Payload | Response Schema | Status Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Public | Register new institution account | `UserRegisterRequest` (`email`, `password`, `institution_name`, `institution_address`) | `UserResponse` | `201`, `400`, `409` |
| `POST` | `/api/auth/login` | Public | Authenticate user, receive JWT cookies | `UserLoginRequest` (`email`, `password`) | `TokenResponse` | `200`, `401` |
| `POST` | `/api/auth/refresh` | Cookie / Bearer | Refresh expired access token | None (uses refresh token cookie) | `TokenResponse` | `200`, `401` |
| `POST` | `/api/auth/logout` | Authenticated | Revoke refresh token and clear cookies | None | `{"message": "Logged out"}` | `200` |
| `GET` | `/api/auth/me` | Authenticated | Retrieve current user profile | None | `UserResponse` (`id`, `email`, `role`, `institution_id`) | `200`, `401` |

---

### 2.2 Institutional Applications (`/api/applications`)
| Method | Path | Auth / Role | Description | Request / Query | Response Schema | Status Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/applications` | `INSTITUTION` | Create a new draft application | `ApplicationCreate` (`institution_name`, `application_category`, `academic_year`) | `ApplicationResponse` | `201`, `422` |
| `GET` | `/api/applications` | Authenticated | List applications (institutions see own; reviewers see submitted) | None | `list[ApplicationResponse]` | `200` |
| `GET` | `/api/applications/{id}` | Access-checked | Get full application details with documents and findings | Path: `id` | `ApplicationDetailResponse` | `200`, `404` |
| `POST` | `/api/applications/{id}/submit` | `INSTITUTION` | Lock and submit application for committee scrutiny | Path: `id` | `ApplicationResponse` (`status="submitted"`) | `200`, `404`, `409` |
| `POST` | `/api/applications/{id}/finalize-review` | `REVIEWER` | Finalize scrutiny after all findings have recorded decisions | Path: `id` | `ApplicationResponse` (`status="review_completed"`) | `200`, `400`, `404`, `409` |

---

### 2.3 Supporting Documents (`/api/applications/{id}/documents`)
| Method | Path | Auth / Role | Description | Parameters / Payload | Response Schema | Status Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/applications/{id}/documents` | `INSTITUTION` | Upload PDF/image supporting document | Multipart: `file` (binary), `document_type` (string code) | `DocumentResponse` | `201`, `400`, `409`, `422` |
| `GET` | `/api/applications/{id}/documents` | Access-checked | List uploaded documents for application | None | `list[DocumentResponse]` | `200` |
| `GET` | `/api/applications/{id}/documents/{doc_id}/file` | Access-checked | Stream original file with inline disposition | Path: `id`, `doc_id` | Binary stream (PDF / image) | `200`, `404` |
| `GET` | `/api/applications/{id}/documents/{doc_id}/pages-info` | Access-checked | Multi-page dimensions for evidence viewer | Path: `id`, `doc_id` | `{"document_id": str, "total_pages": int, "pages": [{"page_number": int, "width": float, "height": float}]}` | `200`, `404`, `500` |
| `GET` | `/api/applications/{id}/documents/{doc_id}/page-image` | Access-checked | Render page as high-res PNG for bounding box overlays | Path: `id`, `doc_id`<br>Query: `page` (default 1), `dpi` (default 150) | Binary image (`image/png`) with headers: `X-Page-Width`, `X-Page-Height`, `X-Image-Width`, `X-Image-Height` | `200`, `400`, `404`, `500` |

---

### 2.4 Validation & Scrutiny Findings (`/api/applications/{id}`)
| Method | Path | Auth / Role | Description | Parameters / Payload | Response Schema | Status Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/applications/{id}/validate` | `INSTITUTION` / `REVIEWER` | Trigger deterministic scrutiny validation engine | Path: `id` | `ReportResponse` (overall status, checklist, findings list) | `200`, `404`, `409` |
| `GET` | `/api/applications/{id}/report` | Access-checked | Get validation report (institutions viewable only when finalized) | Path: `id` | `ReportResponse` | `200`, `404`, `409` |
| `GET` | `/api/applications/{id}/checklist` | Access-checked | Retrieve regulatory checklist for application category | Path: `id` | `ChecklistResponse` | `200`, `404` |
| `PATCH` | `/api/applications/{id}/findings/{finding_id}` | `REVIEWER` | Record reviewer scrutiny determination and notes | Path: `id`, `finding_id`<br>Payload: `FindingReviewUpdate` (`reviewer_decision`, `reviewer_notes`) | `FindingResponse` | `200`, `404`, `409`, `422` |
| `POST` | `/api/applications/{id}/duplicates/{finding_id}/acknowledge` | `REVIEWER` | Acknowledge duplicate document flag | Path: `id`, `finding_id`<br>Payload: `AcknowledgeDuplicateRequest` (`reviewer_notes`) | `{"acknowledged": True, "finding_id": str}` | `200`, `404`, `409`, `422` |

---

### 2.5 Policy Intelligence & Scrutiny Dossier (Priority Sprint Features)
| Method | Path | Auth / Role | Description | Parameters / Payload | Response Schema | Status Codes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/policy/query` | Access-checked | Query AICTE handbook rules offline / with assistant | Payload: `{"query": str, "rule_id": Optional[str], "top_k": int = 3}` | `PolicyQueryResponse` (`matching_clauses`, `explanation`, `disclaimer`) | `200`, `422` |
| `GET` | `/api/policy/clauses` | Access-checked | Retrieve full index of AICTE statutory handbook clauses | None | `list[ClauseDefinition]` | `200` |
| `GET` | `/api/applications/{id}/scrutiny-report` | Access-checked | Export downloadable Preliminary Scrutiny Report PDF | Path: `id` | Binary PDF (`application/pdf`) | `200`, `404` |

---

## 3. Agent Integration Guide

When working on this repository, coding agents must follow these operational rules:

### 3.1 Operating Environment & Shell Protocol
- **Operating System:** Windows.
- **Shell:** PowerShell. Use PowerShell-compatible syntax:
  - Use `;` instead of `&&` for sequencing commands.
  - Set environment variables via `$env:VAR="value"; command`.
  - Use `Select-String` instead of Unix `grep`.
  - Virtual environment binary: `C:\SIH 26-2.0\sih-prototype\backend\venv\Scripts\python.exe`.
- **Command Execution Rule:** Commands running longer than 10 seconds are automatically backgrounded. Do not loop-poll task status; wait for system notifications. Never invoke shell `sleep` commands.

### 3.2 Testing Protocol
Before committing any changes, run the appropriate test suites from `backend/`:
```powershell
# 1. Full pytest suite in legacy mode (default)
$env:PYTHONPATH="backend"; $env:RULE_ENGINE_MODE="legacy"; & "backend/venv/Scripts/python.exe" -m pytest backend/tests -q

# 2. Replay & Parity Harness (must maintain 100% parity across all 28 contexts)
$env:PYTHONPATH="backend"; & "backend/venv/Scripts/python.exe" backend/app/rules/parity_harness.py

# 3. Honest claims verification
$env:PYTHONPATH="backend"; & "backend/venv/Scripts/python.exe" -m pytest backend/tests/test_clause_registry.py -k "banned" -q

# 4. Frontend lint & production build
cd frontend; npm run lint; npm run build; cd ..
```

### 3.3 Git Collaboration Protocol
- Always branch off `main` or the agreed feature branch (`feat/*` or `fix/*`).
- Never force-push to shared branches.
- **Never push directly to `origin/main`** unless explicitly instructed by the user.
- Keep commits small, descriptive, and atomic with verified test summaries.

### 3.4 Regulatory & Language Guardrails
- **Canonical Banned Terms List (`backend/app/rules/banned_terms.py`):**
  `["fraud", "forgery", "fake", "genuine", "verified issuer", "valid signature", "contravention", "violation", "non-compliant", "tampered", "authentic", "complies", "complying"]`
- Automated finding texts and descriptions must state objective facts:
  - Use: `"Discrepancy detected"`, `"Signal for human review"`, `"Unresolved pending reviewer confirmation"`.
  - Never use: `"Genuine document"`, `"Fraudulent application"`, `"Compliance verified"`.
- All statutory citations must reference real clauses from `backend/app/rules/data/clauses.json` or `AICTE_rulebook.pdf` (where PDF page = handbook page + 16).

---

## 4. Database (DB) Management & Fallback/Feedback (FB) Management

### 4.1 Database (DB) Management
1. **Dialect Neutrality (PostgreSQL & SQLite):**
   - The production/demo stack targets PostgreSQL; local development and automated CI use SQLite.
   - All SQLAlchemy models and Alembic migrations must be dialect-neutral. Avoid PostgreSQL-specific constructs (e.g. `JSONB`, native ENUMs without fallback strings) without SQLite compatibility layers.
2. **Session Lifecycle & Concurrency Safety:**
   - Database operations use FastAPI's dependency injection (`get_db`) yielding an `AsyncSession`.
   - **Strict Thread Isolation:** Worker threads spawned via `asyncio.to_thread` must **NEVER** touch an active `AsyncSession` or database connection. Pass plain dictionaries/primitives into background threads to prevent SQLite pool deadlocks.
3. **Foreign Key Integrity in Migrations:**
   - When backfilling columns in Alembic migrations, never insert dummy string values (e.g. `'SYSTEM_MIGRATION'`) into UUID foreign key columns (`actor_user_id`). Leave foreign keys `NULL` and set human-readable fallback names in display columns (`actor_display_name`).
4. **Data Seeding & Showcase Consistency:**
   - Synthetic demo records are seeded via `backend/scripts/seed_demo_showcase.py`. Seed data must adhere to handbook constraints (e.g. realistic completion dates, valid clause IDs).

### 4.2 Fallback and Feedback (FB) Management
1. **Rule Engine Fallback:**
   - The engine operates under `RULE_ENGINE_MODE = "legacy"` by default.
   - If switched to `"declarative"`, the legacy engine remains available as an immediate zero-latency fallback toggle.
   - The shadow declarative engine runs asynchronously out-of-band and will never abort or crash user request lifecycles.
2. **OCR Pipeline Fallback:**
   - Digital text extraction via PyMuPDF is primary.
   - When digital text contains fewer than 50 alphanumeric characters (scanned documents or raster images), the pipeline falls back gracefully to PaddleOCR on rendered page pixmaps.
3. **Policy Retrieval Fallback:**
   - When `GEMINI_API_KEY` is not configured or offline, the Policy Assistant falls back strictly to local BM25 keyword matching over `clauses.json`, returning exact handbook excerpts without external network calls.
4. **Reviewer Feedback Loop:**
   - Rule findings are non-binding signals.
   - Scrutiny Committee reviewers provide the final human determination (`verified`, `confirmed_discrepancy`, `requested_resubmission`, `escalated`).
   - Every reviewer decision requires mandatory justification notes ($\ge 10$ characters after trimming).
   - Once finalized (`POST /api/applications/{id}/finalize-review`), findings and decisions are locked as read-only audit records.

---

## 5. File Handling Architecture

### 5.1 Storage Layout & Security
- **Directory:** `backend/uploads/{application_id}/{document_id}.{ext}`. Excluded from Git via `.gitignore`.
- **Validation:** `backend/app/utils/file_validation.py` inspects magic bytes. Allowed types: PDF (`%PDF`), PNG (`\x89PNG`), JPEG (`\xFF\xD8\xFF`).
- **File Size Cap:** Maximum 10 MB per file.
- **Tenant Isolation:** Files are served only after validating `require_application_access` (ensuring applicants cannot download other institutions' files).

### 5.2 PyMuPDF Document Lifecycle
- Always encapsulate PyMuPDF documents in `try...finally` blocks:
  ```python
  doc = fitz.open(file_path)
  try:
      # Perform extraction or rendering
      page = doc[page_index]
      pix = page.get_pixmap(dpi=150)
  finally:
      doc.close()
  ```
  *Failure to close `doc` locks file handles on Windows, preventing cleanup or re-runs.*

### 5.3 Page Image Rendering & Coordinate Overlays
- Endpoint `GET /api/applications/{id}/documents/{doc_id}/page-image` renders pages at 150 DPI.
- Dimensions are exposed via response headers:
  - `X-Page-Width`: PDF page points (e.g. 595.0)
  - `X-Page-Height`: PDF page points (e.g. 842.0)
  - `X-Image-Width`: Rendered pixel width (e.g. 1240)
  - `X-Image-Height`: Rendered pixel height (e.g. 1754)
- Frontend calculates percentages: `left = (x0 / width) * 100%`, `top = (y0 / height) * 100%`.

### 5.4 Zero SSRF & Data Privacy Guarantees
- QR code extraction decodes string payloads locally. URLs are parsed via `urllib.parse` for parameters (e.g. `?cert_no=...`); the system **NEVER** initiates HTTP requests to decoded URLs.
- Raw uploaded documents, scanned images, and institution names are **NEVER** transmitted to external AI endpoints.

---

## 6. Clear Two-Person Implementation Checklist

### 👤 Person 1: Backend & Policy Intelligence Engineer
- [ ] **Offline Policy Retrieval (`backend/app/policy/retrieval.py`):**
  - Index `backend/app/rules/data/clauses.json` (31+ validated AICTE clauses).
  - Implement fast BM25 / token similarity search over clause titles, summaries, and full text.
  - Return top $k$ matching clauses with verified handbook page and PDF page numbers.
- [ ] **Policy API Endpoints (`backend/app/routes/policy.py`):**
  - Implement `POST /api/policy/query` accepting `{query, rule_id, top_k}`.
  - Implement `GET /api/policy/clauses` returning all indexed statutory clauses.
  - Wire router into `backend/app/main.py`.
- [ ] **Citation Guardrail & LLM Explainer (`backend/app/policy/llm_explainer.py`):**
  - Optional Gemini explainer guarded by `ENABLE_RAG_ASSISTANT`.
  - Strict input allow-list: user query + retrieved clause text only.
  - Automated post-validation filter stripping any ungrounded citations.
- [ ] **PDF Metadata Forensics Provider (`backend/app/tamper/metadata_forensics.py`):**
  - Parse PDF trailer dictionary and `/Info` metadata (Producer, Creator, ModDate).
  - Count non-signature incremental updates (`%%EOF` markers).
  - Emit low-severity informational signals with `"signal, not proof"` text.
- [ ] **Preliminary Scrutiny Report PDF Export (`backend/app/services/dossier_generator.py`):**
  - PyMuPDF binary report generator incorporating compliance checklist, findings, citations, and reviewer sign-off block.
  - Implement `GET /api/applications/{id}/scrutiny-report` streaming downloadable PDF.
- [ ] **Automated Tests:**
  - Write `backend/tests/test_policy_retrieval.py` and `test_metadata_forensics.py`.

---

### 👤 Person 2: Frontend & Demo Experience Engineer
- [ ] **Policy Assistant Chatbot UI (`frontend/src/components/PolicyAssistantDrawer.jsx`):**
  - Build floating "AICTE Policy Assistant" trigger button on the bottom right.
  - Create slide-out chat drawer with message history, quick query chips, and search input.
  - Display verified clause citation cards (Handbook Page, PDF Page, verbatim excerpt with copy action).
- [ ] **Contextual Finding Integration:**
  - Add "Ask Policy Assistant" button on every finding card in `FindingRegister`.
  - Clicking pre-loads the assistant drawer with the finding's statutory clause context.
- [ ] **Tamper Signals Badges in Document Viewer:**
  - Render informational metadata forensics badges in `DocumentViewerDrawer`.
  - Display QR verification match indicators in the document inspector.
- [ ] **Reviewer Duplicate Acknowledgment Interface:**
  - Build acknowledgment modal calling `POST /api/applications/{id}/duplicates/{finding_id}/acknowledge`.
  - Validate mandatory $\ge 10$-character reviewer acknowledgment notes.
- [ ] **Demo Seeding & Script Walkthrough (`docs/DEMO_SCRIPT.md`):**
  - Verify `backend/scripts/seed_demo_showcase.py` generates all demo scenarios:
    1. Clean application with all valid documents.
    2. Expired fire safety certificate.
    3. Cross-document institution name mismatch.
    4. Building > 30 years without structural stability certificate.
    5. Duplicate document detected across institutions.
  - Write `docs/DEMO_SCRIPT.md` with click-by-click instructions, talking points, and honest claims demarcation for the hackathon jury presentation.

