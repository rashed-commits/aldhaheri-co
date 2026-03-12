import api from './api'

export async function getAuthStatus() {
  const res = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/auth/status`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
  return res.json()
}

export async function loginWithPassword(username, password) {
  const res = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
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
