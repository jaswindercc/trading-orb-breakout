"""
Test different take-profit / trailing-exit strategies to find what captures the most momentum.
Approaches:
1. Fixed R:R TP (current - 3:1)
2. No fixed TP, pure EMA trail (ride until trend breaks)
3. No fixed TP, Supertrend trail (exit when supertrend flips)
4. No fixed TP, prev bar low/high trail after 1R
5. Hybrid: remove TP after 2R, switch to trail-only
6. Step-up TP: move TP higher as trade progresses (ratchet)
"""
import csv
import math
from datetime import datetime
from collections import defaultdict

rows = []
with open('spy_data.csv') as f:
    reader = csv.DictReader(f)
    for r in reader:
        dt = datetime.strptime(r['Date'].split(' ')[0], '%m/%d/%Y')
        rows.append({
            'date': dt, 'dow': dt.weekday(),
            'open': float(r['Open']), 'high': float(r['High']),
            'low': float(r['Low']), 'close': float(r['Close']),
        })

closes = [r['close'] for r in rows]

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

def calc_supertrend(rows, period=10, multiplier=2.5):
    n = len(rows)
    atr = calc_atr(rows, period)
    st_dir = [1] * n
    upper_band = [0.0] * n
    lower_band = [0.0] * n
    for i in range(n):
        hl2 = (rows[i]['high'] + rows[i]['low']) / 2
        upper_band[i] = hl2 + multiplier * atr[i]
        lower_band[i] = hl2 - multiplier * atr[i]
        if i > 0:
            if lower_band[i] < lower_band[i-1] and rows[i-1]['close'] > lower_band[i-1]:
                lower_band[i] = lower_band[i-1]
            if upper_band[i] > upper_band[i-1] and rows[i-1]['close'] < upper_band[i-1]:
                upper_band[i] = upper_band[i-1]
            if st_dir[i-1] == -1:
                if rows[i]['close'] < lower_band[i]:
                    st_dir[i] = 1
                else:
                    st_dir[i] = -1
            else:
                if rows[i]['close'] > upper_band[i]:
                    st_dir[i] = -1
                else:
                    st_dir[i] = 1
    return st_dir, lower_band, upper_band

atr14 = calc_atr(rows, 14)
ema10 = calc_ema(closes, 10)
ema20 = calc_ema(closes, 20)
st_dir, st_lower, st_upper = calc_supertrend(rows, 10, 2.5)

weeks = defaultdict(list)
for i, r in enumerate(rows):
    iso = r['date'].isocalendar()
    weeks[(iso[0], iso[1])].append((i, r))
sorted_weeks = sorted(weeks.keys())


