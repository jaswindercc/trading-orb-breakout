#!/usr/bin/env python3
"""Generate MA Bounce backtest JSON for the React dashboard. SPY + all 12 stocks."""
import pandas as pd, numpy as np, json
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/bounce_data.json")
RISK = 100.0

def load(fp):
    df = pd.read_csv(fp)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    for c in ['Open','High','Low','Close','Volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna(subset=['Open','High','Low','Close'])

def add_indicators(df):
    df = df.copy()
    df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['sma50'] = df['Close'].rolling(50).mean()
    df['sma200'] = df['Close'].rolling(200).mean()
    tr = np.maximum(df['High']-df['Low'],
        np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['atr'] = tr.rolling(14).mean()
    df['ema_trail'] = df['Close'].ewm(span=20, adjust=False).mean()
    # For price chart: also compute fast/slow SMA for consistency
    df['fSma'] = df['ema20']   # show EMA20 as "fast" line
    df['sSma'] = df['sma50']   # show SMA50 as "slow" line
    return df

def backtest_bounce(df, name):
    """MA Bounce: enter long when price pulls back to EMA20 and bounces, trend = above SMA50."""
    SL_ATR = 1.0
    BOUNCE_ATR = 0.5
    TRAIL_ATR_BUF = 1.0
    TRAIL_START_R = 2.5

    df = add_indicators(df)
    trades = []
    pos = 0
    ep = er = tsl = 0.0
    ep_date = None
    qty = 1

    for i in range(1, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i-1]
        atr = r['atr']

        if pd.isna(atr) or atr <= 0 or pd.isna(r['ema20']) or pd.isna(r['sma50']):
            continue

        # ── In a trade: check stop / trail ──
        if pos == 1:
            hit_sl = False
            xp = 0.0
            reason = ''

            if r['Low'] <= tsl:
                xp = tsl; hit_sl = True; reason = 'SL'

            if not hit_sl:
                curr_r = (r['Close'] - ep) / er if er > 0 else 0
                if curr_r >= TRAIL_START_R:
                    ema_trail = r['ema_trail'] - TRAIL_ATR_BUF * atr
                    if ema_trail > tsl:
                        tsl = ema_trail
                if r['Low'] <= tsl:
                    xp = tsl; hit_sl = True; reason = 'Trail'

            if hit_sl:
                t = trades[-1]
                t['exitDate'] = r['Date'].strftime('%Y-%m-%d')
                t['exitPrice'] = round(xp, 2)
                pnl_r = (xp - ep) / er if er > 0 else 0
                t['pnlR'] = round(pnl_r, 2)
                t['pnlDollar'] = round(pnl_r * RISK, 2)
                t['exitReason'] = reason
                ed = pd.to_datetime(t['entryDate'])
                t['durationDays'] = int((r['Date'] - ed).days)
                pos = 0
            continue

        # ── Flat: look for long entry ──
        ma_val = r['ema20']
        trend_val = r['sma50']

        # Must be in uptrend
        if r['Close'] <= trend_val:
            continue

        # Previous bar dipped near EMA20
        touched = prev['Low'] <= ma_val + BOUNCE_ATR * atr
        # Today closed above EMA20
        bounced = r['Close'] > ma_val
        # Not already way above
        not_too_far = r['Close'] - ma_val <= 3.0 * atr
        # Not a gap bar
        small_bar = (r['High'] - r['Low']) <= 2.0 * atr

        if touched and bounced and not_too_far and small_bar:
            sl = r['Close'] - SL_ATR * atr
            rk = r['Close'] - sl
            qty = max(1, round(RISK / rk)) if rk > 0 else 1
            pos = 1
            ep = r['Close']
            er = rk
            tsl = sl
            ep_date = r['Date']
            trades.append({
                'stock': name, 'dir': 'LONG',
                'entryDate': r['Date'].strftime('%Y-%m-%d'),
                'entryPrice': round(r['Close'], 2),
                'sl': round(sl, 2), 'risk': round(rk, 2), 'qty': qty,
                'exitDate': '', 'exitPrice': 0, 'pnlR': 0, 'pnlDollar': 0,
                'exitReason': '', 'durationDays': 0
            })

    # Close open trade
    if pos != 0 and trades:
        t = trades[-1]
        l = df.iloc[-1]
        t['exitDate'] = l['Date'].strftime('%Y-%m-%d')
        t['exitPrice'] = round(l['Close'], 2)
        pnl_r = (l['Close'] - ep) / er if er > 0 else 0
        t['pnlR'] = round(pnl_r, 2)
        t['pnlDollar'] = round(pnl_r * RISK, 2)
        t['exitReason'] = 'Open'
        ed = pd.to_datetime(t['entryDate'])
        t['durationDays'] = int((l['Date'] - ed).days)

    # Price series
    prices = []
    for _, row in df.iterrows():
        if pd.notna(row['ema20']) and pd.notna(row['sma50']):
            prices.append({
                'date': row['Date'].strftime('%Y-%m-%d'),
                'close': round(row['Close'], 2),
                'fSma': round(row['ema20'], 2),
                'sSma': round(row['sma50'], 2)
            })
    return trades, prices


all_data = {'stocks': {}, 'allTrades': [], 'settings': {
    'bounceMA': 'EMA 20', 'trendMA': 'SMA 50',
    'bounceATR': 0.5, 'slAtrMult': 1.0,
    'trailEmaLen': 20, 'trailAtrBuf': 1.0, 'trailStartR': 2.5,
    'riskPerTrade': 100,
    'strategy': 'MA Bounce v1'
}}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1","").replace("_data","").upper()
    trades, prices = backtest_bounce(load(f), name)
    all_data['stocks'][name] = {'trades': trades, 'prices': prices}
    all_data['allTrades'].extend(trades)
    print(f"{name}: {len(trades)} trades, {len(prices)} price bars")

all_data['allTrades'].sort(key=lambda t: t['entryDate'])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_data))
print(f"\nWritten {OUT} ({OUT.stat().st_size//1024}KB)")
