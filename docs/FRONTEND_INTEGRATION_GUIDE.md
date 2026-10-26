# Frontend Integration Guide for Person 1 (Reviewer Dashboard)

> **Audience:** Person 1 (Frontend Developer — React + Vite + Tailwind CSS)  
> **Backend Status:** Ready & Verified (FastAPI live at `http://localhost:8000`)  
> **Interactive Swagger UI:** `http://localhost:8000/docs`  
> **Source of Truth:** [API_CONTRACT.md](file:///c:/SIH%2026/sih-prototype/docs/API_CONTRACT.md)

---

## 1. Vite Proxy Configuration

In `frontend/vite.config.js`:
```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

---

## 2. API Endpoints Quick Reference

### Step 1: Create or Load Application
```http
POST /api/applications
Content-Type: application/json

{
  "institution_name": "Synthetic ABC Institute of Technology",
  "application_category": "eoa",
  "academic_year": "2026-27"
}
```
**Response (`201 Created`):**
```json
{
  "id": "app_e1a2b3c4",
  "institution_name": "Synthetic ABC Institute of Technology",
  "application_category": "eoa",
  "academic_year": "2026-27",
  "created_at": "2026-10-25T12:00:00Z",
  "overall_status": "processing_incomplete"
}
```

---

### Step 2: Upload Supporting Documents
```http
POST /api/applications/{application_id}/documents
Content-Type: multipart/form-data

file: <File Binary: PDF, JPG, PNG>
document_type: "fire_safety_certificate" | "building_completion_certificate" | "affidavit_2"
```
**Response (`201 Created`):**
```json
{
  "id": "doc_f8e7d6c5",
  "application_id": "app_e1a2b3c4",
  "document_type": "fire_safety_certificate",
  "original_filename": "valid_fire_safety.pdf",
  "mime_type": "application/pdf",
  "processing_status": "processed"
}
```

---

### Step 3: Trigger Automated Scrutiny & Validation
```http
POST /api/applications/{application_id}/validate
```
**Response (`200 OK`):**
```json
{
  "application_id": "app_e1a2b3c4",
  "overall_status": "checks_passed",
  "summary": {
    "pass": 6,
    "flagged": 0,
    "missing": 0,
    "unresolved": 0,
    "not_applicable": 0
  },
  "missing_document_types": [],
  "findings": [
    {
      "id": "finding_a1b2c3d4",
      "rule_id": "EXPIRY_001",
      "status": "pass",
      "title": "Fire Safety Certificate is currently valid",
      "reason": "The extracted expiry date (2027-02-09) is on or after the reference date.",
      "document_id": "doc_f8e7d6c5",
      "document_name": "valid_fire_safety.pdf",
      "evidence": {
        "page_number": 1,
        "text": "Valid Until: 09-02-2027",
        "field": "expiry_date",
        "value": "2027-02-09",
        "bbox": [55.0, 240.0, 320.0, 260.0]
      },
      "next_action": null
    }
  ],
  "generated_at": "2026-10-25T12:05:00Z"
}
```

---

### Step 4: Fetch Detailed Application State (for View Reload)
```http
GET /api/applications/{application_id}
```
Returns application metadata, uploaded `documents` array, and latest `findings` array.

---

## 3. UI Component Architecture for Reviewer Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Application Header: "Synthetic ABC Institute of Technology" | EoA 2026-27   │
│ Status Badge: [ CHECKS PASSED / DISCREPANCIES FOUND / MISSING DOCUMENTS ]   │
├───────────────────────────────────┬─────────────────────────────────────────┤
│ Left Panel: Document Checklist    │ Right Panel: Validation Findings        │
│ --------------------------------- │ --------------------------------------- │
│ 1. Fire Safety Certificate   [OK] │ [PASS] All mandatory documents present  │
│ 2. Building Completion Cert  [OK] │ [FLAG] Expiry date issue (if any)       │
│ 3. Affidavit-2               [OK] │ [FLAG] Name mismatch warning (if any)   │
│                                   │                                         │
│ [ + Upload New Document ]         │ Click finding -> Highlights bbox in doc │
├───────────────────────────────────┴─────────────────────────────────────────┤
│ Center / Bottom: Document Preview & Extracted Fields                        │
│ - Render PDF page with bounding box [x1, y1, x2, y2] highlights            │
│ - Extracted Fields: Certificate No, Issue Date, Expiry Date, Authority      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Status Badge Color Guide

| Status Code | Display Label | Recommended Color |
|---|---|---|
| `checks_passed` | Checks Passed | Green (`bg-emerald-500/10 text-emerald-600 border-emerald-500`) |
| `discrepancies_found` | Discrepancies Found | Amber (`bg-amber-500/10 text-amber-600 border-amber-500`) |
| `missing_documents` | Missing Documents | Rose (`bg-rose-500/10 text-rose-600 border-rose-500`) |
| `unresolved_checks` | Unresolved Checks | Blue (`bg-sky-500/10 text-sky-600 border-sky-500`) |
| `processing_incomplete` | Processing Incomplete | Slate (`bg-slate-500/10 text-slate-600 border-slate-500`) |
| `ready_for_review` | Ready For Review | Violet (`bg-violet-500/10 text-violet-600 border-violet-500`) |

---

## 5. Ready-Made Demo Files (`backend/tests/demo_samples/`)

Person 1 can use these pre-generated PDFs for 1-click live demo buttons:

1. **Clean/Valid Demo:**
   - `backend/tests/demo_samples/valid_fire_safety.pdf`
   - `backend/tests/demo_samples/valid_building_completion.pdf`
   - `backend/tests/demo_samples/valid_affidavit_2.pdf`
   - *Outcome:* `checks_passed` (Green)
2. **Expired Document Demo:**
   - `backend/tests/demo_samples/expired_fire_safety.pdf`
   - *Outcome:* `discrepancies_found` (Amber), `EXPIRY_001` flagged
3. **Missing Fields Demo:**
   - `backend/tests/demo_samples/missing_fields_building.pdf`
   - *Outcome:* `missing_documents` (Rose), `FIELD_002` missing certificate number
4. **Name Mismatch Demo:**
   - `backend/tests/demo_samples/mismatched_fire_safety.pdf`
   - *Outcome:* `discrepancies_found` (Amber), `CONSISTENCY_001` flagged
