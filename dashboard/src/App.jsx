import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import StrategyPage from './pages/StrategyPage'
import BouncePage from './pages/BouncePage'
import BreakoutPage from './pages/BreakoutPage'
import RsiPage from './pages/RsiPage'
import MeanRevPage from './pages/MeanRevPage'
import TrendlinePage from './pages/TrendlinePage'
import SrPage from './pages/SrPage'
import FvgPage from './pages/FvgPage'
import VcpPage from './pages/VcpPage'
import VolumePage from './pages/VolumePage'
import ComparePage from './pages/ComparePage'
import FilterLabPage from './pages/FilterLabPage'
import MasterLearningsPage from './pages/MasterLearningsPage'
import TrailStudyPage from './pages/TrailStudyPage'
import StockPage from './pages/StockPage'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

const STRATS = [
  { path: '/trend-rider', label: 'Trend Rider v1', prefix: 'trend-rider' },
  { path: '/bounce', label: 'MA Bounce v1', prefix: 'bounce' },
  { path: '/breakout', label: 'Breakout v1', prefix: 'breakout' },
  { path: '/rsi', label: 'RSI Trend v1', prefix: 'rsi' },
  { path: '/meanrev', label: 'Mean Rev v1', prefix: 'meanrev' },
  { path: '/trendline', label: 'Trendline v1', prefix: 'trendline' },
  { path: '/sr', label: 'S/R Bounce v1', prefix: 'sr' },
  { path: '/fvg', label: 'FVG v1', prefix: 'fvg' },
  { path: '/vcp', label: 'VCP v1', prefix: 'vcp' },
  { path: '/volume', label: 'Volume v1', prefix: 'volume' },
]

