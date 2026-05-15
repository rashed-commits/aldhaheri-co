import { useEffect, useState } from 'react'
import { COLORS } from '../config/theme'
import AgentSprite from './AgentSprite'
import ChatPanel from './ChatPanel'
import MemoryPanel from './MemoryPanel'
import SkillsPanel from './SkillsPanel'

/**
 * Right-side slide-in side panel. Owns the wrapper, header, and tab strip.
 * Renders Chat | Memory | Skills tab bodies. Tabs only appear once an agent
 * exists (so spawn mode is chat-only until accepted).
 */
export default function AgentPanel({ conversation, onClose, onAgentSpawned }) {
  const agent = conversation?.agent || null
  const isSpawnMode = conversation?.mode === 'spawn' && !conversation?.agentId
  const [tab, setTab] = useState('chat')

  // Whenever the targeted agent changes, snap back to Chat.
  useEffect(() => {
    setTab('chat')
  }, [conversation?.agentId])

  return (
    <div style={{
      position: 'fixed',
      top: 80, // below project nav (40) + app nav (40)
      right: 0,
      bottom: 0,
      width: 'min(480px, 100vw)',
      backgroundColor: COLORS.bgBase,
      borderLeft: `1px solid ${COLORS.border}`,
      boxShadow: '-10px 0 30px rgba(0,0,0,0.4)',
      display: 'flex',
      flexDirection: 'column',
      animation: 'slide-in 0.25s ease-out',
      zIndex: 50,
    }}>
      <div style={{
        padding: '12px 18px',
        borderBottom: `1px solid ${COLORS.border}`,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <div style={{ width: 28, display: 'flex', justifyContent: 'center' }}>
          <AgentSprite
            status={agent?.status || 'idle'}
            bodyColor={agent?.role === 'manager' ? COLORS.accent : COLORS.accentLight}
            isManager={agent?.role === 'manager'}
            size={28}
          />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            {isSpawnMode ? `Spawning: ${conversation.proposedAgent?.name || '?'}` : agent?.name || 'Agent'}
          </div>
          {agent?.specialization && !isSpawnMode && (
            <div style={{ fontSize: 11, color: COLORS.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {agent.specialization}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: COLORS.textMuted,
            fontSize: 22,
            cursor: 'pointer',
            padding: 4,
            lineHeight: 1,
          }}
          aria-label="Close"
        >
          ×
        </button>
      </div>

      {!isSpawnMode && agent && (
        <div style={{
          display: 'flex',
          borderBottom: `1px solid ${COLORS.border}`,
          padding: '0 8px',
        }}>
          {['chat', 'memory', 'skills'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '10px 16px',
                background: 'transparent',
                border: 'none',
                borderBottom: tab === t ? `2px solid ${COLORS.accent}` : '2px solid transparent',
                color: tab === t ? COLORS.accentLight : COLORS.textMuted,
                fontSize: 12,
                fontWeight: tab === t ? 600 : 500,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                cursor: 'pointer',
              }}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0 }}>
        {(tab === 'chat' || isSpawnMode) && (
          <ChatPanel
            conversation={conversation}
            onAgentSpawned={onAgentSpawned}
            onClose={onClose}
          />
        )}
        {tab === 'memory' && !isSpawnMode && agent && (
          <MemoryPanel agentId={agent.id} />
        )}
        {tab === 'skills' && !isSpawnMode && agent && (
          <SkillsPanel agentId={agent.id} />
        )}
      </div>
    </div>
  )
}
