#!/usr/bin/env python3
"""
TRAILING STOP STUDY — Comprehensive Parameter Sweep
=====================================================
Uses MA Bounce entry logic (512 trades, most statistical power)
and systematically varies exit parameters to answer:

  1. WHEN should trailing activate? (Trail Start R)
  2. HOW TIGHT should the trail be? (Trail ATR Buffer)
  3. Is trailing BETTER than fixed take-profit?
  4. Does initial stop distance interact with trail timing?
  5. What's the optimal combination?

Methodology:
  - Same entry logic for ALL parameter sets (MA Bounce: EMA20 pullback, SMA50 trend filter)
  - Entry signal is identical; only exit management changes
  - Because exits affect when we're flat → different params = different trade counts
  - All 12 stocks tested, metrics aggregated
  - $100 risk per trade (constant across all tests)

Parameter Grid:
  A. Trail Start R: never, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 7.5, 10.0
  B. Fixed TP (no trail): 1.0R, 1.5R, 2.0R, 2.5R, 3.0R, 4.0R, 5.0R, 7.5R, 10.0R
  C. Trail Buffer: 0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0
  D. Initial SL: 0.5, 0.75, 1.0, 1.5, 2.0
  E. Heatmap: Trail Start R × Trail Buffer (full matrix)
  F. Validation: best params tested on Breakout + Trend Rider entries too

Author: Quant backtest engine
"""
import pandas as pd, numpy as np, json, itertools
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/trail_study_data.json")
RISK = 100.0

# ──────────────────────────────────────────────────────────────
# DATA LOADING + INDICATORS
# ──────────────────────────────────────────────────────────────
def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def add_indicators(df):
    df = df.copy()
    df['ema10'] = df['Close'].ewm(span=10, adjust=False).mean()
    df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['ema30'] = df['Close'].ewm(span=30, adjust=False).mean()
    df['sma10'] = df['Close'].rolling(10).mean()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean()
    tr = np.maximum(df['High'] - df['Low'],
        np.maximum(abs(df['High'] - df['Close'].shift(1)),
                   abs(df['Low'] - df['Close'].shift(1))))
    df['atr'] = tr.rolling(14).mean()
    # Pre-compute trail EMAs for different lengths
    for elen in [10, 15, 20, 30, 50]:
        df[f'trail_ema_{elen}'] = df['Close'].ewm(span=elen, adjust=False).mean()
    return df

