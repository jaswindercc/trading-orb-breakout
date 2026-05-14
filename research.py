#!/usr/bin/env python3
"""
Deep research: multi-stock SMA crossover strategy optimization.
Tests current pine_orb v3 logic + variations across all 7 stocks.
Focus: fewer back-to-back SLs, less drawdown, ride momentum.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product
from dataclasses import dataclass, field
from typing import List, Tuple
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# DATA LOADING
# ============================================================

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
        print(f"  {name}: {len(stocks[name])} bars, price range ${stocks[name]['Close'].min():.2f}-${stocks[name]['Close'].max():.2f}")
    return stocks

# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df, fast_len, slow_len, atr_len=14, trail_ema_len=20):
    df = df.copy()
    df['fastSma'] = df['Close'].rolling(fast_len).mean()
    df['slowSma'] = df['Close'].rolling(slow_len).mean()
    
    # ATR
    df['tr'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift(1)),
            abs(df['Low'] - df['Close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(atr_len).mean()
    
    # Trail EMA
    df['trailEma'] = df['Close'].ewm(span=trail_ema_len, adjust=False).mean()
    
    # Bar range
    df['barRange'] = df['High'] - df['Low']
    
    # Day of week (0=Mon, 4=Fri)
    df['dow'] = df['Date'].dt.dayofweek
    
    # Week number for grouping
    df['week'] = df['Date'].dt.isocalendar().week.astype(int)
    df['year'] = df['Date'].dt.year
    
    # SMA cross detection
    df['fastAbove'] = (df['fastSma'] > df['slowSma']).astype(int)
    df['crossUp'] = (df['fastAbove'] == 1) & (df['fastAbove'].shift(1) == 0)
    df['crossDown'] = (df['fastAbove'] == 0) & (df['fastAbove'].shift(1) == 1)
    
    # ADX (trend strength) - simplified using directional movement
    plus_dm = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']),
                       np.maximum(df['High'] - df['High'].shift(1), 0), 0)
    minus_dm = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)),
                        np.maximum(df['Low'].shift(1) - df['Low'], 0), 0)
    
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).rolling(atr_len).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).rolling(atr_len).mean()
    
    plus_di = 100 * plus_dm_smooth / df['atr'].replace(0, np.nan)
    minus_di = 100 * minus_dm_smooth / df['atr'].replace(0, np.nan)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
    df['adx'] = dx.rolling(atr_len).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Volume SMA for volume filter
    df['volSma'] = df['Volume'].rolling(20).mean()
    df['relVol'] = df['Volume'] / df['volSma'].replace(0, np.nan)
    
    return df

# ============================================================
# BACKTEST ENGINE
# ============================================================

@dataclass
class Trade:
    entry_date: str
    direction: int  # 1=long, -1=short
    entry_price: float
    sl: float
    risk: float
    qty: int
    exit_date: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_r: float = 0.0
    pnl_dollar: float = 0.0

@dataclass 
class BacktestConfig:
    # SMA
    fast_len: int = 10
    slow_len: int = 50
    # Entry filters
    max_dist_atr: float = 1.5
    max_bar_atr: float = 2.0
    adx_min: float = 0.0          # Min ADX for entry (0=off)
    rsi_long_max: float = 100.0   # Max RSI for long entry (avoid overbought)
    rsi_short_min: float = 0.0    # Min RSI for short entry (avoid oversold)
    vol_min: float = 0.0          # Min relative volume (0=off)
    # Stops
    sl_atr_mult: float = 1.5
    # Trailing
    trail_ema_len: int = 20
    trail_atr_mult: float = 0.5
    trail_start_r: float = 1.0
    # Exit
    use_fixed_tp: bool = False
    fixed_tp_r: float = 3.0       # Fixed TP in R (if use_fixed_tp)
    # Other
    risk_per_trade: float = 100.0
    # Trend alignment
    require_trend_align: bool = False  # Require price on right side of slow SMA
    # Re-entry after cross
    allow_late_entry: bool = False     # Allow entry N bars after cross
    late_entry_bars: int = 3

def backtest(df, cfg: BacktestConfig):
    df = add_indicators(df, cfg.fast_len, cfg.slow_len, trail_ema_len=cfg.trail_ema_len)
    
    trades = []
    position = 0  # 0=flat, 1=long, -1=short
    entry_price = 0.0
    entry_risk = 0.0
    trail_sl = 0.0
    entry_dir = 0
    last_cross_dir = 0
    bars_since_cross = 999
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Track crossovers
        if row['crossUp']:
            last_cross_dir = 1
            bars_since_cross = 0
        elif row['crossDown']:
            last_cross_dir = -1
            bars_since_cross = 0
        else:
            bars_since_cross += 1
        
        atr = row['atr']
        if pd.isna(atr) or atr <= 0:
            continue
        
        # ---- CHECK EXITS FIRST ----
        if position != 0:
            hit_sl = False
            hit_tp = False
            
            if position == 1:  # Long
                # Check if SL hit during bar
                if row['Low'] <= trail_sl:
                    exit_price = trail_sl
                    hit_sl = True
                # Check fixed TP
                elif cfg.use_fixed_tp:
                    tp = entry_price + entry_risk * cfg.fixed_tp_r
                    if row['High'] >= tp:
                        exit_price = tp
                        hit_tp = True
                
                if not hit_sl and not hit_tp:
                    # Update trailing stop
                    curr_pnl = row['Close'] - entry_price
                    curr_r = curr_pnl / entry_risk if entry_risk > 0 else 0
                    if curr_r >= cfg.trail_start_r:
                        ema_trail = row['trailEma'] - cfg.trail_atr_mult * atr
                        if ema_trail > trail_sl:
                            trail_sl = ema_trail
                            
            elif position == -1:  # Short
                if row['High'] >= trail_sl:
                    exit_price = trail_sl
                    hit_sl = True
                elif cfg.use_fixed_tp:
                    tp = entry_price - entry_risk * cfg.fixed_tp_r
                    if row['Low'] <= tp:
                        exit_price = tp
                        hit_tp = True
                
                if not hit_sl and not hit_tp:
                    curr_pnl = entry_price - row['Close']
                    curr_r = curr_pnl / entry_risk if entry_risk > 0 else 0
                    if curr_r >= cfg.trail_start_r:
                        ema_trail = row['trailEma'] + cfg.trail_atr_mult * atr
                        if ema_trail < trail_sl:
                            trail_sl = ema_trail
            
            if hit_sl or hit_tp:
                t = trades[-1]
                t.exit_date = str(row['Date'].date())
                t.exit_price = exit_price
                t.exit_reason = "TP" if hit_tp else "SL"
                if position == 1:
                    t.pnl_r = (exit_price - entry_price) / entry_risk if entry_risk > 0 else 0
                else:
                    t.pnl_r = (entry_price - exit_price) / entry_risk if entry_risk > 0 else 0
                t.pnl_dollar = t.pnl_r * cfg.risk_per_trade
                position = 0
                entry_dir = 0
        
        # ---- CHECK ENTRIES ----
        if position == 0:
            # Fresh cross signal
            is_fresh_cross_long = (last_cross_dir == 1 and bars_since_cross == 0)
            is_fresh_cross_short = (last_cross_dir == -1 and bars_since_cross == 0)
            
            # Late entry (within N bars of cross)
            if cfg.allow_late_entry:
                is_fresh_cross_long = is_fresh_cross_long or (last_cross_dir == 1 and bars_since_cross <= cfg.late_entry_bars)
                is_fresh_cross_short = is_fresh_cross_short or (last_cross_dir == -1 and bars_since_cross <= cfg.late_entry_bars)
            
            # Distance filter
            dist_ok = abs(row['Close'] - row['fastSma']) <= cfg.max_dist_atr * atr
            
            # Big candle filter
            bar_ok = row['barRange'] <= cfg.max_bar_atr * atr
            
            # ADX filter
            adx_ok = cfg.adx_min <= 0 or (not pd.isna(row['adx']) and row['adx'] >= cfg.adx_min)
            
            # Volume filter
            vol_ok = cfg.vol_min <= 0 or (not pd.isna(row['relVol']) and row['relVol'] >= cfg.vol_min)
            
            # Trend alignment filter
            trend_ok = True
            if cfg.require_trend_align:
                if is_fresh_cross_long:
                    trend_ok = row['Close'] > row['slowSma']
                elif is_fresh_cross_short:
                    trend_ok = row['Close'] < row['slowSma']
            
            # RSI filter
            rsi_ok = True
            if not pd.isna(row.get('rsi', np.nan)):
                if is_fresh_cross_long and row['rsi'] > cfg.rsi_long_max:
                    rsi_ok = False
                if is_fresh_cross_short and row['rsi'] < cfg.rsi_short_min:
                    rsi_ok = False
            
            can_enter = dist_ok and bar_ok and adx_ok and vol_ok and trend_ok and rsi_ok
            
            if can_enter and is_fresh_cross_long:
                sl = row['Close'] - cfg.sl_atr_mult * atr
                risk = row['Close'] - sl
                qty = max(1, round(cfg.risk_per_trade / risk)) if risk > 0 else 1
                
                position = 1
                entry_price = row['Close']
                entry_risk = risk
                entry_dir = 1
                trail_sl = sl
                
                trades.append(Trade(
                    entry_date=str(row['Date'].date()),
                    direction=1,
                    entry_price=row['Close'],
                    sl=sl, risk=risk, qty=qty
                ))
                
            elif can_enter and is_fresh_cross_short:
                sl = row['Close'] + cfg.sl_atr_mult * atr
                risk = sl - row['Close']
                qty = max(1, round(cfg.risk_per_trade / risk)) if risk > 0 else 1
                
                position = -1
                entry_price = row['Close']
                entry_risk = risk
                entry_dir = -1
                trail_sl = sl
                
                trades.append(Trade(
                    entry_date=str(row['Date'].date()),
                    direction=-1,
                    entry_price=row['Close'],
                    sl=sl, risk=risk, qty=qty
                ))
    
    # Close any open position at last bar
    if position != 0 and trades:
        t = trades[-1]
        last = df.iloc[-1]
        t.exit_date = str(last['Date'].date())
        t.exit_price = last['Close']
        t.exit_reason = "EOD"
        if position == 1:
            t.pnl_r = (last['Close'] - entry_price) / entry_risk if entry_risk > 0 else 0
        else:
            t.pnl_r = (entry_price - last['Close']) / entry_risk if entry_risk > 0 else 0
        t.pnl_dollar = t.pnl_r * cfg.risk_per_trade
    
    return trades

# ============================================================
# METRICS
# ============================================================

def calc_metrics(trades: List[Trade], label=""):
    if not trades:
        return {
            'label': label, 'trades': 0, 'win_rate': 0, 'total_r': 0,
            'avg_r': 0, 'max_dd_r': 0, 'max_consec_loss': 0,
            'profit_factor': 0, 'avg_win_r': 0, 'avg_loss_r': 0,
            'calmar': 0, 'back2back_sl': 0
        }
    
    pnls = [t.pnl_r for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    # Max drawdown in R
    cumulative = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumulative)
    drawdown = peak - cumulative
    max_dd = drawdown.max() if len(drawdown) > 0 else 0
    
    # Consecutive losses
    max_consec = 0
    curr_consec = 0
    back2back_count = 0
    for i, p in enumerate(pnls):
        if p <= 0:
            curr_consec += 1
            if curr_consec >= 2:
                back2back_count += 1
            max_consec = max(max_consec, curr_consec)
        else:
            curr_consec = 0
    
    total_win = sum(wins) if wins else 0
    total_loss = abs(sum(losses)) if losses else 0.001
    
    total_r = sum(pnls)
    calmar = total_r / max_dd if max_dd > 0 else total_r
    
    return {
        'label': label,
        'trades': len(trades),
        'win_rate': len(wins) / len(trades) * 100,
        'total_r': round(total_r, 2),
        'avg_r': round(np.mean(pnls), 3),
        'max_dd_r': round(max_dd, 2),
        'max_consec_loss': max_consec,
        'back2back_sl': back2back_count,
        'profit_factor': round(total_win / total_loss, 2),
        'avg_win_r': round(np.mean(wins), 2) if wins else 0,
        'avg_loss_r': round(np.mean(losses), 2) if losses else 0,
        'calmar': round(calmar, 2)
    }

def print_metrics(m, indent=""):
    print(f"{indent}{m['label']}: {m['trades']} trades | WR {m['win_rate']:.0f}% | "
          f"Total {m['total_r']:+.1f}R | MaxDD {m['max_dd_r']:.1f}R | "
          f"ConsecL {m['max_consec_loss']} | B2B_SL {m['back2back_sl']} | "
          f"PF {m['profit_factor']:.2f} | Calmar {m['calmar']:.2f}")

# ============================================================
# RESEARCH
# ============================================================

def run_across_stocks(stocks, cfg, label=""):
    all_trades = []
    per_stock = {}
    for name, df in stocks.items():
        trades = backtest(df, cfg)
        per_stock[name] = calc_metrics(trades, name)
        all_trades.extend(trades)
    combined = calc_metrics(all_trades, label or "COMBINED")
    return combined, per_stock

def print_comparison(combined, per_stock):
    print_metrics(combined)
    for name in sorted(per_stock.keys()):
        print_metrics(per_stock[name], indent="    ")
    print()

print("=" * 80)
print("LOADING DATA")
print("=" * 80)
stocks = load_all()

# ============================================================
# PHASE 1: Current strategy baseline
# ============================================================

print("\n" + "=" * 80)
print("PHASE 1: CURRENT STRATEGY (SMA 10/50, ATR SL, EMA trail)")
print("=" * 80)

baseline_cfg = BacktestConfig()
combined, per_stock = run_across_stocks(stocks, baseline_cfg, "BASELINE")
print_comparison(combined, per_stock)

# ============================================================
# PHASE 2: SMA length variations
# ============================================================

print("=" * 80)
print("PHASE 2: SMA LENGTH OPTIMIZATION")
print("=" * 80)

best_sma = None
best_calmar = -999

for fast, slow in [(5, 20), (5, 50), (10, 30), (10, 50), (10, 100), (20, 50), (20, 100), (20, 200), (50, 200)]:
    cfg = BacktestConfig(fast_len=fast, slow_len=slow)
    combined, _ = run_across_stocks(stocks, cfg, f"SMA {fast}/{slow}")
    print_metrics(combined)
    # Score: prioritize calmar (return/drawdown) and penalize back-to-back losses
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_calmar:
        best_calmar = score
        best_sma = (fast, slow)

print(f"\n>>> Best SMA: {best_sma[0]}/{best_sma[1]} (score={best_calmar:.2f})")

# ============================================================
# PHASE 3: Stop loss multiplier
# ============================================================

print("\n" + "=" * 80)
print("PHASE 3: STOP LOSS ATR MULTIPLIER")
print("=" * 80)

best_sl = None
best_score = -999

for sl_mult in [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
    cfg = BacktestConfig(fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=sl_mult)
    combined, _ = run_across_stocks(stocks, cfg, f"SL {sl_mult}×ATR")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_sl = sl_mult

print(f"\n>>> Best SL: {best_sl}×ATR")

# ============================================================
# PHASE 4: Trail EMA + buffer + activation
# ============================================================

print("\n" + "=" * 80)
print("PHASE 4: TRAILING STOP OPTIMIZATION")
print("=" * 80)

best_trail = None
best_score = -999

for ema_len in [10, 20, 30]:
    for buf in [0.0, 0.25, 0.5, 1.0]:
        for start_r in [0.5, 1.0, 1.5, 2.0]:
            cfg = BacktestConfig(
                fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
                trail_ema_len=ema_len, trail_atr_mult=buf, trail_start_r=start_r
            )
            combined, _ = run_across_stocks(stocks, cfg, f"Trail EMA{ema_len} buf{buf} @{start_r}R")
            score = combined['calmar'] - 0.1 * combined['back2back_sl']
            if score > best_score:
                best_score = score
                best_trail = (ema_len, buf, start_r)
                print_metrics(combined, "  NEW BEST: ")

print(f"\n>>> Best trail: EMA {best_trail[0]}, buffer {best_trail[1]}×ATR, starts at {best_trail[2]}R")

# ============================================================
# PHASE 5: Big candle filter
# ============================================================

print("\n" + "=" * 80)
print("PHASE 5: BIG CANDLE FILTER")
print("=" * 80)

best_bar = None
best_score = -999

for max_bar in [1.5, 2.0, 2.5, 3.0, 5.0, 99.0]:
    cfg = BacktestConfig(
        fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
        trail_ema_len=best_trail[0], trail_atr_mult=best_trail[1], trail_start_r=best_trail[2],
        max_bar_atr=max_bar
    )
    combined, _ = run_across_stocks(stocks, cfg, f"MaxBar {max_bar}×ATR")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_bar = max_bar

print(f"\n>>> Best big candle filter: {best_bar}×ATR")

# ============================================================
# PHASE 6: Distance filter
# ============================================================

print("\n" + "=" * 80)
print("PHASE 6: MAX DISTANCE FROM FAST SMA")
print("=" * 80)

best_dist = None
best_score = -999

for dist in [1.0, 1.5, 2.0, 3.0, 5.0, 99.0]:
    cfg = BacktestConfig(
        fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
        trail_ema_len=best_trail[0], trail_atr_mult=best_trail[1], trail_start_r=best_trail[2],
        max_bar_atr=best_bar, max_dist_atr=dist
    )
    combined, _ = run_across_stocks(stocks, cfg, f"MaxDist {dist}×ATR")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_dist = dist

print(f"\n>>> Best distance filter: {best_dist}×ATR")

# ============================================================
# PHASE 7: Additional filters (ADX, RSI, Volume, Trend align)
# ============================================================

print("\n" + "=" * 80)
print("PHASE 7: ADDITIONAL FILTERS")
print("=" * 80)

base_cfg = BacktestConfig(
    fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
    trail_ema_len=best_trail[0], trail_atr_mult=best_trail[1], trail_start_r=best_trail[2],
    max_bar_atr=best_bar, max_dist_atr=best_dist
)

# Test ADX
print("--- ADX Filter ---")
best_adx = 0
best_score = -999
for adx_min in [0, 15, 20, 25, 30]:
    cfg = BacktestConfig(**{**base_cfg.__dict__, 'adx_min': adx_min})
    combined, _ = run_across_stocks(stocks, cfg, f"ADX>={adx_min}")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_adx = adx_min

print(f">>> Best ADX: {best_adx}")

# Test RSI
print("\n--- RSI Filter ---")
best_rsi = (100, 0)
best_score = -999
for rsi_max, rsi_min in [(100, 0), (80, 20), (75, 25), (70, 30)]:
    cfg = BacktestConfig(**{**base_cfg.__dict__, 'adx_min': best_adx, 'rsi_long_max': rsi_max, 'rsi_short_min': rsi_min})
    combined, _ = run_across_stocks(stocks, cfg, f"RSI L<{rsi_max} S>{rsi_min}")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_rsi = (rsi_max, rsi_min)

print(f">>> Best RSI: long<{best_rsi[0]}, short>{best_rsi[1]}")

# Test Volume
print("\n--- Volume Filter ---")
best_vol = 0
best_score = -999
for vol_min in [0, 0.8, 1.0, 1.2, 1.5]:
    cfg = BacktestConfig(**{**base_cfg.__dict__, 'adx_min': best_adx, 
                            'rsi_long_max': best_rsi[0], 'rsi_short_min': best_rsi[1],
                            'vol_min': vol_min})
    combined, _ = run_across_stocks(stocks, cfg, f"Vol>={vol_min}")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_vol = vol_min

print(f">>> Best Volume: {best_vol}")

# Test Trend alignment
print("\n--- Trend Alignment ---")
best_trend = False
best_score = -999
for trend in [False, True]:
    cfg = BacktestConfig(**{**base_cfg.__dict__, 'adx_min': best_adx, 
                            'rsi_long_max': best_rsi[0], 'rsi_short_min': best_rsi[1],
                            'vol_min': best_vol, 'require_trend_align': trend})
    combined, _ = run_across_stocks(stocks, cfg, f"TrendAlign={trend}")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_trend = trend

print(f">>> Best Trend Align: {best_trend}")

# ============================================================
# PHASE 8: Fixed TP vs pure trail
# ============================================================

print("\n" + "=" * 80)
print("PHASE 8: FIXED TP vs PURE TRAIL")
print("=" * 80)

best_tp = (False, 0)
best_score = -999

for use_tp, tp_r in [(False, 0), (True, 2.0), (True, 3.0), (True, 4.0), (True, 5.0)]:
    cfg = BacktestConfig(
        fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
        trail_ema_len=best_trail[0], trail_atr_mult=best_trail[1], trail_start_r=best_trail[2],
        max_bar_atr=best_bar, max_dist_atr=best_dist,
        adx_min=best_adx, rsi_long_max=best_rsi[0], rsi_short_min=best_rsi[1],
        vol_min=best_vol, require_trend_align=best_trend,
        use_fixed_tp=use_tp, fixed_tp_r=tp_r
    )
    combined, _ = run_across_stocks(stocks, cfg, f"TP={'trail' if not use_tp else str(tp_r)+'R'}")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_tp = (use_tp, tp_r)

print(f"\n>>> Best TP: {'Fixed ' + str(best_tp[1]) + 'R' if best_tp[0] else 'Pure Trail'}")

# ============================================================
# PHASE 9: Late entry (allow entry within N bars of cross)
# ============================================================

print("\n" + "=" * 80)
print("PHASE 9: LATE ENTRY WINDOW")
print("=" * 80)

best_late = (False, 0)
best_score = -999

for allow, bars in [(False, 0), (True, 1), (True, 2), (True, 3), (True, 5)]:
    cfg = BacktestConfig(
        fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
        trail_ema_len=best_trail[0], trail_atr_mult=best_trail[1], trail_start_r=best_trail[2],
        max_bar_atr=best_bar, max_dist_atr=best_dist,
        adx_min=best_adx, rsi_long_max=best_rsi[0], rsi_short_min=best_rsi[1],
        vol_min=best_vol, require_trend_align=best_trend,
        use_fixed_tp=best_tp[0], fixed_tp_r=best_tp[1],
        allow_late_entry=allow, late_entry_bars=bars
    )
    combined, _ = run_across_stocks(stocks, cfg, f"Late={'off' if not allow else str(bars)+'bars'}")
    print_metrics(combined)
    score = combined['calmar'] - 0.1 * combined['back2back_sl']
    if score > best_score:
        best_score = score
        best_late = (allow, bars)

print(f"\n>>> Best late entry: {'Off' if not best_late[0] else str(best_late[1]) + ' bars'}")

# ============================================================
# FINAL: Optimal config with full per-stock breakdown
# ============================================================

print("\n" + "=" * 80)
print("FINAL OPTIMAL CONFIGURATION")
print("=" * 80)

optimal = BacktestConfig(
    fast_len=best_sma[0], slow_len=best_sma[1], sl_atr_mult=best_sl,
    trail_ema_len=best_trail[0], trail_atr_mult=best_trail[1], trail_start_r=best_trail[2],
    max_bar_atr=best_bar, max_dist_atr=best_dist,
    adx_min=best_adx, rsi_long_max=best_rsi[0], rsi_short_min=best_rsi[1],
    vol_min=best_vol, require_trend_align=best_trend,
    use_fixed_tp=best_tp[0], fixed_tp_r=best_tp[1],
    allow_late_entry=best_late[0], late_entry_bars=best_late[1]
)

print(f"\nSettings:")
print(f"  SMA: {optimal.fast_len}/{optimal.slow_len}")
print(f"  SL: {optimal.sl_atr_mult}×ATR")
print(f"  Trail EMA: {optimal.trail_ema_len}, buffer: {optimal.trail_atr_mult}×ATR, starts: {optimal.trail_start_r}R")
print(f"  Big candle filter: {optimal.max_bar_atr}×ATR")
print(f"  Distance filter: {optimal.max_dist_atr}×ATR")
print(f"  ADX min: {optimal.adx_min}")
print(f"  RSI long max: {optimal.rsi_long_max}, short min: {optimal.rsi_short_min}")
print(f"  Volume min: {optimal.vol_min}")
print(f"  Trend alignment: {optimal.require_trend_align}")
print(f"  TP: {'Fixed ' + str(optimal.fixed_tp_r) + 'R' if optimal.use_fixed_tp else 'Pure Trail'}")
print(f"  Late entry: {'Off' if not optimal.allow_late_entry else str(optimal.late_entry_bars) + ' bars'}")

print(f"\nResults:")
combined, per_stock = run_across_stocks(stocks, optimal, "OPTIMAL")
print_comparison(combined, per_stock)

# Compare vs baseline
print("--- BASELINE vs OPTIMAL ---")
baseline_combined, baseline_per = run_across_stocks(stocks, baseline_cfg, "BASELINE")
print_metrics(baseline_combined)
print_metrics(combined)

print(f"\nImprovement:")
print(f"  Total R: {baseline_combined['total_r']:+.1f} → {combined['total_r']:+.1f}")
print(f"  Max DD:  {baseline_combined['max_dd_r']:.1f}R → {combined['max_dd_r']:.1f}R")
print(f"  Consec Loss: {baseline_combined['max_consec_loss']} → {combined['max_consec_loss']}")
print(f"  B2B SL:  {baseline_combined['back2back_sl']} → {combined['back2back_sl']}")
print(f"  Calmar:  {baseline_combined['calmar']:.2f} → {combined['calmar']:.2f}")

# Per-stock comparison
print(f"\nPer-stock improvement:")
for name in sorted(per_stock.keys()):
    b = baseline_per[name]
    o = per_stock[name]
    print(f"  {name}: {b['total_r']:+.1f}R → {o['total_r']:+.1f}R | "
          f"DD {b['max_dd_r']:.1f}→{o['max_dd_r']:.1f} | "
          f"B2B {b['back2back_sl']}→{o['back2back_sl']}")
