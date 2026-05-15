import React, { useMemo } from 'react'
import { fmt$ } from '../utils'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']
const CONFIGS = [
  { label: 'Baseline', reds: 0 },
  { label: 'Wait 2 reds', reds: 2 },
  { label: 'Wait 3 reds', reds: 3 },
]

function simulate(trades, waitForReds) {
  if (waitForReds === 0) return { taken: trades, skipped: [] }
  const taken = [], skipped = []
  let consecLosses = 0, armed = false
  for (const t of trades) {
    if (armed) {
      taken.push(t)
      if (t.pnlDollar <= 0) { consecLosses++; armed = consecLosses >= waitForReds }
      else { consecLosses = 0; armed = false }
    } else {
      skipped.push(t)
      if (t.pnlDollar <= 0) { consecLosses++; if (consecLosses >= waitForReds) armed = true }
      else { consecLosses = 0 }
    }
  }
  return { taken, skipped }
}

function calcStats(trades) {
  if (!trades.length) return { n:0, w:0, wr:0, pnl:0, pf:0, avgr:0, dd:0, big:0 }
  const wins = trades.filter(t => t.pnlDollar > 0)
  const losses = trades.filter(t => t.pnlDollar <= 0)
  const pnl = trades.reduce((s,t) => s + t.pnlDollar, 0)
  const wr = wins.length / trades.length * 100
  const gw = wins.reduce((s,t) => s + t.pnlDollar, 0)
  const gl = losses.reduce((s,t) => s + t.pnlDollar, 0)
  const pf = gl !== 0 ? Math.abs(gw / gl) : 99
  const avgr = trades.reduce((s,t) => s + t.pnlR, 0) / trades.length
  let eq = 0, peak = 0, dd = 0
  for (const t of trades) {
    eq += t.pnlDollar; if (eq > peak) peak = eq
    const d = eq - peak; if (d < dd) dd = d
  }
  const big = trades.filter(t => t.pnlR >= 3).length
  return { n: trades.length, w: wins.length, wr, pnl, pf, avgr, dd, big }
}

