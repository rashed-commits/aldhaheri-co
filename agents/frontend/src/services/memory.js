import api from './api'

export async function getMemory(agentId) {
  const res = await api(`/api/agents/${agentId}/memory`)
  if (!res.ok) throw new Error(`Failed to load memory: ${res.status}`)
  return res.json()
}

export async function listMemoryVersions(agentId) {
  const res = await api(`/api/agents/${agentId}/memory/versions`)
  if (!res.ok) throw new Error(`Failed to load memory versions: ${res.status}`)
  return res.json()
}

export async function updateMemory(agentId, content_md) {
  const res = await api(`/api/agents/${agentId}/memory`, {
    method: 'PUT',
    body: JSON.stringify({ content_md }),
  })
  if (!res.ok) throw new Error(`Failed to update memory: ${res.status}`)
  return res.json()
}