# ──────────────────────────────────────────────────────────────
# PARAMETERIZED BACKTEST ENGINE
# ──────────────────────────────────────────────────────────────
def backtest(df, name, params):
    """
    Run MA Bounce backtest with configurable exit parameters.
    
    params dict:
      sl_atr:        Initial SL distance in ATR multiples (default 1.0)
      exit_mode:     'trail' | 'fixed_tp' | 'sl_only'
      trail_start_r: R-multiple at which trailing activates (only for 'trail')
      trail_buf:     ATR buffer below trail EMA (only for 'trail')
      trail_ema_len: EMA length for trailing stop (only for 'trail')
      fixed_tp_r:    R-multiple for fixed take profit (only for 'fixed_tp')
    """
    sl_atr = params.get('sl_atr', 1.0)
    exit_mode = params.get('exit_mode', 'trail')
    trail_start_r = params.get('trail_start_r', 2.5)
    trail_buf = params.get('trail_buf', 1.0)
    trail_ema_len = params.get('trail_ema_len', 20)
    fixed_tp_r = params.get('fixed_tp_r', 3.0)

    trail_ema_col = f'trail_ema_{trail_ema_len}'
    BOUNCE_ATR = 0.5

    trades = []
    pos = 0
    ep = er = tsl = 0.0

    for i in range(1, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]
        atr = r['atr']

        if pd.isna(atr) or atr <= 0 or pd.isna(r['ema20']) or pd.isna(r['sma50']):
            continue

        # ── In a trade: manage exit ──
        if pos == 1:
            hit_exit = False
            xp = 0.0
            reason = ''

            # Check initial/trailing SL
            if r['Low'] <= tsl:
                xp = tsl
                hit_exit = True
                reason = 'SL' if exit_mode == 'sl_only' else 'SL'

            if not hit_exit:
                curr_r = (r['Close'] - ep) / er if er > 0 else 0

                if exit_mode == 'trail':
                    # Update trailing stop if in profit enough
                    if curr_r >= trail_start_r:
                        ema_val = r.get(trail_ema_col, r['ema20'])
                        if pd.notna(ema_val):
                            ema_trail = ema_val - trail_buf * atr
                            if ema_trail > tsl:
                                tsl = ema_trail
                    # Check if trail was hit
                    if r['Low'] <= tsl:
                        xp = tsl
                        hit_exit = True
                        reason = 'Trail'

                elif exit_mode == 'fixed_tp':
                    # Fixed take profit at target R
                    tp_price = ep + fixed_tp_r * er
                    if r['High'] >= tp_price:
                        xp = tp_price
                        hit_exit = True
                        reason = 'TP'

                # sl_only: already handled above, just wait for SL

            if hit_exit:
                pnl_r = (xp - ep) / er if er > 0 else 0
                ed = pd.to_datetime(trades[-1]['entryDate'])
                trades[-1].update({
                    'exitDate': r['Date'].strftime('%Y-%m-%d'),
                    'exitPrice': round(xp, 2),
                    'pnlR': round(pnl_r, 2),
                    'pnlDollar': round(pnl_r * RISK, 2),
                    'exitReason': reason,
                    'durationDays': int((r['Date'] - ed).days)
                })
                pos = 0
            continue

        # ── Flat: look for MA Bounce entry (IDENTICAL for all param sets) ──
        ma_val = r['ema20']
        trend_val = r['sma50']

        if r['Close'] <= trend_val:
            continue

        touched = prev['Low'] <= ma_val + BOUNCE_ATR * atr
        bounced = r['Close'] > ma_val
        not_too_far = r['Close'] - ma_val <= 3.0 * atr
        small_bar = (r['High'] - r['Low']) <= 2.0 * atr

        if touched and bounced and not_too_far and small_bar:
            sl = r['Close'] - sl_atr * atr
            rk = r['Close'] - sl
            if rk <= 0:
                continue
            pos = 1
            ep = r['Close']
            er = rk
            tsl = sl
            trades.append({
                'stock': name, 'dir': 'LONG',
                'entryDate': r['Date'].strftime('%Y-%m-%d'),
                'entryPrice': round(r['Close'], 2),
                'sl': round(sl, 2), 'risk': round(rk, 2),
                'qty': max(1, round(RISK / rk)),
                'exitDate': '', 'exitPrice': 0, 'pnlR': 0,
                'pnlDollar': 0, 'exitReason': '', 'durationDays': 0
            })

    # Close open trade at last bar
    if pos != 0 and trades:
        t = trades[-1]
        last = df.iloc[-1]
        pnl_r = (last['Close'] - ep) / er if er > 0 else 0
        ed = pd.to_datetime(t['entryDate'])
        t.update({
            'exitDate': last['Date'].strftime('%Y-%m-%d'),
            'exitPrice': round(last['Close'], 2),
            'pnlR': round(pnl_r, 2),
            'pnlDollar': round(pnl_r * RISK, 2),
            'exitReason': 'Open',
            'durationDays': int((last['Date'] - ed).days)
        })

    return trades


# ──────────────────────────────────────────────────────────────
# METRICS COMPUTATION
# ──────────────────────────────────────────────────────────────
def compute_metrics(trades):
    """Compute comprehensive metrics from a trade list."""
    closed = [t for t in trades if t['exitDate'] and t['exitReason'] != 'Open']
    if not closed:
        return None

    n = len(closed)
    wins = [t for t in closed if t['pnlR'] > 0]
    losses = [t for t in closed if t['pnlR'] <= 0]
    
    total_pnl = sum(t['pnlDollar'] for t in closed)
    win_rate = len(wins) / n * 100 if n else 0
    avg_r = sum(t['pnlR'] for t in closed) / n if n else 0
    
    gross_profit = sum(t['pnlDollar'] for t in wins)
    gross_loss = abs(sum(t['pnlDollar'] for t in losses))
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf')
    
    avg_win_r = sum(t['pnlR'] for t in wins) / len(wins) if wins else 0
    avg_loss_r = sum(t['pnlR'] for t in losses) / len(losses) if losses else 0
    max_win_r = max((t['pnlR'] for t in wins), default=0)
    max_loss_r = min((t['pnlR'] for t in losses), default=0)
    
    avg_dur = sum(t['durationDays'] for t in closed) / n if n else 0
    avg_win_dur = sum(t['durationDays'] for t in wins) / len(wins) if wins else 0
    avg_loss_dur = sum(t['durationDays'] for t in losses) / len(losses) if losses else 0
    
    # Max drawdown
    equity = 0
    peak = 0
    max_dd = 0
    for t in closed:
        equity += t['pnlDollar']
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    # Expectancy per trade
    expectancy = avg_r  # in R terms

    return {
        'trades': n,
        'wins': len(wins),
        'losses': len(losses),
        'winRate': round(win_rate, 1),
        'totalPnl': round(total_pnl, 2),
        'avgR': round(avg_r, 2),
        'profitFactor': pf if pf != float('inf') else 999,
        'avgWinR': round(avg_win_r, 2),
        'avgLossR': round(avg_loss_r, 2),
        'maxWinR': round(max_win_r, 2),
        'maxLossR': round(max_loss_r, 2),
        'avgDuration': round(avg_dur, 1),
        'avgWinDuration': round(avg_win_dur, 1),
        'avgLossDuration': round(avg_loss_dur, 1),
        'maxDD': round(max_dd, 2),
        'expectancy': round(expectancy, 3),
        'grossProfit': round(gross_profit, 2),
        'grossLoss': round(gross_loss, 2),
    }


