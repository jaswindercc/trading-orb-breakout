import csv
from datetime import datetime, timedelta
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

# Group by ISO week
weeks = defaultdict(list)
for r in rows:
    iso = r['date'].isocalendar()
    weeks[(iso[0], iso[1])].append(r)

# Sort weeks
sorted_weeks = sorted(weeks.keys())

def run_backtest(round_int, rr, sl_type, ema_len, require_bull_bear, last_entry_dow, start_year=2021):
    """
    sl_type: 'candle' or 'round'
    last_entry_dow: 0=Mon only, 1=Mon-Tue, 2=Mon-Wed, 3=Mon-Thu
    """
    trades = []
    # Simple EMA calculation
    ema = None
    ema_vals = {}
    alpha = 2 / (ema_len + 1) if ema_len > 0 else 0
    for i, r in enumerate(rows):
        if ema_len > 0:
            if ema is None:
                ema = r['close']
            else:
                ema = alpha * r['close'] + (1 - alpha) * ema
            ema_vals[i] = ema

    for wk_key in sorted_weeks:
        wk = weeks[wk_key]
        if wk[0]['date'].year < start_year:
            continue
        
        week_open = wk[0]['open']
        res = (int(week_open / round_int) + 1) * round_int
        if res == week_open:
            res = week_open + round_int
        sup = int(week_open / round_int) * round_int
        if sup == week_open:
            sup = week_open - round_int

        import math
        res = math.ceil(week_open / round_int) * round_int
        sup = math.floor(week_open / round_int) * round_int
        if res == week_open:
            res = week_open + round_int
        if sup == week_open:
            sup = week_open - round_int

        traded = False
        for j, day in enumerate(wk):
            if traded:
                break
            if day['dow'] > last_entry_dow:
                break
            if day['dow'] == 4:  # no Friday
                break

            # Find global index for EMA
            global_idx = rows.index(day)
            ema_v = ema_vals.get(global_idx, None) if ema_len > 0 else None

            # Check long
            long_ok = day['close'] > res
            if require_bull_bear:
                long_ok = long_ok and day['close'] > day['open']
            if ema_len > 0 and ema_v is not None:
                long_ok = long_ok and day['close'] > ema_v

            # Check short
            short_ok = day['close'] < sup
            if require_bull_bear:
                short_ok = short_ok and day['close'] < day['open']
            if ema_len > 0 and ema_v is not None:
                short_ok = short_ok and day['close'] < ema_v

            if not long_ok and not short_ok:
                continue

            direction = 'long' if long_ok else 'short'
            entry_price = day['close']
            entry_day_idx = j

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

            # Simulate remaining days
            result = None
            exit_price = None
            exit_day = None
            
            for k in range(entry_day_idx + 1, len(wk)):
                future = wk[k]
                if direction == 'long':
                    # Check SL first (conservative)
                    if future['low'] <= sl:
                        result = 'SL'
                        exit_price = sl
                        exit_day = future['date']
                        break
                    if future['high'] >= tp:
                        result = 'TP'
                        exit_price = tp
                        exit_day = future['date']
                        break
                else:
                    if future['high'] >= sl:
                        result = 'SL'
                        exit_price = sl
                        exit_day = future['date']
                        break
                    if future['low'] <= tp:
                        result = 'TP'
                        exit_price = tp
                        exit_day = future['date']
                        break

                # Friday close
                if future['dow'] == 4:
                    result = 'FRI'
                    exit_price = future['close']
                    exit_day = future['date']
                    break

            if result is None:
                # Last day of week
                last = wk[-1]
                result = 'FRI'
                exit_price = last['close']
                exit_day = last['date']

            if direction == 'long':
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price

            trades.append({
                'week': wk_key,
                'entry_date': day['date'],
                'direction': direction,
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'risk': risk,
                'exit': exit_price,
                'exit_type': result,
                'exit_date': exit_day,
                'pnl_pts': pnl,
                'pnl_R': pnl / risk if risk > 0 else 0,
            })
            traded = True

    return trades


# Run many combinations
print("=" * 80)
print("WEEKLY ORB BACKTEST - SPY DAILY (2024-2026)")
print("=" * 80)

best_pf = -999
best_config = None

results_table = []

