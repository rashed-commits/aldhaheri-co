import api from './api'

export async function routeToAgent(message) {
  const res = await api('/api/manager/route', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw new Error(`Manager route failed: ${res.status}`)
  return res.json()
}
