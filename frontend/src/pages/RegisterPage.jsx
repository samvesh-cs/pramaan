import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function RegisterPage() {
  const { register, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const [institutionName, setInstitutionName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  const handleRegister = async (e) => {
    e?.preventDefault()
    setErrorMessage('')

    if (!institutionName.trim() || !email.trim() || !password) {
      setErrorMessage('Please fill in all required fields.')
      return
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await register(email, password, institutionName.trim())
      navigate('/', { replace: true })
    } catch (err) {
      setErrorMessage(err.message || 'Registration failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-140px)] items-center justify-center px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-[#263b42]/20 bg-[#fbf9f4] p-7 shadow-xl shadow-stone-900/5 sm:p-9">
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#263b42]/15 bg-white/70 px-3 py-1 text-[11px] font-semibold tracking-wider text-[#6b7771]">
            <span>INSTITUTION REGISTRATION</span>
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-[#1c3035]">Create Applicant Account</h1>
          <p className="mt-1 text-xs text-[#5d6a64]">
            Register your educational institution to submit and validate AICTE applications.
          </p>
        </div>

        {errorMessage && (
          <div
            className="mb-5 rounded-lg border border-red-200 bg-red-50/80 p-3 text-xs text-red-800"
            role="alert"
          >
            <strong>Registration error: </strong>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#324948]" htmlFor="reg-inst-name">
              Full Legal Institution Name
            </label>
            <input
              id="reg-inst-name"
              type="text"
              required
              className="mt-1 block w-full rounded-lg border border-[#263b42]/20 bg-white px-3 py-2 text-sm text-[#1f3338] placeholder-stone-400 focus:border-[#2f5e5c] focus:outline-none focus:ring-1 focus:ring-[#2f5e5c]"
              placeholder="e.g. Delhi College of Engineering & Technology"
              value={institutionName}
              onChange={(e) => setInstitutionName(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#324948]" htmlFor="reg-email">
              Official Institutional Email Address
            </label>
            <input
              id="reg-email"
              type="email"
              required
              autoComplete="email"
              className="mt-1 block w-full rounded-lg border border-[#263b42]/20 bg-white px-3 py-2 text-sm text-[#1f3338] placeholder-stone-400 focus:border-[#2f5e5c] focus:outline-none focus:ring-1 focus:ring-[#2f5e5c]"
              placeholder="e.g. principal@dcet.edu.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#324948]" htmlFor="reg-password">
              Password (min 8 characters)
            </label>
            <input
              id="reg-password"
              type="password"
              required
              autoComplete="new-password"
              className="mt-1 block w-full rounded-lg border border-[#263b42]/20 bg-white px-3 py-2 text-sm text-[#1f3338] placeholder-stone-400 focus:border-[#2f5e5c] focus:outline-none focus:ring-1 focus:ring-[#2f5e5c]"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#324948]" htmlFor="reg-confirm-password">
              Confirm Password
            </label>
            <input
              id="reg-confirm-password"
              type="password"
              required
              autoComplete="new-password"
              className="mt-1 block w-full rounded-lg border border-[#263b42]/20 bg-white px-3 py-2 text-sm text-[#1f3338] placeholder-stone-400 focus:border-[#2f5e5c] focus:outline-none focus:ring-1 focus:ring-[#2f5e5c]"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>

          <div className="rounded-lg border border-amber-200/80 bg-amber-50/70 p-3 text-[11px] leading-relaxed text-amber-900">
            ℹ️ <b>Reviewer Notice:</b> AICTE scrutiny reviewers cannot self-register. Reviewer credentials are setup and provisioned by the AICTE authority desk.
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[#274548] py-2.5 text-sm font-semibold text-white transition hover:bg-[#1f373a] disabled:opacity-60"
          >
            {isSubmitting ? (
              <>
                <span className="spinner spinner-light" /> Registering…
              </>
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-[#5f6d67]">
          <span>Already have an account? </span>
          <Link
            to="/login"
            className="font-semibold text-[#274548] underline underline-offset-2 hover:text-[#192d30]"
          >
            Sign in here
          </Link>
        </div>
      </div>
    </div>
  )
}
