// Real API mode is the default. Opt into browser-only demo data explicitly.
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export const APPLICATION_CATEGORIES = [{ code: 'eoa', label: 'Extension of Approval (EoA)' }]

// Matches the backend EoA MVP checklist and the recorded APH 2024-2027 clauses.
export const DOCUMENT_TYPES = [
  { code: 'fire_safety_certificate', label: 'Fire Safety Certificate', applicability: 'required', reference: 'APH 2024-2027, Annexure-2, §2.1(v)' },
  { code: 'building_completion_certificate', label: 'Occupancy / Completion Certificate', applicability: 'required', reference: 'APH 2024-2027, Annexure-2, §2.1(iii), Clause 7.17' },
  { code: 'affidavit_2', label: 'Affidavit-2', applicability: 'required', reference: 'APH 2024-2027, Annexure-2, §2.1(i)' },
  { code: 'ter_payment_receipt', label: 'TER Payment Receipt', applicability: 'required_if_applicable', reference: 'APH 2024-2027, Annexure-2, §2.1(ii) & Table 2.1' },
  { code: 'structural_stability_certificate', label: 'Structural Stability Certificate (>30 Yrs)', applicability: 'required_if_applicable', reference: 'APH 2024-2027, Annexure-2, §2.1(iv)' },
]

export const CHECK_STATUSES = ['pass', 'flagged', 'missing', 'unresolved', 'not_applicable']
export const STATUS_LABELS = {
  draft: 'Draft', submitted: 'Pending review', review_completed: 'Review completed',
  ready_for_review: 'Ready for review', missing_documents: 'Missing documents', discrepancies_found: 'Discrepancies found',
  unresolved_checks: 'Unresolved checks', processing_incomplete: 'Processing incomplete', checks_passed: 'Checks passed',
  uploaded: 'Uploaded', processing: 'Processing', processed: 'Processed', processing_failed: 'Processing failed',
  pass: 'Passed', flagged: 'Flagged for review', missing: 'Missing', unresolved: 'Unresolved', not_applicable: 'Not applicable',
  verified: 'Verified by Auditor', confirmed_discrepancy: 'Confirmed Discrepancy', requested_resubmission: 'Resubmission Requested', escalated: 'Escalated to Committee',
}
