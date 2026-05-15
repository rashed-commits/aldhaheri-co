import { COLORS } from '../config/theme'

export default function Header() {
  const projects = [
    { name: 'aldhaheri.co', url: 'https://aldhaheri.co', home: true },
    { name: '\u{1F4B3} Finance', url: 'https://finance.aldhaheri.co' },
    { name: '\u{1F4CA} Market Intel', url: 'https://market.aldhaheri.co' },
    { name: '\u{1F3E0} Real Estate', url: 'https://realestate.aldhaheri.co' },
    { name: '\u{1F9E0} Agents', url: null, active: true },
  ]

  return (
    <nav
      className="flex items-center overflow-x-auto"
      style={{
        background: '#0a0a15',
        borderBottom: `1px solid ${COLORS.border}`,
        padding: '0 24px',
        height: 40,
        fontSize: 13,
      }}
    >
      {projects.map((p) => (
        <button
          key={p.name}
          onClick={() => p.url && (window.location.href = p.url)}
          className="flex items-center whitespace-nowrap transition-colors"
          style={{
            color: p.active ? COLORS.accent : p.home ? COLORS.accentLight : COLORS.textMuted,
            padding: '8px 16px',
            height: '100%',
            background: 'none',
            border: 'none',
            borderBottom: p.active ? `2px solid ${COLORS.accent}` : '2px solid transparent',
            fontWeight: p.home || p.active ? 600 : 400,
            cursor: p.url ? 'pointer' : 'default',
          }}
        >
          {p.name}
        </button>
      ))}
    </nav>
  )
}
