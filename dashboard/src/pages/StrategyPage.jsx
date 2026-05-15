import { computeMetrics, buildEquityCurve, buildDrawdownSeries, buildConsecutive, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import EquityChart from '../components/EquityChart'
import DrawdownChart from '../components/DrawdownChart'
import QuarterlyTable from '../components/QuarterlyTable'
import TradeTable from '../components/TradeTable'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

export default function StrategyPage({ data, strategyName }) {
  const allTrades = data.allTrades.filter(t => t.exitDate)
  const longTrades = allTrades.filter(t => t.dir === 'LONG')
  const shortTrades = allTrades.filter(t => t.dir === 'SHORT')
  const metrics = computeMetrics(allTrades)
  const longMetrics = computeMetrics(longTrades)
  const shortMetrics = computeMetrics(shortTrades)
  const equity = buildEquityCurve(allTrades)
  const dd = buildDrawdownSeries(allTrades)
  const consec = buildConsecutive(allTrades)

  // Per-stock summary
  const stockRows = STOCKS.map(s => {
    const t = (data.stocks[s]?.trades || []).filter(t => t.exitDate)
    const m = computeMetrics(t)
    const d = buildDrawdownSeries(t)
    return { symbol: s, ...m, maxDD: d.maxDD }
  })

  return (
    <div>
      <h1 className="page-title">{strategyName} <span>Longs trail EMA20 · Shorts TP 3R (SMA200 + ATR↓)</span></h1>

      <div className="kpi-grid">
        <KpiCard label="P&L" value={fmt$(metrics.totalPnl)} cls={metrics.totalPnl >= 0 ? 'green' : 'red'} />
        <KpiCard label="Trades" value={metrics.totalTrades} />
        <KpiCard label="Win Rate" value={metrics.winRate + '%'} cls={metrics.winRate >= 40 ? 'green' : 'red'} />
        <KpiCard label="Profit Factor" value={metrics.profitFactor} cls={metrics.profitFactor >= 1.5 ? 'green' : 'red'} />
        <KpiCard label="Max DD" value={fmt$(dd.maxDD)} cls="red" />
        <KpiCard label="Avg R" value={metrics.avgR + 'R'} cls={metrics.avgR >= 0 ? 'green' : 'red'} />
        <KpiCard label="Max Consec Losses" value={consec.maxConsecLoss} cls="red" />
        <KpiCard label="Avg Win" value={fmt$(metrics.avgWin)} cls="green" />
      </div>

      <div className="card">
        <h3>Equity Curve</h3>
        <EquityChart data={equity} />
      </div>

      <div className="card">
        <h3>Drawdown</h3>
        <DrawdownChart data={dd.series} />
      </div>

      <div className="card">
        <h3>Quarterly Performance</h3>
        <QuarterlyTable trades={allTrades} />
      </div>

      <div className="card">
        <h3>Per-Stock</h3>
        <table>
          <thead>
            <tr><th>Stock</th><th>Trades</th><th>Win%</th><th>P&L</th><th>Max DD</th><th>PF</th><th>Avg R</th></tr>
          </thead>
          <tbody>
            {stockRows.map(s => (
              <tr key={s.symbol}>
                <td><strong>{s.symbol}</strong></td>
                <td>{s.totalTrades}</td>
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

      <div className="card">
        <h3 style={{color:'#00e676'}}>Long Trades ({longTrades.length}) · Win Rate {longMetrics.winRate}% · P&L <span style={{color: longMetrics.totalPnl >= 0 ? '#00e676' : '#ff5252'}}>{fmt$(longMetrics.totalPnl)}</span></h3>
        <TradeTable trades={longTrades} showStock />
      </div>

      <div className="card">
        <h3 style={{color:'#ff5252'}}>Short Trades ({shortTrades.length}) · Win Rate {shortMetrics.winRate}% · P&L <span style={{color: shortMetrics.totalPnl >= 0 ? '#00e676' : '#ff5252'}}>{fmt$(shortMetrics.totalPnl)}</span></h3>
        <TradeTable trades={shortTrades} showStock />
      </div>
    </div>
  )
}
