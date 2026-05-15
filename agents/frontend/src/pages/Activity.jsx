import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Header from '../components/Header'
import AppNav from '../components/AppNav'
import { COLORS } from '../config/theme'
import { listAgents } from '../services/agents'
import { getSession, listSessions, searchSessions } from '../services/sessions'

const POLL_INTERVAL_MS = 8000
const SEARCH_DEBOUNCE_MS = 350

/**
 * Activity / sessions browser. Two modes:
 *   - Browse: chronological list of sessions, click to expand transcript.
 *   - Search: FTS5 query across every indexed turn; hits link back into the
 *             underlying session and expand to the matching turn.
 *
 * Live-refreshes every 8s so new sessions appear without a reload.
 */
export default function Activity() {
  const [agents, setAgents] = useState([])
  const [sessions, setSessions] = useState([])
  const [hits, setHits] = useState(null) // null = not searching; array = results

  const [agentFilter, setAgentFilter] = useState('all') // 'all' or agent id (number)
  const [triggerFilter, setTriggerFilter] = useState('all')
  const [searchQ, setSearchQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const [expanded, setExpanded] = useState(null) // session id
  const [transcripts, setTranscripts] = useState({}) // sessionId -> session row

  const searchTimer = useRef(null)

  const loadList = useCallback(async () => {
    setError(null)
    try {
      const opts = agentFilter === 'all'
        ? { limit: 200 }
        : { agentId: Number(agentFilter), limit: 200 }
      const [sess, ags] = await Promise.all([
        listSessions(opts),
        listAgents(),
      ])
      setSessions(sess)
      setAgents(ags)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [agentFilter])

  useEffect(() => {
    loadList()
    const handle = setInterval(loadList, POLL_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [loadList])

  // Debounced FTS5 search
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!searchQ.trim()) {
      setHits(null)
      setSearching(false)
      return
    }
    setSearching(true)
    searchTimer.current = setTimeout(async () => {
      try {
        const opts = { q: searchQ.trim(), limit: 50 }
        if (agentFilter !== 'all') opts.agentId = Number(agentFilter)
        const data = await searchSessions(opts)
        setHits(data)
        setError(null)
      } catch (err) {
        setError(err.message)
        setHits([])
      } finally {
        setSearching(false)
      }
    }, SEARCH_DEBOUNCE_MS)
    return () => searchTimer.current && clearTimeout(searchTimer.current)
  }, [searchQ, agentFilter])

  const agentsById = useMemo(() => {
    const m = new Map()
    for (const a of agents) m.set(a.id, a)
    return m
  }, [agents])

  const filteredSessions = useMemo(() => {
    if (triggerFilter === 'all') return sessions
    return sessions.filter((s) => s.trigger === triggerFilter)
  }, [sessions, triggerFilter])

  const handleExpand = useCallback(async (sessionId) => {
    if (expanded === sessionId) {
      setExpanded(null)
      return
    }
    setExpanded(sessionId)
    if (!transcripts[sessionId]) {
      try {
        const data = await getSession(sessionId)
        setTranscripts((prev) => ({ ...prev, [sessionId]: data }))
      } catch (err) {
        setError(err.message)
      }
    }
  }, [expanded, transcripts])

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: COLORS.bgBase,
      color: COLORS.textPrimary,
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Header />
      <AppNav />

      <main style={{
        flex: 1,
        padding: '32px 16px 48px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
        <div style={{ width: '100%', maxWidth: 880 }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', margin: 0 }}>
            Activity
          </h1>
          <p style={{ fontSize: 13, color: COLORS.textMuted, margin: '6px 0 24px' }}>
            Every chat, delegation, and cron run in the office. Refreshes every {POLL_INTERVAL_MS / 1000}s.
          </p>

          {/* Filter strip */}
          <div style={filterRowStyle}>
            <input
              type="text"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Search across every turn… (FTS5 syntax: AND / NOT / quoted phrases / prefix*)"
              style={searchInputStyle}
            />

            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              style={selectStyle}
            >
              <option value="all">All agents</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>

            <select
              value={triggerFilter}
              onChange={(e) => setTriggerFilter(e.target.value)}
              style={selectStyle}
              disabled={hits !== null}
              title={hits !== null ? 'Trigger filter is hidden during search' : undefined}
            >
              <option value="all">All triggers</option>
              <option value="chat">Chat</option>
              <option value="delegated">Delegated</option>
              <option value="cron">Cron</option>
              <option value="manager_route">Manager route</option>
            </select>
          </div>

          {error && (
            <div style={errorBox}>{error}</div>
          )}

          {/* Search results */}
          {hits !== null && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 10 }}>
                {searching ? 'Searching…' : `${hits.length} ${hits.length === 1 ? 'match' : 'matches'} for "${searchQ}"`}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {hits.map((hit, i) => (
                  <SearchHit
                    key={`${hit.session_id}-${hit.turn_index}-${i}`}
                    hit={hit}
                    agent={agentsById.get(hit.agent_id)}
                    expanded={expanded === hit.session_id}
                    transcript={transcripts[hit.session_id]}
                    onClick={() => handleExpand(hit.session_id)}
                  />
                ))}
                {!searching && hits.length === 0 && (
                  <div style={{ fontSize: 13, color: COLORS.textDim, padding: '20px 0', textAlign: 'center' }}>
                    Nothing matched.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Browse list */}
          {hits === null && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {loading && filteredSessions.length === 0 && (
                <div style={{ fontSize: 13, color: COLORS.textDim, padding: '20px 0', textAlign: 'center' }}>
                  Loading…
                </div>
              )}
              {!loading && filteredSessions.length === 0 && (
                <div style={{ fontSize: 13, color: COLORS.textDim, padding: '20px 0', textAlign: 'center' }}>
                  No sessions match these filters.
                </div>
              )}
              {filteredSessions.map((s) => (
                <SessionCard
                  key={s.id}
                  session={s}
                  agent={agentsById.get(s.agent_id)}
                  expanded={expanded === s.id}
                  transcript={transcripts[s.id]}
                  onClick={() => handleExpand(s.id)}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function SessionCard({ session, agent, expanded, transcript, onClick }) {
  const turns = parseTurns(session.transcript_json)
  const tokens = (session.token_input || 0) + (session.token_output || 0)
  return (
    <div style={cardStyle(expanded)}>
      <button onClick={onClick} style={cardHeaderBtnStyle}>
        <span style={triggerBadge(session.trigger)}>{session.trigger}</span>
        <span style={{ color: COLORS.textPrimary, fontWeight: 600, fontSize: 14 }}>
          {agent ? agent.name : `Agent #${session.agent_id}`}
        </span>
        <span style={{ color: COLORS.textMuted, fontSize: 12 }}>
          {turns.length} {turns.length === 1 ? 'turn' : 'turns'}
        </span>
        <span style={{ color: COLORS.textDim, fontSize: 11 }}>
          {tokens > 0 ? `${formatTokens(tokens)} tok` : ''}
        </span>
        <span style={{ color: COLORS.textDim, fontSize: 11, marginLeft: 'auto' }}>
          {formatDate(session.started_at)}
        </span>
        <span style={{ color: COLORS.textDim }}>{expanded ? '▾' : '▸'}</span>
      </button>

      {expanded && (
        <div style={{ padding: '12px 14px 14px', borderTop: `1px solid ${COLORS.borderSoft}` }}>
          <TranscriptView turns={transcript ? parseTurns(transcript.transcript_json) : turns} />
        </div>
      )}
    </div>
  )
}

function SearchHit({ hit, agent, expanded, transcript, onClick }) {
  return (
    <div style={cardStyle(expanded)}>
      <button onClick={onClick} style={cardHeaderBtnStyle}>
        <span style={{ ...triggerBadge('match'), background: COLORS.warning }}>match</span>
        <span style={{ color: COLORS.textPrimary, fontWeight: 600, fontSize: 14 }}>
          {agent ? agent.name : `Agent #${hit.agent_id}`}
        </span>
        <span style={{ fontSize: 11, color: COLORS.textMuted }}>
          session #{hit.session_id} · turn {hit.turn_index} · {hit.role}
        </span>
        <span style={{ color: COLORS.textDim, fontSize: 11, marginLeft: 'auto' }}>
          rank {hit.rank.toFixed(2)}
        </span>
        <span style={{ color: COLORS.textDim }}>{expanded ? '▾' : '▸'}</span>
      </button>

      <div style={{ padding: '0 14px 12px', fontSize: 13, color: COLORS.textMuted, lineHeight: 1.55 }}>
        <HighlightedSnippet text={hit.content_snippet} />
      </div>

      {expanded && transcript && (
        <div style={{ padding: '0 14px 14px', borderTop: `1px solid ${COLORS.borderSoft}` }}>
          <div style={{ marginTop: 12 }}>
            <TranscriptView turns={parseTurns(transcript.transcript_json)} highlightTurnIndex={hit.turn_index} />
          </div>
        </div>
      )}
    </div>
  )
}

function TranscriptView({ turns, highlightTurnIndex = null }) {
  if (!turns || turns.length === 0) {
    return <div style={{ fontSize: 12, color: COLORS.textDim }}>(empty)</div>
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {turns.map((t, i) => (
        <TurnLine key={i} turn={t} index={i} highlighted={i === highlightTurnIndex} />
      ))}
    </div>
  )
}

function TurnLine({ turn, index, highlighted }) {
  const isUser = turn.role === 'user'
  const content = isUser ? turn.content : stripActionBlocks(turn.content)
  return (
    <div style={{
      padding: '8px 12px',
      borderRadius: 8,
      background: highlighted ? 'rgba(245,158,11,0.08)' : (isUser ? 'rgba(124,58,237,0.10)' : COLORS.bgBase),
      border: `1px solid ${highlighted ? COLORS.warning : (isUser ? 'rgba(124,58,237,0.3)' : COLORS.borderSoft)}`,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: isUser ? COLORS.accentLight : COLORS.textMuted,
        marginBottom: 6,
      }}>
        <span>{isUser ? 'User' : 'Assistant'}</span>
        <span style={{ color: COLORS.textDim, fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>
          turn {index}{turn.ts ? ` · ${formatDate(turn.ts)}` : ''}
        </span>
      </div>
      {isUser ? (
        <div style={{ fontSize: 13, color: COLORS.textPrimary, whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>
          {content}
        </div>
      ) : (
        <div className="markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}

function HighlightedSnippet({ text }) {
  // FTS5 snippet() wraps matches in [brackets]. Convert to <mark>.
  const parts = []
  let buffer = ''
  let inMark = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '[' && !inMark) {
      if (buffer) parts.push({ mark: false, text: buffer })
      buffer = ''
      inMark = true
    } else if (ch === ']' && inMark) {
      if (buffer) parts.push({ mark: true, text: buffer })
      buffer = ''
      inMark = false
    } else {
      buffer += ch
    }
  }
  if (buffer) parts.push({ mark: inMark, text: buffer })
  return (
    <span>
      {parts.map((p, i) => p.mark ? (
        <mark key={i} style={{
          background: 'rgba(245,158,11,0.25)',
          color: COLORS.warning,
          padding: '0 3px',
          borderRadius: 3,
        }}>{p.text}</mark>
      ) : (
        <span key={i}>{p.text}</span>
      ))}
    </span>
  )
}

// ── helpers ────────────────────────────────────────────────────────────────

function parseTurns(jsonStr) {
  try { return JSON.parse(jsonStr || '[]') } catch { return [] }
}

function stripActionBlocks(text) {
  return (text || '').replace(/<action>[\s\S]*?<\/action>/g, '').trim()
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

function formatTokens(n) {
  if (n < 1000) return String(n)
  if (n < 100_000) return `${(n / 1000).toFixed(1)}K`
  return `${Math.round(n / 1000)}K`
}

function triggerBadge(trigger) {
  const colors = {
    chat: COLORS.accent,
    delegated: COLORS.accentLight,
    cron: COLORS.warning,
    manager_route: COLORS.textMuted,
    match: COLORS.warning,
  }
  return {
    fontSize: 10,
    fontWeight: 700,
    padding: '2px 7px',
    borderRadius: 999,
    background: colors[trigger] || COLORS.textMuted,
    color: '#0F0F1A',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  }
}

const cardStyle = (expanded) => ({
  borderRadius: 12,
  backgroundColor: COLORS.bgCard,
  border: `1px solid ${expanded ? COLORS.accent : COLORS.border}`,
  overflow: 'hidden',
  transition: 'border-color 0.15s',
})

const cardHeaderBtnStyle = {
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '12px 14px',
  background: 'transparent',
  border: 'none',
  color: 'inherit',
  cursor: 'pointer',
  textAlign: 'left',
}

const filterRowStyle = {
  display: 'flex',
  gap: 8,
  marginBottom: 16,
  flexWrap: 'wrap',
  alignItems: 'center',
}

const searchInputStyle = {
  flex: '1 1 320px',
  padding: '8px 12px',
  borderRadius: 8,
  border: `1px solid ${COLORS.border}`,
  background: COLORS.bgCard,
  color: COLORS.textPrimary,
  fontSize: 13,
  outline: 'none',
  fontFamily: 'inherit',
}

const selectStyle = {
  padding: '8px 10px',
  borderRadius: 8,
  border: `1px solid ${COLORS.border}`,
  background: COLORS.bgCard,
  color: COLORS.textPrimary,
  fontSize: 13,
  outline: 'none',
  fontFamily: 'inherit',
}

const errorBox = {
  padding: '10px 12px',
  borderRadius: 8,
  backgroundColor: COLORS.bgCard,
  border: `1px solid ${COLORS.danger}`,
  color: COLORS.danger,
  fontSize: 13,
  marginBottom: 16,
}
