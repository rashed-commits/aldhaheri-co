import { useCallback, useEffect, useState } from 'react'
import { COLORS } from '../config/theme'
import { listCronRuns } from '../services/crons'

/**
 * Per-cron run log. Mounts when the user expands a cron card. Shows up to
 * 50 most-recent runs with status, timing, output excerpt, and error.
 */
export default function CronRunHistory({ cronId }) {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const data = await listCronRuns(cronId)
      setRuns(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [cronId])

  useEffect(() => {
    reload()
  }, [reload])

  if (loading) {
    return <div style={{ fontSize: 12, color: COLORS.textDim, padding: '8px 0' }}>Loading runs…</div>
  }

  if (error) {
    return <div style={{ fontSize: 12, color: COLORS.danger, padding: '8px 0' }}>{error}</div>
  }

  if (runs.length === 0) {
    return <div style={{ fontSize: 12, color: COLORS.textDim, padding: '8px 0' }}>No runs yet.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
      {runs.map((r) => (
        <RunRow key={r.id} run={r} />
      ))}
    </div>
  )
}

function RunRow({ run }) {
  const statusColor = {
    success: COLORS.success,
    failed: COLORS.danger,
    running: COLORS.warning,
  }[run.status] || COLORS.textMuted

  return (
    <div style={{
      padding: '8px 10px',
      borderRadius: 8,
      backgroundColor: COLORS.bgBase,
      border: `1px solid ${COLORS.borderSoft}`,
      fontSize: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontSize: 10,
          fontWeight: 700,
          color: '#0F0F1A',
          background: statusColor,
          padding: '1px 7px',
          borderRadius: 999,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}>
          {run.status}
        </span>
        <span style={{ color: COLORS.textMuted }}>{formatDate(run.started_at)}</span>
        {run.finished_at && (
          <span style={{ color: COLORS.textDim, marginLeft: 'auto' }}>
            {formatDuration(run.started_at, run.finished_at)}
          </span>
        )}
      </div>
      {run.error && (
        <div style={{ marginTop: 6, color: COLORS.danger, fontSize: 11, wordBreak: 'break-word' }}>
          {run.error}
        </div>
      )}
      {run.output_excerpt && (
        <details style={{ marginTop: 6 }}>
          <summary style={{ cursor: 'pointer', color: COLORS.accentLight, fontSize: 11, userSelect: 'none' }}>
            Show output excerpt
          </summary>
          <pre style={{
            marginTop: 6,
            padding: 8,
            backgroundColor: COLORS.bgCard,
            border: `1px solid ${COLORS.borderSoft}`,
            borderRadius: 6,
            fontSize: 11,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'ui-monospace, monospace',
            maxHeight: 220,
            overflowY: 'auto',
            color: COLORS.textPrimary,
          }}>{run.output_excerpt}</pre>
        </details>
      )}
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

function formatDuration(startIso, endIso) {
  try {
    const start = new Date(startIso).getTime()
    const end = new Date(endIso).getTime()
    const ms = end - start
    if (ms < 1000) return `${ms}ms`
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60_000).toFixed(1)}m`
  } catch {
    return ''
  }
}
