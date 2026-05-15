import { useCallback, useEffect, useMemo, useState } from 'react'
import Header from '../components/Header'
import IsoGrid from '../components/IsoGrid'
import ManagerInput from '../components/ManagerInput'
import ChatPanel from '../components/ChatPanel'
import { listAgents } from '../services/agents'
import { routeToAgent } from '../services/manager'
import { COLORS } from '../config/theme'

const POLL_INTERVAL_MS = 3000

export default function Office() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [routeError, setRouteError] = useState(null)
  const [routePending, setRoutePending] = useState(false)
  const [conversation, setConversation] = useState(null)

  const fetchAgents = useCallback(async () => {
    try {
      const data = await listAgents()
      setAgents(data)
    } catch (err) {
      console.error('Failed to list agents', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAgents()
    const handle = setInterval(fetchAgents, POLL_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [fetchAgents])

  const manager = useMemo(
    () => agents.find((a) => a.role === 'manager') || null,
    [agents],
  )
  const subAgents = useMemo(
    () => agents.filter((a) => a.role !== 'manager'),
    [agents],
  )

  const openChatWithAgent = useCallback(
    (agent, initialMessage = null, framing = '') => {
      setConversation({
        mode: 'chat',
        agentId: agent.id,
        agent,
        initialMessage,
        framing,
      })
    },
    [],
  )

  const openSpawnApproval = useCallback(
    (proposedAgent, rationale, initialMessage) => {
      setConversation({
        mode: 'spawn',
        proposedAgent,
        rationale,
        initialMessage,
      })
    },
    [],
  )

  const closeChat = useCallback(() => setConversation(null), [])

  const handleAgentSpawned = useCallback((newAgent) => {
    setAgents((prev) => [...prev, newAgent])
  }, [])

  const handleRoute = useCallback(
    async (message) => {
      setRoutePending(true)
      setRouteError(null)
      try {
        const result = await routeToAgent(message)
        if (result.action === 'route') {
          const target = agents.find((a) => a.id === result.agent_id)
          if (target) {
            openChatWithAgent(target, message, result.framing || '')
          } else {
            setRouteError(`Manager routed to unknown agent #${result.agent_id}`)
          }
        } else if (result.action === 'spawn') {
          openSpawnApproval(result.proposed_agent, result.rationale, message)
        }
        fetchAgents()
      } catch (err) {
        setRouteError(err.message || 'Manager routing failed')
      } finally {
        setRoutePending(false)
      }
    },
    [agents, fetchAgents, openChatWithAgent, openSpawnApproval],
  )

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: COLORS.bgBase,
        color: COLORS.textPrimary,
      }}
    >
      <Header />

      <main
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '32px 16px 16px',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: 980,
            textAlign: 'center',
            marginBottom: 32,
          }}
        >
          <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em', margin: 0 }}>
            Office
          </h1>
          <p style={{ fontSize: 13, color: COLORS.textMuted, margin: '6px 0 0' }}>
            {loading
              ? 'Loading…'
              : `${subAgents.length} ${subAgents.length === 1 ? 'specialist' : 'specialists'} on staff`}
          </p>
        </div>

        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
          }}
        >
          {!loading && (
            <IsoGrid
              agents={subAgents}
              manager={manager}
              onCellClick={(a) => openChatWithAgent(a)}
            />
          )}
        </div>
      </main>

      <ManagerInput
        onSubmit={handleRoute}
        isPending={routePending}
        error={routeError}
      />

      {conversation && (
        <ChatPanel
          key={conversation.mode === 'spawn' ? 'spawn' : `agent-${conversation.agentId}`}
          conversation={conversation}
          onClose={closeChat}
          onAgentSpawned={handleAgentSpawned}
        />
      )}
    </div>
  )
}
