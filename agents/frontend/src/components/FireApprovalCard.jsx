import { useEffect } from 'react'
import { COLORS } from '../config/theme'

/**
 * Centered modal for confirming agent dismissal. Triggered from two paths:
 *   1. Manager returns action='fire' from /api/manager/route.
 *   2. User clicks the Fire button in AgentPanel header.
 *
 * Props:
 *   agent:     Agent to fire (must be non-manager — caller enforces).
 *   rationale: Optional explanation (manager-supplied when path #1).
 *   onAccept:  () => Promise<void>   delete + cleanup
 *   onCancel:  () => void
 *   isPending: boolean
 *   error:     string | null
 */
export default function FireApprovalCard({ agent, rationale, onAccept, onCancel, isPending, error }) {
  // Close on Escape
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape' && !isPending) onCancel?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isPending, onCancel])

  if (!agent) return null

  return (
    <div
      onClick={isPending ? undefined : onCancel}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 420,
          backgroundColor: COLORS.bgCard,
          border: `1px solid ${COLORS.danger}`,
          borderRadius: 14,
          padding: 22,
          boxShadow: '0 10px 40px rgba(0,0,0,0.6)',
        }}
      >
        <div style={{
          fontSize: 11,
          fontWeight: 700,
          color: COLORS.danger,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          marginBottom: 8,
        }}>
          Fire agent
        </div>

        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
          Dismiss {agent.name}?
        </div>

        <div style={{ fontSize: 13, color: COLORS.textMuted, marginBottom: 14 }}>
          This soft-deletes the agent and hides it from the office. Their memory,
          skills, and session history remain in the database — but they won't
          appear or respond unless restored manually.
        </div>

        {rationale && (
          <div style={{
            padding: '8px 12px',
            borderRadius: 8,
            backgroundColor: COLORS.bgBase,
            border: `1px solid ${COLORS.borderSoft}`,
            fontSize: 12,
            color: COLORS.textMuted,
            marginBottom: 14,
          }}>
            <span style={{ color: COLORS.accentLight, fontWeight: 600 }}>Manager: </span>
            {rationale}
          </div>
        )}

        {error && (
          <div style={{
            padding: '8px 12px',
            borderRadius: 8,
            backgroundColor: COLORS.bgBase,
            border: `1px solid ${COLORS.danger}`,
            color: COLORS.danger,
            fontSize: 12,
            marginBottom: 14,
          }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            onClick={onCancel}
            disabled={isPending}
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: `1px solid ${COLORS.border}`,
              background: 'transparent',
              color: COLORS.textMuted,
              fontSize: 13,
              cursor: isPending ? 'default' : 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onAccept}
            disabled={isPending}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              border: 'none',
              background: isPending ? COLORS.border : COLORS.danger,
              color: '#0F0F1A',
              fontWeight: 700,
              fontSize: 13,
              cursor: isPending ? 'default' : 'pointer',
            }}
          >
            {isPending ? 'Firing…' : 'Fire'}
          </button>
        </div>
      </div>
    </div>
  )
}
