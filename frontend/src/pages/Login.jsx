import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../services/auth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [lockoutUntil, setLockoutUntil] = useState(null)
  const [countdown, setCountdown] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      navigate('/dashboard', { replace: true })
    }
  }, [navigate])

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

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (lockoutUntil) return
    setError('')
    setLoading(true)
    try {
      const data = await login(username, password)
      localStorage.setItem('token', data.token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const res = err.response?.data
      if (res?.lockout_until) {
        setLockoutUntil(res.lockout_until)
        setError(res.detail || 'Account locked. Please wait.')
      } else {
        setError(res?.detail || 'Login failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

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
          Sign in to your command center
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
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

          {error && (
            <div className="text-sm rounded-lg px-3 py-2" style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#EF4444' }}>
              {error}
              {countdown > 0 && (
                <span className="block mt-1 font-mono">
                  Try again in {countdown}s
                </span>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !!lockoutUntil}
            className="w-full py-2.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              backgroundColor: '#7C3AED',
              color: '#F1F5F9',
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
