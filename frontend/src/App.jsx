import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { APPLICATION_CATEGORIES, CHECK_STATUSES, STATUS_LABELS, USE_MOCKS } from './config'
import { labelForDocument } from './demoData'
import { createApplication, getApplication, getChecklist, getReport, listApplications, runValidation, uploadDocument, reviewFinding, finalizeApplicationReview, getDocumentFileUrl, fetchDocumentBlob, submitApplication } from './api'
import { useAuth } from './auth/useAuth'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { buildReviewerDecisionPayload, hasRecordedReviewerDecision, pendingReviewerFindings, requiresReviewerDecision, REVIEW_ACTIONS, reviewerStateLabel } from './reviewWorkflow'

const iconPaths = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></>,
  applications: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6a2 2 0 0 1-2-2V5.5Z"/><path d="M4 6h13M8 10h8M8 14h6"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  documents: <><path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/></>,
  audit: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5M8 10.5l1.7 1.7 3.3-3.6"/></>,
  report: <><path d="M5 3h14v18H5zM8 8h8M8 12h8M8 16h5"/></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
  upload: <><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 15v5h16v-5"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  alert: <><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/></>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
  shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
  file: <><path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/></>,
  printer: <><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></>,
}
function Icon({ name, size = 20 }) { return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round">{iconPaths[name] || iconPaths.documents}</svg> }
function Status({ value }) { return <span className={`status status-${value || 'unknown'}`}><i />{STATUS_LABELS[value] || value?.replaceAll('_', ' ') || 'Not available'}</span> }
function PageHeader({ eyebrow, title, description, action }) { return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{action}</div> }
function ButtonLink({ to, children, variant = 'primary', icon }) { return <Link className={`button button-${variant}`} to={to}>{children}{icon && <Icon name={icon} size={17} />}</Link> }
function EmptyState({ title, text, action }) { return <div className="empty-state"><span className="empty-mark"><Icon name="documents" size={23} /></span><h3>{title}</h3><p>{text}</p>{action}</div> }
function Loading({ label = 'Loading workspace' }) { return <div className="loading-state"><span className="spinner"/><span>{label}</span></div> }
function ErrorNotice({ message, onRetry }) { return <div className="error-notice" role="alert"><Icon name="alert" size={20}/><div><strong>We couldn’t complete that request.</strong><p>{message}</p>{onRetry && <button type="button" className="text-button" onClick={onRetry}>Try again <Icon name="arrow" size={15}/></button>}</div></div> }

function Shell({ children }) {
  const location = useLocation()
  const { user, logout, isReviewer } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 800px)').matches)
  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 800px)')
    const updateViewport = () => { setIsMobile(mediaQuery.matches); setMenuOpen(false) }
    mediaQuery.addEventListener('change', updateViewport)
    return () => mediaQuery.removeEventListener('change', updateViewport)
  }, [])
  useEffect(() => { if (isMobile) setMenuOpen(false) }, [location.pathname, isMobile])
  useEffect(() => {
    if (!isMobile || !menuOpen) return undefined
    const closeOnEscape = (event) => { if (event.key === 'Escape') setMenuOpen(false) }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [isMobile, menuOpen])
  const primary = isReviewer
    ? [['/', 'overview', 'Scrutiny Queue']]
    : [['/', 'overview', 'My Applications'], ['/documents', 'upload', 'Documents'], ['/applications/new', 'plus', 'New application']]
  const pageTitle = location.pathname === '/' ? (isReviewer ? 'Scrutiny Queue' : 'My Applications') : location.pathname === '/documents' ? 'Documents' : location.pathname.includes('/report') ? 'Validation report' : location.pathname.includes('/audit') ? 'Audit workspace' : location.pathname.includes('/documents') ? 'Document centre' : 'New application'
  const sidebarExpanded = isMobile ? menuOpen : !menuOpen
  return <div className={`app-shell ${!isMobile && menuOpen ? 'sidebar-collapsed' : ''}`}>
    <button type="button" className={`sidebar-backdrop ${isMobile && menuOpen ? 'visible' : ''}`} aria-label="Close navigation" tabIndex={isMobile && menuOpen ? 0 : -1} onClick={() => setMenuOpen(false)} />
    <aside id="primary-navigation" className={`sidebar ${isMobile && menuOpen ? 'sidebar-open' : ''}`} aria-label="Primary navigation" aria-hidden={isMobile && !menuOpen} inert={isMobile && !menuOpen}>
      <Link to="/" className="brand" aria-label="Pramaan home"><span className="brand-mark"><svg aria-hidden="true" viewBox="0 0 32 32" fill="none"><path d="M12 5H7v22h5M20 5h5v22h-5" stroke="#e6e1d7" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter"/><path d="M12.5 12.5h7M12.5 16h5" stroke="#e6e1d7" strokeWidth="1.6" strokeLinecap="round"/><path d="m18 21 2 2 4-5" stroke="#d8a66c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg></span><span className="brand-copy"><b>pramaan</b><small>REVIEW WORKSPACE</small></span></Link>
      <nav className="side-nav">{primary.map(([to, icon, label]) => <NavLink key={to} to={to} end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} title={label} aria-label={label}><Icon name={icon} size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-foot">
        <div className="review-note"><Icon name="shield" size={16}/><p>Preliminary scrutiny supports reviewers; it does not verify authenticity or decide approval.</p></div>
        <div className="sidebar-user" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="sidebar-user-copy" style={{ maxWidth: '140px', overflow: 'hidden' }}>
            <b style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={user?.institution_name || user?.email}>{user?.institution_name || user?.email}</b>
            <small style={{ color: isReviewer ? '#d8a66c' : '#7fc4be', fontWeight: 600 }}>{isReviewer ? 'AICTE REVIEWER' : 'INSTITUTION'}</small>
          </span>
          <button type="button" onClick={logout} style={{ background: 'none', border: 'none', color: '#aab4ac', cursor: 'pointer', fontSize: '11px', textDecoration: 'underline' }}>Sign out</button>
        </div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar">
        <button type="button" className="icon-button mobile-menu" aria-controls="primary-navigation" aria-expanded={sidebarExpanded} aria-label={sidebarExpanded ? 'Collapse navigation sidebar' : 'Expand navigation sidebar'} onClick={() => setMenuOpen((open) => !open)}><Icon name="menu"/></button>
        <div className="topbar-page-title" aria-live="polite">{pageTitle}</div>
        <div className="topbar-right" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '12px', color: '#68736d' }}>{user?.email}</span>
          <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '3px', background: isReviewer ? '#d8a66c22' : '#315e5b22', color: isReviewer ? '#9a5d43' : '#315e5b', fontWeight: 600 }}>
            {isReviewer ? 'REVIEWER' : 'INSTITUTION'}
          </span>
        </div>
      </header>
      <div className="page-stage" key={location.pathname}>{children}</div>
      <footer className="footer"><span>SIH 2026 · PS 26261</span><span>Preliminary review only <i>·</i> Human judgment required</span></footer>
    </main>
  </div>
}

