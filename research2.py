#!/usr/bin/env python3
"""
Round 2: Practical optimization with minimum trade requirements.
Key insight from round 1: wider SL + better trail = fewer B2B losses + momentum riding.
But SMA 50/200 is overfit (7 trades). Need realistic trade count.

Minimum: 5 trades per stock, 30+ total.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path("/workspaces/jas/data")

def load_stock(filepath):
    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['Open','High','Low','Close'])
    return df

def load_all():
    stocks = {}
    for f in sorted(DATA_DIR.glob("*.csv")):
        name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
        stocks[name] = load_stock(f)
    return stocks

def add_indicators(df, fast_len, slow_len, atr_len=14, trail_ema_len=20):
    df = df.copy()
    df['fastSma'] = df['Close'].rolling(fast_len).mean()
    df['slowSma'] = df['Close'].rolling(slow_len).mean()
    df['tr'] = np.maximum(df['High'] - df['Low'],
        np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
    df['atr'] = df['tr'].rolling(atr_len).mean()
    df['trailEma'] = df['Close'].ewm(span=trail_ema_len, adjust=False).mean()
    df['barRange'] = df['High'] - df['Low']
    df['fastAbove'] = (df['fastSma'] > df['slowSma']).astype(int)
    df['crossUp'] = (df['fastAbove'] == 1) & (df['fastAbove'].shift(1) == 0)
    df['crossDown'] = (df['fastAbove'] == 0) & (df['fastAbove'].shift(1) == 1)
    
    # ADX
    plus_dm = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']),
                       np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    minus_dm = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)),
                        np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(atr_len).mean() / df['atr'].replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(atr_len).mean() / df['atr'].replace(0, np.nan)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    df['adx'] = dx.rolling(atr_len).mean()
    
    return df

@dataclass
class Trade:
    stock: str = ""
    entry_date: str = ""
    direction: int = 0
    entry_price: float = 0.0
    sl: float = 0.0
    risk: float = 0.0
    qty: int = 1
    exit_date: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_r: float = 0.0

@dataclass
class Cfg:
    fast_len: int = 10
    slow_len: int = 50
    max_dist_atr: float = 1.5
    max_bar_atr: float = 2.0
    sl_atr_mult: float = 1.5
    trail_ema_len: int = 20
    trail_atr_mult: float = 0.5
    trail_start_r: float = 1.0
    use_fixed_tp: bool = False
    fixed_tp_r: float = 3.0
    adx_min: float = 0.0
    risk_per_trade: float = 100.0
    # New: allow re-entry on pullback to SMA after initial cross
    allow_pullback_entry: bool = False

def backtest(df, cfg, stock_name=""):
    df = add_indicators(df, cfg.fast_len, cfg.slow_len, trail_ema_len=cfg.trail_ema_len)
    
    trades = []
    position = 0
    entry_price = 0.0
    entry_risk = 0.0
    trail_sl = 0.0
    entry_dir = 0
    last_cross_dir = 0
    bars_since_cross = 999
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        atr = row['atr']
        if pd.isna(atr) or atr <= 0:
            continue
        
        if row['crossUp']:
            last_cross_dir = 1
            bars_since_cross = 0
        elif row['crossDown']:
            last_cross_dir = -1
            bars_since_cross = 0
        else:
            bars_since_cross += 1
        
        # EXITS
        if position != 0:
            hit_sl = hit_tp = False
            exit_price = 0.0
            
            if position == 1:
                if row['Low'] <= trail_sl:
                    exit_price = trail_sl; hit_sl = True
                elif cfg.use_fixed_tp:
                    tp = entry_price + entry_risk * cfg.fixed_tp_r
                    if row['High'] >= tp:
                        exit_price = tp; hit_tp = True
                if not hit_sl and not hit_tp:
                    curr_r = (row['Close'] - entry_price) / entry_risk if entry_risk > 0 else 0
                    if curr_r >= cfg.trail_start_r:
                        et = row['trailEma'] - cfg.trail_atr_mult * atr
                        if et > trail_sl: trail_sl = et
                # Opposite cross = close
                if not hit_sl and not hit_tp and last_cross_dir == -1 and bars_since_cross == 0:
                    exit_price = row['Close']; hit_sl = True  # treat as exit
                    
            elif position == -1:
                if row['High'] >= trail_sl:
                    exit_price = trail_sl; hit_sl = True
                elif cfg.use_fixed_tp:
                    tp = entry_price - entry_risk * cfg.fixed_tp_r
                    if row['Low'] <= tp:
                        exit_price = tp; hit_tp = True
                if not hit_sl and not hit_tp:
                    curr_r = (entry_price - row['Close']) / entry_risk if entry_risk > 0 else 0
                    if curr_r >= cfg.trail_start_r:
                        et = row['trailEma'] + cfg.trail_atr_mult * atr
                        if et < trail_sl: trail_sl = et
                if not hit_sl and not hit_tp and last_cross_dir == 1 and bars_since_cross == 0:
                    exit_price = row['Close']; hit_sl = True
            
            if hit_sl or hit_tp:
                t = trades[-1]
                t.exit_date = str(row['Date'].date())
                t.exit_price = exit_price
                t.exit_reason = "TP" if hit_tp else "SL/Cross"
                t.pnl_r = ((exit_price - entry_price) / entry_risk if position == 1 
                           else (entry_price - exit_price) / entry_risk) if entry_risk > 0 else 0
                position = 0
        
        # ENTRIES
        if position == 0:
            is_cross_long = (last_cross_dir == 1 and bars_since_cross == 0)
            is_cross_short = (last_cross_dir == -1 and bars_since_cross == 0)
            
            # Pullback entry: price was on right side of fast SMA but pulled back near it
            if cfg.allow_pullback_entry and not is_cross_long and not is_cross_short:
                if last_cross_dir == 1 and bars_since_cross <= 10:
                    # Long pullback: price dipped to within 0.5 ATR of fast SMA and bounced
                    if (row['Low'] <= row['fastSma'] + 0.5 * atr and 
                        row['Close'] > row['fastSma'] and 
                        row['Close'] > row['Open']):  # green candle
                        is_cross_long = True
                elif last_cross_dir == -1 and bars_since_cross <= 10:
                    if (row['High'] >= row['fastSma'] - 0.5 * atr and
                        row['Close'] < row['fastSma'] and
                        row['Close'] < row['Open']):  # red candle
                        is_cross_short = True
            
            dist_ok = abs(row['Close'] - row['fastSma']) <= cfg.max_dist_atr * atr
            bar_ok = row['barRange'] <= cfg.max_bar_atr * atr
            adx_ok = cfg.adx_min <= 0 or (not pd.isna(row.get('adx', np.nan)) and row['adx'] >= cfg.adx_min)
            
            can_enter = dist_ok and bar_ok and adx_ok
            
            if can_enter and is_cross_long:
                sl = row['Close'] - cfg.sl_atr_mult * atr
                risk = row['Close'] - sl
                position = 1; entry_price = row['Close']; entry_risk = risk; trail_sl = sl
                trades.append(Trade(stock=stock_name, entry_date=str(row['Date'].date()),
                    direction=1, entry_price=row['Close'], sl=sl, risk=risk))
                    
            elif can_enter and is_cross_short:
                sl = row['Close'] + cfg.sl_atr_mult * atr
                risk = sl - row['Close']
                position = -1; entry_price = row['Close']; entry_risk = risk; trail_sl = sl
                trades.append(Trade(stock=stock_name, entry_date=str(row['Date'].date()),
                    direction=-1, entry_price=row['Close'], sl=sl, risk=risk))
    
    # Close open
    if position != 0 and trades:
        t = trades[-1]
        last = df.iloc[-1]
        t.exit_date = str(last['Date'].date())
        t.exit_price = last['Close']
        t.exit_reason = "EOD"
        t.pnl_r = ((last['Close'] - entry_price) / entry_risk if position == 1 
                   else (entry_price - last['Close']) / entry_risk) if entry_risk > 0 else 0
    
    return trades

def metrics(trades):
    if not trades:
        return {'n': 0, 'wr': 0, 'total_r': 0, 'max_dd': 0, 'consec': 0, 'b2b': 0, 'pf': 0, 'calmar': 0, 'avg_win': 0, 'avg_loss': 0}
    pnls = [t.pnl_r for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    cumul = np.cumsum(pnls)
    dd = (np.maximum.accumulate(cumul) - cumul).max() if len(cumul) > 0 else 0
    
    mc = cc = b2b = 0
    for p in pnls:
        if p <= 0:
            cc += 1
            if cc >= 2: b2b += 1
            mc = max(mc, cc)
        else: cc = 0
    
    tw = sum(wins) if wins else 0
    tl = abs(sum(losses)) if losses else 0.001
    tr = sum(pnls)
    
    return {
        'n': len(trades), 'wr': len(wins)/len(trades)*100, 'total_r': round(tr,2),
        'max_dd': round(dd,2), 'consec': mc, 'b2b': b2b, 'pf': round(tw/tl,2),
        'calmar': round(tr/dd if dd > 0 else tr, 2),
        'avg_win': round(np.mean(wins),2) if wins else 0,
        'avg_loss': round(np.mean(losses),2) if losses else 0
    }

def run_all(stocks, cfg, label=""):
    all_trades = []
    per = {}
    min_per_stock = True
    for name, df in stocks.items():
        trades = backtest(df, cfg, name)
        per[name] = metrics(trades)
        if per[name]['n'] < 3:  # need at least 3 trades per stock
            min_per_stock = False
        all_trades.extend(trades)
    m = metrics(all_trades)
    m['label'] = label
    m['all_have_trades'] = min_per_stock
    return m, per, all_trades

def fmt(m, indent=""):
    flag = " ✓" if m.get('all_have_trades') else " ✗"
    return (f"{indent}{m.get('label','')}: {m['n']}t | WR {m['wr']:.0f}% | "
            f"{m['total_r']:+.1f}R | DD {m['max_dd']:.1f}R | "
            f"CL {m['consec']} | B2B {m['b2b']} | PF {m['pf']:.2f} | "
            f"Cal {m['calmar']:.2f} | AvgW {m['avg_win']:.1f} AvgL {m['avg_loss']:.1f}{flag}")

# ============================================================

stocks = load_all()
print(f"Loaded {len(stocks)} stocks\n")

# Score function: balance return, drawdown, B2B losses
# Penalize heavily for B2B and drawdown
def score(m):
    if m['n'] < 25:  # need reasonable sample
        return -999
    if not m.get('all_have_trades', False):
        return -998
    # Calmar (return/DD) - penalize B2B - bonus for high win rate
    return m['calmar'] - 0.15 * m['b2b'] + 0.02 * m['wr']

# ============================================================
# SWEEP: All practical combinations
# ============================================================

print("=" * 100)
print("COMPREHENSIVE SWEEP (minimum 25 trades, 3+ per stock)")
print("=" * 100)

results = []

sma_pairs = [(5,20), (5,50), (10,30), (10,50), (10,100), (20,50), (20,100), (20,200)]
sl_mults = [1.5, 2.0, 2.5]
trail_cfgs = [
    (10, 0.5, 1.0), (10, 1.0, 1.0), (10, 1.0, 1.5),
    (20, 0.5, 1.0), (20, 1.0, 1.5), (30, 1.0, 1.5)
]
bar_filters = [2.0, 3.0, 99.0]  # 99 = off
dist_filters = [1.5, 3.0, 99.0]
tp_configs = [(False, 0), (True, 3.0), (True, 5.0)]
adx_vals = [0, 20]

total_combos = len(sma_pairs) * len(sl_mults) * len(trail_cfgs) * len(bar_filters) * len(dist_filters) * len(tp_configs) * len(adx_vals)
print(f"Testing {total_combos} combinations...\n")

best_score = -999
best_cfg = None
best_m = None
count = 0

for fast, slow in sma_pairs:
    for sl in sl_mults:
        for tl, tb, tsr in trail_cfgs:
            for mb in bar_filters:
                for md in dist_filters:
                    for use_tp, tp_r in tp_configs:
                        for adx in adx_vals:
                            cfg = Cfg(
                                fast_len=fast, slow_len=slow, sl_atr_mult=sl,
                                trail_ema_len=tl, trail_atr_mult=tb, trail_start_r=tsr,
                                max_bar_atr=mb, max_dist_atr=md,
                                use_fixed_tp=use_tp, fixed_tp_r=tp_r, adx_min=adx
                            )
                            m, per, _ = run_all(stocks, cfg, f"SMA{fast}/{slow} SL{sl} T{tl}/{tb}/{tsr} B{mb} D{md} TP{'t' if not use_tp else str(tp_r)} ADX{adx}")
                            s = score(m)
                            count += 1
                            
                            if s > best_score:
                                best_score = s
                                best_cfg = cfg
                                best_m = m
                                best_per = per
                                print(f"[{count}/{total_combos}] NEW BEST (score={s:.2f}):")
                                print(f"  {fmt(m)}")

print(f"\nTested {count} combinations.")

# ============================================================
# Also test pullback entry on top configs
# ============================================================

print("\n" + "=" * 100)
print("TESTING PULLBACK ENTRY on best config")
print("=" * 100)

cfg_pb = Cfg(**{**best_cfg.__dict__, 'allow_pullback_entry': True})
m_pb, per_pb, _ = run_all(stocks, cfg_pb, "BEST + Pullback")
print(fmt(m_pb))
print(f"  vs without: {fmt(best_m)}")

if score(m_pb) > best_score:
    best_cfg = cfg_pb
    best_m = m_pb
    best_per = per_pb
    print("  >>> Pullback entry is BETTER")
else:
    print("  >>> Pullback entry did NOT improve")

# ============================================================
# FINAL RESULTS
# ============================================================

print("\n" + "=" * 100)
print("FINAL OPTIMAL (PRACTICAL)")
print("=" * 100)

print(f"\nSettings:")
print(f"  SMA: {best_cfg.fast_len}/{best_cfg.slow_len}")
print(f"  SL: {best_cfg.sl_atr_mult}×ATR")
print(f"  Trail EMA: {best_cfg.trail_ema_len}, buffer: {best_cfg.trail_atr_mult}×ATR, starts: {best_cfg.trail_start_r}R")
print(f"  Big candle filter: {best_cfg.max_bar_atr}×ATR {'(off)' if best_cfg.max_bar_atr >= 50 else ''}")
print(f"  Distance filter: {best_cfg.max_dist_atr}×ATR {'(off)' if best_cfg.max_dist_atr >= 50 else ''}")
print(f"  ADX min: {best_cfg.adx_min} {'(off)' if best_cfg.adx_min == 0 else ''}")
print(f"  TP: {'Fixed ' + str(best_cfg.fixed_tp_r) + 'R' if best_cfg.use_fixed_tp else 'Pure Trail'}")
print(f"  Pullback entry: {best_cfg.allow_pullback_entry}")

print(f"\nCombined: {fmt(best_m)}")
print(f"\nPer-stock breakdown:")
for name in sorted(best_per.keys()):
    p = best_per[name]
    print(f"  {name:6s}: {p['n']:2d}t | WR {p['wr']:.0f}% | {p['total_r']:+.1f}R | DD {p['max_dd']:.1f}R | B2B {p['b2b']} | AvgW {p['avg_win']:.1f} AvgL {p['avg_loss']:.1f}")

# Show trade-by-trade for the best config
print(f"\n--- Individual trades ---")
_, _, all_trades = run_all(stocks, best_cfg, "FINAL")
all_trades.sort(key=lambda t: t.entry_date)
for t in all_trades:
    dir_str = "LONG " if t.direction == 1 else "SHORT"
    print(f"  {t.stock:6s} {t.entry_date} {dir_str} @{t.entry_price:.2f} → "
          f"{t.exit_date} @{t.exit_price:.2f} [{t.exit_reason:8s}] {t.pnl_r:+.2f}R")

# ============================================================
# BASELINE COMPARISON
# ============================================================

print(f"\n" + "=" * 100)
print("BASELINE vs OPTIMAL COMPARISON")
print("=" * 100)

baseline = Cfg()  # current pine_orb defaults
m_base, per_base, _ = run_all(stocks, baseline, "BASELINE (current)")
print(fmt(m_base))
print(fmt(best_m))

print(f"\n  Total R: {m_base['total_r']:+.1f} → {best_m['total_r']:+.1f}")
print(f"  Max DD:  {m_base['max_dd']:.1f}R → {best_m['max_dd']:.1f}R")
print(f"  B2B SL:  {m_base['b2b']} → {best_m['b2b']}")
print(f"  Win Rate: {m_base['wr']:.0f}% → {best_m['wr']:.0f}%")
print(f"  Calmar:  {m_base['calmar']:.2f} → {best_m['calmar']:.2f}")
print(f"  Avg Win: {m_base['avg_win']:.1f}R → {best_m['avg_win']:.1f}R")
print(f"  Avg Loss: {m_base['avg_loss']:.1f}R → {best_m['avg_loss']:.1f}R")

print(f"\nPer-stock:")
for name in sorted(per_base.keys()):
    b = per_base[name]
    o = best_per[name]
    print(f"  {name:6s}: {b['total_r']:+5.1f}R → {o['total_r']:+5.1f}R | "
          f"DD {b['max_dd']:4.1f}→{o['max_dd']:4.1f} | "
          f"B2B {b['b2b']:2d}→{o['b2b']:2d} | "
          f"WR {b['wr']:.0f}%→{o['wr']:.0f}%")
