# Trend Rider v1 — Asymmetric Long-Biased SMA Crossover

A mechanical trend-following strategy on the **daily timeframe**. Long-biased with filtered shorts.
Backtested across 12 stocks: SPY, AAPL, NVDA, TSLA, META, GOOGL, AMD, ADBE, BA, CRM, MSFT, SNOW (Jan 2021 – May 2026).

---

## Strategy Summary

| | Long | Short |
|---|---|---|
| **Entry** | SMA(10) crosses above SMA(50) | SMA(10) crosses below SMA(50) + price < SMA(200) + ATR contracting |
| **Stop** | 1.0 × ATR below entry | 1.0 × ATR above entry |
| **Exit** | EMA(20) trailing stop at 2.5R | Fixed TP at 3R |
| **Risk** | $100 per trade | $100 per trade |

---

## Entry Rules

- **Long:** SMA(10) crosses above SMA(50)
- **Short:** SMA(10) crosses below SMA(50), price below SMA(200), ATR < SMA(ATR, 20)
- Price within 3.0 × ATR of fast SMA (don't chase)
- Bar range ≤ 2.0 × ATR (skip gap/news bars)
- One cross = one trade (need opposite cross before same direction fires again)

---

## Exit Rules

- **Longs:** Trailing EMA(20) − 1.0×ATR stop, activates at 2.5R. No cap on upside.
- **Shorts:** Fixed take profit at 3R. Stop loss only, no trailing.
- If stopped before trail/TP: lose exactly $100 (−1R)

---

## Position Sizing

- Risk $100 per trade
- Stop = 1.0 × ATR(14)
- Quantity = $100 ÷ stop distance (min 1 share)

---

## Settings

| Setting | Value |
|---------|-------|
| Fast SMA | 10 |
| Slow SMA | 50 |
| SMA 200 (short filter) | 200 |
| ATR Contraction SMA | 20 |
| Stop Loss | 1.0 × ATR |
| Trail EMA | 20 |
| Trail ATR Buffer | 1.0 |
| Trail Starts At | 2.5R |
| Short TP | 3.0R |
| Risk Per Trade | $100 |

---

## Project Structure

```
├── pine_trend_rider_v1       # TradingView PineScript v5 strategy
├── scripts/
│   ├── generate_data.py      # Backtest data generator → data.json
│   ├── atr_short_filter_analysis.py  # ATR analysis (10-part)
│   └── compare_atr_filter.py # A/B: baseline vs ATR contraction filter
├── dashboard/                # React dashboard (Vite + Recharts)
│   ├── src/pages/            # Strategy overview + per-stock pages
│   ├── src/components/       # Charts, tables, KPI cards
│   └── public/data.json      # Generated backtest data
├── data/                     # Daily OHLCV CSVs (2021-2026)
└── README.md
```

---

## Dashboard

```bash
# Generate data
python3 scripts/generate_data.py

# Run dashboard
cd dashboard && npm install && npm run dev
```

Per-stock pages with equity curves, drawdown charts, price charts with trade markers, quarterly/monthly/yearly breakdowns, and full trade logs.

---

## Disclaimer

For **educational and research purposes only**. Past backtest results do not guarantee future performance. Trading involves risk of loss.
