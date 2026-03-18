import { useState, useEffect } from 'react'
import Header from '../components/Header'
import ProjectNav from '../components/ProjectNav'
import { getCredentials, deleteCredential, startRegistration } from '../services/webauthn'
import { getTotpStatus, setupTotp, verifyTotpSetup, disableTotp } from '../services/totp'

export default function Settings() {
  const [credentials, setCredentials] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [registering, setRegistering] = useState(false)
  const [deleting, setDeleting] = useState(null)

  // TOTP state
  const [totpEnabled, setTotpEnabled] = useState(false)
  const [totpLoading, setTotpLoading] = useState(true)
  const [totpSetupData, setTotpSetupData] = useState(null) // { qr_code, secret }
  const [totpCode, setTotpCode] = useState('')
  const [totpVerifying, setTotpVerifying] = useState(false)
  const [totpDisabling, setTotpDisabling] = useState(false)

  const loadCredentials = async () => {
    try {
      const creds = await getCredentials()
      setCredentials(creds)
    } catch {
      setError('Failed to load passkeys')
    } finally {
      setLoading(false)
    }
  }

  const loadTotpStatus = async () => {
    try {
      const status = await getTotpStatus()
      setTotpEnabled(status.enabled)
    } catch {
      // TOTP status check failed — assume not enabled
    } finally {
      setTotpLoading(false)
    }
  }

  useEffect(() => {
    loadCredentials()
    loadTotpStatus()
  }, [])

  const handleAddPasskey = async () => {
    setError('')
    setSuccess('')
    setRegistering(true)
    try {
      await startRegistration()
      setSuccess('Passkey registered successfully')
      await loadCredentials()
    } catch (err) {
      setError(err.message || 'Failed to register passkey')
    } finally {
      setRegistering(false)
    }
  }

  const handleDeletePasskey = async (id) => {
    if (credentials.length <= 1) return
    setError('')
    setSuccess('')
    setDeleting(id)
    try {
      await deleteCredential(id)
      setSuccess('Passkey deleted')
      await loadCredentials()
    } catch (err) {
      setError(err.message || 'Failed to delete passkey')
    } finally {
      setDeleting(null)
    }
  }

  const handleTotpSetup = async () => {
    setError('')
    setSuccess('')
    try {
      const data = await setupTotp()
      setTotpSetupData(data)
    } catch (err) {
      setError(err.message || 'Failed to set up TOTP')
    }
  }

  const handleTotpVerify = async (e) => {
    e.preventDefault()
    setError('')
    setTotpVerifying(true)
    try {
      await verifyTotpSetup(totpCode)
      setTotpEnabled(true)
      setTotpSetupData(null)
      setTotpCode('')
      setSuccess('Authenticator enabled successfully')
    } catch (err) {
      setError(err.message || 'Invalid code')
    } finally {
      setTotpVerifying(false)
    }
  }

  const handleTotpDisable = async () => {
    setError('')
    setSuccess('')
    setTotpDisabling(true)
    try {
      await disableTotp()
      setTotpEnabled(false)
      setSuccess('Authenticator disabled')
    } catch (err) {
      setError(err.message || 'Failed to disable TOTP')
    } finally {
      setTotpDisabling(false)
    }
  }

  const handleCancelTotpSetup = () => {
    setTotpSetupData(null)
    setTotpCode('')
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#0F0F1A' }}>
      <ProjectNav />
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h2 className="text-xl font-bold mb-6" style={{ color: '#F1F5F9' }}>
          Security Settings
        </h2>

        {/* Messages */}
        {error && (
          <div className="text-sm rounded-lg px-3 py-2 mb-4" style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#EF4444' }}>
            {error}
          </div>
        )}
        {success && (
          <div className="text-sm rounded-lg px-3 py-2 mb-4" style={{ backgroundColor: 'rgba(16,185,129,0.1)', color: '#10B981' }}>
            {success}
          </div>
        )}

        {/* Registered Passkeys */}
        <div className="rounded-xl p-6 mb-6" style={{ backgroundColor: '#1A1A2E', border: '1px solid #2D2D4E' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold" style={{ color: '#F1F5F9' }}>
              Registered Passkeys
            </h3>
            <button
              onClick={handleAddPasskey}
              disabled={registering}
              className="text-sm px-4 py-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: '#7C3AED', color: '#F1F5F9' }}
            >
              {registering ? 'Registering...' : 'Add Passkey'}
            </button>
          </div>

          {loading ? (
            <div className="text-sm py-4 text-center" style={{ color: '#94A3B8' }}>
              Loading passkeys...
            </div>
          ) : credentials.length === 0 ? (
            <div className="text-sm py-4 text-center" style={{ color: '#94A3B8' }}>
              No passkeys registered. Add one to enable passwordless login.
            </div>
          ) : (
            <div className="space-y-3">
              {credentials.map((cred) => (
                <div
                  key={cred.id}
                  className="flex items-center justify-between rounded-lg px-4 py-3"
                  style={{ backgroundColor: '#0F0F1A', border: '1px solid #2D2D4E' }}
                >
                  <div>
                    <div className="text-sm font-medium" style={{ color: '#F1F5F9' }}>
                      {cred.name || 'Passkey'}
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#94A3B8' }}>
                      Created: {formatDate(cred.created_at)}
                      {cred.last_used && ` | Last used: ${formatDate(cred.last_used)}`}
                    </div>
                  </div>
                  <div className="relative group">
                    <button
                      onClick={() => handleDeletePasskey(cred.id)}
                      disabled={credentials.length <= 1 || deleting === cred.id}
                      className="text-xs px-3 py-1 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                      style={{ color: '#EF4444', border: '1px solid #EF4444', background: 'none' }}
                    >
                      {deleting === cred.id ? 'Deleting...' : 'Delete'}
                    </button>
                    {credentials.length <= 1 && (
                      <div
                        className="absolute right-0 bottom-full mb-2 px-2 py-1 rounded text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
                        style={{ backgroundColor: '#2D2D4E', color: '#F1F5F9' }}
                      >
                        Must keep at least one passkey
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Two-Factor Authentication (TOTP) */}
        <div className="rounded-xl p-6 mb-6" style={{ backgroundColor: '#1A1A2E', border: '1px solid #2D2D4E' }}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold" style={{ color: '#F1F5F9' }}>
              Authenticator App
            </h3>
            {!totpLoading && totpEnabled && (
              <span className="text-xs px-2 py-1 rounded-full" style={{ backgroundColor: 'rgba(16,185,129,0.15)', color: '#10B981' }}>
                Enabled
              </span>
            )}
          </div>

          {totpLoading ? (
            <div className="text-sm py-4 text-center" style={{ color: '#94A3B8' }}>
              Loading...
            </div>
          ) : totpEnabled && !totpSetupData ? (
            <div className="space-y-3">
              <p className="text-sm" style={{ color: '#94A3B8' }}>
                Two-factor authentication is active. You will be prompted for a code from your authenticator app when logging in with a password.
              </p>
              <button
                onClick={handleTotpDisable}
                disabled={totpDisabling}
                className="text-xs px-3 py-1.5 rounded transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ color: '#EF4444', border: '1px solid #EF4444', background: 'none' }}
              >
                {totpDisabling ? 'Disabling...' : 'Disable Authenticator'}
              </button>
            </div>
          ) : totpSetupData ? (
            <div className="space-y-4">
              <p className="text-sm" style={{ color: '#94A3B8' }}>
                Scan this QR code with Microsoft Authenticator or any TOTP app:
              </p>
              <div className="flex justify-center py-2">
                <img
                  src={`data:image/png;base64,${totpSetupData.qr_code}`}
                  alt="TOTP QR Code"
                  className="rounded-lg"
                  style={{ width: 200, height: 200 }}
                />
              </div>
              <div className="text-center">
                <p className="text-xs mb-1" style={{ color: '#94A3B8' }}>
                  Or enter this key manually:
                </p>
                <code
                  className="text-xs px-3 py-1.5 rounded font-mono select-all"
                  style={{ backgroundColor: '#0F0F1A', color: '#A78BFA', border: '1px solid #2D2D4E' }}
                >
                  {totpSetupData.secret}
                </code>
              </div>
              <form onSubmit={handleTotpVerify} className="space-y-3">
                <div>
                  <label className="block text-sm font-medium mb-1.5" style={{ color: '#94A3B8' }}>
                    Enter code to verify
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="000000"
                    className="w-full px-3 py-2.5 rounded-lg text-sm text-center font-mono tracking-widest outline-none transition-colors focus:ring-2"
                    style={{
                      backgroundColor: '#0F0F1A',
                      border: '1px solid #2D2D4E',
                      color: '#F1F5F9',
                      '--tw-ring-color': '#7C3AED',
                    }}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={totpVerifying || totpCode.length !== 6}
                    className="flex-1 py-2 rounded-lg text-sm font-semibold transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ backgroundColor: '#7C3AED', color: '#F1F5F9' }}
                  >
                    {totpVerifying ? 'Verifying...' : 'Enable'}
                  </button>
                  <button
                    type="button"
                    onClick={handleCancelTotpSetup}
                    className="px-4 py-2 rounded-lg text-sm transition-colors cursor-pointer"
                    style={{ color: '#94A3B8', border: '1px solid #2D2D4E', background: 'none' }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm" style={{ color: '#94A3B8' }}>
                Add an extra layer of security by requiring a code from an authenticator app (Microsoft Authenticator, Google Authenticator, etc.) when logging in.
              </p>
              <button
                onClick={handleTotpSetup}
                className="text-sm px-4 py-1.5 rounded-lg transition-colors cursor-pointer"
                style={{ backgroundColor: '#7C3AED', color: '#F1F5F9' }}
              >
                Set Up Authenticator
              </button>
            </div>
          )}
        </div>

        {/* Active Sessions */}
        <div className="rounded-xl p-6" style={{ backgroundColor: '#1A1A2E', border: '1px solid #2D2D4E' }}>
          <h3 className="text-base font-semibold mb-4" style={{ color: '#F1F5F9' }}>
            Active Sessions
          </h3>
          <div className="flex items-center gap-3 rounded-lg px-4 py-3" style={{ backgroundColor: '#0F0F1A', border: '1px solid #2D2D4E' }}>
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: '#10B981' }}
            />
            <div>
              <div className="text-sm font-medium" style={{ color: '#F1F5F9' }}>
                Current Session
              </div>
              <div className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>
                Active now
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
