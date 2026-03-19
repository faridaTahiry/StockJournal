import { useEffect } from 'react'
import AddStockForm from './AddStockForm'
import StockCard from './StockCard'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Watchlist({ watchlist, setWatchlist }) {

  useEffect(() => {
    fetch(`${API_URL}/watchlist`)
      .then(res => res.json())
      .then(data => setWatchlist(data))
  }, [])

  const removeStock = (symbol) => {
    fetch(`${API_URL}/watchlist/${symbol}`, { method: 'DELETE' })
      .then(res => {
        if (res.ok) {
          setWatchlist(watchlist.filter(item => item.symbol !== symbol))
        }
      })
  }

  return (
    <div className="watchlist">
      <h2>My Watchlist</h2>

      <AddStockForm watchlist={watchlist} setWatchlist={setWatchlist} />

      <div className="stock-list">
        {watchlist.length === 0 ? (
          <p className="empty">No stocks added yet.</p>
        ) : (
          watchlist.map(item => (
            <StockCard
              key={item.id}
              symbol={item.symbol}
              onRemove={removeStock}
            />
          ))
        )}
      </div>
    </div>
  )
}

export default Watchlist