def run_strategy(tp_mode='fixed_rr', rr=3.0, sl_atr_mult=1.5,
                 trail_ema_len=10, trail_atr_mult=0.5,
                 trail_activate_r=1.0,
                 # New params for different TP modes
                 supertrend_exit=False,    # exit when supertrend flips
                 prev_bar_trail=False,     # trail with prev bar low/high
                 remove_tp_after_r=0,      # remove fixed TP after this R (0=never)
                 friday_hold_r=0.5,
                 start_year=2024):
    """
    tp_mode: 
      'fixed_rr' - standard fixed TP
      'no_tp'    - no fixed TP, pure trail
      'hybrid'   - fixed TP until X R, then remove and trail
    """
    
    trail_ema = calc_ema(closes, trail_ema_len)
    trades = []
    
    for wk_key in sorted_weeks:
        wk = weeks[wk_key]
        if wk[0][1]['date'].year < start_year:
            continue
        
        first_idx, first_day = wk[0]
        week_open = first_day['open']
        res = math.ceil(week_open / 10) * 10
        sup = math.floor(week_open / 10) * 10
        if res == week_open: res += 10
        if sup == week_open: sup -= 10
        
        traded = False
        for j, (global_idx, day) in enumerate(wk):
            if traded: break
            if day['dow'] == 4: break
            
            atr_v = atr14[global_idx]
            body = abs(day['close'] - day['open'])
            rng = day['high'] - day['low']
            body_pct = (body / rng * 100) if rng > 0 else 0
            
            bull_trend = st_dir[global_idx] < 0
            bear_trend = st_dir[global_idx] > 0
            
            long_ok = (day['close'] > res and bull_trend and body_pct >= 50 and day['close'] > day['open'])
            short_ok = (day['close'] < sup and bear_trend and body_pct >= 50 and day['close'] < day['open'])
            
            if not long_ok and not short_ok:
                continue
            
            direction = 'long' if long_ok else 'short'
            entry_price = day['close']
            
            if direction == 'long':
                sl = entry_price - sl_atr_mult * atr_v
                risk = entry_price - sl
                tp = entry_price + risk * rr if tp_mode != 'no_tp' else 99999
            else:
                sl = entry_price + sl_atr_mult * atr_v
                risk = sl - entry_price
                tp = entry_price - risk * rr if tp_mode != 'no_tp' else -99999
            
            if risk <= 0: continue
            
            # Simulate
            result = None
            exit_price = None
            trail_sl = sl
            tp_active = (tp_mode != 'no_tp')
            max_r_reached = 0
            
            all_future = []
            for k in range(j + 1, len(wk)):
                all_future.append(wk[k])
            entry_wk_idx = sorted_weeks.index(wk_key)
            for offset in range(1, 6):  # up to 5 more weeks
                fut_wk_idx = entry_wk_idx + offset
                if fut_wk_idx >= len(sorted_weeks): break
                for bar in weeks[sorted_weeks[fut_wk_idx]]:
                    all_future.append(bar)
            
            for k, (fut_idx, future) in enumerate(all_future):
                curr_pnl = (future['close'] - entry_price) if direction == 'long' else (entry_price - future['close'])
                curr_r = curr_pnl / risk if risk > 0 else 0
                max_r_reached = max(max_r_reached, curr_r)
                
                # Hybrid: remove TP after reaching threshold
                if tp_mode == 'hybrid' and remove_tp_after_r > 0 and max_r_reached >= remove_tp_after_r:
                    tp_active = False
                
                # Trailing stop logic
                if curr_r >= trail_activate_r:
                    if prev_bar_trail and k > 0:
                        prev_fut_idx, prev_future = all_future[k-1]
                        if direction == 'long':
                            new_trail = prev_future['low']
                            if new_trail > trail_sl:
                                trail_sl = new_trail
                        else:
                            new_trail = prev_future['high']
                            if new_trail < trail_sl:
                                trail_sl = new_trail
                    
                    # EMA trail
                    if fut_idx < len(trail_ema):
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
                
                # Supertrend exit
                if supertrend_exit and curr_r >= trail_activate_r:
                    if direction == 'long' and st_dir[fut_idx] > 0:  # flipped bearish
                        result = 'ST_FLIP'
                        exit_price = future['close']
                        break
                    if direction == 'short' and st_dir[fut_idx] < 0:  # flipped bullish
                        result = 'ST_FLIP'
                        exit_price = future['close']
                        break
                
                # Check SL
                if direction == 'long':
                    if future['low'] <= trail_sl:
                        result = 'SL'
                        exit_price = trail_sl
                        break
                    if tp_active and future['high'] >= tp:
                        result = 'TP'
                        exit_price = tp
                        break
                else:
                    if future['high'] >= trail_sl:
                        result = 'SL'
                        exit_price = trail_sl
                        break
                    if tp_active and future['low'] <= tp:
                        result = 'TP'
                        exit_price = tp
                        break
                
                # Friday
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
                'entry_date': day['date'], 'direction': direction,
                'entry': entry_price, 'sl': sl, 'tp': tp,
                'exit': exit_price, 'exit_type': result,
                'pnl_pts': pnl, 'pnl_R': pnl_r, 'risk': risk,
                'max_r': max_r_reached,
            })
            traded = True
    
    return trades


