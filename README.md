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

At application startup, `backend/app/main.py` calls `init_db()`, which uses SQLAlchemy `Base.metadata.create_all` in `backend/app/database.py`. This creates missing tables; it is not a schema migration system. Alembic configuration exists, but there are no migration revision scripts in the repository. No destructive database reset is needed. A database connection failure is printed as a warning and startup continues, so check the backend log and make a real API/database request to confirm connectivity; `/health` alone only confirms that the FastAPI process responds.

With the backend running and the database ready, run `Invoke-RestMethod http://localhost:8000/api/applications` in PowerShell. A successful response (an empty list for a new database) confirms that this database-backed endpoint can query PostgreSQL.

Backend tests override the database dependency with an in-memory SQLite database in `backend/tests/conftest.py`. They do not require PostgreSQL or a `DATABASE_URL`, though the project's Python dependencies still need to be installed. OCR-related tests can additionally depend on PaddleOCR and its model runtime.

## Run the backend and frontend

Start PostgreSQL first. Then start the backend in one PowerShell window:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

The API is at `http://localhost:8000/api`; interactive documentation is at `http://localhost:8000/docs`. The health endpoint is `http://localhost:8000/health`. Startup attempts to initialize the database tables and creates the upload directory.

Start the frontend in a second window:

```powershell
cd frontend
npm run dev
```

Vite is configured to bind to `127.0.0.1`; its default development URL is `http://127.0.0.1:5173`. `frontend/src/config.js` defaults to real API mode and uses `http://localhost:8000` as the API base. `frontend/src/api.js` sends requests to that host under `/api`. The API must be running for live application creation, uploads, validation, and report retrieval.

To use the isolated browser-only demonstration, set `VITE_USE_MOCKS=true` in `frontend/.env.local` and restart Vite. This mode stores synthetic applications and demonstration reports in browser local storage; it does not call the backend or run its OCR/rules. Set it back to `false` for live mode.

## Tests and checks

Run backend tests from `backend/`:

```powershell
python -m pytest -q
```

The suite covers API routes, upload handling, OCR integration, validation rules, and the synthetic scenarios in `backend/tests/test_scenarios.py`. Its test database is in-memory SQLite; PostgreSQL is not needed. **This command could not be executed in the documentation session because neither `python` nor the Windows `py` launcher was available.**

There is no frontend test script configured in `frontend/package.json`. The configured lint and production build commands are:

```powershell
cd frontend
npm run lint
npm run build
```

Both commands were run successfully during this documentation update. `lint` runs ESLint. `build` runs the Vite production build. There is no configured test script or migration command documented by the repository.

## API workflow

The frontend uses these live endpoints (base URL `http://localhost:8000/api`):

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/applications` | Create an EoA application record |
| `GET` | `/applications` | List applications in the review queue |
| `GET` | `/applications/{application_id}` | Retrieve application, documents, and latest extracted fields |
| `POST` | `/applications/{application_id}/documents` | Upload one file with a `document_type` form field |
| `GET` | `/applications/{application_id}/documents` | List document records |
| `POST` | `/applications/{application_id}/validate` | Run the configured rules and generate findings |
| `GET` | `/applications/{application_id}/report` | Retrieve the saved validation report |

FastAPI's interactive request interface is available at `http://localhost:8000/docs` while the backend is running.

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
