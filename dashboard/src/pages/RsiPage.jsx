import { computeMetrics, buildDrawdownSeries, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import { NavLink } from 'react-router-dom'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

export default function RsiPage({ data, strategyName }) {
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
      <h1 className="page-title">{strategyName} <span>RSI crosses above 50 · SMA50 trend filter · EMA20 trailing stop</span></h1>

      <div className="card strategy-summary">
        <h3>The System</h3>
        <ul>
          <li><strong>Long:</strong> RSI(14) crosses above 50 from below + above SMA 50 → trail with EMA stop at 2.5R</li>
          <li><strong>Logic:</strong> RSI crossing 50 = momentum shifting bullish. Confirms trend, not just a bounce.</li>
          <li><strong>Risk:</strong> $100 per trade, 1× ATR stop</li>
        </ul>

        <h3>Know This</h3>
        <ul>
          <li className="loss"><strong>More signals than crossover</strong> — RSI crosses 50 frequently in choppy markets.</li>
          <li className="win"><strong>Catches momentum shifts early.</strong></li>
          <li><strong>Same trailing exit</strong> as all other strategies for fair comparison.</li>
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
                <td><NavLink to={`/rsi/stock/${r.symbol}`}>{r.symbol}</NavLink></td>
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
