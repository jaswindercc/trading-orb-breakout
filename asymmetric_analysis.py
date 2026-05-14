#!/usr/bin/env python3
"""
Asymmetric strategy: aggressive longs + selective/quick shorts.
Tests: strict short filters, tighter short exits, fixed TP on shorts.
"""
import pandas as pd, numpy as np
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("/workspaces/jas/data")
RISK = 100.0

def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def add_indicators(df):
    d = df.copy()
    d['fSma']  = d['Close'].rolling(10).mean()
    d['sSma']  = d['Close'].rolling(50).mean()
    d['sma200']= d['Close'].rolling(200).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr']  = d['tr'].rolling(14).mean()
    d['tEma'] = d['Close'].ewm(span=20, adjust=False).mean()
    d['tEma10'] = d['Close'].ewm(span=10, adjust=False).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp']  = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn']  = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)
    d['atr_pct'] = d['atr'] / d['Close'] * 100
    d['atr_ratio'] = d['atr'] / d['atr'].rolling(50).mean()
    d['ret20d'] = d['Close'].pct_change(20)
    d['sma200_slope'] = d['sma200'].pct_change(20)  # 20-day slope of SMA200
    return d

# ─────────────────────────────────────────────────────────────────────
# ASYMMETRIC BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────
def backtest_asym(df, name, cfg):
    """
    cfg = dict with:
      long_sla, short_sla: SL multiplier per side
      long_tsr, short_tsr: trail start R per side
      long_te, short_te:   trail EMA length per side
      long_tb, short_tb:   trail buffer per side
      short_tp_r:          fixed TP in R for shorts (None = no fixed TP, use trail)
      short_filter:        'none','sma200','sma200_slope','momentum','strict','very_strict'
      mbar, mdist:         entry filters (same for both)
    """
    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; sSma = df['sSma'].values; atr = df['atr'].values
    bRng = df['bRng'].values; fAbv = df['fAbv'].values
    xUp = df['xUp'].values; xDn = df['xDn'].values
    sma200 = df['sma200'].values
    sma200_slope = df['sma200_slope'].values
    ret20d = df['ret20d'].values
    atr_ratio = df['atr_ratio'].values
    dates = df['Date'].values

    # Precompute both EMAs
    def ema(arr, span):
        alpha = 2.0 / (span + 1)
        e = np.empty_like(arr)
        e[0] = arr[0]
        for i in range(1, len(arr)):
            e[i] = alpha * arr[i] + (1 - alpha) * e[i-1]
        return e

    tEma_long = ema(c, cfg.get('long_te', 20))
    tEma_short = ema(c, cfg.get('short_te', 20))

    mbar = cfg.get('mbar', 2.0); mdist = cfg.get('mdist', 3.0)
    short_filter = cfg.get('short_filter', 'none')
    short_tp_r = cfg.get('short_tp_r', None)

    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999

    for i in range(1, len(df)):
        a = atr[i]
        if np.isnan(a) or a <= 0: continue
        if xUp[i]:  lcd = 1; bsc = 0
        elif xDn[i]: lcd = -1; bsc = 0
        else: bsc += 1

        # ── Manage position ──
        if pos != 0:
            hit = False; xp = 0.0; reason = ''
            if pos == 1:  # LONG
                tsr = cfg.get('long_tsr', 2.5)
                tb = cfg.get('long_tb', 1.0)
                if l[i] <= tsl: xp = tsl; hit = True; reason = 'SL'
                if not hit:
                    cr = (c[i] - ep) / er if er > 0 else 0
                    if cr >= tsr:
                        et = tEma_long[i] - tb * a
                        if et > tsl: tsl = et
                    # Check if trail stop hit at close
                    if c[i] <= tsl: xp = tsl; hit = True; reason = 'Trail'
            else:  # SHORT
                tsr = cfg.get('short_tsr', 2.5)
                tb = cfg.get('short_tb', 1.0)
                if h[i] >= tsl: xp = tsl; hit = True; reason = 'SL'
                if not hit:
                    cr = (ep - c[i]) / er if er > 0 else 0
                    # Fixed TP for shorts
                    if short_tp_r and cr >= short_tp_r:
                        xp = c[i]; hit = True; reason = 'TP'
                    elif not short_tp_r or cr < short_tp_r:
                        if cr >= tsr:
                            et = tEma_short[i] + tb * a
                            if et < tsl: tsl = et
                        if c[i] >= tsl: xp = tsl; hit = True; reason = 'Trail'

            if hit:
                pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
                ed = pd.Timestamp(dates[trades[-1]['_ei']])
                xd = pd.Timestamp(dates[i])
                trades[-1].update({
                    'exitDate': str(dates[i])[:10], 'exitPrice': round(xp, 2),
                    'pnlR': round(pnl_r, 2), 'pnlDollar': round(pnl_r * RISK, 2),
                    'exitReason': reason, 'durationDays': int((xd - ed).days),
                })
                pos = 0

        # ── Entry ──
        if pos == 0:
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a

            entered = False
            if dok and bok and xl:
                sla = cfg.get('long_sla', 1.0)
                sl_v = c[i] - sla * a; rk = c[i] - sl_v
                qty = max(1, round(RISK / rk)) if rk > 0 else 1
                pos = 1; ep = c[i]; er = rk; tsl = sl_v; entered = True
                trades.append({'stock': name, 'dir': 'LONG', 'entryDate': str(dates[i])[:10],
                    'entryPrice': round(ep, 2), '_ei': i, 'exitDate': '', 'pnlR': 0, 'pnlDollar': 0})

            elif dok and bok and xs:
                # Apply short filter
                short_ok = True
                if short_filter == 'sma200':
                    # Only short when price is below SMA200
                    short_ok = not np.isnan(sma200[i]) and c[i] < sma200[i]
                elif short_filter == 'sma200_slope':
                    # Only short when SMA200 is declining
                    short_ok = not np.isnan(sma200_slope[i]) and sma200_slope[i] < 0
                elif short_filter == 'momentum':
                    # Only short when 20d momentum is negative
                    short_ok = not np.isnan(ret20d[i]) and ret20d[i] < 0
                elif short_filter == 'strict':
                    # Below SMA200 AND negative momentum
                    below200 = not np.isnan(sma200[i]) and c[i] < sma200[i]
                    neg_mom = not np.isnan(ret20d[i]) and ret20d[i] < 0
                    short_ok = below200 and neg_mom
                elif short_filter == 'very_strict':
                    # Below SMA200 AND negative momentum AND ATR expanding
                    below200 = not np.isnan(sma200[i]) and c[i] < sma200[i]
                    neg_mom = not np.isnan(ret20d[i]) and ret20d[i] < -0.05
                    atr_exp = not np.isnan(atr_ratio[i]) and atr_ratio[i] > 1.0
                    short_ok = below200 and neg_mom and atr_exp
                elif short_filter == 'sma200_momentum':
                    # Below SMA200 OR strong negative momentum
                    below200 = not np.isnan(sma200[i]) and c[i] < sma200[i]
                    neg_mom = not np.isnan(ret20d[i]) and ret20d[i] < -0.05
                    short_ok = below200 or neg_mom

                if short_ok:
                    sla = cfg.get('short_sla', 1.0)
                    sl_v = c[i] + sla * a; rk = sl_v - c[i]
                    qty = max(1, round(RISK / rk)) if rk > 0 else 1
                    pos = -1; ep = c[i]; er = rk; tsl = sl_v
                    trades.append({'stock': name, 'dir': 'SHORT', 'entryDate': str(dates[i])[:10],
                        'entryPrice': round(ep, 2), '_ei': i, 'exitDate': '', 'pnlR': 0, 'pnlDollar': 0})

    # Close open
    if pos != 0 and trades:
        xp = c[-1]
        pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
        ed = pd.Timestamp(dates[trades[-1]['_ei']])
        trades[-1].update({
            'exitDate': str(dates[-1])[:10], 'exitPrice': round(xp, 2),
            'pnlR': round(pnl_r, 2), 'pnlDollar': round(pnl_r * RISK, 2),
            'exitReason': 'Open', 'durationDays': int((pd.Timestamp(dates[-1]) - ed).days),
        })

    closed = [t for t in trades if t.get('exitDate')]
    for t in closed: t.pop('_ei', None)
    return closed

