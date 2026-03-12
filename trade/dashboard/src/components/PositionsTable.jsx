function PositionsTable({ positions }) {
  if (!positions || positions.length === 0) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Current Positions</h2>
        <p className="text-[#94A3B8] text-sm">No open positions.</p>
      </div>
    )
  }

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5 overflow-x-auto">
      <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Current Positions</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[#94A3B8] border-b border-[#2D2D4E]">
            <th className="text-left py-2 px-3">Ticker</th>
            <th className="text-right py-2 px-3">Qty</th>
            <th className="text-right py-2 px-3">Entry Price</th>
            <th className="text-right py-2 px-3">Current Price</th>
            <th className="text-right py-2 px-3">P&L</th>
            <th className="text-right py-2 px-3">Entry Date</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos, i) => {
            const pnl = pos.unrealized_pl || 0
            const pnlColor = pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
            return (
              <tr key={i} className="border-b border-[#2D2D4E]/50 hover:bg-[#2D2D4E]/20">
                <td className="py-2 px-3 font-medium">{pos.ticker}</td>
                <td className="py-2 px-3 text-right">{pos.qty}</td>
                <td className="py-2 px-3 text-right">${pos.entry_price?.toFixed(2)}</td>
                <td className="py-2 px-3 text-right">${pos.current_price?.toFixed(2)}</td>
                <td className={`py-2 px-3 text-right font-medium ${pnlColor}`}>
                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                </td>
                <td className="py-2 px-3 text-right text-[#94A3B8]">
                  {pos.entry_date || '--'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default PositionsTable
