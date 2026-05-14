import { useState, useEffect, useMemo } from 'react'
import { fmt$ } from '../utils'
import EquityChart from '../components/EquityChart'
import KpiCard from '../components/KpiCard'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
  BarChart, Bar, Cell, ReferenceLine
} from 'recharts'

const METRIC_COLS = [
  { key: 'trades', label: 'Trades', better: 'neutral' },
  { key: 'wr', label: 'Win%', better: 'high', fmt: v => v + '%' },
  { key: 'pnl', label: 'P&L $', better: 'high', fmt: v => '$' + v.toLocaleString() },
  { key: 'mdd', label: 'MDD $', better: 'low', fmt: v => '$' + v.toLocaleString() },
  { key: 'pf', label: 'PF', better: 'high' },
  { key: 'avgR', label: 'Avg R', better: 'high' },
  { key: 'rf', label: 'RF', better: 'high' },
  { key: 'mcl', label: 'MCL', better: 'low' },
]

const STOCK_COLORS = {
  SPY: '#448aff', AAPL: '#00c853', AMD: '#ff1744', GOOGL: '#ff9100',
  META: '#b388ff', NVDA: '#18ffff', TSLA: '#ffeb3b', ALL: '#e0e0e0'
}
const COMPARE_COLORS = ['#448aff','#00c853','#ff1744','#ff9100','#b388ff','#18ffff','#ffeb3b','#e040fb']

function cmp(val, base, better) {
  if (better === 'neutral' || val === base) return ''
  if (better === 'high') return val > base ? 'better' : val < base ? 'worse' : ''
  return val < base ? 'better' : val > base ? 'worse' : ''
}

