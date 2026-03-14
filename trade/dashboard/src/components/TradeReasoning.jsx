import { useState } from 'react'

function TradeReasoning({ date, signals }) {
  const [expanded, setExpanded] = useState(null)

  if (!signals || signals.length === 0) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Trade Reasoning</h2>
        <p className="text-[#94A3B8] text-sm">No reasoning data available. Reasoning is generated with each signal run.</p>
      </div>
    )
  }

  const signalColor = (signal) => {
    switch (signal) {
      case 'BUY': return 'text-[#10B981] bg-[#10B981]/10 border-[#10B981]/30'
      case 'SELL': return 'text-[#EF4444] bg-[#EF4444]/10 border-[#EF4444]/30'
      case 'HOLD': return 'text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/30'
      default: return 'text-[#94A3B8]'
    }
  }

  const indicatorIcon = (indicator) => {
    const icons = {
      'RSI': '📊',
      'MACD': '📈',
      'Bollinger Bands': '📉',
      'Volume': '📶',
      '1-Day Return': '⚡',
      '5-Day Return': '🔄',
      'VIX': '🌡️',
      'Relative Strength (20d)': '💪',
      'ATR': '🎯',
    }
    return icons[indicator] || '•'
  }

  // Only show signals with reasoning
  const actionSignals = signals.filter(s => s.reasoning && s.reasoning.length > 0)

  if (actionSignals.length === 0) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Trade Reasoning</h2>
        <p className="text-[#94A3B8] text-sm">No reasoning data available yet.</p>
      </div>
    )
  }

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-1 text-[#F1F5F9]">Trade Reasoning</h2>
      <p className="text-xs text-[#94A3B8] mb-4">
        Why the model made each decision on {date || 'the latest run'}
      </p>

      <div className="space-y-3">
        {actionSignals.map((sig, i) => (
          <div
            key={i}
            className={`border rounded-lg overflow-hidden transition-all ${
              expanded === i ? 'border-[#7C3AED]/50' : 'border-[#2D2D4E]'
            }`}
          >
            {/* Header row — clickable */}
            <button
              onClick={() => setExpanded(expanded === i ? null : i)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#2D2D4E]/30 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-[#F1F5F9] font-semibold text-sm">{sig.ticker}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${signalColor(sig.signal)}`}>
                  {sig.signal}
                </span>
                <span className="text-[#94A3B8] text-xs">
                  {(sig.prob_up * 100).toFixed(1)}% conviction
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[#94A3B8] text-xs">
                  {sig.reasoning.length} factor{sig.reasoning.length !== 1 ? 's' : ''}
                </span>
                <svg
                  className={`w-4 h-4 text-[#94A3B8] transition-transform ${expanded === i ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </button>

            {/* Expanded reasoning factors */}
            {expanded === i && (
              <div className="px-4 pb-4 space-y-2 border-t border-[#2D2D4E]">
                <div className="pt-3">
                  {sig.reasoning.map((factor, j) => (
                    <div key={j} className="flex items-start gap-3 py-2">
                      <span className="text-base mt-0.5 shrink-0">{indicatorIcon(factor.indicator)}</span>
                      <div className="min-w-0">
                        <div className="flex items-baseline gap-2">
                          <span className="text-[#A78BFA] text-sm font-medium">{factor.indicator}</span>
                          <span className="text-[#F1F5F9] text-sm font-mono">{factor.value}</span>
                        </div>
                        <p className="text-[#94A3B8] text-xs mt-0.5">{factor.interpretation}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default TradeReasoning
