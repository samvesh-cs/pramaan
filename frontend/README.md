# SIH 2026 · PS 26261 frontend

React + Vite + Tailwind reviewer workspace. The frontend supports preliminary scrutiny; it does not prove authenticity or make AICTE approval decisions.

## Run locally (Windows PowerShell)

```powershell
cd C:\path\to\sih-prototype-main\frontend
npm install
npm run dev
```

The default mode uses the FastAPI API at `http://localhost:8000`. Copy `.env.example` to `.env.local` to configure it. Set `VITE_USE_MOCKS=true` only for isolated frontend demonstrations backed by synthetic browser `localStorage` data; the header identifies that mode as **DEMO DATA**.

## Pages

- `/` — review queue and overview
- `/documents` — choose an application and jump directly to its document centre
- `/applications/new` — create an application
- `/applications/:id/documents` — upload documents, checklist, and extracted-field inspection
- `/applications/:id/audit` — request preliminary validation
- `/applications/:id/report` — inspect returned summary and findings

## Integration notes

- Application and upload requests follow `docs/API_CONTRACT.md` exactly. Audit runs use `POST /api/applications/{id}/validate`, then read the documented report endpoint; the validation response itself is not assumed to have a schema.
- The application list uses `GET /api/applications`, implemented by the backend and documented in the API contract.
- The EoA MVP document codes and source clauses match the backend checklist. This is a three-document prototype subset, not a complete EoA checklist.
- Document-list detail is read from the documented application response. The standalone document-list endpoint has no response schema in the current contract.
- No upload-size, page-count, or extraction-confidence values are invented. The browser filters the contract's PDF/JPG/PNG formats; the API remains responsible for file validation.

## Commands

```powershell
npm run lint
npm run build
npm run preview
```
