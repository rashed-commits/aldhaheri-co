import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'

const API_URL = import.meta.env.VITE_API_URL || ''

function App() {
  const [authenticated, setAuthenticated] = useState(null)

  useEffect(() => {
    fetch(`${API_URL}/api/auth/verify`, { credentials: 'include' })
      .then(res => {
        if (res.ok) setAuthenticated(true)
        else window.location.href = 'https://aldhaheri.co'
      })
      .catch(() => {
        window.location.href = 'https://aldhaheri.co'
      })
  }, [])

  if (authenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0F0F1A' }}>
        <div style={{ color: '#94A3B8' }}>Loading...</div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
