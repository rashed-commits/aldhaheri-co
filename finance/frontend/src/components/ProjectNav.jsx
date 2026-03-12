export default function ProjectNav() {
  const navigate = (url) => {
    window.location.href = url
  }

  const projects = [
    { name: 'aldhaheri.co', url: 'https://aldhaheri.co/dashboard', home: true },
    { name: 'Finance', url: null, active: true },
    { name: 'Market Intel', url: 'https://market.aldhaheri.co' },
    { name: 'Real Estate', url: 'https://realestate.aldhaheri.co' },
    { name: 'Trade Bot', url: 'https://trade.aldhaheri.co' },
  ]

  return (
    <nav className="flex items-center gap-0 overflow-x-auto" style={{ background: '#0a0a15', borderBottom: '1px solid #2D2D4E', padding: '0 24px', height: '40px', fontSize: '13px' }}>
      {projects.map((p) => (
        <button
          key={p.name}
          onClick={() => p.url && navigate(p.url)}
          className="flex items-center whitespace-nowrap transition-colors cursor-pointer"
          style={{
            color: p.active ? '#7C3AED' : p.home ? '#A78BFA' : '#94A3B8',
            padding: '8px 16px',
            height: '100%',
            background: 'none',
            border: 'none',
            borderBottom: p.active ? '2px solid #7C3AED' : '2px solid transparent',
            fontWeight: p.home ? 600 : 400,
            cursor: p.url ? 'pointer' : 'default',
          }}
        >
          {p.name}
        </button>
      ))}
    </nav>
  )
}
