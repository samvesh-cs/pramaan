import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  if (isAuthenticated) {
    return <Navigate to={from} replace />
  }

  const handleLogin = async (e) => {
    e?.preventDefault()
    if (!email || !password) {
      setErrorMessage('Please enter both email address and password.')
      return
    }

    setIsSubmitting(true)
    setErrorMessage('')
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setErrorMessage(err.message || 'Login failed. Please verify credentials.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const fillQuickCredentials = (demoEmail, demoPassword) => {
    setEmail(demoEmail)
    setPassword(demoPassword)
    setErrorMessage('')
  }

  return (
    <main className="auth-page">
      <div className="auth-panel">
        <div className="auth-heading">
          <div className="auth-brand-mark" aria-hidden="true">P</div>
          <div className="eyebrow">SIH 2026 · PS 26261</div>
          <h1>Sign in to Pramaan</h1>
          <p>
            Document Scrutiny and Compliance Verification Workspace
          </p>
        </div>

        {errorMessage && (
          <div
            className="auth-error"
            role="alert"
          >
            <strong>Authentication failed: </strong>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="auth-form">
          <div>
            <label htmlFor="login-email">
              Institutional or Reviewer Email
            </label>
            <input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              className="auth-input"
              placeholder="e.g. principal@college.edu.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              className="auth-input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="auth-submit"
          >
            {isSubmitting ? (
              <>
                <span className="spinner spinner-light" /> Signing in…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="auth-demo">
          <div className="auth-demo-label">
            Quick Demo Credentials
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() =>
                fillQuickCredentials(
                  'institution@engg-college.edu.in',
                  'College@Pramaan2026'
                )
              }
              className="auth-demo-button"
            >
              <div className="font-semibold text-[#233c3f]"> Institution</div>
              <div className="truncate text-[10px] text-[#697670]">College Demo</div>
            </button>
            <button
              type="button"
              onClick={() =>
                fillQuickCredentials(
                  'reviewer@aicte-india.org',
                  'Reviewer@AICTE2026'
                )
              }
              className="auth-demo-button"
            >
              <div className="font-semibold text-[#233c3f]"> AICTE Reviewer</div>
              <div className="truncate text-[10px] text-[#697670]">Scrutiny Desk</div>
            </button>
          </div>
        </div>

        <div className="auth-register-link">
          <span>New institutional applicant? </span>
          <Link
            to="/register"
            className="auth-link"
          >
            Register your institution
          </Link>
        </div>
      </div>
    </main>
  )
}
