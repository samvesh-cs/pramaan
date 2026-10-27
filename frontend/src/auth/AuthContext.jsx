import { createContext, useCallback, useEffect, useState } from 'react'
import {
  getCurrentUser,
  login as apiLogin,
  logout as apiLogout,
  refreshAuth,
  register as apiRegister,
  setAccessToken,
} from '../api'

export const AuthContext = createContext(null)

const AUTH_CHANNEL_NAME = 'pramaan_auth_sync'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  // Broadcast channel for multi-tab auth state synchronization
  useEffect(() => {
    let channel
    try {
      channel = new BroadcastChannel(AUTH_CHANNEL_NAME)
      channel.onmessage = (event) => {
        if (event.data?.type === 'LOGOUT') {
          setUser(null)
          setAccessToken(null)
        } else if (event.data?.type === 'LOGIN' && event.data?.user) {
          setUser(event.data.user)
        }
      }
    } catch {
      // BroadcastChannel not supported in environment
    }

    return () => {
      if (channel) channel.close()
    }
  }, [])

  const broadcastEvent = (type, data = {}) => {
    try {
      const channel = new BroadcastChannel(AUTH_CHANNEL_NAME)
      channel.postMessage({ type, ...data })
      channel.close()
    } catch {
      // BroadcastChannel ignore
    }
  }

  // Silent session restore on application mount
  useEffect(() => {
    let isMounted = true

    const initializeAuth = async () => {
      try {
        const refreshResult = await refreshAuth()
        if (refreshResult?.user && isMounted) {
          setUser(refreshResult.user)
        } else if (refreshResult?.access_token && isMounted) {
          const profile = await getCurrentUser()
          if (isMounted) setUser(profile)
        }
      } catch {
        if (isMounted) {
          setUser(null)
          setAccessToken(null)
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    initializeAuth()

    return () => {
      isMounted = false
    }
  }, [])

  const handleLogin = useCallback(async (email, password) => {
    setError(null)
    try {
      const result = await apiLogin(email, password)
      setUser(result.user)
      broadcastEvent('LOGIN', { user: result.user })
      return result.user
    } catch (err) {
      setError(err.message)
      throw err
    }
  }, [])

  const handleRegister = useCallback(async (email, password, institutionName) => {
    setError(null)
    try {
      const result = await apiRegister(email, password, institutionName)
      setUser(result.user)
      broadcastEvent('LOGIN', { user: result.user })
      return result.user
    } catch (err) {
      setError(err.message)
      throw err
    }
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setUser(null)
      setAccessToken(null)
      broadcastEvent('LOGOUT')
    }
  }, [])

  const value = {
    user,
    isLoading,
    error,
    isAuthenticated: !!user,
    isReviewer: user?.role === 'REVIEWER',
    isInstitution: user?.role === 'INSTITUTION',
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
