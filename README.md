# Weekly ORB v3 — Dual SMA Crossover Strategy

A simple, mechanical weekly trading strategy for SPY (daily timeframe).

---

## Entry Rules

Only **two conditions** for entry:

1. **LONG**: Fast SMA (10) crosses above Slow SMA (50)
2. **SHORT**: Fast SMA (10) crosses below Slow SMA (50)

**Filters** (not entry conditions — these prevent overtrading):
- One trade per week max
- No entries on Friday
- Skip 1 week after a stop loss (cooloff)

---

## Exit Rules

### Stop Loss
- Set at **1.5 × ATR** below entry (long) or above entry (short)
- Once trade reaches **+1R profit**, stop tightens to EMA(20) - 0.5×ATR
- Stop only moves in your favor, never loosens

### Take Profit (Hybrid)
- Starts as a fixed **3:1 R:R** target
- Once trade reaches **+2R profit**, the fixed TP is **removed**
- From that point, only the EMA(20) trailing stop can exit the trade
- This lets big winners run past 3R

### Friday Close
- If it's Friday and profit is **less than 0.5R**, close the trade
- If profit is **≥ 0.5R** on Friday, hold through the weekend

### Cooloff
- After a losing trade (stopped out), skip the next week entirely
- Reduces consecutive losses

---

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| Fast SMA | 10 | Short-term trend |
| Slow SMA | 50 | Long-term trend |
| Cooloff Weeks | 1 | Weeks to skip after a loss |
| R:R | 3.0 | Initial take profit target |
| Risk/Trade | $100 | Dollar risk per trade |
| Stop Loss (×ATR) | 1.5 | Stop distance |
| Trail EMA | 20 | EMA for trailing stop |
| Trail ATR Buffer | 0.5 | Cushion below trail EMA |
| Remove TP At (R) | 2.0 | Remove fixed TP at this profit level |
| Friday Hold Min (R) | 0.5 | Min profit to hold over weekend |

---

## How It Works (Plain English)

> Enter when the fast moving average crosses the slow one — that means the short-term trend just flipped.
> Risk 1.5×ATR. Target 3:1. But if the trade is running hot past 2R, rip the target off and ride it with the 20 EMA until the trend actually breaks.
> Skip a week after a loss. Don't hold garbage over weekends.

---

## Disclaimer
This script is provided for educational and research purposes only. Trading involves significant risk. Always backtest strategies thoroughly before considering live deployment.
