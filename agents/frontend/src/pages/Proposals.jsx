import { useCallback, useEffect, useMemo, useState } from 'react'
import Header from '../components/Header'
import AppNav from '../components/AppNav'
import { COLORS } from '../config/theme'
import { listAgents } from '../services/agents'
import { acceptProposal, listProposals, rejectProposal } from '../services/proposals'

/**
 * Global queue of pending proposals across all agents. Accept commits the
 * change (memory version row OR new skill); Reject marks resolved.
 */
export default function Proposals() {
  const [proposals, setProposals] = useState([])
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const [props, ags] = await Promise.all([
        listProposals({ status: 'pending' }),
        listAgents(),
      ])
      setProposals(props)
      setAgents(ags)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const agentsById = useMemo(() => {
    const map = new Map()
    for (const a of agents) map.set(a.id, a)
    return map
  }, [agents])

  const handleAccept = useCallback(async (id) => {
    setBusyId(id)
    setError(null)
    try {
      await acceptProposal(id)
      setProposals((prev) => prev.filter((p) => p.id !== id))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [])

  const handleReject = useCallback(async (id) => {
    setBusyId(id)
    setError(null)
    try {
      await rejectProposal(id)
      setProposals((prev) => prev.filter((p) => p.id !== id))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [])

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: COLORS.bgBase,
      color: COLORS.textPrimary,
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Header />
      <AppNav pendingProposalsCount={proposals.length} />

      <main style={{
        flex: 1,
        padding: '32px 16px 48px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
        <div style={{ width: '100%', maxWidth: 760 }}>
          <div style={{ marginBottom: 24 }}>
            <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', margin: 0 }}>
              Pending proposals
            </h1>
            <p style={{ fontSize: 13, color: COLORS.textMuted, margin: '6px 0 0' }}>
              {loading
                ? 'Loading…'
                : proposals.length === 0
                  ? 'Nothing waiting on review.'
                  : `${proposals.length} ${proposals.length === 1 ? 'proposal' : 'proposals'} from the self-improving loop.`}
            </p>
          </div>

          {error && (
            <div style={{
              padding: '10px 12px',
              borderRadius: 8,
              backgroundColor: COLORS.bgCard,
              border: `1px solid ${COLORS.danger}`,
              color: COLORS.danger,
              fontSize: 13,
              marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {proposals.map((p) => (
              <QueueRow
                key={p.id}
                proposal={p}
                agent={agentsById.get(p.agent_id)}
                onAccept={() => handleAccept(p.id)}
                onReject={() => handleReject(p.id)}
                isBusy={busyId === p.id}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}

function QueueRow({ proposal, agent, onAccept, onReject, isBusy }) {
  const isMemory = proposal.kind === 'memory_update'
  const accentColor = isMemory ? COLORS.accentLight : COLORS.success

  return (
    <div style={{
      padding: 16,
      borderRadius: 12,
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${accentColor}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{
          fontSize: 10,
          fontWeight: 700,
          color: '#0F0F1A',
          background: accentColor,
          padding: '2px 8px',
          borderRadius: 999,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}>
          {isMemory ? 'Memory' : 'Skill'}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600 }}>
          {agent ? agent.name : `Agent #${proposal.agent_id}`}
        </span>
        <span style={{ fontSize: 11, color: COLORS.textDim, marginLeft: 'auto' }}>
          {formatDate(proposal.created_at)}
        </span>
      </div>

      {proposal.rationale && (
        <div style={{ fontSize: 13, color: COLORS.textMuted, marginBottom: 10 }}>
          {proposal.rationale}
        </div>
      )}

      <details style={{ fontSize: 12, color: COLORS.textMuted }}>
        <summary style={{ cursor: 'pointer', userSelect: 'none' }}>Show proposed content</summary>
        <pre style={{
          marginTop: 8,
          padding: 10,
          backgroundColor: COLORS.bgBase,
          border: `1px solid ${COLORS.borderSoft}`,
          borderRadius: 6,
          fontSize: 11,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontFamily: 'ui-monospace, monospace',
          maxHeight: 320,
          overflowY: 'auto',
        }}>
          {isMemory ? proposal.proposed_snapshot : tryFormatJson(proposal.proposed_snapshot)}
        </pre>
      </details>

      {isMemory && proposal.current_snapshot && (
        <details style={{ fontSize: 12, color: COLORS.textMuted, marginTop: 6 }}>
          <summary style={{ cursor: 'pointer', userSelect: 'none' }}>Compare against current memory</summary>
          <pre style={{
            marginTop: 8,
            padding: 10,
            backgroundColor: COLORS.bgBase,
            border: `1px solid ${COLORS.borderSoft}`,
            borderRadius: 6,
            fontSize: 11,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'ui-monospace, monospace',
            maxHeight: 320,
            overflowY: 'auto',
            opacity: 0.7,
          }}>
            {proposal.current_snapshot}
          </pre>
        </details>
      )}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
        <button onClick={onReject} disabled={isBusy} style={{
          padding: '6px 14px',
          borderRadius: 6,
          border: `1px solid ${COLORS.border}`,
          background: 'transparent',
          color: COLORS.textMuted,
          fontSize: 12,
          cursor: isBusy ? 'default' : 'pointer',
        }}>Reject</button>
        <button onClick={onAccept} disabled={isBusy} style={{
          padding: '6px 14px',
          borderRadius: 6,
          border: 'none',
          background: accentColor,
          color: '#0F0F1A',
          fontWeight: 600,
          fontSize: 12,
          cursor: isBusy ? 'default' : 'pointer',
        }}>Accept</button>
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

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}
