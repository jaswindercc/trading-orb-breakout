import React from 'react'
import { computeMetrics, fmt$ } from '../utils'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

const STRATS = [
  { key: 'tr', label: 'Trend Rider', color: '#4caf50', icon: '🟢' },
  { key: 'bn', label: 'MA Bounce', color: '#2196f3', icon: '🔵' },
  { key: 'br', label: 'Breakout', color: '#ff9800', icon: '🟡' },
  { key: 'rsi', label: 'RSI Trend', color: '#e040fb', icon: '🟣' },
  { key: 'mr', label: 'Mean Rev', color: '#ff5252', icon: '🔴' },
]

function getStats(data, symbol) {
  const t = (data.stocks[symbol]?.trades || []).filter(t => t.exitDate)
  const m = computeMetrics(t)
  return { pnl: m?.totalPnl ?? 0, trades: t.length, wr: m?.winRate ?? 0 }
}

export default function ComparePage({ trData, bnData, brData, rsiData, mrData }) {
  const dataMap = { tr: trData, bn: bnData, br: brData, rsi: rsiData, mr: mrData }

  const rows = STOCKS.map(s => {
    const row = { symbol: s }
    const pnls = []
    for (const st of STRATS) {
      row[st.key] = getStats(dataMap[st.key], s)
      pnls.push({ key: st.key, pnl: row[st.key].pnl })
    }
    pnls.sort((a, b) => b.pnl - a.pnl)
    // Everyone within $500 of the top is a winner
    row.winners = pnls.filter(p => pnls[0].pnl - p.pnl < 500).map(p => p.key)
    row.bestPnl = pnls[0].pnl
    row.spread = pnls[0].pnl - pnls[pnls.length - 1].pnl
    return row
  })

  const sum = (key, strat) => rows.reduce((s, r) => s + r[strat][key], 0)
  const wins = (key) => rows.filter(r => r.winners.includes(key)).length
  const stratInfo = Object.fromEntries(STRATS.map(s => [s.key, s]))

  return (
    <div>
      <h1 className="page-title">Head-to-Head <span>All 5 Strategies · 12 Stocks</span></h1>

      <div className="kpi-grid" style={{ marginBottom: '1.5rem' }}>
        {STRATS.map(st => (
          <div className="kpi-card" key={st.key}>
            <div className="kpi-label">{st.icon} {st.label}</div>
            <div className={`kpi-value ${sum('pnl', st.key) >= 0 ? 'win' : 'loss'}`}>{fmt$(sum('pnl', st.key))}</div>
            <div className="kpi-sub">{sum('trades', st.key)} trades · {wins(st.key)} wins</div>
          </div>
        ))}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th rowSpan={2}>Stock</th>
              {STRATS.map(st => (
                <th key={st.key} colSpan={2} style={{ textAlign: 'center', borderBottom: `2px solid ${st.color}` }}>{st.label}</th>
              ))}
              <th rowSpan={2}>Winner</th>
            </tr>
            <tr>
              {STRATS.map(st => (
                <React.Fragment key={st.key}><th>P&L</th><th>WR%</th></React.Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.sort((a, b) => b.bestPnl - a.bestPnl).map(r => {
              const highlight = r.spread > 4000 ? 'big-diff' : ''
              return (
                <tr key={r.symbol}>
                  <td><strong>{r.symbol}</strong></td>
                  {STRATS.map(st => (
                    <React.Fragment key={st.key}>
                      <td className={`${r[st.key].pnl >= 0 ? 'win' : 'loss'} ${highlight}`}>{fmt$(r[st.key].pnl)}</td>
                      <td>{r[st.key].wr.toFixed(1)}%</td>
                    </React.Fragment>
                  ))}
                  <td>{r.winners.map(w => stratInfo[w]?.icon).join(' ')}
                    {' '}{r.winners.length > 1 ? 'Tie' : stratInfo[r.winners[0]]?.label}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
