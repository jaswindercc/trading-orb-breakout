#!/usr/bin/env python3
"""
Deep analysis: WHY does the SMA crossover strategy work on some stocks but not others?
Compares stock characteristics with strategy performance to find the pattern.
"""
import pandas as pd, numpy as np, json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("/workspaces/jas/data")
RISK = 100.0
CFG = dict(mdist=3.0, mbar=2.0, sla=1.0, tb=1.0, tsr=2.5)

# ─────────────────────────────────────────────────────────────────────
# DATA LOADING & INDICATORS
# ─────────────────────────────────────────────────────────────────────
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
    d['sma100']= d['Close'].rolling(100).mean()
    d['sma200']= d['Close'].rolling(200).mean()
    d['tr'] = np.maximum(d['High']-d['Low'],
        np.maximum(abs(d['High']-d['Close'].shift(1)), abs(d['Low']-d['Close'].shift(1))))
    d['atr']  = d['tr'].rolling(14).mean()
    d['tEma'] = d['Close'].ewm(span=20, adjust=False).mean()
    d['bRng'] = d['High'] - d['Low']
    d['fAbv'] = (d['fSma'] > d['sSma']).astype(int)
    d['xUp']  = (d['fAbv']==1) & (d['fAbv'].shift(1)==0)
    d['xDn']  = (d['fAbv']==0) & (d['fAbv'].shift(1)==1)
    # Returns for analysis
    d['ret1d'] = d['Close'].pct_change()
    d['ret5d'] = d['Close'].pct_change(5)
    d['ret20d']= d['Close'].pct_change(20)
    d['vol20'] = d['ret1d'].rolling(20).std() * np.sqrt(252)  # annualized vol
    d['atr_pct'] = d['atr'] / d['Close'] * 100  # ATR as % of price
    return d

