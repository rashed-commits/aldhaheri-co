import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-lg px-4 py-3 shadow-lg">
      <p className="text-[#94A3B8] text-xs mb-1">{label}</p>
      <p className="text-[#F1F5F9] font-semibold text-sm">
        ${payload[0].value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>
    </div>
  )
}

function EquityChart({ history }) {
  if (!history || history.length === 0) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Portfolio Value</h2>
        <p className="text-[#94A3B8] text-sm">No equity history available.</p>
      </div>
    )
  }

  const minEquity = Math.min(...history.map(d => d.equity))
  const maxEquity = Math.max(...history.map(d => d.equity))
  const padding = (maxEquity - minEquity) * 0.1 || 1000
  const yMin = Math.floor((minEquity - padding) / 100) * 100
  const yMax = Math.ceil((maxEquity + padding) / 100) * 100

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4 text-[#F1F5F9]">Portfolio Value</h2>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={history} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2D2D4E" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#94A3B8', fontSize: 12 }}
            tickLine={{ stroke: '#2D2D4E' }}
            axisLine={{ stroke: '#2D2D4E' }}
            tickFormatter={(val) => {
              const parts = val.split('-')
              return `${parts[1]}/${parts[2]}`
            }}
          />
          <YAxis
            domain={[yMin, yMax]}
            tick={{ fill: '#94A3B8', fontSize: 12 }}
            tickLine={{ stroke: '#2D2D4E' }}
            axisLine={{ stroke: '#2D2D4E' }}
            tickFormatter={(val) => `$${(val / 1000).toFixed(0)}k`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#7C3AED"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: '#7C3AED', stroke: '#0F0F1A', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default EquityChart
