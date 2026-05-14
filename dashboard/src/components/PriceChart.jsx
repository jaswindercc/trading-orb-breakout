import { useMemo, useState } from 'react'
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot } from 'recharts'

export default function PriceChart({ prices, trades }) {
  const [showSma, setShowSma] = useState(true)

  // Downsample price data for performance (keep every 1st point)
  const chartData = useMemo(() => {
    return prices.map(p => ({ ...p }))
  }, [prices])

  // Build trade markers
  const entries = useMemo(() =>
    trades.map(t => ({ date: t.entryDate, price: t.entryPrice, type: 'entry', dir: t.dir })),
    [trades]
  )
  const exits = useMemo(() =>
    trades.filter(t => t.exitDate).map(t => ({ date: t.exitDate, price: t.exitPrice, type: 'exit', pnl: t.pnlDollar })),
    [trades]
  )

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 12, color: '#8e8e9a', cursor: 'pointer' }}>
          <input type="checkbox" checked={showSma} onChange={e => setShowSma(e.target.checked)} style={{ marginRight: 4 }} />
          Show SMA Lines
        </label>
      </div>
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
          <XAxis dataKey="date" tick={{ fill: '#8e8e9a', fontSize: 10 }} tickFormatter={d => d.slice(2, 7)} interval={60} />
          <YAxis tick={{ fill: '#8e8e9a', fontSize: 11 }} domain={['auto', 'auto']} tickFormatter={v => `$${v}`} />
          <Tooltip
            contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }}
            formatter={(v, name) => [`$${Number(v).toFixed(2)}`, name]}
            labelStyle={{ color: '#8e8e9a' }}
          />
          <Line type="monotone" dataKey="close" stroke="#e0e0e0" strokeWidth={1.5} dot={false} name="Close" />
          {showSma && <Line type="monotone" dataKey="fSma" stroke="#448aff" strokeWidth={1} dot={false} name="SMA 10" />}
          {showSma && <Line type="monotone" dataKey="sSma" stroke="#ff9100" strokeWidth={1} dot={false} name="SMA 50" />}
          {entries.map((e, i) => (
            <ReferenceDot key={`e${i}`} x={e.date} y={e.price} r={4} fill={e.dir === 'LONG' ? '#00c853' : '#ff1744'} stroke="none" />
          ))}
          {exits.map((e, i) => (
            <ReferenceDot key={`x${i}`} x={e.date} y={e.price} r={3} fill={e.pnl >= 0 ? '#00c853' : '#ff1744'} stroke="#fff" strokeWidth={1} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
