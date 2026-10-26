# SIH 2026 PS 26261 — Application Validation & Document Compliance Verification

Shared project documentation for the SIH 2026 Problem Statement 26261 prototype.

## Files
- `AGENTS.md` — shared instructions for AI coding agents and module ownership.
- `docs/PROJECT_CONTEXT.md` — project purpose, MVP scope, workflow, and limitations.
- `docs/API_CONTRACT.md` — shared API shapes and integration rules.
- `docs/TASKS.md` — workstream checklists and integration checkpoints.
- `docs/DECISIONS.md` — accepted technical decisions and open scope questions.

## Project scope
The prototype supports preliminary scrutiny of institutional applications using synthetic data. It extracts selected document fields, runs explicit validation rules, and presents evidence-linked findings for human review. It does not make final AICTE approval decisions or prove document authenticity.

## Selected stack
React + Vite + Tailwind CSS; Python + FastAPI; PaddleOCR; PyMuPDF; PostgreSQL; custom Python validation rules.

## Local setup

The backend and frontend run as separate development servers. Use synthetic test documents only.

### PostgreSQL

Create a PostgreSQL database and database user, then set the connection string in `backend/.env` using `backend/.env.example`. The backend uses PostgreSQL for application data and creates its tables when it starts.

### Backend (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set DATABASE_URL to the PostgreSQL database you created.
uvicorn app.main:app --reload --port 8000
```

The API base is `http://localhost:8000/api`; interactive API documentation is at `http://localhost:8000/docs`. Uploads are stored in `backend/uploads/`, excluded from Git. The configured maximum is 10 MB and 20 PDF pages.

### Frontend (second PowerShell window)

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

`VITE_USE_MOCKS=false` uses the real backend (default); `VITE_API_BASE_URL` defaults to `http://localhost:8000`. Set `VITE_USE_MOCKS=true` only for an isolated synthetic frontend demo. Run `npm run lint` and `npm run build` from `frontend/`.

### API workflow

The frontend uses `POST /api/applications`, `GET /api/applications`, `GET /api/applications/{id}`, `POST /api/applications/{id}/documents`, `POST /api/applications/{id}/validate`, and `GET /api/applications/{id}/report`. The document checklist is the three-document EoA prototype subset recorded in `docs/AICTE_RULEBOOK_REFERENCE.md`; it is not the full EoA checklist. See `docs/API_CONTRACT.md` for request and response shapes.

Required backend environment variables are `DATABASE_URL`, `UPLOAD_DIR`, `MAX_FILE_SIZE_MB`, `MAX_PAGES`, `API_PREFIX`, `DEBUG`, and `CORS_ORIGINS`. Frontend variables are `VITE_USE_MOCKS` and `VITE_API_BASE_URL`. Use the example files as templates; do not commit local `.env` or `.env.local` files.

This system provides preliminary document scrutiny for human review. A mismatch or OCR anomaly is not proof of fraud, authenticity, or an AICTE approval decision.
