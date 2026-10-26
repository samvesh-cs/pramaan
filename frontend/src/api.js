import { API_BASE_URL, DOCUMENT_TYPES, USE_MOCKS } from './config'
import { seedApplications, seedReports } from './demoData'

const STORAGE_KEY = 'pramaan-demo-applications-v1'
const REPORT_KEY = 'pramaan-demo-reports-v1'
const pause = (ms = 420) => new Promise((resolve) => setTimeout(resolve, ms))
const readStore = (key, fallback) => {
  try { const value = JSON.parse(localStorage.getItem(key)); return value ?? structuredClone(fallback) }
  catch { return structuredClone(fallback) }
}
const writeStore = (key, value) => localStorage.setItem(key, JSON.stringify(value))
const errorMessage = async (response) => {
  try { const payload = await response.json(); return payload?.error?.message || `Request failed (${response.status}).` }
  catch { return `Request failed (${response.status}).` }
}
async function request(path, options) {
  let response
  try { response = await fetch(`${API_BASE_URL}/api${path}`, options) }
  catch { throw new Error(`Could not reach the API at ${API_BASE_URL}. Check that the backend is running.`) }
  if (!response.ok) throw new Error(await errorMessage(response))
  if (response.status === 204) return null
  return response.json()
}
const mockApplications = () => readStore(STORAGE_KEY, seedApplications)
const mockReports = () => readStore(REPORT_KEY, seedReports)

export async function listApplications() {
  if (USE_MOCKS) {
    await pause(260); return mockApplications()
  }
  return request('/applications')
}

export async function getApplication(id) {
  if (USE_MOCKS) { await pause(250); return mockApplications().find((item) => item.id === id) || null }
  return request(`/applications/${encodeURIComponent(id)}`)
}

export async function createApplication(payload) {
  if (USE_MOCKS) {
    await pause(650)
    const app = { ...payload, id: `app_demo_${Date.now()}`, created_at: new Date().toISOString(), overall_status: 'processing_incomplete', documents: [] }
    const apps = mockApplications(); apps.unshift(app); writeStore(STORAGE_KEY, apps); return app
  }
  return request('/applications', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
}

export async function uploadDocument(applicationId, file, documentType) {
  if (USE_MOCKS) {
    await pause(850)
    const doc = { id: `doc_demo_${Date.now()}`, application_id: applicationId, document_type: documentType, original_filename: file.name, mime_type: file.type || 'application/octet-stream', processing_status: 'uploaded' }
    const apps = mockApplications(); const app = apps.find((item) => item.id === applicationId)
    if (!app) throw new Error('Application not found in demonstration data.')
    app.documents ||= []; app.documents.push(doc); writeStore(STORAGE_KEY, apps); return doc
  }
  const form = new FormData(); form.append('file', file); form.append('document_type', documentType)
  return request(`/applications/${encodeURIComponent(applicationId)}/documents`, { method: 'POST', body: form })
}

export async function runValidation(applicationId) {
  if (USE_MOCKS) {
    await pause(1300)
    const reports = mockReports(); const report = reports[applicationId]
    if (report) return report
    const app = mockApplications().find((item) => item.id === applicationId)
    if (!app) throw new Error('Application not found in demonstration data.')
    const docs = app.documents || []
    const present = new Set(docs.map((doc) => doc.document_type))
    const missing = DOCUMENT_TYPES.filter((doc) => !present.has(doc.code)).map((doc) => doc.code)
    const generated = {
      application_id: applicationId, overall_status: missing.length ? 'missing_documents' : 'unresolved_checks',
      summary: { pass: 0, flagged: 0, missing: missing.length, unresolved: docs.length ? 1 : 0, not_applicable: 0 }, missing_document_types: missing,
      findings: docs.length ? [{ id: `finding_${Date.now()}`, rule_id: 'DEMO_REVIEW_001', status: 'unresolved', title: 'Reviewer inspection required', reason: 'The demonstration audit does not make a final assessment.', document_id: docs[0].id, document_name: docs[0].original_filename, evidence: null, next_action: 'Inspect the supplied file and confirm all relevant details.' }] : [], generated_at: new Date().toISOString(),
    }
    reports[applicationId] = generated; writeStore(REPORT_KEY, reports); return generated
  }
  await request(`/applications/${encodeURIComponent(applicationId)}/validate`, { method: 'POST' })
  return request(`/applications/${encodeURIComponent(applicationId)}/report`)
}

export async function getReport(applicationId) {
  if (USE_MOCKS) { await pause(300); return mockReports()[applicationId] || null }
  return request(`/applications/${encodeURIComponent(applicationId)}/report`)
}

export function getChecklist() { return DOCUMENT_TYPES }
