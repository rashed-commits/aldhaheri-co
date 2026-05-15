import api from './api'

/**
 * Stream a chat turn with an agent. Async generator that yields parsed SSE
 * events as they arrive: `{ type, data }`. Caller decides what to do with
 * `session`, `chunk`, `actions`, `end`, `error`. The generator returns
 * naturally when the server closes the stream.
 */
export async function* streamChat({ agentId, message, sessionId, taskFraming }) {
  const res = await api(`/api/agents/${agentId}/chat`, {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId ?? null,
      task_framing: taskFraming ?? '',
    }),
  })
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      if (buffer.trim()) {
        const evt = parseSSEEvent(buffer)
        if (evt) yield evt
      }
      break
    }
    buffer += decoder.decode(value, { stream: true })

    let sepIdx
    while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
      const eventStr = buffer.slice(0, sepIdx)
      buffer = buffer.slice(sepIdx + 2)
      const evt = parseSSEEvent(eventStr)
      if (evt) yield evt
    }
  }
}

function parseSSEEvent(eventStr) {
  let type = 'message'
  const dataLines = []
  for (const line of eventStr.split('\n')) {
    if (line.startsWith('event: ')) type = line.slice(7).trim()
    else if (line.startsWith('data: ')) dataLines.push(line.slice(6))
  }
  if (dataLines.length === 0) return null
  try {
    return { type, data: JSON.parse(dataLines.join('\n')) }
  } catch {
    return { type, data: { raw: dataLines.join('\n') } }
  }
}
