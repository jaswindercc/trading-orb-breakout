import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function DurationHistogram({ trades }) {
  const bins = useMemo(() => {
    const buckets = [
      { label: '1-5d', min: 1, max: 5 },
      { label: '6-10d', min: 6, max: 10 },
      { label: '11-20d', min: 11, max: 20 },
      { label: '21-40d', min: 21, max: 40 },
      { label: '41-60d', min: 41, max: 60 },
      { label: '61-100d', min: 61, max: 100 },
      { label: '100d+', min: 101, max: Infinity },
    ]
    return buckets.map(b => {
      const inBin = trades.filter(t => t.durationDays >= b.min && t.durationDays <= b.max)
      const wins = inBin.filter(t => t.pnlDollar > 0).length
      const losses = inBin.length - wins
      return { label: b.label, total: inBin.length, wins, losses }
    }).filter(b => b.total > 0)
  }, [trades])

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={bins} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
        <XAxis dataKey="label" tick={{ fill: '#8e8e9a', fontSize: 11 }} />
        <YAxis tick={{ fill: '#8e8e9a', fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: '#1a1d28', border: '1px solid #2a2d3a', borderRadius: 8 }}
          labelStyle={{ color: '#8e8e9a' }}
        />
        <Bar dataKey="wins" stackId="a" fill="#00c853" name="Wins" radius={[0, 0, 0, 0]} />
        <Bar dataKey="losses" stackId="a" fill="#ff1744" name="Losses" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
