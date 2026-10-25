# SIH 2026 · PS 26261 frontend

React + Vite + Tailwind reviewer workspace. The frontend supports preliminary scrutiny; it does not prove authenticity or make AICTE approval decisions.

## Run locally (Windows PowerShell)

```powershell
cd C:\path\to\sih-prototype-main\frontend
npm install
npm run dev
```

The default mode is a synthetic demonstration backed by browser `localStorage`. The header identifies it as **DEMO DATA**. Set `VITE_USE_MOCKS=false` in a local `.env.local` to use the documented API base URL (`http://localhost:8000` by default). Copy `.env.example` as a starting point.

## Pages

- `/` — review queue and overview
- `/documents` — choose an application and jump directly to its document centre
- `/applications/new` — create an application
- `/applications/:id/documents` — upload documents, checklist, and extracted-field inspection
- `/applications/:id/audit` — request preliminary validation
- `/applications/:id/report` — inspect returned summary and findings

## Integration notes

- Application and upload requests follow `docs/API_CONTRACT.md` exactly. Audit runs use `POST /api/applications/{id}/validate`, then read the documented report endpoint; the validation response itself is not assumed to have a schema.
- The contract does not define an applications list endpoint, so the overview shows a useful API-mode error instead of inventing one when mock mode is disabled.
- The application category (`eoa`) is a configurable candidate code, pending team confirmation. The document checklist is synthetic demo configuration, not an official AICTE checklist. Replace the constants in `src/config.js` when decisions are confirmed.
- Document-list detail is read from the documented application response. The standalone document-list endpoint has no response schema in the current contract.
- No upload-size, page-count, or extraction-confidence values are invented. The browser filters the contract's PDF/JPG/PNG formats; the API remains responsible for file validation.

## Commands

```powershell
npm run lint
npm run build
npm run preview
```
