#!/usr/bin/env python3
"""
Adaptive ATR strategy analysis.
Tests: dynamic SL based on ATR regime, ATR expansion filters, etc.
Goal: one set of rules that works across ALL stocks.
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
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr']  = d['tr'].rolling(14).mean()
    d['tEma'] = d['Close'].ewm(span=20, adjust=False).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp']  = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn']  = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)

    # ATR analysis indicators
    d['atr_pct'] = d['atr'] / d['Close'] * 100          # ATR as % of price
    d['atr_ma50'] = d['atr'].rolling(50).mean()          # 50-bar MA of ATR
    d['atr_ratio'] = d['atr'] / d['atr_ma50']            # ATR expansion ratio (>1 = expanding)
    d['atr_pct_ma50'] = d['atr_pct'].rolling(50).mean()  # 50-bar MA of ATR%

    # ATR percentile (where is current ATR in last 100 bars)
    d['atr_pctile'] = d['atr'].rolling(100).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)

    return d

# ─────────────────────────────────────────────────────────────────────
# ADAPTIVE BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────
def backtest_adaptive(df, name, strategy_fn):
    """
    strategy_fn(df, i, base_sla=1.0) -> (sla, should_trade)
    Returns: list of trade dicts
    """
    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; atr = df['atr'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values; xUp = df['xUp'].values; xDn = df['xDn'].values
    tEma = df['tEma'].values

    tsr = 2.5; tb = 1.0; mbar = 2.0; mdist = 3.0

    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999; trade_sla = 1.0

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
                trades.append({
                    'pnlDollar': round(pnl_r * RISK, 2),
                    'pnlR': round(pnl_r, 2),
                    'sla_used': trade_sla,
                    'dir': 'LONG' if pos == 1 else 'SHORT',
                    'exitDate': str(df['Date'].iloc[i])[:10],
                })
                pos = 0

        if pos == 0:
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a

            if dok and bok and (xl or xs):
                # Ask strategy function for SL and whether to trade
                sla, should_trade = strategy_fn(df, i)
                if not should_trade:
                    continue

                trade_sla = sla
                if xl:
                    sl_v = c[i] - sla * a; rk = c[i] - sl_v
                    pos = 1; ep = c[i]; er = rk; tsl = sl_v
                elif xs:
                    sl_v = c[i] + sla * a; rk = sl_v - c[i]
                    pos = -1; ep = c[i]; er = rk; tsl = sl_v

    if pos != 0:
        xp = c[-1]
        pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
        trades.append({
            'pnlDollar': round(pnl_r * RISK, 2), 'pnlR': round(pnl_r, 2),
            'sla_used': trade_sla, 'dir': 'LONG' if pos == 1 else 'SHORT',
            'exitDate': str(df['Date'].iloc[-1])[:10],
        })

    return trades

def metrics(trades):
    if not trades: return (0, 0, 0, 0, 0, 0, 0)
    n = len(trades)
    pnls = [t['pnlDollar'] for t in trades]
    pnl = sum(pnls)
    wins = len([p for p in pnls if p > 0])
    gw = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p <= 0))
    wr = round(100 * wins / n, 1)
    pf = round(gw / gl, 2) if gl else 99
    eq = 0; peak = 0; mdd = 0
    for p in pnls:
        eq += p; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    rf = round(pnl / mdd, 2) if mdd > 0 else 99
    return (n, pnl, wr, pf, mdd, rf, round(pnl/n, 2))

# ─────────────────────────────────────────────────────────────────────
# STRATEGY VARIANTS
# ─────────────────────────────────────────────────────────────────────

def make_baseline(df, i):
    """Current strategy: SL = 1.0× always."""
    return (1.0, True)

def make_atr_expanding_only(df, i):
    """Only trade when ATR > its 50-bar MA (expanding volatility)."""
    ratio = df['atr_ratio'].iloc[i]
    if np.isnan(ratio): return (1.0, True)
    return (1.0, ratio > 1.0)

def make_atr_expanding_1_1(df, i):
    """Only trade when ATR > 1.1× its 50-bar MA."""
    ratio = df['atr_ratio'].iloc[i]
    if np.isnan(ratio): return (1.0, True)
    return (1.0, ratio > 1.1)

def make_dynamic_sl_atr_pct(df, i):
    """Dynamic SL based on ATR%.
    Low ATR% (<2%) = wider SL (1.5×) to avoid noise stops.
    High ATR% (>3%) = tight SL (1.0×) = bigger position on trending stocks.
    Medium = 1.25×."""
    atr_pct = df['atr_pct'].iloc[i]
    if np.isnan(atr_pct): return (1.0, True)
    if atr_pct < 2.0:
        return (1.5, True)
    elif atr_pct < 3.0:
        return (1.25, True)
    else:
        return (1.0, True)

def make_dynamic_sl_v2(df, i):
    """More granular: scale SL inversely with ATR%.
    ATR% < 1.5 → SL 2.0 (very calm, need wide stop)
    ATR% 1.5-2.5 → SL 1.5
    ATR% 2.5-3.5 → SL 1.25
    ATR% > 3.5 → SL 1.0 (volatile, tight stop works)"""
    atr_pct = df['atr_pct'].iloc[i]
    if np.isnan(atr_pct): return (1.0, True)
    if atr_pct < 1.5:
        return (2.0, True)
    elif atr_pct < 2.5:
        return (1.5, True)
    elif atr_pct < 3.5:
        return (1.25, True)
    else:
        return (1.0, True)

def make_dynamic_sl_atr_ratio(df, i):
    """Dynamic SL based on ATR expansion ratio.
    Expanding ATR (ratio > 1.0) = tight SL (1.0×) — trend is moving.
    Contracting ATR (ratio < 0.8) = wider SL (1.5×) or skip.
    Normal = 1.25×."""
    ratio = df['atr_ratio'].iloc[i]
    if np.isnan(ratio): return (1.0, True)
    if ratio > 1.1:
        return (1.0, True)   # Expanding — tight stop, big position
    elif ratio > 0.9:
        return (1.25, True)  # Normal
    else:
        return (1.5, True)   # Contracting — wider stop, smaller position

def make_skip_contracting_atr(df, i):
    """Skip when ATR is contracting (ratio < 0.85). Trade everything else with SL 1.0."""
    ratio = df['atr_ratio'].iloc[i]
    if np.isnan(ratio): return (1.0, True)
    return (1.0, ratio >= 0.85)

def make_dynamic_sl_percentile(df, i):
    """SL based on ATR percentile in last 100 bars.
    Top quartile (>75th) = tight 1.0× (trending)
    Middle (25-75th) = 1.25×
    Bottom quartile (<25th) = 1.5× or skip"""
    pctile = df['atr_pctile'].iloc[i]
    if np.isnan(pctile): return (1.0, True)
    if pctile > 0.75:
        return (1.0, True)
    elif pctile > 0.25:
        return (1.25, True)
    else:
        return (1.5, True)

def make_skip_low_pctile(df, i):
    """Skip when ATR is in bottom 25th percentile. SL 1.0 otherwise."""
    pctile = df['atr_pctile'].iloc[i]
    if np.isnan(pctile): return (1.0, True)
    return (1.0, pctile > 0.25)

def make_combined_expand_dynamic(df, i):
    """Combined: skip contracting + dynamic SL.
    Contracting (ratio < 0.85) = skip.
    Expanding (ratio > 1.1) = SL 1.0.
    Normal = SL 1.25."""
    ratio = df['atr_ratio'].iloc[i]
    if np.isnan(ratio): return (1.0, True)
    if ratio < 0.85:
        return (1.0, False)
    elif ratio > 1.1:
        return (1.0, True)
    else:
        return (1.25, True)

def make_atr_pct_dynamic_skip_low(df, i):
    """Skip when ATR% < 1.5 (too calm). Dynamic SL for rest."""
    atr_pct = df['atr_pct'].iloc[i]
    if np.isnan(atr_pct): return (1.0, True)
    if atr_pct < 1.5:
        return (1.0, False)  # Skip — too calm, will whipsaw
    elif atr_pct < 2.5:
        return (1.5, True)   # Moderate — wider stop
    elif atr_pct < 3.5:
        return (1.25, True)  # Good vol
    else:
        return (1.0, True)   # High vol — tight stop

def make_only_longs(df, i):
    """Only longs, SL 1.0."""
    return (1.0, True)  # Filter applied differently

def make_longs_dynamic_sl(df, i):
    """Only longs + dynamic SL based on ATR%."""
    atr_pct = df['atr_pct'].iloc[i]
    if np.isnan(atr_pct): return (1.0, True)
    if atr_pct < 2.0:
        return (1.5, True)
    elif atr_pct < 3.0:
        return (1.25, True)
    else:
        return (1.0, True)

def make_expanding_longs_only(df, i):
    """Only trade when ATR expanding + only longs."""
    ratio = df['atr_ratio'].iloc[i]
    if np.isnan(ratio): return (1.0, True)
    return (1.0, ratio > 1.0)

# Special backtest for long-only variants
def backtest_longs_only(df, name, strategy_fn):
    """Same as adaptive but only takes long signals."""
    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; atr = df['atr'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values; xUp = df['xUp'].values; xDn = df['xDn'].values
    tEma = df['tEma'].values
    tsr = 2.5; tb = 1.0; mbar = 2.0; mdist = 3.0
    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999; trade_sla = 1.0

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
            if hit:
                pnl_r = ((xp - ep) / er) if er > 0 else 0
                trades.append({'pnlDollar': round(pnl_r * RISK, 2), 'pnlR': round(pnl_r, 2),
                               'sla_used': trade_sla, 'dir': 'LONG',
                               'exitDate': str(df['Date'].iloc[i])[:10]})
                pos = 0

        if pos == 0:
            xl = (lcd == 1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a
            if dok and bok and xl:
                sla, should_trade = strategy_fn(df, i)
                if not should_trade: continue
                trade_sla = sla
                sl_v = c[i] - sla * a; rk = c[i] - sl_v
                pos = 1; ep = c[i]; er = rk; tsl = sl_v

    if pos != 0:
        xp = c[-1]
        pnl_r = ((xp - ep) / er) if er > 0 else 0
        trades.append({'pnlDollar': round(pnl_r * RISK, 2), 'pnlR': round(pnl_r, 2),
                       'sla_used': trade_sla, 'dir': 'LONG',
                       'exitDate': str(df['Date'].iloc[-1])[:10]})
    return trades

# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 110)
    print("ADAPTIVE ATR STRATEGY ANALYSIS")
    print("=" * 110)

    dfs = {}
    for f in sorted(DATA_DIR.glob("*.csv")):
        name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
        dfs[name] = add_indicators(load(f))
    stocks = sorted(dfs.keys())
    print(f"{len(dfs)} stocks: {', '.join(stocks)}\n")

    # ── PART 1: HOW ATR BEHAVES ACROSS STOCKS ──
    print("=" * 110)
    print("PART 1: ATR CHARACTERISTICS PER STOCK")
    print("=" * 110)
    print(f"\n  {'Stock':<8s} {'Avg ATR%':>8s} {'Med ATR%':>8s} {'Min ATR%':>8s} {'Max ATR%':>8s} {'Avg Ratio':>9s} {'%Expanding':>11s}")
    print("  " + "-" * 65)
    for name in stocks:
        d = dfs[name]
        ap = d['atr_pct'].dropna()
        ar = d['atr_ratio'].dropna()
        pct_exp = (ar > 1.0).mean() * 100
        print(f"  {name:<8s} {ap.mean():>7.2f}% {ap.median():>7.2f}% {ap.min():>7.2f}% {ap.max():>7.2f}% {ar.mean():>8.3f}  {pct_exp:>10.1f}%")

    # ── PART 2: ALL STRATEGIES — COMBINED RESULTS ──
    print("\n" + "=" * 110)
    print("PART 2: STRATEGY COMPARISON (ALL 12 STOCKS COMBINED)")
    print("=" * 110)

    strategies = {
        '1. BASELINE (SL=1.0)':          (backtest_adaptive, make_baseline),
        '2. Dynamic SL by ATR%':         (backtest_adaptive, make_dynamic_sl_atr_pct),
        '3. Dynamic SL v2 (granular)':   (backtest_adaptive, make_dynamic_sl_v2),
        '4. Dynamic SL by ATR ratio':    (backtest_adaptive, make_dynamic_sl_atr_ratio),
        '5. Dynamic SL by percentile':   (backtest_adaptive, make_dynamic_sl_percentile),
        '6. Skip contracting ATR':       (backtest_adaptive, make_skip_contracting_atr),
        '7. ATR expanding only':         (backtest_adaptive, make_atr_expanding_only),
        '8. ATR expanding >1.1 only':    (backtest_adaptive, make_atr_expanding_1_1),
        '9. Skip low ATR percentile':    (backtest_adaptive, make_skip_low_pctile),
        '10. Combined skip+dynamic':     (backtest_adaptive, make_combined_expand_dynamic),
        '11. Skip ATR%<1.5 + dynamic':   (backtest_adaptive, make_atr_pct_dynamic_skip_low),
        '12. LONGS ONLY (SL=1.0)':       (backtest_longs_only, make_baseline),
        '13. Longs + dynamic SL':        (backtest_longs_only, make_longs_dynamic_sl),
        '14. Longs + ATR expanding':     (backtest_longs_only, make_expanding_longs_only),
    }

    header = f"  {'Strategy':<35s} {'Trades':>6s} {'P&L':>9s} {'WR%':>6s} {'PF':>6s} {'MaxDD':>8s} {'RF':>6s} {'$/Trade':>8s}"
    print(f"\n{header}")
    print("  " + "-" * (len(header)-2))

    all_results = {}
    for sname, (bt_fn, strat_fn) in strategies.items():
        all_trades = []
        per_stock = {}
        for name in stocks:
            trades = bt_fn(dfs[name], name, strat_fn)
            all_trades.extend(trades)
            per_stock[name] = trades
        all_trades.sort(key=lambda t: t.get('exitDate', ''))
        n, pnl, wr, pf, mdd, rf, ppt = metrics(all_trades)
        all_results[sname] = {'all': all_trades, 'per_stock': per_stock,
                               'metrics': (n, pnl, wr, pf, mdd, rf, ppt)}
        print(f"  {sname:<35s} {n:>6d} ${pnl:>8.0f} {wr:>5.1f}% {pf:>5.2f} ${mdd:>7.0f} {rf:>5.2f} ${ppt:>7.2f}")

    # ── PART 3: PER-STOCK BREAKDOWN OF TOP STRATEGIES ──
    print("\n" + "=" * 110)
    print("PART 3: PER-STOCK P&L FOR TOP STRATEGIES")
    print("=" * 110)

    top_strats = [
        '1. BASELINE (SL=1.0)',
        '2. Dynamic SL by ATR%',
        '3. Dynamic SL v2 (granular)',
        '6. Skip contracting ATR',
        '11. Skip ATR%<1.5 + dynamic',
        '12. LONGS ONLY (SL=1.0)',
        '13. Longs + dynamic SL',
    ]

    # Header
    h = f"  {'Stock':<8s}"
    for sn in top_strats:
        short = sn.split('. ')[1][:18]
        h += f" {short:>20s}"
    print(f"\n{h}")
    print("  " + "-" * (6 + 21 * len(top_strats)))

    for name in stocks:
        row = f"  {name:<6s}"
        for sn in top_strats:
            trades = all_results[sn]['per_stock'][name]
            pnl = sum(t['pnlDollar'] for t in trades)
            n = len(trades)
            row += f"  ${pnl:>6.0f} ({n:>2d}t)"
        print(row)

    # Totals
    row = f"  {'TOTAL':<6s}"
    for sn in top_strats:
        n, pnl, *_ = all_results[sn]['metrics']
        row += f"  ${pnl:>6.0f} ({n:>2d}t)"
    print("  " + "-" * (6 + 21 * len(top_strats)))
    print(row)

    # ── PART 4: WHAT SL DID THE DYNAMIC STRATEGIES ACTUALLY USE? ──
    print("\n" + "=" * 110)
    print("PART 4: SL DISTRIBUTION IN DYNAMIC STRATEGIES")
    print("=" * 110)

    for sn in ['2. Dynamic SL by ATR%', '3. Dynamic SL v2 (granular)', '11. Skip ATR%<1.5 + dynamic']:
        print(f"\n  {sn}:")
        for name in stocks:
            trades = all_results[sn]['per_stock'][name]
            if not trades:
                print(f"    {name}: no trades")
                continue
            slas = [t['sla_used'] for t in trades]
            sl_counts = defaultdict(int)
            for s in slas: sl_counts[s] += 1
            pnl = sum(t['pnlDollar'] for t in trades)
            sl_str = ", ".join(f"SL{k}×:{v}t" for k, v in sorted(sl_counts.items()))
            print(f"    {name}: P&L=${pnl:>7.0f}  {sl_str}")

    # ── PART 5: DEEP COMPARISON — WHAT CHANGED FOR LOSERS? ──
    print("\n" + "=" * 110)
    print("PART 5: IMPACT ON PREVIOUSLY LOSING STOCKS")
    print("=" * 110)

    losers = ['MSFT', 'ADBE', 'META', 'SNOW']
    for name in losers:
        print(f"\n  ── {name} ──")
        print(f"  {'Strategy':<35s} {'Trades':>6s} {'P&L':>8s} {'WR%':>6s}")
        print(f"  {'-'*58}")
        for sn, res in all_results.items():
            trades = res['per_stock'][name]
            n = len(trades)
            pnl = sum(t['pnlDollar'] for t in trades)
            wins = len([t for t in trades if t['pnlDollar'] > 0])
            wr = round(100 * wins / n, 1) if n else 0
            marker = " ★" if pnl > 0 else ""
            print(f"  {sn:<35s} {n:>6d} ${pnl:>7.0f} {wr:>5.1f}%{marker}")

    # ── PART 6: YEARLY CONSISTENCY CHECK ──
    print("\n" + "=" * 110)
    print("PART 6: YEARLY P&L — BASELINE vs BEST ADAPTIVE")
    print("=" * 110)

    for sn in ['1. BASELINE (SL=1.0)', '2. Dynamic SL by ATR%', '3. Dynamic SL v2 (granular)',
               '12. LONGS ONLY (SL=1.0)', '13. Longs + dynamic SL']:
        trades = all_results[sn]['all']
        by_year = defaultdict(list)
        for t in trades:
            yr = t['exitDate'][:4]
            by_year[yr].append(t['pnlDollar'])
        years = sorted(by_year)
        ystr = "  ".join(f"{yr}: ${sum(by_year[yr]):>6.0f} ({len(by_year[yr]):>2d}t)" for yr in years)
        print(f"\n  {sn}")
        print(f"    {ystr}")

    # ── PART 7: VERDICT ──
    print("\n" + "=" * 110)
    print("PART 7: VERDICT")
    print("=" * 110)

    print("""
  ATR MEASUREMENT:
    ATR% = ATR(14) / Close × 100    → normalizes across stocks ($5 ATR on a $500 stock = 1%)
    ATR Ratio = ATR(14) / SMA(ATR,50) → >1.0 means expanding (trending), <1.0 contracting (choppy)
    ATR Percentile = rank of current ATR in last 100 bars → 0.75 = higher than 75% of recent bars

  THE IDEA:
    High ATR% stocks (NVDA 4.15%, TSLA 4.98%) → tight SL (1.0×) works → bigger position, bigger R
    Low ATR% stocks (MSFT 2.17%, SPY 1.32%) → tight SL gets clipped by noise → need wider SL
    When ATR is expanding → market is moving, trends forming → trade
    When ATR is contracting → market is quiet, whipsaw zone → skip or widen stops
    """)

    # Find best overall
    best = max(all_results.items(), key=lambda x: x[1]['metrics'][5])  # by RF
    n, pnl, wr, pf, mdd, rf, ppt = best[1]['metrics']
    print(f"  BEST BY RECOVERY FACTOR: {best[0]}")
    print(f"    {n} trades, ${pnl:.0f} P&L, {wr}% WR, PF {pf}, MaxDD ${mdd:.0f}, RF {rf}, ${ppt}/trade")

    best_pnl = max(all_results.items(), key=lambda x: x[1]['metrics'][1])  # by P&L
    n, pnl, wr, pf, mdd, rf, ppt = best_pnl[1]['metrics']
    print(f"\n  BEST BY TOTAL P&L: {best_pnl[0]}")
    print(f"    {n} trades, ${pnl:.0f} P&L, {wr}% WR, PF {pf}, MaxDD ${mdd:.0f}, RF {rf}, ${ppt}/trade")

    print()
