import React from 'react'
import { computeMetrics, buildDrawdownSeries, fmt$ } from '../utils'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

const STRATS = [
  { key: 'tr', label: 'Trend Rider', color: '#4caf50', icon: '🟢', desc: 'SMA crossover → ride the trend' },
  { key: 'bn', label: 'MA Bounce', color: '#2196f3', icon: '🔵', desc: 'Pullback to EMA20 in uptrend' },
  { key: 'br', label: 'Breakout', color: '#ff9800', icon: '🟡', desc: 'Price breaks above recent high' },
  { key: 'rsi', label: 'RSI Trend', color: '#e040fb', icon: '🟣', desc: 'RSI oversold bounce in uptrend' },
  { key: 'mr', label: 'Mean Rev', color: '#ff5252', icon: '🔴', desc: 'Bollinger Band mean reversion' },
  { key: 'tl', label: 'Trendline', color: '#00bcd4', icon: '🩵', desc: 'Rising trendline bounce' },
  { key: 'sr', label: 'S/R Bounce', color: '#8bc34a', icon: '💚', desc: 'Horizontal support bounce' },
  { key: 'fvg', label: 'FVG', color: '#ffeb3b', icon: '💛', desc: 'Fair Value Gap pullback' },
  { key: 'vcp', label: 'VCP', color: '#9c27b0', icon: '💜', desc: 'Volatility contraction breakout' },
  { key: 'vol', label: 'Volume', color: '#ff7043', icon: '🧡', desc: 'Volume spike breakout' },
]

function getFullStats(data, symbol) {
  const t = (data.stocks[symbol]?.trades || []).filter(t => t.exitDate)
  const m = computeMetrics(t)
  const d = buildDrawdownSeries(t)
  return {
    pnl: m?.totalPnl ?? 0, trades: t.length, wr: m?.winRate ?? 0,
    avgR: m?.avgR ?? 0, pf: m?.profitFactor ?? 0, maxDD: d.maxDD ?? 0,
    avgDur: m?.avgDuration ?? 0
  }
}

