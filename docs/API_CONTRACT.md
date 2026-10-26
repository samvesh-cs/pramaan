# API_CONTRACT.md — Frontend / Backend / OCR Integration

This is the shared contract for the prototype. Keep property names and status values consistent. If the implementation needs to change, update this file and notify every affected owner before changing code.

## 1. General conventions
- Base URL during local development: `http://localhost:8000`
- API prefix: `/api`
- Request/response content type: `application/json`, except file-upload requests, which use `multipart/form-data`.
- IDs are strings in API JSON. Database internals may use native types, but serialize them consistently.
- Dates in structured fields use ISO `YYYY-MM-DD`. If a date cannot be parsed, set the structured value to `null` and preserve the raw text.
- Never send local filesystem absolute paths to the frontend.
- Do not return stack traces or secrets in user-facing errors.

## 2. Standard status values
### Check status
Use exactly one of:
- `pass` — the check ran and passed.
- `flagged` — the check ran and found a potential issue/discrepancy.
- `missing` — a required document or required field is absent.
- `unresolved` — the check could not be completed reliably.
- `not_applicable` — the requirement does not apply.

Do not use `failed`, `warning`, `error`, or other synonyms as check status values. Errors in processing are represented separately using HTTP errors or document processing status.

### Document processing status
- `uploaded`
- `processing`
- `processed`
- `processing_failed`

### Overall application status
Use one of:
- `ready_for_review` — processing and selected checks are complete, with no flagged/missing/unresolved results.
- `missing_documents`
- `discrepancies_found`
- `unresolved_checks`
- `processing_incomplete` — at least one document has not been successfully processed.
- `checks_passed` — all configured applicable checks ran and passed.

Priority when multiple conditions exist: `processing_incomplete` > `missing_documents` > `discrepancies_found` > `unresolved_checks` > `checks_passed`. `ready_for_review` is reserved for a complete application awaiting human review; do not use it as an approval status. The team may simplify the visible status labels, but keep the backend semantics consistent.

## 3. Application schema
### Create application
`POST /api/applications`

Request:
```json
{
  "institution_name": "Synthetic ABC Engineering College",
  "application_category": "eoa",
  "academic_year": "2026-27"
}
```

Response: `201 Created`
```json
{
  "id": "app_001",
  "institution_name": "Synthetic ABC Engineering College",
  "application_category": "eoa",
  "academic_year": "2026-27",
  "created_at": "2026-10-24T12:00:00Z",
  "overall_status": "processing_incomplete"
}
```

`application_category` is a stable code, not a display label. The selected Basic MVP category is `eoa` (EoA Self-Disclosure); other categories are not supported.

### Get application
`GET /api/applications/{application_id}`

Response:
```json
{
  "id": "app_001",
  "institution_name": "Synthetic ABC Engineering College",
  "application_category": "eoa",
  "academic_year": "2026-27",
  "overall_status": "processing_incomplete",
  "documents": [],
  "findings": []
}
```

### List applications
`GET /api/applications`

Response: `200 OK`, an array of the application response objects above, ordered newest first. This additive endpoint supports the reviewer queue used by the frontend.

## 4. Upload document
`POST /api/applications/{application_id}/documents`

Request: `multipart/form-data`
- `file`: required PDF, JPG, or PNG file.
- `document_type`: required stable document-type code, selected from the configured checklist. Example: `fire_safety_certificate`.
- `issued_date` and `expiry_date` are not supplied by the client as authoritative data; they must be extracted or entered through an explicitly marked reviewer correction flow, if such a flow is implemented.

Response: `201 Created`
```json
{
  "id": "doc_001",
  "application_id": "app_001",
  "document_type": "fire_safety_certificate",
  "original_filename": "sample_fire_certificate.pdf",
  "mime_type": "application/pdf",
  "processing_status": "uploaded",
  "fields": {
    "document_number": {
      "value": "FS-2026-104",
      "normalized_value": "FS-2026-104",
      "raw_text": "Certificate No: FS-2026-104",
      "confidence": 0.94,
      "page_number": 1,
      "bbox": [100, 180, 330, 210],
      "status": "extracted"
    }
  }
}
```

`fields` contains the latest extraction result using the field structure in section 5. It may be empty if processing has not produced fields. Application detail responses include this property on each document so the reviewer can inspect actual extracted values.

The server must validate file size, extension and detected content type. Do not trust the filename alone. The exact maximum file size must be set in configuration and documented in the README.

## 5. Document extraction result
This is the internal output shape expected from Person 2's OCR/extraction module. Person 3 integrates it; it does not need to be exposed directly as a public endpoint unless useful for debugging.

