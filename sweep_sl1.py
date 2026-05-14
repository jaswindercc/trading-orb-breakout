#!/usr/bin/env python3
"""Quick parameter sweep with SL 1.0× as the new baseline."""
import pandas as pd, numpy as np, time
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
RISK = 100.0
STOCKS = ['SPY','AAPL','AMD','GOOGL','META','NVDA','TSLA']

def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def precompute(df):
    d = df.copy()
    d['fSma']  = d['Close'].rolling(10).mean()
    d['sSma']  = d['Close'].rolling(50).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr']  = d['tr'].rolling(14).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp']  = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn']  = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)
    return d

def make_ema(arr, span):
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(arr)
    ema[0] = arr[0]
    for i in range(1, len(arr)):
        ema[i] = alpha * arr[i] + (1 - alpha) * ema[i-1]
    return ema

def backtest(df, params):
    sla  = params['sla']
    tsr  = params['tsr']
    te   = params['te']
    tb   = params['tb']
    mbar = params.get('mbar', 2.0)
    mdist= params.get('mdist', 3.0)

    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; atr = df['atr'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values; xUp = df['xUp'].values; xDn = df['xDn'].values
    tEma = make_ema(c, te)

    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999

    for i in range(1, len(df)):
        a = atr[i]
        if np.isnan(a) or a <= 0: continue
        if xUp[i]:  lcd = 1; bsc = 0
        elif xDn[i]: lcd = -1; bsc = 0
        else: bsc += 1

        if pos != 0:
            hit = False; xp = 0.0
            if pos == 1:
                if l[i] <= tsl: xp = tsl; hit = True
                if not hit:
                    cr = (c[i] - ep) / er if er > 0 else 0
                    if cr >= tsr:
                        et = tEma[i] - tb * a
                        if et > tsl: tsl = et
            else:
                if h[i] >= tsl: xp = tsl; hit = True
                if not hit:
                    cr = (ep - c[i]) / er if er > 0 else 0
                    if cr >= tsr:
                        et = tEma[i] + tb * a
                        if et < tsl: tsl = et
            if hit:
                pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
                trades.append(pnl_r * RISK)
                pos = 0

        if pos == 0:
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a
            if dok and bok and xl:
                sl_v = c[i] - sla * a; rk = c[i] - sl_v
                pos = 1; ep = c[i]; er = rk; tsl = sl_v
            elif dok and bok and xs:
                sl_v = c[i] + sla * a; rk = sl_v - c[i]
                pos = -1; ep = c[i]; er = rk; tsl = sl_v

    # close open position
    if pos != 0:
        xp = c[-1]
        pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
        trades.append(pnl_r * RISK)

    return trades

def metrics(trades_pnl):
    if not trades_pnl: return (0, 0, 0, 0, 0, 0)
    n = len(trades_pnl)
    wins = [t for t in trades_pnl if t > 0]
    pnl = sum(trades_pnl)
    gw = sum(t for t in trades_pnl if t > 0)
    gl = abs(sum(t for t in trades_pnl if t <= 0))
    pf = round(gw/gl, 2) if gl else 99
    wr = round(100*len(wins)/n, 1)
    eq = 0; peak = 0; mdd = 0
    for t in trades_pnl:
        eq += t; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    rf = round(pnl/mdd, 2) if mdd > 0 else 99
    return (n, pnl, wr, pf, mdd, rf)

# ── Load ──
print("Loading data...")
dfs = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    if name in STOCKS:
        dfs[name] = precompute(load(f))

# ── New baseline: SL 1.0× with current defaults ──
NEW_BASE = dict(sla=1.0, tsr=2.5, te=20, tb=1.0, mbar=2.0, mdist=3.0)

scenarios = {}
scenarios['new_baseline'] = ('SL1.0 Baseline (current pine_orb)', NEW_BASE)

# Trail Start R sweep
for tsr in [1.0, 1.5, 2.0, 3.0, 3.5, 4.0]:
    scenarios[f'tsr_{tsr}'] = (f'Trail start {tsr}R', {**NEW_BASE, 'tsr': tsr})

# Trail EMA sweep
for te in [10, 15, 25, 30, 40]:
    scenarios[f'te_{te}'] = (f'Trail EMA {te}', {**NEW_BASE, 'te': te})

# Trail buffer sweep
for tb in [0.0, 0.25, 0.5, 0.75, 1.25, 1.5, 2.0]:
    scenarios[f'tb_{tb}'] = (f'Trail buffer {tb}×', {**NEW_BASE, 'tb': tb})

# SL fine-tune around 1.0
for sla in [0.5, 0.75, 1.25, 1.5]:
    scenarios[f'sl_{sla}'] = (f'SL {sla}× ATR', {**NEW_BASE, 'sla': sla})

# Max bar filter
for mbar in [1.0, 1.5, 2.5, 3.0]:
    scenarios[f'mbar_{mbar}'] = (f'Max bar {mbar}×ATR', {**NEW_BASE, 'mbar': mbar})

# Max dist filter
for mdist in [1.5, 2.0, 2.5, 4.0, 5.0]:
    scenarios[f'mdist_{mdist}'] = (f'Max dist {mdist}×ATR', {**NEW_BASE, 'mdist': mdist})

# Best combos
combos = [
    ('combo_tsr20_te15', {**NEW_BASE, 'tsr': 2.0, 'te': 15}),
    ('combo_tsr20_tb05', {**NEW_BASE, 'tsr': 2.0, 'tb': 0.5}),
    ('combo_tsr20_te15_tb05', {**NEW_BASE, 'tsr': 2.0, 'te': 15, 'tb': 0.5}),
    ('combo_tsr15_te15', {**NEW_BASE, 'tsr': 1.5, 'te': 15}),
    ('combo_tsr30_te15', {**NEW_BASE, 'tsr': 3.0, 'te': 15}),
    ('combo_tsr20_te15_tb075', {**NEW_BASE, 'tsr': 2.0, 'te': 15, 'tb': 0.75}),
]
for sid, p in combos:
    label = ' + '.join(f'{k}={v}' for k, v in p.items() if p[k] != NEW_BASE.get(k))
    scenarios[sid] = (f'Combo: {label}', p)

print(f"\n{len(scenarios)} scenarios × {len(STOCKS)} stocks\n")
print(f"{'Scenario':<45s} {'Trades':>6s} {'P&L':>9s} {'WR%':>6s} {'PF':>6s} {'MaxDD':>8s} {'RF':>6s}")
print("-" * 90)

for sid, (label, params) in sorted(scenarios.items(), key=lambda x: x[0]):
    all_pnl = []
    for name in STOCKS:
        all_pnl.extend(backtest(dfs[name], params))
    n, pnl, wr, pf, mdd, rf = metrics(all_pnl)
    marker = " <<<" if sid == 'new_baseline' else ""
    print(f"  {label:<43s} {n:>6d} ${pnl:>8.0f} {wr:>5.1f}% {pf:>5.2f} ${mdd:>7.0f} {rf:>5.2f}{marker}")
