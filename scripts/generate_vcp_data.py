#!/usr/bin/env python3
"""
VCP (Volatility Contraction Pattern) Strategy — Backtest Generator
====================================================================
Based on Mark Minervini's VCP concept.

Entry Logic:
  - Stock must be in a Stage 2 uptrend:
    * Close > SMA(50) > SMA(200) (both MAs rising or price above both)
    * Close above SMA(50)
  - Volatility contracting:
    * Current ATR(14) < SMA(20) of ATR (ATR is below its own average = contracting)
    * Recent range (10-bar high - 10-bar low) is narrower than range from 20 bars ago
  - Price near the top of the consolidation:
    * Close within 5% of the 50-bar high (coiled near highs)
  - Breakout trigger:
    * Close breaks above the highest high of the last 10 bars
  - Volume confirmation:
    * Volume > 1.0× average (not requiring a spike, just not dead volume)
  - Bar not overextended (range ≤ 2.5×ATR)

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
OUT = Path("/workspaces/jas/dashboard/public/vcp_data.json")
RISK = 100.0

# Parameters
SL_ATR = 1.0
TRAIL_ATR_BUF = 1.0
TRAIL_START_R = 2.5
NEAR_HIGH_PCT = 0.08       # within 8% of 50-bar high
BREAKOUT_LOOKBACK = 10     # break above this many bars' high
CONTRACTION_LOOKBACK = 15  # compare current range vs range from N bars ago
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
    df['sma200'] = df['Close'].rolling(200).mean()
    tr = np.maximum(df['High'] - df['Low'],
        np.maximum(abs(df['High'] - df['Close'].shift(1)),
                   abs(df['Low'] - df['Close'].shift(1))))
    df['atr'] = tr.rolling(14).mean()
    df['atr_sma'] = df['atr'].rolling(20).mean()
    df['ema_trail'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['vol_sma'] = df['Volume'].rolling(20).mean()
    df['high_50'] = df['High'].rolling(50).max()
    df['high_10'] = df['High'].rolling(BREAKOUT_LOOKBACK).max()
    # Range contraction: compare current 10-bar range vs 20 bars ago
    df['range_10'] = df['High'].rolling(10).max() - df['Low'].rolling(10).min()
    df['range_10_prev'] = df['range_10'].shift(CONTRACTION_LOOKBACK)
    df['fSma'] = df['ema20']
    df['sSma'] = df['sma50']
    return df


def backtest_vcp(df, name):
    df = add_indicators(df)
    trades = []
    pos = 0
    ep = er = tsl = 0.0
    last_entry_bar = -100
    last_breakout_level = 0.0

    for i in range(1, len(df)):
        r = df.iloc[i]
        prev = df.iloc[i - 1]
        atr = r['atr']

        if (pd.isna(atr) or atr <= 0 or pd.isna(r['sma50']) or pd.isna(r['sma200'])
            or pd.isna(r['atr_sma']) or pd.isna(r['high_50']) or pd.isna(r['high_10'])
            or pd.isna(r['range_10']) or pd.isna(r['range_10_prev'])):
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

        # ── Flat: look for VCP breakout ──
        if i - last_entry_bar < COOLDOWN:
            continue

        # Stage 2 uptrend: close > SMA50
        if r['Close'] <= r['sma50']:
            continue

        # Volatility contracting: ATR < its SMA
        if r['atr'] >= r['atr_sma']:
            continue

        # Range contracting: current 10-bar range < range from 20 bars ago
        if r['range_10'] >= r['range_10_prev']:
            continue

        # Near the highs: close within 5% of 50-bar high
        if r['Close'] < r['high_50'] * (1 - NEAR_HIGH_PCT):
            continue

        # Breakout: close above highest high of last 10 bars (shifted by 1 to avoid same-bar)
        breakout_level = prev['high_10'] if not pd.isna(prev['high_10']) else r['high_10']
        if r['Close'] <= breakout_level:
            continue

        # Prevent re-entry at same breakout level
        if abs(breakout_level - last_breakout_level) < 0.5 * atr:
            continue

        # Volume: at least 0.8× average (not dead)
        if pd.notna(r['vol_sma']) and r['Volume'] < r['vol_sma'] * 0.8:
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
        last_breakout_level = breakout_level

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
    'strategy': 'VCP Breakout v1',
    'entry': 'Volatility Contraction Pattern breakout (Minervini)',
    'nearHighPct': NEAR_HIGH_PCT,
    'breakoutLookback': BREAKOUT_LOOKBACK,
    'slAtrMult': SL_ATR,
    'trailEmaLen': 20, 'trailAtrBuf': TRAIL_ATR_BUF,
    'trailStartR': TRAIL_START_R,
    'riskPerTrade': RISK
}}

for f in sorted(DATA_DIR.glob("*.csv")):
    name = f.stem.replace("_daily_data - Sheet1", "").replace("_data", "").upper()
    trades, prices = backtest_vcp(load(f), name)
    all_data['stocks'][name] = {'trades': trades, 'prices': prices}
    all_data['allTrades'].extend(trades)
    print(f"{name}: {len(trades)} trades, {len(prices)} price bars")

all_data['allTrades'].sort(key=lambda t: t['entryDate'])
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(all_data))
print(f"\nWritten {OUT} ({OUT.stat().st_size // 1024}KB)")
