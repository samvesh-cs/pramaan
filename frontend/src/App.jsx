import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { APPLICATION_CATEGORIES, CHECK_STATUSES, STATUS_LABELS, USE_MOCKS } from './config'
import { labelForDocument } from './demoData'
import { createApplication, getApplication, getChecklist, getReport, listApplications, runValidation, uploadDocument } from './api'

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
  const [menuOpen, setMenuOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 800px)').matches)
  const previousPath = useRef(location.pathname)
  const [transitionPath, setTransitionPath] = useState(null)
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
  useEffect(() => {
    if (previousPath.current === location.pathname) return undefined
    previousPath.current = location.pathname
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined
    setTransitionPath(location.pathname)
    const timeout = window.setTimeout(() => setTransitionPath((activePath) => activePath === location.pathname ? null : activePath), 720)
    return () => window.clearTimeout(timeout)
  }, [location.pathname])
  const primary = [['/', 'overview', 'Overview'], ['/documents', 'upload', 'Documents'], ['/applications/new', 'plus', 'New application']]
  const pageTitle = location.pathname === '/' ? 'Overview' : location.pathname === '/documents' ? 'Documents' : location.pathname.includes('/report') ? 'Validation report' : location.pathname.includes('/audit') ? 'Audit workspace' : location.pathname.includes('/documents') ? 'Document centre' : 'New application'
  const sidebarExpanded = isMobile ? menuOpen : !menuOpen
  return <div className={`app-shell ${!isMobile && menuOpen ? 'sidebar-collapsed' : ''}`}>
    {transitionPath === location.pathname && <div key={transitionPath} className="holo-transition is-active" aria-hidden="true"><span className="holo-veil"/><span className="holo-grid"/><span className="holo-document-outline"><i className="holo-corner corner-tl"/><i className="holo-corner corner-tr"/><i className="holo-corner corner-bl"/><i className="holo-corner corner-br"/></span><span className="holo-scan-line"/><span className="holo-fragment fragment-a"/><span className="holo-fragment fragment-b"/><span className="holo-fragment fragment-c"/></div>}
    <button type="button" className={`sidebar-backdrop ${isMobile && menuOpen ? 'visible' : ''}`} aria-label="Close navigation" tabIndex={isMobile && menuOpen ? 0 : -1} onClick={() => setMenuOpen(false)} />
    <aside id="primary-navigation" className={`sidebar ${isMobile && menuOpen ? 'sidebar-open' : ''}`} aria-label="Primary navigation" aria-hidden={isMobile && !menuOpen} inert={isMobile && !menuOpen}>
      <Link to="/" className="brand" aria-label="Pramaan home"><span className="brand-mark"><svg aria-hidden="true" viewBox="0 0 32 32" fill="none"><path d="M12 5H7v22h5M20 5h5v22h-5" stroke="#e6e1d7" strokeWidth="2" strokeLinecap="square" strokeLinejoin="miter"/><path d="M12.5 12.5h7M12.5 16h5" stroke="#e6e1d7" strokeWidth="1.6" strokeLinecap="round"/><path d="m18 21 2 2 4-5" stroke="#d8a66c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg></span><span className="brand-copy"><b>pramaan</b><small>REVIEW WORKSPACE</small></span></Link>
      <nav className="side-nav">{primary.map(([to, icon, label]) => <NavLink key={to} to={to} end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} title={label} aria-label={label}><Icon name={icon} size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-foot"><div className="review-note"><Icon name="shield" size={16}/><p>Preliminary scrutiny supports reviewers; it does not verify authenticity or decide approval.</p></div><div className="sidebar-user"><span className="sidebar-user-copy"><b>Review desk</b><small>Institutional scrutiny</small></span></div></div>
    </aside>
    <main className="main-area"><div className="ambient-contours" aria-hidden="true"><svg viewBox="0 0 600 600" fill="none"><path d="M608 31C494 4 331 34 274 115c-38 54-13 115 43 135 76 28 196-25 198-94 2-59-78-89-144-65-82 30-114 123-86 204 28 80 121 126 220 101 75-19 122-75 99-131-21-50-98-63-155-33-70 37-82 118-42 183 40 66 116 103 193 91"/><path d="M603 66c-94-20-228 5-277 67-33 43-15 91 32 109 63 24 163-20 164-76 1-48-64-73-120-52-69 26-95 103-72 170 23 66 102 103 185 83 63-16 101-62 82-108-18-42-82-53-130-28-57 30-67 96-35 150 34 56 96 87 160 77"/><path d="M600 103c-75-15-177 1-216 49-27 33-15 69 23 84 49 18 128-16 129-59 1-37-51-56-95-39-55 21-75 82-58 135 18 52 81 81 148 65 50-12 80-49 65-84-14-33-65-41-103-22-45 24-53 75-27 117 26 44 76 68 127 60"/><path d="M596 144c-55-9-128 0-158 34-21 23-13 48 15 59 37 13 96-12 97-43 1-27-38-41-70-28-40 15-55 60-42 99 13 38 60 58 108 47 36-8 57-36 46-62-10-23-47-29-74-15-32 17-37 53-19 83 19 32 55 49 92 43"/></svg></div><header className="topbar"><button type="button" className="icon-button mobile-menu" aria-controls="primary-navigation" aria-expanded={sidebarExpanded} aria-label={sidebarExpanded ? 'Collapse navigation sidebar' : 'Expand navigation sidebar'} onClick={() => setMenuOpen((open) => !open)}><Icon name="menu"/></button><div className="topbar-page-title" aria-live="polite">{pageTitle}</div></header>
      <div className={`page-stage ${transitionPath === location.pathname ? 'route-entering' : ''}`} key={location.pathname}>{children}</div>
      <footer className="footer"><span>SIH 2026 · PS 26261</span><span>Preliminary review only <i>·</i> Human judgment required</span></footer>
    </main>
  </div>
}