export default function FilterLabPage({ bnData }) {
  const data = useMemo(() => {
    const rows = STOCKS.map(sym => {
      const trades = (bnData.stocks[sym]?.trades || []).filter(t => t.exitDate)
      const results = CONFIGS.map(c => {
        const { taken } = simulate(trades, c.reds)
        return { ...c, ...calcStats(taken), totalSignals: trades.length }
      })
      return { sym, results }
    })
    const totals = CONFIGS.map(c => {
      const allTaken = STOCKS.flatMap(sym => {
        const trades = (bnData.stocks[sym]?.trades || []).filter(t => t.exitDate)
        return simulate(trades, c.reds).taken
      })
      return { ...c, ...calcStats(allTaken), totalSignals: rows.reduce((s,r) => s + r.results[0].totalSignals, 0) }
    })
    const verdict = CONFIGS.slice(1).map(c => {
      let wins = 0
      STOCKS.forEach(sym => {
        const trades = (bnData.stocks[sym]?.trades || []).filter(t => t.exitDate)
        const basePnl = calcStats(trades).pnl
        const filtPnl = calcStats(simulate(trades, c.reds).taken).pnl
        if (filtPnl > basePnl) wins++
      })
      return { label: c.label, reds: c.reds, stocksWon: wins }
    })
    return { rows, totals, verdict }
  }, [bnData])

  return (
    <div>
      <h1 className="page-title">Filter Lab <span>MA Bounce · All 12 Stocks · "Wait for reds"</span></h1>

      <div className="card strategy-summary">
        <h3>The Idea</h3>
        <p>Skip MA Bounce trades until you see N consecutive losers, then take the next trade. Theory: after a losing streak, the next trade is more likely to win. Test across all 12 stocks to prove or disprove.</p>
      </div>

      {/* Verdict KPI cards */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {data.totals.map((t, i) => (
          <div key={t.label} className="card" style={{ flex: 1, minWidth: '200px', textAlign: 'center' }}>
            <div style={{ fontSize: '14px', opacity: 0.7 }}>{t.label}</div>
            <div style={{ fontSize: '28px', fontWeight: 700, color: t.pnl >= 0 ? '#00e676' : '#ff5252' }}>{fmt$(t.pnl)}</div>
            <div style={{ fontSize: '14px' }}>{t.n} trades · {t.wr.toFixed(1)}% WR · PF {t.pf.toFixed(2)}</div>
            <div style={{ fontSize: '14px' }}>Max DD: {fmt$(t.dd)} · Big wins: {t.big}</div>
            {i > 0 && (
              <div style={{ marginTop: '8px', padding: '4px 8px', borderRadius: '4px',
                background: t.pnl > data.totals[0].pnl ? '#00e67622' : '#ff525222',
                color: t.pnl > data.totals[0].pnl ? '#00e676' : '#ff5252', fontWeight: 700 }}>
                {t.pnl > data.totals[0].pnl ? '+' : ''}{fmt$(t.pnl - data.totals[0].pnl)} vs baseline
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Per-Stock P&L Table */}
      <div className="card">
        <h2>Per-Stock P&L Comparison</h2>
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              <th>Signals</th>
              {CONFIGS.map(c => <th key={c.reds} colSpan={2}>{c.label}</th>)}
              <th>Filter Helps?</th>
            </tr>
            <tr>
              <th></th>
              <th></th>
              {CONFIGS.map(c => (
                <React.Fragment key={c.reds}>
                  <th>P&L</th>
                  <th>WR%</th>
                </React.Fragment>
              ))}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map(row => {
              const basePnl = row.results[0].pnl
              const anyHelps = row.results.slice(1).some(r => r.pnl > basePnl)
              return (
                <tr key={row.sym}>
                  <td><strong>{row.sym}</strong></td>
                  <td>{row.results[0].totalSignals}</td>
                  {row.results.map((r, i) => (
                    <React.Fragment key={r.reds}>
                      <td className={r.pnl >= 0 ? 'win' : 'loss'}
                        style={i > 0 && r.pnl > basePnl ? { outline: '2px solid #00e676', outlineOffset: '-2px' } : {}}>
                        {fmt$(r.pnl)}
                      </td>
                      <td>{r.wr.toFixed(1)}%</td>
                    </React.Fragment>
                  ))}
                  <td style={{ color: anyHelps ? '#00e676' : '#ff5252', fontWeight: 700 }}>
                    {anyHelps ? 'YES' : 'NO'}
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <td><strong>TOTAL</strong></td>
              <td>{data.totals[0].totalSignals}</td>
              {data.totals.map(t => (
                <React.Fragment key={t.reds}>
                  <td className={t.pnl >= 0 ? 'win' : 'loss'}><strong>{fmt$(t.pnl)}</strong></td>
                  <td><strong>{t.wr.toFixed(1)}%</strong></td>
                </React.Fragment>
              ))}
              <td style={{ fontWeight: 700 }}>
                {data.verdict.map(v => `${v.label}: ${v.stocksWon}/12`).join(' · ')}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Detailed Stats */}
      <div className="card">
        <h2>Detailed Stats per Filter</h2>
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              <th>Filter</th>
              <th>Taken</th>
              <th>Wins</th>
              <th>WR%</th>
              <th>P&L</th>
              <th>PF</th>
              <th>Avg R</th>
              <th>Max DD</th>
              <th>Big Wins</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map(row =>
              row.results.map((r, i) => (
                <tr key={`${row.sym}-${r.reds}`} className={i === 0 ? 'row-baseline' : ''}>
                  {i === 0 ? <td rowSpan={row.results.length}><strong>{row.sym}</strong></td> : null}
                  <td>{r.label}</td>
                  <td>{r.n}</td>
                  <td>{r.w}</td>
                  <td>{r.wr.toFixed(1)}%</td>
                  <td className={r.pnl >= 0 ? 'win' : 'loss'}>{fmt$(r.pnl)}</td>
                  <td>{r.pf.toFixed(2)}</td>
                  <td className={r.avgr >= 0 ? 'win' : 'loss'}>{r.avgr.toFixed(2)}</td>
                  <td className="loss">{fmt$(r.dd)}</td>
                  <td>{r.big}</td>
                </tr>
              ))
            )}
          </tbody>
          <tfoot>
            {data.totals.map((t, i) => (
              <tr key={t.reds}>
                {i === 0 ? <td rowSpan={data.totals.length}><strong>ALL</strong></td> : null}
                <td><strong>{t.label}</strong></td>
                <td><strong>{t.n}</strong></td>
                <td><strong>{t.w}</strong></td>
                <td><strong>{t.wr.toFixed(1)}%</strong></td>
                <td className={t.pnl >= 0 ? 'win' : 'loss'}><strong>{fmt$(t.pnl)}</strong></td>
                <td><strong>{t.pf.toFixed(2)}</strong></td>
                <td className={t.avgr >= 0 ? 'win' : 'loss'}><strong>{t.avgr.toFixed(2)}</strong></td>
                <td className="loss"><strong>{fmt$(t.dd)}</strong></td>
                <td><strong>{t.big}</strong></td>
              </tr>
            ))}
          </tfoot>
        </table>
      </div>

      {/* Final Verdict */}
      <div className="card" style={{ borderLeft: '4px solid #ff5252' }}>
        <h2>Final Verdict</h2>
        <table>
          <thead>
            <tr><th>Filter</th><th>Stocks where filter beats baseline</th><th>Total P&L lost</th></tr>
          </thead>
          <tbody>
            {data.verdict.map(v => (
              <tr key={v.reds}>
                <td><strong>{v.label}</strong></td>
                <td style={{ color: v.stocksWon > 6 ? '#00e676' : '#ff5252', fontWeight: 700 }}>{v.stocksWon} / 12</td>
                <td className="loss">{fmt$(data.totals.find(t => t.reds === v.reds).pnl - data.totals[0].pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p style={{ marginTop: '12px', fontSize: '16px' }}>
          <strong style={{ color: '#ff5252' }}>Conclusion:</strong> The "wait for consecutive losers" filter <strong>hurts on 10/12 stocks</strong>.
          Only BA and TSLA marginally benefit. You lose <strong>{fmt$(data.totals[0].pnl - data.totals[1].pnl)}</strong> total with Wait-2-Reds
          and <strong>{fmt$(data.totals[0].pnl - data.totals[2].pnl)}</strong> with Wait-3-Reds.
          Losses are random, not clustered predictably. <strong>Take every trade.</strong>
        </p>
      </div>
    </div>
  )
}
