import { useParams } from 'react-router-dom'
import { computeMetrics, buildEquityCurve, buildDrawdownSeries, buildConsecutive, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import EquityChart from '../components/EquityChart'
import DrawdownChart from '../components/DrawdownChart'
import PriceChart from '../components/PriceChart'
import QuarterlyTable from '../components/QuarterlyTable'
import TradeTable from '../components/TradeTable'

export default function StockPage({ data, strategy }) {
  const { symbol } = useParams()
  const stock = data.stocks[symbol]
  if (!stock) return <div className="loading">Stock "{symbol}" not found</div>

  const trades = stock.trades.filter(t => t.exitDate)
  const longTrades = trades.filter(t => t.dir === 'LONG')
  const shortTrades = trades.filter(t => t.dir === 'SHORT')
  const metrics = computeMetrics(trades)
  const longMetrics = computeMetrics(longTrades)
  const shortMetrics = computeMetrics(shortTrades)
  const equity = buildEquityCurve(trades)
  const dd = buildDrawdownSeries(trades)
  const consec = buildConsecutive(trades)

  return (
    <div>
      <h1 className="page-title">{symbol} <span>{strategy || 'Trend Rider v1'}</span></h1>

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
        <h3>Price + Trades</h3>
        <PriceChart prices={stock.prices} trades={trades} />
      </div>

      <div className="card">
        <h3>Equity</h3>
        <EquityChart data={equity} />
      </div>

      <div className="card">
        <h3>Drawdown</h3>
        <DrawdownChart data={dd.series} />
      </div>

      <div className="card">
        <h3>Quarterly Performance</h3>
        <QuarterlyTable trades={trades} />
      </div>

      <div className="card">
        <h3 style={{color:'#00e676'}}>Long Trades ({longTrades.length}) · Win Rate {longMetrics.winRate}% · P&L <span style={{color: longMetrics.totalPnl >= 0 ? '#00e676' : '#ff5252'}}>{fmt$(longMetrics.totalPnl)}</span></h3>
        <TradeTable trades={longTrades} />
      </div>

      {shortTrades.length > 0 && <div className="card">
        <h3 style={{color:'#ff5252'}}>Short Trades ({shortTrades.length}) · Win Rate {shortMetrics.winRate}% · P&L <span style={{color: shortMetrics.totalPnl >= 0 ? '#00e676' : '#ff5252'}}>{fmt$(shortMetrics.totalPnl)}</span></h3>
        <TradeTable trades={shortTrades} />
      </div>}
    </div>
  )
}