function Overview() {
  const [apps, setApps] = useState(null); const [error, setError] = useState('')
  const load = () => { setError(''); listApplications().then(setApps).catch((e) => setError(e.message)) }
  useEffect(load, [])
  const counts = useMemo(() => (apps || []).reduce((sum, app) => { sum[app.overall_status] = (sum[app.overall_status] || 0) + 1; return sum }, {}), [apps])
  return <div className="mx-auto w-full max-w-6xl">
    <header className="mb-7 mt-2 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end sm:gap-6">
      <div><div className="eyebrow text-[#6e7872]">REVIEW DESK · 2026 / 27</div><h1 className="my-2 text-[29px] font-semibold leading-tight tracking-[-0.035em] text-[#1d3036] sm:text-4xl">Application queue</h1><p className="m-0 max-w-2xl text-[13px] leading-relaxed text-[#68736d] sm:text-sm">Review submitted applications and open a record to inspect its documents and findings.</p></div>
      <ButtonLink to="/applications/new" icon="plus">New application</ButtonLink>
    </header>
    <div><div className="mb-3 text-xs text-[#777f78]">{USE_MOCKS ? 'Synthetic demonstration records' : 'Applications from the live API'}</div>
      {error && <ErrorNotice message={error} onRetry={load}/>}
      {!apps && !error && <div className="queue-loading"><Loading label="Gathering applications"/></div>}
      {apps && <><div className="mb-6 grid grid-cols-3 border-y border-[#263b42]/15" aria-label="Application queue summary"><Metric label="In the queue" value={apps.length}/><Metric label="Needs attention" value={apps.filter((a) => ['missing_documents','discrepancies_found','unresolved_checks','processing_incomplete'].includes(a.overall_status)).length} accent/><Metric label="Checks passed" value={counts.checks_passed || 0}/></div>
        <section aria-labelledby="queue-heading"><div className="mb-3"><h2 id="queue-heading" className="m-0 text-lg font-semibold tracking-tight text-[#334b49]">Applications</h2><p className="mt-1 text-xs leading-relaxed text-[#68736d] sm:text-[13px]">Select a record to review its documents and validation findings.</p></div>
          {apps.length === 0 ? <EmptyState title="No applications yet" text="Create an application to begin a preliminary document review." action={<ButtonLink to="/applications/new" icon="arrow">Create application</ButtonLink>}/> : <div className="overflow-x-auto border-t border-[#263b42]/20"><div className="hidden min-w-190 grid-cols-[minmax(260px,2fr)_120px_100px_minmax(170px,1.2fr)_80px] items-center gap-4 border-b border-[#263b42]/15 px-3 py-3 text-[10px] font-semibold tracking-[.06em] text-[#777f78] sm:grid"><span>INSTITUTION</span><span>ACADEMIC YEAR</span><span>DOCUMENTS</span><span>REVIEW STATUS</span><span/></div>{apps.map((app) => <div className="grid min-h-17 min-w-90 grid-cols-[minmax(0,1fr)_auto_28px] items-center gap-2 border-b border-[#263b42]/15 px-1 py-2.5 text-sm text-[#394d4b] sm:min-w-190 sm:grid-cols-[minmax(260px,2fr)_120px_100px_minmax(170px,1.2fr)_80px] sm:gap-4 sm:px-3" key={app.id}><div className="min-w-0"><b className="block truncate text-xs font-semibold leading-snug text-[#293f3e] sm:text-sm">{app.institution_name}</b><small className="mt-1 block text-[10px] text-[#737d76] sm:text-xs">{app.created_at ? `Created ${new Date(app.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}` : 'Creation date not provided'}<span className="sm:hidden"> · {app.academic_year} · {app.documents?.length ?? '—'} docs</span></small><span className="mt-1 block sm:hidden"><Status value={app.overall_status}/></span></div><span className="hidden text-[13px] text-[#465b57] sm:block">{app.academic_year}</span><span className="hidden text-[13px] text-[#465b57] sm:block">{app.documents?.length ?? '—'}</span><span className="hidden sm:block"><Status value={app.overall_status}/></span><Link className="inline-flex min-h-8 items-center justify-end gap-1 text-[0px] font-semibold text-[#315e5b] underline underline-offset-4 hover:text-[#234643] sm:text-xs" aria-label={`Open documents for ${app.institution_name}`} to={`/applications/${app.id}/documents`}>Open <Icon name="arrow" size={16}/></Link></div>)}</div>}
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
  const navigate = useNavigate(); const [form, setForm] = useState({ institution_name: '', application_category: APPLICATION_CATEGORIES[0]?.code || '', academic_year: '2026-27' });
  const [errors, setErrors] = useState({}); const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const submit = async (event) => { event.preventDefault(); const next = {}; if (!form.institution_name.trim()) next.institution_name = 'Enter the institution name.'; if (!form.application_category) next.application_category = 'Choose the configured category.'; if (!/^\d{4}-\d{2}$/.test(form.academic_year.trim())) next.academic_year = 'Use the format 2026-27.'; setErrors(next); if (Object.keys(next).length) return; setBusy(true); setError(''); try { const app = await createApplication({ ...form, institution_name: form.institution_name.trim(), academic_year: form.academic_year.trim() }); navigate(`/applications/${app.id}/documents`, { state: { created: true } }) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  return <div className="form-page"><PageHeader eyebrow="APPLICATION INTAKE · 01" title={<>Start with the<br/><em>institution.</em></>} description="Create a review record before adding its supporting documents."/><div className="form-layout"><form className="editorial-form" onSubmit={submit} noValidate><div className="form-section-label"><span>01</span><div><b>Application identity</b><small>Use the institution name as submitted.</small></div></div><label className="field-label" htmlFor="institution">Institution name <span>REQUIRED</span></label><input id="institution" autoComplete="organization" placeholder="e.g. Synthetic Northfield Institute of Technology" value={form.institution_name} onChange={(e) => setForm({ ...form, institution_name: e.target.value })} aria-invalid={!!errors.institution_name} aria-describedby={errors.institution_name ? 'institution-error' : undefined}/>{errors.institution_name && <small id="institution-error" className="field-error">{errors.institution_name}</small>}
      <div className="form-grid"><div><label className="field-label" htmlFor="category">Application category <span>CONFIGURED CODE</span></label><select id="category" value={form.application_category} onChange={(e) => setForm({ ...form, application_category: e.target.value })} aria-invalid={!!errors.application_category}>{APPLICATION_CATEGORIES.map((category) => <option value={category.code} key={category.code}>{category.label}</option>)}</select>{errors.application_category && <small className="field-error">{errors.application_category}</small>}<small className="field-helper">The contract lists EoA as a candidate. Team confirmation is pending.</small></div><div><label className="field-label" htmlFor="year">Academic year <span>FORMAT: YYYY-YY</span></label><input id="year" placeholder="2026-27" value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} aria-invalid={!!errors.academic_year}/>{errors.academic_year && <small className="field-error">{errors.academic_year}</small>}</div></div>
      <div className="form-submit"><button type="submit" className="button button-primary" disabled={busy}>{busy ? <><span className="spinner spinner-light"/>Creating record…</> : <>Create application <Icon name="arrow" size={17}/></>}</button><span>Fields marked required must be completed.</span></div>{error && <ErrorNotice message={error}/>}</form>
      <aside className="form-aside"><div className="aside-number">INTAKE NOTE <span>01 / 03</span></div><h3>Keep the record<br/>grounded in the file.</h3><p>This creates an application record. Documents are added in the next step. Validation status comes from actual processing and configured checks.</p><div className="aside-line"/><div className="aside-meta"><span>CONTRACT REQUEST</span><code>institution_name<br/>application_category<br/>academic_year</code></div><div className="aside-meta"><span>REVIEW PRINCIPLE</span><b>Preliminary scrutiny<br/>with a human in control.</b></div></aside></div></div>
}

function ApplicationDocumentCentre() {
  const { id } = useParams()
  const fileInputRef = useRef(null)
  const uploadSectionRef = useRef(null)
  const documentTypeRef = useRef(null)
  const [app, setApp] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [file, setFile] = useState(null)
  const [type, setType] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [dragging, setDragging] = useState(false)

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
  const showUploadedFile = (documentId) => {
    window.document.getElementById(`uploaded-${documentId}`)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
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

  if (loading) return <Loading label="Opening application record" />
  if (error) return <ErrorNotice message={error} onRetry={load} />
  const documents = Array.isArray(app?.documents) ? app.documents : []
  const types = getChecklist()
  const present = new Set(documents.map((doc) => doc.document_type))
  const presentCount = types.filter((item) => present.has(item.code)).length
  const missingCount = types.filter((item) => !present.has(item.code)).length
  const processingCount = documents.filter((doc) => ['uploaded', 'processing'].includes(doc.processing_status)).length
  const failedCount = documents.filter((doc) => doc.processing_status === 'processing_failed').length
  const processedCount = documents.filter((doc) => doc.processing_status === 'processed').length
  const canContinue = documents.length > 0
  const auditMessage = !canContinue
    ? 'Upload at least one document to open the audit workspace.'
    : missingCount
      ? `${missingCount} configured checklist item${missingCount === 1 ? '' : 's'} still have no file. The audit can still report missing types.`
      : processingCount
        ? `${processingCount} file${processingCount === 1 ? ' is' : 's are'} awaiting processing; its status will remain visible in the audit.`
        : 'Review the returned statuses before continuing to preliminary validation.'

  return <div className="document-page document-workflow-page">
    <PageHeader eyebrow="DOCUMENT CENTRE · APPLICATION WORKFLOW" title={<>Document<br /><em>workflow.</em></>} description="Review the configured requirements, add files, then inspect their reported processing states." />
    <section className="application-identity" aria-labelledby="application-identity-title">
      <div className="identity-heading"><div><div className="eyebrow">APPLICATION IDENTIFICATION</div><h2 id="application-identity-title">{app.institution_name || 'Institution name not provided'}</h2><div className="identity-meta"><span>{APPLICATION_CATEGORIES.find((category) => category.code === app.application_category)?.label || app.application_category || 'Category not provided'}</span><i>·</i><span>Academic year {app.academic_year || 'not provided'}</span><i>·</i><span>Reference {app.id}</span></div></div><Status value={app.overall_status} /></div>
      <div className="identity-summary"><span><b>{presentCount} / {types.length}</b><small>listed document types with a file</small></span><span><b>{processedCount}</b><small>processed</small></span><span><b>{processingCount}</b><small>awaiting processing</small></span><span><b>{failedCount}</b><small>processing failed</small></span></div>
    </section>
    {USE_MOCKS && <div className="demo-callout"><span className="mode-dot" /><span><b>Synthetic demonstration data.</b> The three configured document types are an MVP subset, not the complete EoA checklist.</span></div>}
    <ol className="workflow-steps" aria-label="Document workflow steps"><li><span>01</span><b>Check requirements</b></li><li><span>02</span><b>Upload documents</b></li><li><span>03</span><b>Review file status</b></li><li><span>04</span><b>Continue to audit</b></li></ol>

    <section className="workflow-section checklist-section" aria-labelledby="checklist-heading">
      <div className="workflow-section-head"><div><span className="workflow-step-number">01</span><div><div className="eyebrow">REQUIREMENTS · CONFIGURABLE</div><h2 id="checklist-heading">Required-document checklist</h2></div></div><span className="section-side-note">{missingCount ? `${missingCount} still need attention` : 'A file exists for every listed type'}</span></div>
      <div className="workflow-checklist" role="list">{types.map((item, index) => {
        const doc = documents.find((entry) => entry.document_type === item.code)
        const state = doc?.processing_status || 'missing'
        const stateLabel = { missing: 'Missing · not received', uploaded: 'Uploaded · awaiting processing', processing: 'Processing', processed: 'Processed', processing_failed: 'Processing failed' }[state] || state
        return <div className={`workflow-check-row checklist-${state}`} role="listitem" key={item.code}><span className="check-index">{String(index + 1).padStart(2, '0')}</span><span className="workflow-check-name"><b>{item.label}</b><small>{item.reference || 'Configurable document type'}</small></span><Status value={state} /><span className={`workflow-state-copy workflow-state-${state}`}>{stateLabel}</span>{doc?.processing_status === 'processing_failed' ? <button type="button" className="workflow-row-action" onClick={() => focusUpload(item.code)}>Replace document <Icon name="arrow" size={14} /></button> : doc ? <button type="button" className="workflow-row-action" onClick={() => showUploadedFile(doc.id)}>Review file <Icon name="arrow" size={14} /></button> : <button type="button" className="workflow-row-action" onClick={() => focusUpload(item.code)}>Upload this type <Icon name="arrow" size={14} /></button>}</div>
      })}</div>
      <p className="checklist-disclaimer">Presence and processing status are based on the application response. The listed types remain demo configuration until the team confirms an official source.</p>
    </section>

    <section className="workflow-section upload-section" id="upload-section" ref={uploadSectionRef} aria-labelledby="upload-heading">
      <div className="workflow-section-head"><div><span className="workflow-step-number">02</span><div><div className="eyebrow">ADD TO THIS APPLICATION</div><h2 id="upload-heading">Upload documents</h2></div></div><span className="section-side-note">PDF · JPG · PNG</span></div>
      <form onSubmit={submit} className="workflow-upload-form"><div className="upload-form-top"><div><label htmlFor="doc-type" className="field-label">Document type <span>SELECT THE CHECKLIST ITEM</span></label><select ref={documentTypeRef} id="doc-type" value={type} onChange={(event) => setType(event.target.value)} required><option value="" disabled>Select a configured type</option>{types.map((item) => <option value={item.code} key={item.code}>{item.label} · {item.code}</option>)}</select>{type && <p className="selected-type-note">This file will be associated with <b>{types.find((item) => item.code === type)?.label || type}</b>.</p>}</div><div className="upload-contract-note"><Icon name="file" size={16} /><span>Accepted formats follow the API contract. File size and content are checked by the server.</span></div></div>
        <label className={`dropzone ${dragging ? 'dropzone-over' : ''}`} htmlFor="file-input" onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files?.[0]) }}><input ref={fileInputRef} id="file-input" type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" onChange={(event) => acceptFile(event.target.files?.[0])} /><span className="upload-symbol"><Icon name="upload" size={23} /></span><b>{file ? file.name : 'Drag a document into this space'}</b><span>{file ? `${file.type || 'File'} · selected and ready` : 'PDF, JPG, or PNG — or choose a file below'}</span><small>PDF / JPG / PNG</small></label>
        <div className="upload-actions"><button type="button" className="browse-button" onClick={() => fileInputRef.current?.click()}><Icon name="file" size={16} />{file ? 'Choose a different file' : 'Choose file'}<span>{file ? 'Replace selection' : 'From this device'}</span></button><button className="button button-copper upload-submit" type="submit" disabled={busy || !file || !type}>{busy ? <><span className="spinner spinner-light" />Uploading…</> : <>Upload selected file <Icon name="arrow" size={17} /></>}</button></div>
        {file && <div className="selected-file-summary"><Icon name="file" size={17} /><span><b>{file.name}</b><small>{file.type || 'File type unavailable'} · {types.find((item) => item.code === type)?.label || 'Choose a document type'}</small></span><span className="selection-status">Ready to upload</span></div>}
        {message && <div className={`inline-message ${message.startsWith('Upload received') ? 'message-success' : 'message-error'}`} role={message.startsWith('Upload received') ? 'status' : 'alert'}>{message}</div>}
        <p className="upload-note">Dates and fields are extracted or reviewed later; they are not accepted as authoritative upload inputs.</p>
      </form>
    </section>

    <section className="workflow-section uploaded-section" aria-labelledby="uploaded-heading"><div className="workflow-section-head"><div><span className="workflow-step-number">03</span><div><div className="eyebrow">APPLICATION FILE</div><h2 id="uploaded-heading">Uploaded documents</h2></div></div><span className="section-side-note">{documents.length} {documents.length === 1 ? 'file' : 'files'} · {processedCount} processed</span></div>{documents.length === 0 ? <EmptyState title="No documents received" text="Files appear here after the upload request returns successfully." /> : <div className="uploaded-file-table"><div className="uploaded-file-header"><span>FILE NAME</span><span>DOCUMENT TYPE</span><span>PROCESSING STATUS</span><span>FILE TYPE</span></div>{documents.map((doc) => <DocumentItem key={doc.id} doc={doc} />)}</div>}
      {documents.some((doc) => fieldsForDocument(doc).length) && <div className="fields-panel"><div className="eyebrow">EXTRACTED FIELD INSPECTION</div><h3>Fields returned by processing</h3>{documents.flatMap((doc) => fieldsForDocument(doc).map((field, index) => <FieldRow key={`${doc.id}-${index}`} field={{ ...field, source_document: field.source_document || doc.original_filename }} />))}</div>}
    </section>

    <section className="audit-gate" aria-labelledby="audit-gate-heading"><div className="workflow-step-number">04</div><div className="audit-gate-copy"><div className="eyebrow">NEXT · PRELIMINARY VALIDATION</div><h2 id="audit-gate-heading">Continue to the audit workspace</h2><p>{auditMessage}</p></div>{canContinue ? <ButtonLink to={`/applications/${id}/audit`} icon="arrow">Continue to audit</ButtonLink> : <button type="button" className="button button-primary" disabled>Upload a document first <Icon name="arrow" size={17} /></button>}</section>
  </div>
}
function DocumentItem({ doc }) { return <article className="received-item uploaded-file-row" id={`uploaded-${doc.id}`}><span className="uploaded-file-name"><span className="file-mark"><Icon name="documents" size={20} /></span><b>{doc.original_filename || labelForDocument(doc.document_type)}</b></span><span className="uploaded-type-name">{labelForDocument(doc.document_type)}</span><Status value={doc.processing_status || 'uploaded'} /><span className="uploaded-mime">{doc.mime_type?.includes('pdf') ? 'PDF' : doc.mime_type?.split('/')[1]?.toUpperCase() || doc.mime_type || 'Not provided'}</span></article> }
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
  const { id } = useParams(); const [app, setApp] = useState(null); const [report, setReport] = useState(null); const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [error, setError] = useState('')
  const load = () => { setLoading(true); getApplication(id).then((value) => { if (!value) throw new Error('Application could not be found.'); setApp(value); return getReport(id) }).then((value) => setReport(hasValidationRun(value) ? value : null)).catch((e) => setError(e.message)).finally(() => setLoading(false)) }
  useEffect(load, [id])
  const start = async () => { setBusy(true); setError(''); setReport(null); try { const result = await runValidation(id); setReport(result) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  if (loading) return <Loading label="Preparing review workspace"/>
  if (error && !app) return <ErrorNotice message={error} onRetry={load}/>
  const docs = app?.documents || []
  return <div className="audit-page"><PageHeader eyebrow="REVIEW WORKSPACE · 02" title={<>Compare the file<br/><em>with the checks.</em></>} description={<><b>{app?.institution_name}</b><span className="description-dot">·</span>{app?.academic_year}</>}/>
    {USE_MOCKS && <div className="demo-callout"><span className="mode-dot"/><span><b>Demonstration mode.</b> Synthetic records and checklist; results are not a real validation or an authenticity determination.</span></div>}
    <div className={`audit-stage ${busy ? 'is-running' : ''} ${report ? 'is-complete' : ''}`}>
      <div className="audit-instructions"><div><span className="audit-step">01 <i>—</i> DOCUMENTS</span><h2>Submitted material</h2><p>{docs.length} {docs.length === 1 ? 'document' : 'documents'} associated with this record</p></div><div className="audit-center-caption"><span className="center-ring"><Icon name={busy ? 'clock' : report ? 'check' : 'audit'} size={21}/></span><small>{busy ? 'COMPARING' : report ? 'RESPONSE RECEIVED' : 'AWAITING REVIEW'}</small></div><div><span className="audit-step">02 <i>—</i> CONFIGURATION</span><h2>Review checks</h2><p>{getChecklist().length} configured demonstration requirements</p></div></div>
      <div className="audit-panels"><div className="audit-panel doc-panel"><div className="panel-head"><span className="panel-num">A</span><span><b>Application file</b><small>Submitted documents</small></span><span className="panel-count">{docs.length.toString().padStart(2, '0')}</span></div><div className="panel-content">{docs.length ? docs.map((doc, index) => <div className="audit-document-group" key={doc.id}><div className={`audit-doc-line ${busy ? 'stagger' : ''}`} style={{ '--i': index }}><span className="audit-doc-icon"><Icon name="documents" size={17}/></span><span><b>{doc.original_filename || labelForDocument(doc.document_type)}</b><small>{labelForDocument(doc.document_type)} · {STATUS_LABELS[doc.processing_status] || doc.processing_status}</small></span><i className={`status-marker marker-${doc.processing_status}`}/></div>{fieldsForDocument(doc).slice(0, 3).map((field, fieldIndex) => <div className={`audit-field-line ${busy ? 'stagger' : ''}`} style={{ '--i': index + fieldIndex + 1 }} key={`${doc.id}-${field.field || field.name || fieldIndex}`}><span>{field.name || field.field || 'Extracted field'}</span><b>{field.value || 'Unavailable'}</b><small>{field.raw_text || field.evidence || 'No evidence snippet provided'}</small></div>)}</div>) : <div className="panel-empty">No documents have been added yet.<Link to={`/applications/${id}/documents`}>Go to document centre <Icon name="arrow" size={14}/></Link></div>}</div><div className="panel-foot">SOURCE MATERIAL <span>As supplied by applicant</span></div></div>
        <div className="connection-lanes" aria-hidden="true"><svg className="comparison-signature" viewBox="0 0 120 230" preserveAspectRatio="none"><path className="signature-underlay" d="M-10 48C19 46 15 88 35 91s17-58 36-54 12 79 31 83 12-42 31-39"/><path className="signature-main" d="M-10 48C19 46 15 88 35 91s17-58 36-54 12 79 31 83 12-42 31-39"/><path className="signature-flick" d="M70 37c-5 28-12 54-30 79m62 4 14 20"/></svg><span className="lane-line"/><span className="lane-line"/><span className="scan-pulse"/><span className="lane-caption">FIELD<br/>COMPARISON</span></div>
        <div className="audit-panel rules-panel"><div className="panel-head"><span className="panel-num">B</span><span><b>Configured checklist</b><small>Three-document MVP subset</small></span><span className="panel-count">{getChecklist().length.toString().padStart(2, '0')}</span></div><div className="panel-content">{getChecklist().map((item, index) => <div className={`audit-rule-line ${busy ? 'stagger' : ''}`} style={{ '--i': index }} key={item.code}><span className="rule-node">{String(index + 1).padStart(2,'0')}</span><span><b>{item.label}</b><small>{item.code}</small></span><span className="rule-state"><i className={busy ? 'rule-pulse' : ''}/>{report ? 'CONFIGURED' : 'READY'}</span></div>)}</div><div className="panel-foot">SOURCE <span>APH clauses in the checklist</span></div></div></div>
      {!report && <div className="audit-action-row"><div className="audit-caveat"><Icon name="shield" size={17}/><span>Running validation requests a preliminary report. A human reviewer remains responsible for the assessment.</span></div><button type="button" className="button button-primary begin-audit" disabled={busy || docs.length === 0} onClick={start}>{busy ? <><span className="spinner spinner-light"/>Waiting for report…</> : <>Begin validation <Icon name="arrow" size={17}/></>}</button></div>}
      {docs.length === 0 && !report && <p className="audit-prerequisite">Add at least one document before starting validation.</p>}
      {error && <ErrorNotice message={error} onRetry={start}/>}
      {report && <div className="audit-result"><div className="result-seal"><Icon name={report.overall_status === 'checks_passed' ? 'check' : 'report'} size={22}/></div><div className="result-copy"><span className="eyebrow">REPORT RESPONSE RECEIVED</span><h3>Preliminary result returned.</h3><p>The result is ready for a reviewer to inspect. It is not an approval decision.</p><div className="result-finding-preview">{report.summary && Object.entries(report.summary).filter(([, count]) => Number(count) > 0).map(([status, count]) => <span key={status}><b>{count}</b> {STATUS_LABELS[status] || status}</span>)}{Array.isArray(report.findings) && report.findings.slice(0, 2).map((finding) => <span className="result-finding-title" key={finding.id || finding.rule_id}>{finding.title || finding.reason}</span>)}</div></div><Status value={report.overall_status}/><ButtonLink to={`/applications/${id}/report`} icon="arrow">Open validation report</ButtonLink></div>}
    </div>
  </div>
}

function ValidationReport() {
  const { id } = useParams(); const [app, setApp] = useState(null); const [report, setReport] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  const load = () => { setLoading(true); setError(''); Promise.all([getApplication(id), getReport(id)]).then(([a, r]) => { if (!a) throw new Error('Application could not be found.'); setApp(a); setReport(hasValidationRun(r) ? r : null) }).catch((e) => setError(e.message)).finally(() => setLoading(false)) }
  useEffect(load, [id])
  if (loading) return <Loading label="Retrieving report"/>
  if (error) return <ErrorNotice message={error} onRetry={load}/>
  if (!report) return <div className="report-empty"><PageHeader eyebrow="VALIDATION REPORT · 03" title={<>No report<br/><em>on record.</em></>} description={app?.institution_name}/><EmptyState title="Validation has not been run" text="Start the audit workspace to request a report for this application." action={<ButtonLink to={`/applications/${id}/audit`} icon="arrow">Open audit workspace</ButtonLink>}/></div>
  const summary = report.summary || {}; const findings = Array.isArray(report.findings) ? report.findings : []
  const summaryStatuses = CHECK_STATUSES.filter((status) => Number.isFinite(summary[status]))
  const reportedMissingTypes = Array.isArray(report.missing_document_types) ? report.missing_document_types : []
  const missingTypesCoveredByFindings = reportedMissingTypes.every((code) => {
    const label = labelForDocument(code).toLowerCase()
    return findings.some((finding) => finding.status === 'missing' && [finding.title, finding.reason].some((value) => value?.toLowerCase().includes(label)))
  })
  return <div className="report-page"><PageHeader eyebrow="VALIDATION REPORT · HUMAN REVIEW REQUIRED" title={<>Review the<br/><em>evidence trail.</em></>} description={<><b>{app?.institution_name}</b><span className="description-dot">·</span>{app?.academic_year}<span className="description-dot">·</span>{app?.application_category}</>} action={<ButtonLink to={`/applications/${id}/documents`} variant="secondary" icon="documents">Back to documents</ButtonLink>}/>
    {USE_MOCKS && <div className="demo-callout"><span className="mode-dot"/><span><b>Synthetic demonstration report.</b> This report is not based on an actual application and does not prove authenticity or determine AICTE approval.</span></div>}
    <section className="report-overview"><div className="report-status-block"><span className="eyebrow">OVERALL VALIDATION STATUS</span><Status value={report.overall_status}/><p>Preliminary checks only <i>·</i> Reviewer assessment required</p></div><div className="report-meta"><span>APPLICATION REFERENCE</span><b>{app?.id}</b><span>REPORT GENERATED</span><b>{report.generated_at ? new Date(report.generated_at).toLocaleString('en-IN') : 'Not provided by service'}</b></div></section>
    {summaryStatuses.length > 0 && <section className="report-summary"><div className="summary-heading"><div className="eyebrow">CHECK SUMMARY</div><h2>What the checks returned</h2></div><div className="summary-counts">{summaryStatuses.map((status) => <div className={`summary-count count-${status}`} key={status}><span>{STATUS_LABELS[status]}</span><b>{summary[status]}</b></div>)}</div></section>}
    {reportedMissingTypes.length > 0 && !missingTypesCoveredByFindings && <section className="reported-missing" aria-label="Missing document types"><h2>Missing document types reported</h2><p>These checklist items were returned separately from the finding details.</p><ul>{reportedMissingTypes.map((code) => <li key={code}>{labelForDocument(code)}</li>)}</ul></section>}
    <section className="findings-section"><div className="section-title-row"><div><div className="eyebrow">FINDING REGISTER</div><h2>Items for reviewer attention</h2></div><span className="data-note">{findings.length} {findings.length === 1 ? 'finding' : 'findings'}</span></div>{findings.length === 0 ? <EmptyState title="No findings provided" text="The service returned no findings for this report."/> : <div className="finding-list">{findings.map((finding, index) => <Finding key={finding.id || `${finding.rule_id}-${index}`} finding={finding} index={index}/>)}</div>}</section>
    <div className="report-bottom-nav"><Link to={`/applications/${id}/audit`} className="quiet-link"><Icon name="audit" size={17}/>Audit workspace</Link><Link to={`/applications/${id}/documents`} className="quiet-link">Document centre <Icon name="arrow" size={16}/></Link></div>
  </div>
}
const findingContext = {
  pass: 'This configured check returned a pass within its own scope. It does not establish document authenticity or decide application approval.',
  flagged: 'A potential discrepancy needs reviewer attention. A flag is not proof of fraud or an approval decision.',
  missing: 'An item expected by this configured check is absent, so the check cannot be treated as satisfied.',
  unresolved: 'The service could not complete this check reliably. Treat it as open for review, not as passed.',
  not_applicable: 'This check is marked not applicable. That status does not mean the document or claim was verified.',
}

function displayFieldName(value) { return value?.replaceAll('_', ' ') }

function Finding({ finding, index }) {
  const evidence = finding.evidence
  const status = finding.status || 'unresolved'
  const source = finding.document_name || (finding.document_id ? `Document ID ${finding.document_id}` : 'Application-level finding; no document was specified')
  const page = evidence?.page_number != null ? ` · Page ${evidence.page_number}` : ''
  const reason = finding.reason?.trim()
  const nextAction = finding.next_action?.trim()

  return <article className={`finding finding-${status}`}>
    <div className="finding-index">{String(index + 1).padStart(2, '0')}</div>
    <div className="finding-main">
      <header className="finding-title-row"><div><span className="finding-kicker">What was found · {String(status).replaceAll('_', ' ')}</span><h3>{finding.title || 'Finding title not provided by the validation service'}</h3></div><Status value={status}/></header>
      <section className="finding-explanation" aria-label="Finding explanation">
        <div className="finding-detail checked-detail"><h4>What was checked</h4><p>{finding.rule_id ? <>Configured check <code>{finding.rule_id}</code>. The validation service did not provide a plain-language check description.</> : 'The validation service did not provide a check reference or description.'}</p></div>
        <div className="finding-detail impact-detail"><h4>Why it matters</h4><p>{findingContext[status] || 'Review the returned reason and evidence before deciding how to proceed.'}</p></div>
        <div className="finding-detail reason-detail"><h4>Why this result was returned</h4><p>{reason || 'Reason not provided by the validation service.'}</p></div>
      </section>
      <section className="finding-evidence" aria-label="Evidence">
        <div className="finding-evidence-heading"><h4>What the document shows</h4><span>{source}{page}</span></div>
        {evidence ? <>
          {(evidence.field || evidence.value != null) && <div className="evidence-value"><span>{displayFieldName(evidence.field) || 'Extracted value'}</span><b>{evidence.value != null ? String(evidence.value) : 'Value unavailable'}</b></div>}
          {evidence.text ? <blockquote>{evidence.text}</blockquote> : <p className="evidence-unavailable">Supporting text snippet unavailable.</p>}
        </> : <p className="evidence-unavailable">Evidence unavailable. The validation service returned no supporting evidence for this finding.</p>}
      </section>
      <section className="finding-next-action"><h4>Recommended next action</h4><p>{nextAction || 'Recommended next action was not provided by the validation service.'}</p></section>
    </div>
  </article>
}

function NotFound() { return <div className="not-found"><span className="eyebrow">404 · PAGE NOT FOUND</span><h1>This page isn’t<br/><em>in the file.</em></h1><ButtonLink to="/" icon="arrow">Return to overview</ButtonLink></div> }

export default function App() {
  return <><CustomCursor/><Shell><Routes><Route path="/" element={<Overview/>}/><Route path="/documents" element={<DocumentEntry/>}/><Route path="/applications/new" element={<CreateApplication/>}/><Route path="/applications/:id/documents" element={<ApplicationDocumentCentre/>}/><Route path="/applications/:id/audit" element={<AuditWorkspace/>}/><Route path="/applications/:id/report" element={<ValidationReport/>}/><Route path="*" element={<NotFound/>}/></Routes></Shell></>
}

function CustomCursor() {
  const cursorRef = useRef(null)
  useEffect(() => {
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)')
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (!finePointer.matches || reducedMotion.matches) return undefined
    let visible = false
    let previousPointer = null
    const element = cursorRef.current
    const onMove = (event) => {
      if (event.pointerType !== 'mouse') return
      const target = event.target instanceof Element ? event.target : null
      const native = target?.closest('input, textarea, select, [contenteditable="true"], .dropzone, .browse-button, p, h1, h2, h3, h4, blockquote, code, td, th, li')
      const selectingText = window.getSelection()?.type === 'Range'
      const useNativeCursor = !!native || selectingText
      const interactive = target?.closest('a, button, .application-row, .received-item, .checklist-item, .workflow-check-row, .finding, .finding-evidence')
      element.style.transform = `translate3d(${event.clientX - 2}px, ${event.clientY - 1}px, 0)`
      if (previousPointer) {
        const dx = Math.max(-10, Math.min(10, previousPointer.x - event.clientX))
        const dy = Math.max(-10, Math.min(10, previousPointer.y - event.clientY))
        const angle = Math.atan2(event.clientY - previousPointer.y, event.clientX - previousPointer.x) * (180 / Math.PI)
        element.style.setProperty('--cursor-echo-x', `${dx}px`)
        element.style.setProperty('--cursor-echo-y', `${dy}px`)
        element.style.setProperty('--cursor-bearing', `${angle}deg`)
      }
      previousPointer = { x: event.clientX, y: event.clientY }
      if (useNativeCursor) { element.classList.remove('cursor-visible'); visible = false }
      else if (!visible) { element.classList.add('cursor-visible'); visible = true }
      element.classList.toggle('cursor-interactive', !!interactive && !useNativeCursor)
      element.classList.toggle('cursor-nav', !!target?.closest('.nav-item') && !useNativeCursor)
      element.classList.toggle('cursor-action', !!target?.closest('button, .button') && !useNativeCursor)
      element.classList.toggle('cursor-row', !!target?.closest('.application-row, .document-entry-row') && !useNativeCursor)
      element.classList.toggle('cursor-document', !!target?.closest('.received-item, .checklist-item, .workflow-check-row, .finding, .finding-evidence') && !useNativeCursor)
    }
    const onDown = (event) => {
      const target = event.target instanceof Element ? event.target : null
      const native = target?.closest('input, textarea, select, [contenteditable="true"], .dropzone, .browse-button, p, h1, h2, h3, h4, blockquote, code, td, th, li')
      if (event.pointerType === 'mouse' && !native && target?.closest('a, button, .application-row, .document-entry-row, .received-item, .checklist-item, .workflow-check-row')) element.classList.add('cursor-pressed')
    }
    const onUp = () => element.classList.remove('cursor-pressed')
    const hide = () => { element.classList.remove('cursor-visible', 'cursor-interactive', 'cursor-nav', 'cursor-action', 'cursor-row', 'cursor-document', 'cursor-pressed'); visible = false }
    const reveal = () => { if (visible) element.classList.add('cursor-visible') }
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    window.addEventListener('pointerleave', hide)
    window.addEventListener('pointerenter', reveal)
    window.addEventListener('blur', hide)
    return () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerdown', onDown); window.removeEventListener('pointerup', onUp); window.removeEventListener('pointercancel', onUp); window.removeEventListener('pointerleave', hide); window.removeEventListener('pointerenter', reveal); window.removeEventListener('blur', hide) }
  }, [])
  return <div className="custom-cursor" ref={cursorRef} aria-hidden="true"><svg className="cursor-echo" viewBox="0 0 48 48"><path d="M4 3 8 34 17 26 24 43 30 40 23 23 41 22 4 3Z"/></svg><svg className="cursor-glyph" viewBox="0 0 48 48"><path className="cursor-shadow" d="M4 3 8 34 17 26 24 43 30 40 23 23 41 22 4 3Z"/><path className="cursor-shape" d="M3 2 7 32 16 24 23 41 28 38 21 21 39 20 3 2Z"/><path className="cursor-leading-edge" d="M3 2 39 20 21 21"/><path className="cursor-tail" d="M15 36c-3 4-7 7-12 9"/><path className="cursor-scan-mark" d="M28 8h8m-4-4v8"/></svg></div>
}
