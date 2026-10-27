# SIH 2026 PS 26261 — Application Validation and Document Compliance

This repository contains **Pramaan**, a prototype reviewer workspace for preliminary scrutiny of institutional application documents. It helps organize uploads, extract selected text fields, run a small set of explicit checks, and present findings for human review. It does not make AICTE approval decisions or establish document authenticity.

See the [project walkthrough](docs/PROJECT_WALKTHROUGH.md) for the real user flow, architecture, and a synthetic example.

## Project overview and features

The project addresses SIH 2026 Problem Statement **26261**: AI-powered application validation and document compliance verification. The implemented category is Extension of Approval (EoA) for an existing institution. The backend checklist is a representative three-document subset: Fire Safety Certificate, Building Completion/Occupancy Certificate, and Affidavit-2, with sources recorded in `docs/AICTE_RULEBOOK_REFERENCE.md`.

Implemented in the backend: application records, PDF/JPG/PNG upload checks, local file storage, PostgreSQL metadata and extraction storage, PyMuPDF text extraction, PaddleOCR fallback for scanned pages and images, field extraction, four validation rules, and evidence-bearing reports. The React interface supports creating applications, uploading documents, viewing processing and extracted-field information, starting validation, and reading reports. Real API mode is the default.

The browser-only mock mode (`VITE_USE_MOCKS=true`) uses synthetic records in local storage. Its generated findings are demonstration placeholders, not backend validation. The live application workflow is implemented, but the team checklist still marks a complete real-frontend/backend end-to-end rehearsal as pending. OCR and regex extraction are heuristic and can be uncertain. This is not an authenticity or forgery detector.

### Technologies

- React 19, Vite 7, Tailwind CSS 4, and React Router: reviewer interface.
- Python (backend README specifies 3.11+), FastAPI, Pydantic, and SQLAlchemy async: API and data models.
- PostgreSQL through `asyncpg`: application, document, extraction-run, and finding records.
- PyMuPDF (`pymupdf`/`fitz`) and PaddleOCR 3.7.0 with PaddlePaddle 3.3.1: PDF text extraction and OCR.
- Custom Python rules: document presence, field completeness, expiry, and institution-name consistency.

## File structure

```text
.
├── AGENTS.md
├── README.md
├── docs/
│   ├── API_CONTRACT.md
│   ├── AICTE_RULEBOOK_REFERENCE.md
│   ├── DECISIONS.md
│   ├── PROJECT_CONTEXT.md
│   ├── PROJECT_WALKTHROUGH.md
│   └── TASKS.md
├── backend/
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/                 # Migration environment; no revision scripts are present
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, startup, health route
│   │   ├── database.py          # SQLAlchemy engine/session and create_all initialization
│   │   ├── routes/              # Application, document, and validation endpoints
│   │   ├── services/            # Application, upload/extraction, and report workflow
│   │   ├── ocr/                 # PDF/image processing, PaddleOCR, and field extraction
│   │   ├── rules/               # The four implemented validation rules
│   │   ├── checklist/            # EoA MVP checklist and document requirements
│   │   ├── models/              # SQLAlchemy database tables
│   │   └── schemas/              # Pydantic request and response schemas
│   ├── requirements.txt
│   └── tests/                   # API, rules, OCR, and synthetic scenario tests
└── frontend/
    ├── .env.example
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx              # Routes and reviewer screens
        ├── api.js               # Live API calls and mock-mode branch
        ├── config.js            # API address, mode, category, statuses
        └── demoData.js          # Synthetic browser-only demo content
```

Uploaded files are written under `backend/uploads/` by default and are excluded from Git. `backend/app/services/document_service.py` stores extraction results in the database; the files themselves are local. `backend/tests/demo_samples/manifest.json` records synthetic validation scenarios. `frontend/src/styles.css` and `frontend/src/refinement.css` hold the interface styles.

## Prerequisites and installation

