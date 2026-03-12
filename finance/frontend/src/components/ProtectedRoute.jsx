import { useState, useEffect } from 'react'

export default function ProtectedRoute({ children }) {
  const [authed, setAuthed] = useState(null)

  useEffect(() => {
    fetch((import.meta.env.VITE_API_URL || '') + '/api/auth/verify', { credentials: 'include' })
      .then(res => {
        if (res.ok) setAuthed(true)
        else {
          window.location.href = 'https://aldhaheri.co'
        }
      })
      .catch(() => {
        window.location.href = 'https://aldhaheri.co'
      })
  }, [])

  if (authed === null) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-950"><div className="text-gray-400">Loading...</div></div>
  }
  return children
}
