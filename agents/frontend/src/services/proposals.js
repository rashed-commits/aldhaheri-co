import api from './api'

export async function listProposals({ status = 'pending', agentId, kind } = {}) {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (agentId != null) params.set('agent_id', String(agentId))
  if (kind) params.set('kind', kind)
  const res = await api(`/api/proposals?${params.toString()}`)
  if (!res.ok) throw new Error(`Failed to list proposals: ${res.status}`)
  return res.json()
}

export async function acceptProposal(id) {
  const res = await api(`/api/proposals/${id}/accept`, { method: 'POST' })
  if (!res.ok) throw new Error(`Accept failed: ${res.status}`)
  return res.json()
}

export async function rejectProposal(id) {
  const res = await api(`/api/proposals/${id}/reject`, { method: 'POST' })
  if (!res.ok) throw new Error(`Reject failed: ${res.status}`)
  return res.json()
}
