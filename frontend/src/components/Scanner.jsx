import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Scanner() {
  const [movers, setMovers] = useState([])
  const [signals, setSignals] = useState([])
  const [news, setNews] = useState([])
  const [social, setSocial] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loadingRun, setLoadingRun] = useState(false)
  const [loadingSignals, setLoadingSignals] = useState(false)
  const [expandedSignalId, setExpandedSignalId] = useState(null)

  const loadAll = () => {
    fetch(`${API_URL}/scanner/movers?limit=25`).then(r => r.json()).then(setMovers).catch(() => setMovers([]))
    fetch(`${API_URL}/scanner/signals?limit=25`).then(r => r.json()).then(setSignals).catch(() => setSignals([]))
    fetch(`${API_URL}/news?limit=20`).then(r => r.json()).then(setNews).catch(() => setNews([]))
    fetch(`${API_URL}/social?limit=20`).then(r => r.json()).then(setSocial).catch(() => setSocial([]))
    fetch(`${API_URL}/alerts?limit=30`).then(r => r.json()).then(setAlerts).catch(() => setAlerts([]))
  }

  useEffect(() => {
    loadAll()
  }, [])

  const runScan = async () => {
    setLoadingRun(true)
    try {
      await fetch(`${API_URL}/scanner/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ window: '15m' }),
      })
      await fetch(`${API_URL}/news/ingest`, { method: 'POST' })
      loadAll()
    } finally {
      setLoadingRun(false)
    }
  }

  const generateSignals = async () => {
    setLoadingSignals(true)
    try {
      await fetch(`${API_URL}/scanner/signals/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 15 }),
      })
      loadAll()
    } finally {
      setLoadingSignals(false)
    }
  }

  const markRead = async (id) => {
    const res = await fetch(`${API_URL}/alerts/${id}/read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ read: true }),
    })
    if (res.ok) loadAll()
  }

  const formatVolume = (value) => {
    if (value === null || value === undefined) return 'N/A'
    const n = Number(value)
    if (Number.isNaN(n)) return 'N/A'
    if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return `${n.toFixed(0)}`
  }

  const moversBySymbol = movers.reduce((acc, m) => {
    acc[m.symbol] = m
    return acc
  }, {})

  return (
    <div className="scanner">
      <div className="scanner-actions">
        <button onClick={runScan} disabled={loadingRun}>{loadingRun ? 'Running scan...' : 'Run scan now'}</button>
        <button onClick={generateSignals} disabled={loadingSignals}>{loadingSignals ? 'Generating...' : 'Generate signals'}</button>
        <button onClick={loadAll}>Refresh</button>
      </div>

      <section className="scanner-section">
        <h3>Top Movers (Recommended)</h3>
        <p className="scanner-subtitle">These are the scanner’s recommended watch signals. Expand any row to see the reasoning.</p>
        {signals.length === 0 ? <p className="empty">No signals yet. Click “Generate signals”.</p> : signals.map(s => {
          const m = moversBySymbol[s.symbol]
          const isOpen = expandedSignalId === s.id
          return (
            <div key={s.id} className="scanner-card">
              <div className="scanner-row">
                <button
                  className="scanner-expand"
                  onClick={() => setExpandedSignalId(isOpen ? null : s.id)}
                  aria-expanded={isOpen}
                >
                  {isOpen ? '▾' : '▸'}
                </button>
                <strong>{s.symbol}</strong>
                <span className="scanner-meta">Type: {s.signal_type}</span>
                {s.confidence !== null && s.confidence !== undefined && (
                  <span className="scanner-meta">Conf: {Number(s.confidence).toFixed(2)}</span>
                )}
              </div>

              <div className="scanner-row">
                <span className="scanner-meta">Last Price: ${m?.last_price?.toFixed?.(2) ?? m?.last_price ?? 'N/A'}</span>
                <span className={m?.change_pct >= 0 ? 'positive' : 'negative'}>
                  Change: {m?.change_pct >= 0 ? '+' : ''}{Number(m?.change_pct || 0).toFixed(2)}%
                </span>
                <span className="scanner-meta">Vol: {formatVolume(m?.volume)}</span>
                <span className="scanner-meta">Avg Vol: {formatVolume(m?.avg_volume)}</span>
                <span className="scanner-meta">RVOL: {m?.relative_volume ?? 'N/A'}</span>
              </div>

              {isOpen && (
                <div className="scanner-details">
                  <p><strong>Reasoning</strong></p>
                  <p>{s.rationale}</p>
                  {s.catalysts && (
                    <>
                      <p><strong>Catalysts</strong></p>
                      <pre className="scanner-pre">{s.catalysts}</pre>
                    </>
                  )}
                  {s.key_levels && (
                    <>
                      <p><strong>Key levels</strong></p>
                      <pre className="scanner-pre">{s.key_levels}</pre>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </section>

      <section className="scanner-section">
        <h3>Latest News</h3>
        {news.length === 0 ? <p className="empty">No news yet.</p> : news.slice(0, 8).map(n => (
          <a key={n.id} className="scanner-link" href={n.url} target="_blank" rel="noreferrer">{n.title}</a>
        ))}
      </section>

      <section className="scanner-section">
        <h3>Social Pulse</h3>
        {social.length === 0 ? <p className="empty">No social posts yet.</p> : social.slice(0, 8).map(p => (
          <div key={p.id} className="scanner-card">
            <div className="scanner-row"><strong>{p.author || 'unknown'}</strong><span>{p.source}</span></div>
            <p>{p.content}</p>
          </div>
        ))}
      </section>

      <section className="scanner-section">
        <h3>Alerts Inbox</h3>
        {alerts.length === 0 ? <p className="empty">No alerts yet.</p> : alerts.map(a => (
          <div key={a.id} className="scanner-card">
            <div className="scanner-row">
              <strong>{a.title}</strong>
              {!a.read && <button onClick={() => markRead(a.id)}>Mark read</button>}
            </div>
            <p>{a.body}</p>
          </div>
        ))}
      </section>
    </div>
  )
}

export default Scanner
