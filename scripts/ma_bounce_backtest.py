#!/usr/bin/env python3
"""
MA Bounce Strategy — backtest on SPY
Entry: price pulls back near a moving average and bounces off it.
Catches trends already running (no crossover needed).
"""
import pandas as pd, numpy as np
from pathlib import Path

DATA = Path("/workspaces/jas/data/spy_data.csv")
RISK = 100
SL_ATR = 1.0

def run_backtest(df, cfg, label):
    """Run a single MA bounce config and return trades."""
    ma_col = cfg['ma_col']           # which MA to bounce off
    trend_col = cfg['trend_col']     # trend filter MA (must be above for longs)
    bounce_atr = cfg['bounce_atr']   # how close price must get to MA (in ATRs)
    trail_ema = cfg['trail_ema']     # EMA length for trailing stop
    trail_atr_buf = cfg['trail_atr_buf']
    trail_start_r = cfg['trail_start_r']
    allow_shorts = cfg.get('allow_shorts', False)

    trades = []
    pos = 0       # 1=long, -1=short, 0=flat
    ep = sl = er = trail_sl = 0.0

    for i in range(1, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i-1]

        if pd.isna(r[ma_col]) or pd.isna(r[trend_col]) or pd.isna(r['atr']) or pd.isna(r['ema_trail']):
            continue

        # ── In a trade: check stop / trail ──
        if pos != 0:
            # Check stop
            if pos == 1 and r['Low'] <= trail_sl:
                xp = trail_sl
                pnl = (xp - ep) * qty
                pnl_r = (xp - ep) / er if er > 0 else 0
                trades.append({'entry': ep_date, 'exit': r['Date'], 'dir': 'LONG',
                    'entryPrice': ep, 'exitPrice': xp, 'pnl': pnl, 'pnlR': round(pnl_r,1),
                    'days': (r['Date'] - ep_date).days, 'reason': 'SL'})
                pos = 0
                continue
            if pos == -1 and r['High'] >= trail_sl:
                xp = trail_sl
                pnl = (ep - xp) * qty
                pnl_r = (ep - xp) / er if er > 0 else 0
                trades.append({'entry': ep_date, 'exit': r['Date'], 'dir': 'SHORT',
                    'entryPrice': ep, 'exitPrice': xp, 'pnl': pnl, 'pnlR': round(pnl_r,1),
                    'days': (r['Date'] - ep_date).days, 'reason': 'SL'})
                pos = 0
                continue

            # Trail logic (longs only for now)
            if pos == 1:
                curr_r = (r['Close'] - ep) / er if er > 0 else 0
                if curr_r >= trail_start_r:
                    ema_trail = r['ema_trail'] - trail_atr_buf * r['atr']
                    if ema_trail > trail_sl:
                        trail_sl = ema_trail
            continue

        # ── Flat: look for entry ──
        atr = r['atr']
        ma_val = r[ma_col]
        trend_val = r[trend_col]

        # LONG: price in uptrend + pulled back near MA + bounced (close above MA)
        if r['Close'] > trend_val:  # uptrend
            touched = prev['Low'] <= ma_val + bounce_atr * atr  # prev bar dipped near MA
            bounced = r['Close'] > ma_val                        # today closed above MA
            not_too_far = r['Close'] - ma_val <= 3.0 * atr       # not already way above
            small_bar = (r['High'] - r['Low']) <= 2.0 * atr

            if touched and bounced and not_too_far and small_bar:
                pos = 1
                ep = r['Close']
                sl_price = ep - SL_ATR * atr
                er = ep - sl_price
                qty = max(1, round(RISK / er)) if er > 0 else 1
                trail_sl = sl_price
                ep_date = r['Date']

        # SHORT (optional): price in downtrend + pulled back up to MA + rejected
        elif allow_shorts and r['Close'] < trend_val:
            touched = prev['High'] >= ma_val - bounce_atr * atr
            rejected = r['Close'] < ma_val
            not_too_far = ma_val - r['Close'] <= 3.0 * atr
            small_bar = (r['High'] - r['Low']) <= 2.0 * atr

            if touched and rejected and not_too_far and small_bar:
                pos = -1
                ep = r['Close']
                sl_price = ep + SL_ATR * atr
                er = sl_price - ep
                qty = max(1, round(RISK / er)) if er > 0 else 1
                trail_sl = sl_price
                ep_date = r['Date']

    # Close open trade at last bar
    if pos != 0:
        r = df.iloc[-1]
        xp = r['Close']
        pnl = (xp - ep) * qty if pos == 1 else (ep - xp) * qty
        pnl_r = ((xp - ep) / er if pos == 1 else (ep - xp) / er) if er > 0 else 0
        trades.append({'entry': ep_date, 'exit': r['Date'],
            'dir': 'LONG' if pos == 1 else 'SHORT',
            'entryPrice': ep, 'exitPrice': xp, 'pnl': pnl, 'pnlR': round(pnl_r,1),
            'days': (r['Date'] - ep_date).days, 'reason': 'Open'})

    return trades


