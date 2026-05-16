#!/usr/bin/env python3
"""
VOLUME BREAKOUT Strategy — Backtest Generator
================================================
Entry Logic:
  - Volume spike on a bullish candle in an uptrend
  - Volume > 1.5× SMA(20) of volume (clear institutional interest)
  - Bullish candle: close > open AND close > previous close
  - Price above SMA(50) (trend filter)
  - Price at or near a new 20-day high (within 2% of the 20-bar high)
    → Confirms this is a volume-powered breakout, not just noise
  - Bar not overextended (range ≤ 2.5×ATR)
  - Cooldown: 5 bars between entries

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
OUT = Path("/workspaces/jas/dashboard/public/volume_data.json")
RISK = 100.0

# Parameters
SL_ATR = 1.0
TRAIL_ATR_BUF = 1.0
TRAIL_START_R = 2.5
VOL_MULT = 1.5         # volume must be > this × average
NEAR_HIGH_PCT = 0.02   # within 2% of 20-bar high
HIGH_LOOKBACK = 20
COOLDOWN = 5


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
    df['vol_sma'] = df['Volume'].rolling(20).mean()
    df['high_20'] = df['High'].rolling(HIGH_LOOKBACK).max()
    df['fSma'] = df['ema20']
    df['sSma'] = df['sma50']
    return df


def backtest_volume(df, name):
    df = add_indicators(df)
    trades = []
    pos = 0
    ep = er = tsl = 0.0
    last_entry_bar = -100

    for i in range(1, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]
        atr = r['atr']

        if (pd.isna(atr) or atr <= 0 or pd.isna(r['sma50'])
            or pd.isna(r['vol_sma']) or pd.isna(r['high_20'])):
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

        # ── Flat: look for volume breakout entry ──
        if i - last_entry_bar < COOLDOWN:
            continue

        # Trend filter: above SMA50
        if r['Close'] <= r['sma50']:
            continue

        # Volume spike: > 1.5× average
        if r['vol_sma'] <= 0:
            continue
        if r['Volume'] < VOL_MULT * r['vol_sma']:
            continue

        # Bullish candle: close > open AND close > prev close
        if r['Close'] <= r['Open']:
            continue
        if r['Close'] <= prev['Close']:
            continue

        # Near 20-bar high: within 2%
        if r['Close'] < r['high_20'] * (1 - NEAR_HIGH_PCT):
            continue

        # Bar not overextended
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
    'strategy': 'Volume Breakout v1',
    'entry': 'Volume spike (>1.5× avg) on bullish candle near 20-bar high',
    'volMult': VOL_MULT,
    'nearHighPct': NEAR_HIGH_PCT,
    'highLookback': HIGH_LOOKBACK,
    'slAtrMult': SL_ATR,
    'trailEmaLen': 20, 'trailAtrBuf': TRAIL_ATR_BUF,
    'trailStartR': TRAIL_START_R,
    'riskPerTrade': RISK
}}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
    trades, prices = backtest_volume(load(f), name)
    all_data['stocks'][name] = {'trades': trades, 'prices': prices}
    all_data['allTrades'].extend(trades)
    print(f"{name}: {len(trades)} trades, {len(prices)} price bars")

all_data['allTrades'].sort(key=lambda t: t['entryDate'])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_data))
print(f"\nWritten {OUT} ({OUT.stat().st_size // 1024}KB)")
