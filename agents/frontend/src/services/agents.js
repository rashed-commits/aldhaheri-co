import api from './api'

export async function listAgents() {
  const res = await api('/api/agents')
  if (!res.ok) throw new Error(`Failed to list agents: ${res.status}`)
  return res.json()
}

export async function getAgent(id) {
  const res = await api(`/api/agents/${id}`)
  if (!res.ok) throw new Error(`Failed to get agent ${id}: ${res.status}`)
  return res.json()
}

export async function createAgent({ name, specialization = '', soul = '' }) {
  const res = await api('/api/agents', {
    method: 'POST',
    body: JSON.stringify({ name, specialization, soul }),
  })
  if (!res.ok) throw new Error(`Failed to create agent: ${res.status}`)
  return res.json()
}

export async function patchAgent(id, fields) {
  const res = await api(`/api/agents/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  })
  if (!res.ok) throw new Error(`Failed to patch agent ${id}: ${res.status}`)
  return res.json()
}

export async function deleteAgent(id) {
  const res = await api(`/api/agents/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete agent ${id}: ${res.status}`)
}
