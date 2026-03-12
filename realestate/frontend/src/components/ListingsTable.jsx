import { useState, useMemo } from 'react'

function fmtPrice(price) {
  if (!price) return '—'
  if (price >= 1_000_000) return `${(price / 1_000_000).toFixed(2)}M`
  if (price >= 1_000) return `${Math.round(price / 1_000).toLocaleString()}K`
  return price.toLocaleString()
}

function fmtNum(val) {
  if (val === null || val === undefined) return '—'
  return Math.round(val).toLocaleString()
}

function fmtPct(val) {
  if (!val) return '—'
  return `${val > 0 ? '+' : ''}${val.toFixed(1)}%`
}

function ListingsTable({ listings, areas, title, showStar }) {
  const [sortField, setSortField] = useState('discount_pct')
  const [sortDir, setSortDir] = useState('desc')

  // Build area avg lookup
  const areaAvgMap = useMemo(() => {
    const map = {}
    if (areas) {
      areas.forEach(a => {
        const key = `${a.city}|${a.area_name}`
        map[key] = a.avg_price_per_sqft || 0
      })
    }
    return map
  }, [areas])

  if (!listings || listings.length === 0) {
    return (
      <div
        style={{
          backgroundColor: '#1A1A2E',
          border: '1px solid #2D2D4E',
          borderRadius: '6px',
          padding: '24px',
          textAlign: 'center',
          color: '#94A3B8',
        }}
      >
        No listings available
      </div>
    )
  }

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  // Enrich listings with computed fields
  const enriched = listings.map(l => {
    const areaKey = `${l.city}|${l.area_name}`
    const areaAvgPsf = areaAvgMap[areaKey] || 0
    const psf = l.price_per_sqft || (l.price && l.area_sqft ? l.price / l.area_sqft : 0)
    const discountPct = areaAvgPsf > 0 && psf > 0 ? ((psf - areaAvgPsf) / areaAvgPsf) * 100 : 0
    // Simple score: bigger discount below avg = higher score
    // This is a rough approximation since the backend scoring isn't exposed via API
    const discountScore = discountPct < 0 ? Math.min(Math.abs(discountPct) * 2, 40) : 0
    const offplanBonus = l.is_offplan ? 15 : 0
    const score = Math.min(Math.round(discountScore + offplanBonus + 30), 100)
    return {
      ...l,
      psf,
      area_avg_psf: areaAvgPsf,
      discount_pct: discountPct,
      score,
    }
  })

  const sorted = [...enriched].sort((a, b) => {
    let aVal = a[sortField] ?? 0
    let bVal = b[sortField] ?? 0
    if (typeof aVal === 'string') aVal = aVal.toLowerCase()
    if (typeof bVal === 'string') bVal = bVal.toLowerCase()
    if (sortDir === 'asc') return aVal > bVal ? 1 : -1
    return aVal < bVal ? 1 : -1
  })

  const SortArrow = ({ field }) => {
    if (sortField !== field) return null
    return <span className="sort-arrow">{sortDir === 'asc' ? '▲' : '▼'}</span>
  }

  const columns = [
    { key: null, label: '#', sortable: false, cls: '' },
    { key: 'title', label: 'Listing', sortable: false, cls: 'text-left' },
    { key: 'area_name', label: 'Area', sortable: true, cls: 'text-left' },
    { key: 'property_type', label: 'Type', sortable: true, cls: '' },
    { key: 'bedrooms', label: 'Beds', sortable: true, cls: '' },
    { key: 'price', label: 'Price (AED)', sortable: true, cls: 'text-right' },
    { key: 'area_sqft', label: 'Size (sqft)', sortable: true, cls: 'text-right' },
    { key: 'psf', label: 'AED/sqft', sortable: true, cls: 'text-right' },
    { key: 'area_avg_psf', label: 'Area Avg', sortable: true, cls: 'text-right' },
    { key: 'discount_pct', label: 'Disc.', sortable: true, cls: '' },
    { key: 'score', label: 'Score', sortable: true, cls: '' },
  ]

  return (
    <div>
      <div className="section-header">
        {showStar && <span className="star">★</span>}
        {title}
      </div>
      <div className="table-wrapper">
        <table className="report-table">
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th
                  key={i}
                  className={`${col.cls} ${col.sortable ? 'sortable-header' : ''}`}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                >
                  {col.label}
                  {col.sortable && <SortArrow field={col.key} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((listing, idx) => {
              const cityCode = listing.city === 'abu-dhabi' ? 'AD' : 'DXB'
              const ptype = (listing.property_type || '—')
              const typeDisplay = ptype.length > 6 ? ptype.slice(0, 5) + '.' : ptype
              const scoreGood = listing.score >= 60

              return (
                <tr
                  key={listing.id || idx}
                  className={idx % 2 === 0 ? 'row-odd' : 'row-even'}
                >
                  <td className="cell-num">{idx + 1}</td>
                  <td className="cell-title">
                    {listing.url ? (
                      <a href={listing.url} target="_blank" rel="noopener noreferrer">
                        {listing.title || 'Untitled'}
                      </a>
                    ) : (
                      listing.title || 'Untitled'
                    )}
                  </td>
                  <td className="cell-area">
                    {listing.area_name || '—'}
                    <span className="city-code">{cityCode}</span>
                    {listing.is_offplan ? <span className="offplan-star">★</span> : null}
                  </td>
                  <td className="cell-center" style={{ textTransform: 'capitalize', fontSize: '11px' }}>
                    {typeDisplay}
                  </td>
                  <td className="cell-center">
                    {listing.bedrooms ?? '—'}
                  </td>
                  <td className="cell-price">
                    {fmtPrice(listing.price)}
                  </td>
                  <td className="cell-right">
                    {listing.area_sqft ? fmtNum(listing.area_sqft) : '—'}
                  </td>
                  <td className="cell-right">
                    {listing.psf ? fmtNum(listing.psf) : '—'}
                  </td>
                  <td className="cell-right" style={{ color: '#94A3B8' }}>
                    {listing.area_avg_psf ? fmtNum(listing.area_avg_psf) : '—'}
                  </td>
                  <td className="cell-center" style={{
                    color: listing.discount_pct < 0 ? '#2d6a4f' : listing.discount_pct > 0 ? '#e76f51' : '#94A3B8',
                    fontWeight: listing.discount_pct !== 0 ? 600 : 400,
                    fontSize: '11px',
                  }}>
                    {listing.discount_pct !== 0 ? fmtPct(listing.discount_pct) : '—'}
                  </td>
                  <td className="cell-score">
                    <span className={scoreGood ? 'score-good' : 'score-ok'}>
                      {listing.score}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default ListingsTable
