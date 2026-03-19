import { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function AddStockForm({ watchlist, setWatchlist }) {
  const [symbol, setSymbol] = useState('')        // controlled input value
  const [error, setError] = useState('')          // error message
  const [loading, setLoading] = useState(false)   // loading state while request is in flight

  const handleSubmit = (e) => {
    e.preventDefault()                            // prevent page reload on form submit
    setError('')

    const upper = symbol.trim().toUpperCase()
    if (!upper) return

    // check if already in watchlist
    if (watchlist.some(item => item.symbol === upper)) {
      setError(`${upper} is already in your watchlist`)
      return
    }

    setLoading(true)

    fetch(`${API_URL}/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: upper }),
    })
      .then(res => {
        if (!res.ok) return res.json().then(err => { throw new Error(err.detail) })
        return res.json()
      })
      .then(data => {
        setWatchlist([...watchlist, data])        // add new stock to state
        setSymbol('')                             // clear input
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  return (
    <form className="add-stock-form" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Add ticker e.g. AAPL"
        value={symbol}
        onChange={e => setSymbol(e.target.value)}
        disabled={loading}
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Adding...' : '+'}
      </button>
      {error && <p className="form-error">{error}</p>}
    </form>
  )
}

export default AddStockForm