export default function ComparePage({ trData, bnData, brData, rsiData, mrData, tlData, srData, fvgData, vcpData, volData }) {
  const dataMap = { tr: trData, bn: bnData, br: brData, rsi: rsiData, mr: mrData, tl: tlData, sr: srData, fvg: fvgData, vcp: vcpData, vol: volData }

  // Build full stats per strategy
  const stratStats = STRATS.map(st => {
    const allTrades = (dataMap[st.key].allTrades || []).filter(t => t.exitDate)
    const m = computeMetrics(allTrades)
    const stockPnls = STOCKS.map(s => {
      const stats = getFullStats(dataMap[st.key], s)
      return { symbol: s, ...stats }
    })
    const profitable = stockPnls.filter(s => s.pnl > 0).length
    const totalDD = stockPnls.reduce((s, r) => s + r.maxDD, 0)
    return {
      ...st,
      trades: allTrades.length,
      totalPnl: m?.totalPnl ?? 0,
      wr: m?.winRate ?? 0,
      avgR: m?.avgR ?? 0,
      pf: m?.profitFactor ?? 0,
      avgDur: m?.avgDuration ?? 0,
      profitable,
      avgDD: totalDD / STOCKS.length,
      stockPnls
    }
  }).sort((a, b) => b.totalPnl - a.totalPnl)

  // Per-stock comparison rows
  const stockRows = STOCKS.map(s => {
    const row = { symbol: s }
    const pnls = []
    for (const st of STRATS) {
      row[st.key] = getFullStats(dataMap[st.key], s)
      pnls.push({ key: st.key, pnl: row[st.key].pnl })
    }
    pnls.sort((a, b) => b.pnl - a.pnl)
    row.winners = pnls.filter(p => pnls[0].pnl - p.pnl < 500).map(p => p.key)
    row.bestPnl = pnls[0].pnl
    return row
  })

  const winner = stratStats[0]
  const runner = stratStats[1]
  const stratInfo = Object.fromEntries(STRATS.map(s => [s.key, s]))
  const wins = (key) => stockRows.filter(r => r.winners.includes(key)).length

  return (
    <div>
      <h1 className="page-title">Strategy Summary <span>10 Strategies · 12 Stocks · Jan 2021 – Present · $100 risk/trade</span></h1>

      {/* ── THE ANSWER ── */}
      <div className="card" style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', border: '2px solid #00e676', padding: '1.5rem' }}>
        <h2 style={{ color: '#00e676', margin: '0 0 1rem 0', fontSize: 'clamp(1.1rem, 4vw, 1.5rem)' }}>The Bottom Line</h2>
        <div style={{ fontSize: 'clamp(0.9rem, 2.5vw, 1.1rem)', lineHeight: '1.8', color: '#e0e0e0' }}>
          <p style={{ margin: '0 0 1rem 0' }}>
            <strong style={{ color: '#fff', fontSize: 'clamp(1rem, 3vw, 1.3rem)' }}>{winner.icon} {winner.label} is #1</strong> — made <strong style={{ color: '#00e676' }}>{fmt$(winner.totalPnl)}</strong> across
            12 stocks with {winner.trades} trades. Profitable on <strong>{winner.profitable}/12</strong> stocks.
          </p>
          <p style={{ margin: '0 0 1rem 0' }}>
            <strong style={{ color: '#fff' }}>{runner.icon} {runner.label} is #2</strong> — made <strong style={{ color: '#00e676' }}>{fmt$(runner.totalPnl)}</strong> with
            {' '}{runner.trades} trades. Higher win rate ({runner.wr}%) but fewer total dollars.
          </p>
          <p style={{ margin: '0 0 1rem 0', color: '#ffab40' }}>
            All 10 strategies are profitable. The trailing EMA exit works with every entry method.
            The difference is how OFTEN you get in (trade count) and how BIG the winners run (avg R).
          </p>
          <p style={{ margin: 0, padding: '0.75rem', background: 'rgba(0,230,118,0.1)', borderRadius: '8px', borderLeft: '3px solid #00e676' }}>
            <strong>If you trade one strategy:</strong> {winner.label}. <strong>If you want quality over quantity:</strong> {stratStats.find(s => s.key === 'br')?.label || runner.label} (best avg R + win rate combo).
          </p>
        </div>
      </div>

      {/* ── RANKING TABLE ── */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <h3>Final Ranking <span style={{ color: '#8e8e9a', fontWeight: 400, fontSize: 14 }}>sorted by total P&L across all 12 stocks</span></h3>
        <table>
          <thead>
            <tr>
              <th>#</th><th>Strategy</th><th>Entry Type</th><th>Trades</th><th>Win%</th>
              <th>Avg R</th><th>Total P&L</th><th>PF</th><th>Avg Days</th><th>Stocks +</th>
            </tr>
          </thead>
          <tbody>
            {stratStats.map((st, i) => (
              <tr key={st.key} style={i === 0 ? { background: 'rgba(0,230,118,0.08)' } : {}}>
                <td><strong style={i === 0 ? { color: '#00e676', fontSize: '1.1rem' } : {}}>{i === 0 ? '👑' : i + 1}</strong></td>
                <td><strong>{st.icon} {st.label}</strong></td>
                <td style={{ color: '#8e8e9a', fontSize: '0.85rem' }}>{st.desc}</td>
                <td>{st.trades}</td>
                <td>{st.wr}%</td>
                <td className={st.avgR >= 0 ? 'win' : 'loss'}>{st.avgR}R</td>
                <td className={st.totalPnl >= 0 ? 'win' : 'loss'}><strong>{fmt$(st.totalPnl)}</strong></td>
                <td>{st.pf}</td>
                <td>{st.avgDur}d</td>
                <td>{st.profitable}/12</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── KEY INSIGHTS ── */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <h3>Key Insights From This Study</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: '1rem' }}>
          <div style={{ padding: '1rem', background: 'rgba(33,150,243,0.08)', borderRadius: '8px', borderLeft: '3px solid #2196f3' }}>
            <strong style={{ color: '#2196f3' }}>Entry matters less than you think</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              All 10 strategies are profitable. The same exit (EMA20 trail at 2.5R) makes every entry method work.
              The spread between #1 and #10 is only {fmt$(stratStats[0].totalPnl - stratStats[stratStats.length-1].totalPnl)}.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(0,230,118,0.08)', borderRadius: '8px', borderLeft: '3px solid #00e676' }}>
            <strong style={{ color: '#00e676' }}>More trades = more money</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              MA Bounce wins because it fires the most ({winner.trades} trades). Even with a lower win rate,
              the volume of trades × positive expectancy = highest total profit.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(255,171,64,0.08)', borderRadius: '8px', borderLeft: '3px solid #ffab40' }}>
            <strong style={{ color: '#ffab40' }}>Win rate doesn't pick the winner</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              Breakout has the best win rate (33.7%) but finishes #2. Mean Rev has 32.8% win rate but finishes last.
              What matters: avg R × trade count × win rate.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(156,39,176,0.08)', borderRadius: '8px', borderLeft: '3px solid #9c27b0' }}>
            <strong style={{ color: '#9c27b0' }}>Rare patterns have great edges but less profit</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              VCP and Volume have the highest profit factors (2.6 and 2.53) but rank #9 and #8.
              Fewer trades = less total P&L even with a sharper edge per trade.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(255,82,82,0.08)', borderRadius: '8px', borderLeft: '3px solid #ff5252' }}>
            <strong style={{ color: '#ff5252' }}>Fancy ≠ better</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              Trendlines, S/R, FVG (Smart Money Concepts) — all popular on YouTube — none beat
              a simple EMA pullback (MA Bounce). Simple rules, consistently applied, win.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(0,188,212,0.08)', borderRadius: '8px', borderLeft: '3px solid #00bcd4' }}>
            <strong style={{ color: '#00bcd4' }}>The exit IS the strategy</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              All 10 strategies use the same exit: 1×ATR stop, EMA20 trail at 2.5R. That's why they're ALL profitable.
              Change the exit and everything changes. The trailing stop does the heavy lifting.
            </p>
          </div>
        </div>
      </div>

      {/* ── HEAD-TO-HEAD TABLE ── */}
      <div className="card" style={{ marginTop: '1.5rem', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
        <h3>Head-to-Head by Stock <span style={{ color: '#8e8e9a', fontWeight: 400, fontSize: 14 }}>P&L per stock — who wins where?</span></h3>
        <table style={{ fontSize: '0.8rem', minWidth: '900px' }}>
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
                <React.Fragment key={st.key}><th>P&L</th><th>WR</th></React.Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {stockRows.sort((a, b) => b.bestPnl - a.bestPnl).map(r => (
              <tr key={r.symbol}>
                <td><strong>{r.symbol}</strong></td>
                {STRATS.map(st => (
                  <React.Fragment key={st.key}>
                    <td className={r[st.key].pnl >= 0 ? 'win' : 'loss'}>{fmt$(r[st.key].pnl)}</td>
                    <td>{r[st.key].wr.toFixed(0)}%</td>
                  </React.Fragment>
                ))}
                <td>{r.winners.map(w => stratInfo[w]?.icon).join(' ')}
                  {' '}{r.winners.length > 1 ? 'Tie' : stratInfo[r.winners[0]]?.label}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
