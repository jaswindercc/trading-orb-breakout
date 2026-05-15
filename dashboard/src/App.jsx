import { useState, useEffect } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import StrategyPage from './pages/StrategyPage'
import StockPage from './pages/StockPage'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']
const STRATEGY = 'Trend Rider v1'

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
        <div className="sidebar-section">
          <div className="sidebar-label">Strategy</div>
          <NavLink to="/" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            {STRATEGY}
          </NavLink>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-label">Stocks</div>
          {STOCKS.map(s => (
            <NavLink key={s} to={`/stock/${s}`} className={({isActive}) => isActive ? 'active' : ''}>
              {s}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="main">
        <Routes>
          <Route path="/" element={<StrategyPage data={data} strategyName={STRATEGY} />} />
          <Route path="/stock/:symbol" element={<StockPage data={data} />} />
        </Routes>
      </div>
    </div>
  )
}
