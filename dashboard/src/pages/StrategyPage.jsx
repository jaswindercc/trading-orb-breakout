import { computeMetrics, buildEquityCurve, buildDrawdownSeries, buildConsecutive, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import { NavLink } from 'react-router-dom'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

export default function StrategyPage({ data, strategyName }) {
  // Per-stock stats (this is what matters — you trade ONE stock at a time)
  const stockRows = STOCKS.map(s => {
    const t = (data.stocks[s]?.trades || []).filter(t => t.exitDate)
    const lt = t.filter(t => t.dir === 'LONG')
    const st = t.filter(t => t.dir === 'SHORT')
    const m = computeMetrics(t)
    const d = buildDrawdownSeries(t)
    return {
      symbol: s,
      trades: t.length,
      longs: lt.length,
      shorts: st.length,
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
      <h1 className="page-title">{strategyName} <span>Longs trail EMA20 · Shorts TP 3R (SMA200 + ATR↓)</span></h1>

      <div className="card strategy-summary">
        <h3>The System</h3>
        <ul>
          <li><strong>Long:</strong> SMA 10 crosses above 50 → trail with EMA stop at 2.5R, no cap</li>
          <li><strong>Short:</strong> SMA 10 crosses below 50 + below SMA 200 + ATR contracting → fixed TP at 3R</li>
          <li><strong>Risk:</strong> $100 per trade, 1× ATR stop</li>
        </ul>

        <h3>How To Use</h3>
        <ul>
          <li>TradingView → <strong>Daily chart</strong> → paste script → one stock at a time</li>
          <li>Signal fires → enter at close → <strong>set stop, walk away</strong></li>
        </ul>

        <h3>Know This</h3>
        <ul>
          <li className="loss"><strong>65-80% of trades lose.</strong> That's normal.</li>
          <li className="win"><strong>1-2 big wins (5R-10R+) pay for everything.</strong></li>
          <li><strong>Never move your stop.</strong> Never close early.</li>
          <li>Choppy market = small losses. <strong>Trending market = big wins.</strong></li>
        </ul>

        <h3>Picking Stocks</h3>
        <ul>
          <li><strong>Trending = good.</strong> Price clearly above/below 50 SMA, SMAs separated. Staircase on 1Y chart.</li>
          <li><strong>Choppy = skip.</strong> SMAs flat/tangled, price zigzagging sideways.</li>
          <li><strong>Best:</strong> NVDA, TSLA, META, AMD, GOOGL, AAPL — big movers that trend hard</li>
          <li><strong>5+ losses in a row?</strong> Stock is choppy — rotate to something trending</li>
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
        <h3>Per-Stock Performance <span style={{color:'#8e8e9a', fontWeight:400, fontSize:14, textTransform:'none'}}>(sorted by P&L — you trade one stock at a time)</span></h3>
        <table>
          <thead>
            <tr><th>Stock</th><th>Trades</th><th>L</th><th>S</th><th>Win%</th><th>P&L</th><th>Max DD</th><th>PF</th><th>Avg R</th></tr>
          </thead>
          <tbody>
            {stockRows.map(s => (
              <tr key={s.symbol}>
                <td><NavLink to={`/stock/${s.symbol}`}><strong>{s.symbol}</strong></NavLink></td>
                <td>{s.trades}</td>
                <td>{s.longs}</td>
                <td>{s.shorts}</td>
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
