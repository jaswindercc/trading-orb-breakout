"""
Backtest: New entry strategy (Supertrend + strong candle + ATR stop)
vs old strategy (EMA filter + candle stop + day restriction)
"""
import csv
import math
from datetime import datetime
from collections import defaultdict

# Load data
rows = []
with open('spy_data.csv') as f:
    reader = csv.DictReader(f)
    for r in reader:
        dt = datetime.strptime(r['Date'].split(' ')[0], '%m/%d/%Y')
        rows.append({
            'date': dt,
            'dow': dt.weekday(),
            'open': float(r['Open']),
            'high': float(r['High']),
            'low': float(r['Low']),
            'close': float(r['Close']),
        })

# Precompute indicators
closes = [r['close'] for r in rows]
highs = [r['high'] for r in rows]
lows = [r['low'] for r in rows]

def calc_ema(data, length):
    vals = []
    alpha = 2 / (length + 1)
    ema = data[0]
    for v in data:
        ema = alpha * v + (1 - alpha) * ema
        vals.append(ema)
    return vals

def calc_atr(rows, period=14):
    trs = [rows[0]['high'] - rows[0]['low']]
    for i in range(1, len(rows)):
        tr = max(rows[i]['high'] - rows[i]['low'],
                 abs(rows[i]['high'] - rows[i-1]['close']),
                 abs(rows[i]['low'] - rows[i-1]['close']))
        trs.append(tr)
    atr_vals = [trs[0]] * len(rows)
    if len(trs) >= period:
        atr_vals[period-1] = sum(trs[:period]) / period
        for i in range(period, len(rows)):
            atr_vals[i] = (atr_vals[i-1] * (period-1) + trs[i]) / period
    return atr_vals

def calc_supertrend(rows, period=10, multiplier=2.0):
    """Returns (st_line, st_dir) arrays. dir < 0 = bullish, dir > 0 = bearish"""
    n = len(rows)
    atr = calc_atr(rows, period)
    
    st_line = [0.0] * n
    st_dir = [1] * n  # 1 = bearish, -1 = bullish
    
    upper_band = [0.0] * n
    lower_band = [0.0] * n
    
    for i in range(n):
        hl2 = (rows[i]['high'] + rows[i]['low']) / 2
        upper_band[i] = hl2 + multiplier * atr[i]
        lower_band[i] = hl2 - multiplier * atr[i]
        
        if i > 0:
            # Don't let bands flip inward
            if lower_band[i] < lower_band[i-1] and rows[i-1]['close'] > lower_band[i-1]:
                lower_band[i] = lower_band[i-1]
            if upper_band[i] > upper_band[i-1] and rows[i-1]['close'] < upper_band[i-1]:
                upper_band[i] = upper_band[i-1]
            
            # Determine direction
            if st_dir[i-1] == -1:  # was bullish
                if rows[i]['close'] < lower_band[i]:
                    st_dir[i] = 1  # flip to bearish
                    st_line[i] = upper_band[i]
                else:
                    st_dir[i] = -1  # stay bullish
                    st_line[i] = lower_band[i]
            else:  # was bearish
                if rows[i]['close'] > upper_band[i]:
                    st_dir[i] = -1  # flip to bullish
                    st_line[i] = lower_band[i]
                else:
                    st_dir[i] = 1  # stay bearish
                    st_line[i] = upper_band[i]
        else:
            st_line[i] = upper_band[i]
            st_dir[i] = 1
    
    return st_line, st_dir

ema10 = calc_ema(closes, 10)
ema20 = calc_ema(closes, 20)
atr14 = calc_atr(rows, 14)

# Group by ISO week
weeks = defaultdict(list)
for i, r in enumerate(rows):
    iso = r['date'].isocalendar()
    weeks[(iso[0], iso[1])].append((i, r))
sorted_weeks = sorted(weeks.keys())


