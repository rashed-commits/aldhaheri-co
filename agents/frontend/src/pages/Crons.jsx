import { useCallback, useEffect, useMemo, useState } from 'react'
import Header from '../components/Header'
import AppNav from '../components/AppNav'
import CronForm from '../components/CronForm'
import CronRunHistory from '../components/CronRunHistory'
import { COLORS } from '../config/theme'
import { listAgents } from '../services/agents'
import {
  createCron,
  deleteCron,
  listCrons,
  patchCron,
  runCronNow,
} from '../services/crons'

const POLL_INTERVAL_MS = 5000

export default function Crons() {
  const [crons, setCrons] = useState([])
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null) // 'new' or cron.id
  const [busyId, setBusyId] = useState(null)
  const [expandedRunsId, setExpandedRunsId] = useState(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const [crs, ags] = await Promise.all([listCrons(), listAgents()])
      setCrons(crs)
      setAgents(ags)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
    const handle = setInterval(reload, POLL_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [reload])

  const agentsById = useMemo(() => {
    const m = new Map()
    for (const a of agents) m.set(a.id, a)
    return m
  }, [agents])

  const handleCreate = useCallback(async (form) => {
    setBusyId('new')
    setError(null)
    try {
      await createCron(form)
      setEditingId(null)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [reload])

  const handlePatch = useCallback(async (id, form) => {
    setBusyId(id)
    setError(null)
    try {
      await patchCron(id, form)
      setEditingId(null)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [reload])

  const handleToggleEnabled = useCallback(async (cron) => {
    setBusyId(cron.id)
    setError(null)
    try {
      await patchCron(cron.id, { enabled: !cron.enabled })
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [reload])

  const handleDelete = useCallback(async (id) => {
    if (!confirm('Delete this cron? This soft-deletes it and unregisters it from the scheduler.')) return
    setBusyId(id)
    setError(null)
    try {
      await deleteCron(id)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [reload])

  const handleRunNow = useCallback(async (id) => {
    setBusyId(id)
    setError(null)
    try {
      await runCronNow(id)
      // Surface in the runs panel
      setExpandedRunsId(id)
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
      <AppNav />

      <main style={{
        flex: 1,
        padding: '32px 16px 48px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
        <div style={{ width: '100%', maxWidth: 820 }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', margin: 0 }}>
                Crons
              </h1>
              <p style={{ fontSize: 13, color: COLORS.textMuted, margin: '6px 0 0' }}>
                {loading
                  ? 'Loading…'
                  : crons.length === 0
                    ? 'No scheduled jobs yet.'
                    : `${crons.length} scheduled ${crons.length === 1 ? 'job' : 'jobs'}.`}
              </p>
            </div>
            {editingId !== 'new' && agents.length > 0 && (
              <button onClick={() => setEditingId('new')} style={primaryBtn(false)}>
                + Add cron
              </button>
            )}
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

          {editingId === 'new' && (
            <CronForm
              agents={agents}
              onSubmit={handleCreate}
              onCancel={() => setEditingId(null)}
              isPending={busyId === 'new'}
              submitLabel="Create cron"
            />
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {crons.map((c) => (
              editingId === c.id ? (
                <CronForm
                  key={c.id}
                  agents={agents}
                  initial={c}
                  onSubmit={(form) => handlePatch(c.id, form)}
                  onCancel={() => setEditingId(null)}
                  isPending={busyId === c.id}
                  submitLabel="Save changes"
                />
              ) : (
                <CronCard
                  key={c.id}
                  cron={c}
                  agent={agentsById.get(c.agent_id)}
                  onEdit={() => setEditingId(c.id)}
                  onDelete={() => handleDelete(c.id)}
                  onToggleEnabled={() => handleToggleEnabled(c)}
                  onRunNow={() => handleRunNow(c.id)}
                  onToggleRuns={() => setExpandedRunsId(expandedRunsId === c.id ? null : c.id)}
                  runsExpanded={expandedRunsId === c.id}
                  isBusy={busyId === c.id}
                />
              )
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}

function CronCard({
  cron,
  agent,
  onEdit,
  onDelete,
  onToggleEnabled,
  onRunNow,
  onToggleRuns,
  runsExpanded,
  isBusy,
}) {
  return (
    <div style={{
      padding: 16,
      borderRadius: 12,
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${cron.enabled ? COLORS.border : COLORS.borderSoft}`,
      opacity: cron.enabled ? 1 : 0.65,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>{cron.name}</span>
            <span style={{
              fontSize: 10, fontWeight: 700, color: '#0F0F1A',
              padding: '2px 7px', borderRadius: 999,
              background: cron.enabled ? COLORS.success : COLORS.textDim,
              letterSpacing: '0.04em', textTransform: 'uppercase',
            }}>
              {cron.enabled ? 'enabled' : 'paused'}
            </span>
            <span style={{ fontSize: 11, color: COLORS.textMuted }}>
              → {agent ? agent.name : `agent #${cron.agent_id}`}
            </span>
          </div>

          <div style={{ marginTop: 8, fontSize: 12, color: COLORS.textMuted, display: 'flex', flexWrap: 'wrap', gap: 14 }}>
            <span>{cron.nl_schedule}</span>
            <code style={{ color: COLORS.accentLight, fontSize: 11 }}>{cron.cron_expr}</code>
            <span style={{ fontSize: 11, color: COLORS.textDim }}>
              output: {cron.output_target}
            </span>
          </div>

          <div style={{ marginTop: 8, fontSize: 12, color: COLORS.textMuted, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {truncate(cron.prompt, 220)}
          </div>

          <div style={{ marginTop: 10, fontSize: 11, color: COLORS.textDim, display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {cron.next_run_at && <span>Next: {formatDate(cron.next_run_at)}</span>}
            {cron.last_run_at && <span>Last: {formatDate(cron.last_run_at)}</span>}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', marginTop: 12, flexWrap: 'wrap' }}>
        <button onClick={onToggleRuns} disabled={isBusy} style={iconBtn}>
          {runsExpanded ? 'Hide runs' : 'View runs'}
        </button>
        <button onClick={onRunNow} disabled={isBusy} style={iconBtn}>Run now</button>
        <button onClick={onToggleEnabled} disabled={isBusy} style={iconBtn}>
          {cron.enabled ? 'Pause' : 'Resume'}
        </button>
        <button onClick={onEdit} disabled={isBusy} style={iconBtn}>Edit</button>
        <button onClick={onDelete} disabled={isBusy} style={iconBtnDanger}>Delete</button>
      </div>

      {runsExpanded && <CronRunHistory cronId={cron.id} />}
    </div>
  )
}

function truncate(s, n) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

const primaryBtn = (disabled) => ({
  padding: '8px 16px',
  borderRadius: 8,
  border: 'none',
  background: disabled ? COLORS.border : COLORS.accent,
  color: COLORS.textPrimary,
  fontWeight: 600,
  fontSize: 13,
  cursor: disabled ? 'default' : 'pointer',
})

const iconBtn = {
  padding: '5px 11px',
  borderRadius: 6,
  border: `1px solid ${COLORS.border}`,
  background: 'transparent',
  color: COLORS.textMuted,
  fontSize: 12,
  cursor: 'pointer',
}

const iconBtnDanger = {
  ...iconBtn,
  color: COLORS.danger,
  borderColor: 'rgba(239,68,68,0.4)',
}
