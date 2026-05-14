import { useState, useEffect } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Overview from './pages/Overview'
import StockPage from './pages/StockPage'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

export default function App() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch('/data.json')
      .then(r => r.json())
      .then(setData)
  }, [])

  if (!data) return <div className="loading">Loading…</div>

  return (
    <div className="app">
      <nav className="sidebar">
        <h2>ORB v3 Asym</h2>
        <NavLink to="/" end className={({isActive}) => isActive ? 'active' : ''}>
          Overview
        </NavLink>
        {STOCKS.map(s => (
          <NavLink key={s} to={`/stock/${s}`} className={({isActive}) => isActive ? 'active' : ''}>
            {s}
          </NavLink>
        ))}
      </nav>
      <div className="main">
        <Routes>
          <Route path="/" element={<Overview data={data} />} />
          <Route path="/stock/:symbol" element={<StockPage data={data} />} />
        </Routes>
      </div>
    </div>
  )
}
