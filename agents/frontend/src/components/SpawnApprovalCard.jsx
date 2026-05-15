import { useState } from 'react'
import { COLORS } from '../config/theme'

/**
 * Inline card that lets the user review and edit a manager-proposed agent
 * before it's actually spawned. Name/specialization/soul are all editable.
 */
export default function SpawnApprovalCard({
  proposedAgent,
  rationale,
  onAccept,
  onReject,
  isPending,
}) {
  const [name, setName] = useState(proposedAgent?.name || '')
  const [specialization, setSpecialization] = useState(proposedAgent?.specialization || '')
  const [soul, setSoul] = useState(proposedAgent?.soul || '')

  const handleAccept = () => {
    onAccept?.({
      name: name.trim(),
      specialization: specialization.trim(),
      soul: soul.trim(),
    })
  }

  return (
    <div style={{
      padding: 16,
      borderRadius: 12,
      backgroundColor: COLORS.bgCard,
      border: `1px solid ${COLORS.warning}`,
      marginBottom: 14,
    }}>
      <div style={{
        fontSize: 11,
        fontWeight: 600,
        color: COLORS.warning,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        marginBottom: 4,
      }}>
        Spawn proposal
      </div>
      {rationale && (
        <div style={{ fontSize: 13, color: COLORS.textMuted, marginBottom: 12 }}>
          {rationale}
        </div>
      )}

      <Field label="Name">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isPending}
          style={inputStyle}
        />
      </Field>
      <Field label="Specialization">
        <input
          value={specialization}
          onChange={(e) => setSpecialization(e.target.value)}
          disabled={isPending}
          style={inputStyle}
        />
      </Field>
      <Field label="Soul">
        <textarea
          value={soul}
          onChange={(e) => setSoul(e.target.value)}
          disabled={isPending}
          rows={5}
          style={{ ...inputStyle, minHeight: 100, resize: 'vertical', fontFamily: 'inherit' }}
        />
      </Field>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 14 }}>
        <button
          onClick={onReject}
          disabled={isPending}
          style={ghostBtn}
        >
          Reject
        </button>
        <button
          onClick={handleAccept}
          disabled={isPending || !name.trim()}
          style={primaryBtn(isPending || !name.trim())}
        >
          {isPending ? 'Spawning…' : 'Spawn'}
        </button>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
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

const ghostBtn = {
  padding: '8px 14px',
  borderRadius: 8,
  border: `1px solid ${COLORS.border}`,
  background: 'transparent',
  color: COLORS.textMuted,
  fontSize: 13,
  cursor: 'pointer',
}

const primaryBtn = (disabled) => ({
  padding: '8px 16px',
  borderRadius: 8,
  border: 'none',
  background: disabled ? COLORS.border : COLORS.warning,
  color: '#0F0F1A',
  fontWeight: 600,
  fontSize: 13,
  cursor: disabled ? 'default' : 'pointer',
})
