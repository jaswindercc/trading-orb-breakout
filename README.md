# Weekly ORB — Round Level Breakout

## Setup (Every Monday)

1. Note the **weekly open** price (first candle of the week)
2. **Resistance** = nearest round number ABOVE the open
3. **Support** = nearest round number BELOW the open
4. If open lands exactly on a round number, push one interval out

Example: open = 558, interval = 10 → Resistance = 560, Support = 550

---

## Entry Rules

1. Check each daily candle **Monday and Tuesday** (configurable)
2. **LONG** if daily candle **closes above resistance** AND close is above the **20 EMA**
3. **SHORT** if daily candle **closes below support** AND close is below the **20 EMA**
4. If price wicks through both levels but closes above resistance → Long. Closes below support → Short
5. Entry fills at the **bar's close price**
6. **One trade per week max**
7. **No entries on Friday**

---

## Exit Rules

| Exit Type | Long | Short |
|-----------|------|-------|
| **Stop Loss (Candle)** | Entry bar's low | Entry bar's high |
| **Stop Loss (Round Level)** | Support level | Resistance level |
| **Take Profit** | Entry + (risk × R:R) | Entry − (risk × R:R) |
| **Friday Close** | Close at Friday's close | Close at Friday's close |

- First exit to trigger wins (SL, TP, or Friday close)
- **Never hold past Friday**

---

## Settings

| Setting | Default | Notes |
|---------|---------|-------|
| R:R | 1:3 | Reward multiple of risk |
| Risk/Trade | $100 | Max dollar risk per trade |
| Round Interval | 10 | Round number spacing (10 best for SPY) |
| EMA | 20 | Trend filter (0 = disabled) |
| SL Type | Candle | "Candle" (tighter, optimal) or "Round Level" |
| Last Entry Day | Tue (3) | Latest day to enter (2=Mon, 3=Tue, 4=Wed, 5=Thu) |
- [ ] Improved handling of "Boomer" stocks (low volatility).

---

## Disclaimer
This script is provided for educational and research purposes only. Trading involves significant risk. Always backtest strategies thoroughly before considering live deployment.
