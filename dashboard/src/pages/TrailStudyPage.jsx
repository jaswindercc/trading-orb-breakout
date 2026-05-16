import React, { useState, useEffect } from 'react'
import { fmt$ } from '../utils'

const METRIC_LABELS = {
  totalPnl: 'Total P&L',
  winRate: 'Win Rate',
  avgR: 'Avg R',
  profitFactor: 'Profit Factor',
}

function MetricToggle({ metric, setMetric }) {
  return (
    <div className="tab-bar">
      {Object.entries(METRIC_LABELS).map(([k, v]) => (
        <button key={k} className={metric === k ? 'active' : ''} onClick={() => setMetric(k)}>
          {v}
        </button>
      ))}
    </div>
  )
}

function fmtVal(val, metric) {
  if (metric === 'totalPnl') return fmt$(val)
  if (metric === 'winRate') return val.toFixed(1) + '%'
  if (metric === 'avgR') return val.toFixed(2) + 'R'
  if (metric === 'profitFactor') return typeof val === 'number' ? val.toFixed(2) : val
  return val
}

function isCurrent(row, key, currentVal) {
  return row[key] === currentVal
}

function StudyTable({ title, subtitle, data, paramKey, paramLabel, currentVal, note }) {
  const [metric, setMetric] = useState('totalPnl')
  if (!data || !data.length) return null

  const best = data.reduce((a, b) => (b[metric] > a[metric] ? b : a), data[0])

  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <h3>{title} <span style={{ color: '#8e8e9a', fontWeight: 400, fontSize: 14, textTransform: 'none' }}>{subtitle}</span></h3>
      <MetricToggle metric={metric} setMetric={setMetric} />
      {note && <p style={{ color: '#ffab40', fontSize: '0.9rem', margin: '0 0 12px' }}>{note}</p>}
      <table>
        <thead>
          <tr>
            <th>{paramLabel}</th><th>Trades</th><th>Win%</th><th>Avg R</th>
            <th>Total P&L</th><th>PF</th><th>Avg Days</th><th>Max DD</th><th></th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const paramVal = row[paramKey]
            const isBest = row === best
            const isCurr = paramVal === currentVal
            const bgStyle = isBest ? { background: 'rgba(0,230,118,0.08)' } :
                           isCurr ? { background: 'rgba(68,138,255,0.08)' } : {}
            return (
              <tr key={i} style={bgStyle}>
                <td>
                  <strong>{row.label || paramVal}</strong>
                  {isCurr && <span style={{ color: '#448aff', fontSize: '0.75rem', marginLeft: 6 }}>CURRENT</span>}
                  {isBest && <span style={{ color: '#00e676', fontSize: '0.75rem', marginLeft: 6 }}>BEST</span>}
                </td>
                <td>{row.trades}</td>
                <td>{row.winRate}%</td>
                <td className={row.avgR >= 0 ? 'win' : 'loss'}>{row.avgR}R</td>
                <td className={row.totalPnl >= 0 ? 'win' : 'loss'}><strong>{fmt$(row.totalPnl)}</strong></td>
                <td>{row.profitFactor}</td>
                <td>{row.avgDuration}d</td>
                <td className="loss">{fmt$(row.maxDD)}</td>
                <td>
                  {isBest && '👑'}
                  {isCurr && !isBest && '📍'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function HeatmapTable({ data, axes, title, subtitle }) {
  if (!data || !data.length) return null
  const [metric, setMetric] = useState('totalPnl')
  const { startR, buffer } = axes

  const best = data.reduce((a, b) => (b[metric] > a[metric] ? b : a), data[0])

  return (
    <div className="card" style={{ marginTop: '1.5rem', overflowX: 'auto' }}>
      <h3>{title} <span style={{ color: '#8e8e9a', fontWeight: 400, fontSize: 14, textTransform: 'none' }}>{subtitle}</span></h3>
      <MetricToggle metric={metric} setMetric={setMetric} />
      <table style={{ fontSize: '0.85rem' }}>
        <thead>
          <tr>
            <th>Buffer \ Start R</th>
            {startR.map(s => <th key={s} style={{ textAlign: 'center' }}>{s}R</th>)}
          </tr>
        </thead>
        <tbody>
          {buffer.map(buf => (
            <tr key={buf}>
              <td><strong>{buf}×ATR</strong></td>
              {startR.map(s => {
                const cell = data.find(d => d.trailStartR === s && d.trailBuf === buf)
                if (!cell) return <td key={s}>-</td>
                const val = cell[metric]
                const isBest = cell.trailStartR === best.trailStartR && cell.trailBuf === best.trailBuf
                const isCurrent = s === 2.5 && buf === 1.0
                const intensity = metric === 'totalPnl'
                  ? Math.min(1, Math.max(0, (val - 28000) / 12000))
                  : metric === 'winRate'
                  ? Math.min(1, Math.max(0, (val - 15) / 20))
                  : metric === 'avgR'
                  ? Math.min(1, Math.max(0, (val - 0.4) / 0.5))
                  : Math.min(1, Math.max(0, (val - 1.7) / 0.5))
                const bg = `rgba(0, 230, 118, ${(intensity * 0.3).toFixed(2)})`
                return (
                  <td key={s} style={{
                    textAlign: 'center',
                    background: bg,
                    border: isBest ? '2px solid #00e676' : isCurrent ? '2px solid #448aff' : 'none',
                    fontWeight: isBest ? 700 : 400,
                  }}>
                    {fmtVal(val, metric)}
                    {isBest && ' 👑'}
                    {isCurrent && !isBest && ' 📍'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function TrailStudyPage() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch('/trail_study_data.json').then(r => r.json()).then(setData)
  }, [])

  if (!data) return <div className="loading">Loading trail study…</div>

  const studyA = data.studyA_trailStartR || []
  const studyB = data.studyB_fixedTP || []
  const studyC = data.studyC_trailBuffer || []
  const studyD = data.studyD_initialSL || []
  const studyE = data.studyE_emaLength || []
  const heatmap = data.studyF_heatmap || []
  const heatmapAxes = data.studyF_axes || {}
  const bestTrail = data.bestTrail || {}
  const bestTP = data.bestTP || {}
  const combined = data.studyG_combined || []
  const current = data.currentParams || {}

  // Find best from Study G
  const bestOverall = combined.length ? combined.reduce((a, b) => b.totalPnl > a.totalPnl ? b : a) : null

  // Best from Study A (trail only)
  const bestA = studyA.filter(r => r.exitMode === 'trail').reduce((a, b) => b.totalPnl > a.totalPnl ? b : a, studyA[1] || {})
  const currentA = studyA.find(r => r.trailStartR === 2.5)

  return (
    <div>
      <h1 className="page-title">Trailing Stop Study <span>107 parameter sets · MA Bounce · 12 stocks · $100 risk/trade</span></h1>

      {/* ── THE BOTTOM LINE ── */}
      <div className="card" style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', border: '2px solid #00e676', padding: '1.5rem' }}>
        <h2 style={{ color: '#00e676', margin: '0 0 1rem 0', fontSize: 'clamp(1.1rem, 4vw, 1.5rem)' }}>The Bottom Line</h2>
        <div style={{ fontSize: 'clamp(0.9rem, 2.5vw, 1.05rem)', lineHeight: '1.8', color: '#e0e0e0' }}>

          <p style={{ margin: '0 0 1rem 0', padding: '0.75rem', background: 'rgba(0,230,118,0.1)', borderRadius: '8px', borderLeft: '3px solid #00e676' }}>
            <strong style={{ color: '#00e676' }}>Trailing beats fixed TP every time.</strong> Best trailing ({fmt$(bestA?.totalPnl)}) beats best fixed TP ({fmt$(bestTP?.totalPnl)}) by{' '}
            <strong>{fmt$((bestA?.totalPnl || 0) - (bestTP?.totalPnl || 0))}</strong>. Trailing lets winners run to 10R, 20R, 30R+ instead of capping them.
          </p>

          <p style={{ margin: '0 0 1rem 0', padding: '0.75rem', background: 'rgba(68,138,255,0.1)', borderRadius: '8px', borderLeft: '3px solid #448aff' }}>
            <strong style={{ color: '#448aff' }}>Start trailing EARLY (0.5R–1.0R), not late.</strong> Current 2.5R activation = {fmt$(currentA?.totalPnl)}.
            Starting at 1.0R = {fmt$(bestA?.totalPnl)} — that's <strong>{fmt$((bestA?.totalPnl || 0) - (currentA?.totalPnl || 0))} more</strong> (+{(((bestA?.totalPnl || 0) - (currentA?.totalPnl || 0)) / (currentA?.totalPnl || 1) * 100).toFixed(0)}%).
            Earlier trailing locks in more winners before they reverse.
          </p>

          <p style={{ margin: '0 0 1rem 0', padding: '0.75rem', background: 'rgba(255,171,64,0.1)', borderRadius: '8px', borderLeft: '3px solid #ffab40' }}>
            <strong style={{ color: '#ffab40' }}>Tighter initial stop = dramatically more profit.</strong> SL at 0.5×ATR = <strong style={{ color: '#00e676' }}>{fmt$(studyD.find(r => r.slAtr === 0.5)?.totalPnl)}</strong> vs
            current 1.0×ATR = {fmt$(studyD.find(r => r.slAtr === 1.0)?.totalPnl)}.
            That's <strong>2× the profit</strong>. Tighter stop → bigger position (same $100 risk, more shares) → winners pay off in bigger dollars.
            Trade-off: win rate drops from {studyD.find(r => r.slAtr === 1.0)?.winRate}% to {studyD.find(r => r.slAtr === 0.5)?.winRate}%.
          </p>

          {bestOverall && (
            <p style={{ margin: '0 0 0', padding: '0.75rem', background: 'rgba(156,39,176,0.1)', borderRadius: '8px', borderLeft: '3px solid #9c27b0' }}>
              <strong style={{ color: '#9c27b0' }}>Best overall combo: SL={bestOverall.slAtr}×ATR, Trail at {bestOverall.trailStartR}R, Buffer {bestOverall.trailBuf}×ATR</strong>
              {' '}→ <strong style={{ color: '#00e676' }}>{fmt$(bestOverall.totalPnl)}</strong> ({bestOverall.trades} trades, {bestOverall.winRate}% WR, PF {bestOverall.profitFactor}).
              That's <strong>{((bestOverall.totalPnl / (currentA?.totalPnl || 1)) * 100 - 100).toFixed(0)}% more</strong> than current settings.
            </p>
          )}
        </div>
      </div>

      {/* ── HOW IT WORKS — SIMPLE EXPLAINER ── */}
      <div className="card" style={{ marginTop: '1.5rem', padding: '1.5rem' }}>
        <h2 style={{ color: '#fff', margin: '0 0 0.5rem' }}>How the Trailing Stop Actually Works</h2>
        <p style={{ color: '#8e8e9a', margin: '0 0 1.5rem', fontSize: '0.95rem' }}>
          Forget the jargon. Here's what happens in plain English, step by step.
        </p>

        {/* ── CONCEPT 1: What IS a trailing stop? ── */}
        <div style={{ padding: '1.25rem', background: 'rgba(0,230,118,0.06)', borderRadius: 12, marginBottom: '1.5rem', borderLeft: '4px solid #00e676' }}>
          <h3 style={{ color: '#00e676', margin: '0 0 0.75rem', fontSize: '1.1rem' }}>Step 1: What IS a trailing stop?</h3>
          <p style={{ color: '#e0e0e0', margin: 0, lineHeight: 1.8 }}>
            Think of it like a <strong style={{ color: '#fff' }}>floor that only goes UP, never down</strong>.
          </p>
          <ul style={{ color: '#e0e0e0', lineHeight: 2, marginTop: 8 }}>
            <li>You enter a trade. Your stop-loss is placed below your entry (the floor).</li>
            <li>As price rises, the floor <strong style={{ color: '#00e676' }}>rises with it</strong> — following the EMA line.</li>
            <li>If price drops back down and touches the floor, you exit.</li>
            <li>The floor <strong style={{ color: '#ff5252' }}>never moves down</strong>. Once it's at $101, it stays at $101 or higher.</li>
          </ul>
          {/* Visual: simple rising floor */}
          <div style={{ margin: '1rem 0 0', padding: '1rem', background: '#12121a', borderRadius: 8, fontFamily: 'monospace', fontSize: 'clamp(0.7rem, 2vw, 0.85rem)', lineHeight: 1.6, overflowX: 'auto', whiteSpace: 'pre' }}>
{`  Price ↑
  $108 │         ★ price peak
  $106 │       ╱ ╲
  $104 │     ╱     ╲
  $102 │   ╱   ┈┈┈┈┈╳ ← price drops to hit the rising floor = EXIT
  $100 │ ● entry     ┆
   $98 │ ┄┄ initial stop (floor starts here)
       └─────────────────────── Time →

  ● = entry    ★ = peak    ╳ = exit    ┈┈ = trailing stop (the rising floor)`}
          </div>
        </div>

        {/* ── CONCEPT 2: What does "Trail Start R" mean? ── */}
        <div style={{ padding: '1.25rem', background: 'rgba(68,138,255,0.06)', borderRadius: 12, marginBottom: '1.5rem', borderLeft: '4px solid #448aff' }}>
          <h3 style={{ color: '#448aff', margin: '0 0 0.75rem', fontSize: '1.1rem' }}>Step 2: What does "Trail Start at 0.5R" mean?</h3>
          <p style={{ color: '#e0e0e0', margin: '0 0 8px', lineHeight: 1.8 }}>
            <strong style={{ color: '#fff' }}>"Trail Start R"</strong> = how much profit you need before the floor starts rising.
          </p>
          <p style={{ color: '#e0e0e0', margin: '0 0 8px', lineHeight: 1.8 }}>
            <strong style={{ color: '#448aff' }}>Before</strong> the trail activates → your stop stays at the <em>original</em> level (the initial stop-loss). It does NOT move.
          </p>
          <p style={{ color: '#e0e0e0', margin: '0 0 8px', lineHeight: 1.8 }}>
            <strong style={{ color: '#00e676' }}>After</strong> the trail activates → the stop starts following the EMA upward.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 250px), 1fr))', gap: '1rem', marginTop: '1rem' }}>
            <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8 }}>
              <div style={{ color: '#448aff', fontWeight: 700, marginBottom: 8 }}>Trail Start = 2.5R (current)</div>
              <div style={{ color: '#ccc', fontSize: '0.9rem', lineHeight: 1.7 }}>
                Price must rise <strong>2.5× your risk</strong> before the floor starts moving.<br/>
                If your risk is $2/share, price needs to go +$5 (from $100 to $105).<br/>
                Until then, your stop stays at $98 (original).
              </div>
            </div>
            <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8 }}>
              <div style={{ color: '#00e676', fontWeight: 700, marginBottom: 8 }}>Trail Start = 0.5R (recommended)</div>
              <div style={{ color: '#ccc', fontSize: '0.9rem', lineHeight: 1.7 }}>
                Price must rise only <strong>0.5× your risk</strong> before the floor starts moving.<br/>
                If your risk is $2/share, price needs to go +$1 (from $100 to $101).<br/>
                The floor starts rising MUCH sooner.
              </div>
            </div>
          </div>
          <p style={{ color: '#ffab40', margin: '1rem 0 0', fontSize: '0.9rem', lineHeight: 1.7 }}>
            ⚠️ <strong>Important:</strong> "Trail Start 0.5R" does NOT mean "move stop to breakeven at 0.5R."
            It means the stop starts <em>following the EMA</em> once you're 0.5R in profit. Where the stop actually goes depends on where the EMA is at that moment — it could still be below your entry price.
          </p>
        </div>

        {/* ── EXAMPLE A: The trade you SAVE ── */}
        <div style={{ padding: '1.25rem', background: 'rgba(255,171,64,0.06)', borderRadius: 12, marginBottom: '1.5rem', borderLeft: '4px solid #ffab40' }}>
          <h3 style={{ color: '#ffab40', margin: '0 0 0.75rem', fontSize: '1.1rem' }}>Example 1: The Trade You SAVE (this is where 0.5R wins)</h3>
          <p style={{ color: '#8e8e9a', margin: '0 0 1rem', fontSize: '0.85rem' }}>A stock goes up for a few days, then reverses. This happens ALL the time.</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: '1rem' }}>
            {/* Trail 2.5R scenario */}
            <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8, border: '1px solid #ff5252' }}>
              <div style={{ color: '#ff5252', fontWeight: 700, marginBottom: 8, fontSize: '0.95rem' }}>❌ With Trail Start = 2.5R (current)</div>
              <div style={{ fontFamily: 'monospace', fontSize: 'clamp(0.65rem, 1.8vw, 0.8rem)', color: '#ccc', lineHeight: 1.7, whiteSpace: 'pre', overflowX: 'auto' }}>
{`Day 1: Buy at $100. Stop at $98.  Risk = $2.
Day 3: Price rises to $103 (+1.5R) 📈
        Trail NOT active (needs 2.5R).
        Stop still at $98.
Day 5: Price rises to $104 (+2.0R) 📈
        Trail STILL not active.
        Stop still at $98.
Day 7: Price reverses, drops to $98 📉
        Hits original stop.
        
Result: -$2/share = -1R LOSS 😞
You had +$4 profit and gave it ALL back.`}
              </div>
            </div>
            {/* Trail 0.5R scenario */}
            <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8, border: '1px solid #00e676' }}>
              <div style={{ color: '#00e676', fontWeight: 700, marginBottom: 8, fontSize: '0.95rem' }}>✅ With Trail Start = 0.5R (recommended)</div>
              <div style={{ fontFamily: 'monospace', fontSize: 'clamp(0.65rem, 1.8vw, 0.8rem)', color: '#ccc', lineHeight: 1.7, whiteSpace: 'pre', overflowX: 'auto' }}>
{`Day 1: Buy at $100. Stop at $98.  Risk = $2.
Day 3: Price rises to $103 (+1.5R) 📈
        Trail active since $101!
        EMA=$102, buffer=$2 → stop=$100
Day 5: Price rises to $104 (+2.0R) 📈
        EMA=$103, buffer=$2 → stop=$101
        Stop moved up to $101! ↑↑
Day 7: Price reverses, drops to $101 📉
        Hits trailing stop at $101.
        
Result: +$1/share = +0.5R WIN 🎉
Same trade. Same entry. Different exit.`}
              </div>
            </div>
          </div>
          <p style={{ color: '#00e676', margin: '1rem 0 0', fontSize: '0.95rem', fontWeight: 600 }}>
            ↑ This is the WHOLE story. Across 512 trades, dozens of trades like this flip from -1R losses to small wins. That adds up to thousands of dollars.
          </p>
        </div>

        {/* ── EXAMPLE B: The big winner (both work the same) ── */}
        <div style={{ padding: '1.25rem', background: 'rgba(156,39,176,0.06)', borderRadius: 12, marginBottom: '1.5rem', borderLeft: '4px solid #9c27b0' }}>
          <h3 style={{ color: '#9c27b0', margin: '0 0 0.75rem', fontSize: '1.1rem' }}>Example 2: The Big Winner (both settings work the same)</h3>
          <p style={{ color: '#8e8e9a', margin: '0 0 1rem', fontSize: '0.85rem' }}>A stock trends strongly for weeks. This is where your big profits come from.</p>

          <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8 }}>
            <div style={{ fontFamily: 'monospace', fontSize: 'clamp(0.65rem, 1.8vw, 0.8rem)', color: '#ccc', lineHeight: 1.7, whiteSpace: 'pre', overflowX: 'auto' }}>
{`Day 1:  Buy at $100. Stop at $98. Risk = $2.
Day 5:  Price at $105 (+2.5R). Trail active in BOTH settings.
Day 15: Price at $115 (+7.5R). EMA=$113, stop=$111. 📈
Day 25: Price at $130 (+15R). EMA=$128, stop=$126. 📈📈
Day 30: Price reverses to $126. Hits trail stop.

Result with 2.5R start: exit at ~$126 = +13R WIN 🎉
Result with 0.5R start: exit at ~$126 = +13R WIN 🎉

→ Almost identical! Big winners run far past both thresholds.
  The EMA gives the same room once both trails are active.`}
            </div>
          </div>
          <p style={{ color: '#9c27b0', margin: '1rem 0 0', fontSize: '0.95rem', fontWeight: 600 }}>
            ↑ For big runners, it doesn't matter. So 0.5R gives you the same big wins PLUS it saves the mid-size winners that 2.5R gives back. Pure upside.
          </p>
        </div>

        {/* ── EXAMPLE C: Why tighter SL = more profit ── */}
        <div style={{ padding: '1.25rem', background: 'rgba(0,188,212,0.06)', borderRadius: 12, marginBottom: '1.5rem', borderLeft: '4px solid #00bcd4' }}>
          <h3 style={{ color: '#00bcd4', margin: '0 0 0.75rem', fontSize: '1.1rem' }}>Example 3: Why Tighter Stop-Loss = More Profit</h3>
          <p style={{ color: '#8e8e9a', margin: '0 0 1rem', fontSize: '0.85rem' }}>Same $100 risk budget, same stock, same entry. Only the stop distance changes.</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: '1rem' }}>
            <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8 }}>
              <div style={{ color: '#448aff', fontWeight: 700, marginBottom: 8 }}>SL = 1.0×ATR (current)</div>
              <div style={{ fontFamily: 'monospace', fontSize: 'clamp(0.65rem, 1.8vw, 0.8rem)', color: '#ccc', lineHeight: 1.7, whiteSpace: 'pre', overflowX: 'auto' }}>
{`Stock at $100, ATR = $4
Stop = $100 - (1.0 × $4) = $96
Risk per share = $4
Risk budget = $100
Shares = $100 ÷ $4 = 25 shares

If stock goes to $108 (+2R):
  Profit = 25 × $8 = $200 💰`}
              </div>
            </div>
            <div style={{ padding: '1rem', background: '#12121a', borderRadius: 8 }}>
              <div style={{ color: '#00e676', fontWeight: 700, marginBottom: 8 }}>SL = 0.5×ATR (tighter)</div>
              <div style={{ fontFamily: 'monospace', fontSize: 'clamp(0.65rem, 1.8vw, 0.8rem)', color: '#ccc', lineHeight: 1.7, whiteSpace: 'pre', overflowX: 'auto' }}>
{`Stock at $100, ATR = $4
Stop = $100 - (0.5 × $4) = $98
Risk per share = $2
Risk budget = $100
Shares = $100 ÷ $2 = 50 shares  ← 2x!

If stock goes to $108 (+4R):
  Profit = 50 × $8 = $400 💰💰`}
              </div>
            </div>
          </div>
          <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(0,188,212,0.1)', borderRadius: 8 }}>
            <div style={{ color: '#e0e0e0', fontSize: '0.95rem', lineHeight: 1.8 }}>
              <strong style={{ color: '#00bcd4' }}>Same stock. Same entry. Same $100 risk.</strong><br/>
              Tighter stop → more shares → winners pay 2× in dollars.<br/>
              The catch: you get stopped out more often (price hits $98 easier than $96).<br/>
              <strong>Win rate drops from ~28% to ~19%</strong>, but the bigger winners more than compensate.<br/><br/>
              <span style={{ color: '#ffab40' }}>Think of it like this: would you rather win 28 out of 100 trades at $200 each (= $5,600),
              or win 19 out of 100 trades at $400 each (= $7,600)?</span>
            </div>
          </div>
        </div>

        {/* ── VISUAL SUMMARY ── */}
        <div style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.03)', borderRadius: 12, borderLeft: '4px solid #fff' }}>
          <h3 style={{ color: '#fff', margin: '0 0 0.75rem', fontSize: '1.1rem' }}>Visual Summary: What Changed vs. Current Settings</h3>
          <div style={{ fontFamily: 'monospace', fontSize: 'clamp(0.65rem, 1.8vw, 0.8rem)', color: '#ccc', lineHeight: 1.7, overflowX: 'auto', whiteSpace: 'pre' }}>
{`CURRENT SETTINGS            STUDY RECOMMENDATION
═══════════════════         ════════════════════════
Trail starts at 2.5R        Trail starts at 0.5R
  → many winners reverse      → floor starts rising sooner
    before trail kicks in       → saves mid-size winners

SL at 1.0×ATR               SL at 0.5×ATR
  → 25 shares, 28% WR         → 50 shares, 19% WR
  → +$200 per 2R winner        → +$400 per winner

Buffer 1.0×ATR              Buffer 0.5×ATR
  → looser trail                → tighter trail
  → gives back more profit      → locks in more profit

TOTAL: ~$33,700              TOTAL: ~$76,800 (+128%)
across 12 stocks             across 12 stocks`}
          </div>
          <p style={{ color: '#ffab40', margin: '1rem 0 0', fontSize: '0.9rem', lineHeight: 1.7 }}>
            ⚠️ <strong>Reality check:</strong> The recommended settings mean losing ~4 out of every 5 trades. If you can't stomach that, use SL=1.0×ATR with Trail Start=1.0R — still +6% better than current with similar win rate.
          </p>
        </div>
      </div>

      {/* ── STUDY A: Trail Start R ── */}
      <StudyTable
        title="Study A: When Should Trailing Activate?"
        subtitle="Trail Start R sweep — fixed SL=1.0ATR, Buffer=1.0ATR, EMA=20"
        data={studyA}
        paramKey="trailStartR"
        paramLabel="Setting"
        currentVal={2.5}
        note="Without any trail (SL Only), every trade ends at -1R = total wipeout. Trailing is ESSENTIAL. Earlier activation = slightly more profit because it protects more winners before they reverse."
      />

      {/* ── STUDY B: Fixed TP ── */}
      <StudyTable
        title="Study B: Trailing vs Fixed Take-Profit"
        subtitle="Fixed TP at various R-multiples (no trailing at all)"
        data={studyB}
        paramKey="fixedTpR"
        paramLabel="Take Profit"
        currentVal={null}
        note="Every fixed TP underperforms trailing. Fixed TP at 10R = $25,700. But trailing at 1.0R = $35,857. Why? Fixed TP caps your best trades. A trade that could run to +20R gets closed at +5R. Trailing lets outliers run."
      />

      {/* ── STUDY C: Trail Buffer ── */}
      <StudyTable
        title="Study C: How Tight Should the Trail Be?"
        subtitle="Trail ATR Buffer sweep — distance below EMA for the trailing stop"
        data={studyC}
        paramKey="trailBuf"
        paramLabel="Buffer"
        currentVal={1.0}
        note="Buffer 0.0 = trail sits right on the EMA (tightest). Buffer 2.0 = trail is 2×ATR below EMA (loosest). The sweet spot is 0.5–1.5×ATR. Too tight = stopped out by noise. Too loose = gives back too much profit."
      />

      {/* ── STUDY D: Initial SL ── */}
      <StudyTable
        title="Study D: Initial Stop-Loss Distance"
        subtitle="How far from entry to place the initial stop — THIS IS THE BIGGEST LEVER"
        data={studyD}
        paramKey="slAtr"
        paramLabel="SL Distance"
        currentVal={1.0}
        note="⚠️ This is the single biggest profit driver in the entire system. SL at 0.5×ATR DOUBLES profit vs 1.0×ATR. The math: same $100 risk but half the distance = 2× position size = winners pay off 2× in dollars. Trade-off: 18.8% win rate (vs 27.6%) — you get stopped out more, but winners are enormous."
      />

      {/* ── STUDY E: Trail EMA Length ── */}
      <StudyTable
        title="Study E: Trail EMA Responsiveness"
        subtitle="EMA length for the trailing stop — how fast it reacts to price changes"
        data={studyE}
        paramKey="trailEmaLen"
        paramLabel="EMA Length"
        currentVal={20}
        note="Shorter EMA (10) = faster reaction, more exits, more trades. Longer EMA (50) = smoother trail, fewer exits, bigger winners. EMA 20-30 is the sweet spot: responsive enough to protect profits, slow enough to ride trends."
      />

      {/* ── STUDY F: Heatmap ── */}
      <HeatmapTable
        data={heatmap}
        axes={heatmapAxes}
        title="Study F: Trail Start R × Buffer Heatmap"
        subtitle="The interaction between when to start trailing and how tight to trail — 📍 = current, 👑 = best"
      />

      {/* ── STUDY G: Combined Best ── */}
      {combined.length > 0 && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <h3>Study G: Best Trail + SL Combinations <span style={{ color: '#8e8e9a', fontWeight: 400, fontSize: 14, textTransform: 'none' }}>top trail configs × different SL distances</span></h3>
          <p style={{ color: '#ffab40', fontSize: '0.9rem', margin: '0 0 12px' }}>
            Combining the best trail settings (0.5R start, 0.5ATR buffer) with tighter SL creates a multiplicative effect.
          </p>
          <table>
            <thead>
              <tr><th>SL</th><th>Trail Start</th><th>Buffer</th><th>Trades</th><th>Win%</th><th>Total P&L</th><th>PF</th><th></th></tr>
            </thead>
            <tbody>
              {combined.sort((a, b) => b.totalPnl - a.totalPnl).map((row, i) => {
                const isCurr = row.slAtr === 1.0 && row.trailStartR === 1.0 && row.trailBuf === 1.0
                return (
                  <tr key={i} style={i === 0 ? { background: 'rgba(0,230,118,0.08)' } : isCurr ? { background: 'rgba(68,138,255,0.08)' } : {}}>
                    <td><strong>{row.slAtr}×ATR</strong></td>
                    <td>{row.trailStartR}R</td>
                    <td>{row.trailBuf}×ATR</td>
                    <td>{row.trades}</td>
                    <td>{row.winRate}%</td>
                    <td className={row.totalPnl >= 0 ? 'win' : 'loss'}><strong>{fmt$(row.totalPnl)}</strong></td>
                    <td>{row.profitFactor}</td>
                    <td>{i === 0 && '👑'}{isCurr && '📍'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── KEY INSIGHTS ── */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <h3>Key Insights From This Study</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: '1rem' }}>
          <div style={{ padding: '1rem', background: 'rgba(0,230,118,0.08)', borderRadius: '8px', borderLeft: '3px solid #00e676' }}>
            <strong style={{ color: '#00e676' }}>1. Trailing stop is non-negotiable</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              Without it: -$10,900 (every trade hits SL). With it: +$35,857. The trailing stop IS the strategy.
              Fixed TP caps your upside. Trailing lets the market decide how far to run.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(68,138,255,0.08)', borderRadius: '8px', borderLeft: '3px solid #448aff' }}>
            <strong style={{ color: '#448aff' }}>2. Start trailing earlier than you think</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              Waiting until 2.5R to trail means many 1-2R winners reverse before protection kicks in.
              Starting at 0.5-1.0R catches more of those mid-size winners. The big 10R+ winners survive either way.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(255,171,64,0.08)', borderRadius: '8px', borderLeft: '3px solid #ffab40' }}>
            <strong style={{ color: '#ffab40' }}>3. The initial stop is the BIGGEST lever</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              Halving the stop (1.0→0.5 ATR) doubles position size and total profit.
              Yes, you lose more often (18.8% vs 27.6% WR), but each winner is TWICE as big in dollars.
              Psychologically harder, but mathematically superior.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(156,39,176,0.08)', borderRadius: '8px', borderLeft: '3px solid #9c27b0' }}>
            <strong style={{ color: '#9c27b0' }}>4. Parameters are robust, not fragile</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              The heatmap shows a wide "green zone" — many combinations are profitable.
              Trail start 0.5–2.0R and buffer 0.25–1.5ATR all work. There's no cliff edge.
              This means the edge is REAL, not curve-fitted to one magic number.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(255,82,82,0.08)', borderRadius: '8px', borderLeft: '3px solid #ff5252' }}>
            <strong style={{ color: '#ff5252' }}>5. The tradeoff: win rate vs. R-size</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              Tighter stops and earlier trails = lower win rate but bigger avg R.
              Looser stops and later trails = higher win rate but smaller avg R.
              Profit = (Win% × AvgWin) - (Loss% × AvgLoss). Both paths can work, but
              tight stop + early trail maximizes total dollars.
            </p>
          </div>
          <div style={{ padding: '1rem', background: 'rgba(0,188,212,0.08)', borderRadius: '8px', borderLeft: '3px solid #00bcd4' }}>
            <strong style={{ color: '#00bcd4' }}>6. Psychology warning</strong>
            <p style={{ margin: '0.5rem 0 0', color: '#ccc', fontSize: '0.9rem' }}>
              SL at 0.5×ATR means losing ~80% of trades. You need 4-5 losses for every winner.
              Mathematically optimal ≠ psychologically sustainable. If you can't handle long losing
              streaks, SL at 0.75-1.0×ATR is the pragmatic choice. Know yourself.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
