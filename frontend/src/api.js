import { API_BASE_URL, DOCUMENT_TYPES, USE_MOCKS } from './config'
import { labelForDocument, seedApplications, seedReports } from './demoData'
import { buildReviewerDecisionPayload, pendingReviewerFindings, requiresReviewerDecision } from './reviewWorkflow'

const STORAGE_KEY = 'pramaan-demo-applications-v1'
const REPORT_KEY = 'pramaan-demo-reports-v1'
const pause = (ms = 420) => new Promise((resolve) => setTimeout(resolve, ms))
const readStore = (key, fallback) => {
  try { const value = JSON.parse(localStorage.getItem(key)); return value ?? structuredClone(fallback) }
  catch { return structuredClone(fallback) }
}
const writeStore = (key, value) => localStorage.setItem(key, JSON.stringify(value))
let inMemoryAccessToken = null
let refreshPromise = null

export const setAccessToken = (token) => {
  inMemoryAccessToken = token
}

export const getAccessToken = () => inMemoryAccessToken

const errorMessage = async (response) => {
  try {
    const payload = await response.json()
    const detail = payload?.error?.details || payload?.detail
    const msg = payload?.error?.message || payload?.message
    if (detail && typeof detail === 'string') {
      return `${msg || 'Error'}: ${detail}`
    }
    return msg || `Request failed (${response.status}).`
  } catch {
    return `Request failed (${response.status}).`
  }
}

async function request(path, options = {}, isRetry = false) {
  const headers = new Headers(options.headers || {})
  if (inMemoryAccessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${inMemoryAccessToken}`)
  }

  const fetchOptions = {
    ...options,
    headers,
    credentials: 'include',
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}/api${path}`, fetchOptions)
  } catch {
    throw new Error(`Could not reach the API at ${API_BASE_URL}. Check that the backend is running.`)
  }

  // Handle 401: attempt single-flight token refresh if not already on auth path and not retry
  if (response.status === 401 && !isRetry && !path.startsWith('/auth/')) {
    try {
      if (!refreshPromise) {
        refreshPromise = refreshAuth().finally(() => {
          refreshPromise = null
        })
      }
      const refreshResult = await refreshPromise
      if (refreshResult?.access_token) {
        return request(path, options, true)
      }
    } catch {
      inMemoryAccessToken = null
      throw new Error(await errorMessage(response))
    }
  }

  if (!response.ok) throw new Error(await errorMessage(response))
  if (response.status === 204) return null
  return response.json()
}

// Authentication API methods
export async function login(email, password) {
  if (USE_MOCKS) {
    await pause(350)
    const isReviewer = email.toLowerCase().includes('reviewer')
    const user = {
      id: isReviewer ? 'rev_mock_1' : 'inst_mock_1',
      email,
      role: isReviewer ? 'REVIEWER' : 'INSTITUTION',
      is_active: true,
      institution_name: isReviewer ? null : 'Government Engineering College (Demo)',
    }
    const token = 'mock_jwt_access_token'
    setAccessToken(token)
    return { access_token: token, token_type: 'bearer', user }
  }

  const data = await request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  setAccessToken(data.access_token)
  return data
}

export async function register(email, password, institutionName) {
  if (USE_MOCKS) {
    await pause(450)
    const user = {
      id: `inst_mock_${Date.now()}`,
      email,
      role: 'INSTITUTION',
      is_active: true,
      institution_name: institutionName,
    }
    const token = 'mock_jwt_access_token'
    setAccessToken(token)
    return { access_token: token, token_type: 'bearer', user }
  }

  const data = await request('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      institution_name: institutionName,
    }),
  })
  setAccessToken(data.access_token)
  return data
}

export async function refreshAuth() {
  if (USE_MOCKS) {
    await pause(200)
    return { access_token: inMemoryAccessToken }
  }

  const data = await request('/auth/refresh', { method: 'POST' })
  setAccessToken(data.access_token)
  return data
}

export async function logout() {
  if (USE_MOCKS) {
    await pause(150)
    setAccessToken(null)
    return { message: 'Logged out' }
  }

  try {
    await request('/auth/logout', { method: 'POST' })
  } finally {
    setAccessToken(null)
  }
}

export async function getCurrentUser() {
  if (USE_MOCKS) {
    await pause(100)
    if (!inMemoryAccessToken) return null
    return {
      id: 'mock_user_1',
      email: 'institution@engg-college.edu.in',
      role: 'INSTITUTION',
      is_active: true,
      institution_name: 'Government Engineering College (Demo)',
    }
  }

  return request('/auth/me')
}

