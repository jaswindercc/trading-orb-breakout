import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function EquityChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#448aff" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#448aff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
        <XAxis dataKey="date" tick={{ fill: '#8e8e9a', fontSize: 11 }} tickFormatter={d => d.slice(2, 7)} />
        <YAxis tick={{ fill: '#8e8e9a', fontSize: 11 }} tickFormatter={v => `$${v}`} />
        <Tooltip
          contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }}
          formatter={(v) => [`$${v.toFixed(0)}`, 'Equity']}
          labelStyle={{ color: '#8e8e9a' }}
        />
        <ReferenceLine y={0} stroke="#555" strokeDasharray="3 3" />
        <Area type="monotone" dataKey="equity" stroke="#448aff" fill="url(#eqGrad)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
