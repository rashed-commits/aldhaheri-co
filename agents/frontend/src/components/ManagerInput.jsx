import { useState } from 'react'
import { COLORS } from '../config/theme'

/**
 * Global input bar pinned bottom-center. Submits to the parent which calls
 * /api/manager/route. Parent opens the chat panel (route) or the spawn
 * approval card (spawn) — this component just collects input.
 */
export default function ManagerInput({ onSubmit, isPending, error }) {
  const [text, setText] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const msg = text.trim()
    if (!msg || isPending) return
    onSubmit?.(msg)
    setText('')
  }

  return (
    <div style={{ width: '100%', display: 'flex', justifyContent: 'center', padding: '20px 24px 28px' }}>
      <div style={{ width: '100%', maxWidth: 720 }}>
        {error && (
          <div
            style={{
              marginBottom: 10,
              padding: '10px 14px',
              borderRadius: 10,
              backgroundColor: COLORS.bgCard,
              border: `1px solid ${COLORS.danger}`,
              color: COLORS.danger,
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          style={{
            display: 'flex',
            gap: 10,
            padding: 8,
            borderRadius: 14,
            backgroundColor: COLORS.bgCard,
            border: `1px solid ${COLORS.border}`,
            boxShadow: '0 8px 24px rgba(0,0,0,0.45)',
          }}
        >
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Tell the manager what you need…"
            disabled={isPending}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              padding: '10px 12px',
              color: COLORS.textPrimary,
              fontSize: 15,
              fontFamily: 'inherit',
            }}
          />
          <button
            type="submit"
            disabled={isPending || !text.trim()}
            style={{
              padding: '10px 18px',
              borderRadius: 10,
              border: 'none',
              backgroundColor: isPending || !text.trim() ? COLORS.border : COLORS.accent,
              color: COLORS.textPrimary,
              fontWeight: 600,
              fontSize: 14,
              cursor: isPending || !text.trim() ? 'default' : 'pointer',
              transition: 'background-color 0.15s',
            }}
          >
            {isPending ? 'Routing…' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  )
}