def metrics(trades):
    if not trades: return dict(n=0, pnl=0, wr=0, pf=0, mdd=0, rf=0, ppt=0,
                                long_n=0, long_pnl=0, long_wr=0,
                                short_n=0, short_pnl=0, short_wr=0, mcl=0)
    pnls = [t['pnlDollar'] for t in trades]
    n = len(trades); pnl = sum(pnls)
    wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p <= 0]
    gw = sum(wins); gl = abs(sum(losses))
    wr = round(100 * len(wins) / n, 1)
    pf = round(gw / gl, 2) if gl else 99
    eq = 0; peak = 0; mdd = 0
    for p in pnls: eq += p; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    rf = round(pnl / mdd, 2) if mdd > 0 else 99
    cl = 0; mcl = 0
    for p in pnls:
        if p <= 0: cl += 1
        else: cl = 0
        mcl = max(mcl, cl)

    longs = [t for t in trades if t['dir'] == 'LONG']
    shorts = [t for t in trades if t['dir'] == 'SHORT']
    l_wins = len([t for t in longs if t['pnlDollar'] > 0])
    s_wins = len([t for t in shorts if t['pnlDollar'] > 0])

    return dict(n=n, pnl=round(pnl), wr=wr, pf=pf, mdd=round(mdd), rf=rf, ppt=round(pnl/n, 2),
                long_n=len(longs), long_pnl=round(sum(t['pnlDollar'] for t in longs)),
                long_wr=round(100*l_wins/len(longs),1) if longs else 0,
                short_n=len(shorts), short_pnl=round(sum(t['pnlDollar'] for t in shorts)),
                short_wr=round(100*s_wins/len(shorts),1) if shorts else 0, mcl=mcl)