Required: Git, PostgreSQL, Python, and Node.js/npm. The backend README specifies Python 3.11+; `requirements.txt` pins PaddleOCR 3.7.0 and PaddlePaddle 3.3.1 but does not specify a general Python version range. The repository does not specify a Node.js version or PostgreSQL version. PaddleOCR may download model files on first OCR use.

Clone the repository using its URL supplied by your team:

```powershell
git clone https://github.com/samvesh-cs/sih-prototype.git
cd sih-prototype
```

Install the frontend packages:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
```

Install the backend packages in a virtual environment:

```powershell
cd ..\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use the Python executable inside `.venv` directly, or follow your machine's Python environment policy. Configure `backend/.env` as described below. For frontend live mode, `frontend/.env.example` already sets `VITE_USE_MOCKS=false` and the local API base URL. Do not commit `.env` or `.env.local`.

## PostgreSQL configuration

Create a PostgreSQL role and database (replace the sample password with a private local value):

```sql
CREATE USER sih_user WITH PASSWORD 'replace-with-a-local-password';
CREATE DATABASE sih_prototype OWNER sih_user;
```

Set the connection string in `backend/.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://sih_user:<url-encoded-password>@localhost:5432/sih_prototype
```

The application reads these backend settings from `backend/.env` when started from `backend/`:

