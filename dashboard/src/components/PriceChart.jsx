import { useMemo, useState } from 'react'
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Brush } from 'recharts'

// Custom dot shapes for trade markers
const TriangleUp = (props) => {
  const { cx, cy } = props
  if (cx == null || cy == null) return null
  return <polygon points={`${cx},${cy-8} ${cx-6},${cy+4} ${cx+6},${cy+4}`} fill="#00e676" stroke="#000" strokeWidth={0.5} />
}
const TriangleDown = (props) => {
  const { cx, cy } = props
  if (cx == null || cy == null) return null
  return <polygon points={`${cx},${cy+8} ${cx-6},${cy-4} ${cx+6},${cy-4}`} fill="#ff5252" stroke="#000" strokeWidth={0.5} />
}
const WinCircle = (props) => {
  const { cx, cy } = props
  if (cx == null || cy == null) return null
  return <circle cx={cx} cy={cy} r={5} fill="#00e676" stroke="#fff" strokeWidth={1.5} />
}
const LossCircle = (props) => {
  const { cx, cy } = props
  if (cx == null || cy == null) return null
  return <circle cx={cx} cy={cy} r={5} fill="#ff5252" stroke="#fff" strokeWidth={1.5} />
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div style={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
      <div style={{ color: '#8e8e9a', marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#e0e0e0' }}>Close: <strong>${d.close?.toFixed(2)}</strong></div>
      {d.fSma && <div style={{ color: '#448aff', fontSize: 11 }}>SMA10: ${d.fSma?.toFixed(2)}</div>}
      {d.sSma && <div style={{ color: '#ff9100', fontSize: 11 }}>SMA50: ${d.sSma?.toFixed(2)}</div>}
      {d.entryLong != null && <div style={{ color: '#00e676', fontWeight: 700, marginTop: 4 }}>▲ LONG ENTRY @ ${d.entryLong.toFixed(2)}</div>}
      {d.entryShort != null && <div style={{ color: '#ff5252', fontWeight: 700, marginTop: 4 }}>▼ SHORT ENTRY @ ${d.entryShort.toFixed(2)}</div>}
      {d.exitWin != null && <div style={{ color: '#00e676', fontWeight: 700, marginTop: 4 }}>● WIN EXIT @ ${d.exitWin.toFixed(2)} ({d.exitR >= 0 ? '+' : ''}{d.exitR?.toFixed(1)}R)</div>}
      {d.exitLoss != null && <div style={{ color: '#ff5252', fontWeight: 700, marginTop: 4 }}>● LOSS EXIT @ ${d.exitLoss.toFixed(2)} ({d.exitR?.toFixed(1)}R)</div>}
    </div>
  )
}

export default function PriceChart({ prices, trades }) {
  const [showSma, setShowSma] = useState(true)

  const chartData = useMemo(() => {
    const entryMap = {}
    const exitMap = {}
    trades.forEach(t => {
      entryMap[t.entryDate] = { price: t.entryPrice, dir: t.dir }
      if (t.exitDate) exitMap[t.exitDate] = { price: t.exitPrice, pnl: t.pnlDollar, pnlR: t.pnlR }
    })
    return prices.map(p => ({
      ...p,
      entryLong: entryMap[p.date]?.dir === 'LONG' ? entryMap[p.date].price : undefined,
      entryShort: entryMap[p.date]?.dir === 'SHORT' ? entryMap[p.date].price : undefined,
      exitWin: exitMap[p.date]?.pnl >= 0 ? exitMap[p.date].price : undefined,
      exitLoss: exitMap[p.date]?.pnl < 0 ? exitMap[p.date].price : undefined,
      exitR: exitMap[p.date]?.pnlR ?? undefined,
    }))
  }, [prices, trades])

  // Default zoom: last ~300 bars (show recent data in detail)
  const defaultStart = Math.max(0, chartData.length - 300)

  return (
    <div>
      <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12, color: '#8e8e9a', cursor: 'pointer' }}>
          <input type="checkbox" checked={showSma} onChange={e => setShowSma(e.target.checked)} style={{ marginRight: 4 }} />
          SMA Lines
        </label>
        <div className="chart-legend">
          <span><span className="legend-tri-up">▲</span> Long Entry</span>
          <span><span className="legend-tri-dn">▼</span> Short Entry</span>
          <span><span className="legend-dot-win">●</span> Win Exit</span>
          <span><span className="legend-dot-loss">●</span> Loss Exit</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={500}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 30, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
          <XAxis dataKey="date" tick={{ fill: '#8e8e9a', fontSize: 10 }} tickFormatter={d => d.slice(2, 10)} interval="preserveStartEnd" minTickGap={60} />
          <YAxis tick={{ fill: '#8e8e9a', fontSize: 11 }} domain={['auto', 'auto']} tickFormatter={v => `$${v}`} />
          <Tooltip content={<CustomTooltip />} />
          <Line type="monotone" dataKey="close" stroke="#e0e0e0" strokeWidth={1.5} dot={false} name="Close" isAnimationActive={false} />
          {showSma && <Line type="monotone" dataKey="fSma" stroke="#448aff" strokeWidth={1} dot={false} name="SMA 10" isAnimationActive={false} />}
          {showSma && <Line type="monotone" dataKey="sSma" stroke="#ff9100" strokeWidth={1} dot={false} name="SMA 50" isAnimationActive={false} />}
          <Line dataKey="entryLong" stroke="none" strokeWidth={0} dot={<TriangleUp />} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="entryShort" stroke="none" strokeWidth={0} dot={<TriangleDown />} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="exitWin" stroke="none" strokeWidth={0} dot={<WinCircle />} isAnimationActive={false} connectNulls={false} />
          <Line dataKey="exitLoss" stroke="none" strokeWidth={0} dot={<LossCircle />} isAnimationActive={false} connectNulls={false} />
          <Brush dataKey="date" height={30} stroke="#448aff" fill="#1a1d28" startIndex={defaultStart} tickFormatter={d => d?.slice(2, 7) || ''}>
            <ComposedChart>
              <Line type="monotone" dataKey="close" stroke="#555" dot={false} isAnimationActive={false} />
            </ComposedChart>
          </Brush>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
