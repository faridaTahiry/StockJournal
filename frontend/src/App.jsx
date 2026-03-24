import { useState } from 'react'        // useState is React's way of storing data that can change — like a reactive variable
import Watchlist from './components/Watchlist'   // left panel component
import Chatbot from './components/Chatbot'       // right panel component
import Scanner from './components/Scanner'
import './index.css'                             // global styles

function App() {
  const [watchlist, setWatchlist] = useState([])  // stores the list of stocks — shared between both panels
  const [view, setView] = useState('scanner')

  return (
    <div className="app">

      <header className="app-header">
        <h1>Stock Journal</h1>
        <div className="app-nav">
          <button className={view === 'journal' ? 'active' : ''} onClick={() => setView('journal')}>Journal</button>
          <button className={view === 'scanner' ? 'active' : ''} onClick={() => setView('scanner')}>Scanner</button>
        </div>
      </header>

      {view === 'journal' ? (
        <main className="app-body">
          <section className="panel left-panel">
            <Watchlist watchlist={watchlist} setWatchlist={setWatchlist} />
          </section>
          <section className="panel right-panel">
            <Chatbot />
          </section>
        </main>
      ) : (
        <main className="app-body scanner-body">
          <section className="panel scanner-panel">
            <Scanner />
          </section>
        </main>
      )}

    </div>
  )
}

export default App