def analyze(trades, label=""):
    if not trades or len(trades) < 3: return None
    wins = [t for t in trades if t['pnl_R'] > 0]
    losses = [t for t in trades if t['pnl_R'] <= 0]
    total_r = sum(t['pnl_R'] for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_win_r = sum(t['pnl_R'] for t in wins) / len(wins) if wins else 0
    avg_loss_r = sum(t['pnl_R'] for t in losses) / len(losses) if losses else 0
    max_single = max(t['pnl_R'] for t in trades)
    avg_max_r = sum(t['max_r'] for t in trades) / len(trades)
    
    max_consec_loss = 0
    curr_consec = 0
    for t in trades:
        if t['pnl_R'] <= 0:
            curr_consec += 1
            max_consec_loss = max(max_consec_loss, curr_consec)
        else:
            curr_consec = 0
    
    peak_r = 0; running_r = 0; max_dd_r = 0
    for t in trades:
        running_r += t['pnl_R']
        peak_r = max(peak_r, running_r)
        max_dd_r = max(max_dd_r, peak_r - running_r)
    
    gross_wins = sum(t['pnl_R'] for t in wins) if wins else 0
    gross_losses = abs(sum(t['pnl_R'] for t in losses)) if losses else 0.01
    pf = gross_wins / gross_losses if gross_losses > 0 else 999
    
    return {
        'label': label, 'trades': len(trades), 'wins': len(wins),
        'wr': win_rate, 'total_R': total_r, 'avg_win': avg_win_r,
        'avg_loss': avg_loss_r, 'max_single': max_single,
        'avg_max_r': avg_max_r, 'max_consec_loss': max_consec_loss,
        'max_dd_R': max_dd_r, 'pf': pf,
    }


print("=" * 120)
print("TAKE PROFIT / EXIT STRATEGY COMPARISON")
print("=" * 120)

results = []

# 1. Current: Fixed 3:1 TP + EMA trail after 1R
t = run_strategy(tp_mode='fixed_rr', rr=3.0, trail_activate_r=1.0)
results.append(analyze(t, "Fixed 3:1 TP + EMA trail @1R"))

# 2. No TP, pure EMA trail (activate at different R levels)
for act_r in [0.5, 1.0, 1.5]:
    for ema_len in [10, 15, 20]:
        for atr_m in [0.5, 1.0]:
            t = run_strategy(tp_mode='no_tp', trail_ema_len=ema_len, trail_atr_mult=atr_m, trail_activate_r=act_r)
            r = analyze(t, f"No TP, EMA({ema_len})-{atr_m}ATR trail @{act_r}R")
            if r: results.append(r)

# 3. No TP, Supertrend exit (trend flip = exit)
for act_r in [0.5, 1.0, 1.5]:
    t = run_strategy(tp_mode='no_tp', supertrend_exit=True, trail_activate_r=act_r)
    r = analyze(t, f"No TP, Supertrend exit @{act_r}R")
    if r: results.append(r)

# 4. No TP, prev bar low/high trail
for act_r in [0.5, 1.0, 1.5]:
    t = run_strategy(tp_mode='no_tp', prev_bar_trail=True, trail_activate_r=act_r)
    r = analyze(t, f"No TP, prev bar trail @{act_r}R")
    if r: results.append(r)

# 5. No TP, prev bar + EMA combined
for act_r in [0.5, 1.0, 1.5]:
    for ema_len in [10, 20]:
        t = run_strategy(tp_mode='no_tp', prev_bar_trail=True, trail_ema_len=ema_len, trail_atr_mult=0.5, trail_activate_r=act_r)
        r = analyze(t, f"No TP, prevBar+EMA({ema_len}) @{act_r}R")
        if r: results.append(r)

# 6. Hybrid: TP at 3R, but if it reaches 2R remove TP and trail
for remove_r in [1.5, 2.0, 2.5]:
    for ema_len in [10, 20]:
        t = run_strategy(tp_mode='hybrid', rr=3.0, remove_tp_after_r=remove_r, trail_ema_len=ema_len, trail_activate_r=1.0)
        r = analyze(t, f"Hybrid: TP3 remove@{remove_r}R, EMA({ema_len}) trail")
        if r: results.append(r)

# 7. Hybrid with supertrend exit after removing TP
for remove_r in [1.5, 2.0]:
    t = run_strategy(tp_mode='hybrid', rr=3.0, remove_tp_after_r=remove_r, supertrend_exit=True, trail_activate_r=1.0)
    r = analyze(t, f"Hybrid: TP3 remove@{remove_r}R + ST exit")
    if r: results.append(r)

# 8. No TP, Supertrend exit + EMA trail combined
for ema_len in [10, 15, 20]:
    for act_r in [0.5, 1.0]:
        t = run_strategy(tp_mode='no_tp', supertrend_exit=True, trail_ema_len=ema_len, trail_atr_mult=0.5, trail_activate_r=act_r)
        r = analyze(t, f"No TP, ST exit + EMA({ema_len}) @{act_r}R")
        if r: results.append(r)

# Filter valid
results = [r for r in results if r is not None]

# Sort by total R
results.sort(key=lambda x: -x['total_R'])
print(f"\n{'TOP 20 BY TOTAL R (best momentum capture)':}")
print(f"{'Label':<45} {'#':>3} {'WR%':>5} {'TotR':>7} {'AvgW':>6} {'MaxR':>5} {'AvgMR':>5} {'CSL':>3} {'DD':>5} {'PF':>5}")
print("-" * 120)
for r in results[:20]:
    print(f"{r['label']:<45} {r['trades']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_win']:>6.2f} {r['max_single']:>5.1f} {r['avg_max_r']:>5.1f} {r['max_consec_loss']:>3} {r['max_dd_R']:>5.1f} {r['pf']:>5.2f}")

# Sort by avg win (best average winner size = riding momentum)
results.sort(key=lambda x: -x['avg_win'])
print(f"\n{'TOP 20 BY AVERAGE WINNER SIZE (biggest rides)':}")
print(f"{'Label':<45} {'#':>3} {'WR%':>5} {'TotR':>7} {'AvgW':>6} {'MaxR':>5} {'AvgMR':>5} {'CSL':>3} {'DD':>5} {'PF':>5}")
print("-" * 120)
for r in results[:20]:
    print(f"{r['label']:<45} {r['trades']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_win']:>6.2f} {r['max_single']:>5.1f} {r['avg_max_r']:>5.1f} {r['max_consec_loss']:>3} {r['max_dd_R']:>5.1f} {r['pf']:>5.2f}")

# Best risk-adjusted
for r in results:
    r['score'] = r['total_R'] / r['max_dd_R'] if r['max_dd_R'] > 0 else 0
results.sort(key=lambda x: -x['score'])
print(f"\n{'TOP 20 BY RISK-ADJUSTED (TotalR / MaxDD)':}")
print(f"{'Label':<45} {'#':>3} {'WR%':>5} {'TotR':>7} {'AvgW':>6} {'MaxR':>5} {'AvgMR':>5} {'CSL':>3} {'DD':>5} {'PF':>5} {'Adj':>5}")
print("-" * 120)
for r in results[:20]:
    print(f"{r['label']:<45} {r['trades']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_win']:>6.2f} {r['max_single']:>5.1f} {r['avg_max_r']:>5.1f} {r['max_consec_loss']:>3} {r['max_dd_R']:>5.1f} {r['pf']:>5.2f} {r['score']:>5.2f}")

# Show trade log for best
results.sort(key=lambda x: -x['total_R'])
best_label = results[0]['label']
print(f"\n{'=' * 120}")
print(f"BEST CONFIG: {best_label}")
print(f"{'=' * 120}")
