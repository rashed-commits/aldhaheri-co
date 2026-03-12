function StatCard({ label, value, subValue, color }) {
  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
      <div className="text-sm text-[#94A3B8] mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color || 'text-[#F1F5F9]'}`}>
        {value}
      </div>
      {subValue && (
        <div className={`text-sm mt-1 ${color || 'text-[#94A3B8]'}`}>
          {subValue}
        </div>
      )}
    </div>
  )
}

function PortfolioSummary({ data }) {
  if (!data) return null

  const pnlColor = data.total_pnl >= 0 ? 'text-[#4CAF7D]' : 'text-[#E05C5C]'
  const dailyColor = data.daily_pnl >= 0 ? 'text-[#4CAF7D]' : 'text-[#E05C5C]'

  const formatCurrency = (val) =>
    '$' + Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  const formatPnl = (val) => {
    const arrow = val >= 0 ? '\u2191' : '\u2193'
    const sign = val >= 0 ? '+$' : '-$'
    const formatted = Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return `${arrow} ${sign}${formatted}`
  }

  const formatPct = (val) => {
    const arrow = val >= 0 ? '\u2191' : '\u2193'
    const sign = val >= 0 ? '+' : ''
    return `${arrow} ${sign}${val.toFixed(2)}%`
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        label="Total Equity"
        value={formatCurrency(data.equity)}
      />
      <StatCard
        label="Cash"
        value={formatCurrency(data.cash)}
      />
      <StatCard
        label="Total P&L"
        value={formatPnl(data.total_pnl)}
        subValue={formatPct(data.total_pct)}
        color={pnlColor}
      />
      <StatCard
        label="Daily P&L"
        value={formatPnl(data.daily_pnl)}
        subValue={formatPct(data.daily_pct)}
        color={dailyColor}
      />
    </div>
  )
}

export default PortfolioSummary
