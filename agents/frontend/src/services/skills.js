import api from './api'

export async function listSkills(agentId) {
  const res = await api(`/api/agents/${agentId}/skills`)
  if (!res.ok) throw new Error(`Failed to list skills: ${res.status}`)
  return res.json()
}

export async function createSkill(agentId, body) {
  const res = await api(`/api/agents/${agentId}/skills`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await safeError(res)
    throw new Error(`Failed to create skill: ${detail || res.status}`)
  }
  return res.json()
}

export async function patchSkill(skillId, body) {
  const res = await api(`/api/skills/${skillId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await safeError(res)
    throw new Error(`Failed to update skill: ${detail || res.status}`)
  }
  return res.json()
}

export async function deleteSkill(skillId) {
  const res = await api(`/api/skills/${skillId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete skill: ${res.status}`)
}

async function safeError(res) {
  try {
    const data = await res.json()
    return data.detail || null
  } catch {
    return null
  }
}
