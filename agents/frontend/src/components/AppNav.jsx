import { NavLink } from 'react-router-dom'
import { COLORS } from '../config/theme'

/**
 * Internal nav (in-app routes). Sits below the project Header.
 */
export default function AppNav({ pendingProposalsCount = 0 }) {
  const items = [
    { name: 'Office', to: '/office' },
    {
      name: 'Proposals',
      to: '/proposals',
      badge: pendingProposalsCount > 0 ? pendingProposalsCount : null,
    },
    { name: 'Crons', to: '/crons' },
    { name: 'Activity', to: '/activity' },
    { name: 'Settings', to: '/settings' },
  ]

  return (
    <nav
      style={{
        display: 'flex',
        alignItems: 'center',
        background: COLORS.bgBase,
        borderBottom: `1px solid ${COLORS.border}`,
        padding: '0 24px',
        height: 40,
        fontSize: 13,
      }}
    >
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          style={({ isActive }) => ({
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            height: '100%',
            background: 'none',
            color: isActive ? COLORS.accentLight : COLORS.textMuted,
            textDecoration: 'none',
            borderBottom: isActive ? `2px solid ${COLORS.accent}` : '2px solid transparent',
            fontWeight: isActive ? 600 : 500,
            transition: 'color 0.15s',
          })}
        >
          {item.name}
          {item.badge != null && (
            <span
              style={{
                fontSize: 10,
                padding: '1px 6px',
                borderRadius: 999,
                backgroundColor: COLORS.warning,
                color: '#0F0F1A',
                fontWeight: 700,
              }}
            >
              {item.badge}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
