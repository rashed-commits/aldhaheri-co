import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function FeatureChart({ features }) {
  if (!features || features.length === 0) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Feature Importance</h2>
        <p className="text-[#94A3B8] text-sm">No feature data available.</p>
      </div>
    )
  }

  // Prepare data sorted descending, take top 15
  const data = features
    .slice(0, 15)
    .map((f) => ({
      name: f.feature || f.name || '',
      importance: f.importance || 0,
    }))
    .reverse() // reverse so highest is at top in horizontal bar chart

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Feature Importance (Top 15)</h2>
      <div style={{ width: '100%', height: Math.max(300, data.length * 28) }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
            <XAxis type="number" tick={{ fill: '#94A3B8', fontSize: 12 }} />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: '#94A3B8', fontSize: 11 }}
              width={90}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1A1A2E',
                border: '1px solid #2D2D4E',
                borderRadius: '6px',
                color: '#F1F5F9',
              }}
              formatter={(value) => [value.toFixed(4), 'Importance']}
            />
            <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
              {data.map((_, index) => (
                <Cell key={index} fill="#7C3AED" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default FeatureChart
