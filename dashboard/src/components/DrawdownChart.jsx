import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

export default function DrawdownChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ff1744" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#ff1744" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
        <XAxis dataKey="date" tick={{ fill: '#8e8e9a', fontSize: 11 }} tickFormatter={d => d.slice(2, 7)} />
        <YAxis tick={{ fill: '#8e8e9a', fontSize: 11 }} tickFormatter={v => `$${v}`} reversed />
        <Tooltip
          contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }}
          formatter={(v, name) => [`$${v.toFixed(0)}`, name === 'drawdown' ? 'Drawdown' : 'DD%']}
          labelStyle={{ color: '#8e8e9a' }}
        />
        <Area type="monotone" dataKey="drawdown" stroke="#ff1744" fill="url(#ddGrad)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
