import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function MonthlyChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
        <XAxis dataKey="month" tick={{ fill: '#8e8e9a', fontSize: 10 }} angle={-45} textAnchor="end" height={60} />
        <YAxis tick={{ fill: '#8e8e9a', fontSize: 11 }} tickFormatter={v => `$${v}`} />
        <Tooltip
          contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }}
          formatter={(v) => [`$${v.toFixed(0)}`, 'P&L']}
          labelStyle={{ color: '#8e8e9a' }}
        />
        <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.pnl >= 0 ? '#00c853' : '#ff1744'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
