# AICTE Document Scrutiny & Compliance Verification Backend

FastAPI backend and validation engine for SIH 2026 (Problem Statement 26261).

Provides automated institutional document compliance verification for AICTE Extension of Approval (EoA) applications under the Approval Process Handbook (APH 2024-2027, Annexure-2 §2.1).

## Tech Stack
- **Framework:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL (with SQLAlchemy 2.0 Async + asyncpg)
- **PDF Processing:** PyMuPDF (version range in `requirements.txt`)
- **OCR:** PaddleOCR 3.7.0 with PaddlePaddle 3.3.1
- **Validation Engine:** Modular Python Rule Engine
- **Contract:** Uses `docs/API_CONTRACT.md` for routes, statuses, and response shapes

## Getting Started

### 1. Setup Virtual Environment
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure the required PostgreSQL connection in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://<username>:<password>@localhost:5432/<dbname>
```
The API initializes its tables at startup. SQLite is used only by the isolated pytest setup, not as the application database.

### 4. Run the Dev Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000/api`
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

### 5. Run Tests
```bash
pytest -v
```

## API Endpoints (Summary)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/applications` | Create a new institutional application |
| `GET` | `/api/applications` | List all institutional applications |
| `GET` | `/api/applications/{id}` | Get application details, uploaded documents, and findings |
| `POST` | `/api/applications/{id}/documents` | Upload a document (`fire_safety_certificate`, `building_completion_certificate`, `affidavit_2`) |
| `GET` | `/api/applications/{id}/documents` | List uploaded documents for an application |
| `POST` | `/api/applications/{id}/validate` | Run validation engine pipeline and generate findings |
| `GET` | `/api/applications/{id}/report` | Retrieve the validation compliance report |

## EoA Supported Document Types (MVP)
1. `fire_safety_certificate` (Fire Safety Certificate / NOC)
2. `building_completion_certificate` (Occupancy / Building Completion Certificate)
3. `affidavit_2` (Affidavit-2 on Stamp Paper)

## Demo Test Scenarios (`tests/demo_samples/`)
Pre-generated synthetic PDFs are provided in `tests/demo_samples/` for evaluator demonstration:
1. **Scenario 1 — All Valid (`checks_passed`):**
   - `valid_fire_safety.pdf`
   - `valid_building_completion.pdf`
   - `valid_affidavit_2.pdf`
2. **Scenario 2 — Missing Document (`missing_documents`):**
   - Only 2 of 3 documents uploaded (e.g. missing `affidavit_2`).
3. **Scenario 3 — Expired Document (`discrepancies_found`):**
   - `expired_fire_safety.pdf` (expired 2023) triggers `EXPIRY_001` flagged finding.
4. **Scenario 4 — Missing Fields (`missing_documents`):**
   - `missing_fields_building.pdf` lacks required certificate number, triggering `FIELD_002` missing finding.
5. **Scenario 5 — Cross-Document Mismatch (`discrepancies_found`):**
   - `mismatched_fire_safety.pdf` contains a different college name, triggering `CONSISTENCY_001` flagged finding.

Full scenario manifest: `tests/demo_samples/manifest.json`.
Generate fresh samples anytime with: `python tests/generate_demo_dataset.py`.
