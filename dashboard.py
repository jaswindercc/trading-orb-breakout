#!/usr/bin/env python3
"""
Strategy Dashboard - Visual backtest results across all stocks.
Run: python3 dashboard.py  (opens in browser at http://localhost:8050)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, html, os, tempfile, webbrowser, threading

DATA_DIR = Path("/workspaces/jas/data")

# ============================================================
# DATA + BACKTEST (same logic as research3.py)
# ============================================================

def load_stock(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def load_all():
    stocks = {}
    for f in sorted(DATA_DIR.glob("*.csv")):
        name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
        stocks[name] = load_stock(f)
    return stocks

def add_ind(df, fast=10, slow=50, tl=20):
    df = df.copy()
    df['fSma'] = df['Close'].rolling(fast).mean()
    df['sSma'] = df['Close'].rolling(slow).mean()
    df['tr'] = np.maximum(df['High']-df['Low'],
        np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['atr'] = df['tr'].rolling(14).mean()
    df['tEma'] = df['Close'].ewm(span=tl, adjust=False).mean()
    df['bRng'] = df['High'] - df['Low']
    df['fAbv'] = (df['fSma'] > df['sSma']).astype(int)
    df['xUp'] = (df['fAbv']==1) & (df['fAbv'].shift(1)==0)
    df['xDn'] = (df['fAbv']==0) & (df['fAbv'].shift(1)==1)
    return df

def backtest_stock(df, stock_name):
    """Backtest with current pine_orb defaults"""
    cfg = dict(fast=10, slow=50, mdist=3.0, mbar=3.0, sla=2.0, tl=20, tb=1.0, tsr=1.5)
    df = add_ind(df, cfg['fast'], cfg['slow'], cfg['tl'])
    
    trades = []
    pos=0; ep=er=tsl=0.0; edir=0; lcd=0; bsc=999
    
    for i in range(1, len(df)):
        r = df.iloc[i]; atr = r['atr']
        if pd.isna(atr) or atr<=0: continue
        
        if r['xUp']: lcd=1; bsc=0
        elif r['xDn']: lcd=-1; bsc=0
        else: bsc+=1
        
        # Exits
        if pos!=0:
            hsl=htp=False; xp=0.0
            if pos==1:
                if r['Low']<=tsl: xp=tsl; hsl=True
                if not hsl:
                    cr=(r['Close']-ep)/er if er>0 else 0
                    if cr>=cfg['tsr']:
                        et=r['tEma']-cfg['tb']*atr
                        if et>tsl: tsl=et
            else:
                if r['High']>=tsl: xp=tsl; hsl=True
                if not hsl:
                    cr=(ep-r['Close'])/er if er>0 else 0
                    if cr>=cfg['tsr']:
                        et=r['tEma']+cfg['tb']*atr
                        if et<tsl: tsl=et
            
            if hsl:
                t=trades[-1]
                t['exit_date']=str(r['Date'].date()); t['exit_price']=round(xp,2)
                t['pnl_r']=round(((xp-ep)/er if pos==1 else (ep-xp)/er) if er>0 else 0, 2)
                t['exit_reason']='SL'
                pos=0
        
        # Entries
        if pos==0:
            xl=(lcd==1 and bsc==0); xs=(lcd==-1 and bsc==0)
            dok=abs(r['Close']-r['fSma'])<=cfg['mdist']*atr
            bok=r['bRng']<=cfg['mbar']*atr
            
            if dok and bok and xl:
                sl=r['Close']-cfg['sla']*atr; rk=r['Close']-sl
                pos=1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':stock_name,'entry_date':str(r['Date'].date()),
                    'dir':'LONG','entry_price':round(r['Close'],2),'sl':round(sl,2),
                    'risk':round(rk,2),'exit_date':'','exit_price':0,'pnl_r':0,'exit_reason':''})
            elif dok and bok and xs:
                sl=r['Close']+cfg['sla']*atr; rk=sl-r['Close']
                pos=-1; ep=r['Close']; er=rk; tsl=sl
                trades.append({'stock':stock_name,'entry_date':str(r['Date'].date()),
                    'dir':'SHORT','entry_price':round(r['Close'],2),'sl':round(sl,2),
                    'risk':round(rk,2),'exit_date':'','exit_price':0,'pnl_r':0,'exit_reason':''})
    
    # Close open
    if pos!=0 and trades:
        t=trades[-1]; l=df.iloc[-1]
        t['exit_date']=str(l['Date'].date()); t['exit_price']=round(l['Close'],2)
        t['pnl_r']=round(((l['Close']-ep)/er if pos==1 else (ep-l['Close'])/er) if er>0 else 0, 2)
        t['exit_reason']='Open'
    
    return trades, df

# ============================================================
# RUN ALL
# ============================================================

print("Loading data and running backtests...")
stocks = load_all()
all_trades = []
stock_data = {}

for name, df in stocks.items():
    trades, processed_df = backtest_stock(df, name)
    all_trades.extend(trades)
    stock_data[name] = processed_df
    print(f"  {name}: {len(trades)} trades")

# Compute metrics per stock
def compute_metrics(trades):
    if not trades: return {}
    pnls = [t['pnl_r'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    cu = np.cumsum(pnls)
    dd = (np.maximum.accumulate(cu) - cu).max() if len(cu)>0 else 0
    mc=cc=b2b=0
    for p in pnls:
        if p<=0: cc+=1; b2b+=(1 if cc>=2 else 0); mc=max(mc,cc)
        else: cc=0
    tw=sum(wins) if wins else 0; tl=abs(sum(losses)) if losses else 0.001
    return {
        'trades': len(trades), 'win_rate': round(len(wins)/len(trades)*100,1) if trades else 0,
        'total_r': round(sum(pnls),2), 'max_dd': round(dd,2),
        'max_consec_loss': mc, 'b2b_sl': b2b,
        'profit_factor': round(tw/tl,2),
        'avg_win': round(np.mean(wins),2) if wins else 0,
        'avg_loss': round(np.mean(losses),2) if losses else 0
    }

per_stock_metrics = {}
for name in sorted(stocks.keys()):
    st = [t for t in all_trades if t['stock']==name]
    per_stock_metrics[name] = compute_metrics(st)

combined_metrics = compute_metrics(all_trades)

# Build equity curves per stock
equity_curves = {}
for name in sorted(stocks.keys()):
    st = sorted([t for t in all_trades if t['stock']==name], key=lambda t: t['entry_date'])
    if st:
        dates = [t['exit_date'] for t in st]
        cum_r = list(np.cumsum([t['pnl_r'] for t in st]))
        equity_curves[name] = {'dates': dates, 'equity': cum_r}

# Combined equity
sorted_all = sorted(all_trades, key=lambda t: t['exit_date'] if t['exit_date'] else t['entry_date'])
combined_eq = {'dates': [], 'equity': []}
cum = 0
for t in sorted_all:
    cum += t['pnl_r']
    combined_eq['dates'].append(t['exit_date'] or t['entry_date'])
    combined_eq['equity'].append(round(cum, 2))

# ============================================================
# BUILD HTML DASHBOARD
# ============================================================

colors = ['#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f','#edc948','#b07aa1']
stock_names = sorted(stocks.keys())
color_map = {n: colors[i % len(colors)] for i, n in enumerate(stock_names)}

# Equity curve traces
eq_traces = []
for name in stock_names:
    if name in equity_curves:
        ec = equity_curves[name]
        eq_traces.append(f"""{{
            x: {json.dumps(ec['dates'])},
            y: {json.dumps(ec['equity'])},
            name: '{name}',
            type: 'scatter',
            mode: 'lines',
            line: {{color: '{color_map[name]}', width: 2}}
        }}""")

# Combined equity trace
eq_traces.append(f"""{{
    x: {json.dumps(combined_eq['dates'])},
    y: {json.dumps(combined_eq['equity'])},
    name: 'COMBINED',
    type: 'scatter',
    mode: 'lines',
    line: {{color: '#333', width: 3, dash: 'dash'}}
}}""")

# Win rate bar chart
wr_data = {n: per_stock_metrics[n]['win_rate'] for n in stock_names}
# Total R bar chart
tr_data = {n: per_stock_metrics[n]['total_r'] for n in stock_names}
# B2B bar chart
b2b_data = {n: per_stock_metrics[n]['b2b_sl'] for n in stock_names}
# Max DD bar chart
dd_data = {n: per_stock_metrics[n]['max_dd'] for n in stock_names}

# Trade distribution (wins vs losses per stock)
wins_per = {n: len([t for t in all_trades if t['stock']==n and t['pnl_r']>0]) for n in stock_names}
losses_per = {n: len([t for t in all_trades if t['stock']==n and t['pnl_r']<=0]) for n in stock_names}

# R distribution histogram
all_pnls = [t['pnl_r'] for t in all_trades]

# Trade table rows
trade_rows = ""
for t in sorted(all_trades, key=lambda x: x['entry_date']):
    clr = '#2d7d2d' if t['pnl_r'] > 0 else '#c0392b' if t['pnl_r'] < 0 else '#888'
    trade_rows += f"""<tr>
        <td>{t['stock']}</td><td>{t['dir']}</td>
        <td>{t['entry_date']}</td><td>${t['entry_price']:.2f}</td>
        <td>{t['exit_date']}</td><td>${t['exit_price']:.2f}</td>
        <td style="color:{clr};font-weight:bold">{t['pnl_r']:+.2f}R</td>
        <td>{t['exit_reason']}</td>
    </tr>"""

# Metrics table
metrics_rows = ""
for n in stock_names:
    m = per_stock_metrics[n]
    clr = '#2d7d2d' if m['total_r'] > 0 else '#c0392b'
    metrics_rows += f"""<tr>
        <td style="font-weight:bold;color:{color_map[n]}">{n}</td>
        <td>{m['trades']}</td><td>{m['win_rate']}%</td>
        <td style="color:{clr};font-weight:bold">{m['total_r']:+.1f}R</td>
        <td>{m['max_dd']:.1f}R</td><td>{m['max_consec_loss']}</td>
        <td>{m['b2b_sl']}</td><td>{m['profit_factor']:.2f}</td>
        <td>{m['avg_win']:+.2f}R</td><td>{m['avg_loss']:+.2f}R</td>
    </tr>"""

# Combined row
cm = combined_metrics
clr = '#2d7d2d' if cm['total_r'] > 0 else '#c0392b'
metrics_rows += f"""<tr style="background:#1a1a2e;font-weight:bold">
    <td>COMBINED</td><td>{cm['trades']}</td><td>{cm['win_rate']}%</td>
    <td style="color:{clr}">{cm['total_r']:+.1f}R</td>
    <td>{cm['max_dd']:.1f}R</td><td>{cm['max_consec_loss']}</td>
    <td>{cm['b2b_sl']}</td><td>{cm['profit_factor']:.2f}</td>
    <td>{cm['avg_win']:+.2f}R</td><td>{cm['avg_loss']:+.2f}R</td>
