import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import StrategyPage from './pages/StrategyPage'
import BouncePage from './pages/BouncePage'
import BreakoutPage from './pages/BreakoutPage'
import RsiPage from './pages/RsiPage'
import MeanRevPage from './pages/MeanRevPage'
import ComparePage from './pages/ComparePage'
import FilterLabPage from './pages/FilterLabPage'
import MasterLearningsPage from './pages/MasterLearningsPage'
import StockPage from './pages/StockPage'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

const STRATS = [
  { path: '/', label: 'Trend Rider v1', prefix: '' },
  { path: '/bounce', label: 'MA Bounce v1', prefix: 'bounce' },
  { path: '/breakout', label: 'Breakout v1', prefix: 'breakout' },
  { path: '/rsi', label: 'RSI Trend v1', prefix: 'rsi' },
  { path: '/meanrev', label: 'Mean Rev v1', prefix: 'meanrev' },
]

export default function App() {
  const [trData, setTrData] = useState(null)
  const [bnData, setBnData] = useState(null)
  const [brData, setBrData] = useState(null)
  const [rsiData, setRsiData] = useState(null)
  const [mrData, setMrData] = useState(null)
  const location = useLocation()

  useEffect(() => {
    fetch('/data.json').then(r => r.json()).then(setTrData)
    fetch('/bounce_data.json').then(r => r.json()).then(setBnData)
    fetch('/breakout_data.json').then(r => r.json()).then(setBrData)
    fetch('/rsi_data.json').then(r => r.json()).then(setRsiData)
    fetch('/meanrev_data.json').then(r => r.json()).then(setMrData)
  }, [])

  if (!trData || !bnData || !brData || !rsiData || !mrData) return <div className="loading">Loading…</div>

  // Detect active strategy from URL
  const active = STRATS.find(s => s.prefix && location.pathname.startsWith(s.path)) || STRATS[0]
  const stockBase = active.prefix ? `/${active.prefix}/stock` : '/stock'

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="sidebar-section">
          <div className="sidebar-label">Strategies</div>
          {STRATS.map(s => (
            <NavLink key={s.path} to={s.path} end className={({isActive}) =>
              `strategy-link ${(s.path === '/' ? isActive && active === s : isActive) ? 'active' : ''}`
            }>{s.label}</NavLink>
          ))}
          <NavLink to="/compare" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            ⚔️ Compare
          </NavLink>
          <NavLink to="/filterlab" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            🧪 Filter Lab
          </NavLink>
          <NavLink to="/learnings" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            📖 Master Learnings
          </NavLink>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-label">Stocks ({active.label})</div>
          {STOCKS.map(s => (
            <NavLink key={s} to={`${stockBase}/${s}`} className={({isActive}) => isActive ? 'active' : ''}>
              {s}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className="main">
        <Routes>
          <Route path="/" element={<StrategyPage data={trData} strategyName="Trend Rider v1" />} />
          <Route path="/stock/:symbol" element={<StockPage data={trData} strategy="Trend Rider v1" />} />
          <Route path="/bounce" element={<BouncePage data={bnData} strategyName="MA Bounce v1" />} />
          <Route path="/bounce/stock/:symbol" element={<StockPage data={bnData} strategy="MA Bounce v1" />} />
          <Route path="/breakout" element={<BreakoutPage data={brData} strategyName="Breakout v1" />} />
          <Route path="/breakout/stock/:symbol" element={<StockPage data={brData} strategy="Breakout v1" />} />
          <Route path="/rsi" element={<RsiPage data={rsiData} strategyName="RSI Trend v1" />} />
          <Route path="/rsi/stock/:symbol" element={<StockPage data={rsiData} strategy="RSI Trend v1" />} />
          <Route path="/meanrev" element={<MeanRevPage data={mrData} strategyName="Mean Reversion v1" />} />
          <Route path="/meanrev/stock/:symbol" element={<StockPage data={mrData} strategy="Mean Reversion v1" />} />
          <Route path="/compare" element={<ComparePage trData={trData} bnData={bnData} brData={brData} rsiData={rsiData} mrData={mrData} />} />
          <Route path="/filterlab" element={<FilterLabPage bnData={bnData} />} />
          <Route path="/learnings" element={<MasterLearningsPage />} />
        </Routes>
      </div>
    </div>
  )
}