| Variable | Purpose | Default in code |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy async database connection | Local PostgreSQL URL in `app/config.py` |
| `UPLOAD_DIR` | Local uploaded-file directory | `./uploads` |
| `MAX_FILE_SIZE_MB` | Maximum upload size | `10` |
| `MAX_PAGES` | Maximum PDF page count | `20` |
| `API_PREFIX` | API route prefix | `/api` |
| `DEBUG` | SQL echo and internal error logging behavior | `true` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:5173,http://localhost:3000` |
| `JWT_SECRET_KEY` | HS256 secret for signing JWT access tokens | Default dev key in `config.py` (fail-fast in prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime in days | `7` |
| `ADMIN_SETUP_TOKEN` | Bearer token for one-time admin setup route | `admin-setup-secret-pramaan-2026` |
| `RATE_LIMIT_ENABLED` | Global endpoint rate limiter flag | `true` |

At application startup, `backend/app/main.py` calls `init_db()`, which initializes tables via Alembic and SQLAlchemy. In non-debug mode (`DEBUG=false`), the server enforces a fail-fast security check and refuses to boot if `JWT_SECRET_KEY` is left as the development default.

## Authentication and Role-Based Scrutiny

Pramaan enforces strict role separation between educational applicants and regulatory scrutiny reviewers:

1. **`INSTITUTION` (College Applicant):**
   - Can register a new institutional user account (1:1 institution mapping).
   - Manages draft applications, uploads documents, runs preliminary checks.
   - Submits application to AICTE, locking it for official committee scrutiny.
   - Can spawn a revised application prefilled from the validated report findings.
2. **`REVIEWER` (AICTE Scrutiny Committee):**
   - Has read access to all *submitted* applications, documents, and reports.
   - Reviews rule findings and records human-in-the-loop decisions (`Mark Verified`, `Confirm Discrepancy`, `Request Resubmission`, `Escalate`).
   - Reviewers **cannot self-register**. They are provisioned via CLI seed scripts or the one-time admin setup endpoint.

### Demo Credentials

| Role | Email | Password |
|---|---|---|
| **AICTE Reviewer** | `reviewer@aicte-india.org` | `Reviewer@AICTE2026` |
| **Demo Institution** | `institution@engg-college.edu.in` | `College@Pramaan2026` |

Quick-fill buttons for both roles are available directly on the login screen (`/login`).

### Seeding Accounts & Admin Setup

To seed the demo accounts from the command line:

```powershell
cd backend
.\.venv\Scripts\python scripts/seed_reviewer.py
.\.venv\Scripts\python scripts/seed_demo_institution.py
```

Alternatively, provision an initial reviewer via the protected one-time admin setup endpoint:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/auth/admin/setup `
  -Headers @{ "X-Admin-Setup-Token" = "admin-setup-secret-pramaan-2026"; "Content-Type" = "application/json" } `
  -Body '{"email": "auditor@aicte-india.org", "password": "SecurePassword123"}'
```

## Run the backend and frontend

Start PostgreSQL first. Then start the backend in one PowerShell window:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

The API is at `http://localhost:8000/api`; interactive documentation is at `http://localhost:8000/docs` (hidden when `DEBUG=false`). The health endpoint is `http://localhost:8000/health`.

Start the frontend in a second window:

```powershell
cd frontend
npm run dev
```

Visit `http://localhost:5173` to access the application. Unauthenticated users are automatically redirected to `/login`.

## Tests and checks

Run the full backend test suite (49 unit, auth, security enforcement, and scenario tests):

```powershell
cd backend
.\.venv\Scripts\python -m pytest -v
```

Run frontend linting and production build verification:

```powershell
cd frontend
npm run lint
npm run build
```

## API workflow

The application uses these authenticated API endpoints (base URL `http://localhost:8000/api`):

| Method | Endpoint | Auth Role | Purpose |
|---|---|---|---|
| `POST` | `/auth/register` | Public | Register new institution account (Reviewer registration blocked) |
| `POST` | `/auth/login` | Public | Authenticate; returns access token and sets HTTP-only refresh cookie |
| `POST` | `/auth/refresh` | Public | Rotate refresh token and issue new JWT access token |
| `POST` | `/auth/logout` | Authenticated | Revoke refresh token and clear cookie |
| `GET` | `/auth/me` | Authenticated | Return profile of currently signed-in user |
| `POST` | `/auth/admin/setup` | Token (`X-Admin-Setup-Token`) | One-time admin setup to provision first reviewer |
| `POST` | `/applications` | `INSTITUTION` | Create an EoA application record |
| `GET` | `/applications` | Authenticated | List applications (own for Institution, submitted for Reviewer) |
| `GET` | `/applications/{id}` | Authenticated | Scoped retrieval (returns 404 on unowned/unauthorized) |
| `POST` | `/applications/{id}/submit` | `INSTITUTION` | Submit application to AICTE; locks application from further edits |
| `POST` | `/applications/{id}/documents` | `INSTITUTION` | Upload file (rejects with 409 if application is submitted) |
| `GET` | `/applications/{id}/documents` | Authenticated | List document records |
| `POST` | `/applications/{id}/validate` | `INSTITUTION` | Run preliminary validation (rejects with 409 if submitted) |
| `GET` | `/applications/{id}/report` | Authenticated | Retrieve the saved validation report |
| `PATCH` | `/applications/{id}/findings/{id}` | `REVIEWER` | Record reviewer verification determination on submitted application |

FastAPI's interactive request interface is available at `http://localhost:8000/docs` while `DEBUG=true`.

## Known limitations

- Only the three configured EoA document types are checked; this is not the full EoA checklist. Confirm the official source and applicability when extending it.
- `backend/app/ocr/field_extractor.py` uses pattern-based extraction. OCR quality depends on the scan, and missing/uncertain values can make checks unresolved or missing. Digital PDF extraction has no OCR confidence score.
- Extraction uses field aliases to bridge names such as `document_number`/`certificate_number` and `notary_date`/`affidavit_date`; the field set remains limited to the patterns implemented in code.
- The explicit rules check required-document presence, configured required-field completeness, Fire Safety Certificate expiry, and institution-name similarity. They do not verify every regulatory requirement or issuer.
- A name mismatch or expired-date flag is a prompt for human review. Matching fields or passing checks do not prove authenticity, prevent forgery, or constitute AICTE approval.
- Uploaded files are stored locally. Moving or deploying the backend requires appropriate persistent storage and a configured database; no cloud storage or issuing-authority integration is implemented.
- The backend's startup handler catches database initialization errors and continues running. A live database request is needed to establish that persistence works.
- The frontend is connected to the API by default, while demo mode is separately mocked. Full live UI rehearsal and repeat-validation isolation remain unchecked in `docs/TASKS.md`.
- The three-document subset is treated as mandatory by the current checklist. Applicability can vary in real cases; this prototype does not calculate all such conditions.