# ─────────────────────────────────────────────────────────────────────
# BACKTEST ENGINE (returns detailed trade list)
# ─────────────────────────────────────────────────────────────────────
def backtest(df, name, cfg=None):
    if cfg is None: cfg = CFG
    sla = cfg['sla']; tsr = cfg['tsr']; tb = cfg['tb']
    mbar = cfg['mbar']; mdist = cfg['mdist']

    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; sSma = df['sSma'].values
    atr = df['atr'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values; xUp = df['xUp'].values; xDn = df['xDn'].values
    dates = df['Date'].values
    tEma = df['tEma'].values
    vol20 = df['vol20'].values if 'vol20' in df.columns else np.full(len(df), np.nan)
    atr_pct = df['atr_pct'].values if 'atr_pct' in df.columns else np.full(len(df), np.nan)
    sma200 = df['sma200'].values if 'sma200' in df.columns else np.full(len(df), np.nan)
    ret20d = df['ret20d'].values if 'ret20d' in df.columns else np.full(len(df), np.nan)

    trades = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999; ei = 0

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
                ed = pd.Timestamp(dates[ei]); xd = pd.Timestamp(dates[i])
                dur = int((xd - ed).days)
                # Capture context at entry for analysis
                trades.append({
                    'stock': name, 'dir': 'LONG' if pos == 1 else 'SHORT',
                    'entryDate': str(dates[ei])[:10], 'exitDate': str(dates[i])[:10],
                    'entryPrice': round(ep, 2), 'exitPrice': round(xp, 2),
                    'pnlR': round(pnl_r, 2), 'pnlDollar': round(pnl_r * RISK, 2),
                    'exitReason': 'Trail' if pnl_r > 0 else 'SL',
                    'durationDays': dur,
                    # Context at entry
                    'entry_vol20': round(vol20[ei], 4) if not np.isnan(vol20[ei]) else None,
                    'entry_atr_pct': round(atr_pct[ei], 3) if not np.isnan(atr_pct[ei]) else None,
                    'entry_above_sma200': bool(c[ei] > sma200[ei]) if not np.isnan(sma200[ei]) else None,
                    'entry_ret20d': round(ret20d[ei], 4) if not np.isnan(ret20d[ei]) else None,
                    'entry_bar_idx': ei,
                    'exit_bar_idx': i,
                })
                pos = 0

        if pos == 0:
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a
            if dok and bok and xl:
                sl_v = c[i] - sla * a; rk = c[i] - sl_v
                pos = 1; ep = c[i]; er = rk; tsl = sl_v; ei = i
            elif dok and bok and xs:
                sl_v = c[i] + sla * a; rk = sl_v - c[i]
                pos = -1; ep = c[i]; er = rk; tsl = sl_v; ei = i

    # close open position
    if pos != 0:
        xp = c[-1]
        pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
        ed = pd.Timestamp(dates[ei]); xd = pd.Timestamp(dates[-1])
        dur = int((xd - ed).days)
        trades.append({
            'stock': name, 'dir': 'LONG' if pos == 1 else 'SHORT',
            'entryDate': str(dates[ei])[:10], 'exitDate': str(dates[-1])[:10],
            'entryPrice': round(ep, 2), 'exitPrice': round(xp, 2),
            'pnlR': round(pnl_r, 2), 'pnlDollar': round(pnl_r * RISK, 2),
            'exitReason': 'Open', 'durationDays': dur,
            'entry_vol20': round(vol20[ei], 4) if not np.isnan(vol20[ei]) else None,
            'entry_atr_pct': round(atr_pct[ei], 3) if not np.isnan(atr_pct[ei]) else None,
            'entry_above_sma200': bool(c[ei] > sma200[ei]) if not np.isnan(sma200[ei]) else None,
            'entry_ret20d': round(ret20d[ei], 4) if not np.isnan(ret20d[ei]) else None,
            'entry_bar_idx': ei, 'exit_bar_idx': len(df)-1,
        })

    return trades

# ─────────────────────────────────────────────────────────────────────
# STOCK CHARACTERISTIC ANALYSIS
# ─────────────────────────────────────────────────────────────────────
def stock_characteristics(df, name):
    """Compute key characteristics that might explain strategy performance."""
    c = df['Close'].values
    dates = df['Date'].values

    # Overall return
    total_ret = (c[-1] / c[0] - 1) * 100

    # Trendiness: % of time price is above SMA200
    sma200 = df['sma200'].values
    valid_mask = ~np.isnan(sma200)
    pct_above_200 = np.mean(c[valid_mask] > sma200[valid_mask]) * 100 if valid_mask.sum() > 0 else 0

    # Trendiness: SMA50 slope consistency (% of days slope is same direction)
    sma50 = df['sSma'].values
    sma50_diff = np.diff(sma50[~np.isnan(sma50)])
    if len(sma50_diff) > 0:
        pct_same_dir = max(np.mean(sma50_diff > 0), np.mean(sma50_diff < 0)) * 100
    else:
        pct_same_dir = 50

    # Number of SMA10/50 crossovers (more = choppier)
    fAbv = df['fAbv'].values
    crossovers = np.sum(np.abs(np.diff(fAbv[~np.isnan(fAbv)])))

    # Average whipsaw duration: avg days between crossovers
    cross_idx = np.where(np.abs(np.diff(fAbv)) == 1)[0]
    if len(cross_idx) > 1:
        avg_cross_gap = np.mean(np.diff(cross_idx))
    else:
        avg_cross_gap = len(df)

    # Volatility regime
    vol20 = df['vol20'].dropna()
    avg_vol = vol20.mean() * 100  # in %
    vol_of_vol = vol20.std() / vol20.mean() * 100 if vol20.mean() > 0 else 0  # vol stability

    # ATR as % of price (cost of doing business)
    atr_pct = df['atr_pct'].dropna()
    avg_atr_pct = atr_pct.mean()

    # Mean reversion vs trending: autocorrelation of daily returns
    rets = df['ret1d'].dropna()
    autocorr_1 = rets.autocorr(lag=1) if len(rets) > 10 else 0
    autocorr_5 = rets.autocorr(lag=5) if len(rets) > 10 else 0

    # Biggest drawdown of the stock itself
    cummax = np.maximum.accumulate(c)
    dd = (c - cummax) / cummax
    max_dd = dd.min() * 100

    # Choppiness: count how many times price crosses SMA10
    fSma = df['fSma'].values
    valid = ~np.isnan(fSma)
    above = c[valid] > fSma[valid]
    sma10_crosses = np.sum(np.abs(np.diff(above.astype(int))))

    # Trend strength: average absolute 20-day return
    ret20 = df['ret20d'].dropna()
    avg_abs_ret20 = ret20.abs().mean() * 100

    # ADX-like measure: directional movement ratio
    # Ratio of absolute price move over period vs sum of absolute daily moves
    # Higher = more trending, lower = more mean-reverting
    window = 50
    abs_daily = rets.abs()
    if len(rets) > window:
        chunks = [rets.iloc[i:i+window] for i in range(0, len(rets)-window, window)]
        efficiency_ratios = []
        for chunk in chunks:
            if len(chunk) == window:
                net_move = abs(chunk.sum())
                total_move = chunk.abs().sum()
                if total_move > 0:
                    efficiency_ratios.append(net_move / total_move)
        avg_efficiency = np.mean(efficiency_ratios) if efficiency_ratios else 0
    else:
        avg_efficiency = 0

    return {
        'stock': name,
        'total_ret_%': round(total_ret, 1),
        'pct_above_sma200': round(pct_above_200, 1),
        'sma50_trend_consistency_%': round(pct_same_dir, 1),
        'num_crossovers': int(crossovers),
        'avg_days_between_crosses': round(avg_cross_gap, 1),
        'avg_annual_vol_%': round(avg_vol, 1),
        'vol_stability_%': round(vol_of_vol, 1),
        'avg_atr_%': round(avg_atr_pct, 2),
        'autocorr_1d': round(autocorr_1, 3),
        'autocorr_5d': round(autocorr_5, 3),
        'stock_max_dd_%': round(max_dd, 1),
        'sma10_crosses': int(sma10_crosses),
        'avg_abs_20d_ret_%': round(avg_abs_ret20, 1),
        'efficiency_ratio': round(avg_efficiency, 3),
    }

def trade_metrics(trades):
    """Compute strategy metrics for a list of trades."""
    if not trades:
        return {'trades': 0, 'pnl': 0, 'wr': 0, 'pf': 0, 'avg_r': 0, 'mdd': 0, 'rf': 0,
                'avg_win_r': 0, 'avg_loss_r': 0, 'best_r': 0, 'worst_r': 0,
                'long_wr': 0, 'short_wr': 0, 'long_pnl': 0, 'short_pnl': 0, 'mcl': 0}

    wins = [t for t in trades if t['pnlDollar'] > 0]
    losses = [t for t in trades if t['pnlDollar'] <= 0]
    pnl = sum(t['pnlDollar'] for t in trades)
    gw = sum(t['pnlDollar'] for t in wins)
    gl = abs(sum(t['pnlDollar'] for t in losses))
    pf = round(gw / gl, 2) if gl else 99
    wr = round(100 * len(wins) / len(trades), 1)
    avg_r = round(sum(t['pnlR'] for t in trades) / len(trades), 2)

    # Max drawdown
    eq = 0; peak = 0; mdd = 0
    for t in trades:
        eq += t['pnlDollar']; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    rf = round(pnl / mdd, 2) if mdd > 0 else 99

    # Win/loss stats
    avg_win_r = round(np.mean([t['pnlR'] for t in wins]), 2) if wins else 0
    avg_loss_r = round(np.mean([t['pnlR'] for t in losses]), 2) if losses else 0
    best_r = max(t['pnlR'] for t in trades)
    worst_r = min(t['pnlR'] for t in trades)

    # Long vs short
    longs = [t for t in trades if t['dir'] == 'LONG']
    shorts = [t for t in trades if t['dir'] == 'SHORT']
    long_wins = [t for t in longs if t['pnlDollar'] > 0]
    short_wins = [t for t in shorts if t['pnlDollar'] > 0]
    long_wr = round(100 * len(long_wins) / len(longs), 1) if longs else 0
    short_wr = round(100 * len(short_wins) / len(shorts), 1) if shorts else 0
    long_pnl = round(sum(t['pnlDollar'] for t in longs), 2)
    short_pnl = round(sum(t['pnlDollar'] for t in shorts), 2)

    # Max consecutive losses
    cl = 0; mcl_val = 0
    for t in trades:
        if t['pnlDollar'] <= 0: cl += 1
        else: cl = 0
        mcl_val = max(mcl_val, cl)

    return {
        'trades': len(trades), 'pnl': round(pnl, 2), 'wr': wr, 'pf': pf,
        'avg_r': avg_r, 'mdd': round(mdd, 2), 'rf': rf,
        'avg_win_r': avg_win_r, 'avg_loss_r': avg_loss_r,
        'best_r': best_r, 'worst_r': worst_r,
        'long_wr': long_wr, 'short_wr': short_wr,
        'long_pnl': long_pnl, 'short_pnl': short_pnl,
        'mcl': mcl_val,
    }

# ─────────────────────────────────────────────────────────────────────
# YEARLY BREAKDOWN
# ─────────────────────────────────────────────────────────────────────
def yearly_breakdown(trades):
    """P&L and WR by year."""
    by_year = defaultdict(list)
    for t in trades:
        yr = t['exitDate'][:4]
        by_year[yr].append(t)
    result = {}
    for yr in sorted(by_year):
        ts = by_year[yr]
        wins = [t for t in ts if t['pnlDollar'] > 0]
        result[yr] = {
            'trades': len(ts),
            'pnl': round(sum(t['pnlDollar'] for t in ts), 2),
            'wr': round(100 * len(wins) / len(ts), 1) if ts else 0,
        }
    return result

# ─────────────────────────────────────────────────────────────────────
# TRADE CONTEXT ANALYSIS
# ─────────────────────────────────────────────────────────────────────
def context_analysis(trades):
    """Analyze trade outcomes based on market context at entry."""
    if not trades:
        return {}

    # Split by entry volatility
    valid_vol = [t for t in trades if t.get('entry_vol20') is not None]
    if valid_vol:
        med_vol = np.median([t['entry_vol20'] for t in valid_vol])
        high_vol = [t for t in valid_vol if t['entry_vol20'] > med_vol]
        low_vol = [t for t in valid_vol if t['entry_vol20'] <= med_vol]
    else:
        high_vol = low_vol = []

    # Split by trend (above/below SMA200)
    above_200 = [t for t in trades if t.get('entry_above_sma200') == True]
    below_200 = [t for t in trades if t.get('entry_above_sma200') == False]

    # Split by momentum (20d return at entry)
    valid_mom = [t for t in trades if t.get('entry_ret20d') is not None]
    if valid_mom:
        pos_mom = [t for t in valid_mom if t['entry_ret20d'] > 0]
        neg_mom = [t for t in valid_mom if t['entry_ret20d'] <= 0]
    else:
        pos_mom = neg_mom = []

    # Split by direction
    longs = [t for t in trades if t['dir'] == 'LONG']
    shorts = [t for t in trades if t['dir'] == 'SHORT']

    # Above 200 longs vs shorts
    above_200_longs = [t for t in above_200 if t['dir'] == 'LONG']
    below_200_shorts = [t for t in below_200 if t['dir'] == 'SHORT']
    below_200_longs = [t for t in below_200 if t['dir'] == 'LONG']
    above_200_shorts = [t for t in above_200 if t['dir'] == 'SHORT']

    def quick_stats(ts, label):
        if not ts:
            return f"  {label}: no trades"
        wins = len([t for t in ts if t['pnlDollar'] > 0])
        pnl = sum(t['pnlDollar'] for t in ts)
        wr = round(100 * wins / len(ts), 1)
        avg_r = round(sum(t['pnlR'] for t in ts) / len(ts), 2)
        return f"  {label}: {len(ts)}t  WR={wr}%  P&L=${pnl:.0f}  AvgR={avg_r}"

    lines = []
    lines.append(quick_stats(high_vol, "High vol entries"))
    lines.append(quick_stats(low_vol,  "Low vol entries "))
    lines.append(quick_stats(above_200, "Above SMA200    "))
    lines.append(quick_stats(below_200, "Below SMA200    "))
    lines.append(quick_stats(above_200_longs, "Above200 LONG   "))
    lines.append(quick_stats(below_200_shorts,"Below200 SHORT  "))
    lines.append(quick_stats(below_200_longs, "Below200 LONG   "))
    lines.append(quick_stats(above_200_shorts,"Above200 SHORT  "))
    lines.append(quick_stats(pos_mom,  "Pos 20d momentum"))
    lines.append(quick_stats(neg_mom,  "Neg 20d momentum"))
    return '\n'.join(lines)

# ─────────────────────────────────────────────────────────────────────
# STOCK vs STRATEGY EQUITY COMPARISON
# ─────────────────────────────────────────────────────────────────────
def equity_vs_stock(df, trades):
    """Compare strategy equity curve vs buy-and-hold of the stock.
    Returns correlation and whether strategy captures up/down moves."""
    if not trades:
        return {'corr': 0, 'up_capture': 0, 'down_capture': 0}

    # Build strategy equity by date
    eq_by_date = {}
    eq = 0
    for t in trades:
        eq += t['pnlDollar']
        eq_by_date[t['exitDate']] = eq

    # Stock returns in windows matching trade periods
    up_trades_in_up_stock = 0; total_up_stock = 0
    down_trades_in_down_stock = 0; total_down_stock = 0

    for t in trades:
        try:
            entry_idx = t['entry_bar_idx']
            exit_idx = t['exit_bar_idx']
            stock_ret = (df['Close'].iloc[exit_idx] / df['Close'].iloc[entry_idx] - 1)
            trade_ret = t['pnlR']

            if stock_ret > 0:
                total_up_stock += 1
                if trade_ret > 0:
                    up_trades_in_up_stock += 1
            elif stock_ret < 0:
                total_down_stock += 1
                if trade_ret > 0:
                    down_trades_in_down_stock += 1
        except:
            pass

    up_capture = round(100 * up_trades_in_up_stock / total_up_stock, 1) if total_up_stock > 0 else 0
    down_capture = round(100 * down_trades_in_down_stock / total_down_stock, 1) if total_down_stock > 0 else 0

    return {'up_capture_%': up_capture, 'down_capture_%': down_capture}

# ─────────────────────────────────────────────────────────────────────
# IMPROVEMENT IDEAS - TEST FILTERS
# ─────────────────────────────────────────────────────────────────────
def test_filter_ideas(dfs_dict):
    """Test various filter improvements across all stocks."""
    ideas = []

    # Idea 1: Only trade when stock is above SMA200 (longs) / below SMA200 (shorts)
    # Idea 2: Only trade when ATR% is below a threshold (avoid low-ATR choppy stocks)
    # Idea 3: Only trade when efficiency ratio > threshold (trending)
    # Idea 4: Skip stocks with too many crossovers
    # Idea 5: Require minimum 20d momentum in trade direction
    # Idea 6: Volatility filter (only trade in certain vol regimes)
    # Idea 7: Only longs (skip shorts entirely)
    # Idea 8: SMA200 direction filter
    # Idea 9: Different SL per volatility regime

    filters = {
        'baseline': lambda t, df, i: True,
        'only_longs': lambda t, df, i: t == 1,
        'sma200_dir_filter': lambda t, df, i: (
            (t == 1 and not np.isnan(df['sma200'].iloc[i]) and df['Close'].iloc[i] > df['sma200'].iloc[i]) or
            (t == -1 and not np.isnan(df['sma200'].iloc[i]) and df['Close'].iloc[i] < df['sma200'].iloc[i])
        ),
        'sma200_longs_only': lambda t, df, i: (
            t == 1 and not np.isnan(df['sma200'].iloc[i]) and df['Close'].iloc[i] > df['sma200'].iloc[i]
        ),
        'min_atr_pct_0.8': lambda t, df, i: (
            not np.isnan(df['atr_pct'].iloc[i]) and df['atr_pct'].iloc[i] >= 0.8
        ),
        'min_atr_pct_1.2': lambda t, df, i: (
            not np.isnan(df['atr_pct'].iloc[i]) and df['atr_pct'].iloc[i] >= 1.2
        ),
        'pos_20d_mom_long': lambda t, df, i: (
            (t == 1 and not np.isnan(df['ret20d'].iloc[i]) and df['ret20d'].iloc[i] > 0) or
            (t == -1 and not np.isnan(df['ret20d'].iloc[i]) and df['ret20d'].iloc[i] < 0)
        ),
        'vol_above_25pct': lambda t, df, i: (
            not np.isnan(df['vol20'].iloc[i]) and df['vol20'].iloc[i] > 0.25
        ),
    }

    return filters

def backtest_with_filter(df, name, filter_fn, cfg=None):
    """Backtest with an additional entry filter."""
    if cfg is None: cfg = CFG
    sla = cfg['sla']; tsr = cfg['tsr']; tb = cfg['tb']
    mbar = cfg['mbar']; mdist = cfg['mdist']

    c = df['Close'].values; h = df['High'].values; l = df['Low'].values
    fSma = df['fSma'].values; atr = df['atr'].values; bRng = df['bRng'].values
    fAbv = df['fAbv'].values; xUp = df['xUp'].values; xDn = df['xDn'].values
    dates = df['Date'].values; tEma = df['tEma'].values

    trades_pnl = []; pos = 0; ep = er = tsl = 0.0; lcd = 0; bsc = 999

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
                trades_pnl.append(pnl_r * RISK)
                pos = 0

        if pos == 0:
            xl = (lcd == 1 and bsc == 0)
            xs = (lcd == -1 and bsc == 0)
            dok = abs(c[i] - fSma[i]) <= mdist * a if not np.isnan(fSma[i]) else False
            bok = bRng[i] <= mbar * a

            trade_dir = 1 if xl else (-1 if xs else 0)
            if dok and bok and (xl or xs) and filter_fn(trade_dir, df, i):
                if xl:
                    sl_v = c[i] - sla * a; rk = c[i] - sl_v
                    pos = 1; ep = c[i]; er = rk; tsl = sl_v
                elif xs:
                    sl_v = c[i] + sla * a; rk = sl_v - c[i]
                    pos = -1; ep = c[i]; er = rk; tsl = sl_v

    if pos != 0:
        xp = c[-1]
        pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
        trades_pnl.append(pnl_r * RISK)

    return trades_pnl

# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 100)
    print("DEEP ANALYSIS: Why does the strategy work on some stocks but not others?")
    print("=" * 100)

    # Load all stocks
    dfs = {}
    for f in sorted(DATA_DIR.glob("*.csv")):
        name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
        dfs[name] = add_indicators(load(f))

    print(f"\n{len(dfs)} stocks loaded: {', '.join(sorted(dfs.keys()))}")

    # ── PART 1: PER-STOCK PERFORMANCE ──
    print("\n" + "=" * 100)
    print("PART 1: PER-STOCK STRATEGY PERFORMANCE")
    print("=" * 100)

    all_trades = {}
    all_metrics = {}
    all_chars = {}

    for name in sorted(dfs):
        trades = backtest(dfs[name], name)
        closed = [t for t in trades if t['exitDate']]
        all_trades[name] = closed
        all_metrics[name] = trade_metrics(closed)
        all_chars[name] = stock_characteristics(dfs[name], name)

    # Sort by P&L
    sorted_stocks = sorted(all_metrics, key=lambda x: all_metrics[x]['pnl'], reverse=True)

    header = f"{'Stock':<8s} {'Trades':>6s} {'P&L':>9s} {'WR%':>6s} {'PF':>6s} {'AvgR':>6s} {'MaxDD':>8s} {'RF':>6s} {'MCL':>4s} {'LongPnl':>9s} {'ShortPnl':>9s} {'LWR%':>6s} {'SWR%':>6s}"
    print(f"\n{header}")
    print("-" * len(header))
    for name in sorted_stocks:
        m = all_metrics[name]
        print(f"  {name:<6s} {m['trades']:>6d} ${m['pnl']:>8.0f} {m['wr']:>5.1f}% {m['pf']:>5.2f} {m['avg_r']:>5.2f} ${m['mdd']:>7.0f} {m['rf']:>5.2f} {m['mcl']:>4d}  ${m['long_pnl']:>8.0f} ${m['short_pnl']:>8.0f} {m['long_wr']:>5.1f}% {m['short_wr']:>5.1f}%")

    # Total across all stocks
    all_t = []
    for name in sorted(dfs):
        all_t.extend(all_trades[name])
    all_t.sort(key=lambda t: t['exitDate'])
    total_m = trade_metrics(all_t)
    print(f"\n  {'TOTAL':<6s} {total_m['trades']:>6d} ${total_m['pnl']:>8.0f} {total_m['wr']:>5.1f}% {total_m['pf']:>5.2f} {total_m['avg_r']:>5.2f} ${total_m['mdd']:>7.0f} {total_m['rf']:>5.2f} {total_m['mcl']:>4d}  ${total_m['long_pnl']:>8.0f} ${total_m['short_pnl']:>8.0f} {total_m['long_wr']:>5.1f}% {total_m['short_wr']:>5.1f}%")

    # ── PART 2: STOCK CHARACTERISTICS vs PERFORMANCE ──
    print("\n" + "=" * 100)
    print("PART 2: STOCK CHARACTERISTICS (why some work, some don't)")
    print("=" * 100)

    header2 = f"{'Stock':<8s} {'StockRet%':>9s} {'%>SMA200':>8s} {'Crosses':>8s} {'AvgGap':>7s} {'AvgVol%':>7s} {'ATR%':>6s} {'AC1d':>6s} {'Effic':>6s} {'StockDD%':>9s} {'SMA10x':>7s} {'AbsR20%':>8s}"
    print(f"\n{header2}")
    print("-" * len(header2))
    for name in sorted_stocks:
        c = all_chars[name]
        print(f"  {name:<6s} {c['total_ret_%']:>8.1f}% {c['pct_above_sma200']:>7.1f}% {c['num_crossovers']:>8d} {c['avg_days_between_crosses']:>6.1f}d {c['avg_annual_vol_%']:>6.1f}% {c['avg_atr_%']:>5.2f} {c['autocorr_1d']:>5.3f} {c['efficiency_ratio']:>5.3f} {c['stock_max_dd_%']:>8.1f}% {c['sma10_crosses']:>7d} {c['avg_abs_20d_ret_%']:>7.1f}%")

    # ── PART 3: CORRELATION ANALYSIS ──
    print("\n" + "=" * 100)
    print("PART 3: WHAT PREDICTS STRATEGY SUCCESS?")
    print("=" * 100)

    # Build a simple table of characteristics vs P&L
    char_names = ['total_ret_%', 'pct_above_sma200', 'num_crossovers', 'avg_days_between_crosses',
                  'avg_annual_vol_%', 'avg_atr_%', 'autocorr_1d', 'efficiency_ratio',
                  'stock_max_dd_%', 'sma10_crosses', 'avg_abs_20d_ret_%']

    pnls = np.array([all_metrics[name]['pnl'] for name in sorted(dfs)])
    print(f"\nCorrelation of stock characteristics with strategy P&L:")
    print(f"{'Characteristic':<35s} {'Correlation':>12s} {'Interpretation'}")
    print("-" * 80)
    for cname in char_names:
        vals = np.array([all_chars[name][cname] for name in sorted(dfs)])
        if np.std(vals) > 0:
            corr = np.corrcoef(vals, pnls)[0, 1]
        else:
            corr = 0
        # Interpretation
        if abs(corr) > 0.6:
            interp = "STRONG" + (" positive" if corr > 0 else " negative")
        elif abs(corr) > 0.3:
            interp = "moderate" + (" positive" if corr > 0 else " negative")
        else:
            interp = "weak"
        print(f"  {cname:<33s} {corr:>+.3f}       {interp}")

    # ── PART 4: YEARLY BREAKDOWN ──
    print("\n" + "=" * 100)
    print("PART 4: YEARLY BREAKDOWN PER STOCK")
    print("=" * 100)

    years = sorted(set(t['exitDate'][:4] for t in all_t))
    header3 = f"{'Stock':<8s}" + "".join(f" {'──'+yr+'──':>14s}" for yr in years)
    print(f"\n{header3}")
    for name in sorted_stocks:
        yb = yearly_breakdown(all_trades[name])
        row = f"  {name:<6s}"
        for yr in years:
            if yr in yb:
                y = yb[yr]
                row += f"  ${y['pnl']:>5.0f} ({y['wr']:>4.1f}%)"
            else:
                row += f"  {'--':>14s}"
        print(row)

    # ── PART 5: TRADE CONTEXT ANALYSIS (ALL STOCKS COMBINED) ──
    print("\n" + "=" * 100)
    print("PART 5: TRADE CONTEXT ANALYSIS (what entry conditions lead to wins?)")
    print("=" * 100)

    print(f"\n── All stocks combined ──")
    print(context_analysis(all_t))

    # Per winner vs loser stock
    winners = [n for n in sorted_stocks if all_metrics[n]['pnl'] > 0]
    losers = [n for n in sorted_stocks if all_metrics[n]['pnl'] <= 0]

    if winners:
        print(f"\n── Winning stocks ({', '.join(winners)}) ──")
        winner_trades = [t for t in all_t if t['stock'] in winners]
        print(context_analysis(winner_trades))

    if losers:
        print(f"\n── Losing stocks ({', '.join(losers)}) ──")
        loser_trades = [t for t in all_t if t['stock'] in losers]
        print(context_analysis(loser_trades))

    # ── PART 6: STOCK-BY-STOCK EQUITY vs STRATEGY EQUITY ──
    print("\n" + "=" * 100)
    print("PART 6: STRATEGY vs BUY-AND-HOLD ALIGNMENT")
    print("=" * 100)

    print(f"\n{'Stock':<8s} {'UpCapture%':>11s} {'DnCapture%':>11s} {'Interpretation'}")
    print("-" * 70)
    for name in sorted_stocks:
        ev = equity_vs_stock(dfs[name], all_trades[name])
        up = ev['up_capture_%']; dn = ev['down_capture_%']
        if up > 40 and dn > 30:
            interp = "Good: profits in both directions"
        elif up > 40:
            interp = "OK: captures uptrends, weak on shorts"
        elif dn > 30:
            interp = "OK: captures downtrends, weak on longs"
        else:
            interp = "BAD: misaligned with stock movement"
        print(f"  {name:<6s} {up:>10.1f}% {dn:>10.1f}%   {interp}")

    # ── PART 7: FILTER IMPROVEMENT IDEAS ──
    print("\n" + "=" * 100)
    print("PART 7: FILTER IMPROVEMENT IDEAS")
    print("=" * 100)

    filters = test_filter_ideas(dfs)

    header7 = f"{'Filter':<25s} {'Trades':>6s} {'P&L':>9s} {'WR%':>6s} {'PF':>6s} {'MaxDD':>8s} {'RF':>6s} {'P&L/Trade':>10s}"
    print(f"\n{header7}")
    print("-" * len(header7))

    for fname, ffn in sorted(filters.items()):
        total_pnl = []
        for name in sorted(dfs):
            total_pnl.extend(backtest_with_filter(dfs[name], name, ffn))
        n = len(total_pnl)
        if n == 0:
            print(f"  {fname:<23s} {'no trades':>6s}")
            continue
        pnl = sum(total_pnl)
        wins = len([p for p in total_pnl if p > 0])
        gw = sum(p for p in total_pnl if p > 0)
        gl = abs(sum(p for p in total_pnl if p <= 0))
        pf = round(gw / gl, 2) if gl else 99
        wr = round(100 * wins / n, 1)
        eq = 0; peak = 0; mdd = 0
        for p in total_pnl:
            eq += p; peak = max(peak, eq); mdd = max(mdd, peak - eq)
        rf = round(pnl / mdd, 2) if mdd > 0 else 99
        ppt = round(pnl / n, 2)
        print(f"  {fname:<23s} {n:>6d} ${pnl:>8.0f} {wr:>5.1f}% {pf:>5.2f} ${mdd:>7.0f} {rf:>5.2f} ${ppt:>9.2f}")

    # ── PART 8: PER-STOCK FILTER IMPACT ──
    print("\n" + "=" * 100)
    print("PART 8: PER-STOCK IMPACT OF BEST FILTERS")
    print("=" * 100)

    best_filters = ['baseline', 'only_longs', 'sma200_dir_filter', 'sma200_longs_only', 'min_atr_pct_1.2']

    # Header
    h8 = f"{'Stock':<8s}"
    for fn in best_filters:
        h8 += f" {fn:>20s}"
    print(f"\n{h8}")
    print("-" * (8 + 21 * len(best_filters)))

    for name in sorted_stocks:
        row = f"  {name:<6s}"
        for fn in best_filters:
            pnls_list = backtest_with_filter(dfs[name], name, filters[fn])
            pnl = sum(pnls_list)
            n = len(pnls_list)
            row += f"  ${pnl:>6.0f} ({n:>2d}t)"
            if fn == best_filters[-1]:
                pass
        print(row)

    # ── PART 9: DEEP DIVE INTO WORST STOCKS ──
    print("\n" + "=" * 100)
    print("PART 9: DEEP DIVE - WHY DO LOSING STOCKS FAIL?")
    print("=" * 100)

    for name in losers[:5]:  # Top 5 worst
        trades = all_trades[name]
        chars = all_chars[name]
        m = all_metrics[name]
        print(f"\n{'─'*60}")
        print(f"  {name}: P&L = ${m['pnl']:.0f}, {m['trades']} trades, WR = {m['wr']}%")
        print(f"  Stock returned {chars['total_ret_%']:.1f}% over the period")
        print(f"  {chars['num_crossovers']} SMA crossovers (avg {chars['avg_days_between_crosses']:.0f} days between)")
        print(f"  ATR% = {chars['avg_atr_%']:.2f}%, Efficiency = {chars['efficiency_ratio']:.3f}")
        print(f"  Long P&L: ${m['long_pnl']:.0f} (WR {m['long_wr']}%), Short P&L: ${m['short_pnl']:.0f} (WR {m['short_wr']}%)")
        print(f"\n  Trade-by-trade:")
        for t in trades:
            marker = "✓" if t['pnlDollar'] > 0 else "✗"
            print(f"    {marker} {t['dir']:>5s} {t['entryDate']} → {t['exitDate']}  {t['pnlR']:>+6.2f}R  ${t['pnlDollar']:>+7.0f}  ({t['exitReason']}, {t['durationDays']}d)")

    # ── PART 10: KEY FINDINGS SUMMARY ──
    print("\n" + "=" * 100)
    print("PART 10: KEY FINDINGS SUMMARY")
    print("=" * 100)

    print(f"\n  Winners: {', '.join(winners)}")
    print(f"  Losers:  {', '.join(losers)}")

    # Average characteristics
    if winners and losers:
        print(f"\n  {'Characteristic':<35s} {'Winners Avg':>12s} {'Losers Avg':>12s} {'Delta':>8s}")
        print(f"  {'-'*70}")
        for cname in char_names:
            w_avg = np.mean([all_chars[n][cname] for n in winners])
            l_avg = np.mean([all_chars[n][cname] for n in losers])
            print(f"  {cname:<35s} {w_avg:>12.2f} {l_avg:>12.2f} {w_avg-l_avg:>+8.2f}")

    print(f"\n  Total P&L across all {len(dfs)} stocks: ${total_m['pnl']:.0f}")
    print(f"  Total trades: {total_m['trades']}, WR: {total_m['wr']}%, PF: {total_m['pf']}")
    print()
