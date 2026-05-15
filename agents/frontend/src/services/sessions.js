import api from './api'

export async function listSessions({ agentId, limit = 100 } = {}) {
  const params = new URLSearchParams()
  if (agentId != null) params.set('agent_id', String(agentId))
  if (limit != null) params.set('limit', String(limit))
  const res = await api(`/api/sessions?${params.toString()}`)
  if (!res.ok) throw new Error(`Failed to list sessions: ${res.status}`)
  return res.json()
}

export async function getSession(id) {
  const res = await api(`/api/sessions/${id}`)
  if (!res.ok) throw new Error(`Failed to get session ${id}: ${res.status}`)
  return res.json()
}

export async function searchSessions({ q, agentId, limit = 30 } = {}) {
  const params = new URLSearchParams()
  params.set('q', q)
  if (agentId != null) params.set('agent_id', String(agentId))
  if (limit != null) params.set('limit', String(limit))
  const res = await api(`/api/sessions/search?${params.toString()}`)
  if (!res.ok) {
    const detail = await safeError(res)
    throw new Error(detail || `Search failed: ${res.status}`)
  }
  return res.json()
}

async function safeError(res) {
  try {
    const data = await res.json()
    return data.detail || null
  } catch {
    return null
  }
}
