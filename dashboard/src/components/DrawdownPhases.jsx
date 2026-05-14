import { fmt$ } from '../utils'

export default function DrawdownPhases({ phases }) {
  if (!phases.length) return <div style={{ color: '#8e8e9a', padding: 10 }}>No drawdown phases</div>

  return (
    <div style={{ maxHeight: 300, overflowY: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Start</th>
            <th>End</th>
            <th>Depth</th>
            <th>Peak Equity</th>
            <th>DD %</th>
          </tr>
        </thead>
        <tbody>
          {phases.map((p, i) => (
            <tr key={i}>
              <td>{i + 1}</td>
              <td>{p.start}</td>
              <td>{p.end}</td>
              <td className="loss">{fmt$(p.depth)}</td>
              <td>{fmt$(p.peakEquity)}</td>
              <td className="loss">{p.peakEquity > 0 ? ((p.depth / p.peakEquity) * 100).toFixed(1) + '%' : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
