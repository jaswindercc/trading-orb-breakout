"""
Backtest optimizer: Find the best entry filters to reduce consecutive stop losses.
Tests various approaches to filter out low-quality breakouts.
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
            'dow': dt.weekday(),  # 0=Mon, 4=Fri
            'open': float(r['Open']),
            'high': float(r['High']),
            'low': float(r['Low']),
            'close': float(r['Close']),
        })

# Precompute EMAs
def calc_ema(data, length):
    ema_vals = []
    alpha = 2 / (length + 1)
    ema = data[0]
    for v in data:
        ema = alpha * v + (1 - alpha) * ema
        ema_vals.append(ema)
    return ema_vals

closes = [r['close'] for r in rows]
ema20 = calc_ema(closes, 20)
ema10 = calc_ema(closes, 10)

# Precompute ATR(14)
def calc_atr(rows, period=14):
    atrs = [0.0]
    for i in range(1, len(rows)):
        tr = max(rows[i]['high'] - rows[i]['low'],
                 abs(rows[i]['high'] - rows[i-1]['close']),
                 abs(rows[i]['low'] - rows[i-1]['close']))
        atrs.append(tr)
    # SMA for first period, then EMA
    atr_vals = [0.0] * len(rows)
    if len(atrs) > period:
        atr_vals[period] = sum(atrs[1:period+1]) / period
        for i in range(period+1, len(rows)):
            atr_vals[i] = (atr_vals[i-1] * (period-1) + atrs[i]) / period
    return atr_vals

atr14 = calc_atr(rows, 14)

# Group by ISO week
weeks = defaultdict(list)
for i, r in enumerate(rows):
    iso = r['date'].isocalendar()
    weeks[(iso[0], iso[1])].append((i, r))

sorted_weeks = sorted(weeks.keys())


def run_backtest(round_int=10, rr=3.0, sl_type='candle', ema_len=20,
                 last_entry_dow=1, start_year=2024,
                 # New filters to test:
                 min_breakout_pct=0.0,    # min % close must be beyond level
                 min_body_pct=0.0,        # min candle body as % of range
                 require_bull_candle=False, # long needs green candle, short needs red
                 cooloff_after_loss=0,     # skip N weeks after a loss
                 max_atr_mult=0.0,        # skip if ATR > X * round_int (choppy)
                 min_atr_mult=0.0,        # skip if ATR < X (too quiet/boomer)
                 require_close_above_prev_high=False,  # close > prev day high for long
                 trail_ema_len=10,
                 trail_atr_mult=0.5,
                 friday_hold_r=0.5,
                 trail_activate_r=1.0,
                 ):
    trades = []
    consecutive_losses = 0
    weeks_since_loss = 999

    for wk_key in sorted_weeks:
        wk = weeks[wk_key]
        if wk[0][1]['date'].year < start_year:
            continue

        # Cooloff filter
        if cooloff_after_loss > 0 and weeks_since_loss < cooloff_after_loss:
            weeks_since_loss += 1
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
            if day['dow'] > last_entry_dow:
                break
            if day['dow'] == 4:  # no Friday
                break

            ema_v = ema20[global_idx] if ema_len == 20 else (ema10[global_idx] if ema_len == 10 else None)
            atr_v = atr14[global_idx]

            # Max ATR filter (skip choppy markets)
            if max_atr_mult > 0 and atr_v > max_atr_mult * round_int:
                continue
            # Min ATR filter (skip dead markets)
            if min_atr_mult > 0 and atr_v < min_atr_mult:
                continue

            # Check long
            long_ok = day['close'] > res
            short_ok = day['close'] < sup

            if ema_len > 0 and ema_v is not None:
                long_ok = long_ok and day['close'] > ema_v
                short_ok = short_ok and day['close'] < ema_v

            # Min breakout % filter
            if min_breakout_pct > 0:
                if long_ok:
                    breakout_dist = (day['close'] - res) / res * 100
                    if breakout_dist < min_breakout_pct:
                        long_ok = False
                if short_ok:
                    breakout_dist = (sup - day['close']) / sup * 100
                    if breakout_dist < min_breakout_pct:
                        short_ok = False

            # Min body % filter (strong candle)
            if min_body_pct > 0:
                body = abs(day['close'] - day['open'])
                rng = day['high'] - day['low']
                body_pct = body / rng * 100 if rng > 0 else 0
                if body_pct < min_body_pct:
                    long_ok = False
                    short_ok = False

            # Bull/bear candle filter
            if require_bull_candle:
                if long_ok and day['close'] <= day['open']:
                    long_ok = False
                if short_ok and day['close'] >= day['open']:
                    short_ok = False

            # Close above previous day's high (momentum confirmation)
            if require_close_above_prev_high and j > 0:
                prev_idx, prev_day = wk[j-1]
                if long_ok and day['close'] <= prev_day['high']:
                    long_ok = False
                if short_ok and day['close'] >= prev_day['low']:
                    short_ok = False
            elif require_close_above_prev_high and j == 0 and global_idx > 0:
                prev_day = rows[global_idx - 1]
                if long_ok and day['close'] <= prev_day['high']:
                    long_ok = False
                if short_ok and day['close'] >= prev_day['low']:
                    short_ok = False

            if not long_ok and not short_ok:
                continue

            direction = 'long' if long_ok else 'short'
            entry_price = day['close']

            if direction == 'long':
                sl = day['low'] if sl_type == 'candle' else sup
                risk = entry_price - sl
                if risk <= 0:
                    continue
                tp = entry_price + risk * rr
            else:
                sl = day['high'] if sl_type == 'candle' else res
                risk = sl - entry_price
                if risk <= 0:
                    continue
                tp = entry_price - risk * rr

            # Simulate remaining days (with trailing stop)
            result = None
            exit_price = None
            trail_sl = sl
            
            # Compute trail EMA values
            trail_ema_vals = calc_ema(closes[:global_idx+1], trail_ema_len) if trail_ema_len > 0 else None

            remaining_indices = [wk[k] for k in range(j + 1, len(wk))]
            # Also look into next weeks if held past Friday
            # Find all bars after entry until exit
            all_future_bars = []
            for k in range(j + 1, len(wk)):
                all_future_bars.append(wk[k])
            
            # If we can hold past Friday, add next weeks' bars (up to 4 weeks max)
            entry_week_idx = sorted_weeks.index(wk_key)
            for future_wk_offset in range(1, 5):  # up to 4 more weeks
                future_wk_idx = entry_week_idx + future_wk_offset
                if future_wk_idx >= len(sorted_weeks):
                    break
                future_wk_key = sorted_weeks[future_wk_idx]
                for bar in weeks[future_wk_key]:
                    all_future_bars.append(bar)

            for k, (fut_idx, future) in enumerate(all_future_bars):
                # Update trailing stop (EMA-based, activates at trail_activate_r)
                curr_pnl = (future['close'] - entry_price) if direction == 'long' else (entry_price - future['close'])
                curr_r = curr_pnl / risk if risk > 0 else 0

                if curr_r >= trail_activate_r and trail_ema_len > 0 and fut_idx < len(ema10):
                    # Recalculate trail EMA at this point
                    trail_ema_here = ema10[fut_idx] if trail_ema_len == 10 else ema20[fut_idx]
                    atr_here = atr14[fut_idx]
                    if direction == 'long':
                        ema_trail_level = trail_ema_here - trail_atr_mult * atr_here
                        if ema_trail_level > trail_sl:
                            trail_sl = ema_trail_level
                    else:
                        ema_trail_level = trail_ema_here + trail_atr_mult * atr_here
                        if ema_trail_level < trail_sl:
                            trail_sl = ema_trail_level

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

                # Friday close check
                if future['dow'] == 4:
                    fri_pnl = (future['close'] - entry_price) if direction == 'long' else (entry_price - future['close'])
                    fri_r = fri_pnl / risk if risk > 0 else 0
                    if fri_r < friday_hold_r:
                        result = 'FRI'
                        exit_price = future['close']
                        break
                    # else: hold through weekend, continue to next week

            if result is None:
                # Max hold reached or end of data
                last_idx, last_bar = all_future_bars[-1] if all_future_bars else (global_idx, day)
                result = 'EOD'
                exit_price = last_bar['close']

            if direction == 'long':
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price

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

            # Track consecutive losses for cooloff
            if pnl <= 0:
                consecutive_losses += 1
                weeks_since_loss = 0
            else:
                consecutive_losses = 0
                weeks_since_loss = 999

        if not traded:
            weeks_since_loss += 1

    return trades


def analyze(trades, label=""):
    if not trades:
        return None
    wins = [t for t in trades if t['pnl_R'] > 0]
    losses = [t for t in trades if t['pnl_R'] <= 0]
    total_r = sum(t['pnl_R'] for t in trades)
    win_rate = len(wins) / len(trades) * 100
    avg_r = total_r / len(trades)
    
    # Max consecutive losses
    max_consec_loss = 0
    curr_consec = 0
    for t in trades:
        if t['pnl_R'] <= 0:
            curr_consec += 1
            max_consec_loss = max(max_consec_loss, curr_consec)
        else:
            curr_consec = 0

    # Max drawdown in R
    peak_r = 0
    running_r = 0
    max_dd_r = 0
    for t in trades:
        running_r += t['pnl_R']
        peak_r = max(peak_r, running_r)
        dd = peak_r - running_r
        max_dd_r = max(max_dd_r, dd)

    # Profit factor
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
# TEST VARIOUS CONFIGURATIONS
# ============================================================
print("=" * 100)
print("WEEKLY ORB OPTIMIZER — FINDING BEST ENTRY FILTERS TO REDUCE CONSECUTIVE STOP LOSSES")
print("Testing on SPY daily 2024-2026")
print("=" * 100)

results = []

# Baseline: current strategy (no extra filters)
t = run_backtest(start_year=2024)
r = analyze(t, "BASELINE (no filters)")
if r: results.append(r)

# Test 1: Require bull candle for long (green), bear for short (red)
t = run_backtest(start_year=2024, require_bull_candle=True)
r = analyze(t, "Bull/bear candle required")
if r: results.append(r)

# Test 2: Min breakout distance (close must be at least X% beyond level)
for pct in [0.1, 0.2, 0.3, 0.5]:
    t = run_backtest(start_year=2024, min_breakout_pct=pct)
    r = analyze(t, f"Min breakout {pct}%")
    if r: results.append(r)

# Test 3: Min body % (strong candle body vs wicks)
for body in [40, 50, 60]:
    t = run_backtest(start_year=2024, min_body_pct=body)
    r = analyze(t, f"Min body {body}%")
    if r: results.append(r)

# Test 4: Close above prev day high (momentum)
t = run_backtest(start_year=2024, require_close_above_prev_high=True)
r = analyze(t, "Close > prev high/low")
if r: results.append(r)

# Test 5: ATR filter (skip choppy/volatile weeks)
for mult in [0.8, 1.0, 1.2, 1.5]:
    t = run_backtest(start_year=2024, max_atr_mult=mult)
    r = analyze(t, f"Max ATR < {mult}x round")
    if r: results.append(r)

# Test 6: Cooloff after loss (skip 1-2 weeks after a losing trade)
for cooloff in [1, 2]:
    t = run_backtest(start_year=2024, cooloff_after_loss=cooloff)
    r = analyze(t, f"Cooloff {cooloff} week after loss")
    if r: results.append(r)

# Test 7: Entry day restriction
for led in [0, 1, 2]:  # Mon only, Mon-Tue, Mon-Wed
    t = run_backtest(start_year=2024, last_entry_dow=led)
    r = analyze(t, f"Last entry day={['Mon','Tue','Wed'][led]}")
    if r: results.append(r)

# Test 8: Combinations of best filters
t = run_backtest(start_year=2024, require_bull_candle=True, min_breakout_pct=0.1)
r = analyze(t, "Bull candle + 0.1% breakout")
if r: results.append(r)

t = run_backtest(start_year=2024, require_bull_candle=True, min_body_pct=40)
r = analyze(t, "Bull candle + 40% body")
if r: results.append(r)

t = run_backtest(start_year=2024, require_bull_candle=True, min_breakout_pct=0.2, min_body_pct=40)
r = analyze(t, "Bull + 0.2% breakout + 40% body")
if r: results.append(r)

t = run_backtest(start_year=2024, min_breakout_pct=0.1, min_body_pct=50)
r = analyze(t, "0.1% breakout + 50% body")
if r: results.append(r)

t = run_backtest(start_year=2024, require_close_above_prev_high=True, min_body_pct=40)
r = analyze(t, "Close>prev high + 40% body")
if r: results.append(r)

t = run_backtest(start_year=2024, require_bull_candle=True, max_atr_mult=1.2)
r = analyze(t, "Bull candle + ATR<1.2x")
if r: results.append(r)

t = run_backtest(start_year=2024, require_bull_candle=True, cooloff_after_loss=1)
r = analyze(t, "Bull candle + 1wk cooloff")
if r: results.append(r)

t = run_backtest(start_year=2024, require_bull_candle=True, min_breakout_pct=0.1, cooloff_after_loss=1)
r = analyze(t, "Bull+0.1%+1wk cooloff")
if r: results.append(r)

# Test 9: Different R:R with filters
for rr_val in [2.0, 2.5, 3.0, 4.0, 5.0]:
    t = run_backtest(start_year=2024, rr=rr_val, require_bull_candle=True, min_breakout_pct=0.1)
    r = analyze(t, f"R:R={rr_val} + bull + 0.1%")
    if r: results.append(r)

# Test 10: Trail activation thresholds
for act_r in [0.5, 1.0, 1.5, 2.0]:
    t = run_backtest(start_year=2024, trail_activate_r=act_r, require_bull_candle=True, min_breakout_pct=0.1)
    r = analyze(t, f"Trail@{act_r}R + bull + 0.1%")
    if r: results.append(r)

# Test 11: No TP (pure trailing exit)
for act_r in [1.0, 1.5]:
    t = run_backtest(start_year=2024, rr=99.0, trail_activate_r=act_r, 
                     require_bull_candle=True, min_breakout_pct=0.1)
    r = analyze(t, f"No TP, trail@{act_r}R + bull")
    if r: results.append(r)

# ============================================================
# SORT AND DISPLAY RESULTS
# ============================================================
print(f"\n{'RESULTS SORTED BY: Lowest Max Consecutive Losses, then Highest Total R':}")
print(f"{'Label':<35} {'#':>3} {'Win':>3} {'WR%':>5} {'TotR':>7} {'AvgR':>6} {'MaxSL':>5} {'MaxDD':>6} {'PF':>5}")
print("-" * 100)

# Sort: fewer consecutive losses first, then higher total R
results.sort(key=lambda x: (x['max_consec_loss'], -x['total_R']))

for r in results:
    print(f"{r['label']:<35} {r['trades']:>3} {r['wins']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_R']:>6.2f} {r['max_consec_loss']:>5} {r['max_dd_R']:>6.1f} {r['pf']:>5.2f}")

# Also sort by Total R (best profitability)
print(f"\n{'RESULTS SORTED BY: Highest Total R':}")
print(f"{'Label':<35} {'#':>3} {'Win':>3} {'WR%':>5} {'TotR':>7} {'AvgR':>6} {'MaxSL':>5} {'MaxDD':>6} {'PF':>5}")
print("-" * 100)
results.sort(key=lambda x: -x['total_R'])
for r in results[:20]:
    print(f"{r['label']:<35} {r['trades']:>3} {r['wins']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_R']:>6.2f} {r['max_consec_loss']:>5} {r['max_dd_R']:>6.1f} {r['pf']:>5.2f}")

# Also sort by best risk-adjusted (PF * total_R / max_dd)
print(f"\n{'RESULTS SORTED BY: Best Risk-Adjusted (TotalR / MaxDD)':}")
print(f"{'Label':<35} {'#':>3} {'Win':>3} {'WR%':>5} {'TotR':>7} {'AvgR':>6} {'MaxSL':>5} {'MaxDD':>6} {'PF':>5} {'Adj':>5}")
print("-" * 100)
for r in results:
    r['adj'] = r['total_R'] / r['max_dd_R'] if r['max_dd_R'] > 0 else 0
results.sort(key=lambda x: -x['adj'])
for r in results[:20]:
    print(f"{r['label']:<35} {r['trades']:>3} {r['wins']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_R']:>6.2f} {r['max_consec_loss']:>5} {r['max_dd_R']:>6.1f} {r['pf']:>5.2f} {r['adj']:>5.2f}")


# ============================================================
# SHOW TRADE LOG FOR BEST CONFIG
# ============================================================
print("\n" + "=" * 100)
print("TRADE LOG — BEST RISK-ADJUSTED CONFIG")
print("=" * 100)
# Re-run best
best_label = results[0]['label']
print(f"Config: {best_label}")
# We need to figure out which params this was... let me just pick the top one and re-run with known params
# For now, show the baseline comparison

print("\n\nBASELINE TRADE LOG:")
baseline_trades = run_backtest(start_year=2024)
print(f"{'Date':>12} {'Dir':>5} {'Entry':>8} {'SL':>8} {'TP':>8} {'Exit':>8} {'Type':>4} {'PnL(R)':>7}")
print("-" * 70)
for t in baseline_trades:
    print(f"{t['entry_date'].strftime('%Y-%m-%d'):>12} {t['direction']:>5} {t['entry']:>8.2f} {t['sl']:>8.2f} {t['tp']:>8.2f} {t['exit']:>8.2f} {t['exit_type']:>4} {t['pnl_R']:>7.2f}")
total_r = sum(t['pnl_R'] for t in baseline_trades)
print(f"\nTotal: {total_r:.1f}R across {len(baseline_trades)} trades")
