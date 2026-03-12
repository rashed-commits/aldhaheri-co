function StatsBar({ stats, listings, areas }) {
  if (!stats) return null

  const cities = stats.by_city?.length || 0
  const areaCount = areas?.length || 0
  const activeListings = stats.active_listings || 0

  // Compute rough scores from listings data
  const offplanCount = listings?.filter(l => l.is_offplan).length || 0
  const secondaryCount = listings?.filter(l => !l.is_offplan).length || 0

  // Compute avg price per sqft as a proxy stat
  const avgPsf = stats.avg_price_per_sqft
    ? `AED ${Math.round(stats.avg_price_per_sqft).toLocaleString()}`
    : 'N/A'

  return (
    <div className="summary-row">
      <div className="summary-cell">
        <div className="label">Listings</div>
        <div className="value">{activeListings.toLocaleString()}</div>
      </div>
      <div className="summary-cell">
        <div className="label">Off-Plan</div>
        <div className="value">{offplanCount}</div>
      </div>
      <div className="summary-cell">
        <div className="label">Secondary</div>
        <div className="value">{secondaryCount}</div>
      </div>
      <div className="summary-cell">
        <div className="label">Avg PSF</div>
        <div className="value" style={{ fontSize: '14px' }}>{avgPsf}</div>
      </div>
      <div className="summary-cell">
        <div className="label">Cities</div>
        <div className="value">{cities}</div>
      </div>
      <div className="summary-cell">
        <div className="label">Areas</div>
        <div className="value">{areaCount}</div>
      </div>
      <div className="summary-cell">
        <div className="label">Scoring Weights</div>
        <div className="value small-text">Yield 40% · Discount 25% · Drop 20% · Off-plan 15%</div>
      </div>
    </div>
  )
}

export default StatsBar