def run_sweep(stocks_data, params, label=''):
    """Run backtest across all stocks with given params, return aggregate metrics."""
    all_trades = []
    per_stock = {}
    for name, df in stocks_data.items():
        trades = backtest(df, name, params)
        closed = [t for t in trades if t['exitDate'] and t['exitReason'] != 'Open']
        all_trades.extend(closed)
        m = compute_metrics(trades)
        if m:
            per_stock[name] = m

    agg = compute_metrics(all_trades) if all_trades else None
    stocks_positive = sum(1 for s, m in per_stock.items() if m['totalPnl'] > 0)
    
    if agg:
        agg['stocksPositive'] = stocks_positive
        agg['stocksTotal'] = len(per_stock)
    
    return agg, per_stock


# ──────────────────────────────────────────────────────────────
# LOAD ALL STOCK DATA
# ──────────────────────────────────────────────────────────────
print("Loading and preparing stock data...")
stocks_data = {}
for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
    stocks_data[name] = add_indicators(load(f))
print(f"Loaded {len(stocks_data)} stocks: {', '.join(stocks_data.keys())}\n")


# ══════════════════════════════════════════════════════════════
# STUDY A: Trail Start R Sweep
# "When should the trailing stop activate?"
# Fixed: SL=1.0ATR, Buffer=1.0ATR, EMA=20
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("STUDY A: Trail Start R Sweep")
print("=" * 60)

trail_start_values = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 7.5, 10.0]
study_a_results = []

# Baseline: SL only (no trail, no TP)
params = {'sl_atr': 1.0, 'exit_mode': 'sl_only'}
agg, per_stock = run_sweep(stocks_data, params)
if agg:
    result = {'label': 'SL Only (no trail)', 'trailStartR': None, 'exitMode': 'sl_only', **agg}
    study_a_results.append(result)
    print(f"  SL Only:     {agg['trades']:>4} trades  WR={agg['winRate']:>5.1f}%  AvgR={agg['avgR']:>6.2f}  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}")

# Trail at various R-multiples
for r_val in trail_start_values:
    params = {'sl_atr': 1.0, 'exit_mode': 'trail', 'trail_start_r': r_val,
              'trail_buf': 1.0, 'trail_ema_len': 20}
    agg, per_stock = run_sweep(stocks_data, params)
    if agg:
        result = {'label': f'Trail at {r_val}R', 'trailStartR': r_val, 'exitMode': 'trail', **agg}
        study_a_results.append(result)
        marker = ' ← CURRENT' if r_val == 2.5 else ''
        print(f"  Trail {r_val:>4.1f}R:  {agg['trades']:>4} trades  WR={agg['winRate']:>5.1f}%  AvgR={agg['avgR']:>6.2f}  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}{marker}")


# ══════════════════════════════════════════════════════════════
# STUDY B: Fixed TP Comparison
# "Is trailing better than fixed take-profit?"
# Fixed: SL=1.0ATR
# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("STUDY B: Fixed TP Comparison (no trailing)")
print("=" * 60)

fixed_tp_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0]
study_b_results = []

for tp_val in fixed_tp_values:
    params = {'sl_atr': 1.0, 'exit_mode': 'fixed_tp', 'fixed_tp_r': tp_val}
    agg, per_stock = run_sweep(stocks_data, params)
    if agg:
        result = {'label': f'TP at {tp_val}R', 'fixedTpR': tp_val, 'exitMode': 'fixed_tp', **agg}
        study_b_results.append(result)
        print(f"  TP {tp_val:>4.1f}R:    {agg['trades']:>4} trades  WR={agg['winRate']:>5.1f}%  AvgR={agg['avgR']:>6.2f}  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}")


