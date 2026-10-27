import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

export function ProtectedRoute({ children, allowedRoles }) {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f7f5f0]">
        <div className="flex flex-col items-center gap-3 text-sm text-[#4b615d]">
          <span className="spinner" />
          <span>Verifying authentication session…</span>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="mx-auto max-w-xl py-12 text-center">
        <div className="not-found">
          <span className="eyebrow">403 · RESTRICTED ACCESS</span>
          <h1 className="text-2xl font-semibold text-[#1e3237]">Access restricted to {allowedRoles.join(' or ')} accounts.</h1>
          <p className="mt-2 text-sm text-[#5d6a65]">
            You are signed in as <b>{user.email}</b> ({user.role}). This workspace is reserved for authorized personnel.
          </p>
        </div>
      </div>
    )
  }

  return children
}
