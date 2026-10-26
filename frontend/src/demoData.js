import { DOCUMENT_TYPES } from './config'

const now = new Date()
const date = (offset = 0) => new Date(now.getTime() - offset * 86400000).toISOString()

export const seedApplications = [
  {
    id: 'app_demo_01', institution_name: 'Synthetic Northfield Institute of Technology', application_category: 'eoa', academic_year: '2026-27', created_at: date(1), overall_status: 'discrepancies_found',
    documents: [
      { id: 'doc_demo_01', application_id: 'app_demo_01', document_type: 'fire_safety_certificate', original_filename: 'northfield_fire_certificate.pdf', mime_type: 'application/pdf', processing_status: 'processed', fields: [
        { name: 'Institution name', value: 'Synthetic Northfield Institute of Technology', status: 'pass', evidence: 'Institution: Synthetic Northfield Institute of Technology', page_number: 1, source_document: 'northfield_fire_certificate.pdf' },
        { name: 'Document number', value: 'FS-2026-104', status: 'pass', evidence: 'Certificate No: FS-2026-104', page_number: 1, source_document: 'northfield_fire_certificate.pdf' },
        { name: 'Expiry date', value: '2026-12-31', status: 'unresolved', evidence: null, page_number: null, source_document: 'northfield_fire_certificate.pdf' },
      ] },
      { id: 'doc_demo_02', application_id: 'app_demo_01', document_type: 'building_completion_certificate', original_filename: 'building_completion_scan.png', mime_type: 'image/png', processing_status: 'processing' },
    ],
  },
  { id: 'app_demo_02', institution_name: 'Synthetic Lakeside Polytechnic', application_category: 'eoa', academic_year: '2026-27', created_at: date(3), overall_status: 'missing_documents', documents: [] },
  { id: 'app_demo_03', institution_name: 'Synthetic Meridian College', application_category: 'eoa', academic_year: '2025-26', created_at: date(8), overall_status: 'checks_passed', documents: [] },
]

export const seedReports = {
  app_demo_01: {
    application_id: 'app_demo_01', overall_status: 'discrepancies_found',
    summary: { pass: 2, flagged: 0, missing: 1, unresolved: 2, not_applicable: 0 },
    missing_document_types: ['affidavit_2'],
    findings: [
      { id: 'finding_demo_01', rule_id: 'EXPIRY_001', status: 'unresolved', title: 'Expiry date needs reviewer confirmation', reason: 'The expiry date could not be reliably read from the supplied scan.', document_id: 'doc_demo_01', document_name: 'northfield_fire_certificate.pdf', evidence: { page_number: 1, text: 'Valid Until: [unclear]', field: 'expiry_date', value: null }, next_action: 'Review the source document and confirm the date before relying on this check.' },
      { id: 'finding_demo_02', rule_id: 'DOC_REQUIRED_001', status: 'missing', title: 'Affidavit-2 not provided', reason: 'No document is currently associated with this configured demonstration checklist item.', document_id: null, document_name: null, evidence: null, next_action: 'Upload the selected document type if it is required for this application.' },
      { id: 'finding_demo_03', rule_id: 'NAME_MATCH_001', status: 'unresolved', title: 'Institution name comparison is pending', reason: 'One document is still processing, so this comparison could not be completed.', document_id: 'doc_demo_02', document_name: 'building_completion_scan.png', evidence: null, next_action: 'Wait for processing to finish, then review the comparison.' },
    ], generated_at: date(0),
  },
}

export function labelForDocument(code) {
  return DOCUMENT_TYPES.find((item) => item.code === code)?.label || code?.replaceAll('_', ' ') || 'Document'
}
