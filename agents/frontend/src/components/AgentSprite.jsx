import { COLORS, STATUS_COLORS } from '../config/theme'

/**
 * Procedural SVG agent sprite drawn in a near-pixel-art aesthetic so we can
 * swap in real art later without changing layout. Four states: idle |
 * thinking | working | done. Falls back to idle for anything else (incl. error).
 *
 * Anchor: the bottom of the body sits at y=46, so the caller can place the
 * sprite by aligning that point with the back edge of the desk on a cell.
 */
export default function AgentSprite({
  status = 'idle',
  bodyColor = COLORS.accent,
  isManager = false,
  size = 56,
}) {
  const statusColor = STATUS_COLORS[status] || STATUS_COLORS.idle
  const skin = '#D4A853'
  const outline = '#0F0F1A'

  // Bob/breath: thinking bobs, idle breathes slightly.
  const containerAnim =
    status === 'thinking'
      ? 'bob 1.8s ease-in-out infinite'
      : status === 'working'
        ? 'pulse-soft 1.6s ease-in-out infinite'
        : status === 'done'
          ? 'spawn-in 0.4s ease-out'
          : 'none'

  // Manager is rendered with a small "crown" (accent triangle) above the head.
  return (
    <div
      style={{
        width: size,
        height: size * 1.5,
        animation: containerAnim,
        transformOrigin: 'center bottom',
        position: 'relative',
        pointerEvents: 'none',
      }}
    >
      <svg
        viewBox="0 0 32 48"
        width={size}
        height={size * 1.5}
        className="pixel-crisp"
        style={{ display: 'block' }}
      >
        {/* shadow on floor */}
        <ellipse cx="16" cy="46" rx="9" ry="1.6" fill="rgba(0,0,0,0.5)" />

        {/* legs */}
        <rect x="11" y="36" width="3" height="8" fill="#222238" />
        <rect x="18" y="36" width="3" height="8" fill="#222238" />

        {/* body — slightly trapezoidal via two rects + side fills */}
        <rect x="9" y="22" width="14" height="16" fill={bodyColor} />
        <rect x="9" y="22" width="14" height="2" fill="rgba(255,255,255,0.12)" />
        <rect x="9" y="36" width="14" height="2" fill="rgba(0,0,0,0.18)" />

        {/* neck */}
        <rect x="14" y="19" width="4" height="3" fill={skin} />

        {/* head */}
        <rect x="10" y="10" width="12" height="10" fill={skin} stroke={outline} strokeWidth="0.5" />

        {/* hair line */}
        <rect x="10" y="10" width="12" height="2" fill="#2D2D4E" />

        {/* eyes */}
        <rect x="12" y="14" width="2" height="2" fill={outline} />
        <rect x="18" y="14" width="2" height="2" fill={outline} />

        {/* manager crown */}
        {isManager && (
          <g>
            <polygon points="13,8 16,4 19,8" fill={COLORS.accentLight} stroke={outline} strokeWidth="0.4" />
            <circle cx="16" cy="3.5" r="0.9" fill={COLORS.accent} />
          </g>
        )}

        {/* status indicator above head */}
        <g transform="translate(16, 0)">
          {status === 'thinking' && (
            <g>
              <circle cx="0" cy="3" r="2.6" fill={COLORS.bgCard} stroke={statusColor} strokeWidth="0.6" />
              <text x="0" y="4.7" textAnchor="middle" fill={statusColor} fontSize="4.5" fontWeight="700" fontFamily="Inter, sans-serif">?</text>
            </g>
          )}
          {status === 'working' && (
            <g>
              <circle cx="-3" cy="3" r="1" fill={statusColor} style={{ animation: 'typing-dot 1.2s ease-in-out infinite' }} />
              <circle cx="0" cy="3" r="1" fill={statusColor} style={{ animation: 'typing-dot 1.2s ease-in-out 0.2s infinite' }} />
              <circle cx="3" cy="3" r="1" fill={statusColor} style={{ animation: 'typing-dot 1.2s ease-in-out 0.4s infinite' }} />
            </g>
          )}
          {status === 'done' && (
            <g>
              <circle cx="0" cy="3" r="2.6" fill={COLORS.bgCard} stroke={statusColor} strokeWidth="0.6" />
              <polyline points="-1.5,3 -0.3,4.3 1.7,1.7" fill="none" stroke={statusColor} strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
            </g>
          )}
          {status === 'error' && (
            <g>
              <circle cx="0" cy="3" r="2.6" fill={COLORS.bgCard} stroke={statusColor} strokeWidth="0.6" />
              <text x="0" y="4.7" textAnchor="middle" fill={statusColor} fontSize="4.5" fontWeight="700" fontFamily="Inter, sans-serif">!</text>
            </g>
          )}
        </g>
      </svg>
    </div>
  )
}
