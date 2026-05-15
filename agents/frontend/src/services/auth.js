import api from './api'

export async function verify() {
  try {
    const res = await api('/api/auth/verify')
    if (!res.ok) return false
    const data = await res.json()
    return !!data.valid
  } catch {
    return false
  }
}
