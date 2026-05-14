#!/usr/bin/env python3
"""
Deep parameter research: sweep trail start R, SL mult, trail EMA, trail buffer,
and re-entry variants. Per-stock equity curves + comparison data for dashboard.
"""
import pandas as pd, numpy as np, json, itertools, time
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/research_data.json")
RISK = 100.0
STOCKS = ['SPY','AAPL','AMD','GOOGL','META','NVDA','TSLA']

# ── data loading ─────────────────────────────────────────────────────
def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def precompute(df):
    """Precompute all indicators including SMA100/200 for re-entry filters."""
    d = df.copy()
    d['fSma']   = d['Close'].rolling(10).mean()
    d['sSma']   = d['Close'].rolling(50).mean()
    d['sma100'] = d['Close'].rolling(100).mean()
    d['sma200'] = d['Close'].rolling(200).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr']  = d['tr'].rolling(14).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp']  = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn']  = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)
    return d

def make_ema(close_arr, span):
    """Fast EMA calculation using numpy."""
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(close_arr)
    ema[0] = close_arr[0]
    for i in range(1, len(close_arr)):
        ema[i] = alpha * close_arr[i] + (1 - alpha) * ema[i-1]
    return ema

# ── backtest engine ──────────────────────────────────────────────────
def backtest(df, name, params, reentry=None):
    """
    params = dict with: sla, tsr, te (trail ema len), tb (trail buffer), mbar, mdist
    reentry = None or dict with: mode, sl_mult, ma_filter, min_wait
    Returns list of trade dicts.
    """
    sla   = params['sla']
    tsr   = params['tsr']
    te    = params['te']
    tb    = params['tb']
    mbar  = params.get('mbar', 2.0)
    mdist = params.get('mdist', 3.0)

    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; sSma = df['sSma'].values
    atr = df['atr'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values
    xUp = df['xUp'].values; xDn = df['xDn'].values
    sma100 = df['sma100'].values; sma200 = df['sma200'].values
    dates = df['Date'].values
    tEma = make_ema(c, te)

    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999
    last_trail_dir = 0; last_trail_bar = -999; reentry_used = False

    for i in range(1, len(df)):
        a = atr[i]
        if np.isnan(a) or a <= 0: continue

        if xUp[i]:  lcd = 1; bsc = 0
        elif xDn[i]: lcd = -1; bsc = 0
        else: bsc += 1

        # ── manage open position ──
        if pos != 0:
            hit_sl = False; xp = 0.0
            if pos == 1:
                if l[i] <= tsl: xp = tsl; hit_sl = True
                if not hit_sl:
                    cr = (c[i] - ep) / er if er > 0 else 0
                    if cr >= tsr:
                        et = tEma[i] - tb * a
                        if et > tsl: tsl = et
            else:
                if h[i] >= tsl: xp = tsl; hit_sl = True
                if not hit_sl:
                    cr = (ep - c[i]) / er if er > 0 else 0
                    if cr >= tsr:
                        et = tEma[i] + tb * a
                        if et < tsl: tsl = et

            if hit_sl:
                pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
                is_trail = pnl_r > 0
                ed = pd.Timestamp(dates[trades[-1]['_ei']])
                xd = pd.Timestamp(dates[i])
                dur = int((xd - ed).days)
                t = trades[-1]
                t['exitDate'] = str(dates[i])[:10]
                t['exitPrice'] = round(xp, 2)
                t['pnlR'] = round(pnl_r, 2)
                t['pnlDollar'] = round(pnl_r * RISK, 2)
                t['exitReason'] = 'Trail' if is_trail else 'SL'
                t['durationDays'] = dur
                if is_trail:
                    last_trail_dir = pos; last_trail_bar = i; reentry_used = False
                pos = 0

        # ── entry ──
        if pos == 0:
            entered = False
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a

            if dok and bok and xl:
                sl_v = c[i] - sla * a; rk = c[i] - sl_v
                qty = max(1, round(RISK / rk)) if rk > 0 else 1
                pos = 1; ep = c[i]; er = rk; tsl = sl_v
                trades.append(_mkt(name, 'LONG', dates[i], c[i], sl_v, rk, qty, i, False))
                entered = True; last_trail_dir = 0
            elif dok and bok and xs:
                sl_v = c[i] + sla * a; rk = sl_v - c[i]
                qty = max(1, round(RISK / rk)) if rk > 0 else 1
                pos = -1; ep = c[i]; er = rk; tsl = sl_v
                trades.append(_mkt(name, 'SHORT', dates[i], c[i], sl_v, rk, qty, i, False))
                entered = True; last_trail_dir = 0

            # re-entry
            if not entered and reentry and last_trail_dir != 0 and not reentry_used:
                bars_since = i - last_trail_bar
                if bars_since < reentry.get('min_wait', 2): continue
                trend_ok = (last_trail_dir == 1 and fAbv[i] == 1) or (last_trail_dir == -1 and fAbv[i] == 0)
                if not trend_ok: last_trail_dir = 0; continue
                if not (bok and dok): continue

                ma_f = reentry.get('ma_filter')
                if ma_f:
                    mv = sma100[i] if ma_f == 100 else sma200[i]
                    if np.isnan(mv): continue
                    if last_trail_dir == 1 and c[i] < mv: continue
                    if last_trail_dir == -1 and c[i] > mv: continue

                # EMA pullback trigger
                touched = (last_trail_dir == 1 and l[i] <= tEma[i]) or (last_trail_dir == -1 and h[i] >= tEma[i])
                closed_ok = (last_trail_dir == 1 and c[i] > tEma[i]) or (last_trail_dir == -1 and c[i] < tEma[i])
                if not (touched and closed_ok): continue

                re_sl = reentry.get('sl_mult', sla)
                if last_trail_dir == 1:
                    sl_v = c[i] - re_sl * a; rk = c[i] - sl_v
                    qty = max(1, round(RISK / rk)) if rk > 0 else 1
                    pos = 1; ep = c[i]; er = rk; tsl = sl_v
                    trades.append(_mkt(name, 'LONG', dates[i], c[i], sl_v, rk, qty, i, True))
                else:
                    sl_v = c[i] + re_sl * a; rk = sl_v - c[i]
                    qty = max(1, round(RISK / rk)) if rk > 0 else 1
                    pos = -1; ep = c[i]; er = rk; tsl = sl_v
                    trades.append(_mkt(name, 'SHORT', dates[i], c[i], sl_v, rk, qty, i, True))
                reentry_used = True

    # close open
    if pos != 0 and trades:
        t = trades[-1]; last_row = df.iloc[-1]
        pnl_r = ((last_row['Close'] - ep) / er if pos == 1 else (ep - last_row['Close']) / er) if er > 0 else 0
        ed = pd.Timestamp(dates[t['_ei']])
        t['exitDate'] = str(dates[len(df)-1])[:10]
        t['exitPrice'] = round(last_row['Close'], 2)
        t['pnlR'] = round(pnl_r, 2); t['pnlDollar'] = round(pnl_r * RISK, 2)
        t['exitReason'] = 'Open'; t['durationDays'] = int((last_row['Date'] - ed).days)

    for t in trades: t.pop('_ei', None)
    return trades

def _mkt(name, d, date, px, sl, rk, qty, idx, isre):
    return {'stock':name,'dir':d,'entryDate':str(date)[:10],'entryPrice':round(px,2),
            'sl':round(sl,2),'risk':round(rk,2),'qty':qty,'exitDate':'','exitPrice':0,
            'pnlR':0,'pnlDollar':0,'exitReason':'','durationDays':0,'isReentry':isre,'_ei':idx}

def calc_metrics(trades):
    if not trades: return dict(trades=0,wr=0,pnl=0,mdd=0,pf=0,avgR=0,rf=0,mcl=0,re_trades=0,re_wr=0,re_pnl=0)
    wins=[t for t in trades if t['pnlDollar']>0]
    losses=[t for t in trades if t['pnlDollar']<=0]
    pnl=sum(t['pnlDollar'] for t in trades)
    gw=sum(t['pnlDollar'] for t in wins); gl=abs(sum(t['pnlDollar'] for t in losses))
    pf=round(gw/gl,2) if gl else 99
    wr=round(100*len(wins)/len(trades),1)
    avgr=round(sum(t['pnlR'] for t in trades)/len(trades),2)
    eq=0;peak=0;mdd=0
    for t in trades: eq+=t['pnlDollar']; peak=max(peak,eq); mdd=max(mdd,peak-eq)
    rf=round(pnl/mdd,2) if mdd>0 else 99
    cl=0;mcl=0
    for t in trades:
        if t['pnlDollar']<=0: cl+=1
        else: cl=0
        mcl=max(mcl,cl)
    ret=[t for t in trades if t.get('isReentry')]
    rw=[t for t in ret if t['pnlDollar']>0]
    return dict(trades=len(trades),wr=wr,pnl=round(pnl,2),mdd=round(mdd,2),pf=pf,avgR=avgr,rf=rf,mcl=mcl,
                re_trades=len(ret),re_wr=round(100*len(rw)/len(ret),1) if ret else 0,re_pnl=round(sum(t['pnlDollar'] for t in ret),2))

def equity_curve(trades):
    eq=0; pts=[]
    for t in trades:
        eq+=t['pnlDollar']
        pts.append({'date':t['exitDate'],'equity':round(eq,2),'pnl':t['pnlDollar']})
    return pts

# ── Load data ────────────────────────────────────────────────────────
print("Loading & precomputing data...")
t0 = time.time()
dfs = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    if name in STOCKS:
        dfs[name] = precompute(load(f))
        print(f"  {name}: {len(dfs[name])} bars")

# ── Define all scenarios ─────────────────────────────────────────────
BASELINE = dict(sla=2.0, tsr=2.5, te=20, tb=1.0, mbar=2.0, mdist=3.0)

scenarios = {}

# 1. Baseline
scenarios['baseline'] = {
    'label': 'v4 Baseline',
    'desc': 'Current: SL 2.0× ATR, Trail starts 2.5R, EMA20 trail, buffer 1.0×',
    'params': BASELINE, 'reentry': None, 'group': 'baseline'
}

# 2. Trail Start R variations
for tsr in [1.0, 1.5, 2.0, 3.0, 3.5]:
    p = {**BASELINE, 'tsr': tsr}
    scenarios[f'tsr_{tsr}'] = {
        'label': f'Trail start {tsr}R',
        'desc': f'Same as baseline but trail activates at {tsr}R instead of 2.5R',
        'params': p, 'reentry': None, 'group': 'trail_start'
    }

# 3. SL multiplier variations
for sla in [1.0, 1.25, 1.5, 2.5, 3.0]:
    p = {**BASELINE, 'sla': sla}
    scenarios[f'sl_{sla}'] = {
        'label': f'SL {sla}× ATR',
        'desc': f'Stop loss at {sla}× ATR instead of 2.0×',
        'params': p, 'reentry': None, 'group': 'stop_loss'
    }

# 4. Trail EMA length variations
for te in [10, 15, 30, 40]:
    p = {**BASELINE, 'te': te}
    scenarios[f'te_{te}'] = {
        'label': f'Trail EMA {te}',
        'desc': f'Trail with EMA({te}) instead of EMA(20)',
        'params': p, 'reentry': None, 'group': 'trail_ema'
    }

# 5. Trail buffer variations
for tb in [0.0, 0.5, 1.5, 2.0]:
    p = {**BASELINE, 'tb': tb}
    scenarios[f'tb_{tb}'] = {
        'label': f'Trail buffer {tb}×',
        'desc': f'Trail buffer at {tb}× ATR instead of 1.0×',
        'params': p, 'reentry': None, 'group': 'trail_buffer'
    }

# 6. Combined improvements (promising combos)
combos = [
    ('combo_tsr15_sl15', 'TSR 1.5R + SL 1.5×', dict(tsr=1.5, sla=1.5)),
    ('combo_tsr20_sl15', 'TSR 2.0R + SL 1.5×', dict(tsr=2.0, sla=1.5)),
    ('combo_tsr20_te15', 'TSR 2.0R + EMA15 trail', dict(tsr=2.0, te=15)),
    ('combo_tsr15_te15', 'TSR 1.5R + EMA15 trail', dict(tsr=1.5, te=15)),
    ('combo_tsr20_tb05', 'TSR 2.0R + buffer 0.5×', dict(tsr=2.0, tb=0.5)),
    ('combo_tsr20_te15_tb05', 'TSR 2.0R + EMA15 + buffer 0.5×', dict(tsr=2.0, te=15, tb=0.5)),
    ('combo_tsr15_te15_tb05', 'TSR 1.5R + EMA15 + buffer 0.5×', dict(tsr=1.5, te=15, tb=0.5)),
    ('combo_tsr20_sl15_te15', 'TSR 2.0R + SL 1.5× + EMA15', dict(tsr=2.0, sla=1.5, te=15)),
]
for sid, label, overrides in combos:
    p = {**BASELINE, **overrides}
    desc_parts = [f"{k}={v}" for k,v in overrides.items()]
    scenarios[sid] = {
        'label': label,
        'desc': f'Combined: {", ".join(desc_parts)}',
        'params': p, 'reentry': None, 'group': 'combo'
    }

# 7. Best param combos WITH re-entry
reentry_combos = [
    ('re_base_sma200', 'Baseline + re-entry SMA200', BASELINE, dict(mode='ema_pb', sl_mult=2.0, ma_filter=200, min_wait=2)),
    ('re_base_tight15', 'Baseline + re-entry tight 1.5×', BASELINE, dict(mode='ema_pb', sl_mult=1.5, ma_filter=None, min_wait=2)),
    ('re_tsr20_sma200', 'TSR 2.0R + re-entry SMA200', dict(tsr=2.0), dict(mode='ema_pb', sl_mult=2.0, ma_filter=200, min_wait=2)),
    ('re_tsr20_tight15_sma200', 'TSR 2.0R + re-entry tight 1.5× + SMA200', dict(tsr=2.0), dict(mode='ema_pb', sl_mult=1.5, ma_filter=200, min_wait=2)),
]
for sid, label, pover, recfg in reentry_combos:
    p = {**BASELINE, **pover}
    scenarios[sid] = {
        'label': label,
        'desc': f'Params: {pover}, Re-entry: {recfg}',
        'params': p, 'reentry': recfg, 'group': 'reentry'
    }

print(f"\n{len(scenarios)} scenarios to test across {len(STOCKS)} stocks")

# ── Run all ──────────────────────────────────────────────────────────
results = {}
for sid, scen in scenarios.items():
    all_trades = []
    per_stock = {}
    per_stock_equity = {}
    per_stock_trades = {}

    for name in STOCKS:
        trades = backtest(dfs[name], name, scen['params'], scen['reentry'])
        closed = [t for t in trades if t['exitDate']]
        closed.sort(key=lambda t: t['exitDate'])
        m = calc_metrics(closed)
        per_stock[name] = m
        per_stock_equity[name] = equity_curve(closed)
        per_stock_trades[name] = closed
        all_trades.extend(closed)

    all_trades.sort(key=lambda t: t['exitDate'])
    total_m = calc_metrics(all_trades)
    per_stock['ALL'] = total_m
    per_stock_equity['ALL'] = equity_curve(all_trades)

    results[sid] = {
        'label': scen['label'], 'desc': scen['desc'], 'group': scen['group'],
        'per_stock': per_stock, 'equity': per_stock_equity,
        'trades': all_trades, 'params': scen['params'],
    }

    ri = f" | re:{total_m['re_trades']}t ${total_m['re_pnl']}" if total_m['re_trades'] else ""
    print(f"  {scen['label']:40s} {total_m['trades']:3d}t  {total_m['wr']:5.1f}%  ${total_m['pnl']:8.0f}  DD${total_m['mdd']:6.0f}  PF={total_m['pf']:.2f}  RF={total_m['rf']:.2f}{ri}")

# ── Build output JSON ────────────────────────────────────────────────
output = {
    'scenarios': {},
    'stockList': STOCKS,
    'baseline_id': 'baseline',
    'groups': {
        'baseline': 'Baseline',
        'trail_start': 'Trail Start (R)',
        'stop_loss': 'Stop Loss (×ATR)',
        'trail_ema': 'Trail EMA Length',
        'trail_buffer': 'Trail ATR Buffer',
        'combo': 'Combined Improvements',
        'reentry': 'Re-entry Rules',
    }
}

for sid, r in results.items():
    output['scenarios'][sid] = {
        'id': sid,
        'label': r['label'],
        'desc': r['desc'],
        'group': r['group'],
        'params': r['params'],
        'per_stock': r['per_stock'],
        'equity': r['equity'],
        'trades': r['trades'],
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(output))
elapsed = time.time() - t0
print(f"\nWritten {OUT} ({OUT.stat().st_size//1024}KB) in {elapsed:.1f}s")
