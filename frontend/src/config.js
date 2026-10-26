// Real API mode is the default. Opt into browser-only demo data explicitly.
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export const APPLICATION_CATEGORIES = [{ code: 'eoa', label: 'Extension of Approval (EoA)' }]

// Matches the backend EoA MVP checklist and the recorded APH 2024-2027 clauses.
export const DOCUMENT_TYPES = [
  { code: 'fire_safety_certificate', label: 'Fire Safety Certificate', reference: 'APH 2024-2027, Annexure-2, §2.1(v)' },
  { code: 'building_completion_certificate', label: 'Occupancy / Completion Certificate', reference: 'APH 2024-2027, Annexure-2, §2.1(iii), Clause 7.17' },
  { code: 'affidavit_2', label: 'Affidavit-2', reference: 'APH 2024-2027, Annexure-2, §2.1(i)' },
]

export const CHECK_STATUSES = ['pass', 'flagged', 'missing', 'unresolved', 'not_applicable']
export const STATUS_LABELS = {
  ready_for_review: 'Ready for review', missing_documents: 'Missing documents', discrepancies_found: 'Discrepancies found',
  unresolved_checks: 'Unresolved checks', processing_incomplete: 'Processing incomplete', checks_passed: 'Checks passed',
  uploaded: 'Uploaded', processing: 'Processing', processed: 'Processed', processing_failed: 'Processing failed',
  pass: 'Passed', flagged: 'Flagged for review', missing: 'Missing', unresolved: 'Unresolved', not_applicable: 'Not applicable',
}
