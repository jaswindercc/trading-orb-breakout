#!/usr/bin/env python3
"""
FAIR VALUE GAP (FVG) Strategy — Backtest Generator
====================================================
Entry Logic:
  - Detect bullish Fair Value Gaps (FVGs):
    A bullish FVG exists when candle[i-2].high < candle[i].low
    (gap between the high of 2 bars ago and the low of current bar,
     with candle[i-1] being the big impulsive move that created the gap)
  - Track open (unfilled) FVGs
  - Entry: price pulls back INTO the FVG zone and shows a bullish close
    (low enters the gap zone AND close is above the midpoint of the gap)
  - FVG must have been created with a strong candle (bar[i-1] body > 0.5×ATR)
  - Price must be above SMA(50) (trend filter)
  - FVG must be < 30 bars old (stale gaps are less reliable)
  - Remove FVG once filled (low goes below FVG bottom) or used for entry

Exit Logic (same as all strategies):
  - Initial SL: 1× ATR below entry
  - Trail: EMA(20) − 1×ATR, activates at 2.5R
  - No fixed TP

Risk:
  - $100 per trade
"""
import pandas as pd, numpy as np, json
from pathlib import Path

DATA_DIR = Path("/workspaces/jas/data")
OUT = Path("/workspaces/jas/dashboard/public/fvg_data.json")
RISK = 100.0

# Parameters
SL_ATR = 1.0
TRAIL_ATR_BUF = 1.0
TRAIL_START_R = 2.5
FVG_MAX_AGE = 30       # bars: discard FVGs older than this
MIN_BODY_ATR = 0.5     # minimum body size of impulse candle (in ATR)
COOLDOWN = 3           # bars between entries


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


def backtest_fvg(df, name):
    df = add_indicators(df)
    trades = []
    pos = 0
    ep = er = tsl = 0.0
    last_entry_bar = -100

    # Track open bullish FVGs: list of (bar_index_created, gap_top, gap_bottom)
    open_fvgs = []

    for i in range(2, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]
        prev2 = df.iloc[i - 2]
        atr = r['atr']

        if pd.isna(atr) or atr <= 0 or pd.isna(r['sma50']) or pd.isna(r['ema20']):
            continue

        # ── Detect new bullish FVG ──
        # Bullish FVG: bar[i-2].high < bar[i].low (gap between them)
        # Impulse candle is bar[i-1] (the big move)
        gap_bottom = prev2['High']  # top of bar 2 ago
        gap_top = r['Low']          # bottom of current bar

        if gap_top > gap_bottom:
            # There IS a gap — check if impulse candle was strong
            impulse_body = abs(prev['Close'] - prev['Open'])
            prev_atr = df.iloc[i-1]['atr'] if not pd.isna(df.iloc[i-1]['atr']) else atr
            if impulse_body >= MIN_BODY_ATR * prev_atr:
                open_fvgs.append({
                    'created': i,
                    'top': gap_top,
                    'bottom': gap_bottom,
                })

        # ── Remove stale or filled FVGs ──
        open_fvgs = [fvg for fvg in open_fvgs
                     if i - fvg['created'] <= FVG_MAX_AGE
                     and r['Low'] >= fvg['bottom']]  # not yet filled below bottom

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

        # ── Flat: look for FVG entry ──
        if i - last_entry_bar < COOLDOWN:
            continue

        # Trend filter
        if r['Close'] <= r['sma50']:
            continue

        # Check if price pulled back into any open FVG
        entered_fvg = None
        for fvg in open_fvgs:
            # Don't enter on the same bar the FVG was created
            if fvg['created'] >= i - 1:
                continue
            # Price low dipped into the FVG zone
            if r['Low'] <= fvg['top'] and r['Low'] >= fvg['bottom']:
                # Bullish close: close above the midpoint of the gap
                midpoint = (fvg['top'] + fvg['bottom']) / 2
                if r['Close'] > midpoint:
                    entered_fvg = fvg
                    break

        if entered_fvg is None:
            continue

        # Bar size filter
        if (r['High'] - r['Low']) > 2.5 * atr:
            continue

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

        # Remove used FVG
        open_fvgs.remove(entered_fvg)

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
    'strategy': 'FVG (Fair Value Gap) v1',
    'entry': 'Pullback into bullish FVG zone with bullish close',
    'fvgMaxAge': FVG_MAX_AGE,
    'minBodyAtr': MIN_BODY_ATR,
    'slAtrMult': SL_ATR,
    'trailEmaLen': 20, 'trailAtrBuf': TRAIL_ATR_BUF,
    'trailStartR': TRAIL_START_R,
    'riskPerTrade': RISK
}}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
    trades, prices = backtest_fvg(load(f), name)
    all_data['stocks'][name] = {'trades': trades, 'prices': prices}
    all_data['allTrades'].extend(trades)
    print(f"{name}: {len(trades)} trades, {len(prices)} price bars")

all_data['allTrades'].sort(key=lambda t: t['entryDate'])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_data))
print(f"\nWritten {OUT} ({OUT.stat().st_size // 1024}KB)")
