import { fmt$ } from '../utils'

export default function TradeTable({ trades, showStock }) {
  const sorted = [...trades].reverse()
  return (
    <div style={{ maxHeight: 500, overflowY: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>#</th>
            {showStock && <th>Stock</th>}
            <th>Dir</th>
            <th>Entry Date</th>
            <th>Entry $</th>
            <th>Exit Date</th>
            <th>Exit $</th>
            <th>P&L ($)</th>
            <th>P&L (R)</th>
            <th>Duration</th>
            <th>Exit Reason</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            <tr key={i}>
              <td>{trades.length - i}</td>
              {showStock && <td>{t.stock}</td>}
              <td style={{ color: t.dir === 'LONG' ? '#00c853' : '#ff1744' }}>{t.dir}</td>
              <td>{t.entryDate}</td>
              <td>${t.entryPrice.toFixed(2)}</td>
              <td>{t.exitDate}</td>
              <td>${t.exitPrice.toFixed(2)}</td>
              <td className={t.pnlDollar >= 0 ? 'win' : 'loss'}>
                {t.pnlDollar >= 0 ? '+' : '-'}{fmt$(t.pnlDollar)}
              </td>
              <td className={t.pnlR >= 0 ? 'win' : 'loss'}>
                {t.pnlR >= 0 ? '+' : ''}{t.pnlR.toFixed(1)}R
              </td>
              <td>{t.durationDays}d</td>
              <td>{t.exitReason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
