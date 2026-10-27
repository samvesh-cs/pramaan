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
    <main className="auth-page">
      <div className="auth-panel">
        <div className="auth-heading">
          <div className="auth-brand-mark" aria-hidden="true">P</div>
          <div className="eyebrow">INSTITUTION REGISTRATION</div>
          <h1>Create Applicant Account</h1>
          <p>
            Register your educational institution to submit and validate AICTE applications.
          </p>
        </div>

        {errorMessage && (
          <div
            className="auth-error"
            role="alert"
          >
            <strong>Registration error: </strong>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleRegister} className="auth-form">
          <div>
            <label htmlFor="reg-inst-name">
              Full Legal Institution Name
            </label>
            <input
              id="reg-inst-name"
              type="text"
              required
              className="auth-input"
              placeholder="e.g. Delhi College of Engineering & Technology"
              value={institutionName}
              onChange={(e) => setInstitutionName(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="reg-email">
              Official Institutional Email Address
            </label>
            <input
              id="reg-email"
              type="email"
              required
              autoComplete="email"
              className="auth-input"
              placeholder="e.g. principal@dcet.edu.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="reg-password">
              Password (min 8 characters)
            </label>
            <input
              id="reg-password"
              type="password"
              required
              autoComplete="new-password"
              className="auth-input"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div>
            <label htmlFor="reg-confirm-password">
              Confirm Password
            </label>
            <input
              id="reg-confirm-password"
              type="password"
              required
              autoComplete="new-password"
              className="auth-input"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>

          <div className="auth-notice">
            <b>Reviewer access</b> AICTE scrutiny reviewers cannot self-register. Reviewer credentials are provisioned by the AICTE authority desk.
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="auth-submit"
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

        <div className="auth-register-link">
          <span>Already have an account? </span>
          <Link
            to="/login"
            className="auth-link"
          >
            Sign in here
          </Link>
        </div>
      </div>
    </main>
  )
}
