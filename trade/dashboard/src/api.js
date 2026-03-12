const API_URL = import.meta.env.VITE_API_URL || ''

async function api(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (res.status === 401) {
    window.location.href = 'https://aldhaheri.co'
    return null
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export default api
