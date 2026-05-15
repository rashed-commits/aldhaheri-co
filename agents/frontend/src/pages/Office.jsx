import { useCallback, useEffect, useMemo, useState } from 'react'
import Header from '../components/Header'
import IsoGrid from '../components/IsoGrid'
import ManagerInput from '../components/ManagerInput'
import { listAgents } from '../services/agents'
import { routeToAgent } from '../services/manager'
import { COLORS } from '../config/theme'

const POLL_INTERVAL_MS = 3000

export default function Office() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [routeError, setRouteError] = useState(null)
  const [routeResult, setRouteResult] = useState(null)
  const [routePending, setRoutePending] = useState(false)

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

  const manager = useMemo(() => agents.find((a) => a.role === 'manager') || null, [agents])
  const subAgents = useMemo(() => agents.filter((a) => a.role !== 'manager'), [agents])

  const handleRoute = useCallback(async (message) => {
    setRoutePending(true)
    setRouteError(null)
    setRouteResult(null)
    try {
      const result = await routeToAgent(message)
      setRouteResult(result)
      // Refresh immediately so any agent that goes thinking/working shows up
      fetchAgents()
    } catch (err) {
      setRouteError(err.message || 'Manager routing failed')
    } finally {
      setRoutePending(false)
    }
  }, [fetchAgents])

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
        <div style={{ width: '100%', maxWidth: 980, textAlign: 'center', marginBottom: 32 }}>
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
              onCellClick={(a) => {
                // Phase 10 will open a chat panel here; for now just log.
                console.log('Clicked agent', a)
              }}
            />
          )}
        </div>
      </main>

      <ManagerInput
        onSubmit={handleRoute}
        isPending={routePending}
        lastResult={routeResult}
        error={routeError}
      />
    </div>
  )
}
