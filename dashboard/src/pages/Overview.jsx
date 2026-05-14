import { computeMetrics, buildEquityCurve, buildDrawdownSeries, buildConsecutive, buildMonthlyReturns, buildProfitWaveData, fmt$ } from '../utils'
import KpiCard from '../components/KpiCard'
import EquityChart from '../components/EquityChart'
import DrawdownChart from '../components/DrawdownChart'
import MonthlyChart from '../components/MonthlyChart'
import ProfitWaveChart from '../components/ProfitWaveChart'
import TradeTable from '../components/TradeTable'
import DrawdownPhases from '../components/DrawdownPhases'
import StockSummaryTable from '../components/StockSummaryTable'

const STOCKS = ['SPY', 'AAPL', 'AMD', 'GOOGL', 'META', 'NVDA', 'TSLA']

export default function Overview({ data }) {
  const allTrades = data.allTrades.filter(t => t.exitDate)
  const metrics = computeMetrics(allTrades)
  const equity = buildEquityCurve(allTrades)
  const dd = buildDrawdownSeries(allTrades)
  const consec = buildConsecutive(allTrades)
  const monthly = buildMonthlyReturns(allTrades)
  const waves = buildProfitWaveData(allTrades)

  // Per-stock metrics
  const stockMetrics = STOCKS.map(s => {
    const trades = (data.stocks[s]?.trades || []).filter(t => t.exitDate)
    const m = computeMetrics(trades)
    const d = buildDrawdownSeries(trades)
    return { symbol: s, ...m, maxDD: d.maxDD }
  })

  return (
    <div>
      <h1 className="page-title">Portfolio Overview <span>SMA 10/50 Crossover · $100 Risk/Trade</span></h1>

      <div className="kpi-grid">
        <KpiCard label="Total P&L" value={fmt$(metrics.totalPnl)} cls={metrics.totalPnl >= 0 ? 'green' : 'red'} />
        <KpiCard label="Total Trades" value={metrics.totalTrades} />
        <KpiCard label="Win Rate" value={metrics.winRate + '%'} cls={metrics.winRate >= 50 ? 'green' : 'red'} />
        <KpiCard label="Profit Factor" value={metrics.profitFactor} cls={metrics.profitFactor >= 1.5 ? 'green' : 'red'} />
        <KpiCard label="Total Profit" value={fmt$(metrics.totalProfit)} cls="green" />
        <KpiCard label="Total Loss" value={'-' + fmt$(metrics.totalLoss)} cls="red" />
        <KpiCard label="Max Drawdown" value={fmt$(dd.maxDD)} cls="red" />
        <KpiCard label="Avg Win" value={fmt$(metrics.avgWin)} cls="green" />
        <KpiCard label="Avg Loss" value={fmt$(metrics.avgLoss)} cls="red" />
        <KpiCard label="Avg R" value={metrics.avgR + 'R'} cls={metrics.avgR >= 0 ? 'green' : 'red'} />
        <KpiCard label="Max Consec Wins" value={consec.maxConsecWin} cls="green" />
        <KpiCard label="Max Consec Losses" value={consec.maxConsecLoss} cls="red" />
        <KpiCard label="Avg Trade Duration" value={metrics.avgDuration + ' days'} />
        <KpiCard label="Avg Win Duration" value={metrics.avgWinDuration + ' days'} cls="green" />
        <KpiCard label="Avg Loss Duration" value={metrics.avgLossDuration + ' days'} cls="red" />
        <KpiCard label="Max Win" value={fmt$(metrics.maxWin)} cls="green" />
      </div>

      <div className="chart-row">
        <div className="card">
          <h3>Equity Curve (All Stocks Combined)</h3>
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

      <div className="card">
        <h3>Drawdown Phases</h3>
        <DrawdownPhases phases={dd.phases} />
      </div>

      <div className="card">
        <h3>Per-Stock Summary</h3>
        <StockSummaryTable data={stockMetrics} />
      </div>

      <div className="card">
        <h3>All Trades ({allTrades.length})</h3>
        <TradeTable trades={allTrades} showStock />
      </div>
    </div>
  )
}