```json
{
  "document_id": "doc_001",
  "document_type": "fire_safety_certificate",
  "processing_status": "processed",
  "pages": [
    {
      "page_number": 1,
      "text": "Institution: Synthetic ABC Engineering College\nCertificate No: FS-2026-104\nValid Until: 2026-12-31",
      "regions": [
        {
          "text": "Synthetic ABC Engineering College",
          "confidence": 0.97,
          "bbox": [100, 120, 440, 150]
        }
      ]
    }
  ],
  "fields": {
    "institution_name": {
      "value": "Synthetic ABC Engineering College",
      "normalized_value": "synthetic abc engineering college",
      "raw_text": "Institution: Synthetic ABC Engineering College",
      "confidence": 0.97,
      "page_number": 1,
      "bbox": [100, 120, 440, 150]
    },
    "document_number": {
      "value": "FS-2026-104",
      "normalized_value": "FS-2026-104",
      "raw_text": "Certificate No: FS-2026-104",
      "confidence": 0.94,
      "page_number": 1,
      "bbox": [100, 180, 330, 210]
    },
    "issue_date": {
      "value": null,
      "normalized_value": null,
      "raw_text": null,
      "confidence": null,
      "page_number": null,
      "bbox": null
    },
    "expiry_date": {
      "value": "2026-12-31",
      "normalized_value": "2026-12-31",
      "raw_text": "Valid Until: 2026-12-31",
      "confidence": 0.96,
      "page_number": 1,
      "bbox": [100, 240, 330, 270]
    }
  },
  "error": null
}
```

Rules:
- Field keys must be stable snake_case.
- `value` is the parsed value; use `null` if not reliably extracted.
- `raw_text` preserves the supporting original snippet when available.
- `confidence` is a number from `0` to `1` when supplied by OCR, otherwise `null`. Do not fabricate confidence for PDF text extraction.
- `status` is `extracted`, `missing`, or `uncertain`; it describes extraction certainty, not a compliance result.
- For validation, OCR confidence below `0.70` is treated as uncertain and produces an `unresolved` check for a rule that relies on that value. This is a prototype review threshold, not an AICTE requirement.
- `bbox` is `[x1, y1, x2, y2]` in the coordinate system of the processed page image. If the coordinates are not available, use `null`.
- `page_number` is 1-based.
- The field list can contain only fields configured for the selected document type; this example shows the common fields for illustration.
- OCR extraction must not make compliance decisions. It only returns recognized text and extracted fields.

## 6. Validation finding schema
Each rule returns one finding in this format:
```json
{
  "id": "finding_001",
  "rule_id": "EXPIRY_001",
  "status": "flagged",
  "title": "Document appears expired",
  "reason": "The extracted expiry date is earlier than the current date.",
  "document_id": "doc_001",
  "document_name": "sample_fire_certificate.pdf",
  "evidence": {
    "page_number": 1,
    "text": "Valid Until: 2025-12-31",
    "field": "expiry_date",
    "value": "2025-12-31",
    "bbox": [100, 240, 330, 270]
  },
  "next_action": "Request a current document or have a reviewer confirm the extracted date."
}
```

Rules:
- `document_id` may be `null` for an application-level finding such as a missing document type.
- `evidence` may be `null` if no reliable evidence is available; explain why in `reason`.
- Never say that a document is forged based only on OCR or a mismatch.
- The rule engine must not silently treat missing extracted values as passing checks.

## 7. Report response
`GET /api/applications/{application_id}/report`

Response:
```json
{
  "application_id": "app_001",
  "overall_status": "discrepancies_found",
  "summary": {
    "pass": 3,
    "flagged": 1,
    "missing": 1,
    "unresolved": 0,
    "not_applicable": 0
  },
  "missing_document_types": ["affidavit_2"],
  "findings": [],
  "generated_at": "2026-10-24T12:05:00Z"
}
```

The summary counts are illustrative. In implementation, calculate them from the actual current validation run. Decide and document whether summary counts include checklist items as well as field-level rules; use one consistent method throughout.

## 8. Error response format
Use this shape for API errors:
```json
{
  "error": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Upload a PDF, JPG, or PNG file.",
    "details": null
  }
}
```

Suggested codes:
- `APPLICATION_NOT_FOUND`
- `UNSUPPORTED_FILE_TYPE`
- `FILE_TOO_LARGE`
- `INVALID_FILE_CONTENT`
- `PDF_PROCESSING_FAILED`
- `OCR_FAILED`
- `VALIDATION_FAILED`
- `INTERNAL_ERROR`

Do not return sensitive internal details or stack traces to the client.

## 9. Minimum endpoints
- `POST /api/applications`
- `GET /api/applications`
- `GET /api/applications/{application_id}`
- `POST /api/applications/{application_id}/documents`
- `GET /api/applications/{application_id}/documents`
- `POST /api/applications/{application_id}/validate`
- `GET /api/applications/{application_id}/report`

Keep endpoint naming consistent with this file. FastAPI's interactive docs may be used for manual testing.

## 10. Contract change process
Before changing a field name, status value, endpoint, or required property:
1. Propose the change in the team chat.
2. Update this file.
3. Tell the owners of the affected modules.
4. Update code and tests together.
5. Verify frontend/backend integration after merging.