for ri in [5, 10]:
    for rr_val in [1.0, 1.5, 2.0, 3.0]:
        for sl in ['candle', 'round']:
            for ema in [0, 10, 20]:
                for bull in [True, False]:
                    for led in [2, 3, 4]:  # Mon-Wed, Mon-Thu, Mon-Fri(Thu)
                        trades = run_backtest(ri, rr_val, sl, ema, bull, led, start_year=2024)
                        if len(trades) < 5:
                            continue
                        wins = [t for t in trades if t['pnl_pts'] > 0]
                        losses = [t for t in trades if t['pnl_pts'] <= 0]
                        total_pnl = sum(t['pnl_R'] for t in trades)
                        win_rate = len(wins) / len(trades) * 100
                        avg_r = total_pnl / len(trades)
                        
                        results_table.append({
                            'round': ri, 'rr': rr_val, 'sl': sl, 'ema': ema,
                            'bull': bull, 'last_day': led,
                            'trades': len(trades), 'wins': len(wins),
                            'wr': win_rate, 'total_R': total_pnl, 'avg_R': avg_r
                        })

# Sort by total R
results_table.sort(key=lambda x: x['total_R'], reverse=True)

print(f"\n{'TOP 15 CONFIGURATIONS (by Total R-Multiple, 2024-2026)':}")
print(f"{'Round':>5} {'R:R':>4} {'SL':>6} {'EMA':>4} {'Bull':>5} {'Last':>4} | {'#':>3} {'Win':>3} {'WR%':>5} {'TotR':>7} {'AvgR':>6}")
print("-" * 75)
for r in results_table[:15]:
    print(f"{r['round']:>5} {r['rr']:>4} {r['sl']:>6} {r['ema']:>4} {str(r['bull']):>5} {r['last_day']:>4} | {r['trades']:>3} {r['wins']:>3} {r['wr']:>5.1f} {r['total_R']:>7.1f} {r['avg_R']:>6.2f}")

# Best config details
best = results_table[0]
print(f"\n{'=' * 80}")
print(f"BEST CONFIG: Round={best['round']}, R:R={best['rr']}, SL={best['sl']}, EMA={best['ema']}, Bull/Bear={best['bull']}, LastDay={best['last_day']}")
print(f"Trades={best['trades']}, Wins={best['wins']}, WinRate={best['wr']:.1f}%, Total R={best['total_R']:.1f}, Avg R/trade={best['avg_R']:.2f}")

# Run best config and show trade details
best_trades = run_backtest(best['round'], best['rr'], best['sl'], best['ema'], best['bull'], best['last_day'], start_year=2024)

print(f"\n{'TRADE LOG (Best Config, 2024-2026)':}")
print(f"{'Date':>12} {'Dir':>5} {'Entry':>8} {'SL':>8} {'TP':>8} {'Exit':>8} {'Type':>4} {'PnL($)':>8} {'PnL(R)':>7}")
print("-" * 80)
for t in best_trades:
    print(f"{t['entry_date'].strftime('%Y-%m-%d'):>12} {t['direction']:>5} {t['entry']:>8.2f} {t['sl']:>8.2f} {t['tp']:>8.2f} {t['exit']:>8.2f} {t['exit_type']:>4} {t['pnl_pts']:>8.2f} {t['pnl_R']:>7.2f}")

total_pts = sum(t['pnl_pts'] for t in best_trades)
total_r = sum(t['pnl_R'] for t in best_trades)
print(f"\nTotal PnL: ${total_pts:.2f}/share | Total R: {total_r:.1f}R")

# Also test 2026 only
print(f"\n{'=' * 80}")
print(f"2026 ONLY - BEST CONFIG")
trades_2026 = [t for t in best_trades if t['entry_date'].year == 2026]
if trades_2026:
    wins_26 = [t for t in trades_2026 if t['pnl_pts'] > 0]
    print(f"Trades={len(trades_2026)}, Wins={len(wins_26)}, WinRate={len(wins_26)/len(trades_2026)*100:.1f}%")
    for t in trades_2026:
        print(f"{t['entry_date'].strftime('%Y-%m-%d'):>12} {t['direction']:>5} {t['entry']:>8.2f} {t['sl']:>8.2f} {t['tp']:>8.2f} {t['exit']:>8.2f} {t['exit_type']:>4} {t['pnl_pts']:>8.2f} {t['pnl_R']:>7.2f}")
    print(f"Total R (2026): {sum(t['pnl_R'] for t in trades_2026):.1f}R")
