#!/usr/bin/env python3
"""
Re-entry research: test market-strength filters + tighter stops on re-entries.
Outputs JSON for the dashboard Research tab.
"""
import pandas as pd, numpy as np, json
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/research_data.json")
RISK = 100.0
STOCKS = ['SPY','AAPL','AMD','GOOGL','META','NVDA','TSLA']

# ── helpers ──────────────────────────────────────────────────────────
def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def add_ind(df):
    d = df.copy()
    d['fSma']  = d['Close'].rolling(10).mean()
    d['sSma']  = d['Close'].rolling(50).mean()
    d['sma100'] = d['Close'].rolling(100).mean()
    d['sma200'] = d['Close'].rolling(200).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr']  = d['tr'].rolling(14).mean()
    d['tEma'] = d['Close'].ewm(span=20, adjust=False).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp']  = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn']  = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)
    return d

# ── backtest engine with optional re-entry ───────────────────────────
def backtest(df, name, reentry_cfg=None):
    """
    reentry_cfg = None  → baseline (no re-entry)
    reentry_cfg = {
        'mode':      'ema_pullback',          # trigger type
        'min_wait':  2,                        # min bars after exit before re-enter
        'sl_mult':   2.0,                      # SL multiplier for re-entries (can be tighter)
        'ma_filter': None | 100 | 200,         # require price above SMA(N) for longs / below for shorts
        'ma_slope':  False,                     # also require major MA slope in trend dir
    }
    """
    cfg = dict(mdist=3.0, mbar=2.0, sla=2.0, tb=1.0, tsr=2.5)
    df = add_ind(df)
    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; sSma = df['sSma'].values
    atr = df['atr'].values; tEma = df['tEma'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values
    xUp = df['xUp'].values; xDn = df['xDn'].values
    sma100 = df['sma100'].values; sma200 = df['sma200'].values
    dates = df['Date'].values

    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999
    # Re-entry state
    last_trail_dir = 0   # direction of last trail exit (1=long, -1=short)
    last_trail_bar = -999 # bar index of last trail exit
    reentry_used = False  # only one re-entry per trail exit

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
                    if cr >= cfg['tsr']:
                        et = tEma[i] - cfg['tb'] * a
                        if et > tsl: tsl = et
            else:
                if h[i] >= tsl: xp = tsl; hit_sl = True
                if not hit_sl:
                    cr = (ep - c[i]) / er if er > 0 else 0
                    if cr >= cfg['tsr']:
                        et = tEma[i] + cfg['tb'] * a
                        if et < tsl: tsl = et

            if hit_sl:
                pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
                is_trail = pnl_r > 0
                ed = pd.Timestamp(dates[trades[-1]['_entry_idx']]) if trades else pd.NaT
                xd = pd.Timestamp(dates[i])
                dur = int((xd - ed).days) if not pd.isna(ed) else 0
                t = trades[-1]
                t['exitDate'] = str(dates[i])[:10]
                t['exitPrice'] = round(xp, 2)
                t['pnlR'] = round(pnl_r, 2)
                t['pnlDollar'] = round(pnl_r * RISK, 2)
                t['exitReason'] = 'Trail' if is_trail else 'SL'
                t['durationDays'] = dur
                t['isReentry'] = t.get('isReentry', False)
                if is_trail:
                    last_trail_dir = pos
                    last_trail_bar = i
                    reentry_used = False
                pos = 0

        # ── entry logic ──
        if pos == 0:
            entered = False
            # Normal cross entry
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= cfg['mdist'] * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= cfg['mbar'] * a

            if dok and bok and xl:
                sl_val = c[i] - cfg['sla'] * a; rk = c[i] - sl_val
                qty = max(1, round(RISK / rk)) if rk > 0 else 1
                pos = 1; ep = c[i]; er = rk; tsl = sl_val
                trades.append(_make_trade(name, 'LONG', dates[i], c[i], sl_val, rk, qty, i, False))
                entered = True
                last_trail_dir = 0; reentry_used = False
            elif dok and bok and xs:
                sl_val = c[i] + cfg['sla'] * a; rk = sl_val - c[i]
                qty = max(1, round(RISK / rk)) if rk > 0 else 1
                pos = -1; ep = c[i]; er = rk; tsl = sl_val
                trades.append(_make_trade(name, 'SHORT', dates[i], c[i], sl_val, rk, qty, i, False))
                entered = True
                last_trail_dir = 0; reentry_used = False

            # Re-entry logic (only if enabled and no normal entry)
            if not entered and reentry_cfg and last_trail_dir != 0 and not reentry_used:
                bars_since = i - last_trail_bar
                min_wait = reentry_cfg.get('min_wait', 2)
                if bars_since < min_wait:
                    continue

                # Trend must still be intact (fast SMA on correct side)
                trend_ok = (last_trail_dir == 1 and fAbv[i] == 1) or \
                           (last_trail_dir == -1 and fAbv[i] == 0)
                if not trend_ok:
                    last_trail_dir = 0
                    continue

                # Bar filter still applies
                if not (bok and dok):
                    continue

                # ── MA filter: market strength ──
                ma_len = reentry_cfg.get('ma_filter', None)
                if ma_len:
                    ma_val = sma100[i] if ma_len == 100 else sma200[i]
                    if np.isnan(ma_val):
                        continue
                    if last_trail_dir == 1 and c[i] < ma_val:
                        continue  # long re-entry needs price above major MA
                    if last_trail_dir == -1 and c[i] > ma_val:
                        continue  # short re-entry needs price below major MA
                    # Optional: slope check
                    if reentry_cfg.get('ma_slope', False) and i >= 10:
                        ma_prev = sma100[i-10] if ma_len == 100 else sma200[i-10]
                        if not np.isnan(ma_prev):
                            if last_trail_dir == 1 and ma_val < ma_prev:
                                continue
                            if last_trail_dir == -1 and ma_val > ma_prev:
                                continue

                # ── Trigger: EMA pullback ──
                if reentry_cfg['mode'] == 'ema_pullback':
                    touched_ema = (last_trail_dir == 1 and l[i] <= tEma[i]) or \
                                  (last_trail_dir == -1 and h[i] >= tEma[i])
                    closed_right = (last_trail_dir == 1 and c[i] > tEma[i]) or \
                                   (last_trail_dir == -1 and c[i] < tEma[i])
                    if not (touched_ema and closed_right):
                        continue
                elif reentry_cfg['mode'] == 'sma10_pullback':
                    touched = (last_trail_dir == 1 and l[i] <= fSma[i]) or \
                              (last_trail_dir == -1 and h[i] >= fSma[i])
                    closed_right = (last_trail_dir == 1 and c[i] > fSma[i]) or \
                                   (last_trail_dir == -1 and c[i] < fSma[i])
                    if not (touched and closed_right):
                        continue
                elif reentry_cfg['mode'] == 'any_pullback_ema':
                    # Just require close back above/below EMA (no touch needed)
                    if last_trail_dir == 1 and c[i] <= tEma[i]: continue
                    if last_trail_dir == -1 and c[i] >= tEma[i]: continue
                else:
                    continue

                # ── Execute re-entry ──
                re_sl_mult = reentry_cfg.get('sl_mult', cfg['sla'])
                if last_trail_dir == 1:
                    sl_val = c[i] - re_sl_mult * a; rk = c[i] - sl_val
                    qty = max(1, round(RISK / rk)) if rk > 0 else 1
                    pos = 1; ep = c[i]; er = rk; tsl = sl_val
                    trades.append(_make_trade(name, 'LONG', dates[i], c[i], sl_val, rk, qty, i, True))
                else:
                    sl_val = c[i] + re_sl_mult * a; rk = sl_val - c[i]
                    qty = max(1, round(RISK / rk)) if rk > 0 else 1
                    pos = -1; ep = c[i]; er = rk; tsl = sl_val
                    trades.append(_make_trade(name, 'SHORT', dates[i], c[i], sl_val, rk, qty, i, True))
                reentry_used = True

    # Close open position at end
    if pos != 0 and trades:
        t = trades[-1]; last = df.iloc[-1]
        pnl_r = ((last['Close'] - ep) / er if pos == 1 else (ep - last['Close']) / er) if er > 0 else 0
        ed = pd.Timestamp(dates[t['_entry_idx']])
        t['exitDate'] = str(dates[len(df)-1])[:10]
        t['exitPrice'] = round(last['Close'], 2)
        t['pnlR'] = round(pnl_r, 2)
        t['pnlDollar'] = round(pnl_r * RISK, 2)
        t['exitReason'] = 'Open'
        t['durationDays'] = int((last['Date'] - ed).days)

    # Clean internal fields
    for t in trades:
        t.pop('_entry_idx', None)
    return trades


def _make_trade(name, dir_, date, price, sl, rk, qty, idx, is_re):
    return {
        'stock': name, 'dir': dir_,
        'entryDate': str(date)[:10],
        'entryPrice': round(price, 2),
        'sl': round(sl, 2), 'risk': round(rk, 2), 'qty': qty,
        'exitDate': '', 'exitPrice': 0,
        'pnlR': 0, 'pnlDollar': 0,
        'exitReason': '', 'durationDays': 0,
        'isReentry': is_re,
        '_entry_idx': idx,
    }


def metrics(trades):
    if not trades:
        return dict(trades=0, wr=0, pnl=0, mdd=0, pf=0, avgR=0, rf=0, mcl=0,
                    re_trades=0, re_wr=0, re_pnl=0)
    wins = [t for t in trades if t['pnlDollar'] > 0]
    losses = [t for t in trades if t['pnlDollar'] <= 0]
    pnl = sum(t['pnlDollar'] for t in trades)
    gross_w = sum(t['pnlDollar'] for t in wins)
    gross_l = abs(sum(t['pnlDollar'] for t in losses))
    pf = round(gross_w / gross_l, 2) if gross_l else 99
    wr = round(100 * len(wins) / len(trades), 1)
    avgr = round(sum(t['pnlR'] for t in trades) / len(trades), 2)

    # MDD
    eq = 0; peak = 0; mdd = 0
    for t in trades:
        eq += t['pnlDollar']
        if eq > peak: peak = eq
        dd = peak - eq
        if dd > mdd: mdd = dd

    rf = round(pnl / mdd, 2) if mdd > 0 else 99

    # MCL
    cl = 0; mcl = 0
    for t in trades:
        if t['pnlDollar'] <= 0: cl += 1
        else: cl = 0
        if cl > mcl: mcl = cl

    # Re-entry specific
    re_trades = [t for t in trades if t.get('isReentry')]
    re_wins = [t for t in re_trades if t['pnlDollar'] > 0]
    re_pnl = sum(t['pnlDollar'] for t in re_trades)
    re_wr = round(100 * len(re_wins) / len(re_trades), 1) if re_trades else 0

    return dict(trades=len(trades), wr=wr, pnl=round(pnl, 2), mdd=round(mdd, 2),
                pf=pf, avgR=avgr, rf=rf, mcl=mcl,
                re_trades=len(re_trades), re_wr=re_wr, re_pnl=round(re_pnl, 2))


# ── define scenarios ─────────────────────────────────────────────────
SCENARIOS = {
    'baseline': {
        'label': 'Current (no re-entry)',
        'desc': 'Baseline v4 strategy. One SMA cross = one trade.',
        'cfg': None,
    },
    # ── Market strength filters ──
    'reentry_sma100': {
        'label': 'Re-entry + SMA100 filter',
        'desc': 'EMA pullback re-entry, only when price above SMA100 (longs) or below (shorts). SL = 2.0× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 2.0, 'ma_filter': 100},
    },
    'reentry_sma200': {
        'label': 'Re-entry + SMA200 filter',
        'desc': 'EMA pullback re-entry, only when price above SMA200 (longs) or below (shorts). SL = 2.0× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 2.0, 'ma_filter': 200},
    },
    'reentry_sma100_slope': {
        'label': 'Re-entry + SMA100 filter + slope',
        'desc': 'EMA pullback re-entry, price above SMA100 AND SMA100 sloping up (longs). SL = 2.0× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 2.0, 'ma_filter': 100, 'ma_slope': True},
    },
    'reentry_sma200_slope': {
        'label': 'Re-entry + SMA200 filter + slope',
        'desc': 'EMA pullback re-entry, price above SMA200 AND SMA200 sloping up (longs). SL = 2.0× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 2.0, 'ma_filter': 200, 'ma_slope': True},
    },
    # ── Tighter stops ──
    'reentry_tight15': {
        'label': 'Re-entry + tight SL 1.5×',
        'desc': 'EMA pullback re-entry, no MA filter, SL = 1.5× ATR (tighter than normal 2.0×).',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 1.5, 'ma_filter': None},
    },
    'reentry_tight10': {
        'label': 'Re-entry + tight SL 1.0×',
        'desc': 'EMA pullback re-entry, no MA filter, SL = 1.0× ATR (very tight).',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 1.0, 'ma_filter': None},
    },
    # ── Combos: market strength + tighter stops ──
    'reentry_sma100_tight15': {
        'label': 'Re-entry + SMA100 + tight 1.5×',
        'desc': 'EMA pullback + SMA100 filter + tighter SL 1.5× ATR. Best of both worlds?',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 1.5, 'ma_filter': 100},
    },
    'reentry_sma200_tight15': {
        'label': 'Re-entry + SMA200 + tight 1.5×',
        'desc': 'EMA pullback + SMA200 filter + tighter SL 1.5× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 1.5, 'ma_filter': 200},
    },
    'reentry_sma100_tight10': {
        'label': 'Re-entry + SMA100 + tight 1.0×',
        'desc': 'EMA pullback + SMA100 filter + very tight SL 1.0× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 1.0, 'ma_filter': 100},
    },
    'reentry_sma200_tight10': {
        'label': 'Re-entry + SMA200 + tight 1.0×',
        'desc': 'EMA pullback + SMA200 filter + very tight SL 1.0× ATR.',
        'cfg': {'mode': 'ema_pullback', 'min_wait': 2, 'sl_mult': 1.0, 'ma_filter': 200},
    },
    # ── SMA10 pullback variants ──
    'reentry_sma10_pb_sma100': {
        'label': 'SMA10 pullback + SMA100 filter',
        'desc': 'Pullback to SMA10 re-entry, SMA100 market filter, SL = 2.0×.',
        'cfg': {'mode': 'sma10_pullback', 'min_wait': 2, 'sl_mult': 2.0, 'ma_filter': 100},
    },
    'reentry_sma10_pb_tight15': {
        'label': 'SMA10 pullback + tight 1.5×',
        'desc': 'Pullback to SMA10 re-entry, no MA filter, SL = 1.5×.',
        'cfg': {'mode': 'sma10_pullback', 'min_wait': 2, 'sl_mult': 1.5, 'ma_filter': None},
    },
}

