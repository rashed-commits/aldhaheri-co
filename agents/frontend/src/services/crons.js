import api from './api'

export async function listCrons() {
  const res = await api('/api/crons')
  if (!res.ok) throw new Error(`Failed to list crons: ${res.status}`)
  return res.json()
}

export async function parseCronNL(nlSchedule) {
  const res = await api('/api/crons/parse', {
    method: 'POST',
    body: JSON.stringify({ nl_schedule: nlSchedule }),
  })
  if (!res.ok) throw new Error(`Failed to parse schedule: ${res.status}`)
  return res.json() // { cron_expr, explanation }
}

export async function createCron(body) {
  const res = await api('/api/crons', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await safeError(res)
    throw new Error(detail || `Create failed: ${res.status}`)
  }
  return res.json()
}

export async function patchCron(id, body) {
  const res = await api(`/api/crons/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await safeError(res)
    throw new Error(detail || `Update failed: ${res.status}`)
  }
  return res.json()
}

export async function deleteCron(id) {
  const res = await api(`/api/crons/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`)
}

export async function runCronNow(id) {
  const res = await api(`/api/crons/${id}/run-now`, { method: 'POST' })
  if (!res.ok) throw new Error(`Run-now failed: ${res.status}`)
  return res.json()
}

export async function listCronRuns(id) {
  const res = await api(`/api/crons/${id}/runs`)
  if (!res.ok) throw new Error(`Failed to load runs: ${res.status}`)
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