def run_new_strategy(round_int=10, rr=3.0, st_len=10, st_mult=2.0,
                     min_body_pct=50, sl_atr_mult=1.5, cooloff=1,
                     trail_ema_len=10, trail_atr_mult=0.5,
                     friday_hold_r=0.5, trail_activate_r=1.0,
                     start_year=2024):
    """New strategy: Supertrend + strong candle + ATR stop"""
    
    # Compute supertrend with given params
    _, st_dir = calc_supertrend(rows, st_len, st_mult)
    trail_ema = calc_ema(closes, trail_ema_len)
    
    trades = []
    cooloff_left = 0
    
    for wk_key in sorted_weeks:
        wk = weeks[wk_key]
        if wk[0][1]['date'].year < start_year:
            continue
        
        if cooloff_left > 0:
            cooloff_left -= 1
            continue
        
        first_idx, first_day = wk[0]
        week_open = first_day['open']
        res = math.ceil(week_open / round_int) * round_int
        sup = math.floor(week_open / round_int) * round_int
        if res == week_open:
            res = week_open + round_int
        if sup == week_open:
            sup = week_open - round_int
        
        traded = False
        for j, (global_idx, day) in enumerate(wk):
            if traded:
                break
            if day['dow'] == 4:  # no Friday
                break
            
            atr_v = atr14[global_idx]
            
            # Body strength
            body = abs(day['close'] - day['open'])
            rng = day['high'] - day['low']
            body_pct = (body / rng * 100) if rng > 0 else 0
            
            # Supertrend direction
            bull_trend = st_dir[global_idx] < 0
            bear_trend = st_dir[global_idx] > 0
            
            # Entry conditions
            long_ok = (day['close'] > res and bull_trend and 
                      body_pct >= min_body_pct and day['close'] > day['open'])
            
            short_ok = (day['close'] < sup and bear_trend and 
                       body_pct >= min_body_pct and day['close'] < day['open'])
            
            if not long_ok and not short_ok:
                continue
            
            direction = 'long' if long_ok else 'short'
            entry_price = day['close']
            
            # ATR-based stop loss
            if direction == 'long':
                sl = entry_price - sl_atr_mult * atr_v
                risk = entry_price - sl
                tp = entry_price + risk * rr
            else:
                sl = entry_price + sl_atr_mult * atr_v
                risk = sl - entry_price
                tp = entry_price - risk * rr
            
            if risk <= 0:
                continue
            
            # Simulate trade
            result = None
            exit_price = None
            trail_sl = sl
            
            # Get all future bars (up to 4 weeks)
            all_future = []
            for k in range(j + 1, len(wk)):
                all_future.append(wk[k])
            entry_wk_idx = sorted_weeks.index(wk_key)
            for offset in range(1, 5):
                fut_wk_idx = entry_wk_idx + offset
                if fut_wk_idx >= len(sorted_weeks):
                    break
                for bar in weeks[sorted_weeks[fut_wk_idx]]:
                    all_future.append(bar)
            
            for k, (fut_idx, future) in enumerate(all_future):
                # Trailing stop
                curr_pnl = (future['close'] - entry_price) if direction == 'long' else (entry_price - future['close'])
                curr_r = curr_pnl / risk if risk > 0 else 0
                
                if curr_r >= trail_activate_r and fut_idx < len(trail_ema):
                    t_ema = trail_ema[fut_idx]
                    t_atr = atr14[fut_idx]
                    if direction == 'long':
                        ema_trail = t_ema - trail_atr_mult * t_atr
                        if ema_trail > trail_sl:
                            trail_sl = ema_trail
                    else:
                        ema_trail = t_ema + trail_atr_mult * t_atr
                        if ema_trail < trail_sl:
                            trail_sl = ema_trail
                
                # Check SL/TP
                if direction == 'long':
                    if future['low'] <= trail_sl:
                        result = 'SL'
                        exit_price = trail_sl
                        break
                    if future['high'] >= tp:
                        result = 'TP'
                        exit_price = tp
                        break
                else:
                    if future['high'] >= trail_sl:
                        result = 'SL'
                        exit_price = trail_sl
                        break
                    if future['low'] <= tp:
                        result = 'TP'
                        exit_price = tp
                        break
                
                # Friday hold check
                if future['dow'] == 4:
                    fri_pnl = (future['close'] - entry_price) if direction == 'long' else (entry_price - future['close'])
                    fri_r = fri_pnl / risk if risk > 0 else 0
                    if fri_r < friday_hold_r:
                        result = 'FRI'
                        exit_price = future['close']
                        break
            
            if result is None:
                last_idx, last_bar = all_future[-1] if all_future else (global_idx, day)
                result = 'EOD'
                exit_price = last_bar['close']
            
            pnl = (exit_price - entry_price) if direction == 'long' else (entry_price - exit_price)
            pnl_r = pnl / risk if risk > 0 else 0
            
            trades.append({
                'entry_date': day['date'],
                'direction': direction,
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'exit': exit_price,
                'exit_type': result,
                'pnl_pts': pnl,
                'pnl_R': pnl_r,
                'risk': risk,
            })
            traded = True
            
            if pnl <= 0:
                cooloff_left = cooloff
    
    return trades


