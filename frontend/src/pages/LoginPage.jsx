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
    <div className="flex min-h-[calc(100vh-140px)] items-center justify-center px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-[#263b42]/20 bg-[#fbf9f4] p-7 shadow-xl shadow-stone-900/5 sm:p-9">
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#263b42]/15 bg-white/70 px-3 py-1 text-[11px] font-semibold tracking-wider text-[#6b7771]">
            <span>AICTE PS 26261</span>
            <span>·</span>
            <span>SECURE ACCESS</span>
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-[#1c3035]">Sign in to Pramaan</h1>
          <p className="mt-1 text-xs text-[#5d6a64]">
            Document Scrutiny and Compliance Verification Workspace
          </p>
        </div>

        {errorMessage && (
          <div
            className="mb-5 rounded-lg border border-red-200 bg-red-50/80 p-3 text-xs text-red-800"
            role="alert"
          >
            <strong>Authentication failed: </strong>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#324948]" htmlFor="login-email">
              Institutional or Reviewer Email
            </label>
            <input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              className="mt-1 block w-full rounded-lg border border-[#263b42]/20 bg-white px-3 py-2 text-sm text-[#1f3338] placeholder-stone-400 focus:border-[#2f5e5c] focus:outline-none focus:ring-1 focus:ring-[#2f5e5c]"
              placeholder="e.g. principal@college.edu.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#324948]" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              className="mt-1 block w-full rounded-lg border border-[#263b42]/20 bg-white px-3 py-2 text-sm text-[#1f3338] placeholder-stone-400 focus:border-[#2f5e5c] focus:outline-none focus:ring-1 focus:ring-[#2f5e5c]"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[#274548] py-2.5 text-sm font-semibold text-white transition hover:bg-[#1f373a] disabled:opacity-60"
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

        <div className="mt-6 border-t border-[#263b42]/10 pt-5">
          <div className="text-center text-[11px] font-semibold uppercase tracking-wider text-[#79847e]">
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
              className="rounded-lg border border-[#263b42]/15 bg-white/80 p-2 text-left text-xs transition hover:border-[#2f5e5c] hover:bg-white"
            >
              <div className="font-semibold text-[#233c3f]">🎓 Institution</div>
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
              className="rounded-lg border border-[#263b42]/15 bg-white/80 p-2 text-left text-xs transition hover:border-[#2f5e5c] hover:bg-white"
            >
              <div className="font-semibold text-[#233c3f]">⚖️ AICTE Reviewer</div>
              <div className="truncate text-[10px] text-[#697670]">Scrutiny Desk</div>
            </button>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-[#5f6d67]">
          <span>New institutional applicant? </span>
          <Link
            to="/register"
            className="font-semibold text-[#274548] underline underline-offset-2 hover:text-[#192d30]"
          >
            Register your institution
          </Link>
        </div>
      </div>
    </div>
  )
}