def print_results(trades, label):
    print(f'\n{"="*70}')
    print(f' {label}')
    print(f'{"="*70}')

    if not trades:
        print('  No trades.')
        return

    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    total_pnl = sum(t['pnl'] for t in trades)
    gross_w = sum(t['pnl'] for t in wins) if wins else 0
    gross_l = abs(sum(t['pnl'] for t in losses)) if losses else 0.01
    pf = gross_w / gross_l if gross_l > 0 else float('inf')
    wr = len(wins) / len(trades) * 100
    avg_r = np.mean([t['pnlR'] for t in trades])

    print(f'  Trades: {len(trades)}  |  Wins: {len(wins)}  |  Losses: {len(losses)}')
    print(f'  Win Rate: {wr:.1f}%  |  Avg R: {avg_r:+.2f}R')
    print(f'  Total P&L: ${total_pnl:,.0f}  |  PF: {pf:.2f}')
    print(f'  Avg Win: ${np.mean([t["pnl"] for t in wins]):,.0f} ({np.mean([t["pnlR"] for t in wins]):+.1f}R)' if wins else '')
    print(f'  Avg Loss: ${np.mean([t["pnl"] for t in losses]):,.0f} ({np.mean([t["pnlR"] for t in losses]):+.1f}R)' if losses else '')

    # Yearly breakdown
    print(f'\n  {"Year":<6} {"Trades":>6} {"Wins":>5} {"WR%":>5} {"P&L":>10} {"AvgR":>6}')
    print(f'  {"-"*40}')
    by_year = {}
    for t in trades:
        y = t['entry'].year
        by_year.setdefault(y, []).append(t)
    for y in sorted(by_year):
        yt = by_year[y]
        yw = [t for t in yt if t['pnl'] > 0]
        print(f'  {y:<6} {len(yt):>6} {len(yw):>5} {len(yw)/len(yt)*100:>5.1f} ${sum(t["pnl"] for t in yt):>9,.0f} {np.mean([t["pnlR"] for t in yt]):>+5.1f}R')

    # Show trade list
    print(f'\n  {"#":<3} {"Dir":<6} {"Entry":<12} {"Exit":<12} {"P&L":>8} {"R":>6} {"Days":>5}')
    print(f'  {"-"*55}')
    for i, t in enumerate(trades):
        print(f'  {i+1:<3} {t["dir"]:<6} {str(t["entry"].date()):<12} {str(t["exit"].date()):<12} ${t["pnl"]:>7,.0f} {t["pnlR"]:>+5.1f}R {t["days"]:>5}d')