export default function App() {
  const [trData, setTrData] = useState(null)
  const [bnData, setBnData] = useState(null)
  const [brData, setBrData] = useState(null)
  const [rsiData, setRsiData] = useState(null)
  const [mrData, setMrData] = useState(null)
  const [tlData, setTlData] = useState(null)
  const [srData, setSrData] = useState(null)
  const [fvgData, setFvgData] = useState(null)
  const [vcpData, setVcpData] = useState(null)
  const [volData, setVolData] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  // Close sidebar on route change (mobile)
  useEffect(() => { setSidebarOpen(false) }, [location.pathname])

  useEffect(() => {
    fetch('/data.json').then(r => r.json()).then(setTrData)
    fetch('/bounce_data.json').then(r => r.json()).then(setBnData)
    fetch('/breakout_data.json').then(r => r.json()).then(setBrData)
    fetch('/rsi_data.json').then(r => r.json()).then(setRsiData)
    fetch('/meanrev_data.json').then(r => r.json()).then(setMrData)
    fetch('/trendline_data.json').then(r => r.json()).then(setTlData)
    fetch('/sr_data.json').then(r => r.json()).then(setSrData)
    fetch('/fvg_data.json').then(r => r.json()).then(setFvgData)
    fetch('/vcp_data.json').then(r => r.json()).then(setVcpData)
    fetch('/volume_data.json').then(r => r.json()).then(setVolData)
  }, [])

  if (!trData || !bnData || !brData || !rsiData || !mrData || !tlData || !srData || !fvgData || !vcpData || !volData) return <div className="loading">Loading…</div>

  // Detect active strategy from URL
  const active = STRATS.find(s => location.pathname.startsWith(s.path)) || null
  const stockBase = active ? `/${active.prefix}/stock` : '/trend-rider/stock'

  return (
    <div className="app">
      <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
        {sidebarOpen ? '✕' : '☰'}
      </button>
      <nav className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-section">
          <NavLink to="/" end className={({isActive}) => `strategy-link summary-link ${isActive ? 'active' : ''}`}>
            📊 Summary
          </NavLink>
          <div className="sidebar-label" style={{ marginTop: '0.75rem' }}>Strategies</div>
          {STRATS.map(s => (
            <NavLink key={s.path} to={s.path} end className={({isActive}) =>
              `strategy-link ${isActive ? 'active' : ''}`
            }>{s.label}</NavLink>
          ))}
          <NavLink to="/skip-analysis" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            🧪 Trade Skip Analysis
          </NavLink>
          <NavLink to="/trail-study" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            🔬 Trail Stop Study (MA Bounce)
          </NavLink>
          <NavLink to="/learnings" end className={({isActive}) => `strategy-link ${isActive ? 'active' : ''}`}>
            📖 Master Learnings
          </NavLink>
        </div>
        {active && (
        <div className="sidebar-section">
          <div className="sidebar-label">Stocks ({active.label})</div>
          {STOCKS.map(s => (
            <NavLink key={s} to={`${stockBase}/${s}`} className={({isActive}) => isActive ? 'active' : ''}>
              {s}
            </NavLink>
          ))}
        </div>
        )}
      </nav>
      {sidebarOpen && <div className="sidebar-overlay show" onClick={() => setSidebarOpen(false)} />}
      <div className="main">
        <Routes>
          <Route path="/" element={<ComparePage trData={trData} bnData={bnData} brData={brData} rsiData={rsiData} mrData={mrData} tlData={tlData} srData={srData} fvgData={fvgData} vcpData={vcpData} volData={volData} />} />
          <Route path="/trend-rider" element={<StrategyPage data={trData} strategyName="Trend Rider v1" />} />
          <Route path="/trend-rider/stock/:symbol" element={<StockPage data={trData} strategy="Trend Rider v1" />} />
          <Route path="/bounce" element={<BouncePage data={bnData} strategyName="MA Bounce v1" />} />
          <Route path="/bounce/stock/:symbol" element={<StockPage data={bnData} strategy="MA Bounce v1" />} />
          <Route path="/breakout" element={<BreakoutPage data={brData} strategyName="Breakout v1" />} />
          <Route path="/breakout/stock/:symbol" element={<StockPage data={brData} strategy="Breakout v1" />} />
          <Route path="/rsi" element={<RsiPage data={rsiData} strategyName="RSI Trend v1" />} />
          <Route path="/rsi/stock/:symbol" element={<StockPage data={rsiData} strategy="RSI Trend v1" />} />
          <Route path="/meanrev" element={<MeanRevPage data={mrData} strategyName="Mean Reversion v1" />} />
          <Route path="/meanrev/stock/:symbol" element={<StockPage data={mrData} strategy="Mean Reversion v1" />} />
          <Route path="/trendline" element={<TrendlinePage data={tlData} strategyName="Trendline v1" />} />
          <Route path="/trendline/stock/:symbol" element={<StockPage data={tlData} strategy="Trendline v1" />} />
          <Route path="/sr" element={<SrPage data={srData} strategyName="S/R Bounce v1" />} />
          <Route path="/sr/stock/:symbol" element={<StockPage data={srData} strategy="S/R Bounce v1" />} />
          <Route path="/fvg" element={<FvgPage data={fvgData} strategyName="FVG v1" />} />
          <Route path="/fvg/stock/:symbol" element={<StockPage data={fvgData} strategy="FVG v1" />} />
          <Route path="/vcp" element={<VcpPage data={vcpData} strategyName="VCP v1" />} />
          <Route path="/vcp/stock/:symbol" element={<StockPage data={vcpData} strategy="VCP v1" />} />
          <Route path="/volume" element={<VolumePage data={volData} strategyName="Volume v1" />} />
          <Route path="/volume/stock/:symbol" element={<StockPage data={volData} strategy="Volume v1" />} />
          <Route path="/skip-analysis" element={<FilterLabPage bnData={bnData} />} />
          <Route path="/trail-study" element={<TrailStudyPage />} />
          <Route path="/learnings" element={<MasterLearningsPage />} />
        </Routes>
      </div>
    </div>
  )
}