function Overview() {
  const { isReviewer, isInstitution } = useAuth()
  const [apps, setApps] = useState(null); const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [attentionOnly, setAttentionOnly] = useState(false)
  const load = () => { setError(''); listApplications().then(setApps).catch((e) => setError(e.message)) }
  useEffect(load, [])
  const counts = useMemo(() => (apps || []).reduce((sum, app) => { sum[app.overall_status] = (sum[app.overall_status] || 0) + 1; return sum }, {}), [apps])
  const filteredApps = useMemo(() => (apps || []).filter((app) => {
    const matchesQuery = `${app.institution_name || ''} ${app.id || ''} ${app.academic_year || ''}`.toLowerCase().includes(query.trim().toLowerCase())
    const needsAttention = ['missing_documents', 'discrepancies_found', 'unresolved_checks', 'processing_incomplete'].includes(app.overall_status)
    return matchesQuery && (!attentionOnly || needsAttention)
  }), [apps, query, attentionOnly])
  return <div className="mx-auto w-full max-w-6xl">
    <header className="mb-7 mt-2 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end sm:gap-6">
      <div>
        <div className="eyebrow text-[#6e7872]">{isReviewer ? 'AICTE SCRUTINY DESK · 2026 / 27' : 'INSTITUTION WORKSPACE · 2026 / 27'}</div>
        <h1 className="my-2 text-[29px] font-semibold leading-tight tracking-[-0.035em] text-[#1d3036] sm:text-4xl">{isReviewer ? 'Scrutiny queue' : 'My applications'}</h1>
        <p className="m-0 max-w-2xl text-[13px] leading-relaxed text-[#68736d] sm:text-sm">
          {isReviewer
            ? 'Review submitted institution applications, inspect supporting documents, and audit rule findings.'
            : 'Manage your AICTE applications, upload supporting documents, run preliminary validation, and track review status.'}
        </p>
      </div>
      {isInstitution && <ButtonLink to="/applications/new" icon="plus">New application</ButtonLink>}
    </header>
    <div><div className="mb-3 text-xs text-[#777f78]">{USE_MOCKS ? 'Synthetic demonstration records' : 'Applications from the live API'}</div>
      {error && <ErrorNotice message={error} onRetry={load}/>}
      {!apps && !error && <div className="queue-loading"><Loading label="Gathering applications"/></div>}
      {apps && <><div className="mb-6 grid grid-cols-3 border-y border-[#263b42]/15" aria-label="Application queue summary"><Metric label="In the queue" value={apps.length}/><Metric label="Needs attention" value={apps.filter((a) => ['missing_documents','discrepancies_found','unresolved_checks','processing_incomplete'].includes(a.overall_status)).length} accent/><Metric label="Checks passed" value={counts.checks_passed || 0}/></div>
        <section aria-labelledby="queue-heading"><div className="queue-section-head"><div><h2 id="queue-heading" className="m-0 text-lg font-semibold tracking-tight text-[#334b49]">Applications</h2><p className="mt-1 text-xs leading-relaxed text-[#68736d] sm:text-[13px]">Select a record to review its documents and validation findings.</p></div><label className="queue-search"><span className="sr-only">Search applications</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search institution or reference" /></label></div>
          {apps.length === 0 ? <EmptyState title={isReviewer ? 'No applications submitted yet' : 'No applications yet'} text={isReviewer ? 'Submitted applications from institutions will appear here.' : 'Create an application to begin a preliminary document review.'} action={isInstitution ? <ButtonLink to="/applications/new" icon="arrow">Create application</ButtonLink> : null}/> : <><div className="queue-filters"><button type="button" className={!attentionOnly ? 'is-active' : ''} onClick={() => setAttentionOnly(false)}>All <span>{apps.length}</span></button><button type="button" className={attentionOnly ? 'is-active' : ''} onClick={() => setAttentionOnly(true)}>Needs attention <span>{apps.filter((a) => ['missing_documents','discrepancies_found','unresolved_checks','processing_incomplete'].includes(a.overall_status)).length}</span></button></div><div className="overflow-x-auto border-t border-[#263b42]/20"><div className="hidden min-w-190 grid-cols-[minmax(260px,2fr)_120px_100px_minmax(170px,1.2fr)_80px] items-center gap-4 border-b border-[#263b42]/15 px-3 py-3 text-[10px] font-semibold tracking-[.06em] text-[#777f78] sm:grid"><span>INSTITUTION</span><span>ACADEMIC YEAR</span><span>DOCUMENTS</span><span>REVIEW STATUS</span><span/></div>{filteredApps.map((app) => <div className="application-queue-row grid min-h-17 min-w-90 grid-cols-[minmax(0,1fr)_auto_28px] items-center gap-2 border-b border-[#263b42]/15 px-1 py-2.5 text-sm text-[#394d4b] sm:min-w-190 sm:grid-cols-[minmax(260px,2fr)_120px_100px_minmax(170px,1.2fr)_80px] sm:gap-4 sm:px-3" key={app.id}><div className="min-w-0"><b className="block truncate text-xs font-semibold leading-snug text-[#293f3e] sm:text-sm">{app.institution_name}</b><small className="mt-1 block text-[10px] text-[#737d76] sm:text-xs">{app.id}<span className="sm:hidden"> · {app.academic_year} · {app.documents?.length ?? '—'} docs</span></small><span className="mt-1 block sm:hidden"><Status value={app.overall_status}/></span></div><span className="hidden text-[13px] text-[#465b57] sm:block">{app.academic_year}</span><span className="hidden text-[13px] text-[#465b57] sm:block">{app.documents?.length ?? '—'}</span><span className="hidden sm:flex sm:items-center sm:gap-2"><Status value={app.overall_status}/><Status value={app.status || 'draft'}/></span>{isReviewer ? (<Link className="queue-row-action" aria-label={`Review ${app.institution_name}`} to={`/applications/${app.id}/report`}>Review <Icon name="arrow" size={16}/></Link>) : (<Link className="queue-row-action" aria-label={`Open documents for ${app.institution_name}`} to={`/applications/${app.id}/documents`}>Open <Icon name="arrow" size={16}/></Link>)}</div>)}{filteredApps.length === 0 && <EmptyState title="No matching applications" text="Adjust the search or choose a different status filter."/>}</div></>}
        </section></>}
    </div>
  </div>
}
function Metric({ label, value, accent }) { return <div className={`flex min-h-15.5 flex-col justify-center gap-1 py-2 pr-1 sm:min-h-17.5 sm:pr-4 ${accent ? 'text-[#9a5d43]' : 'text-[#344f4d]'} [&+div]:border-l [&+div]:border-[#263b42]/15 [&+div]:pl-2 sm:[&+div]:pl-5`}><span className="text-[10px] font-semibold leading-snug text-[#626f69] sm:text-[11px]">{label}</span><strong className="text-xl font-semibold leading-tight sm:text-2xl">{value}</strong></div> }

function DocumentEntry() {
  const [apps, setApps] = useState(null); const [error, setError] = useState('')
  const load = () => { setError(''); setApps(null); listApplications().then(setApps).catch((e) => setError(e.message)) }
  useEffect(load, [])
  return <div className="document-entry-page">
    <PageHeader eyebrow="DOCUMENTS · SELECT AN APPLICATION" title={<>Every file has<br/><em>a place.</em></>} description="Choose an application to open its dedicated document centre, or create a new review record." action={<ButtonLink to="/applications/new" icon="arrow">Create an application</ButtonLink>}/>
    {USE_MOCKS && <div className="demo-callout"><span className="mode-dot"/><span><b>Synthetic demonstration records.</b> Select a record to add or inspect documents.</span></div>}
    {error && <ErrorNotice message={error} onRetry={load}/>}
    {!apps && !error && <Loading label="Finding applications"/>}
    {apps && (apps.length ? <section className="document-entry-list"><div className="entry-list-heading"><span>APPLICATION</span><span>REVIEW STATUS</span><span>FILES</span><span/></div>{apps.map((app, index) => <Link className="document-entry-row" to={`/applications/${app.id}/documents`} key={app.id} style={{ '--row': index }}><span className="entry-institution"><span className="institution-monogram">{app.institution_name?.split(' ').slice(0,2).map((v) => v[0]).join('')}</span><span><b>{app.institution_name}</b><small>{app.academic_year} · {APPLICATION_CATEGORIES.find((c) => c.code === app.application_category)?.label || app.application_category}</small></span></span><Status value={app.overall_status}/><span className="entry-file-count">{app.documents?.length ?? '—'} <small>documents</small></span><span className="entry-open">Open Document Centre <Icon name="arrow" size={17}/></span></Link>)}</section> : <EmptyState title="No applications yet" text="Create an application first; its document centre will be ready immediately." action={<ButtonLink to="/applications/new" icon="arrow">Create application</ButtonLink>}/>)}
  </div>
}