def main():
    df = pd.read_csv(DATA, parse_dates=['Date']).sort_values('Date').reset_index(drop=True)

    # Compute indicators
    df['sma20'] = df['Close'].rolling(20).mean()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean()
    df['ema20'] = df['Close'].ewm(span=20).mean()
    df['ema10'] = df['Close'].ewm(span=10).mean()
    tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['ema_trail'] = df['Close'].ewm(span=20).mean()

    configs = [
        # Config 1: Bounce off EMA 20, trend = above SMA 50
        {'ma_col': 'ema20', 'trend_col': 'sma50', 'bounce_atr': 0.5,
         'trail_ema': 20, 'trail_atr_buf': 1.0, 'trail_start_r': 2.5,
         'label': 'Bounce EMA20 (trend: >SMA50) | bounce 0.5 ATR'},

        # Config 2: Bounce off SMA 50, trend = above SMA 200
        {'ma_col': 'sma50', 'trend_col': 'sma200', 'bounce_atr': 0.5,
         'trail_ema': 20, 'trail_atr_buf': 1.0, 'trail_start_r': 2.5,
         'label': 'Bounce SMA50 (trend: >SMA200) | bounce 0.5 ATR'},

        # Config 3: Bounce off EMA 20, trend = above SMA 50, tighter bounce
        {'ma_col': 'ema20', 'trend_col': 'sma50', 'bounce_atr': 0.2,
         'trail_ema': 20, 'trail_atr_buf': 1.0, 'trail_start_r': 2.5,
         'label': 'Bounce EMA20 (trend: >SMA50) | bounce 0.2 ATR (tight)'},

        # Config 4: Bounce off SMA 50, trend = above SMA 50 (same MA)
        {'ma_col': 'sma50', 'trend_col': 'sma50', 'bounce_atr': 0.5,
         'trail_ema': 20, 'trail_atr_buf': 1.0, 'trail_start_r': 2.5,
         'label': 'Bounce SMA50 (trend: >SMA50) | bounce 0.5 ATR'},

        # Config 5: Bounce off EMA 20 with shorter trail start
        {'ma_col': 'ema20', 'trend_col': 'sma50', 'bounce_atr': 0.5,
         'trail_ema': 20, 'trail_atr_buf': 1.0, 'trail_start_r': 1.5,
         'label': 'Bounce EMA20 (trend: >SMA50) | trail at 1.5R'},

        # Config 6: Bounce off EMA 10 (faster), trend = above EMA 20
        {'ma_col': 'ema10', 'trend_col': 'ema20', 'bounce_atr': 0.3,
         'trail_ema': 20, 'trail_atr_buf': 1.0, 'trail_start_r': 2.5,
         'label': 'Bounce EMA10 (trend: >EMA20) | bounce 0.3 ATR'},
    ]

    print('MA BOUNCE STRATEGY — SPY BACKTEST')
    print(f'Data: {df["Date"].iloc[0].date()} to {df["Date"].iloc[-1].date()}')
    print(f'Risk: ${RISK}/trade | Stop: {SL_ATR}x ATR | Longs only')

    for cfg in configs:
        label = cfg.pop('label')
        trades = run_backtest(df, cfg, label)
        print_results(trades, label)
        cfg['label'] = label  # restore

    # === Compare to Trend Rider on SPY ===
    print(f'\n{"="*70}')
    print(f' TREND RIDER v1 ON SPY (from dashboard data)')
    print(f'{"="*70}')
    import json
    d = json.load(open('/workspaces/jas/dashboard/public/data.json'))
    spy_trades = [t for t in d['stocks']['SPY']['trades'] if t['exitDate']]
    tw = [t for t in spy_trades if t['pnlDollar'] > 0]
    tl = [t for t in spy_trades if t['pnlDollar'] <= 0]
    total = sum(t['pnlDollar'] for t in spy_trades)
    gw = sum(t['pnlDollar'] for t in tw) if tw else 0
    gl = abs(sum(t['pnlDollar'] for t in tl)) if tl else 0.01
    print(f'  Trades: {len(spy_trades)}  |  Wins: {len(tw)}  |  Losses: {len(tl)}')
    print(f'  Win Rate: {len(tw)/len(spy_trades)*100:.1f}%  |  Avg R: {np.mean([t["pnlR"] for t in spy_trades]):+.2f}R')
    print(f'  Total P&L: ${total:,.0f}  |  PF: {gw/gl:.2f}')


if __name__ == '__main__':
    main()
