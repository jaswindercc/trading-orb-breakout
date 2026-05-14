import { useParams } from 'react-router-dom'
import { computeMetrics, buildEquityCurve, buildDrawdownSeries, buildConsecutive, buildMonthlyReturns, buildProfitWaveData, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import EquityChart from '../components/EquityChart'
import DrawdownChart from '../components/DrawdownChart'
import MonthlyChart from '../components/MonthlyChart'
import ProfitWaveChart from '../components/ProfitWaveChart'
import PriceChart from '../components/PriceChart'
import TradeTable from '../components/TradeTable'
import DrawdownPhases from '../components/DrawdownPhases'
import DurationHistogram from '../components/DurationHistogram'

export default function StockPage({ data }) {
  const { symbol } = useParams()
  const stock = data.stocks[symbol]
  if (!stock) return <div className="loading">Stock "{symbol}" not found</div>

  const trades = stock.trades.filter(t => t.exitDate)
  const metrics = computeMetrics(trades)
  const equity = buildEquityCurve(trades)
  const dd = buildDrawdownSeries(trades)
  const consec = buildConsecutive(trades)
  const monthly = buildMonthlyReturns(trades)
  const waves = buildProfitWaveData(trades)

  // Drawdown rate: maxDD / number of trading days
  const totalDays = trades.reduce((s, t) => s + t.durationDays, 0)
  const ddRate = totalDays > 0 ? (dd.maxDD / totalDays).toFixed(2) : 0

  return (
    <div>
      <h1 className="page-title">{symbol} <span>SMA 10/50 Crossover · $100 Risk/Trade</span></h1>

      <div className="kpi-grid">
        <KpiCard label="Total P&L" value={(metrics.totalPnl >= 0 ? '' : '-') + fmt$(metrics.totalPnl)} cls={metrics.totalPnl >= 0 ? 'green' : 'red'} />
        <KpiCard label="Total Trades" value={metrics.totalTrades} />
        <KpiCard label="Win Rate" value={metrics.winRate + '%'} cls={metrics.winRate >= 50 ? 'green' : 'red'} />
        <KpiCard label="Profit Factor" value={metrics.profitFactor} cls={metrics.profitFactor >= 1.5 ? 'green' : 'red'} />
        <KpiCard label="Total Profit" value={fmt$(metrics.totalProfit)} cls="green" />
        <KpiCard label="Total Loss" value={'-' + fmt$(metrics.totalLoss)} cls="red" />
        <KpiCard label="Max Drawdown" value={fmt$(dd.maxDD)} cls="red" />
        <KpiCard label="DD Rate ($/day)" value={'$' + ddRate} cls="red" />
        <KpiCard label="Avg Win" value={fmt$(metrics.avgWin)} cls="green" />
        <KpiCard label="Avg Loss" value={fmt$(metrics.avgLoss)} cls="red" />
        <KpiCard label="Avg R" value={metrics.avgR + 'R'} cls={metrics.avgR >= 0 ? 'green' : 'red'} />
        <KpiCard label="Max Consec Wins" value={consec.maxConsecWin} cls="green" />
        <KpiCard label="Max Consec Losses" value={consec.maxConsecLoss} cls="red" />
        <KpiCard label="Avg Trade Duration" value={metrics.avgDuration + ' days'} />
        <KpiCard label="Avg Win Duration" value={metrics.avgWinDuration + ' days'} cls="green" />
        <KpiCard label="Avg Loss Duration" value={metrics.avgLossDuration + ' days'} cls="red" />
        <KpiCard label="Max Win" value={fmt$(metrics.maxWin)} cls="green" />
        <KpiCard label="Max Loss" value={fmt$(metrics.maxLoss)} cls="red" />
      </div>

      <div className="card">
        <h3>{symbol} Price Chart with SMA 10/50</h3>
        <PriceChart prices={stock.prices} trades={trades} />
      </div>

      <div className="chart-row">
        <div className="card">
          <h3>Equity Curve</h3>
          <EquityChart data={equity} />
        </div>
        <div className="card">
          <h3>Drawdown ($)</h3>
          <DrawdownChart data={dd.series} />
        </div>
      </div>

      <div className="chart-row">
        <div className="card">
          <h3>Monthly P&L</h3>
          <MonthlyChart data={monthly} />
        </div>
        <div className="card">
          <h3>Profit Wave – Winner Duration vs Profit</h3>
          <ProfitWaveChart data={waves} />
        </div>
      </div>

      <div className="chart-row">
        <div className="card">
          <h3>Trade Duration Distribution</h3>
          <DurationHistogram trades={trades} />
        </div>
        <div className="card">
          <h3>Drawdown Phases</h3>
          <DrawdownPhases phases={dd.phases} />
        </div>
      </div>

      <div className="card">
        <h3>All Trades ({trades.length})</h3>
        <TradeTable trades={trades} />
      </div>
    </div>
  )
}