function CreateApplication() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const prefill = location.state?.prefill || {}
  const [form, setForm] = useState({
    institution_name: prefill.institution_name || user?.institution_name || '',
    application_category: prefill.application_category || APPLICATION_CATEGORIES[0]?.code || '',
    academic_year: prefill.academic_year || '2026-27',
  })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    const next = {}
    if (!form.institution_name.trim()) next.institution_name = 'Enter the institution name.'
    if (!form.application_category) next.application_category = 'Choose the configured category.'
    if (!/^\d{4}-\d{2}$/.test(form.academic_year.trim())) next.academic_year = 'Use the format 2026-27.'
    setErrors(next)
    if (Object.keys(next).length) return
    setBusy(true)
    setError('')
    try {
      const app = await createApplication({
        ...form,
        institution_name: form.institution_name.trim(),
        academic_year: form.academic_year.trim(),
      })
      navigate(`/applications/${app.id}/documents`, { state: { created: true } })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="form-page">
      <PageHeader
        eyebrow="APPLICATION INTAKE · 01"
        title={<>Start with the<br/><em>institution.</em></>}
        description="Create a review record before adding its supporting documents."
      />
      {prefill.institution_name && (
        <div style={{
          background: 'rgba(216,166,108,0.12)',
          border: '1px solid rgba(216,166,108,0.3)',
          borderRadius: '4px',
          padding: '12px 16px',
          marginBottom: '20px',
          fontSize: '13px',
          color: '#344f4d',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Icon name="check" size={16} />
          <span>Creating a revised application based on previous report for <b>{prefill.institution_name}</b>. You can update category/year and upload new or corrected documents.</span>
        </div>
      )}
      <div className="form-layout">
        <form className="editorial-form" onSubmit={submit} noValidate>
          <div className="form-section-label">
            <span>01</span>
            <div><b>Application identity</b><small>Use the institution name as submitted.</small></div>
          </div>
          <label className="field-label" htmlFor="institution">Institution name <span>REQUIRED</span></label>
          <input
            id="institution"
            autoComplete="organization"
            placeholder="e.g. Synthetic Northfield Institute of Technology"
            value={form.institution_name}
            onChange={(e) => setForm({ ...form, institution_name: e.target.value })}
            aria-invalid={!!errors.institution_name}
            aria-describedby={errors.institution_name ? 'institution-error' : undefined}
          />
          {errors.institution_name && <small id="institution-error" className="field-error">{errors.institution_name}</small>}

          <div className="form-grid">
            <div>
              <label className="field-label" htmlFor="category">Application category <span>CONFIGURED CODE</span></label>
              <select
                id="category"
                value={form.application_category}
                onChange={(e) => setForm({ ...form, application_category: e.target.value })}
                aria-invalid={!!errors.application_category}
              >
                {APPLICATION_CATEGORIES.map((category) => (
                  <option value={category.code} key={category.code}>{category.label}</option>
                ))}
              </select>
              {errors.application_category && <small className="field-error">{errors.application_category}</small>}
              <small className="field-helper">The contract lists EoA as a candidate. Team confirmation is pending.</small>
            </div>
            <div>
              <label className="field-label" htmlFor="year">Academic year <span>FORMAT: YYYY-YY</span></label>
              <input
                id="year"
                placeholder="2026-27"
                value={form.academic_year}
                onChange={(e) => setForm({ ...form, academic_year: e.target.value })}
                aria-invalid={!!errors.academic_year}
              />
              {errors.academic_year && <small className="field-error">{errors.academic_year}</small>}
            </div>
          </div>

          <div className="form-submit">
            <button type="submit" className="button button-primary" disabled={busy}>
              {busy ? <><span className="spinner spinner-light"/>Creating record…</> : <>Create application <Icon name="arrow" size={17}/></>}
            </button>
            <span>Fields marked required must be completed.</span>
          </div>
          {error && <ErrorNotice message={error}/>}
        </form>
        <aside className="form-aside">
          <div className="aside-number">INTAKE NOTE <span>01 / 03</span></div>
          <h3>Keep the record<br/>grounded in the file.</h3>
          <p>This creates an application record. Documents are added in the next step. Validation status comes from actual processing and configured checks.</p>
          <div className="aside-line"/>
          <div className="aside-meta"><span>CONTRACT REQUEST</span><code>institution_name<br/>application_category<br/>academic_year</code></div>
          <div className="aside-meta"><span>REVIEW PRINCIPLE</span><b>Preliminary scrutiny<br/>with a human in control.</b></div>
        </aside>
      </div>
    </div>
  )
}

function ApplicationDocumentCentre() {
  const { id } = useParams()
  const { isReviewer, isInstitution } = useAuth()
  const fileInputRef = useRef(null)
  const uploadSectionRef = useRef(null)
  const documentTypeRef = useRef(null)
  const [app, setApp] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [file, setFile] = useState(null)
  const [type, setType] = useState('')
  const [busy, setBusy] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')
  const [submissionNotice, setSubmissionNotice] = useState(null)
  const [dragging, setDragging] = useState(false)

  const [drawerDoc, setDrawerDoc] = useState(null)

  const load = () => {
    setLoading(true)
    setError('')
    getApplication(id)
      .then((value) => { if (!value) throw new Error('Application could not be found.'); setApp(value) })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [id])

  const acceptFile = (selected) => {
    if (!selected) return
    const allowed = ['application/pdf', 'image/jpeg', 'image/png']
    if (!allowed.includes(selected.type) && !/\.(pdf|jpe?g|png)$/i.test(selected.name)) {
      setMessage('Choose a PDF, JPG, or PNG file.')
      return
    }
    setMessage('')
    setFile(selected)
  }
  const focusUpload = (documentType) => {
    setType(documentType)
    uploadSectionRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
    requestAnimationFrame(() => documentTypeRef.current?.focus())
  }
  const inspectDoc = (doc) => {
    setDrawerDoc({
      documentId: doc.id,
      documentName: doc.original_filename || labelForDocument(doc.document_type),
      pageNumber: 1,
    })
  }
  const submit = async (event) => {
    event.preventDefault()
    if (!file || !type) return
    setBusy(true)
    setMessage('')
    try {
      const uploaded = await uploadDocument(id, file, type)
      setApp((current) => ({ ...current, documents: [...(current.documents || []), uploaded] }))
      setFile(null)
      setType('')
      if (fileInputRef.current) fileInputRef.current.value = ''
      setMessage('Upload received. Processing status will update when the service reports it.')
    } catch (requestError) {
      setMessage(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  const handleSubmitToAicte = async () => {
    if (submitting) return
    if (!window.confirm('Submit this application to AICTE? The application will be locked while it waits for reviewer scrutiny.')) {
      return
    }
    setSubmitting(true)
    setSubmissionNotice(null)
    try {
      const updated = await submitApplication(id)
      setApp((current) => ({ ...current, ...(updated || {}), status: updated?.status || 'submitted' }))
      setSubmissionNotice({ tone: 'success', text: 'Application submitted. It is now waiting for an AICTE reviewer. The scrutiny report will appear here after the reviewer finalizes the review.' })
    } catch (err) {
      setSubmissionNotice({ tone: 'error', text: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <Loading label="Opening application record" />
  if (error) return <ErrorNotice message={error} onRetry={load} />
  const documents = Array.isArray(app?.documents) ? app.documents : []
  const types = getChecklist()
  const present = new Set(documents.map((doc) => doc.document_type))
  const presentCount = types.filter((item) => present.has(item.code)).length
  const processingCount = documents.filter((doc) => ['uploaded', 'processing'].includes(doc.processing_status)).length
  const failedCount = documents.filter((doc) => doc.processing_status === 'processing_failed').length
  const processedCount = documents.filter((doc) => doc.processing_status === 'processed').length
  const requiredTypes = types.filter((item) => item.applicability === 'required')
  const missingRequiredTypes = requiredTypes.filter((item) => !present.has(item.code))
  const isLocked = ['submitted', 'review_completed'].includes(app?.status)
  const reviewCompleted = app?.status === 'review_completed'
  const pendingReview = app?.status === 'submitted'

  return <div className="document-page document-workflow-page">
    <PageHeader eyebrow={isReviewer ? "SCRUTINY DESK · APPLICATION WORKFLOW" : "DOCUMENT CENTRE · APPLICATION WORKFLOW"} title={<>Document<br /><em>workflow.</em></>} description={isReviewer ? "Inspect uploaded files, review extracted document evidence, and conduct regulatory scrutiny." : "Review the configured requirements, add files, and submit your application for AICTE scrutiny."} />

    {isLocked && (
      <div className={`application-state-banner ${reviewCompleted ? 'is-complete' : 'is-pending'}`} role="status">
        <Icon name={reviewCompleted ? 'check' : 'clock'} size={22} />
        <div>
          <strong>{reviewCompleted ? 'Scrutiny review completed' : 'Submitted · awaiting reviewer'}</strong>
          <p>{reviewCompleted
            ? 'A reviewer finalized this scrutiny. The completed review report is now available.'
            : isReviewer
              ? 'The institution submitted this application. Review its documents and findings, then finalize the scrutiny.'
              : 'Your application is locked while an AICTE reviewer completes scrutiny. The final report will be available here after the reviewer finalizes the review.'}</p>
        </div>
      </div>
    )}

    <section className="application-identity" aria-labelledby="application-identity-title">
      <div className="identity-heading"><div><div className="eyebrow">APPLICATION IDENTIFICATION</div><h2 id="application-identity-title">{app.institution_name || 'Institution name not provided'}</h2><div className="identity-meta"><span>{APPLICATION_CATEGORIES.find((category) => category.code === app.application_category)?.label || app.application_category || 'Category not provided'}</span><i>·</i><span>Academic year {app.academic_year || 'not provided'}</span><i>·</i><span>Reference {app.id}</span></div></div><div className="identity-statuses"><Status value={app.overall_status} /><Status value={app.status || 'draft'} /></div></div>
      <div className="identity-summary"><span><b>{presentCount} / {types.length}</b><small>listed document types with a file</small></span><span><b>{processedCount}</b><small>processed</small></span><span><b>{processingCount}</b><small>awaiting processing</small></span><span><b>{failedCount}</b><small>processing failed</small></span></div>
    </section>
    {USE_MOCKS && <div className="demo-callout"><span className="mode-dot" /><span><b>Synthetic demonstration data.</b> The three configured document types are an MVP subset, not the complete EoA checklist.</span></div>}
    {isReviewer ? (
      <ol className="workflow-steps" aria-label="Reviewer scrutiny workflow steps">
        <li><span>01</span><b>Check requirements</b></li>
        <li><span>02</span><b>Submitted documents</b></li>
        <li><span>03</span><b>Extracted evidence</b></li>
        <li><span>04</span><b>Scrutiny review</b></li>
      </ol>
    ) : (
      <ol className="workflow-steps" aria-label="Institution document workflow steps">
        <li><span>01</span><b>Check requirements</b></li>
        <li><span>02</span><b>Upload documents</b></li>
        <li><span>03</span><b>Review file status</b></li>
        <li><span>04</span><b>{reviewCompleted ? 'Review complete' : pendingReview ? 'Awaiting review' : 'Submit to AICTE'}</b></li>
      </ol>
    )}

    <section className="workflow-section checklist-section" aria-labelledby="checklist-heading">
      <div className="workflow-section-head"><div><span className="workflow-step-number">01</span><div><div className="eyebrow">REQUIREMENTS · CONFIGURABLE</div><h2 id="checklist-heading">Required-document checklist</h2></div></div><span className="section-side-note">{missingRequiredTypes.length ? `${missingRequiredTypes.length} required item${missingRequiredTypes.length === 1 ? '' : 's'} missing` : 'Required files are present'}</span></div>
      <div className="workflow-checklist" role="list">{types.map((item, index) => {
        const doc = documents.find((entry) => entry.document_type === item.code)
        const state = doc?.processing_status || (item.applicability === 'required' ? 'missing' : 'unresolved')
        const stateLabel = { missing: 'Required · not received', unresolved: 'Conditional · applicability to confirm', uploaded: 'Uploaded · awaiting processing', processing: 'Processing', processed: 'Processed', processing_failed: 'Processing failed' }[state] || state
        const applicabilityLabel = item.applicability === 'required' ? 'Required' : 'Required if applicable'
        return <div className={`workflow-check-row checklist-${state}`} role="listitem" key={item.code}><span className="check-index">{String(index + 1).padStart(2, '0')}</span><span className="workflow-check-name"><b>{item.label}</b><small>{applicabilityLabel} · {item.reference || 'Configurable document type'}</small></span><Status value={state} /><span className={`workflow-state-copy workflow-state-${state}`}>{stateLabel}</span>{doc?.processing_status === 'processing_failed' ? (isLocked || isReviewer ? <button type="button" className="workflow-row-action" onClick={() => inspectDoc(doc)}>Review file <Icon name="arrow" size={14} /></button> : <button type="button" className="workflow-row-action" onClick={() => focusUpload(item.code)}>Replace document <Icon name="arrow" size={14} /></button>) : doc ? <button type="button" className="workflow-row-action" onClick={() => inspectDoc(doc)}>Review file <Icon name="arrow" size={14} /></button> : (isLocked || isReviewer) ? <span className="workflow-row-action" style={{ opacity: 0.6 }}>Not submitted</span> : <button type="button" className="workflow-row-action" onClick={() => focusUpload(item.code)}>Upload this type <Icon name="arrow" size={14} /></button>}</div>
      })}</div>
      <p className="checklist-disclaimer">Three types are required for submission. TER receipts and structural-stability certificates remain conditional and do not block submission unless applicable.</p>
    </section>

    {!isReviewer && (
      <section className="workflow-section upload-section" id="upload-section" ref={uploadSectionRef} aria-labelledby="upload-heading">
        <div className="workflow-section-head"><div><span className="workflow-step-number">02</span><div><div className="eyebrow">ADD TO THIS APPLICATION</div><h2 id="upload-heading">Upload documents</h2></div></div><span className="section-side-note">PDF · JPG · PNG</span></div>
        {isLocked ? (
          <div style={{ padding: '32px 20px', background: 'rgba(38,59,66,0.03)', borderRadius: '6px', border: '1px dashed rgba(38,59,66,0.2)', textAlign: 'center' }}>
            <p style={{ margin: 0, color: '#68736d', fontSize: '14px' }}>
              Document uploads are locked because this application has been submitted to AICTE for review.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="workflow-upload-form"><div className="upload-form-top"><div><label htmlFor="doc-type" className="field-label">Document type <span>SELECT THE CHECKLIST ITEM</span></label><select ref={documentTypeRef} id="doc-type" value={type} onChange={(event) => setType(event.target.value)} required><option value="" disabled>Select a configured type</option>{types.map((item) => <option value={item.code} key={item.code}>{item.label} · {item.code}</option>)}</select>{type && <p className="selected-type-note">This file will be associated with <b>{types.find((item) => item.code === type)?.label || type}</b>.</p>}</div><div className="upload-contract-note"><Icon name="file" size={16} /><span>Accepted formats follow the API contract. File size and content are checked by the server.</span></div></div>
            <label className={`dropzone ${dragging ? 'dropzone-over' : ''}`} htmlFor="file-input" onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files?.[0]) }}><input ref={fileInputRef} id="file-input" type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" onChange={(event) => acceptFile(event.target.files?.[0])} /><span className="upload-symbol"><Icon name="upload" size={23} /></span><b>{file ? file.name : 'Drag a document into this space'}</b><span>{file ? `${file.type || 'File'} · selected and ready` : 'PDF, JPG, or PNG — or choose a file below'}</span><small>PDF / JPG / PNG</small></label>
            <div className="upload-actions"><button type="button" className="browse-button" onClick={() => fileInputRef.current?.click()}><Icon name="file" size={16} />{file ? 'Choose a different file' : 'Choose file'}<span>{file ? 'Replace selection' : 'From this device'}</span></button><button className="button button-copper upload-submit" type="submit" disabled={busy || !file || !type}>{busy ? <><span className="spinner spinner-light" />Uploading…</> : <>Upload selected file <Icon name="arrow" size={17} /></>}</button></div>
            {file && <div className="selected-file-summary"><Icon name="file" size={17} /><span><b>{file.name}</b><small>{file.type || 'File type unavailable'} · {types.find((item) => item.code === type)?.label || 'Choose a document type'}</small></span><span className="selection-status">Ready to upload</span></div>}
            {message && <div className={`inline-message ${message.startsWith('Upload received') ? 'message-success' : 'message-error'}`} role={message.startsWith('Upload received') ? 'status' : 'alert'}>{message}</div>}
            <p className="upload-note">Dates and fields are extracted or reviewed later; they are not accepted as authoritative upload inputs.</p>
          </form>
        )}
      </section>
    )}

    <section className="workflow-section uploaded-section" aria-labelledby="uploaded-heading"><div className="workflow-section-head"><div><span className="workflow-step-number">{isReviewer ? '02' : '03'}</span><div><div className="eyebrow">APPLICATION FILE</div><h2 id="uploaded-heading">Uploaded documents</h2></div></div><span className="section-side-note">{documents.length} {documents.length === 1 ? 'file' : 'files'} · {processedCount} processed</span></div>{documents.length === 0 ? <EmptyState title="No documents received" text="Files appear here after the upload request returns successfully." /> : <div className="uploaded-file-table"><div className="uploaded-file-header"><span>FILE NAME</span><span>DOCUMENT TYPE</span><span>PROCESSING STATUS</span><span>FILE TYPE</span></div>{documents.map((doc) => <DocumentItem key={doc.id} doc={doc} onInspect={inspectDoc} />)}</div>}
      {isReviewer && documents.some((doc) => fieldsForDocument(doc).length) && (
        <div className="fields-panel">
          <div className="eyebrow">EXTRACTED FIELD INSPECTION</div>
          <h3>Fields returned by processing</h3>
          {documents.flatMap((doc) => fieldsForDocument(doc).map((field, index) => (
            <FieldRow key={`${doc.id}-${index}`} field={{ ...field, source_document: field.source_document || doc.original_filename }} />
          )))}
        </div>
      )}
    </section>

    {isInstitution ? (
      <section className={`audit-gate submission-gate ${pendingReview ? 'is-pending' : ''} ${reviewCompleted ? 'is-complete' : ''}`} aria-labelledby="submission-gate-heading">
        <div className="workflow-step-number">{reviewCompleted ? '✓' : '04'}</div>
        <div className="audit-gate-copy">
          <div className="eyebrow">{reviewCompleted ? 'REVIEW COMPLETE' : pendingReview ? 'SUBMITTED · PENDING REVIEW' : 'NEXT · FORMAL SUBMISSION'}</div>
          <h2 id="submission-gate-heading">{reviewCompleted ? 'Scrutiny review completed' : pendingReview ? 'Application submitted' : 'Submit application to AICTE'}</h2>
          <p>
            {reviewCompleted
              ? 'The reviewer finalized scrutiny. View the completed review report for findings and next steps.'
              : pendingReview
                ? 'The application is locked while it waits for reviewer scrutiny. The reviewer has not finalized a report yet.'
                : missingRequiredTypes.length > 0
                  ? `Upload the ${missingRequiredTypes.map((item) => item.label).join(', ')} before submitting.`
                  : 'Required document types are present. Submit to lock the application and place it in the reviewer queue.'}
          </p>
        </div>
        <div className="submission-actions">
          {reviewCompleted ? (
            <ButtonLink to={`/applications/${id}/report`} icon="arrow">
              View completed report
            </ButtonLink>
          ) : pendingReview ? (
            <span className="awaiting-review-label"><Icon name="clock" size={16} /> Awaiting reviewer</span>
          ) : (
            <button
              type="button"
              className="button button-primary"
              onClick={handleSubmitToAicte}
              disabled={submitting || missingRequiredTypes.length > 0}
              aria-describedby={missingRequiredTypes.length > 0 ? 'submission-requirements' : undefined}
            >
              {submitting ? <><span className="spinner spinner-light"/>Submitting…</> : <>Submit to AICTE <Icon name="arrow" size={17}/></>}
            </button>
          )}
        </div>
        {missingRequiredTypes.length > 0 && !isLocked && <p id="submission-requirements" className="submission-requirement-note">Submission is unavailable until all three required document types have a file.</p>}
        {submissionNotice && <div className={`submission-feedback is-${submissionNotice.tone}`} role={submissionNotice.tone === 'error' ? 'alert' : 'status'}>{submissionNotice.text}</div>}
      </section>
    ) : (
      <section className="audit-gate" aria-labelledby="reviewer-gate-heading">
        <div className="workflow-step-number">03</div>
        <div className="audit-gate-copy">
          <div className="eyebrow">SCRUTINY DESK · AUDIT WORKSPACE</div>
          <h2 id="reviewer-gate-heading">Proceed to Scrutiny Findings & Review</h2>
          <p>Examine automated rule checks, inspect document evidence snippets, and record auditor verification decisions.</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <ButtonLink to={`/applications/${id}/report`} icon="arrow">
            Open Scrutiny Findings
          </ButtonLink>
          <Link to={`/applications/${id}/audit`} className="quiet-link" style={{ marginLeft: '8px' }}>
            <Icon name="audit" size={17} /> Cross-Document Audit Workspace
          </Link>
        </div>
      </section>
    )}

    <DocumentViewerDrawer
      isOpen={!!drawerDoc}
      onClose={() => setDrawerDoc(null)}
      applicationId={id}
      docInfo={drawerDoc}
    />
  </div>
}
function DocumentItem({ doc, onInspect }) {
  return (
    <article className="received-item uploaded-file-row" id={`uploaded-${doc.id}`} style={{ cursor: onInspect ? 'pointer' : 'default' }} onClick={() => onInspect?.(doc)}>
      <span className="uploaded-file-name">
        <span className="file-mark"><Icon name="documents" size={20} /></span>
        <b>{doc.original_filename || labelForDocument(doc.document_type)}</b>
      </span>
      <span className="uploaded-type-name">{labelForDocument(doc.document_type)}</span>
      <Status value={doc.processing_status || 'uploaded'} />
      <span className="uploaded-mime" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
        <span>{doc.mime_type?.includes('pdf') ? 'PDF' : doc.mime_type?.split('/')[1]?.toUpperCase() || doc.mime_type || 'Not provided'}</span>
        {onInspect && (
          <span style={{ fontSize: '11px', color: '#315e5b', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '2px', textDecoration: 'underline' }}>
            View <Icon name="arrow" size={12} />
          </span>
        )}
      </span>
    </article>
  )
}
function fieldsForDocument(doc) {
  if (Array.isArray(doc.fields)) return doc.fields
  if (doc.fields && typeof doc.fields === 'object') return Object.entries(doc.fields).map(([name, data]) => ({ name: name.replaceAll('_', ' '), field: name, ...data, status: data.status === 'uncertain' ? 'unresolved' : data.status === 'missing' || data.value == null ? 'missing' : 'processed', evidence: data.raw_text || null }))
  return []
}
function FieldRow({ field }) { return <div className="field-row"><div className="field-value"><span>{field.name || field.field || 'Extracted field'}</span><b>{field.value || 'Unavailable'}</b><small>{field.source_document || 'Source document unavailable'}{field.page_number ? ` · page ${field.page_number}` : ''}{field.confidence != null ? ` · ${Math.round(field.confidence * 100)}% confidence` : ''}</small></div><Status value={field.status || 'unresolved'}/>{field.evidence && <blockquote>{field.evidence}</blockquote>}</div> }

function hasValidationRun(report) {
  if (!report) return false
  const hasFindings = Array.isArray(report.findings) && report.findings.length > 0
  const hasSummaryCounts = Object.values(report.summary || {}).some((count) => Number(count) > 0)
  return hasFindings || hasSummaryCounts || report.overall_status !== 'processing_incomplete'
}

function AuditWorkspace() {
  const { id } = useParams()
  const { isReviewer, isInstitution } = useAuth()
  const [app, setApp] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    getApplication(id)
      .then((value) => {
        if (!value) throw new Error('Application could not be found.')
        setApp(value)
        return getReport(id)
      })
      .then((value) => setReport(hasValidationRun(value) ? value : null))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [id])

  if (isInstitution || (isReviewer && app?.status === 'review_completed')) {
    return <Navigate to={`/applications/${id}/report`} replace />
  }

  const start = async () => {
    setBusy(true)
    setError('')
    setReport(null)
    try {
      const result = await runValidation(id)
      setReport(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Loading label="Preparing review workspace"/>
  if (error && !app) return <ErrorNotice message={error} onRetry={load}/>
  const docs = app?.documents || []
  return <div className="audit-page"><PageHeader eyebrow={isReviewer ? "SCRUTINY DESK · CROSS-DOCUMENT AUDIT" : "REVIEW WORKSPACE · 02"} title={<>Compare the file<br/><em>with the checks.</em></>} description={<><b>{app?.institution_name}</b><span className="description-dot">·</span>{app?.academic_year}<span className="description-dot">·</span>{app?.application_category?.toUpperCase()} (EoA)</>}/>
    {USE_MOCKS && <div className="demo-callout"><span className="mode-dot"/><span><b>Demonstration mode.</b> Synthetic records and checklist; results are not a real validation or an authenticity determination.</span></div>}
    <div className={`audit-stage ${busy ? 'is-running' : ''} ${report ? 'is-complete' : ''}`}>
      <div className="audit-instructions"><div><span className="audit-step">01 <i>—</i> DOCUMENTS</span><h2>Submitted material</h2><p>{docs.length} {docs.length === 1 ? 'document' : 'documents'} associated with this record</p></div><div className="audit-center-caption"><span className="center-ring"><Icon name={busy ? 'clock' : report ? 'check' : 'audit'} size={21}/></span><small>{busy ? 'COMPARING' : report ? 'RESPONSE RECEIVED' : 'AWAITING REVIEW'}</small></div><div><span className="audit-step">02 <i>—</i> CONFIGURATION</span><h2>Review checks</h2><p>{getChecklist().length} configured demonstration requirements</p></div></div>
      <div className="audit-panels"><div className="audit-panel doc-panel"><div className="panel-head"><span className="panel-num">A</span><span><b>Application file</b><small>Submitted documents</small></span><span className="panel-count">{docs.length.toString().padStart(2, '0')}</span></div><div className="panel-content">{docs.length ? docs.map((doc, index) => <div className="audit-document-group" key={doc.id}><div className={`audit-doc-line ${busy ? 'stagger' : ''}`} style={{ '--i': index }}><span className="audit-doc-icon"><Icon name="documents" size={17}/></span><span><b>{doc.original_filename || labelForDocument(doc.document_type)}</b><small>{labelForDocument(doc.document_type)} · {STATUS_LABELS[doc.processing_status] || doc.processing_status}</small></span><i className={`status-marker marker-${doc.processing_status}`}/></div>{fieldsForDocument(doc).slice(0, 3).map((field, fieldIndex) => <div className={`audit-field-line ${busy ? 'stagger' : ''}`} style={{ '--i': index + fieldIndex + 1 }} key={`${doc.id}-${field.field || field.name || fieldIndex}`}><span>{field.name || field.field || 'Extracted field'}</span><b>{field.value || 'Unavailable'}</b><small>{field.raw_text || field.evidence || 'No evidence snippet provided'}</small></div>)}</div>) : <div className="panel-empty">No documents have been added yet.<Link to={`/applications/${id}/documents`}>Go to document centre <Icon name="arrow" size={14}/></Link></div>}</div><div className="panel-foot">SOURCE MATERIAL <span>As supplied by applicant</span></div></div>
        <div className="connection-lanes" aria-hidden="true"><svg className="comparison-signature" viewBox="0 0 120 230" preserveAspectRatio="none"><path className="signature-underlay" d="M-10 48C19 46 15 88 35 91s17-58 36-54 12 79 31 83 12-42 31-39"/><path className="signature-main" d="M-10 48C19 46 15 88 35 91s17-58 36-54 12 79 31 83 12-42 31-39"/><path className="signature-flick" d="M70 37c-5 28-12 54-30 79m62 4 14 20"/></svg><span className="lane-line"/><span className="lane-line"/><span className="scan-pulse"/><span className="lane-caption">FIELD<br/>COMPARISON</span></div>
        <div className="audit-panel rules-panel"><div className="panel-head"><span className="panel-num">B</span><span><b>Configured checklist</b><small>Three-document MVP subset</small></span><span className="panel-count">{getChecklist().length.toString().padStart(2, '0')}</span></div><div className="panel-content">{getChecklist().map((item, index) => <div className={`audit-rule-line ${busy ? 'stagger' : ''}`} style={{ '--i': index }} key={item.code}><span className="rule-node">{String(index + 1).padStart(2,'0')}</span><span><b>{item.label}</b><small>{item.code}</small></span><span className="rule-state"><i className={busy ? 'rule-pulse' : ''}/>{report ? 'CONFIGURED' : 'READY'}</span></div>)}</div><div className="panel-foot">SOURCE <span>APH clauses in the checklist</span></div></div></div>
      {!report && (
        <div className="audit-action-row">
          <div className="audit-caveat">
            <Icon name="shield" size={17}/>
            <span>Automated scrutiny rules will evaluate submitted document fields against APH compliance requirements.</span>
          </div>
          <button type="button" className="button button-primary begin-audit" disabled={busy || docs.length === 0} onClick={start}>
            {busy ? <><span className="spinner spinner-light"/>Evaluating documents…</> : <>Run Scrutiny Checks <Icon name="arrow" size={17}/></>}
          </button>
        </div>
      )}
      {docs.length === 0 && !report && <p className="audit-prerequisite">No documents available to validate.</p>}
      {error && <ErrorNotice message={error} onRetry={start}/>}
      {report && (
        <div className="audit-result">
          <div className="result-seal"><Icon name={report.overall_status === 'checks_passed' ? 'check' : 'report'} size={22}/></div>
          <div className="result-copy">
            <span className="eyebrow">SCRUTINY FINDINGS RECORDED</span>
            <h3>Compliance checks complete.</h3>
            <p>Preliminary findings are ready. Human auditor review is required to verify discrepancies or accept findings.</p>
            <div className="result-finding-preview">
              {report.summary && Object.entries(report.summary).filter(([, count]) => Number(count) > 0).map(([status, count]) => (
                <span key={status}><b>{count}</b> {STATUS_LABELS[status] || status}</span>
              ))}
              {Array.isArray(report.findings) && report.findings.slice(0, 2).map((finding) => (
                <span className="result-finding-title" key={finding.id || finding.rule_id}>{finding.title || finding.reason}</span>
              ))}
            </div>
          </div>
          <Status value={report.overall_status}/>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <ButtonLink to={`/applications/${id}/report`} icon="arrow">Open Scrutiny Findings & Review Desk</ButtonLink>
            <button type="button" className="button button-secondary" disabled={busy} onClick={start}>
              {busy ? 'Re-running…' : 'Re-run Checks'}
            </button>
          </div>
        </div>
      )}
    </div>
  </div>
}

function AuditorReviewModal({ isOpen, onClose, finding, decision, onSave, error }) {
  const action = REVIEW_ACTIONS[decision]
  const [details, setDetails] = useState('')
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const modalRef = useRef(null)
  const previousFocusRef = useRef(null)
  const onCloseRef = useRef(onClose)
  const savingRef = useRef(saving)
  onCloseRef.current = onClose
  savingRef.current = saving

  useEffect(() => {
    if (!isOpen) return undefined
    previousFocusRef.current = document.activeElement
    const modal = modalRef.current
    const focusable = () => [...modal.querySelectorAll('button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]')]
    modal.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !savingRef.current) { event.preventDefault(); onCloseRef.current(); return }
      if (event.key !== 'Tab') return
      const items = focusable()
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === modal)) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    modal.addEventListener('keydown', onKeyDown)
    return () => {
      modal.removeEventListener('keydown', onKeyDown)
      previousFocusRef.current?.focus?.()
    }
  }, [isOpen])

  useEffect(() => {
    if (finding) {
      setDetails(finding.reviewer_decision === decision ? finding.reviewer_notes || '' : '')
      setFormError('')
    }
  }, [finding, decision])

  if (!isOpen || !finding || !action) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    let payload
    try {
      payload = buildReviewerDecisionPayload(decision, details)
    } catch (err) {
      setFormError(err.message)
      return
    }
    setSaving(true)
    try {
      const saved = await onSave(finding.id, payload)
      if (saved !== false) onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="auditor-modal-backdrop" onClick={() => !saving && onClose()}>
      <div ref={modalRef} className="auditor-modal" role="dialog" aria-modal="true" aria-labelledby="review-modal-title" aria-describedby="review-modal-description" tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <div className="auditor-modal-head">
          <div>
            <span className="eyebrow">HUMAN REVIEW · {reviewerStateLabel(finding)}</span>
            <h3 id="review-modal-title">{action.title}</h3>
          </div>
          <button type="button" className="icon-button" onClick={onClose} disabled={saving} aria-label="Close"><Icon name="close" size={18}/></button>
        </div>
        <form onSubmit={handleSubmit} className="auditor-modal-body">
          <p className="finding-target-title"><b>Target finding:</b> {finding.title}</p>
          <p id="review-modal-description" className="review-action-description">{action.description}</p>
          <div className="modal-field">
            <label htmlFor="review-action-details">{action.fieldLabel}</label>
            <textarea
              id="review-action-details"
              rows={3}
              value={details}
              onChange={(e) => { setDetails(e.target.value); setFormError('') }}
              placeholder={action.placeholder}
              required
            />
          </div>
          <p className="reviewer-identity-note">Recorded under the signed-in reviewer account.</p>
          {(formError || error) && <div className="submission-feedback is-error" role="alert">{formError || error}</div>}
          <div className="auditor-modal-actions">
            <button type="button" className="button button-secondary" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="button button-primary" disabled={saving}>
              {saving ? 'Saving…' : action.submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function DocumentViewerDrawer({ isOpen, onClose, applicationId, docInfo }) {
  const { documentId, documentName, pageNumber, bbox, evidenceText } = docInfo || {}
  const fileUrl = applicationId && documentId ? getDocumentFileUrl(applicationId, documentId) : ''
  const [blobUrl, setBlobUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    if (!isOpen || !applicationId || !documentId) {
      setBlobUrl(null)
      return undefined
    }

    let active = true
    let createdUrl = null
    setLoading(true)
    setLoadError('')
    setBlobUrl(null)

    fetchDocumentBlob(applicationId, documentId)
      .then((blob) => {
        if (!active) return
        createdUrl = URL.createObjectURL(blob)
        setBlobUrl(createdUrl)
      })
      .catch((err) => {
        if (!active) return
        setLoadError(err.message || 'Could not load document preview.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl)
      }
    }
  }, [isOpen, applicationId, documentId])

  if (!isOpen || !docInfo) return null

  return (
    <div className="viewer-drawer-backdrop" onClick={onClose}>
      <div className="viewer-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-header">
          <div>
            <span className="eyebrow">DOCUMENT EVIDENCE VIEWER</span>
            <h3>{documentName || 'Document Preview'}</h3>
            <div className="viewer-meta">
              <span>Page {pageNumber || 1}</span>
              {bbox && (
                <span className="bbox-pill">
                  BBox: [{bbox.map((v) => (typeof v === 'number' ? v.toFixed(1) : v)).join(', ')}]
                </span>
              )}
            </div>
          </div>
          <button type="button" className="icon-button close-drawer" onClick={onClose}>
            <Icon name="close" size={20} />
          </button>
        </div>

        {evidenceText && (
          <div className="viewer-evidence-snippet">
            <span className="snippet-label">TARGET EVIDENCE SNIPPET</span>
            <blockquote>{evidenceText}</blockquote>
          </div>
        )}

        <div className="viewer-frame-container" style={{ position: 'relative', minHeight: '400px' }}>
          {loading && <Loading label="Loading document preview…" />}
          {loadError && (
            <div style={{ padding: '32px 20px', textAlign: 'center' }}>
              <ErrorNotice message={loadError} />
              <p style={{ marginTop: '16px', fontSize: '13px', color: '#68736d' }}>
                You can also try opening the authenticated document in a new tab:
              </p>
              <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="button button-primary" style={{ display: 'inline-flex', marginTop: '8px' }}>
                Open in new tab <Icon name="arrow" size={14} />
              </a>
            </div>
          )}
          {blobUrl && (
            <iframe
              src={`${blobUrl}#page=${pageNumber || 1}`}
              title="Document Viewer"
              className="viewer-iframe"
            />
          )}
        </div>

        <div className="viewer-footer">
          <a href={fileUrl} target="_blank" rel="noopener noreferrer" className="quiet-link">
            Open in new tab <Icon name="arrow" size={14} />
          </a>
        </div>
      </div>
    </div>
  )
}

function ValidationReport() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, isReviewer, isInstitution } = useAuth()
  const [app, setApp] = useState(null)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalFinding, setModalFinding] = useState(null)
  const [modalInitialDecision, setModalInitialDecision] = useState('verified')
  const [drawerDoc, setDrawerDoc] = useState(null)
  const [finalizing, setFinalizing] = useState(false)
  const [finalizeError, setFinalizeError] = useState('')
  const [savingFindingId, setSavingFindingId] = useState(null)
  const [reviewFeedback, setReviewFeedback] = useState('')
  const [reviewError, setReviewError] = useState('')
  const [showAllFindings, setShowAllFindings] = useState(!isReviewer)

  const load = () => {
    setLoading(true)
    setError('')
    getApplication(id)
      .then(async (a) => {
        if (!a) throw new Error('Application could not be found.')
        setApp(a)
        if (isInstitution && a.status !== 'review_completed') {
          setReport(null)
          return
        }
        const r = await getReport(id)
        setReport(hasValidationRun(r) ? r : null)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [id, isInstitution])

  const handleOpenReview = (finding, decisionType) => {
    setReviewError('')
    setReviewFeedback('')
    if (decisionType === 'verified') {
      void handleSaveReview(finding.id, { reviewer_decision: 'verified' })
      return
    }
    setModalInitialDecision(decisionType)
    setModalFinding(finding)
  }

  const handleSaveReview = async (findingId, reviewPayload) => {
    if (savingFindingId) return false
    setSavingFindingId(findingId)
    setReviewError('')
    setReviewFeedback('')
    try {
      const saved = await reviewFinding(id, findingId, {
        ...reviewPayload,
        reviewed_by: user?.email,
      })
      setReport((current) => current && ({
        ...current,
        findings: current.findings.map((finding) => finding.id === findingId ? { ...finding, ...saved } : finding),
      }))
      const message = reviewPayload.reviewer_decision === 'verified'
        ? 'Finding marked verified.'
        : REVIEW_ACTIONS[reviewPayload.reviewer_decision]?.successLabel || 'Reviewer decision recorded.'
      setReviewFeedback(message)
      getApplication(id).then((latestApp) => {
        if (latestApp) {
          setApp(latestApp)
          setReport((current) => current && ({ ...current, overall_status: latestApp.overall_status || current.overall_status }))
        }
      }).catch(() => {})
      return true
    } catch (err) {
      setReviewError(`Could not save reviewer decision: ${err.message}`)
      return false
    } finally {
      setSavingFindingId(null)
    }
  }

  const handleFinalizeReview = async () => {
    if (finalizing) return
    if (!window.confirm('Finalize this scrutiny review? The completed report will become available to the institution, and review decisions will become read-only.')) return
    setFinalizing(true)
    setFinalizeError('')
    try {
      const updated = await finalizeApplicationReview(id)
      setApp((current) => ({ ...current, ...(updated || {}), status: updated?.status || 'review_completed' }))
    } catch (err) {
      setFinalizeError(err.message)
    } finally {
      setFinalizing(false)
    }
  }

  const handleInspectDoc = (docInfo) => {
    setDrawerDoc(docInfo)
  }

  const handlePrint = () => {
    window.print()
  }

  if (loading) return <Loading label="Retrieving report" />
  if (error) return <ErrorNotice message={error} onRetry={load} />
  if (isInstitution && app?.status !== 'review_completed') {
    const awaitingReview = app?.status === 'submitted'
    return <div className="report-empty awaiting-review-page">
      <PageHeader eyebrow={awaitingReview ? 'APPLICATION · PENDING REVIEW' : 'APPLICATION · DRAFT'} title={awaitingReview ? <>Awaiting reviewer<br/>scrutiny.</> : <>The report follows<br/>review.</>} description={app?.institution_name} />
      <div className="application-state-banner is-pending" role="status"><Icon name="clock" size={22}/><div><strong>{awaitingReview ? 'Your application is in the reviewer queue' : 'This application has not been submitted'}</strong><p>{awaitingReview ? 'The reviewer has not finalized scrutiny yet. The completed report will appear here when the review is finished.' : 'Submit the required documents first. A final scrutiny report is available only after reviewer review is complete.'}</p></div></div>
      <ButtonLink to={`/applications/${id}/documents`} variant="secondary" icon="documents">Open document centre</ButtonLink>
    </div>
  }
  if (!report) return (
    <div className="report-empty">
      <PageHeader eyebrow={isReviewer ? "SCRUTINY DESK · AUDITOR REVIEW" : "VALIDATION REPORT · 03"} title={<>No report<br/><em>on record.</em></>} description={app?.institution_name} />
      <EmptyState
        title="Scrutiny checks have not been run"
        text="Run automated scrutiny checks to evaluate this submitted application against APH requirements."
        action={
          isReviewer ? (
            <button
              type="button"
              className="button button-primary"
              onClick={async () => {
                setLoading(true)
                try {
                  const res = await runValidation(id)
                  setReport(res)
                } catch (e) {
                  setError(e.message)
                } finally {
                  setLoading(false)
                }
              }}
            >
              Run Scrutiny Checks <Icon name="arrow" size={17} />
            </button>
          ) : (
            <ButtonLink to={`/applications/${id}/documents`} icon="arrow">Open Document Centre</ButtonLink>
          )
        }
      />
    </div>
  )

  const summary = report.summary || {}
  const findings = Array.isArray(report.findings) ? report.findings : []
  const pendingFindings = pendingReviewerFindings(findings)
  const pendingReviewerCount = pendingFindings.length
  const displayedFindings = (showAllFindings ? findings : pendingFindings)
    .slice()
    .sort((left, right) => Number(requiresReviewerDecision(right)) - Number(requiresReviewerDecision(left)))
  const hasRecordedDecisions = findings.some((finding) => finding.reviewer_decision || finding.reviewed_at)
  const summaryStatuses = CHECK_STATUSES.filter((status) => Number.isFinite(summary[status]))
  const reportedMissingTypes = Array.isArray(report.missing_document_types) ? report.missing_document_types : []
  const missingTypesCoveredByFindings = reportedMissingTypes.every((code) => {
    const label = labelForDocument(code).toLowerCase()
    return findings.some((finding) => finding.status === 'missing' && [finding.title, finding.reason].some((value) => value?.toLowerCase().includes(label)))
  })

  return (
    <div className="report-page">
      <PageHeader
        eyebrow={isReviewer ? "SCRUTINY DESK · AUDITOR VERIFICATION" : "VALIDATION REPORT · SCRUTINY FINDINGS"}
        title={isReviewer ? <>Scrutiny<br/><em>review desk.</em></> : <>Review the<br/><em>evidence trail.</em></>}
        description={<><b>{app?.institution_name}</b><span className="description-dot">·</span>{app?.academic_year}<span className="description-dot">·</span>{app?.application_category?.toUpperCase()} (EoA)</>}
        action={
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            {isInstitution && (
              <button
                type="button"
                className="button button-secondary"
                onClick={() =>
                  navigate('/applications/new', {
                    state: {
                      prefill: {
                        institution_name: app?.institution_name,
                        application_category: app?.application_category,
                        academic_year: app?.academic_year,
                      },
                    },
                  })
                }
              >
                <Icon name="plus" size={16} /> Create New Application from Report
              </button>
            )}
            {isReviewer && app?.status === 'submitted' && !hasRecordedDecisions && (
              <button
                type="button"
                className="button button-secondary"
                onClick={async () => {
                  setLoading(true)
                  try {
                    const res = await runValidation(id)
                    setReport(res)
                  } catch (e) {
                    setError(e.message)
                  } finally {
                    setLoading(false)
                  }
                }}
              >
                Re-run Scrutiny Checks
              </button>
            )}
            {isReviewer && app?.status === 'submitted' && hasRecordedDecisions && (
              <span className="review-lock-note">Checks are locked after a reviewer decision to preserve the audit record.</span>
            )}
            <button type="button" className="button button-primary" onClick={handlePrint}>
              <Icon name="printer" size={16} /> Export Scrutiny Dossier (PDF)
            </button>
            <ButtonLink to={`/applications/${id}/documents`} variant="secondary" icon="documents">
              Inspect documents
            </ButtonLink>
          </div>
        }
      />
      {USE_MOCKS && <div className="demo-callout"><span className="mode-dot"/><span><b>Synthetic demonstration report.</b> This report is not based on an actual application and does not prove authenticity or determine AICTE approval.</span></div>}
      
      <section className="report-overview">
        <div className="report-status-block">
          <span className="eyebrow">OVERALL VALIDATION STATUS</span>
          <Status value={report.overall_status} />
          <p>Preliminary checks only <i>·</i> Reviewer assessment required</p>
        </div>
        <div className="report-meta">
          <span>APPLICATION REFERENCE</span><b>{app?.id}</b>
          <span>REPORT GENERATED</span><b>{report.generated_at ? new Date(report.generated_at).toLocaleString('en-IN') : 'Not provided by service'}</b>
        </div>
      </section>

      {summaryStatuses.length > 0 && (
        <section className="report-summary">
          <div className="summary-heading">
            <div className="eyebrow">CHECK SUMMARY</div>
            <h2>What the checks returned</h2>
          </div>
          <div className="summary-counts">
            {summaryStatuses.map((status) => (
              <div className={`summary-count count-${status}`} key={status}>
                <span>{STATUS_LABELS[status]}</span>
                <b>{summary[status]}</b>
              </div>
            ))}
          </div>
        </section>
      )}

      {reportedMissingTypes.length > 0 && !missingTypesCoveredByFindings && (
        <section className="reported-missing" aria-label="Missing document types">
          <h2>Missing document types reported</h2>
          <p>These checklist items were returned separately from the finding details.</p>
          <ul>{reportedMissingTypes.map((code) => <li key={code}>{labelForDocument(code)}</li>)}</ul>
        </section>
      )}

      {isReviewer && app?.status === 'submitted' && (
        <section className="review-finalization" aria-labelledby="finalize-review-heading">
          <div>
            <div className="eyebrow">REVIEWER ACTION</div>
            <h2 id="finalize-review-heading">Finalize scrutiny</h2>
            <p>{pendingReviewerCount
              ? `${pendingReviewerCount} finding${pendingReviewerCount === 1 ? '' : 's'} in an open review state still need action.`
              : 'All findings that require reviewer action have a recorded decision. Finalizing closes scrutiny; resubmission and escalation outcomes remain distinct from compliance.'}</p>
            {pendingReviewerCount > 0 && (
              <ul className="review-pending-list">
                {pendingFindings.slice(0, 3).map((finding) => <li key={finding.id}>{finding.title || finding.rule_id}{finding.document_name ? ` · ${finding.document_name}` : ''}</li>)}
                {pendingReviewerCount > 3 && <li>And {pendingReviewerCount - 3} more</li>}
              </ul>
            )}
          </div>
          <button type="button" className="button button-primary" disabled={finalizing || pendingReviewerCount > 0 || findings.length === 0} onClick={handleFinalizeReview}>
            {finalizing ? 'Finalizing review…' : 'Finalize scrutiny'} <Icon name="check" size={17}/>
          </button>
          {finalizeError && <div className="submission-feedback is-error" role="alert">{finalizeError}</div>}
        </section>
      )}

      <section className="findings-section" id="finding-register">
        <div className="section-title-row">
          <div>
            <div className="eyebrow">FINDING REGISTER</div>
            <h2>{isReviewer && !showAllFindings ? 'Findings needing a decision' : 'Validation findings'}</h2>
          </div>
          <span className="data-note">{isReviewer ? `${pendingReviewerCount} open · ${findings.length} total` : `${findings.length} ${findings.length === 1 ? 'finding' : 'findings'}`}</span>
        </div>
        {isReviewer && <div className="finding-filters" role="group" aria-label="Filter validation findings"><button type="button" aria-pressed={!showAllFindings} className={!showAllFindings ? 'is-active' : ''} onClick={() => setShowAllFindings(false)}>Needs decision <span>{pendingReviewerCount}</span></button><button type="button" aria-pressed={showAllFindings} className={showAllFindings ? 'is-active' : ''} onClick={() => setShowAllFindings(true)}>All results <span>{findings.length}</span></button></div>}
        {reviewFeedback && <div className="review-feedback is-success" role="status">{reviewFeedback}</div>}
        {findings.length === 0 ? (
          <EmptyState title="No findings provided" text="The service returned no findings for this report." />
        ) : (
          <div className="finding-list">
            {displayedFindings.map((finding, index) => (
              <Finding
                key={finding.id || `${finding.rule_id}-${index}`}
                finding={finding}
                index={findings.indexOf(finding)}
                onReview={handleOpenReview}
                onInspectDoc={handleInspectDoc}
                isReviewer={isReviewer && app?.status !== 'review_completed'}
                saving={savingFindingId === finding.id}
                reviewBusy={Boolean(savingFindingId)}
              />
            ))}
          </div>
        )}
      </section>

      {isReviewer && app?.status === 'review_completed' && (
        <div className="review-complete-note" role="status"><Icon name="check" size={17}/> Scrutiny finalized. The institution can now view this report.</div>
      )}

      <div className="report-bottom-nav">
        {isReviewer ? (
          <>
            <Link to={`/applications/${id}/audit`} className="quiet-link"><Icon name="audit" size={17}/>Cross-Document Audit</Link>
            <Link to={`/applications/${id}/documents`} className="quiet-link"><Icon name="documents" size={17}/>Inspect Documents</Link>
            <Link to="/" className="quiet-link">Scrutiny queue <Icon name="arrow" size={16}/></Link>
          </>
        ) : (
          <>
            <Link to={`/applications/${id}/documents`} className="quiet-link"><Icon name="documents" size={17}/>Document centre</Link>
            <Link to="/" className="quiet-link">My applications <Icon name="arrow" size={16}/></Link>
          </>
        )}
      </div>

      {/* Official AICTE Scrutiny Dossier Print-Only Element */}
      <div className="official-print-dossier" aria-hidden="true">
        <div className="dossier-print-header">
          <div className="dossier-emblem-text">GOVERNMENT OF INDIA · MINISTRY OF EDUCATION</div>
          <div className="dossier-council-title">ALL INDIA COUNCIL FOR TECHNICAL EDUCATION</div>
          <div className="dossier-subtitle">Nelson Mandela Marg, Vasant Kunj, New Delhi – 110070 | Ph: 011-29581000 | Website: aicte-india.org</div>
          <div className="dossier-doc-title">
            OFFICIAL PRELIMINARY SCRUTINY COMMITTEE DOSSIER · EXTENSION OF APPROVAL ({app?.academic_year || '2026-27'})
          </div>
        </div>

        <table className="dossier-table">
          <tbody>
            <tr>
              <th style={{ width: '25%' }}>Application ID</th>
              <td style={{ width: '25%' }}><code>{app?.id}</code></td>
              <th style={{ width: '25%' }}>Application Category</th>
              <td style={{ width: '25%' }}>{app?.application_category?.toUpperCase()} (EoA)</td>
            </tr>
            <tr>
              <th>Institution Name</th>
              <td colSpan={3}><b>{app?.institution_name}</b></td>
            </tr>
            <tr>
              <th>Scrutiny Date</th>
              <td>{report?.generated_at ? new Date(report.generated_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : new Date().toLocaleDateString('en-IN')}</td>
              <th>Preliminary Scrutiny Status</th>
              <td><b>{STATUS_LABELS[report?.overall_status] || report?.overall_status}</b></td>
            </tr>
          </tbody>
        </table>

        <h4>1. Mandatory AICTE Checklist Compliance Matrix (APH 2024–2027)</h4>
        <table className="dossier-table">
          <thead>
            <tr>
              <th>Document Type</th>
              <th>Official Reference Clause</th>
              <th>Applicability</th>
              <th>Submission Status</th>
            </tr>
          </thead>
          <tbody>
            {getChecklist().map((item) => {
              const isUploaded = (app?.documents || []).some((d) => d.document_type === item.code)
              return (
                <tr key={item.code}>
                  <td><b>{item.label}</b></td>
                  <td>{item.reference}</td>
                  <td>{item.code === 'structural_stability_certificate' ? 'Conditional (>30 Yrs)' : 'Mandatory'}</td>
                  <td>{isUploaded ? '✓ SUBMITTED' : (report?.missing_document_types || []).includes(item.code) ? '✗ MISSING' : 'EXEMPT / NOT APPLICABLE'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>

        <h4>2. Scrutiny Findings Register & Human Auditor Verification Decisions</h4>
        <table className="dossier-table">
          <thead>
            <tr>
              <th>Rule ID</th>
              <th>Finding Title & Explanation</th>
              <th>Automated Rule Status</th>
              <th>Auditor Determination & Remarks</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f, i) => (
              <tr key={f.id || i}>
                <td><code>{f.rule_id}</code></td>
                <td><b>{f.title}</b><br/><small>{f.reason}</small></td>
                <td>{STATUS_LABELS[f.status] || f.status}</td>
                <td>
                  {f.reviewer_decision ? (
                    <div>
                      <b>{STATUS_LABELS[f.reviewer_decision] || f.reviewer_decision}</b><br/>
                      <em>"{f.reviewer_notes}"</em><br/>
                      <small>— {f.reviewed_by} ({f.reviewed_at ? new Date(f.reviewed_at).toLocaleDateString('en-IN') : ''})</small>
                    </div>
                  ) : requiresReviewerDecision(f) ? (
                    <span>Pending Scrutiny Desk Verification</span>
                  ) : (
                    <span>No reviewer decision required for this check.</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="dossier-signatures">
          <div className="signature-block">
            <b>Member 1 (Technical Expert)</b><br/>
            <small>AICTE Scrutiny Committee</small>
          </div>
          <div className="signature-block">
            <b>Member 2 (Directorate Nominee)</b><br/>
            <small>State Technical Education Directorate</small>
          </div>
          <div className="signature-block">
            <b>Convener / Regional Officer</b><br/>
            <small>AICTE Regional Office</small>
          </div>
        </div>
      </div>

      <AuditorReviewModal
        isOpen={!!modalFinding}
        onClose={() => setModalFinding(null)}
        finding={modalFinding}
        decision={modalInitialDecision}
        onSave={handleSaveReview}
        error={reviewError}
      />

      <DocumentViewerDrawer
        isOpen={!!drawerDoc}
        onClose={() => setDrawerDoc(null)}
        applicationId={id}
        docInfo={drawerDoc}
      />
    </div>
  )
}

const findingContext = {
  pass: 'This configured check returned a pass within its own scope. It does not establish document authenticity or decide application approval.',
  flagged: 'A potential discrepancy needs reviewer attention. A flag is not proof of fraud or an approval decision.',
  missing: 'An item expected by this configured check is absent, so the check cannot be treated as satisfied.',
  unresolved: 'The service could not complete this check reliably. Treat it as open for review, not as passed.',
  not_applicable: 'This check is marked not applicable. That status does not mean the document or claim was verified.',
}

function displayFieldName(value) { return value?.replaceAll('_', ' ') }

function Finding({ finding, index, onReview, onInspectDoc, isReviewer, saving, reviewBusy }) {
  const evidence = finding.evidence
  const status = finding.status || 'unresolved'
  const source = finding.document_name || (finding.document_id ? `Document ID ${finding.document_id}` : 'Application-level finding; no document was specified')
  const page = evidence?.page_number != null ? ` · Page ${evidence.page_number}` : ''
  const reason = finding.reason?.trim()
  const nextAction = finding.next_action?.trim()
  const reviewerDecision = finding.reviewer_decision
  const decisionRequired = requiresReviewerDecision(finding)
  const reviewState = reviewerStateLabel(finding)

  return (
    <article className={`finding finding-${status}`}>
      <div className="finding-index">{String(index + 1).padStart(2, '0')}</div>
      <div className="finding-main">
        <header className="finding-title-row">
          <div>
            <span className="finding-kicker">What was found · {String(status).replaceAll('_', ' ')}</span>
            <h3>{finding.title || 'Finding title not provided by the validation service'}</h3>
          </div>
          <Status value={status} />
        </header>

        {reviewerDecision && (
          <div className={`auditor-badge-card is-${reviewerDecision}`}>
            <div className="auditor-badge-head">
              <span className="auditor-decision-tag">{reviewState}</span>
              {finding.reviewed_at && (
                <span className="auditor-date">
                  {new Date(finding.reviewed_at).toLocaleString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              )}
            </div>
            {finding.reviewed_by && (
              <p className="auditor-reviewer-id">Reviewed by: {finding.reviewed_by}</p>
            )}
            {finding.reviewer_notes && (
              <p className="auditor-notes">"{finding.reviewer_notes}"</p>
            )}
          </div>
        )}
        {!reviewerDecision && (
          <div className={`review-state-note ${decisionRequired ? 'is-pending' : 'is-not-required'}`}>
            {reviewState}
          </div>
        )}

        <details open={decisionRequired && !reviewerDecision} className="finding-details-disclosure"><summary>View check details, evidence and recommended action</summary>
        <section className="finding-explanation" aria-label="Finding explanation">
          <div className="finding-detail checked-detail">
            <h4>What was checked</h4>
            <p>
              {finding.rule_id ? (
                <>Configured check <code>{finding.rule_id}</code>.</>
              ) : (
                'The validation service did not provide a check reference or description.'
              )}
            </p>
          </div>
          <div className="finding-detail impact-detail">
            <h4>Why it matters</h4>
            <p>{findingContext[status] || 'Review the returned reason and evidence before deciding how to proceed.'}</p>
          </div>
          <div className="finding-detail reason-detail">
            <h4>Why this result was returned</h4>
            <p>{reason || 'Reason not provided by the validation service.'}</p>
          </div>
        </section>

        <section className="finding-evidence" aria-label="Evidence">
          <div className="finding-evidence-heading">
            <h4>What the document shows</h4>
            <span>{source}{page}</span>
          </div>
          {evidence ? (
            <>
              {(evidence.field || evidence.value != null) && (
                <div className="evidence-value">
                  <span>{displayFieldName(evidence.field) || 'Extracted value'}</span>
                  <b>{evidence.value != null ? String(evidence.value) : 'Value unavailable'}</b>
                </div>
              )}
              {evidence.raw_text || evidence.text ? (
                <blockquote>{evidence.raw_text || evidence.text}</blockquote>
              ) : (
                <p className="evidence-unavailable">Supporting text snippet unavailable.</p>
              )}
            </>
          ) : (
            <p className="evidence-unavailable">
              Evidence unavailable. The validation service returned no supporting evidence for this finding.
            </p>
          )}
        </section>

        <section className="finding-next-action">
          <h4>Recommended next action</h4>
          <p>{nextAction || 'Recommended next action was not provided by the validation service.'}</p>
        </section>

        <div className="auditor-action-bar">
          {isReviewer && decisionRequired && !hasRecordedReviewerDecision(finding) && (
            <>
              <button
                type="button"
                className="button-auditor button-auditor-verify"
                onClick={() => onReview(finding, 'verified')}
                disabled={reviewBusy}
              >
                {saving ? <span className="spinner spinner-small"/> : <Icon name="check" size={14} />} {saving ? 'Saving…' : 'Mark Verified'}
              </button>
              <button
                type="button"
                className="button-auditor button-auditor-resubmit"
                onClick={() => onReview(finding, 'requested_resubmission')}
                disabled={reviewBusy}
              >
                <Icon name="alert" size={14} /> Request Resubmission
              </button>
              <button
                type="button"
                className="button-auditor button-auditor-escalate"
                onClick={() => onReview(finding, 'escalated')}
                disabled={reviewBusy}
              >
                <Icon name="shield" size={14} /> Escalate
              </button>
            </>
          )}

          {finding.document_id && (
            <button
              type="button"
              className="button-auditor button-inspect-doc"
              onClick={() =>
                onInspectDoc({
                  documentId: finding.document_id,
                  documentName: finding.document_name,
                  pageNumber: evidence?.page_number || 1,
                  bbox: evidence?.bbox || null,
                  evidenceText: evidence?.raw_text || evidence?.text || null,
                })
              }
            >
              <Icon name="documents" size={14} /> View in Document
            </button>
          )}
        </div>
        </details>
      </div>
    </article>
  )
}

function NotFound() { return <div className="not-found"><span className="eyebrow">404 · PAGE NOT FOUND</span><h1>This page isn’t<br/><em>in the file.</em></h1><ButtonLink to="/" icon="arrow">Return to overview</ButtonLink></div> }

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Shell>
                <Routes>
                  <Route path="/" element={<Overview />} />
                  <Route
                    path="/documents"
                    element={
                      <ProtectedRoute allowedRoles={['INSTITUTION']}>
                        <DocumentEntry />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/applications/new"
                    element={
                      <ProtectedRoute allowedRoles={['INSTITUTION']}>
                        <CreateApplication />
                      </ProtectedRoute>
                    }
                  />
                  <Route path="/applications/:id/documents" element={<ApplicationDocumentCentre />} />
                  <Route path="/applications/:id/audit" element={<AuditWorkspace />} />
                  <Route path="/applications/:id/report" element={<ValidationReport />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Shell>
            </ProtectedRoute>
          }
        />
      </Routes>
    </>
  )
}
