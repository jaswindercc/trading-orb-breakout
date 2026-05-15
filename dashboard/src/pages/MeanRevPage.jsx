import { computeMetrics, buildDrawdownSeries, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import { NavLink } from 'react-router-dom'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

export default function MeanRevPage({ data, strategyName }) {
  const stockRows = STOCKS.map(s => {
    const t = (data.stocks[s]?.trades || []).filter(t => t.exitDate)
    const m = computeMetrics(t)
    const d = buildDrawdownSeries(t)
    return {
      symbol: s, trades: t.length,
      longs: t.filter(t => t.dir === 'LONG').length,
      shorts: t.filter(t => t.dir === 'SHORT').length,
      winRate: m?.winRate ?? 0, totalPnl: m?.totalPnl ?? 0,
      maxDD: d.maxDD, profitFactor: m?.profitFactor ?? '-', avgR: m?.avgR ?? 0,
    }
  }).sort((a, b) => b.totalPnl - a.totalPnl)

  const profitable = stockRows.filter(s => s.totalPnl > 0).length
  const avgPnl = stockRows.reduce((s, r) => s + r.totalPnl, 0) / stockRows.length
  const avgWR = stockRows.reduce((s, r) => s + r.winRate, 0) / stockRows.length
  const bestStock = stockRows[0]
  const worstStock = stockRows[stockRows.length - 1]
  const sorted = [...stockRows].sort((a, b) => a.totalPnl - b.totalPnl)
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid].totalPnl : (sorted[mid - 1].totalPnl + sorted[mid].totalPnl) / 2

  return (
    <div>
      <h1 className="page-title">{strategyName} <span>3 down days in uptrend · Buy the dip · EMA20 trailing stop</span></h1>

      <div className="card strategy-summary">
        <h3>The System</h3>
        <ul>
          <li><strong>Long:</strong> 3 consecutive lower closes + above SMA 50 → trail with EMA stop at 2.5R</li>
          <li><strong>Logic:</strong> Connors-style mean reversion — buy when everyone is panicking but trend is intact.</li>
          <li><strong>Risk:</strong> $100 per trade, 1.5× ATR stop (wider — needs room for the bounce)</li>
        </ul>

        <h3>Know This</h3>
        <ul>
          <li className="loss"><strong>Catching falling knives.</strong> Sometimes the 3rd down day is the start of a crash.</li>
          <li className="win"><strong>When the trend holds, you buy at a discount.</strong></li>
          <li><strong>Wider stop (1.5× ATR)</strong> means smaller position size per trade.</li>
        </ul>
      </div>

      <div className="kpi-grid">
        <KpiCard label="Profitable" value={`${profitable} / 12`} sub={`${(profitable/12*100).toFixed(0)}% of stocks`} />
        <KpiCard label="Avg P&L / Stock" value={fmt$(avgPnl)} className={avgPnl >= 0 ? 'win' : 'loss'} />
        <KpiCard label="Median P&L" value={fmt$(median)} className={median >= 0 ? 'win' : 'loss'} />
        <KpiCard label="Avg Win Rate" value={`${avgWR.toFixed(1)}%`} />
        <KpiCard label="Best Stock" value={bestStock.symbol} sub={fmt$(bestStock.totalPnl)} className="win" />
        <KpiCard label="Worst Stock" value={worstStock.symbol} sub={fmt$(worstStock.totalPnl)} className={worstStock.totalPnl >= 0 ? 'win' : 'loss'} />
      </div>

      <div className="card">
        <h2>Per-Stock Breakdown</h2>
        <table>
          <thead>
            <tr><th>Stock</th><th>Trades</th><th>L / S</th><th>Win %</th><th>P&L</th><th>Max DD</th><th>PF</th><th>Avg R</th></tr>
          </thead>
          <tbody>
            {stockRows.map(r => (
              <tr key={r.symbol}>
                <td><NavLink to={`/meanrev/stock/${r.symbol}`}>{r.symbol}</NavLink></td>
                <td>{r.trades}</td>
                <td>{r.longs} / {r.shorts}</td>
                <td>{r.winRate.toFixed(1)}%</td>
                <td className={r.totalPnl >= 0 ? 'win' : 'loss'}>{fmt$(r.totalPnl)}</td>
                <td className="loss">{fmt$(r.maxDD)}</td>
                <td>{r.profitFactor === Infinity ? '∞' : typeof r.profitFactor === 'number' ? r.profitFactor.toFixed(2) : r.profitFactor}</td>
                <td className={r.avgR >= 0 ? 'win' : 'loss'}>{r.avgR.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
