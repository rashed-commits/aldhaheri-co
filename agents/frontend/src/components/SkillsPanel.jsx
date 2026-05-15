import { useCallback, useEffect, useState } from 'react'
import { COLORS } from '../config/theme'
import { createSkill, deleteSkill, listSkills, patchSkill } from '../services/skills'

/**
 * Per-agent skills CRUD. Inline expanding form for add/edit, soft-delete
 * via the API's DELETE endpoint (sets `deleted=true`, the list reload
 * filters them out).
 */
export default function SkillsPanel({ agentId }) {
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null) // 'new' for create, or skill.id
  const [busyId, setBusyId] = useState(null)

  const reload = useCallback(async () => {
    setError(null)
    try {
      const data = await listSkills(agentId)
      setSkills(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => {
    reload()
  }, [reload])

  const handleCreate = useCallback(async (form) => {
    setBusyId('new')
    setError(null)
    try {
      await createSkill(agentId, form)
      setEditingId(null)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [agentId, reload])

  const handlePatch = useCallback(async (id, form) => {
    setBusyId(id)
    setError(null)
    try {
      await patchSkill(id, form)
      setEditingId(null)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [reload])

  const handleDelete = useCallback(async (id) => {
    if (!confirm('Delete this skill?')) return
    setBusyId(id)
    setError(null)
    try {
      await deleteSkill(id)
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }, [reload])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {loading ? 'Loading…' : `${skills.length} ${skills.length === 1 ? 'skill' : 'skills'}`}
          </div>
          {editingId !== 'new' && (
            <button
              onClick={() => setEditingId('new')}
              style={ghostBtn}
            >
              + Add skill
            </button>
          )}
        </div>

        {editingId === 'new' && (
          <SkillForm
            onSubmit={handleCreate}
            onCancel={() => setEditingId(null)}
            isPending={busyId === 'new'}
            submitLabel="Create skill"
          />
        )}

        {error && <div style={errorBox}>{error}</div>}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
          {skills.map((s) => (
            editingId === s.id ? (
              <SkillForm
                key={s.id}
                initial={s}
                onSubmit={(form) => handlePatch(s.id, form)}
                onCancel={() => setEditingId(null)}
                isPending={busyId === s.id}
                submitLabel="Save changes"
              />
            ) : (
              <SkillCard
                key={s.id}
                skill={s}
                onEdit={() => setEditingId(s.id)}
                onDelete={() => handleDelete(s.id)}
                isBusy={busyId === s.id}
              />
            )
          ))}
          {skills.length === 0 && !loading && (
            <div style={{ fontSize: 13, color: COLORS.textDim, padding: '20px 0', textAlign: 'center' }}>
              No skills yet. Add one manually or accept a skill proposal from the queue.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function SkillCard({ skill, onEdit, onDelete, isBusy }) {
  const keywords = parseKeywords(skill.trigger_keywords)
  return (
    <div style={{
      padding: 12,
      borderRadius: 10,
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${COLORS.border}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: COLORS.textPrimary }}>{skill.name}</div>
          <div style={{ fontSize: 11, color: COLORS.textDim, marginTop: 2 }}>
            {skill.slug} · {skill.source}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={onEdit} disabled={isBusy} style={iconBtn}>Edit</button>
          <button onClick={onDelete} disabled={isBusy} style={iconBtnDanger}>Delete</button>
        </div>
      </div>

      {skill.description && (
        <div style={{ fontSize: 13, color: COLORS.textMuted, marginTop: 8 }}>{skill.description}</div>
      )}

      {keywords.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {keywords.map((kw, i) => (
            <span key={i} style={tag}>{kw}</span>
          ))}
        </div>
      )}

      {skill.instructions_md && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: 'pointer', fontSize: 12, color: COLORS.accentLight, userSelect: 'none' }}>
            Show playbook
          </summary>
          <pre style={detailsPre}>{skill.instructions_md}</pre>
        </details>
      )}

      {skill.frontmatter_yaml && (
        <details style={{ marginTop: 4 }}>
          <summary style={{ cursor: 'pointer', fontSize: 12, color: COLORS.textMuted, userSelect: 'none' }}>
            Show frontmatter
          </summary>
          <pre style={detailsPre}>{skill.frontmatter_yaml}</pre>
        </details>
      )}
    </div>
  )
}

function SkillForm({ initial, onSubmit, onCancel, isPending, submitLabel }) {
  const [name, setName] = useState(initial?.name || '')
  const [slug, setSlug] = useState(initial?.slug || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [keywords, setKeywords] = useState(parseKeywords(initial?.trigger_keywords).join(', '))
  const [frontmatter, setFrontmatter] = useState(initial?.frontmatter_yaml || '')
  const [instructions, setInstructions] = useState(initial?.instructions_md || '')

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      name: name.trim(),
      slug: slug.trim() || undefined,
      description: description.trim(),
      trigger_keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
      frontmatter_yaml: frontmatter,
      instructions_md: instructions,
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        padding: 14,
        borderRadius: 10,
        backgroundColor: COLORS.bgCard,
        border: `1px solid ${COLORS.accent}`,
        marginBottom: 12,
      }}
    >
      <FormField label="Name">
        <input value={name} onChange={(e) => setName(e.target.value)} required disabled={isPending} style={inputStyle} />
      </FormField>
      <FormField label="Slug (optional — auto-generated from name)">
        <input value={slug} onChange={(e) => setSlug(e.target.value)} disabled={isPending} style={inputStyle} placeholder="auto" />
      </FormField>
      <FormField label="Description">
        <input value={description} onChange={(e) => setDescription(e.target.value)} disabled={isPending} style={inputStyle} />
      </FormField>
      <FormField label="Trigger keywords (comma-separated)">
        <input value={keywords} onChange={(e) => setKeywords(e.target.value)} disabled={isPending} style={inputStyle} placeholder="email, draft, followup" />
      </FormField>
      <FormField label="Frontmatter YAML (optional)">
        <textarea value={frontmatter} onChange={(e) => setFrontmatter(e.target.value)} disabled={isPending} rows={3} style={{ ...inputStyle, fontFamily: 'ui-monospace, monospace', resize: 'vertical' }} />
      </FormField>
      <FormField label="Instructions (markdown)">
        <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} disabled={isPending} rows={6} style={{ ...inputStyle, fontFamily: 'ui-monospace, monospace', resize: 'vertical' }} />
      </FormField>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
        <button type="button" onClick={onCancel} disabled={isPending} style={ghostBtn}>Cancel</button>
        <button type="submit" disabled={isPending || !name.trim()} style={primaryBtn(isPending || !name.trim())}>
          {isPending ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  )
}

function FormField({ label, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
      <span style={{ fontSize: 11, color: COLORS.textMuted, letterSpacing: '0.02em' }}>{label}</span>
      {children}
    </label>
  )
}

function parseKeywords(raw) {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const inputStyle = {
  background: COLORS.bgBase,
  border: `1px solid ${COLORS.border}`,
  outline: 'none',
  padding: '8px 10px',
  borderRadius: 6,
  color: COLORS.textPrimary,
  fontSize: 13,
  width: '100%',
  fontFamily: 'inherit',
}

const ghostBtn = {
  padding: '6px 12px',
  borderRadius: 6,
  border: `1px solid ${COLORS.border}`,
  background: 'transparent',
  color: COLORS.textMuted,
  fontSize: 12,
  cursor: 'pointer',
}

const iconBtn = {
  padding: '4px 10px',
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

const tag = {
  padding: '2px 8px',
  borderRadius: 999,
  fontSize: 11,
  backgroundColor: 'rgba(124,58,237,0.15)',
  color: COLORS.accentLight,
  border: '1px solid rgba(124,58,237,0.3)',
}

const detailsPre = {
  marginTop: 6,
  padding: 10,
  backgroundColor: COLORS.bgBase,
  border: `1px solid ${COLORS.borderSoft}`,
  borderRadius: 6,
  fontSize: 11,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  fontFamily: 'ui-monospace, monospace',
  maxHeight: 220,
  overflowY: 'auto',
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
