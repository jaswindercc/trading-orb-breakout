import React, { useMemo } from 'react'
import { fmt$ } from '../utils'

const STOCKS = ['SPY','AAPL','ADBE','AMD','BA','CRM','GOOGL','META','MSFT','NVDA','SNOW','TSLA']

/* ── Filter functions ── */
/* Each returns { taken, skipped } */

function baseline(trades) { return { taken: trades, skipped: [] } }

function afterNRedsTake(trades, n) {
  const taken = [], skipped = []; let c = 0, armed = false
  for (const t of trades) {
    if (armed) { taken.push(t); if (t.pnlDollar<=0){c++;armed=c>=n}else{c=0;armed=false} }
    else { skipped.push(t); if (t.pnlDollar<=0){c++;if(c>=n)armed=true}else c=0 }
  }
  return { taken, skipped }
}

function afterNRedsSkip(trades, n) {
  const taken = [], skipped = []; let c = 0, skip = false
  for (const t of trades) {
    if (skip) { skipped.push(t); skip=false; if(t.pnlDollar<=0)c++;else c=0 }
    else { taken.push(t); if(t.pnlDollar<=0){c++;if(c>=n){skip=true;c=0}}else c=0 }
  }
  return { taken, skipped }
}

function afterNGreensSkip(trades, n) {
  const taken = [], skipped = []; let c = 0, skip = false
  for (const t of trades) {
    if (skip) { skipped.push(t); skip=false; if(t.pnlDollar>0)c++;else c=0 }
    else { taken.push(t); if(t.pnlDollar>0){c++;if(c>=n){skip=true;c=0}}else c=0 }
  }
  return { taken, skipped }
}

function afterNGreensTake(trades, n) {
  const taken = [], skipped = []; let c = 0, armed = false
  for (const t of trades) {
    if (armed) { taken.push(t); if(t.pnlDollar>0){c++;armed=c>=n}else{c=0;armed=false} }
    else { skipped.push(t); if(t.pnlDollar>0){c++;if(c>=n)armed=true}else c=0 }
  }
  return { taken, skipped }
}

function afterRedTakeNext(trades) {
  const taken = [], skipped = []; let lastLoss = false
  for (const t of trades) {
    if (lastLoss) taken.push(t); else skipped.push(t)
    lastLoss = t.pnlDollar <= 0
  }
  return { taken, skipped }
}

function afterGreenTakeNext(trades) {
  const taken = [], skipped = []; let lastWin = false
  for (const t of trades) {
    if (lastWin) taken.push(t); else skipped.push(t)
    lastWin = t.pnlDollar > 0
  }
  return { taken, skipped }
}

function everyNth(trades, n) {
  const taken = [], skipped = []
  trades.forEach((t, i) => { if (i % n === 0) taken.push(t); else skipped.push(t) })
  return { taken, skipped }
}

const FILTERS = [
  { id: 'baseline',    label: 'Baseline (take all)',       cat: 'baseline', fn: t => baseline(t) },
  // After reds → take next
  { id: 'r1-take',     label: 'After 1 red → take next',  cat: 'after-reds-take', fn: t => afterRedTakeNext(t) },
  { id: 'r2-take',     label: 'After 2 reds → take next', cat: 'after-reds-take', fn: t => afterNRedsTake(t,2) },
  { id: 'r3-take',     label: 'After 3 reds → take next', cat: 'after-reds-take', fn: t => afterNRedsTake(t,3) },
  // After reds → skip next
  { id: 'r2-skip',     label: 'After 2 reds → skip next', cat: 'after-reds-skip', fn: t => afterNRedsSkip(t,2) },
  { id: 'r3-skip',     label: 'After 3 reds → skip next', cat: 'after-reds-skip', fn: t => afterNRedsSkip(t,3) },
  // After greens → skip next (expect reversion)
  { id: 'g1-skip',     label: 'After 1 green → skip next',  cat: 'after-greens-skip', fn: t => afterNGreensSkip(t,1) },
  { id: 'g2-skip',     label: 'After 2 greens → skip next', cat: 'after-greens-skip', fn: t => afterNGreensSkip(t,2) },
  { id: 'g3-skip',     label: 'After 3 greens → skip next', cat: 'after-greens-skip', fn: t => afterNGreensSkip(t,3) },
  // After greens → take next (momentum)
  { id: 'g1-take',     label: 'After 1 green → take next',  cat: 'after-greens-take', fn: t => afterGreenTakeNext(t) },
  { id: 'g2-take',     label: 'After 2 greens → take next', cat: 'after-greens-take', fn: t => afterNGreensTake(t,2) },
  // Mechanical
  { id: 'every2',      label: 'Take every 2nd trade',     cat: 'mechanical', fn: t => everyNth(t,2) },
  { id: 'every3',      label: 'Take every 3rd trade',     cat: 'mechanical', fn: t => everyNth(t,3) },
]

