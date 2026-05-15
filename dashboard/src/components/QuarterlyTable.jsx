import { useState } from 'react'
import { fmt$ } from '../utils'

const VIEWS = ['Quarterly', 'Monthly', 'Yearly']

function bucket(trades, mode) {
  const map = {}
  trades.forEach(t => {
    if (!t.exitDate) return
    const y = t.exitDate.slice(0, 4)
    const m = parseInt(t.exitDate.slice(5, 7))
    let key
    if (mode === 'Yearly') key = y
    else if (mode === 'Monthly') key = `${y}-${String(m).padStart(2, '0')}`
    else key = `${y} Q${Math.ceil(m / 3)}`
    if (!map[key]) map[key] = { pnl: 0, trades: 0, tradesList: [] }
    map[key].trades++
    map[key].pnl += t.pnlDollar
    map[key].tradesList.push(t)
  })

  const rows = Object.entries(map)
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([period, d]) => {
      // Max drawdown within this period
      let peak = 0, equity = 0, maxDD = 0
      d.tradesList.sort((a, b) => a.exitDate.localeCompare(b.exitDate)).forEach(t => {
        equity += t.pnlDollar
        if (equity > peak) peak = equity
        const dd = peak - equity
        if (dd > maxDD) maxDD = dd
      })
      return { period, trades: d.trades, pnl: +d.pnl.toFixed(0), maxDD: +maxDD.toFixed(0) }
    })

  // Cumulative: compute from oldest to newest, then keep reverse order for display
  const sorted = [...rows].reverse()
  let cum = 0
  const cumMap = {}
  sorted.forEach(r => { cum += r.pnl; cumMap[r.period] = cum })
  rows.forEach(r => { r.cumPnl = cumMap[r.period] })

  return rows
}

export default function QuarterlyTable({ trades }) {
  const [view, setView] = useState('Quarterly')
  const rows = bucket(trades, view)

  return (
    <div>
      <div className="tab-bar" style={{ marginBottom: 12 }}>
        {VIEWS.map(v => (
          <button key={v} className={view === v ? 'active' : ''} onClick={() => setView(v)}>{v}</button>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>Period</th>
            <th>Trades</th>
            <th>P&L</th>
            <th>Max DD</th>
            <th>Cumulative</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.period}>
              <td><strong>{r.period}</strong></td>
              <td>{r.trades}</td>
              <td className={r.pnl >= 0 ? 'win' : 'loss'}>{fmt$(r.pnl)}</td>
              <td className="loss">{r.maxDD > 0 ? fmt$(r.maxDD) : '-'}</td>
              <td className={r.cumPnl >= 0 ? 'win' : 'loss'}>{fmt$(r.cumPnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