export async function submitApplication(applicationId) {
  if (USE_MOCKS) {
    await pause(350)
    const apps = mockApplications()
    const app = apps.find((a) => a.id === applicationId)
    if (app) {
      const requiredTypes = DOCUMENT_TYPES.filter((doc) => doc.applicability === 'required').map((doc) => doc.code)
      const presentTypes = new Set((app.documents || []).map((doc) => doc.document_type))
      const missing = requiredTypes.filter((type) => !presentTypes.has(type))
      if (missing.length) throw new Error(`Upload all required document types before submission: ${missing.map((type) => labelForDocument(type)).join(', ')}.`)
      if (app.status && app.status !== 'draft') throw new Error('This application has already been submitted and is locked for review.')
      app.status = 'submitted'
      writeStore(STORAGE_KEY, apps)
    }
    return app
  }

  return request(`/applications/${encodeURIComponent(applicationId)}/submit`, {
    method: 'POST',
  })
}

export async function finalizeApplicationReview(applicationId) {
  if (USE_MOCKS) {
    await pause(350)
    const apps = mockApplications()
    const app = apps.find((item) => item.id === applicationId)
    if (!app || app.status !== 'submitted') throw new Error('Only an application pending review can be finalized.')
    const report = mockReports()[applicationId]
    const findings = report?.findings || []
    if (!findings.length) throw new Error('Run scrutiny checks before finalizing this review.')
    const pending = pendingReviewerFindings(findings).length
    if (pending) throw new Error(`Review all ${pending} remaining finding${pending === 1 ? '' : 's'} before finalizing.`)
    app.status = 'review_completed'
    writeStore(STORAGE_KEY, apps)
    return app
  }

  return request(`/applications/${encodeURIComponent(applicationId)}/finalize-review`, { method: 'POST' })
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
    if (report) {
      if (report.findings?.some((finding) => finding.reviewer_decision || finding.reviewed_at)) {
        throw new Error('Checks cannot be rerun after a reviewer decision is recorded because rerunning would replace the audit findings.')
      }
      return report
    }
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

export async function reviewFinding(applicationId, findingId, payload) {
  const decisionPayload = buildReviewerDecisionPayload(payload.reviewer_decision, payload.reviewer_notes)
  if (USE_MOCKS) {
    await pause(300)
    const reports = mockReports()
    const report = reports[applicationId]
    if (report && report.findings) {
      const finding = report.findings.find((f) => f.id === findingId)
      if (!finding) throw new Error('Finding not found in the demonstration report.')
      if (!requiresReviewerDecision(finding)) throw new Error('This finding does not require a reviewer decision.')
      finding.reviewer_decision = decisionPayload.reviewer_decision
      finding.reviewer_notes = decisionPayload.reviewer_notes || null
      finding.reviewed_by = payload.reviewed_by || 'Signed-in demonstration reviewer'
      finding.reviewed_at = new Date().toISOString()
      writeStore(REPORT_KEY, reports)
      return structuredClone(finding)
    }
    throw new Error('No demonstration report is available for this application.')
  }
  return request(`/applications/${encodeURIComponent(applicationId)}/findings/${encodeURIComponent(findingId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...decisionPayload, reviewed_by: payload.reviewed_by }),
  })
}

export function getDocumentFileUrl(applicationId, documentId) {
  const token = inMemoryAccessToken
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  return `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(documentId)}/file${query}`
}

export async function fetchDocumentBlob(applicationId, documentId) {
  let token = inMemoryAccessToken
  const headers = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const url = `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(documentId)}/file`
  let response = await fetch(url, { headers, credentials: 'include' })

  if (response.status === 401) {
    try {
      if (!refreshPromise) {
        refreshPromise = refreshAuth().finally(() => {
          refreshPromise = null
        })
      }
      const refreshResult = await refreshPromise
      if (refreshResult?.access_token) {
        token = refreshResult.access_token
        headers['Authorization'] = `Bearer ${token}`
        response = await fetch(url, { headers, credentials: 'include' })
      }
    } catch {
      inMemoryAccessToken = null
      throw new Error('Authentication expired. Please log in again.')
    }
  }

  if (!response.ok) {
    throw new Error(await errorMessage(response))
  }
  return response.blob()
}

export function getChecklist() { return DOCUMENT_TYPES }

