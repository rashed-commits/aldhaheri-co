import { useEffect, useState } from 'react'
import { verify } from '../services/auth'
import { COLORS } from '../config/theme'

export default function ProtectedRoute({ children }) {
  const [authed, setAuthed] = useState(null) // null = checking

  useEffect(() => {
    verify().then(setAuthed).catch(() => setAuthed(false))
  }, [])

  if (authed === null) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: COLORS.bgBase,
          color: COLORS.textMuted,
        }}
      >
        Checking session…
      </div>
    )
  }

  if (!authed) {
    window.location.href = 'https://aldhaheri.co'
    return null
  }

  return children
}
