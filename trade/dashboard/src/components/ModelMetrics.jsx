function ModelMetrics({ metrics }) {
  if (!metrics) {
    return (
      <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
        <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Model Performance</h2>
        <p className="text-[#94A3B8] text-sm">No metrics available.</p>
      </div>
    )
  }

  // Support both flat and nested metric structures
  const getValue = (key) => {
    if (typeof metrics[key] === 'number') return metrics[key]
    if (typeof metrics[key] === 'object' && metrics[key] !== null) {
      return metrics[key].value || metrics[key].score || null
    }
    return null
  }

  const metricItems = [
    { label: 'Accuracy', key: 'accuracy' },
    { label: 'ROC-AUC', key: 'roc_auc' },
    { label: 'F1 Score', key: 'f1' },
    { label: 'Precision', key: 'precision' },
    { label: 'Recall', key: 'recall' },
  ]

  return (
    <div className="bg-[#1A1A2E] border border-[#2D2D4E] rounded-xl p-5">
      <h2 className="text-lg font-semibold mb-3 text-[#F1F5F9]">Model Performance</h2>
      <div className="space-y-3">
        {metricItems.map(({ label, key }) => {
          const val = getValue(key)
          if (val === null) return null
          const pct = (val * 100).toFixed(1)
          return (
            <div key={key}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-[#94A3B8]">{label}</span>
                <span className="font-medium">{pct}%</span>
              </div>
              <div className="w-full bg-[#2D2D4E] rounded-full h-2">
                <div
                  className="bg-[#7C3AED] h-2 rounded-full transition-all"
                  style={{ width: `${Math.min(100, pct)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default ModelMetrics