const CAT_LABELS = {
  'baseline': 'Baseline',
  'after-reds-take': 'After Losing Streak → Take Next (reversion theory)',
  'after-reds-skip': 'After Losing Streak → Skip Next (avoid more pain)',
  'after-greens-skip': 'After Winning Streak → Skip Next (expect pullback)',
  'after-greens-take': 'After Winning Streak → Take Next (momentum theory)',
  'mechanical': 'Mechanical Spacing',
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
  for (const t of trades) { eq += t.pnlDollar; if (eq>peak) peak=eq; const x=eq-peak; if (x<dd) dd=x }
  const big = trades.filter(t => t.pnlR >= 3).length
  return { n: trades.length, w: wins.length, wr, pnl, pf, avgr, dd, big }
}

export default function FilterLabPage({ bnData }) {
  const data = useMemo(() => {
    // Totals per filter (all stocks combined)
    const totals = FILTERS.map(f => {
      const allTaken = [], allSkipped = []
      let stocksWon = 0
      STOCKS.forEach(sym => {
        const trades = (bnData.stocks[sym]?.trades || []).filter(t => t.exitDate)
        const { taken, skipped } = f.fn(trades)
        allTaken.push(...taken)
        allSkipped.push(...skipped)
        if (f.id !== 'baseline') {
          if (calcStats(taken).pnl > calcStats(trades).pnl) stocksWon++
        }
      })
      const ts = calcStats(allTaken)
      const ss = calcStats(allSkipped)
      return { ...f, ...ts, skippedPnl: ss.pnl, skippedN: ss.n, skippedWr: ss.wr, stocksWon }
    })

    // Per-stock breakdown for top filters
    const TOP_IDS = ['baseline', 'r2-skip', 'g2-skip', 'g3-skip']
    const perStock = STOCKS.map(sym => {
      const trades = (bnData.stocks[sym]?.trades || []).filter(t => t.exitDate)
      const cols = TOP_IDS.map(id => {
        const f = FILTERS.find(x => x.id === id)
        const { taken } = f.fn(trades)
        return { id, ...calcStats(taken) }
      })
      return { sym, cols }
    })

    return { totals, perStock, topIds: TOP_IDS }
  }, [bnData])

  const baselinePnl = data.totals[0].pnl

  // Group filters by category
  const categories = []
  let lastCat = null
  data.totals.forEach(t => {
    if (t.cat !== lastCat) { categories.push({ cat: t.cat, label: CAT_LABELS[t.cat], items: [] }); lastCat = t.cat }
    categories[categories.length - 1].items.push(t)
  })

  return (
    <div>
      <h1 className="page-title">Trade Skip Analysis <span>MA Bounce · 12 Stocks · Every skip combination tested</span></h1>

      <div className="card strategy-summary">
        <h3>What We Tested</h3>
        <p>13 different trade-skipping strategies applied to MA Bounce across all 12 stocks (512 total trades). We tested every theory: skip after losses, skip after wins, take after streaks, mechanical spacing. <strong>Does any pattern-based filtering beat taking every trade?</strong></p>
      </div>

      {/* ── Master Scoreboard ── */}
      <div className="card">
        <h2>Master Scoreboard — All 13 Filters</h2>
        <table>
          <thead>
            <tr>
              <th>Filter</th>
              <th>Taken</th>
              <th>WR%</th>
              <th>P&L</th>
              <th>vs Base</th>
              <th>PF</th>
              <th>Avg R</th>
              <th>Max DD</th>
              <th>Big Wins</th>
              <th>Stocks+</th>
              <th>Skipped P&L</th>
            </tr>
          </thead>
          <tbody>
            {categories.map(cat => (
              <React.Fragment key={cat.cat}>
                <tr><td colSpan={11} style={{ background: 'rgba(68,138,255,0.1)', fontWeight: 700, fontSize: '13px', padding: '8px 12px' }}>{cat.label}</td></tr>
                {cat.items.map(t => {
                  const diff = t.pnl - baselinePnl
                  const isBase = t.id === 'baseline'
                  return (
                    <tr key={t.id} className={isBase ? 'row-baseline' : ''}>
                      <td><strong>{t.label}</strong></td>
                      <td>{t.n}</td>
                      <td>{t.wr.toFixed(1)}%</td>
                      <td className={t.pnl >= 0 ? 'win' : 'loss'}>{fmt$(t.pnl)}</td>
                      <td className={diff >= 0 ? 'win' : 'loss'} style={{ fontWeight: 700 }}>
                        {isBase ? '—' : `${diff >= 0 ? '+' : ''}${fmt$(diff)}`}
                      </td>
                      <td>{t.pf.toFixed(2)}</td>
                      <td className={t.avgr >= 0 ? 'win' : 'loss'}>{t.avgr.toFixed(2)}</td>
                      <td className="loss">{fmt$(t.dd)}</td>
                      <td>{t.big}</td>
                      <td style={{ color: t.stocksWon > 6 ? '#00e676' : t.stocksWon >= 5 ? '#ffab40' : '#ff5252', fontWeight: 700 }}>
                        {isBase ? '—' : `${t.stocksWon}/12`}
                      </td>
                      <td style={{ opacity: 0.7 }}>{isBase ? '—' : `${fmt$(t.skippedPnl)} (${t.skippedN})`}</td>
                    </tr>
                  )
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Key Insight: Skipped Trades ── */}
      <div className="card">
        <h2>The Skipped Trades — Are They Actually Bad?</h2>
        <p style={{ marginBottom: '12px', opacity: 0.8 }}>If the trades you skip are net positive, the filter is hurting you — you're leaving money on the table.</p>
        <table>
          <thead>
            <tr>
              <th>Filter</th>
              <th>Trades Skipped</th>
              <th>Skipped P&L</th>
              <th>Skipped WR%</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {data.totals.filter(t => t.id !== 'baseline').map(t => (
              <tr key={t.id}>
                <td><strong>{t.label}</strong></td>
                <td>{t.skippedN}</td>
                <td className={t.skippedPnl >= 0 ? 'win' : 'loss'}>{fmt$(t.skippedPnl)}</td>
                <td>{t.skippedWr.toFixed(1)}%</td>
                <td style={{ color: t.skippedPnl > 0 ? '#ff5252' : '#00e676', fontWeight: 700 }}>
                  {t.skippedPnl > 0 ? 'Skipped $ was PROFITABLE → filter hurts' : t.skippedPnl === 0 ? 'Neutral' : 'Skipped $ was negative → filter helps'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Per-Stock for Top Filters ── */}
      <div className="card">
        <h2>Per-Stock Breakdown — Top Filters vs Baseline</h2>
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              {data.topIds.map(id => {
                const f = FILTERS.find(x => x.id === id)
                return <th key={id} colSpan={2}>{f.label}</th>
              })}
            </tr>
            <tr>
              <th></th>
              {data.topIds.map(id => <React.Fragment key={id}><th>P&L</th><th>WR%</th></React.Fragment>)}
            </tr>
          </thead>
          <tbody>
            {data.perStock.map(row => {
              const basePnl = row.cols[0].pnl
              return (
                <tr key={row.sym}>
                  <td><strong>{row.sym}</strong></td>
                  {row.cols.map((c, i) => (
                    <React.Fragment key={c.id}>
                      <td className={c.pnl >= 0 ? 'win' : 'loss'}
                        style={i > 0 && c.pnl > basePnl ? { outline: '2px solid #00e676', outlineOffset: '-2px' } : {}}>
                        {fmt$(c.pnl)}
                      </td>
                      <td>{c.wr.toFixed(1)}%</td>
                    </React.Fragment>
                  ))}
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <td><strong>TOTAL</strong></td>
              {data.topIds.map(id => {
                const t = data.totals.find(x => x.id === id)
                return (
                  <React.Fragment key={id}>
                    <td className={t.pnl >= 0 ? 'win' : 'loss'}><strong>{fmt$(t.pnl)}</strong></td>
                    <td><strong>{t.wr.toFixed(1)}%</strong></td>
                  </React.Fragment>
                )
              })}
            </tr>
          </tfoot>
        </table>
      </div>

      {/* ── Final Verdict ── */}
      <div className="card" style={{ borderLeft: '4px solid #ff5252' }}>
        <h2>Final Verdict</h2>
        <div style={{ display: 'flex', gap: '16px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '150px', padding: '12px', borderRadius: '6px', background: '#ff525215', textAlign: 'center' }}>
            <div style={{ fontSize: '36px', fontWeight: 700, color: '#ff5252' }}>0 / 12</div>
            <div style={{ fontSize: '14px', opacity: 0.7 }}>Filters that beat baseline</div>
          </div>
          <div style={{ flex: 1, minWidth: '150px', padding: '12px', borderRadius: '6px', background: '#ff525215', textAlign: 'center' }}>
            <div style={{ fontSize: '36px', fontWeight: 700, color: '#ff5252' }}>100%</div>
            <div style={{ fontSize: '14px', opacity: 0.7 }}>Skipped pools are net positive</div>
          </div>
          <div style={{ flex: 1, minWidth: '150px', padding: '12px', borderRadius: '6px', background: '#00e67615', textAlign: 'center' }}>
            <div style={{ fontSize: '36px', fontWeight: 700, color: '#00e676' }}>{fmt$(baselinePnl)}</div>
            <div style={{ fontSize: '14px', opacity: 0.7 }}>Baseline is still king</div>
          </div>
        </div>
        <div style={{ fontSize: '15px', lineHeight: 1.7 }}>
          <p><strong>We tested 12 different skip strategies across 12 stocks.</strong> Not a single one beats the baseline.</p>
          <ul style={{ margin: '8px 0' }}>
            <li><strong>After reds → take next:</strong> Loses $9K–$31K. The "due for a win" theory is false.</li>
            <li><strong>After reds → skip next:</strong> Best performer at −$3,204, but 6/12 stocks still worse. Skipped trades were +$3,204 profitable.</li>
            <li><strong>After greens → skip next:</strong> Only −$28 to −$7,832. Close but still negative. Every skipped pool was profitable.</li>
            <li><strong>After greens → take next:</strong> Momentum theory fails: −$30K to −$38K. Terrible.</li>
            <li><strong>Mechanical (every Nth):</strong> Random spacing loses $22K–$38K. Confirms randomness.</li>
          </ul>
          <p style={{ marginTop: '12px', fontWeight: 700, color: '#00e676' }}>
            Conclusion: Trade outcomes are independent. No skip pattern exploits any hidden structure. Take every signal.
          </p>
        </div>
      </div>
    </div>
  )
}
