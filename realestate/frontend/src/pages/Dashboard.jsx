import { useEffect, useState, useMemo } from 'react'
import api from '../api'
import ProjectNav from '../components/ProjectNav'
import Header from '../components/Header'
import StatsBar from '../components/StatsBar'
import ListingsTable from '../components/ListingsTable'
import AreaBenchmarkChart from '../components/AreaChart'

function Dashboard() {
  const [stats, setStats] = useState(null)
  const [listings, setListings] = useState([])
  const [areas, setAreas] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsData, listingsData, areasData] = await Promise.all([
          api('/api/stats'),
          api('/api/listings?purpose=sale&limit=50'),
          api('/api/areas?purpose=sale'),
        ])
        if (!statsData || !listingsData || !areasData) return
        setStats(statsData)
        setListings(listingsData.listings || [])
        setAreas(areasData.areas || [])
      } catch (err) {
        console.error('Failed to fetch data:', err)
        setError(err.message || 'Failed to load data')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // Split listings into off-plan and secondary
  const offplanListings = useMemo(() => listings.filter(l => l.is_offplan), [listings])
  const secondaryListings = useMemo(() => listings.filter(l => !l.is_offplan), [listings])

  // City breakdown for stats panel
  const cityBreakdown = stats?.by_city || []

  const now = new Date()
  const dateTimeStr = now.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  })

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0F0F1A' }}>
      <ProjectNav />
      <Header />

      <main style={{ maxWidth: '1440px', margin: '0 auto', padding: '16px 20px 40px 20px' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '80px 0' }}>
            <div style={{ color: '#94A3B8', fontSize: '14px' }}>Loading dashboard...</div>
          </div>
        ) : error ? (
          <div
            style={{
              backgroundColor: '#1A1A2E',
              border: '1px solid #EF4444',
              borderRadius: '6px',
              padding: '24px',
              textAlign: 'center',
              color: '#EF4444',
            }}
          >
            {error}
          </div>
        ) : (
          <>
            {/* Summary Stats Row (PDF-style) */}
            <div style={{ marginBottom: '8px' }}>
              <StatsBar stats={stats} listings={listings} areas={areas} />
            </div>

            {/* Off-Plan Opportunities Table */}
            <ListingsTable
              listings={offplanListings}
              areas={areas}
              title="Top Off-Plan Opportunities"
              showStar={true}
            />

            {/* Secondary / Ready Opportunities Table */}
            <ListingsTable
              listings={secondaryListings}
              areas={areas}
              title="Top Secondary / Ready Opportunities"
              showStar={false}
            />

            {/* Charts row */}
            <div style={{ marginTop: '28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              {/* Area Benchmarks Chart */}
              <AreaBenchmarkChart areas={areas} />

              {/* City Distribution */}
              <div
                style={{
                  backgroundColor: '#1A1A2E',
                  border: '1px solid #2D2D4E',
                  borderRadius: '6px',
                  padding: '16px',
                }}
              >
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#c4b5fd', marginBottom: '16px' }}>
                  Distribution by City
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {cityBreakdown.map((city) => {
                    const total = stats.active_listings || 1
                    const pct = ((city.cnt / total) * 100).toFixed(1)
                    return (
                      <div key={city.city}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontSize: '12px', color: '#F1F5F9', textTransform: 'capitalize' }}>
                            {city.city?.replace('-', ' ')}
                          </span>
                          <span style={{ fontSize: '12px', color: '#94A3B8' }}>
                            {city.cnt.toLocaleString()} ({pct}%)
                          </span>
                        </div>
                        <div style={{ width: '100%', height: '6px', borderRadius: '3px', backgroundColor: '#2D2D4E' }}>
                          <div
                            style={{
                              height: '6px',
                              borderRadius: '3px',
                              width: `${pct}%`,
                              backgroundColor: city.city === 'abu-dhabi' ? '#7C3AED' : '#A78BFA',
                              transition: 'width 0.3s ease',
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}

                  {/* By purpose */}
                  <div style={{ paddingTop: '12px', marginTop: '4px', borderTop: '1px solid #2D2D4E' }}>
                    <h4 style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', marginBottom: '8px' }}>
                      By Purpose
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      {stats.by_purpose?.map((p) => (
                        <div
                          key={p.purpose}
                          style={{
                            backgroundColor: '#0F0F1A',
                            border: '1px solid #2D2D4E',
                            borderRadius: '6px',
                            padding: '10px',
                            textAlign: 'center',
                          }}
                        >
                          <p style={{ fontSize: '16px', fontWeight: 700, color: '#F1F5F9' }}>
                            {p.cnt.toLocaleString()}
                          </p>
                          <p style={{ fontSize: '11px', color: '#94A3B8', textTransform: 'capitalize' }}>
                            {p.purpose}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* By type */}
                  <div style={{ paddingTop: '12px', marginTop: '4px', borderTop: '1px solid #2D2D4E' }}>
                    <h4 style={{ fontSize: '11px', fontWeight: 600, color: '#94A3B8', marginBottom: '8px' }}>
                      By Property Type
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {stats.by_type?.slice(0, 5).map((t) => (
                        <div key={t.property_type} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                          <span style={{ color: '#F1F5F9', textTransform: 'capitalize' }}>
                            {t.property_type}
                          </span>
                          <span style={{ color: '#94A3B8' }}>{t.cnt.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer matching PDF */}
            <div className="report-footer">
              <span>Generated by UAE Real Estate Monitor — {dateTimeStr}</span>
              <span>·</span>
              <span style={{ color: '#facc15' }}>★</span>
              <span>= Off-plan</span>
              <span>·</span>
              <span>AD = Abu Dhabi</span>
              <span>·</span>
              <span>DXB = Dubai</span>
              <span>·</span>
              <span style={{ color: '#2d6a4f', fontWeight: 600 }}>60+</span>
              <span>= Good Score</span>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default Dashboard
