import { useNavigate } from 'react-router-dom'
import { logout } from '../services/auth'

export default function Header() {
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/', { replace: true })
  }

  return (
    <header
      className="flex items-center justify-between px-6"
      style={{
        height: '56px',
        backgroundColor: '#1A1A2E',
        borderBottom: '1px solid #2D2D4E',
      }}
    >
      <span className="text-lg font-bold" style={{ color: '#F1F5F9' }}>
        aldhaheri.co
      </span>
      <button
        onClick={handleLogout}
        className="text-sm px-4 py-1.5 rounded-lg transition-colors cursor-pointer"
        style={{
          color: '#94A3B8',
          border: '1px solid #2D2D4E',
          backgroundColor: 'transparent',
        }}
      >
        Logout
      </button>
    </header>
  )
}
