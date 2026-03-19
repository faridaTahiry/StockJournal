import { useState } from 'react'        // useState is React's way of storing data that can change — like a reactive variable
import Watchlist from './components/Watchlist'   // left panel component
import Chatbot from './components/Chatbot'       // right panel component
import './index.css'                             // global styles

function App() {
  const [watchlist, setWatchlist] = useState([])  // stores the list of stocks — shared between both panels

  return (
    <div className="app">

      <header className="app-header">
        <h1>Stock Journal</h1>
      </header>

      <main className="app-body">

        <section className="panel left-panel">
          <Watchlist watchlist={watchlist} setWatchlist={setWatchlist} />  {/* pass watchlist data down */}
        </section>

        <section className="panel right-panel">
          <Chatbot watchlist={watchlist} />  {/* chatbot only needs to read the watchlist */}
        </section>

      </main>

    </div>
  )
}

export default App
