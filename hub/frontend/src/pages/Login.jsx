import { useState, useEffect } from 'react'
import { getAuthStatus, loginWithPassword } from '../services/auth'
import { startAuthentication, startRegistration } from '../services/webauthn'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [authStatus, setAuthStatus] = useState(null) // null = loading
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [lockoutUntil, setLockoutUntil] = useState(null)
  const [countdown, setCountdown] = useState(0)
  const [registeringPasskey, setRegisteringPasskey] = useState(false)

  useEffect(() => {
    getAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatus({ setup_required: true, has_passkeys: false }))
  }, [])

  useEffect(() => {
    if (!lockoutUntil) return
    const interval = setInterval(() => {
      const remaining = Math.ceil((new Date(lockoutUntil) - Date.now()) / 1000)
      if (remaining <= 0) {
        setLockoutUntil(null)
        setCountdown(0)
        setError('')
        clearInterval(interval)
      } else {
        setCountdown(remaining)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [lockoutUntil])

  const handlePasswordLogin = async (e) => {
    e.preventDefault()
    if (lockoutUntil) return
    setError('')
    setLoading(true)
    try {
      await loginWithPassword(username, password)
      // If setup mode, prompt passkey registration after password login
      if (authStatus?.setup_required) {
        setRegisteringPasskey(true)
        try {
          await startRegistration()
        } catch {
          // Passkey registration is optional during setup — continue to dashboard
        }
      }
      window.location.href = '/dashboard'
    } catch (err) {
      if (err.message.includes('429') || err.message.includes('locked') || err.message.includes('Too many')) {
        setLockoutUntil(new Date(Date.now() + 60000).toISOString())
        setError('Too many login attempts. Please wait.')
      } else {
        setError(err.message || 'Login failed. Please try again.')
      }
    } finally {
      setLoading(false)
      setRegisteringPasskey(false)
    }
  }

  const handlePasskeyLogin = async () => {
    setError('')
    setLoading(true)
    try {
      await startAuthentication()
      window.location.href = '/dashboard'
    } catch (err) {
      setError(err.message || 'Passkey authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  // Loading state while checking auth status
  if (authStatus === null) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: '#0F0F1A' }}>
        <div style={{ color: '#94A3B8' }}>Loading...</div>
      </div>
    )
  }

  const isSetup = authStatus.setup_required
  const hasPasskeys = authStatus.has_passkeys

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: '#0F0F1A' }}>
      <div
        className="w-full max-w-sm rounded-xl p-8"
        style={{ backgroundColor: '#1A1A2E', border: '1px solid #2D2D4E' }}
      >
        <h1 className="text-2xl font-bold text-center mb-2" style={{ color: '#F1F5F9' }}>
          aldhaheri.co
        </h1>
        <p className="text-center mb-8" style={{ color: '#94A3B8' }}>
          {isSetup ? 'Set up your account' : 'Sign in to your command center'}
        </p>

        {/* Passkey registration prompt after setup login */}
        {registeringPasskey && (
          <div className="text-sm rounded-lg px-3 py-2 mb-4" style={{ backgroundColor: 'rgba(124,58,237,0.1)', color: '#A78BFA' }}>
            Follow the browser prompt to register your passkey...
          </div>
        )}

        {/* Passkey login button — shown when passkeys exist and not in setup mode */}
        {hasPasskeys && !isSetup && !showPasswordForm && (
          <div className="space-y-4">
            <button
              onClick={handlePasskeyLogin}
              disabled={loading}
              className="w-full py-3 rounded-lg text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              style={{
                backgroundColor: '#7C3AED',
                color: '#F1F5F9',
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 18v3c0 .6.4 1 1 1h4v-3h3v-3h2l1.4-1.4a6.5 6.5 0 1 0-4-4Z" />
                <circle cx="16.5" cy="7.5" r=".5" fill="currentColor" />
              </svg>
              {loading ? 'Authenticating...' : 'Sign in with Passkey'}
            </button>

            <div className="text-center">
              <button
                onClick={() => setShowPasswordForm(true)}
                className="text-xs transition-colors cursor-pointer"
                style={{ color: '#94A3B8', background: 'none', border: 'none' }}
              >
                Use password instead
              </button>
            </div>
          </div>
        )}

        {/* Password form — shown in setup mode, or when user clicks "Use password instead" */}
        {(isSetup || !hasPasskeys || showPasswordForm) && (
          <form onSubmit={handlePasswordLogin} className="space-y-5">
            {showPasswordForm && (
              <div className="text-center mb-2">
                <button
                  type="button"
                  onClick={() => setShowPasswordForm(false)}
                  className="text-xs transition-colors cursor-pointer"
                  style={{ color: '#7C3AED', background: 'none', border: 'none' }}
                >
                  Back to passkey login
                </button>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: '#94A3B8' }}>
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-colors focus:ring-2"
                style={{
                  backgroundColor: '#0F0F1A',
                  border: '1px solid #2D2D4E',
                  color: '#F1F5F9',
                  '--tw-ring-color': '#7C3AED',
                }}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: '#94A3B8' }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-colors focus:ring-2"
                style={{
                  backgroundColor: '#0F0F1A',
                  border: '1px solid #2D2D4E',
                  color: '#F1F5F9',
                  '--tw-ring-color': '#7C3AED',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !!lockoutUntil}
              className="w-full py-2.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                backgroundColor: '#7C3AED',
                color: '#F1F5F9',
              }}
            >
              {loading ? 'Signing in...' : isSetup ? 'Set Up Account' : 'Sign In'}
            </button>
          </form>
        )}

        {/* Error display */}
        {error && (
          <div className="text-sm rounded-lg px-3 py-2 mt-4" style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#EF4444' }}>
            {error}
            {countdown > 0 && (
              <span className="block mt-1 font-mono">
                Try again in {countdown}s
              </span>
            )}
          </div>
        )}

        {isSetup && (
          <p className="text-xs text-center mt-6" style={{ color: '#94A3B8' }}>
            After signing in, you will be prompted to register a passkey for future logins.
          </p>
        )}
      </div>
    </div>
  )
}
