# Weekly ORB v3 — Dual SMA Crossover Strategy

A simple, mechanical trading strategy optimized for **SPY** (daily timeframe).
Best suited for index ETFs with clean trends. Not recommended for individual stocks without parameter adjustments.

---

## Entry Rules

1. **LONG**: Fast SMA (10) crosses above Slow SMA (50)
2. **SHORT**: Fast SMA (10) crosses below Slow SMA (50)

**Additional filters:**
- One cross = one trade. Must see opposite cross before same direction triggers again.
- Price must be within 1.5×ATR of the fast SMA (no chasing extended moves).
- Cooloff: skip 1 week after a stop loss.

---

## Exit Rules

### Stop Loss
- Set at **1.5 × ATR** below entry (long) or above entry (short)
- Once trade reaches profit of **Trail Starts At (R)** (default 1R), stop tightens to EMA(20) - 0.5×ATR
- Stop only moves in your favor, never loosens

### No Fixed Take Profit
- No fixed TP ceiling. Ride the trend until the trailing EMA stop gets hit.
- This lets big winners run as far as the trend goes.

---

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| Fast SMA | 10 | Short-term trend |
| Slow SMA | 50 | Long-term trend |
| Max Distance (×ATR) | 1.5 | Skip entry if price too far from fast SMA |
| Cooloff Weeks | 1 | Weeks to skip after a loss |
| Risk/Trade | $100 | Dollar risk per trade |
| Stop Loss (×ATR) | 1.5 | Stop distance |
| Trail EMA | 20 | EMA for trailing stop |
| Trail ATR Buffer | 0.5 | Cushion below trail EMA |
| Trail Starts At (R) | 1.0 | Profit level where trailing activates |

---

## How It Works (Plain English)

> Enter when the fast moving average crosses the slow one — that means the short-term trend just flipped.
> Only enter if price hasn't already run away from the MA. One cross = one trade, no repeats.
> Risk 1.5×ATR. No fixed profit target. Ride with the 20 EMA trail until the trend breaks.
> Skip a week after a loss.

---

## Why This Works on SPY But Not Individual Stocks

- **SPY** is an index ETF — smooth trends, low gap risk, less noise. MA crossovers catch real trend shifts.
- **Individual stocks** (GOOGL, TSLA, etc.) are choppier — earnings gaps, news, more whipsaws. The 10/50 cross is too sensitive.
- For stocks, try: longer MAs (20/100), wider stop (2.0-2.5×ATR), or don't use this strategy at all.

---

## Disclaimer
This script is provided for educational and research purposes only. Trading involves significant risk. Always backtest strategies thoroughly before considering live deployment.
