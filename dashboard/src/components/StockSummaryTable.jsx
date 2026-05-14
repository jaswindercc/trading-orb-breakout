import { Link } from 'react-router-dom'
import { fmt$ } from '../utils'

export default function StockSummaryTable({ data }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Stock</th>
          <th>Trades</th>
          <th>Win Rate</th>
          <th>Total P&L</th>
          <th>Profit</th>
          <th>Loss</th>
          <th>Max DD</th>
          <th>PF</th>
          <th>Avg R</th>
          <th>Avg Win Days</th>
        </tr>
      </thead>
      <tbody>
        {data.map(s => (
          <tr key={s.symbol}>
            <td><Link to={`/stock/${s.symbol}`}>{s.symbol}</Link></td>
            <td>{s.totalTrades}</td>
            <td className={s.winRate >= 50 ? 'win' : 'loss'}>{s.winRate}%</td>
            <td className={s.totalPnl >= 0 ? 'win' : 'loss'}>{s.totalPnl >= 0 ? '+' : '-'}{fmt$(s.totalPnl)}</td>
            <td className="win">{fmt$(s.totalProfit)}</td>
            <td className="loss">-{fmt$(s.totalLoss)}</td>
            <td className="loss">{fmt$(s.maxDD)}</td>
            <td>{s.profitFactor}</td>
            <td className={s.avgR >= 0 ? 'win' : 'loss'}>{s.avgR}R</td>
            <td>{s.avgWinDuration}d</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
