import { useEffect, useState } from 'react'
import ProjectNav from '../components/ProjectNav'
import Header from '../components/Header'
import PortfolioSummary from '../components/PortfolioSummary'
import EquityChart from '../components/EquityChart'
import AllocationChart from '../components/AllocationChart'
import PositionsTable from '../components/PositionsTable'
import SignalsPanel from '../components/SignalsPanel'
import ModelMetrics from '../components/ModelMetrics'
import FeatureChart from '../components/FeatureChart'
import TradeReasoning from '../components/TradeReasoning'
import api from '../api'

function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [positions, setPositions] = useState([])
  const [history, setHistory] = useState([])
  const [signals, setSignals] = useState({ date: null, signals: [] })
  const [metrics, setMetrics] = useState(null)
  const [features, setFeatures] = useState(null)
  const [reasoning, setReasoning] = useState({ date: null, signals: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function loadData() {
      try {
        const [sumRes, posRes, histRes, sigRes, perfRes, featRes, reasonRes] = await Promise.allSettled([
          api('/api/portfolio/summary'),
          api('/api/portfolio/positions'),
          api('/api/portfolio/history'),
          api('/api/portfolio/signals/latest'),
          api('/api/portfolio/performance'),
          api('/api/portfolio/features'),
          api('/api/portfolio/signals/latest/reasoning'),
        ])

        if (sumRes.status === 'fulfilled' && sumRes.value) setSummary(sumRes.value)
        if (posRes.status === 'fulfilled' && posRes.value) setPositions(posRes.value.positions || [])
        if (histRes.status === 'fulfilled' && histRes.value) setHistory(histRes.value.history || [])
        if (sigRes.status === 'fulfilled' && sigRes.value) setSignals(sigRes.value)
        if (perfRes.status === 'fulfilled' && perfRes.value) setMetrics(perfRes.value.metrics)
        if (featRes.status === 'fulfilled' && featRes.value) setFeatures(featRes.value.features)
        if (reasonRes.status === 'fulfilled' && reasonRes.value) setReasoning(reasonRes.value)
      } catch (err) {
        setError('Failed to load portfolio data.')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  return (
    <div className="min-h-screen bg-[#0F0F1A]">
      <ProjectNav />
      <Header />
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-[#94A3B8]">Loading portfolio data...</div>
          </div>
        )}

        {error && (
          <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-xl p-4 text-[#EF4444]">
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            <PortfolioSummary data={summary} />

            <EquityChart history={history} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <AllocationChart positions={positions} cash={summary?.cash} />
              <PositionsTable positions={positions} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SignalsPanel date={signals.date} signals={signals.signals} />
              <ModelMetrics metrics={metrics} />
            </div>

            <FeatureChart features={features} />

            <TradeReasoning date={reasoning.date} signals={reasoning.signals} />
          </>
        )}
      </main>
    </div>
  )
}

export default Dashboard
