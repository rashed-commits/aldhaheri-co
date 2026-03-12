const API_URL = import.meta.env.VITE_API_URL || ''

async function api(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (res.status === 401) {
    window.location.href = 'https://aldhaheri.co'
    return null
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  if (res.status === 204) return null
  return res.json()
}

export async function fetchTransactions(page = 1, perPage = 50) {
  return api(`/api/transactions?page=${page}&per_page=${perPage}`)
}

export async function fetchSummary() {
  return api('/api/transactions/summary')
}

export async function updateTransaction(id, data) {
  return api(`/api/transactions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteTransaction(id) {
  return api(`/api/transactions/${id}`, {
    method: 'DELETE',
  })
}

export default api
