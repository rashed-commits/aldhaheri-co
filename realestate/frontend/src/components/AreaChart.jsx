import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const COLORS = {
  abuDhabi: '#7C3AED',
  dubai: '#A78BFA',
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload
  return (
    <div
      style={{
        backgroundColor: '#16213e',
        border: '1px solid #2D2D4E',
        borderRadius: '6px',
        padding: '10px 14px',
        fontSize: '12px',
      }}
    >
      <p style={{ color: '#F1F5F9', fontWeight: 600, marginBottom: '4px' }}>{data.area_name}</p>
      <p style={{ color: '#94A3B8' }}>City: {data.city}</p>
      <p style={{ color: '#A78BFA' }}>Avg: AED {data.avg_price_per_sqft?.toLocaleString()}/sqft</p>
      <p style={{ color: '#94A3B8' }}>{data.listing_count} listings</p>
    </div>
  )
}

function AreaBenchmarkChart({ areas }) {
  if (!areas || areas.length === 0) {
    return (
      <div
        style={{
          backgroundColor: '#1A1A2E',
          border: '1px solid #2D2D4E',
          borderRadius: '6px',
          padding: '32px',
          textAlign: 'center',
          color: '#94A3B8',
        }}
      >
        No area data available
      </div>
    )
  }

  // Take top 15 areas by listing count, sorted by avg PSF
  const data = areas
    .slice(0, 15)
    .sort((a, b) => (b.avg_price_per_sqft || 0) - (a.avg_price_per_sqft || 0))

  return (
    <div
      style={{
        backgroundColor: '#1A1A2E',
        border: '1px solid #2D2D4E',
        borderRadius: '6px',
        padding: '16px',
      }}
    >
      <h3
        style={{
          fontSize: '14px',
          fontWeight: 600,
          color: '#c4b5fd',
          marginBottom: '16px',
        }}
      >
        Average Price/sqft by Area (Sale)
      </h3>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2D2D4E" />
          <XAxis
            dataKey="area_name"
            tick={{ fill: '#94A3B8', fontSize: 10 }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis
            tick={{ fill: '#94A3B8', fontSize: 10 }}
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="avg_price_per_sqft" radius={[3, 3, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.city === 'abu-dhabi' ? COLORS.abuDhabi : COLORS.dubai}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', gap: '24px', justifyContent: 'center', marginTop: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: COLORS.abuDhabi }} />
          <span style={{ fontSize: '11px', color: '#94A3B8' }}>Abu Dhabi</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: COLORS.dubai }} />
          <span style={{ fontSize: '11px', color: '#94A3B8' }}>Dubai</span>
        </div>
      </div>
    </div>
  )
}

export default AreaBenchmarkChart
