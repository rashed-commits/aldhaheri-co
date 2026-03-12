import api from './api'

export async function getAuthStatus() {
  const res = await api('/api/auth/status')
  return res.json()
}

export async function loginWithPassword(username, password) {
  const res = await api('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const data = await res.json()
    throw new Error(data.detail || 'Login failed')
  }
  return res.json()
}

export async function logout() {
  await api('/api/auth/logout', { method: 'POST' })
}

export async function verify() {
  const res = await api('/api/auth/verify')
  return res.ok
}
