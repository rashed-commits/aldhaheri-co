import { useCallback, useEffect, useState } from 'react'
import { COLORS } from '../config/theme'
import { getMemory, listMemoryVersions, updateMemory } from '../services/memory'

/**
 * Per-agent MEMORY.md editor. The latest version is loaded on mount and
 * dropped into a textarea. Saving creates a new append-only version row;
 * older versions are listed below and expandable read-only.
 */
export default function MemoryPanel({ agentId }) {
  const [current, setCurrent] = useState(null)
  const [draft, setDraft] = useState('')
  const [versions, setVersions] = useState([])
  const [expandedVersionId, setExpandedVersionId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [savedAt, setSavedAt] = useState(null)

  const reload = useCallback(async () => {
    try {
      const [mem, vers] = await Promise.all([
        getMemory(agentId),
        listMemoryVersions(agentId),
      ])
      setCurrent(mem)
      setDraft(mem.content_md)
      setVersions(vers)
    } catch (err) {
      setError(err.message)
    }
  }, [agentId])

  useEffect(() => {
    reload()
  }, [reload])

  const isDirty = current && draft !== current.content_md

  const handleSave = useCallback(async () => {
    if (saving || !isDirty) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateMemory(agentId, draft)
      setCurrent(updated)
      setDraft(updated.content_md)
      setSavedAt(Date.now())
      // Reload versions to include the new one
      const vers = await listMemoryVersions(agentId)
      setVersions(vers)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }, [agentId, draft, isDirty, saving])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <div style={metaLineStyle}>
          {current
            ? <>Version {current.version} · {formatSource(current.source)} · {formatDate(current.created_at)}</>
            : 'Loading…'}
        </div>

        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          rows={18}
          style={textareaStyle}
          placeholder="# Agent memory&#10;&#10;Things this agent should remember across sessions…"
        />

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            style={primaryBtn(saving || !isDirty)}
          >
            {saving ? 'Saving…' : isDirty ? 'Save new version' : 'No changes'}
          </button>
          {savedAt && !isDirty && (
            <span style={{ fontSize: 12, color: COLORS.success }}>Saved</span>
          )}
        </div>

        {error && <div style={errorBox}>{error}</div>}

        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
            Version history
          </div>
          {versions.length === 0 ? (
            <div style={{ fontSize: 13, color: COLORS.textDim }}>No versions yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {versions.map((v) => (
                <VersionRow
                  key={v.id}
                  v={v}
                  expanded={expandedVersionId === v.id}
                  onToggle={() => setExpandedVersionId(expandedVersionId === v.id ? null : v.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function VersionRow({ v, expanded, onToggle }) {
  return (
    <div style={{
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 8,
      padding: '8px 12px',
    }}>
      <button
        onClick={onToggle}
        style={{
          background: 'transparent',
          border: 'none',
          color: COLORS.textPrimary,
          fontSize: 12,
          cursor: 'pointer',
          width: '100%',
          textAlign: 'left',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ color: COLORS.accentLight, fontWeight: 600 }}>v{v.version}</span>
        <span style={{ color: COLORS.textMuted }}>{formatSource(v.source)}</span>
        <span style={{ color: COLORS.textDim, fontSize: 11, marginLeft: 'auto' }}>{formatDate(v.created_at)}</span>
        <span style={{ color: COLORS.textDim }}>{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded && (
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
          maxHeight: 280,
          overflowY: 'auto',
        }}>
          {v.content_md}
        </pre>
      )}
    </div>
  )
}

function formatSource(source) {
  return {
    initial: 'initial',
    manual_edit: 'manual edit',
    proposal_accepted: 'from proposal',
  }[source] || source
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}

const metaLineStyle = {
  fontSize: 11,
  color: COLORS.textMuted,
  marginBottom: 8,
  letterSpacing: '0.02em',
}

const textareaStyle = {
  width: '100%',
  padding: '12px',
  borderRadius: 10,
  border: `1px solid ${COLORS.border}`,
  background: COLORS.bgCard,
  color: COLORS.textPrimary,
  fontSize: 13,
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  outline: 'none',
  resize: 'vertical',
  minHeight: 280,
  lineHeight: 1.55,
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

const errorBox = {
  marginTop: 10,
  padding: '8px 12px',
  borderRadius: 8,
  backgroundColor: COLORS.bgCard,
  border: `1px solid ${COLORS.danger}`,
  color: COLORS.danger,
  fontSize: 12,
}
