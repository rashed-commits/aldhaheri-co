import api from './api'

export async function login(username, password) {
  const response = await api.post('/api/auth/login', { username, password })
  return response.data
}

export async function verify() {
  const response = await api.get('/api/auth/verify')
  return response.data
}

export async function logout() {
  try {
    await api.post('/api/auth/logout')
  } finally {
    localStorage.removeItem('token')
  }
}