# ─────────────────────────────────────────────────────────────────────
# STRATEGIES TO TEST
# ─────────────────────────────────────────────────────────────────────
STRATEGIES = {
    # ── Baselines ──
    'A. Baseline (current)': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=None),

    'B. Longs only': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='very_strict', short_tp_r=None),  # so strict almost no shorts

    # ── Short ENTRY filters (keep same exit) ──
    'C1. Short: below SMA200': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='sma200', short_tp_r=None),

    'C2. Short: neg momentum': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='momentum', short_tp_r=None),

    'C3. Short: SMA200 declining': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='sma200_slope', short_tp_r=None),

    'C4. Short: strict (200+mom)': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='strict', short_tp_r=None),

    'C5. Short: sma200 OR neg mom': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='sma200_momentum', short_tp_r=None),

    # ── Short EXIT: faster trail ──
    'D1. Short: early trail 1.5R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=1.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=None),

    'D2. Short: tighter EMA10': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=10,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=None),

    'D3. Short: early trail + EMA10': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=1.5,
        long_te=20, short_te=10,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=None),

    # ── Short EXIT: fixed TP ──
    'E1. Short: TP at 2R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=2.0),

    'E2. Short: TP at 3R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=3.0),

    'E3. Short: TP at 4R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='none', short_tp_r=4.0),

    # ── COMBOS: strict entry + quick exit on shorts ──
    'F1. SMA200 + TP 3R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='sma200', short_tp_r=3.0),

    'F2. SMA200 + early trail': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=1.5,
        long_te=20, short_te=10,
        long_tb=1.0, short_tb=0.5,
        short_filter='sma200', short_tp_r=None),

    'F3. Neg mom + TP 3R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='momentum', short_tp_r=3.0),

    'F4. Neg mom + early trail EMA10': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=1.5,
        long_te=20, short_te=10,
        long_tb=1.0, short_tb=0.5,
        short_filter='momentum', short_tp_r=None),

    'F5. SMA200+mom + TP 3R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='strict', short_tp_r=3.0),

    'F6. SMA200+mom + early EMA10': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=1.5,
        long_te=20, short_te=10,
        long_tb=1.0, short_tb=0.5,
        short_filter='strict', short_tp_r=None),

    'F7. SMA200 OR negmom + TP3R': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=2.5,
        long_te=20, short_te=20,
        long_tb=1.0, short_tb=1.0,
        short_filter='sma200_momentum', short_tp_r=3.0),

    'F8. SMA200 OR negmom + early trail': dict(
        long_sla=1.0, short_sla=1.0,
        long_tsr=2.5, short_tsr=1.5,
        long_te=20, short_te=10,
        long_tb=1.0, short_tb=0.5,
        short_filter='sma200_momentum', short_tp_r=None),
}

# ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 120)
    print("ASYMMETRIC STRATEGY: Aggressive Longs + Selective/Quick Shorts")
    print("=" * 120)

    dfs = {}
    for f in sorted(DATA_DIR.glob("*.csv")):
        name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
        dfs[name] = add_indicators(load(f))
    stocks = sorted(dfs.keys())
    print(f"{len(dfs)} stocks: {', '.join(stocks)}\n")

    # ── RUN ALL STRATEGIES ──
    all_results = {}
    for sname, cfg in STRATEGIES.items():
        all_trades = []
        per_stock = {}
        for name in stocks:
            trades = backtest_asym(dfs[name], name, cfg)
            all_trades.extend(trades)
            per_stock[name] = trades
        all_trades.sort(key=lambda t: t.get('exitDate', ''))
        m = metrics(all_trades)
        all_results[sname] = {'trades': all_trades, 'per_stock': per_stock, 'metrics': m}

    # ── PART 1: OVERVIEW TABLE ──
    print("=" * 120)
    print("PART 1: ALL STRATEGIES COMPARED")
    print("=" * 120)

    h = f"  {'Strategy':<38s} {'Tot':>4s} {'P&L':>8s} {'WR%':>5s} {'PF':>5s} {'MDD':>7s} {'RF':>5s} {'$/T':>6s} {'MCL':>3s} │ {'#L':>3s} {'L$':>7s} {'LWR':>5s} │ {'#S':>3s} {'S$':>7s} {'SWR':>5s}"
    print(f"\n{h}")
    print("  " + "─" * 116)

    for sname in STRATEGIES:
        m = all_results[sname]['metrics']
        print(f"  {sname:<38s} {m['n']:>4d} ${m['pnl']:>7d} {m['wr']:>4.1f}% {m['pf']:>4.2f} ${m['mdd']:>6d} {m['rf']:>4.2f} ${m['ppt']:>5.0f} {m['mcl']:>3d} │ {m['long_n']:>3d} ${m['long_pnl']:>6d} {m['long_wr']:>4.1f}% │ {m['short_n']:>3d} ${m['short_pnl']:>6d} {m['short_wr']:>4.1f}%")

    # ── PART 2: PER-STOCK for top strategies ──
    print("\n" + "=" * 120)
    print("PART 2: PER-STOCK P&L (top strategies)")
    print("=" * 120)

    tops = ['A. Baseline (current)', 'B. Longs only',
            'C5. Short: sma200 OR neg mom',
            'F7. SMA200 OR negmom + TP3R',
            'F8. SMA200 OR negmom + early trail',
            'F1. SMA200 + TP 3R',
            'F2. SMA200 + early trail']

    h2 = f"\n  {'Stock':<7s}"
    for sn in tops:
        short_name = sn.split('. ')[1][:16]
        h2 += f" {short_name:>18s}"
    print(h2)
    print("  " + "─" * (5 + 19 * len(tops)))

    for name in stocks:
        row = f"  {name:<5s}"
        for sn in tops:
            trades = all_results[sn]['per_stock'][name]
            pnl = sum(t['pnlDollar'] for t in trades)
            n = len(trades)
            shorts_n = len([t for t in trades if t['dir'] == 'SHORT'])
            row += f"  ${pnl:>5.0f}({n:>2d}t/{shorts_n:>1d}s)"
            if sn == tops[-1]: pass
        print(row)

    # Totals
    row = f"  {'TOTAL':<5s}"
    for sn in tops:
        m = all_results[sn]['metrics']
        row += f"  ${m['pnl']:>5d}({m['n']:>2d}t/{m['short_n']:>1d}s)"
    print("  " + "─" * (5 + 19 * len(tops)))
    print(row)

    # ── PART 3: YEARLY CONSISTENCY ──
    print("\n" + "=" * 120)
    print("PART 3: YEARLY P&L CONSISTENCY")
    print("=" * 120)

    check = ['A. Baseline (current)', 'B. Longs only',
             'F7. SMA200 OR negmom + TP3R', 'F8. SMA200 OR negmom + early trail']

    for sn in check:
        trades = all_results[sn]['trades']
        by_year = defaultdict(list)
        for t in trades: by_year[t['exitDate'][:4]].append(t['pnlDollar'])
        years = sorted(by_year)
        ystr = "  ".join(f"{yr}:${sum(by_year[yr]):>6.0f}({len(by_year[yr]):>2d}t)" for yr in years)
        print(f"\n  {sn}")
        print(f"    {ystr}")

    # ── PART 4: SHORT TRADE DETAIL ON BEST COMBO ──
    print("\n" + "=" * 120)
    print("PART 4: SHORT TRADES IN BEST COMBOS (what shorts survive the filter?)")
    print("=" * 120)

    for sn in ['F7. SMA200 OR negmom + TP3R', 'F8. SMA200 OR negmom + early trail']:
        trades = all_results[sn]['trades']
        shorts = [t for t in trades if t['dir'] == 'SHORT']
        print(f"\n  ── {sn} ({len(shorts)} shorts) ──")
        for t in shorts:
            marker = "✓" if t['pnlDollar'] > 0 else "✗"
            print(f"    {marker} {t['stock']:>5s} {t['entryDate']} → {t['exitDate']}  {t['pnlR']:>+5.2f}R ${t['pnlDollar']:>+6.0f}  {t['exitReason']:<5s} {t['durationDays']:>3d}d")

        s_pnl = sum(t['pnlDollar'] for t in shorts)
        s_wins = len([t for t in shorts if t['pnlDollar'] > 0])
        s_wr = round(100 * s_wins / len(shorts), 1) if shorts else 0
        print(f"    ──── Shorts total: ${s_pnl:.0f}, {len(shorts)} trades, {s_wr}% WR")

    # ── PART 5: RECOMMENDATION ──
    print("\n" + "=" * 120)
    print("PART 5: RECOMMENDATION")
    print("=" * 120)

    # Find best by RF among combos (F-series) and overall
    f_strats = {k: v for k, v in all_results.items() if k.startswith('F')}
    if f_strats:
        best_combo = max(f_strats.items(), key=lambda x: x[1]['metrics']['rf'])
        m = best_combo[1]['metrics']
        print(f"\n  BEST COMBO (by Recovery Factor): {best_combo[0]}")
        print(f"    {m['n']} trades, ${m['pnl']} P&L, {m['wr']}% WR, PF {m['pf']}, MaxDD ${m['mdd']}, RF {m['rf']}")
        print(f"    Longs: {m['long_n']}t ${m['long_pnl']} ({m['long_wr']}% WR)")
        print(f"    Shorts: {m['short_n']}t ${m['short_pnl']} ({m['short_wr']}% WR)")

    best_pnl = max(f_strats.items(), key=lambda x: x[1]['metrics']['pnl'])
    m = best_pnl[1]['metrics']
    print(f"\n  BEST COMBO (by Total P&L): {best_pnl[0]}")
    print(f"    {m['n']} trades, ${m['pnl']} P&L, {m['wr']}% WR, PF {m['pf']}, MaxDD ${m['mdd']}, RF {m['rf']}")
    print(f"    Longs: {m['long_n']}t ${m['long_pnl']} ({m['long_wr']}% WR)")
    print(f"    Shorts: {m['short_n']}t ${m['short_pnl']} ({m['short_wr']}% WR)")

    # Compare baseline → best
    base_m = all_results['A. Baseline (current)']['metrics']
    print(f"\n  IMPROVEMENT vs BASELINE:")
    print(f"    P&L:      ${base_m['pnl']} → ${m['pnl']} ({'+' if m['pnl']>base_m['pnl'] else ''}{m['pnl']-base_m['pnl']})")
    print(f"    Trades:   {base_m['n']} → {m['n']}")
    print(f"    WR:       {base_m['wr']}% → {m['wr']}%")
    print(f"    PF:       {base_m['pf']} → {m['pf']}")
    print(f"    MaxDD:    ${base_m['mdd']} → ${m['mdd']}")
    print(f"    RF:       {base_m['rf']} → {m['rf']}")
    print(f"    MCL:      {base_m['mcl']} → {m['mcl']}")
    print(f"    $/Trade:  ${base_m['ppt']} → ${m['ppt']}")
    print()
