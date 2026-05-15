import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { COLORS } from '../config/theme'
import SpawnApprovalCard from './SpawnApprovalCard'
import { createAgent } from '../services/agents'
import { streamChat } from '../services/chat'
import { acceptProposal, listProposals, rejectProposal } from '../services/proposals'

/**
 * Chat-tab body. Renders the transcript, streams Sonnet responses,
 * surfaces inline proposals after each turn, and (in spawn mode) renders
 * the SpawnApprovalCard until the user accepts and the agent is created.
 *
 * Wrapper/header live in AgentPanel.jsx now.
 *
 * Props:
 *   conversation:   { mode, agentId?, agent?, proposedAgent?, rationale?, initialMessage?, framing? }
 *   onAgentSpawned: (newAgent) => void   parent transitions conversation to chat mode
 *   onClose:        () => void           used by spawn-reject
 */
export default function ChatPanel({ conversation, onAgentSpawned, onClose }) {
  const agentId = conversation?.agentId ?? null
  const isSpawnMode = conversation?.mode === 'spawn' && !agentId

  const [sessionId, setSessionId] = useState(null)
  const [turns, setTurns] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState(null)
  const [pendingProposals, setPendingProposals] = useState([])
  const [input, setInput] = useState('')
  const [spawnPending, setSpawnPending] = useState(false)
  const scrollRef = useRef(null)
  const initialFiredRef = useRef(false)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns, pendingProposals])

  const fetchProposalsForSession = useCallback(async (sid, aid) => {
    try {
      const all = await listProposals({ status: 'pending', agentId: aid })
      const forSession = all.filter((p) => p.session_id === sid)
      if (forSession.length > 0) {
        setPendingProposals((prev) => {
          const existing = new Set(prev.map((p) => p.id))
          return [...prev, ...forSession.filter((p) => !existing.has(p.id))]
        })
      }
    } catch (err) {
      console.warn('Failed to load proposals', err)
    }
  }, [])

  const streamTurn = useCallback(async (targetId, message, taskFraming = '') => {
    if (!targetId || streaming) return
    setError(null)
    setStreaming(true)

    setTurns((prev) => [
      ...prev,
      { role: 'user', content: message },
      { role: 'assistant', content: '', streaming: true },
    ])

    let assistantText = ''
    let endedSessionId = sessionId
    let receivedActions = []

    try {
      for await (const evt of streamChat({
        agentId: targetId,
        message,
        sessionId,
        taskFraming,
      })) {
        if (evt.type === 'session') {
          setSessionId(evt.data.session_id)
          endedSessionId = evt.data.session_id
        } else if (evt.type === 'chunk') {
          assistantText += evt.data.text || ''
          setTurns((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.streaming) next[next.length - 1] = { ...last, content: assistantText }
            return next
          })
        } else if (evt.type === 'actions') {
          receivedActions = evt.data.actions || []
        } else if (evt.type === 'error') {
          setError(evt.data.message || 'Stream error')
        }
      }
    } catch (err) {
      setError(err.message || 'Network error')
    }

    setTurns((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last?.streaming) {
        next[next.length - 1] = { ...last, streaming: false, actions: receivedActions }
      }
      return next
    })
    setStreaming(false)

    if (endedSessionId && targetId) {
      setTimeout(() => fetchProposalsForSession(endedSessionId, targetId), 4000)
    }
  }, [sessionId, streaming, fetchProposalsForSession])

  // Auto-fire initial message in chat mode
  useEffect(() => {
    if (initialFiredRef.current) return
    if (conversation?.mode === 'chat' && conversation.initialMessage && agentId) {
      initialFiredRef.current = true
      streamTurn(agentId, conversation.initialMessage, conversation.framing || '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation, agentId])

  const handleSpawnAccept = useCallback(async (edited) => {
    setSpawnPending(true)
    setError(null)
    try {
      const newAgent = await createAgent(edited)
      onAgentSpawned?.(newAgent)
      initialFiredRef.current = true
      // Fire the initial message at the new agent immediately. We can't wait
      // for the conversation prop to round-trip — streamTurn takes the id
      // explicitly so the call doesn't depend on prop propagation.
      await streamTurn(newAgent.id, conversation.initialMessage || '', '')
    } catch (err) {
      setError(err.message || 'Spawn failed')
    } finally {
      setSpawnPending(false)
    }
  }, [conversation, onAgentSpawned, streamTurn])

  const handleSpawnReject = useCallback(() => onClose?.(), [onClose])

  const handleProposalAccept = useCallback(async (id) => {
    try {
      await acceptProposal(id)
      setPendingProposals((prev) => prev.filter((p) => p.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const handleProposalReject = useCallback(async (id) => {
    try {
      await rejectProposal(id)
      setPendingProposals((prev) => prev.filter((p) => p.id !== id))
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const handleInputSubmit = (e) => {
    e.preventDefault()
    const msg = input.trim()
    if (!msg || streaming || !agentId) return
    setInput('')
    streamTurn(agentId, msg)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {isSpawnMode && (
          <SpawnApprovalCard
            proposedAgent={conversation.proposedAgent}
            rationale={conversation.rationale}
            onAccept={handleSpawnAccept}
            onReject={handleSpawnReject}
            isPending={spawnPending}
          />
        )}

        {turns.map((turn, idx) => (
          <TurnRow key={idx} turn={turn} />
        ))}

        {pendingProposals.map((p) => (
          <ProposalCard
            key={p.id}
            proposal={p}
            onAccept={() => handleProposalAccept(p.id)}
            onReject={() => handleProposalReject(p.id)}
          />
        ))}

        {error && (
          <div style={{
            padding: '10px 12px',
            borderRadius: 8,
            backgroundColor: COLORS.bgCard,
            border: `1px solid ${COLORS.danger}`,
            color: COLORS.danger,
            fontSize: 12,
            marginTop: 8,
          }}>
            {error}
          </div>
        )}
      </div>

      {agentId && (
        <form onSubmit={handleInputSubmit} style={{
          padding: 12,
          borderTop: `1px solid ${COLORS.border}`,
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
        }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={streaming}
            placeholder={streaming ? 'Agent is responding…' : 'Send a message…'}
            rows={1}
            style={{
              flex: 1,
              padding: '10px 12px',
              borderRadius: 10,
              border: `1px solid ${COLORS.border}`,
              background: COLORS.bgCard,
              color: COLORS.textPrimary,
              fontSize: 14,
              outline: 'none',
              resize: 'none',
              fontFamily: 'inherit',
              maxHeight: 120,
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleInputSubmit(e)
              }
            }}
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            style={{
              padding: '10px 14px',
              borderRadius: 10,
              border: 'none',
              background: streaming || !input.trim() ? COLORS.border : COLORS.accent,
              color: COLORS.textPrimary,
              fontWeight: 600,
              fontSize: 13,
              cursor: streaming || !input.trim() ? 'default' : 'pointer',
            }}
          >
            Send
          </button>
        </form>
      )}
    </div>
  )
}

function TurnRow({ turn }) {
  const isUser = turn.role === 'user'
  const displayContent = isUser ? turn.content : stripActionBlocks(turn.content)

  return (
    <div style={{
      marginBottom: 14,
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '85%',
        padding: '10px 14px',
        borderRadius: 12,
        background: isUser ? COLORS.accent : COLORS.bgCard,
        color: COLORS.textPrimary,
        fontSize: 14,
        lineHeight: 1.55,
        whiteSpace: isUser ? 'pre-wrap' : 'normal',
        border: isUser ? 'none' : `1px solid ${COLORS.border}`,
      }}>
        {isUser ? (
          <>
            {displayContent}
            {turn.streaming && <span style={{ opacity: 0.5 }}> ▍</span>}
          </>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
            {turn.streaming && <span style={{ opacity: 0.5 }}>▍</span>}
          </div>
        )}
      </div>
      {turn.actions?.length > 0 && (
        <div style={{ width: '100%', marginTop: 8 }}>
          {turn.actions.map((action, i) => (
            <ActionPreview key={i} action={action} />
          ))}
        </div>
      )}
    </div>
  )
}

function stripActionBlocks(text) {
  let cleaned = text.replace(/<action>[\s\S]*?<\/action>/g, '')
  const partial = cleaned.lastIndexOf('<action>')
  if (partial !== -1) cleaned = cleaned.slice(0, partial)
  return cleaned
}

function ActionPreview({ action }) {
  return (
    <div style={{
      padding: '10px 12px',
      borderRadius: 8,
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${COLORS.accentLight}`,
      marginBottom: 6,
      fontSize: 12,
    }}>
      <div style={{
        color: COLORS.accentLight,
        fontWeight: 600,
        fontSize: 11,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        marginBottom: 4,
      }}>
        Action · {action.type || 'unknown'}
      </div>
      <pre style={{
        margin: 0,
        fontSize: 11,
        color: COLORS.textMuted,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        fontFamily: 'ui-monospace, monospace',
      }}>{JSON.stringify(action, null, 2)}</pre>
    </div>
  )
}

function ProposalCard({ proposal, onAccept, onReject }) {
  const isMemory = proposal.kind === 'memory_update'
  const headerColor = isMemory ? COLORS.accentLight : COLORS.success
  return (
    <div style={{
      padding: 12,
      borderRadius: 10,
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${headerColor}`,
      marginTop: 8,
      marginBottom: 8,
    }}>
      <div style={{
        fontSize: 11,
        fontWeight: 600,
        color: headerColor,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        marginBottom: 6,
      }}>
        Proposal · {isMemory ? 'Memory update' : 'New skill'}
      </div>
      {proposal.rationale && (
        <div style={{ fontSize: 12, color: COLORS.textMuted, marginBottom: 8 }}>
          {proposal.rationale}
        </div>
      )}
      <details style={{ fontSize: 12, color: COLORS.textMuted }}>
        <summary style={{ cursor: 'pointer', userSelect: 'none' }}>Show proposed content</summary>
        <pre style={{
          marginTop: 8,
          padding: 10,
          backgroundColor: COLORS.bgBase,
          borderRadius: 6,
          fontSize: 11,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontFamily: 'ui-monospace, monospace',
          maxHeight: 240,
          overflowY: 'auto',
        }}>
          {isMemory ? proposal.proposed_snapshot : tryFormatJson(proposal.proposed_snapshot)}
        </pre>
      </details>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 10 }}>
        <button
          onClick={onReject}
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            border: `1px solid ${COLORS.border}`,
            background: 'transparent',
            color: COLORS.textMuted,
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          Reject
        </button>
        <button
          onClick={onAccept}
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            border: 'none',
            background: headerColor,
            color: '#0F0F1A',
            fontWeight: 600,
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          Accept
        </button>
      </div>
    </div>
  )
}

function tryFormatJson(s) {
  try {
    return JSON.stringify(JSON.parse(s), null, 2)
  } catch {
    return s
  }
}
