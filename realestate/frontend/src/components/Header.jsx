function Header() {
  const now = new Date()
  const dateStr = now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <header
      style={{
        backgroundColor: '#16213e',
        borderBottom: '2px solid #2D2D4E',
        padding: '18px 24px 14px 24px',
      }}
    >
      <h1
        style={{
          fontSize: '22px',
          fontWeight: 700,
          color: '#F1F5F9',
          margin: 0,
          letterSpacing: '-0.01em',
        }}
      >
        UAE Real Estate — Daily Opportunity Report
      </h1>
      <p
        style={{
          fontSize: '13px',
          color: '#94A3B8',
          marginTop: '4px',
        }}
      >
        {dateStr}
      </p>
    </header>
  )
}

export default Header
