import { useState, useEffect } from 'react'
import StockChart from './StockChart'


const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function StockCard({ symbol, onRemove }) {
  const [data, setData] = useState(null)        // stock price data
  const [error, setError] = useState(false)     // failed to fetch price
  const [showChart, setShowChart] = useState(false)



  useEffect(() => {
    fetch(`${API_URL}/stock/${symbol}`)
      .then(res => res.json())
      .then(data => setData(data))
      .catch(() => setError(true))
  }, [symbol])                                  // re-fetch if symbol changes

  const isPositive = data && data.change_pct >= 0

  return (
    <div className="stock-card-wrapper">
      <div className="stock-card" onClick={() => setShowChart(!showChart)}>  {/* toggle on click */}
        <div className="stock-info">
          <span className="stock-symbol">{symbol}</span>
          {data ? (
            <span className="stock-price">${data.price.toFixed(2)}</span>
          ) : error ? (
            <span className="stock-error">unavailable</span>
          ) : (
            <span className="stock-loading">loading...</span>
          )}
        </div>
        {data && (
          <span className={`stock-change ${isPositive ? 'positive' : 'negative'}`}>
            {isPositive ? '+' : ''}{data.change_pct.toFixed(2)}%
          </span>
        )}
        <button className="remove-btn" onClick={(e) => { e.stopPropagation(); onRemove(symbol) }}>×</button>
      </div>

      {showChart && <StockChart symbol={symbol} />}  {/* only render if showChart is true */}
    </div>
)

}

export default StockCard
