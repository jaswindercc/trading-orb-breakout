#!/usr/bin/env python3
"""
TRENDLINE BOUNCE Strategy — Backtest Generator
==================================================
Entry Logic:
  - Identify rising trendline by connecting the two most recent pivot lows (swing lows)
  - Pivot low = bar with lowest low among 5 bars on each side (lookback=5)
  - Trendline must have positive slope (rising)
  - Price must be above SMA(50) (trend filter)
  - Previous bar's low touched or came within 0.5×ATR of the trendline value
  - Current bar closes above the trendline (bounce confirmation)
  - Bar not overextended (range ≤ 2×ATR, price ≤ 3×ATR from trendline)
  - Cooldown: at least 5 bars between entries

Exit Logic (same as all strategies):
  - Initial SL: 1× ATR below entry
  - Trail: EMA(20) − 1×ATR, activates at 2.5R
  - No fixed TP for longs

Risk:
  - $100 per trade, position sized by ATR stop distance
"""
import pandas as pd, numpy as np, json
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/trendline_data.json")
RISK = 100.0

# Parameters
PIVOT_LOOKBACK = 5     # bars on each side for pivot detection
MIN_PIVOTS_DIST = 10   # minimum bars between pivot lows used for trendline
SL_ATR = 1.0
BOUNCE_ATR = 0.5       # how close price must get to trendline
TRAIL_ATR_BUF = 1.0
TRAIL_START_R = 2.5
COOLDOWN = 5           # min bars between entries


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
    tr = np.maximum(df['High'] - df['Low'],
        np.maximum(abs(df['High'] - df['Close'].shift(1)),
                   abs(df['Low'] - df['Close'].shift(1))))
    df['atr'] = tr.rolling(14).mean()
    df['ema_trail'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['fSma'] = df['ema20']
    df['sSma'] = df['sma50']
    return df


def find_pivot_lows(df, lookback=PIVOT_LOOKBACK):
    """Find pivot lows: bar where Low is lowest within lookback bars on each side."""
    pivots = []
    for i in range(lookback, len(df) - lookback):
        low_i = df.iloc[i]['Low']
        is_pivot = True
        for j in range(i - lookback, i + lookback + 1):
            if j == i:
                continue
            if df.iloc[j]['Low'] < low_i:
                is_pivot = False
                break
        if is_pivot:
            pivots.append(i)
    return pivots


def get_trendline_value(pivot1_idx, pivot1_low, pivot2_idx, pivot2_low, current_idx):
    """Calculate trendline value at current_idx given two pivot points."""
    if pivot2_idx == pivot1_idx:
        return pivot2_low
    slope = (pivot2_low - pivot1_low) / (pivot2_idx - pivot1_idx)
    return pivot2_low + slope * (current_idx - pivot2_idx)


def backtest_trendline(df, name):
    df = add_indicators(df)
    pivot_indices = find_pivot_lows(df)
    trades = []
    pos = 0
    ep = er = tsl = 0.0
    last_entry_bar = -100

    for i in range(1, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]
        atr = r['atr']

        if pd.isna(atr) or atr <= 0 or pd.isna(r['sma50']) or pd.isna(r['ema20']):
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

        # ── Flat: look for trendline bounce entry ──
        # Cooldown check
        if i - last_entry_bar < COOLDOWN:
            continue

        # Trend filter: above SMA50
        if r['Close'] <= r['sma50']:
            continue

        # Need at least 2 pivot lows BEFORE current bar
        recent_pivots = [p for p in pivot_indices if p < i - 1 and p >= i - 100]
        if len(recent_pivots) < 2:
            continue

        # Use two most recent pivot lows
        p2_idx = recent_pivots[-1]
        p1_idx = recent_pivots[-2]

        # Ensure minimum distance between pivots
        if p2_idx - p1_idx < MIN_PIVOTS_DIST:
            # Try to find a more distant pivot
            if len(recent_pivots) >= 3:
                p1_idx = recent_pivots[-3]
                if p2_idx - p1_idx < MIN_PIVOTS_DIST:
                    continue
            else:
                continue

        p1_low = df.iloc[p1_idx]['Low']
        p2_low = df.iloc[p2_idx]['Low']

        # Trendline must be rising
        slope = (p2_low - p1_low) / (p2_idx - p1_idx)
        if slope <= 0:
            continue

        # Calculate trendline value at previous bar and current bar
        tl_prev = get_trendline_value(p1_idx, p1_low, p2_idx, p2_low, i - 1)
        tl_curr = get_trendline_value(p1_idx, p1_low, p2_idx, p2_low, i)

        # Trendline should be below current price (not broken)
        if tl_curr <= 0 or tl_curr > r['Close']:
            continue

        # Previous bar dipped near trendline (within BOUNCE_ATR × ATR)
        touched = prev['Low'] <= tl_prev + BOUNCE_ATR * atr

        # Current bar bounced: closed above trendline
        bounced = r['Close'] > tl_curr

        # Not overextended
        not_too_far = r['Close'] - tl_curr <= 3.0 * atr
        small_bar = (r['High'] - r['Low']) <= 2.0 * atr

        if touched and bounced and not_too_far and small_bar:
            sl = r['Close'] - SL_ATR * atr
            rk = r['Close'] - sl
            if rk <= 0:
                continue
            qty = max(1, round(RISK / rk))
            pos = 1
            ep = r['Close']
            er = rk
            tsl = sl
            last_entry_bar = i
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
    'strategy': 'Trendline Bounce v1',
    'entry': 'Pivot-low trendline bounce',
    'pivotLookback': PIVOT_LOOKBACK,
    'bounceATR': BOUNCE_ATR,
    'slAtrMult': SL_ATR,
    'trailEmaLen': 20, 'trailAtrBuf': TRAIL_ATR_BUF,
    'trailStartR': TRAIL_START_R,
    'riskPerTrade': RISK
}}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
    trades, prices = backtest_trendline(load(f), name)
    all_data['stocks'][name] = {'trades': trades, 'prices': prices}
    all_data['allTrades'].extend(trades)
    print(f"{name}: {len(trades)} trades, {len(prices)} price bars")

all_data['allTrades'].sort(key=lambda t: t['entryDate'])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_data))
print(f"\nWritten {OUT} ({OUT.stat().st_size // 1024}KB)")
