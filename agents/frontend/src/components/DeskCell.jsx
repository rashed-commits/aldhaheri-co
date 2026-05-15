import { COLORS } from '../config/theme'
import AgentSprite from './AgentSprite'

/**
 * One isometric cell: floor diamond + (optionally) a desk + agent sprite + label.
 *
 * Coordinate convention: SVG is centered on (0,0). The floor diamond's vertices
 * are at ±60 horizontal and ±30 vertical. The desk sits roughly in front of the
 * agent (south side of the tile). The sprite is HTML-positioned absolutely so
 * its animations don't fight SVG re-renders.
 */
export default function DeskCell({ agent, isManager = false, isEmpty = false, onClick }) {
  const tileFill = isManager
    ? COLORS.bgCard
    : isEmpty
      ? COLORS.bgCardSubtle
      : COLORS.bgCard
  const tileStroke = isManager ? COLORS.accent : COLORS.border
  const tileStrokeWidth = isManager ? 1.2 : 0.7

  const status = agent?.status || 'idle'
  const bodyColor = isManager ? COLORS.accent : pickAgentColor(agent?.id ?? 0)

  return (
    <div
      onClick={onClick}
      style={{
        position: 'relative',
        width: 120,
        height: 92,
        cursor: !isEmpty && onClick ? 'pointer' : 'default',
        userSelect: 'none',
      }}
    >
      <svg
        viewBox="-60 -30 120 92"
        width={120}
        height={92}
        className="pixel-crisp"
        style={{ display: 'block', position: 'absolute', inset: 0, overflow: 'visible' }}
      >
        {/* Floor tile (isometric rhombus) */}
        <polygon
          points="-60,0 0,-30 60,0 0,30"
          fill={tileFill}
          stroke={tileStroke}
          strokeWidth={tileStrokeWidth}
        />

        {/* Inner highlight to give the tile a slight bevel */}
        <polygon
          points="-56,0 0,-28 56,0 0,28"
          fill="none"
          stroke={isManager ? COLORS.accentLight : COLORS.borderSoft}
          strokeWidth="0.4"
          opacity="0.5"
        />

        {agent && (
          <>
            {/* Desk top (rhombus in front of agent position) */}
            <polygon
              points="-22,8 0,18 22,8 0,-2"
              fill={COLORS.bgCardSubtle}
              stroke={COLORS.border}
              strokeWidth="0.6"
            />
            {/* Desk front-right face */}
            <polygon
              points="0,18 22,8 22,12 0,22"
              fill="#0E0E1C"
              stroke={COLORS.border}
              strokeWidth="0.4"
            />
            {/* Desk front-left face */}
            <polygon
              points="0,18 -22,8 -22,12 0,22"
              fill="#0E0E1C"
              stroke={COLORS.border}
              strokeWidth="0.4"
            />

            {/* Tiny laptop hint on the desk top */}
            <rect x="-7" y="2" width="14" height="6" fill={COLORS.bgBase} stroke={COLORS.borderSoft} strokeWidth="0.3" />
            <rect x="-7" y="2" width="14" height="2" fill={isManager ? COLORS.accentLight : bodyColor} opacity="0.6" />

            {/* Status halo under the agent feet */}
            {status !== 'idle' && (
              <ellipse
                cx="0"
                cy="-2"
                rx="14"
                ry="4"
                fill="none"
                stroke={statusHalo(status)}
                strokeWidth="0.8"
                opacity="0.6"
              />
            )}
          </>
        )}
      </svg>

      {/* Sprite — absolutely positioned over the tile, anchored to the back of the desk */}
      {agent && (
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '4px',
            transform: 'translateX(-50%)',
          }}
        >
          <AgentSprite
            status={status}
            bodyColor={bodyColor}
            isManager={isManager}
            size={36}
          />
        </div>
      )}

      {/* Name label */}
      {agent && (
        <div
          style={{
            position: 'absolute',
            left: '50%',
            bottom: '-18px',
            transform: 'translateX(-50%)',
            fontSize: '10px',
            color: isManager ? COLORS.accentLight : COLORS.textMuted,
            fontWeight: isManager ? 600 : 500,
            letterSpacing: '0.02em',
            whiteSpace: 'nowrap',
            textShadow: '0 1px 0 #0F0F1A',
          }}
        >
          {agent.name}
        </div>
      )}
    </div>
  )
}

function statusHalo(status) {
  return {
    thinking: '#F59E0B',
    working: '#7C3AED',
    done: '#10B981',
    error: '#EF4444',
  }[status]
}

/** Deterministic accent color per agent id (avoids identical sprites). */
function pickAgentColor(id) {
  const palette = ['#7C3AED', '#A78BFA', '#34D399', '#60A5FA', '#F472B6', '#FBBF24', '#22D3EE', '#F87171']
  return palette[id % palette.length]
}
