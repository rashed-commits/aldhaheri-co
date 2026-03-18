import { useState, useEffect, useRef } from 'react'
import { getAuthStatus, loginWithPassword, loginWithTotp } from '../services/auth'
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

  // TOTP state
  const [totpRequired, setTotpRequired] = useState(false)
  const [totpToken, setTotpToken] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const totpInputRef = useRef(null)

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

  useEffect(() => {
    if (totpRequired && totpInputRef.current) {
      totpInputRef.current.focus()
    }
  }, [totpRequired])

  const handlePasswordLogin = async (e) => {
    e.preventDefault()
    if (lockoutUntil) return
    setError('')
    setLoading(true)
    try {
      const result = await loginWithPassword(username, password)

      // Check if TOTP verification is needed
      if (result.totp_required) {
        setTotpRequired(true)
        setTotpToken(result.totp_token)
        setLoading(false)
        return
      }

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
        setLockoutUntil(new Date(Date.now() + 1800000).toISOString())
        setError('Too many login attempts. Please wait.')
      } else {
        setError(err.message || 'Login failed. Please try again.')
      }
    } finally {
      setLoading(false)
      setRegisteringPasskey(false)
    }
  }

  const handleTotpSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await loginWithTotp(totpToken, totpCode)
      window.location.href = '/dashboard'
    } catch (err) {
      if (err.message.includes('429') || err.message.includes('locked') || err.message.includes('Too many')) {
        setLockoutUntil(new Date(Date.now() + 1800000).toISOString())
        setError('Too many attempts. Please wait.')
      } else if (err.message.includes('expired')) {
        setError('Session expired. Please log in again.')
        setTotpRequired(false)
        setTotpToken('')
        setTotpCode('')
      } else {
        setError(err.message || 'Invalid code. Please try again.')
      }
    } finally {
      setLoading(false)
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

  const handleTotpBack = () => {
    setTotpRequired(false)
    setTotpToken('')
    setTotpCode('')
    setError('')
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
        {isSetup && (
          <p className="text-center mb-8" style={{ color: '#94A3B8' }}>
            Set up your account
          </p>
        )}
        {!isSetup && <div className="mb-8" />}

        {/* Passkey registration prompt after setup login */}
        {registeringPasskey && (
          <div className="text-sm rounded-lg px-3 py-2 mb-4" style={{ backgroundColor: 'rgba(124,58,237,0.1)', color: '#A78BFA' }}>
            Follow the browser prompt to register your passkey...
          </div>
        )}

        {/* TOTP verification step */}
        {totpRequired && (
          <form onSubmit={handleTotpSubmit} className="space-y-5">
            <div className="text-center mb-2">
              <div className="flex items-center justify-center gap-2 mb-3" style={{ color: '#A78BFA' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span className="text-sm font-medium">Two-Factor Authentication</span>
              </div>
              <p className="text-xs" style={{ color: '#94A3B8' }}>
                Enter the 6-digit code from your authenticator app
              </p>
            </div>

            <div>
              <input
                ref={totpInputRef}
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="w-full px-3 py-3 rounded-lg text-center text-lg font-mono tracking-widest outline-none transition-colors focus:ring-2"
                style={{
                  backgroundColor: '#0F0F1A',
                  border: '1px solid #2D2D4E',
                  color: '#F1F5F9',
                  '--tw-ring-color': '#7C3AED',
                  letterSpacing: '0.3em',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading || totpCode.length !== 6}
              className="w-full py-2.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                backgroundColor: '#7C3AED',
                color: '#F1F5F9',
              }}
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={handleTotpBack}
                className="text-xs transition-colors cursor-pointer"
                style={{ color: '#94A3B8', background: 'none', border: 'none' }}
              >
                Back to login
              </button>
            </div>
          </form>
        )}

        {/* Passkey login button — shown when passkeys exist and not in setup mode */}
        {!totpRequired && hasPasskeys && !isSetup && !showPasswordForm && (
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
        {!totpRequired && (isSetup || !hasPasskeys || showPasswordForm) && (
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

        {isSetup && !totpRequired && (
          <p className="text-xs text-center mt-6" style={{ color: '#94A3B8' }}>
            After signing in, you will be prompted to register a passkey for future logins.
          </p>
        )}
      </div>
    </div>
  )
}