def analyze(trades, label=""):
    if not trades or len(trades) < 3:
        return None
    wins = [t for t in trades if t['pnl_R'] > 0]
    losses = [t for t in trades if t['pnl_R'] <= 0]
    total_r = sum(t['pnl_R'] for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_r = total_r / len(trades)
    
    max_consec_loss = 0
    curr_consec = 0
    for t in trades:
        if t['pnl_R'] <= 0:
            curr_consec += 1
            max_consec_loss = max(max_consec_loss, curr_consec)
        else:
            curr_consec = 0
    
    peak_r = 0
    running_r = 0
    max_dd_r = 0
    for t in trades:
        running_r += t['pnl_R']
        peak_r = max(peak_r, running_r)
        dd = peak_r - running_r
        max_dd_r = max(max_dd_r, dd)
    
    gross_wins = sum(t['pnl_R'] for t in wins) if wins else 0
    gross_losses = abs(sum(t['pnl_R'] for t in losses)) if losses else 0.01
    pf = gross_wins / gross_losses if gross_losses > 0 else 999
    
    return {
        'label': label,
        'trades': len(trades),
        'wins': len(wins),
        'wr': win_rate,
        'total_R': total_r,
        'avg_R': avg_r,
        'max_consec_loss': max_consec_loss,
        'max_dd_R': max_dd_r,
        'pf': pf,
    }


# ============================================================
print("=" * 110)
print("SUPERTREND + STRONG CANDLE + ATR STOP — PARAMETER OPTIMIZATION")
print("SPY Daily 2024-2026")
print("=" * 110)

results = []

# Grid search over key parameters
for st_len in [7, 10, 14]:
    for st_mult in [1.5, 2.0, 2.5, 3.0]:
        for sl_atr in [1.0, 1.5, 2.0]:
            for body_pct in [0, 40, 50, 60]:
                for rr_val in [2.0, 3.0, 4.0]:
                    for cooloff in [0, 1]:
                        t = run_new_strategy(
                            st_len=st_len, st_mult=st_mult,
                            sl_atr_mult=sl_atr, min_body_pct=body_pct,
                            rr=rr_val, cooloff=cooloff, start_year=2024
                        )
                        r = analyze(t, f"ST({st_len},{st_mult}) SL={sl_atr}ATR Body={body_pct}% RR={rr_val} Cool={cooloff}")
                        if r and r['trades'] >= 5:
                            results.append(r)

print(f"\nTested {len(results)} valid configurations\n")

# Sort by risk-adjusted return
for r in results:
    r['adj'] = r['total_R'] / r['max_dd_R'] if r['max_dd_R'] > 0 else r['total_R']
    r['score'] = r['total_R'] * (1 - r['max_consec_loss']/10) * r['pf']  # composite score

results.sort(key=lambda x: -x['score'])

print(f"{'TOP 25 BY COMPOSITE SCORE (TotalR × PF × streak penalty)':}")
print(f"{'Label':<50} {'#':>3} {'Win':>3} {'WR%':>5} {'TotR':>7} {'AvgR':>6} {'MaxSL':>5} {'MaxDD':>6} {'PF':>5}")
print("-" * 110)
for r in results[:25]:
    print(f"{r['label']:<50} {r['trades']:>3} {r['wins']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_R']:>6.2f} {r['max_consec_loss']:>5} {r['max_dd_R']:>6.1f} {r['pf']:>5.2f}")

# Also show by fewest consecutive losses
results.sort(key=lambda x: (x['max_consec_loss'], -x['total_R']))
print(f"\n{'TOP 25 BY FEWEST CONSECUTIVE LOSSES':}")
print(f"{'Label':<50} {'#':>3} {'Win':>3} {'WR%':>5} {'TotR':>7} {'AvgR':>6} {'MaxSL':>5} {'MaxDD':>6} {'PF':>5}")
print("-" * 110)
for r in results[:25]:
    print(f"{r['label']:<50} {r['trades']:>3} {r['wins']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_R']:>6.2f} {r['max_consec_loss']:>5} {r['max_dd_R']:>6.1f} {r['pf']:>5.2f}")

# Show trade log for best
print(f"\n{'=' * 110}")
print("TRADE LOG — BEST COMPOSITE SCORE CONFIG")
print(f"{'=' * 110}")
results.sort(key=lambda x: -x['score'])
best = results[0]
print(f"Config: {best['label']}")
print(f"Trades={best['trades']}, WR={best['wr']:.1f}%, TotalR={best['total_R']:.1f}, MaxConsecLoss={best['max_consec_loss']}, MaxDD={best['max_dd_R']:.1f}R, PF={best['pf']:.2f}\n")

# Parse best config and re-run for trade log
# Extract params from label
import re
m = re.match(r'ST\((\d+),([\d.]+)\) SL=([\d.]+)ATR Body=(\d+)% RR=([\d.]+) Cool=(\d+)', best['label'])
if m:
    b_st_len = int(m.group(1))
    b_st_mult = float(m.group(2))
    b_sl_atr = float(m.group(3))
    b_body = float(m.group(4))
    b_rr = float(m.group(5))
    b_cool = int(m.group(6))
    
    best_trades = run_new_strategy(
        st_len=b_st_len, st_mult=b_st_mult,
        sl_atr_mult=b_sl_atr, min_body_pct=b_body,
        rr=b_rr, cooloff=b_cool, start_year=2024
    )
    
    print(f"{'Date':>12} {'Dir':>5} {'Entry':>8} {'SL':>8} {'TP':>8} {'Exit':>8} {'Type':>4} {'PnL(R)':>7}")
    print("-" * 75)
    for t in best_trades:
        print(f"{t['entry_date'].strftime('%Y-%m-%d'):>12} {t['direction']:>5} {t['entry']:>8.2f} {t['sl']:>8.2f} {t['tp']:>8.2f} {t['exit']:>8.2f} {t['exit_type']:>4} {t['pnl_R']:>7.2f}")
    
    total_r = sum(t['pnl_R'] for t in best_trades)
    print(f"\nTotal: {total_r:.1f}R | {len(best_trades)} trades")
