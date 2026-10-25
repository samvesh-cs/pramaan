export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

// EoA is the contract's candidate code, not a team-confirmed category.
export const APPLICATION_CATEGORIES = [{ code: 'eoa', label: 'Extension of Approval (EoA)', configuredAssumption: true }]

// Demonstration checklist only. Replace with team-confirmed, source-backed configuration.
export const DOCUMENT_TYPES = [
  { code: 'fire_safety_certificate', label: 'Fire safety certificate', reference: 'Demonstration requirement' },
  { code: 'building_safety_certificate', label: 'Building safety certificate', reference: 'Demonstration requirement' },
  { code: 'audited_accounts', label: 'Audited accounts', reference: 'Demonstration requirement' },
]

export const CHECK_STATUSES = ['pass', 'flagged', 'missing', 'unresolved', 'not_applicable']
export const STATUS_LABELS = {
  ready_for_review: 'Ready for review', missing_documents: 'Missing documents', discrepancies_found: 'Discrepancies found',
  unresolved_checks: 'Unresolved checks', processing_incomplete: 'Processing incomplete', checks_passed: 'Checks passed',
  uploaded: 'Uploaded', processing: 'Processing', processed: 'Processed', processing_failed: 'Processing failed',
  pass: 'Passed', flagged: 'Flagged for review', missing: 'Missing', unresolved: 'Unresolved', not_applicable: 'Not applicable',
}
