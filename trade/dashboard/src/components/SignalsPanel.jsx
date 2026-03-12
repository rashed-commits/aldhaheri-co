function SignalsPanel({ date, signals }) {
  if (!signals || signals.length === 0) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Latest Signals</h2>
        <p className="text-[#94A3B8] text-sm">No signals available.</p>
      </div>
    )
  }

  const signalColor = (signal) => {
    switch (signal) {
      case 'BUY': return 'text-[#10B981] bg-[#10B981]/10'
      case 'SELL': return 'text-[#EF4444] bg-[#EF4444]/10'
      case 'HOLD': return 'text-[#F59E0B] bg-[#F59E0B]/10'
      default: return 'text-[#94A3B8]'
    }
  }

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5 overflow-x-auto">
      <h2 className="text-lg font-semibold mb-1 text-[#F1F5F9]">Latest Signals</h2>
      <p className="text-xs text-[#94A3B8] mb-3">{date || 'Unknown date'}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[#94A3B8] border-b border-[#2D2D4E]">
            <th className="text-left py-2 px-3">Ticker</th>
            <th className="text-center py-2 px-3">Signal</th>
            <th className="text-right py-2 px-3">Probability</th>
            <th className="text-right py-2 px-3">Close</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((sig, i) => (
            <tr key={i} className="border-b border-[#2D2D4E]/50 hover:bg-[#2D2D4E]/20">
              <td className="py-2 px-3 font-medium">{sig.ticker}</td>
              <td className="py-2 px-3 text-center">
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${signalColor(sig.signal)}`}>
                  {sig.signal}
                </span>
              </td>
              <td className="py-2 px-3 text-right">{(sig.prob_up * 100).toFixed(1)}%</td>
              <td className="py-2 px-3 text-right">${sig.close?.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default SignalsPanel
