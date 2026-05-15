import api from './api'

export async function getUserProfile() {
  const res = await api('/api/user-profile')
  if (!res.ok) throw new Error(`Failed to load user profile: ${res.status}`)
  return res.json()
}

export async function updateUserProfile(body) {
  const res = await api('/api/user-profile', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Failed to update user profile: ${res.status}`)
  return res.json()
}
