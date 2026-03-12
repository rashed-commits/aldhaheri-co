export default function ProjectCard({ name, description, icon, url, status }) {
  const handleClick = () => {
    window.open(url, '_blank')
  }

  const isOnline = status === 'online'
  const isChecking = status === 'checking'
  const isUnknown = status === 'unknown'

  const statusColor = isChecking ? '#94A3B8' : isOnline ? '#10B981' : isUnknown ? '#F59E0B' : '#EF4444'
  const statusText = isChecking ? 'Checking...' : isOnline ? 'Online' : isUnknown ? 'Unknown' : 'Offline'

  return (
    <div
      onClick={handleClick}
      className="rounded-xl p-5 cursor-pointer transition-all duration-200"
      style={{
        backgroundColor: '#1A1A2E',
        border: '1px solid #2D2D4E',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#7C3AED')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#2D2D4E')}
    >
      <div className="text-4xl mb-3">{icon}</div>
      <h3 className="text-base font-semibold mb-1" style={{ color: '#F1F5F9' }}>
        {name}
      </h3>
      <p className="text-sm mb-4 leading-relaxed" style={{ color: '#94A3B8' }}>
        {description}
      </p>
      <div className="flex items-center gap-2">
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{ backgroundColor: statusColor }}
        />
        <span
          className="text-xs font-medium"
          style={{ color: statusColor }}
        >
          {statusText}
        </span>
      </div>
    </div>
  )
}
