import { useState, useRef, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function Chatbot({ watchlist }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! I can help you analyze your watchlist. Ask me anything, or drag a stock here to focus on it.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [focusedSymbol, setFocusedSymbol] = useState(null)   // symbol dropped into chat
  const bottomRef = useRef(null)                // ref to scroll to bottom of chat

  // auto scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleDragOver = (e) => e.preventDefault()           // required to allow dropping

  const handleDrop = (e) => {
    e.preventDefault()
    const symbol = e.dataTransfer.getData('symbol')           // retrieve symbol from drag event
    if (!symbol) return
    setFocusedSymbol(symbol)                                  // set focused symbol
    setMessages(prev => [...prev, {
      role: 'assistant',
      text: `Now focused on ${symbol}. Ask me anything about it.`
    }])
  }

  const clearFocus = () => setFocusedSymbol(null)             // clear focused symbol

  const sendMessage = (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMessage }])
    setLoading(true)

    fetch(`${API_URL}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage, focused_symbol: focusedSymbol }),  // send focused symbol
    })
      .then(res => res.json())
      .then(data => {
        setMessages(prev => [...prev, { role: 'assistant', text: data.response }])
      })
      .catch(() => {
        setMessages(prev => [...prev, { role: 'assistant', text: 'Something went wrong. Please try again.' }])
      })
      .finally(() => setLoading(false))
  }

  return (
    <div
      className="chatbot"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="chatbot-header">
        <h2>AI Assistant</h2>
        {focusedSymbol && (
          <div className="focused-symbol">
            <span>Focused: {focusedSymbol}</span>
            <button onClick={clearFocus}>×</button>
          </div>
        )}
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <p>{msg.text}</p>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <p className="typing">Thinking...</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input-form" onSubmit={sendMessage}>
        <input
          type="text"
          placeholder="Ask about your portfolio..."
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading}>Send</button>
      </form>
    </div>
  )
}

export default Chatbot
