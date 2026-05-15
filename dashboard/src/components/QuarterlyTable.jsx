import { fmt$ } from '../utils'

export default function QuarterlyTable({ trades }) {
  const quarters = {}
  trades.forEach(t => {
    if (!t.exitDate) return
    const year = t.exitDate.slice(0, 4)
    const month = parseInt(t.exitDate.slice(5, 7))
    const q = `${year} Q${Math.ceil(month / 3)}`
    if (!quarters[q]) quarters[q] = { trades: 0, wins: 0, pnl: 0, grossWin: 0, grossLoss: 0 }
    quarters[q].trades++
    if (t.pnlDollar > 0) { quarters[q].wins++; quarters[q].grossWin += t.pnlDollar }
    else quarters[q].grossLoss += Math.abs(t.pnlDollar)
    quarters[q].pnl += t.pnlDollar
  })

  const rows = Object.entries(quarters).sort().map(([quarter, d]) => ({
    quarter,
    trades: d.trades,
    wins: d.wins,
    losses: d.trades - d.wins,
    winRate: d.trades > 0 ? +(d.wins / d.trades * 100).toFixed(1) : 0,
    pnl: +d.pnl.toFixed(0),
    pf: d.grossLoss > 0 ? +(d.grossWin / d.grossLoss).toFixed(2) : (d.grossWin > 0 ? '∞' : '-'),
  }))

  let cumPnl = 0
  rows.forEach(r => { cumPnl += r.pnl; r.cumPnl = cumPnl })

  return (
    <table>
      <thead>
        <tr>
          <th>Quarter</th>
          <th>Trades</th>
          <th>W</th>
          <th>L</th>
          <th>Win%</th>
          <th>P&L</th>
          <th>Cumulative</th>
          <th>PF</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.quarter}>
            <td><strong>{r.quarter}</strong></td>
            <td>{r.trades}</td>
            <td className="win">{r.wins}</td>
            <td className="loss">{r.losses}</td>
            <td>{r.winRate}%</td>
            <td className={r.pnl >= 0 ? 'win' : 'loss'}>{fmt$(r.pnl)}</td>
            <td className={r.cumPnl >= 0 ? 'win' : 'loss'}>{fmt$(r.cumPnl)}</td>
            <td>{r.pf}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
