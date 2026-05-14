import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis } from 'recharts'

export default function ProfitWaveChart({ data }) {
  if (!data.length) return <div style={{ color: '#8e8e9a', padding: 20 }}>No winning trades</div>

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
        <XAxis type="number" dataKey="duration" name="Duration" unit=" days"
          tick={{ fill: '#8e8e9a', fontSize: 11 }} label={{ value: 'Holding Period (days)', position: 'insideBottom', offset: -2, fill: '#8e8e9a', fontSize: 11 }} />
        <YAxis type="number" dataKey="profit" name="Profit"
          tick={{ fill: '#8e8e9a', fontSize: 11 }} tickFormatter={v => `$${v}`} label={{ value: 'Profit ($)', angle: -90, position: 'insideLeft', fill: '#8e8e9a', fontSize: 11 }} />
        <ZAxis type="number" dataKey="pnlR" range={[40, 400]} name="R Multiple" />
        <Tooltip
          contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }}
          formatter={(v, name) => {
            if (name === 'Profit') return [`$${v.toFixed(0)}`, name]
            if (name === 'Duration') return [`${v} days`, name]
            return [`${v.toFixed(1)}R`, name]
          }}
          labelStyle={{ color: '#8e8e9a' }}
        />
        <Scatter data={data} fill="#00c853" fillOpacity={0.7} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