# ══════════════════════════════════════════════════════════════
# STUDY C: Trail Buffer Sweep
# "How tight should the trailing stop be?"
# Fixed: SL=1.0ATR, Trail Start=2.5R, EMA=20
# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("STUDY C: Trail Buffer Sweep (tightness)")
print("=" * 60)

trail_buf_values = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
study_c_results = []

for buf_val in trail_buf_values:
    params = {'sl_atr': 1.0, 'exit_mode': 'trail', 'trail_start_r': 2.5,
              'trail_buf': buf_val, 'trail_ema_len': 20}
    agg, per_stock = run_sweep(stocks_data, params)
    if agg:
        result = {'label': f'Buffer {buf_val}×ATR', 'trailBuf': buf_val, **agg}
        study_c_results.append(result)
        marker = ' ← CURRENT' if buf_val == 1.0 else ''
        print(f"  Buf {buf_val:>4.2f}ATR: {agg['trades']:>4} trades  WR={agg['winRate']:>5.1f}%  AvgR={agg['avgR']:>6.2f}  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}{marker}")


# ══════════════════════════════════════════════════════════════
# STUDY D: Initial SL Sweep
# "How much room to give before stopping out?"
# Fixed: Trail Start=2.5R, Buffer=1.0ATR, EMA=20
# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("STUDY D: Initial SL Distance Sweep")
print("=" * 60)

sl_atr_values = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
study_d_results = []

for sl_val in sl_atr_values:
    params = {'sl_atr': sl_val, 'exit_mode': 'trail', 'trail_start_r': 2.5,
              'trail_buf': 1.0, 'trail_ema_len': 20}
    agg, per_stock = run_sweep(stocks_data, params)
    if agg:
        result = {'label': f'SL {sl_val}×ATR', 'slAtr': sl_val, **agg}
        study_d_results.append(result)
        marker = ' ← CURRENT' if sl_val == 1.0 else ''
        print(f"  SL {sl_val:>4.2f}ATR:  {agg['trades']:>4} trades  WR={agg['winRate']:>5.1f}%  AvgR={agg['avgR']:>6.2f}  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}{marker}")


# ══════════════════════════════════════════════════════════════
# STUDY E: Trail EMA Length Sweep
# "How responsive should the trailing EMA be?"
# Fixed: SL=1.0ATR, Trail Start=2.5R, Buffer=1.0ATR
# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("STUDY E: Trail EMA Length Sweep")
print("=" * 60)

ema_len_values = [10, 15, 20, 30, 50]
study_e_results = []

for ema_len in ema_len_values:
    params = {'sl_atr': 1.0, 'exit_mode': 'trail', 'trail_start_r': 2.5,
              'trail_buf': 1.0, 'trail_ema_len': ema_len}
    agg, per_stock = run_sweep(stocks_data, params)
    if agg:
        result = {'label': f'EMA {ema_len}', 'trailEmaLen': ema_len, **agg}
        study_e_results.append(result)
        marker = ' ← CURRENT' if ema_len == 20 else ''
        print(f"  EMA {ema_len:>3}:     {agg['trades']:>4} trades  WR={agg['winRate']:>5.1f}%  AvgR={agg['avgR']:>6.2f}  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}{marker}")


# ══════════════════════════════════════════════════════════════
# STUDY F: HEATMAP — Trail Start R × Trail Buffer
# The interaction matrix
# Fixed: SL=1.0ATR, EMA=20
# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("STUDY F: Heatmap — Trail Start R × Trail Buffer")
print("=" * 60)

heatmap_start_values = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
heatmap_buf_values = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
heatmap_results = []

for start_r in heatmap_start_values:
    for buf in heatmap_buf_values:
        params = {'sl_atr': 1.0, 'exit_mode': 'trail', 'trail_start_r': start_r,
                  'trail_buf': buf, 'trail_ema_len': 20}
        agg, _ = run_sweep(stocks_data, params)
        if agg:
            heatmap_results.append({
                'trailStartR': start_r, 'trailBuf': buf,
                'totalPnl': agg['totalPnl'], 'winRate': agg['winRate'],
                'avgR': agg['avgR'], 'profitFactor': agg['profitFactor'],
                'trades': agg['trades'], 'maxDD': agg['maxDD'],
                'avgDuration': agg['avgDuration'],
                'stocksPositive': agg['stocksPositive']
            })

# Find the best combination
best_combo = max(heatmap_results, key=lambda x: x['totalPnl'])
print(f"\n  BEST COMBINATION: Trail Start={best_combo['trailStartR']}R, Buffer={best_combo['trailBuf']}ATR")
print(f"    P&L={best_combo['totalPnl']:,.0f}$  WR={best_combo['winRate']}%  AvgR={best_combo['avgR']}  PF={best_combo['profitFactor']}")