# ── run ──────────────────────────────────────────────────────────────
print("Loading data...")
dfs = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    if name in STOCKS:
        dfs[name] = load(f)
        print(f"  {name}: {len(dfs[name])} bars")

results = {}

for sid, scen in SCENARIOS.items():
    print(f"\n{'='*60}")
    print(f"  {scen['label']}")
    print(f"{'='*60}")

    all_trades = []
    per_stock = {}

    for name in STOCKS:
        trades = backtest(dfs[name], name, scen['cfg'])
        m = metrics(trades)
        per_stock[name] = m
        all_trades.extend(trades)
        re_info = f" | re-entries: {m['re_trades']}t {m['re_wr']}% ${m['re_pnl']}" if m['re_trades'] else ""
        print(f"  {name:>5}: {m['trades']:3d}t  {m['wr']:5.1f}%  ${m['pnl']:8.0f}  DD${m['mdd']:6.0f}  PF={m['pf']:.2f}  RF={m['rf']:.2f}{re_info}")

    # Sort by date for portfolio metrics
    all_trades.sort(key=lambda t: t['entryDate'])
    total_m = metrics(all_trades)
    per_stock['ALL'] = total_m
    re_info = f" | re-entries: {total_m['re_trades']}t {total_m['re_wr']}% ${total_m['re_pnl']}" if total_m['re_trades'] else ""
    print(f"  {'TOTAL':>5}: {total_m['trades']:3d}t  {total_m['wr']:5.1f}%  ${total_m['pnl']:8.0f}  DD${total_m['mdd']:6.0f}  PF={total_m['pf']:.2f}  RF={total_m['rf']:.2f}{re_info}")

    results[sid] = {
        'label': scen['label'],
        'desc': scen['desc'],
        'per_stock': per_stock,
        'trades': all_trades,
    }

# ── save JSON ────────────────────────────────────────────────────────
output = {
    'scenarios': {},
    'stockList': STOCKS,
    'baseline_id': 'baseline',
}

for sid, r in results.items():
    output['scenarios'][sid] = {
        'id': sid,
        'label': r['label'],
        'desc': r['desc'],
        'per_stock': r['per_stock'],
        'trades': r['trades'],
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(output))
print(f"\nWritten {OUT} ({OUT.stat().st_size//1024}KB)")
print("Done!")
