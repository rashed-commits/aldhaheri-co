import { useCallback, useEffect, useState } from 'react'
import { COLORS } from '../config/theme'
import { parseCronNL } from '../services/crons'
import { listSkills } from '../services/skills'

/**
 * Create / edit form for a cron job. Implements the two-step parse flow:
 * user types NL, hits Parse, sees the resulting cron expression + Haiku's
 * one-line explanation, then Saves. On edit, the existing NL is pre-filled
 * and Parse is optional — the backend will re-parse on its own if the NL
 * field changed.
 */
export default function CronForm({
  agents,
  initial,
  onSubmit,
  onCancel,
  isPending,
  submitLabel,
}) {
  const [name, setName] = useState(initial?.name || '')
  const [agentId, setAgentId] = useState(initial?.agent_id || agents?.[0]?.id || null)
  const [nlSchedule, setNlSchedule] = useState(initial?.nl_schedule || '')
  const [prompt, setPrompt] = useState(initial?.prompt || '')
  const [skillId, setSkillId] = useState(initial?.skill_id || null)
  const [outputTarget, setOutputTarget] = useState(initial?.output_target || 'ui_only')

  const [skills, setSkills] = useState([])
  const [parsed, setParsed] = useState(
    initial?.cron_expr
      ? { cron_expr: initial.cron_expr, explanation: '(existing schedule)' }
      : null,
  )
  const [parseError, setParseError] = useState(null)
  const [parsing, setParsing] = useState(false)

  // Load skills when the selected agent changes
  useEffect(() => {
    if (!agentId) {
      setSkills([])
      return
    }
    listSkills(agentId).then(setSkills).catch(() => setSkills([]))
  }, [agentId])

  // Reset parsed expression if the NL text changes
  useEffect(() => {
    if (initial && nlSchedule === initial.nl_schedule) return
    setParsed(null)
  }, [nlSchedule, initial])

  const handleParse = useCallback(async () => {
    if (!nlSchedule.trim()) return
    setParseError(null)
    setParsing(true)
    try {
      const result = await parseCronNL(nlSchedule.trim())
      if (!result.cron_expr) {
        setParseError(result.explanation || 'Could not parse this schedule.')
        setParsed(null)
      } else {
        setParsed(result)
      }
    } catch (err) {
      setParseError(err.message)
    } finally {
      setParsing(false)
    }
  }, [nlSchedule])

  const isCreate = !initial
  const canSubmit =
    !isPending &&
    name.trim() &&
    agentId &&
    nlSchedule.trim() &&
    prompt.trim() &&
    (isCreate ? !!parsed?.cron_expr : true)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSubmit) return
    if (isCreate) {
      onSubmit({
        agent_id: agentId,
        name: name.trim(),
        nl_schedule: nlSchedule.trim(),
        cron_expr: parsed.cron_expr,
        prompt: prompt.trim(),
        skill_id: skillId || null,
        output_target: outputTarget,
      })
    } else {
      // PATCH: only send fields the user might have edited
      const patch = {
        name: name.trim(),
        nl_schedule: nlSchedule.trim(),
        prompt: prompt.trim(),
        skill_id: skillId || null,
        output_target: outputTarget,
      }
      onSubmit(patch)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        padding: 16,
        borderRadius: 12,
        backgroundColor: COLORS.bgCard,
        border: `1px solid ${COLORS.accent}`,
        marginBottom: 14,
      }}
    >
      <FormField label="Name">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isPending}
          style={inputStyle}
          placeholder="e.g. Morning digest"
        />
      </FormField>

      <FormField label="Agent">
        <select
          value={agentId || ''}
          onChange={(e) => {
            setAgentId(Number(e.target.value))
            setSkillId(null)
          }}
          disabled={isPending}
          style={inputStyle}
        >
          <option value="" disabled>Pick an agent…</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}{a.role === 'manager' ? ' (manager)' : ''}
            </option>
          ))}
        </select>
      </FormField>

      <FormField label="Schedule (natural language)">
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={nlSchedule}
            onChange={(e) => setNlSchedule(e.target.value)}
            disabled={isPending}
            style={{ ...inputStyle, flex: 1 }}
            placeholder="every Monday at 9am"
          />
          <button
            type="button"
            onClick={handleParse}
            disabled={parsing || !nlSchedule.trim() || isPending}
            style={secondaryBtn(parsing || !nlSchedule.trim() || isPending)}
          >
            {parsing ? 'Parsing…' : 'Parse'}
          </button>
        </div>
        {parsed?.cron_expr && (
          <div style={parsedBox}>
            <code style={{ color: COLORS.accentLight, fontSize: 13 }}>{parsed.cron_expr}</code>
            {parsed.explanation && (
              <span style={{ color: COLORS.textMuted, fontSize: 12, marginLeft: 8 }}>
                — {parsed.explanation}
              </span>
            )}
          </div>
        )}
        {parseError && (
          <div style={errorBox}>{parseError}</div>
        )}
      </FormField>

      <FormField label="Prompt the agent will receive">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isPending}
          rows={4}
          style={{ ...inputStyle, resize: 'vertical', minHeight: 80, fontFamily: 'inherit' }}
          placeholder="What should the agent do when this fires?"
        />
      </FormField>

      <FormField label="Force a skill (optional)">
        <select
          value={skillId || ''}
          onChange={(e) => setSkillId(e.target.value ? Number(e.target.value) : null)}
          disabled={isPending || skills.length === 0}
          style={inputStyle}
        >
          <option value="">— none (let the matcher decide) —</option>
          {skills.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </FormField>

      <FormField label="Output target">
        <div style={{ display: 'flex', gap: 14, marginTop: 2 }}>
          {[
            { v: 'ui_only', label: 'UI only' },
            { v: 'telegram', label: 'Telegram' },
            { v: 'both', label: 'Both' },
          ].map((opt) => (
            <label key={opt.v} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
              <input
                type="radio"
                name="output_target"
                value={opt.v}
                checked={outputTarget === opt.v}
                onChange={() => setOutputTarget(opt.v)}
                disabled={isPending}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </FormField>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={isPending}
          style={ghostBtn}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!canSubmit}
          style={primaryBtn(!canSubmit)}
        >
          {isPending ? 'Saving…' : submitLabel || (isCreate ? 'Create cron' : 'Save changes')}
        </button>
      </div>
    </form>
  )
}

function FormField({ label, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
      <span style={{ fontSize: 11, color: COLORS.textMuted, letterSpacing: '0.02em' }}>{label}</span>
      {children}
    </label>
  )
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

const parsedBox = {
  marginTop: 8,
  padding: '8px 10px',
  borderRadius: 6,
  backgroundColor: COLORS.bgBase,
  border: `1px solid ${COLORS.borderSoft}`,
}

const errorBox = {
  marginTop: 8,
  padding: '8px 10px',
  borderRadius: 6,
  backgroundColor: COLORS.bgCard,
  border: `1px solid ${COLORS.danger}`,
  color: COLORS.danger,
  fontSize: 12,
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

const secondaryBtn = (disabled) => ({
  padding: '8px 14px',
  borderRadius: 8,
  border: `1px solid ${COLORS.accentLight}`,
  background: 'transparent',
  color: disabled ? COLORS.textDim : COLORS.accentLight,
  fontSize: 13,
  fontWeight: 600,
  cursor: disabled ? 'default' : 'pointer',
})

const ghostBtn = {
  padding: '8px 14px',
  borderRadius: 8,
  border: `1px solid ${COLORS.border}`,
  background: 'transparent',
  color: COLORS.textMuted,
  fontSize: 13,
  cursor: 'pointer',
}
