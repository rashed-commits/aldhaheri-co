import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const COLORS = [
  '#7C3AED', '#3B82F6', '#10B981', '#F59E0B', '#EF4444',
  '#EC4899', '#06B6D4', '#8B5CF6', '#F97316', '#14B8A6',
  '#6366F1', '#84CC16',
]

const CASH_COLOR = '#475569'

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-lg px-4 py-3 shadow-lg">
      <p className="text-[#F1F5F9] font-semibold text-sm">{d.name}</p>
      <p className="text-[#94A3B8] text-xs">
        ${d.value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>
      <p className="text-[#94A3B8] text-xs">{d.percent.toFixed(1)}%</p>
    </div>
  )
}

function CustomLegend({ payload, data }) {
  return (
    <ul className="space-y-1.5 text-xs max-h-[280px] overflow-y-auto pr-2">
      {data.map((entry, i) => (
        <li key={entry.name} className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-sm flex-shrink-0"
            style={{ backgroundColor: entry.name === 'Cash' ? CASH_COLOR : COLORS[i % COLORS.length] }}
          />
          <span className="text-[#F1F5F9] font-medium truncate">{entry.name}</span>
          <span className="text-[#94A3B8] ml-auto whitespace-nowrap">
            {entry.percent.toFixed(1)}%
          </span>
        </li>
      ))}
    </ul>
  )
}

function AllocationChart({ positions, cash }) {
  if ((!positions || positions.length === 0) && (!cash || cash <= 0)) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Position Allocation</h2>
        <p className="text-[#94A3B8] text-sm">No allocation data available.</p>
      </div>
    )
  }

  const totalPositionValue = (positions || []).reduce((sum, p) => sum + (p.market_value || 0), 0)
  const totalValue = totalPositionValue + (cash || 0)

  const data = (positions || [])
    .filter(p => p.market_value > 0)
    .map(p => ({
      name: p.ticker,
      value: Math.round(p.market_value * 100) / 100,
      percent: totalValue > 0 ? (p.market_value / totalValue) * 100 : 0,
    }))
    .sort((a, b) => b.value - a.value)

  if (cash && cash > 0) {
    data.push({
      name: 'Cash',
      value: Math.round(cash * 100) / 100,
      percent: totalValue > 0 ? (cash / totalValue) * 100 : 0,
    })
  }

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-4 text-[#F1F5F9]">Position Allocation</h2>
      <div className="flex flex-col md:flex-row items-center gap-4">
        <div className="w-full md:w-1/2">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={110}
                paddingAngle={2}
                dataKey="value"
                stroke="#0F0F1A"
                strokeWidth={2}
              >
                {data.map((entry, i) => (
                  <Cell
                    key={entry.name}
                    fill={entry.name === 'Cash' ? CASH_COLOR : COLORS[i % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="w-full md:w-1/2">
          <CustomLegend data={data} />
        </div>
      </div>
    </div>
  )
}

export default AllocationChart