</tr>"""

dashboard_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ORB Strategy Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0d1117; color:#c9d1d9; font-family:'Segoe UI',system-ui,sans-serif; padding:20px; }}
h1 {{ color:#58a6ff; margin-bottom:5px; font-size:28px; }}
h2 {{ color:#8b949e; font-size:14px; margin-bottom:20px; font-weight:normal; }}
h3 {{ color:#58a6ff; margin:20px 0 10px; font-size:18px; }}
.grid {{ display:grid; gap:15px; margin-bottom:20px; }}
.grid-2 {{ grid-template-columns: 1fr 1fr; }}
.grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
.card {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:15px; }}
.card-title {{ color:#8b949e; font-size:12px; text-transform:uppercase; margin-bottom:5px; }}
.card-value {{ font-size:28px; font-weight:bold; }}
.green {{ color:#3fb950; }} .red {{ color:#f85149; }} .blue {{ color:#58a6ff; }} .yellow {{ color:#d29922; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#21262d; color:#8b949e; padding:8px 10px; text-align:left; position:sticky; top:0; }}
td {{ padding:6px 10px; border-bottom:1px solid #21262d; }}
tr:hover {{ background:#1c2128; }}
.chart {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px; margin-bottom:15px; }}
.tabs {{ display:flex; gap:5px; margin-bottom:15px; }}
.tab {{ padding:8px 16px; background:#21262d; border:1px solid #30363d; border-radius:6px; cursor:pointer; color:#8b949e; font-size:13px; }}
.tab.active {{ background:#1f6feb; color:white; border-color:#1f6feb; }}
.scroll-table {{ max-height:400px; overflow-y:auto; }}
</style>
</head>
<body>
<h1>📊 ORB v3 Strategy Dashboard</h1>
<h2>SMA 10/50 Crossover | SL 2.0×ATR | EMA Trail @1.5R | 7 Stocks | 2021-2026</h2>

<!-- KPI Cards -->
<div class="grid grid-4">
    <div class="card">
        <div class="card-title">Total Return</div>
        <div class="card-value {'green' if cm['total_r']>0 else 'red'}">{cm['total_r']:+.1f}R</div>
    </div>
    <div class="card">
        <div class="card-title">Win Rate</div>
        <div class="card-value blue">{cm['win_rate']}%</div>
    </div>
    <div class="card">
        <div class="card-title">Max Drawdown</div>
        <div class="card-value red">{cm['max_dd']:.1f}R</div>
    </div>
    <div class="card">
        <div class="card-title">Profit Factor</div>
        <div class="card-value yellow">{cm['profit_factor']:.2f}</div>
    </div>
    <div class="card">
        <div class="card-title">Total Trades</div>
        <div class="card-value blue">{cm['trades']}</div>
    </div>
    <div class="card">
        <div class="card-title">Back-to-Back SLs</div>
        <div class="card-value {'green' if cm['b2b_sl']<20 else 'red'}">{cm['b2b_sl']}</div>
    </div>
    <div class="card">
        <div class="card-title">Max Consec Loss</div>
        <div class="card-value {'green' if cm['max_consec_loss']<=3 else 'yellow' if cm['max_consec_loss']<=5 else 'red'}">{cm['max_consec_loss']}</div>
    </div>
    <div class="card">
        <div class="card-title">Avg Win / Avg Loss</div>
        <div class="card-value green">{cm['avg_win']:+.1f} / {cm['avg_loss']:.1f}</div>
    </div>
</div>

<!-- Equity Curves -->
<div class="chart" id="equity-chart" style="height:400px;"></div>

<!-- Charts Row -->
<div class="grid grid-2">
    <div class="chart" id="winrate-chart" style="height:300px;"></div>
    <div class="chart" id="totalr-chart" style="height:300px;"></div>
</div>
<div class="grid grid-2">
    <div class="chart" id="b2b-chart" style="height:300px;"></div>
    <div class="chart" id="rdist-chart" style="height:300px;"></div>
</div>

<!-- Per-Stock Metrics Table -->
<h3>Per-Stock Breakdown</h3>
<div class="card">
<table>
<thead><tr>
    <th>Stock</th><th>Trades</th><th>Win Rate</th><th>Total R</th>
    <th>Max DD</th><th>Consec L</th><th>B2B SL</th><th>PF</th>
    <th>Avg Win</th><th>Avg Loss</th>
</tr></thead>
<tbody>{metrics_rows}</tbody>
</table>
</div>

<!-- Trade Log -->
<h3>Trade Log ({len(all_trades)} trades)</h3>
<div class="card scroll-table">
<table>
<thead><tr>
    <th>Stock</th><th>Dir</th><th>Entry</th><th>Price</th>
    <th>Exit</th><th>Price</th><th>P&L</th><th>Reason</th>
</tr></thead>
<tbody>{trade_rows}</tbody>
</table>
</div>

<script>
const darkLayout = {{
    paper_bgcolor: '#161b22', plot_bgcolor: '#161b22',
    font: {{ color: '#c9d1d9', size: 12 }},
    xaxis: {{ gridcolor: '#21262d', linecolor: '#30363d' }},
    yaxis: {{ gridcolor: '#21262d', linecolor: '#30363d' }},
    margin: {{ t: 40, b: 40, l: 50, r: 20 }},
    legend: {{ bgcolor: 'rgba(0,0,0,0)', font: {{ size: 11 }} }}
}};

// Equity Curves
Plotly.newPlot('equity-chart', [{','.join(eq_traces)}],
    {{...darkLayout, title: 'Equity Curves (Cumulative R)', yaxis: {{...darkLayout.yaxis, title: 'R'}}}});

// Win Rate
Plotly.newPlot('winrate-chart', [{{
    x: {json.dumps(stock_names)},
    y: {json.dumps([wr_data[n] for n in stock_names])},
    type: 'bar',
    marker: {{ color: {json.dumps([color_map[n] for n in stock_names])} }}
}}], {{...darkLayout, title: 'Win Rate by Stock (%)', yaxis: {{...darkLayout.yaxis, title: '%'}}}});

// Total R
Plotly.newPlot('totalr-chart', [{{
    x: {json.dumps(stock_names)},
    y: {json.dumps([tr_data[n] for n in stock_names])},
    type: 'bar',
    marker: {{ color: {json.dumps([('#3fb950' if tr_data[n]>0 else '#f85149') for n in stock_names])} }}
}}], {{...darkLayout, title: 'Total R by Stock'}});

// B2B + DD
Plotly.newPlot('b2b-chart', [
    {{ x: {json.dumps(stock_names)}, y: {json.dumps([b2b_data[n] for n in stock_names])},
       name: 'B2B SLs', type: 'bar', marker: {{ color: '#f85149' }} }},
    {{ x: {json.dumps(stock_names)}, y: {json.dumps([dd_data[n] for n in stock_names])},
       name: 'Max DD (R)', type: 'bar', marker: {{ color: '#d29922' }} }}
], {{...darkLayout, title: 'Back-to-Back SLs & Max Drawdown', barmode: 'group'}});

// R Distribution
Plotly.newPlot('rdist-chart', [{{
    x: {json.dumps(all_pnls)},
    type: 'histogram',
    xbins: {{ size: 0.5 }},
    marker: {{ color: '#58a6ff', line: {{ color: '#30363d', width: 1 }} }}
}}], {{...darkLayout, title: 'P&L Distribution (R)', xaxis: {{...darkLayout.xaxis, title: 'R'}}, yaxis: {{...darkLayout.yaxis, title: 'Count'}}}});
</script>

<p style="color:#484f58;text-align:center;margin-top:20px;font-size:12px;">
    Generated from /data — SPY, AAPL, AMD, GOOGL, META, NVDA, TSLA daily 2021-2026
</p>
</body></html>"""

# Write and serve
OUT = Path("/workspaces/jas/dashboard.html")
OUT.write_text(dashboard_html)
print(f"\nDashboard written to {OUT}")
print(f"Opening in browser...")

PORT = 8080

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/workspaces/jas", **kwargs)
    def log_message(self, format, *args):
        pass  # suppress logs

server = HTTPServer(('0.0.0.0', PORT), Handler)
print(f"\nServing at http://localhost:{PORT}/dashboard.html")
print("Press Ctrl+C to stop")

# Open in browser
os.system(f'"$BROWSER" http://localhost:{PORT}/dashboard.html &')

server.serve_forever()
