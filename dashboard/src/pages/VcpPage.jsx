import { computeMetrics, buildEquityCurve, buildDrawdownSeries, buildConsecutive, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import { NavLink } from 'react-router-dom'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

export default function VcpPage({ data, strategyName }) {
  const stockRows = STOCKS.map(s => {
    const t = (data.stocks[s]?.trades || []).filter(t => t.exitDate)
    const m = computeMetrics(t)
    const d = buildDrawdownSeries(t)
    return {
      symbol: s,
      trades: t.length,
      longs: t.length,
      shorts: 0,
      winRate: m?.winRate ?? 0,
      totalPnl: m?.totalPnl ?? 0,
      maxDD: d.maxDD,
      profitFactor: m?.profitFactor ?? '-',
      avgR: m?.avgR ?? 0,
    }
  }).sort((a, b) => b.totalPnl - a.totalPnl)

  const profitable = stockRows.filter(s => s.totalPnl > 0).length
  const avgPnl = stockRows.reduce((s, r) => s + r.totalPnl, 0) / stockRows.length
  const avgWR = stockRows.reduce((s, r) => s + r.winRate, 0) / stockRows.length
  const avgDD = stockRows.reduce((s, r) => s + r.maxDD, 0) / stockRows.length
  const bestStock = stockRows[0]
  const worstStock = stockRows[stockRows.length - 1]
  const medianPnl = [...stockRows].sort((a, b) => a.totalPnl - b.totalPnl)
  const mid = Math.floor(medianPnl.length / 2)
  const median = medianPnl.length % 2 ? medianPnl[mid].totalPnl : (medianPnl[mid - 1].totalPnl + medianPnl[mid].totalPnl) / 2

  return (
    <div>
      <h1 className="page-title">{strategyName} <span>Volatility Contraction Breakout · Trail EMA stop at 2.5R · Longs only</span></h1>

      <div className="card strategy-summary">
        <h3>The System</h3>
        <ul>
          <li><strong>Long only.</strong> Minervini-style VCP: tight range near highs, then breakout</li>
          <li><strong>Setup:</strong> Close &gt; SMA(50), ATR contracting, 10-bar range shrinking</li>
          <li><strong>Near highs:</strong> Within 8% of 50-bar high (consolidation, not correction)</li>
          <li><strong>Entry:</strong> Close breaks above 10-bar high with decent volume</li>
          <li><strong>Exit:</strong> EMA(20) trailing stop at 2.5R</li>
          <li><strong>Risk:</strong> $100 per trade, 1× ATR stop</li>
        </ul>

        <h3>Why This Exists</h3>
        <ul>
          <li>VCP is Mark Minervini's bread-and-butter pattern — proven over decades</li>
          <li>Volatility contraction before expansion = <strong>energy building before release</strong></li>
          <li>Tight stops possible (contraction gives small risk relative to potential)</li>
        </ul>

        <h3>Know This</h3>
        <ul>
          <li>Rare pattern — fewer trades but historically high win rate when conditions are met</li>
          <li>Works best in <strong>new leaders emerging from bases</strong></li>
          <li>In bear markets, VCPs resolve downward → SMA50 trend filter prevents those</li>
        </ul>
      </div>

      <div className="kpi-grid">
        <KpiCard label="Profitable Stocks" value={`${profitable} / ${stockRows.length}`} cls={profitable >= 8 ? 'green' : 'red'} />
        <KpiCard label="Avg P&L / Stock" value={fmt$(avgPnl)} cls={avgPnl >= 0 ? 'green' : 'red'} />
        <KpiCard label="Median P&L / Stock" value={fmt$(median)} cls={median >= 0 ? 'green' : 'red'} />
        <KpiCard label="Avg Win Rate" value={avgWR.toFixed(1) + '%'} cls={avgWR >= 35 ? 'green' : 'red'} />
        <KpiCard label="Avg Max DD / Stock" value={fmt$(avgDD)} cls="red" />
        <KpiCard label="Best → Worst" value={`${bestStock.symbol} → ${worstStock.symbol}`} />
      </div>

      <div className="card">
        <h3>Per-Stock Performance <span style={{color:'#8e8e9a', fontWeight:400, fontSize:14, textTransform:'none'}}>(sorted by P&L)</span></h3>
        <table>
          <thead>
            <tr><th>Stock</th><th>Trades</th><th>Win%</th><th>P&L</th><th>Max DD</th><th>PF</th><th>Avg R</th></tr>
          </thead>
          <tbody>
            {stockRows.map(s => (
              <tr key={s.symbol}>
                <td><NavLink to={`/vcp/stock/${s.symbol}`}><strong>{s.symbol}</strong></NavLink></td>
                <td>{s.trades}</td>
                <td>{s.winRate}%</td>
                <td className={s.totalPnl >= 0 ? 'win' : 'loss'}>{fmt$(s.totalPnl)}</td>
                <td className="loss">{fmt$(s.maxDD)}</td>
                <td>{s.profitFactor}</td>
                <td className={s.avgR >= 0 ? 'win' : 'loss'}>{s.avgR}R</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
