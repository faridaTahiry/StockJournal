import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Brush } from 'recharts'


const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function StockChart({symbol}){
    const [data, setData] = useState([])
    const [loading, setLoading] = useState(true)
    const [mode, setMode] = useState('3mo')                                   // active button: '1d', '7d', '1mo', '3mo'

    const fetchData = (sym, period, interval) => {
        setLoading(true)
        fetch(`${API_URL}/stock/${sym}/history?period=${period}&interval=${interval}`)
          .then(res => res.json())
          .then(data => setData(data))
          .finally(() => setLoading(false))
    }

    // fetch on symbol or mode change
    useEffect(() => {
        if (mode === '1d')  fetchData(symbol, '1d',  '1h')                   // 1 day hourly
        if (mode === '7d')  fetchData(symbol, '7d',  '1h')                   // 7 days hourly
        if (mode === '1mo') fetchData(symbol, '1mo', '1d')                   // 1 month daily
        if (mode === '3mo') fetchData(symbol, '3mo', '1d')                   // 3 months daily
    }, [symbol, mode])



    return (
    <div className="stock-chart">

      <div className="chart-controls">
        {[['1d', '1D'], ['7d', '7D'], ['1mo', '1M'], ['3mo', '3M']].map(([value, label]) => (
          <button
            key={value}
            className={`period-btn ${mode === value ? 'active' : ''}`}
            onClick={() => setMode(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* chart or loading message */}
      {loading ? (
        <p className="chart-loading">Loading chart...</p>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data}>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#555' }} tickFormatter={d => d.slice(5)} />
            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10, fill: '#555' }} tickFormatter={v => `$${v}`} width={55} />
            <Tooltip formatter={v => [`$${v}`, 'Close']} contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '6px' }} />
            <Line type="monotone" dataKey="close" stroke="#ffffff" dot={false} strokeWidth={1.5} />
            <Brush
            dataKey="date"
            height={15}
            stroke="#ffffff"
            travellerWidth={6}
            fill="#2a2a2a"
            strokeWidth={1}
            fillOpacity={0.3}
            tickFormatter={() => ''}
            />

          </LineChart>
        </ResponsiveContainer>
      )}

    </div>
)

}

export default StockChart