export default function ResearchPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [stockFilter, setStockFilter] = useState('ALL')
  const [groupFilter, setGroupFilter] = useState('all')
  const [compareIds, setCompareIds] = useState([])

  useEffect(() => {
    fetch('/research_data.json')
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then(setData)
      .catch(e => setError(e.message))
  }, [])

  const groups = data?.groups || {}
  const stocks = data?.stockList || []
  const baseline = data?.scenarios?.[data?.baseline_id]

  const filteredIds = useMemo(() => {
    if (!data) return []
    return Object.keys(data.scenarios).filter(sid =>
      groupFilter === 'all' || data.scenarios[sid].group === groupFilter
    )
  }, [data, groupFilter])

  const getRow = (sid) => data?.scenarios?.[sid]?.per_stock?.[stockFilter] || {}
  const baseRow = baseline ? getRow(data.baseline_id) : {}

  // Equity overlay for compare checkboxes
  const compEquity = useMemo(() => {
    if (!data || compareIds.length === 0) return []
    const ids = ['baseline', ...compareIds.filter(id => id !== 'baseline')]
    const dateMap = {}
    ids.forEach(sid => {
      const eq = data.scenarios[sid]?.equity?.[stockFilter] || []
      eq.forEach(pt => {
        if (!dateMap[pt.date]) dateMap[pt.date] = { date: pt.date }
        dateMap[pt.date][sid] = pt.equity
      })
    })
    return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date))
  }, [data, compareIds, stockFilter])

  // Per-stock delta for selected
  const stockDelta = useMemo(() => {
    if (!data || !selected) return []
    return stocks.map(s => ({
      stock: s,
      delta: Math.round((data.scenarios[selected]?.per_stock?.[s]?.pnl || 0) - (baseline?.per_stock?.[s]?.pnl || 0)),
    }))
  }, [data, selected, baseline, stocks])

  if (error) return <div className="loading">Error loading research data: {error}</div>
  if (!data) return <div className="loading">Loading research data…</div>

  const toggleCompare = (sid) =>
    setCompareIds(prev => prev.includes(sid) ? prev.filter(id => id !== sid) : [...prev, sid])

  const scen = selected ? data.scenarios[selected] : null

  return (
    <div>
      <h1 className="page-title">
        Strategy Research Lab
        <span>{Object.keys(data.scenarios).length} scenarios · {stocks.length} stocks</span>
      </h1>

      <div className="research-filters">
        <label>Stock:</label>
        <select value={stockFilter} onChange={e => setStockFilter(e.target.value)}>
          <option value="ALL">ALL (Portfolio)</option>
          {stocks.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <label style={{marginLeft:16}}>Group:</label>
        <select value={groupFilter} onChange={e => setGroupFilter(e.target.value)}>
          <option value="all">All Groups</option>
          {Object.entries(groups).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        {compareIds.length > 0 && (
          <button className="clear-compare-btn" onClick={() => setCompareIds([])}>
            Clear Compare ({compareIds.length})
          </button>
        )}
      </div>

      {/* === MAIN TABLE === */}
      <div className="card research-table-card">
        <h3>Scenario Comparison{stockFilter !== 'ALL' ? ` — ${stockFilter}` : ' — Portfolio'}</h3>
        <div className="research-table-wrap">
          <table className="research-table">
            <thead>
              <tr>
                <th style={{width:30}}>📊</th>
                <th className="sticky-col">Scenario</th>
                {METRIC_COLS.map(c => <th key={c.key}>{c.label}</th>)}
                <th>Δ P&L</th>
              </tr>
            </thead>
            <tbody>
              {filteredIds.map(sid => {
                const row = getRow(sid)
                const isBase = sid === data.baseline_id
                const isSel = sid === selected
                const isComp = compareIds.includes(sid)
                const delta = (row.pnl || 0) - (baseRow.pnl || 0)
                return (
                  <tr key={sid}
                      className={[isBase && 'baseline-row', isSel && 'selected-row', isComp && 'compare-row'].filter(Boolean).join(' ')}
                      onClick={() => setSelected(sid === selected ? null : sid)}
                      style={{cursor:'pointer'}}>
                    <td onClick={e => { e.stopPropagation(); toggleCompare(sid) }} style={{cursor:'pointer',textAlign:'center'}}>
                      {isComp ? '✅' : '⬜'}
                    </td>
                    <td className="sticky-col">
                      <strong>{data.scenarios[sid].label}</strong>
                      {isBase && <span className="baseline-badge">BASE</span>}
                      <div className="scenario-group-tag">{groups[data.scenarios[sid].group]}</div>
                    </td>
                    {METRIC_COLS.map(c => {
                      const val = row[c.key] ?? 0
                      return (
                        <td key={c.key} className={isBase ? '' : cmp(val, baseRow[c.key] ?? 0, c.better)}>
                          {c.fmt ? c.fmt(val) : val}
                        </td>
                      )
                    })}
                    <td className={isBase ? '' : delta > 0 ? 'better' : delta < 0 ? 'worse' : ''}>
                      {isBase ? '—' : (delta >= 0 ? '+$' : '-$') + Math.abs(Math.round(delta)).toLocaleString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="research-hint">Click row → details below · Click 📊 → overlay equity curves</p>
      </div>

      {/* === EQUITY OVERLAY === */}
      {compareIds.length > 0 && compEquity.length > 0 && (
        <div className="card">
          <h3>Equity Overlay{stockFilter !== 'ALL' ? ` — ${stockFilter}` : ' — Portfolio'}</h3>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={compEquity}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="date" tick={{fill:'#888',fontSize:11}} tickFormatter={d => d?.slice(5)} />
              <YAxis tick={{fill:'#888',fontSize:11}} tickFormatter={v => '$'+v} />
              <Tooltip contentStyle={{background:'#1a1d28',border:'1px solid #333'}}
                       formatter={(v, n) => ['$' + (v||0).toLocaleString(), data.scenarios[n]?.label || n]} />
              <Legend formatter={n => data.scenarios[n]?.label?.slice(0, 30) || n} />
              {['baseline', ...compareIds.filter(id => id !== 'baseline')].map((sid, i) => (
                <Line key={sid} type="monotone" dataKey={sid} dot={false}
                      strokeWidth={sid === 'baseline' ? 3 : 2}
                      stroke={COMPARE_COLORS[i % COMPARE_COLORS.length]}
                      strokeDasharray={sid === 'baseline' ? '' : '5 3'} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* === SELECTED SCENARIO DETAIL === */}
      {scen && (() => {
        const row = getRow(selected)
        const d = (row.pnl||0) - (baseRow.pnl||0)
        const dPF = ((row.pf||0) - (baseRow.pf||0)).toFixed(2)
        const dMDD = (row.mdd||0) - (baseRow.mdd||0)
        return (
          <>
            <div className="card">
              <h3>{scen.label} <span style={{fontWeight:'normal',color:'#888',fontSize:14}}>vs Baseline</span></h3>
              <p style={{color:'#888',marginBottom:12,fontSize:13}}>{scen.desc}</p>
              <div className="kpi-grid">
                <KpiCard label="P&L" value={fmt$(row.pnl||0)} cls={(row.pnl||0) >= 0 ? 'green' : 'red'} />
                <KpiCard label="Δ P&L" value={(d>=0?'+':'-') + fmt$(Math.abs(d))} cls={d >= 0 ? 'green' : 'red'} />
                <KpiCard label="Win Rate" value={(row.wr||0)+'%'} cls={(row.wr||0) >= (baseRow.wr||0) ? 'green' : 'red'} />
                <KpiCard label="PF" value={row.pf} cls={(row.pf||0) >= (baseRow.pf||0) ? 'green' : 'red'} />
                <KpiCard label="Δ PF" value={dPF} cls={+dPF >= 0 ? 'green' : 'red'} />
                <KpiCard label="MDD" value={fmt$(row.mdd||0)} cls="red" />
                <KpiCard label="Δ MDD" value={(dMDD<=0?'':'+') + fmt$(Math.abs(dMDD))} cls={dMDD <= 0 ? 'green' : 'red'} />
                <KpiCard label="RF" value={row.rf} cls={(row.rf||0) >= (baseRow.rf||0) ? 'green' : 'red'} />
              </div>
            </div>

            {/* Per-stock delta bar */}
            <div className="card">
              <h3>Per-Stock P&L Δ vs Baseline</h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={stockDelta} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis type="number" tick={{fill:'#888',fontSize:11}} tickFormatter={v => '$'+v} />
                  <YAxis type="category" dataKey="stock" tick={{fill:'#ccc',fontSize:12}} width={55} />
                  <Tooltip contentStyle={{background:'#1a1d28',border:'1px solid #333'}}
                           formatter={v => ['$'+v.toLocaleString(),'Δ P&L']} />
                  <ReferenceLine x={0} stroke="#666" />
                  <Bar dataKey="delta" radius={[0,4,4,0]}>
                    {stockDelta.map((d, i) => <Cell key={i} fill={d.delta >= 0 ? '#00c853' : '#ff1744'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Side-by-side equity */}
            <div className="chart-row">
              <div className="card">
                <h3>Equity: Baseline{stockFilter !== 'ALL' ? ` (${stockFilter})` : ''}</h3>
                <EquityChart data={baseline?.equity?.[stockFilter] || []} />
              </div>
              <div className="card">
                <h3>Equity: {scen.label}</h3>
                <EquityChart data={scen.equity?.[stockFilter] || []} />
              </div>
            </div>

            {/* Per-stock breakdown */}
            <div className="card research-table-card">
              <h3>Per-Stock Breakdown</h3>
              <div className="research-table-wrap">
                <table className="research-table">
                  <thead>
                    <tr>
                      <th className="sticky-col">Stock</th>
                      <th>Trades</th><th>WR%</th><th>P&L</th><th>Δ P&L</th>
                      <th>MDD</th><th>PF</th><th>RF</th><th>Avg R</th><th>MCL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...stocks, 'ALL'].map(s => {
                      const r = scen.per_stock?.[s] || {}
                      const b = baseline?.per_stock?.[s] || {}
                      const dd = (r.pnl||0) - (b.pnl||0)
                      return (
                        <tr key={s} className={s === 'ALL' ? 'total-row' : ''}>
                          <td className="sticky-col">
                            <span style={{display:'inline-block',width:10,height:10,borderRadius:'50%',
                                          background:STOCK_COLORS[s]||'#888',marginRight:6}} />
                            <strong>{s}</strong>
                          </td>
                          <td>{r.trades}</td>
                          <td className={cmp(r.wr,b.wr,'high')}>{r.wr}%</td>
                          <td className={cmp(r.pnl,b.pnl,'high')}>${(r.pnl||0).toLocaleString()}</td>
                          <td className={dd>=0?'better':'worse'}>{dd>=0?'+':''}{dd.toLocaleString()}</td>
                          <td className={cmp(r.mdd,b.mdd,'low')}>${(r.mdd||0).toLocaleString()}</td>
                          <td className={cmp(r.pf,b.pf,'high')}>{r.pf}</td>
                          <td className={cmp(r.rf,b.rf,'high')}>{r.rf}</td>
                          <td className={cmp(r.avgR,b.avgR,'high')}>{r.avgR}</td>
                          <td className={cmp(r.mcl,b.mcl,'low')}>{r.mcl}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Per-stock equity lines */}
            <div className="card">
              <h3>Per-Stock Equity Curves</h3>
              <ResponsiveContainer width="100%" height={350}>
                <LineChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" tick={{fill:'#888',fontSize:10}}
                         tickFormatter={d => d?.slice(2,10)} allowDuplicatedCategory={false} />
                  <YAxis tick={{fill:'#888',fontSize:11}} tickFormatter={v => '$'+v} />
                  <Tooltip contentStyle={{background:'#1a1d28',border:'1px solid #333'}} />
                  <Legend />
                  {stocks.map(s => (
                    <Line key={s} data={scen.equity?.[s] || []} type="monotone" dataKey="equity"
                          name={s} dot={false} strokeWidth={1.5} stroke={STOCK_COLORS[s]} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )
      })()}

      {/* Scenario list */}
      <div className="card research-descriptions">
        <h3>All Scenarios</h3>
        {Object.entries(data.scenarios).map(([sid, s]) => (
          <div key={sid} className="scenario-desc" onClick={() => setSelected(sid)} style={{cursor:'pointer'}}>
            <strong>{s.label}</strong>
            <span className="scenario-group-tag">{groups[s.group]}</span>
            <span>{s.desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}