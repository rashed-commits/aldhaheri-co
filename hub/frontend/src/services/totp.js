import api from './api'

export async function getTotpStatus() {
  const res = await api('/api/auth/totp/status')
  return res.json()
}

export async function setupTotp() {
  const res = await api('/api/auth/totp/setup', { method: 'POST' })
  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.detail || 'Failed to set up TOTP')
  }
  return res.json()
}

export async function verifyTotpSetup(code) {
  const res = await api('/api/auth/totp/verify', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.detail || 'Invalid code')
  }
  return res.json()
}

export async function disableTotp() {
  const res = await api('/api/auth/totp/disable', { method: 'DELETE' })
  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.detail || 'Failed to disable TOTP')
  }
  return res.json()
}