# Print heatmap
print(f"\n  Heatmap (Total P&L):")
print(f"  {'Buf\\Start':>10}", end='')
for s in heatmap_start_values:
    print(f"  {s:>6.1f}R", end='')
print()
for buf in heatmap_buf_values:
    print(f"  {buf:>8.2f}ATR", end='')
    for start_r in heatmap_start_values:
        match = next((h for h in heatmap_results if h['trailStartR'] == start_r and h['trailBuf'] == buf), None)
        if match:
            pnl = match['totalPnl']
            print(f"  {pnl:>7.0f}", end='')
        else:
            print(f"  {'N/A':>7}", end='')
    print()


# ══════════════════════════════════════════════════════════════
# STUDY G: Best Trail Params × SL Variants (focused test)
# Study D showed SL=0.5ATR doubled profit. Verify with best trail.
# ══════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print("STUDY G: Best Trail + SL Combinations (focused)")
print("=" * 60)

# Test the top 3 trail configs from Study F with different SL values
top_trail_configs = [
    (0.5, 0.5),   # Best from heatmap
    (1.0, 0.5),   # Second best
    (1.0, 1.0),   # Current-ish
]
sl_test_values = [0.5, 0.75, 1.0, 1.5]
heatmap_g_results = []

for sl_val in sl_test_values:
    for (start_r, buf) in top_trail_configs:
        params = {'sl_atr': sl_val, 'exit_mode': 'trail', 'trail_start_r': start_r,
                  'trail_buf': buf, 'trail_ema_len': 20}
        agg, _ = run_sweep(stocks_data, params)
        if agg:
            heatmap_g_results.append({
                'slAtr': sl_val, 'trailStartR': start_r, 'trailBuf': buf,
                'totalPnl': agg['totalPnl'], 'winRate': agg['winRate'],
                'avgR': agg['avgR'], 'profitFactor': agg['profitFactor'],
                'trades': agg['trades'], 'maxDD': agg['maxDD'],
                'stocksPositive': agg.get('stocksPositive', 0)
            })
            print(f"  SL={sl_val}ATR Trail={start_r}R Buf={buf}ATR: {agg['trades']:>4} trades  PnL={agg['totalPnl']:>9.0f}$  PF={agg['profitFactor']:>5}")

if heatmap_g_results:
    best_g = max(heatmap_g_results, key=lambda x: x['totalPnl'])
    print(f"\n  BEST OVERALL: SL={best_g['slAtr']}ATR, Trail Start={best_g['trailStartR']}R, Buffer={best_g['trailBuf']}ATR")
    print(f"    P&L={best_g['totalPnl']:,.0f}$  WR={best_g['winRate']}%  PF={best_g['profitFactor']}")


# ══════════════════════════════════════════════════════════════
# ASSEMBLE OUTPUT
# ══════════════════════════════════════════════════════════════
all_trail_combos = [r for r in heatmap_results]
best_overall = max(all_trail_combos, key=lambda x: x['totalPnl'])
best_tp = max(study_b_results, key=lambda x: x['totalPnl']) if study_b_results else None

output = {
    'studyA_trailStartR': study_a_results,
    'studyB_fixedTP': study_b_results,
    'studyC_trailBuffer': study_c_results,
    'studyD_initialSL': study_d_results,
    'studyE_emaLength': study_e_results,
    'studyF_heatmap': heatmap_results,
    'studyF_axes': {
        'startR': heatmap_start_values,
        'buffer': heatmap_buf_values,
    },
    'studyG_combined': heatmap_g_results,
    'bestTrail': best_overall,
    'bestTP': best_tp,
    'currentParams': {
        'sl_atr': 1.0,
        'trail_start_r': 2.5,
        'trail_buf': 1.0,
        'trail_ema_len': 20,
    },
    'metadata': {
        'baseStrategy': 'MA Bounce v1',
        'stocks': list(stocks_data.keys()),
        'riskPerTrade': RISK,
        'dataRange': 'Jan 2021 – Present',
        'totalParameterSets': (
            len(study_a_results) + len(study_b_results) + len(study_c_results) +
            len(study_d_results) + len(study_e_results) + len(heatmap_results) +
            len(heatmap_g_results)
        )
    }
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(output))
print(f"\n\nWritten {OUT} ({OUT.stat().st_size // 1024}KB)")
print(f"Total parameter sets tested: {output['metadata']['totalParameterSets']}")
print(f"Total parameter sets tested: {output['metadata']['totalParameterSets']}")
