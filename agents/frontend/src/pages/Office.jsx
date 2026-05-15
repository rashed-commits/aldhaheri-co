import { useCallback, useEffect, useMemo, useState } from 'react'
import Header from '../components/Header'
import AppNav from '../components/AppNav'
import IsoGrid from '../components/IsoGrid'
import ManagerInput from '../components/ManagerInput'
import AgentPanel from '../components/AgentPanel'
import { listAgents } from '../services/agents'
import { routeToAgent } from '../services/manager'
import { listProposals } from '../services/proposals'
import { COLORS } from '../config/theme'

const POLL_INTERVAL_MS = 3000

export default function Office() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [routeError, setRouteError] = useState(null)
  const [routePending, setRoutePending] = useState(false)
  const [conversation, setConversation] = useState(null)
  const [pendingProposalsCount, setPendingProposalsCount] = useState(0)

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

  const fetchProposalCount = useCallback(async () => {
    try {
      const data = await listProposals({ status: 'pending' })
      setPendingProposalsCount(data.length)
    } catch (err) {
      console.warn('Failed to load proposal count', err)
    }
  }, [])

  useEffect(() => {
    fetchAgents()
    fetchProposalCount()
    const handle = setInterval(() => {
      fetchAgents()
      fetchProposalCount()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(handle)
  }, [fetchAgents, fetchProposalCount])

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

  // After spawn-accept, both add to agents list AND transition the active
  // conversation into chat mode so AgentPanel shows tabs and the right header.
  const handleAgentSpawned = useCallback((newAgent) => {
    setAgents((prev) => [...prev, newAgent])
    setConversation((prev) =>
      prev && prev.mode === 'spawn'
        ? {
            ...prev,
            mode: 'chat',
            agentId: newAgent.id,
            agent: newAgent,
          }
        : prev,
    )
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
      <AppNav pendingProposalsCount={pendingProposalsCount} />

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
        <AgentPanel
          key={conversation.mode === 'spawn' ? 'spawn' : `agent-${conversation.agentId}`}
          conversation={conversation}
          onClose={closeChat}
          onAgentSpawned={handleAgentSpawned}
        />
      )}
    </div>
  )
}
