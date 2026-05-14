# SMA Crossover v3 — Multi-Stock Trend Following Strategy

A fully mechanical, dual moving-average crossover strategy running on the **daily timeframe**.
Optimized across 7 stocks: **SPY, AAPL, AMD, GOOGL, META, NVDA, TSLA** (Jan 2021 – May 2026).

---

## Strategy Logic At A Glance

```
IF fast SMA crosses above slow SMA → go LONG
IF fast SMA crosses below slow SMA → go SHORT
Risk $100 per trade. No fixed profit target. Ride winners with a trailing EMA stop.
```

---

## Entry Rules (When to Get In)

A trade triggers on the **exact bar** that a crossover happens. Both longs and shorts.

### Long Entry
1. The **SMA(10)** crosses **above** the **SMA(50)** — short-term momentum just flipped bullish.
2. Price must be within **3.0 × ATR(14)** of the fast SMA — don't chase if price already ran.
3. Today's candle range (high − low) must be ≤ **3.0 × ATR** — skip abnormally large bars.
4. Must be **flat** (no open position).

### Short Entry
Same rules, but SMA(10) crosses **below** SMA(50).

### One Cross = One Trade
- Each crossover can only fire **once**. You must see the opposite cross before the same direction can trigger again.
- Example: SMA(10) crosses above SMA(50) → long. Even if the fast SMA dips and re-crosses above again without first crossing below, no new long fires. You need a bearish cross first, then the next bullish cross is valid.

### Why These Filters Exist
| Filter | What It Prevents |
|--------|-----------------|
| Max Distance 3.0×ATR | Entering after a huge move when the cross is "stale" — price already far from the MA |
| Max Candle 3.0×ATR | Entering on news/earnings gap bars that distort the signal |
| One-cross-one-trade | Taking the same signal twice, stacking losses on whipsaws |

---

## Position Sizing (How Much to Buy)

- You risk exactly **$100 per trade**.
- Stop distance = **2.0 × ATR(14)** from entry price.
- Quantity = `$100 ÷ stop distance`, rounded to nearest share (minimum 1).
- Example: Stock at $150, ATR = $5, stop distance = $10 → qty = 10 shares.

---

## Stop Loss Rules (When You're Wrong)

| Direction | Stop Placement |
|-----------|---------------|
| Long | Entry price **minus** 2.0 × ATR |
| Short | Entry price **plus** 2.0 × ATR |

- The stop is set **immediately** on entry. It does not move until the trailing logic kicks in.
- If the stop is hit before trailing activates, you lose exactly **$100** (1R).
- A wider 2.0×ATR stop (vs. 1.5) reduces whipsaws on volatile stocks like TSLA and NVDA.

---

## Trailing Stop Rules (Riding Winners)

The strategy has **no fixed take profit**. Winners ride until the trailing stop catches them.

### How the Trail Works

1. **Trail is dormant** until your open profit reaches **1.5R** (i.e., $150 profit on a $100 risk trade).
2. Once 1.5R is hit, the trailing stop activates:
   - **Long**: trail = EMA(20) − 1.0 × ATR. This sits below the 20-period EMA with an ATR cushion.
   - **Short**: trail = EMA(20) + 1.0 × ATR. Sits above the EMA.
3. The trail **only moves in your favor** — it never loosens back.
   - Long: trail ratchets up. If the new EMA-based level is higher than the current trail, it updates. Otherwise stays.
   - Short: trail ratchets down.
4. Trade closes when price hits the trail stop.

### Why 1.5R Activation?
- If you trail immediately, you get stopped out on the first pullback after entry — locking in tiny gains.
- Waiting for 1.5R means the trend has proven itself. You're protecting real profit, not noise.

### Why EMA(20) with 1.0×ATR buffer?
- EMA(20) follows the short-term trend tightly. It moves with the stock.
- The 1.0×ATR buffer gives room for normal daily volatility (tested at 0.5 for SPY, but 1.0 works better across volatile stocks like TSLA/NVDA/AMD).
- Result: big trends ride for weeks/months. The trail only triggers when the trend genuinely reverses.

---

## Exit Summary

| Scenario | What Happens | Typical P&L |
|----------|-------------|-------------|
| Stop hit before 1.5R | Hard stop at entry ± 2.0×ATR | −$100 (−1R) |
| Trail activates, then hit | EMA(20) ± 1.0×ATR trail stop | Varies, often +$200 to +$2000+ |
| No fixed TP | Winners run as long as the trend holds | Unlimited upside |

---

## Complete Settings Reference

| Setting | Value | Purpose |
|---------|-------|---------|
| Fast SMA | 10 | Short-term trend direction |
| Slow SMA | 50 | Long-term trend direction |
| ATR Period | 14 | Volatility measurement for stops & filters |
| Max Distance (×ATR) | 3.0 | Don't enter if price is too far from fast SMA |
| Max Candle (×ATR) | 3.0 | Skip abnormally large bars |
| Risk Per Trade | $100 | Fixed dollar risk per trade |
| Stop Loss (×ATR) | 2.0 | Initial stop distance from entry |
| Trail EMA Length | 20 | EMA used for trailing stop |
| Trail ATR Buffer | 1.0 | Cushion below/above trail EMA |
| Trail Starts At | 1.5R | Minimum profit before trail activates |

---

## Walk-Through Example (Long Trade)

```
Day 1:  NVDA at $120. SMA(10) = $118, SMA(50) = $117.
        SMA(10) just crossed above SMA(50). Bullish cross!
        ATR(14) = $4.00.
        Distance from fast SMA: |$120 - $118| = $2 < 3.0 × $4 = $12 ✓
        Bar range: $3.50 < 3.0 × $4 = $12 ✓
        → ENTER LONG at $120.
        Stop = $120 - 2.0 × $4 = $112.
        Risk = $8/share. Qty = $100 / $8 = 13 shares.

Day 5:  NVDA at $128. Profit = $8/share × 13 = $104. That's 1.04R.
        Trail still dormant (need 1.5R = $150).

Day 12: NVDA at $135. Profit = $15/share × 13 = $195. That's 1.95R.
        Trail activates! EMA(20) = $130, ATR = $4.20.
        Trail stop = $130 - 1.0 × $4.20 = $125.80.
        Old stop was $112 → updated to $125.80.

Day 20: NVDA at $148. EMA(20) = $142, ATR = $4.50.
        New trail = $142 - $4.50 = $137.50.
        Trail ratchets up from $125.80 → $137.50.

Day 25: NVDA pulls back to $137. Hits trail stop at $137.50.
        → EXIT at $137.50.
        P&L = ($137.50 - $120) × 13 = $227.50 (+2.28R).
```

---

## Walk-Through Example (Losing Trade)

```
Day 1:  AMD at $160. SMA(10) crosses above SMA(50). ATR = $6.
        → ENTER LONG at $160. Stop = $160 - 2×$6 = $148. Qty = $100/$12 = 8 shares.

Day 3:  AMD drops to $147. Stop at $148 is hit.
        → EXIT at $148.
        P&L = ($148 - $160) × 8 = -$96 (≈ −1R).
        Trail never activated. Clean loss.
```

---

## Project Structure

```
├── pine_orb              # TradingView PineScript v5 strategy
├── dashboard/            # React dashboard (Vite + Recharts)
│   ├── src/pages/        # Overview + per-stock pages
│   ├── src/components/   # Charts, tables, KPI cards
│   └── generate_data.py  # Backtest data generator ($100 risk)
├── dashboard.py          # Python backtest engine (generates HTML dashboard)
├── dashboard.html        # Static Plotly dashboard
├── data/                 # Daily OHLCV CSVs (2021-2026)
├── research.py           # Optimization round 1
├── research2.py          # Optimization round 2
└── research3.py          # Optimization round 3 (final params)
```

---

## Dashboard

Run the React dashboard:

```bash
cd dashboard && npm install && npm run dev
```

Features: per-stock pages, equity curves, drawdown phases, profit wave analysis, trade duration histograms, full trade logs.

---

## Disclaimer

This strategy is for **educational and research purposes only**. Past backtest performance does not guarantee future results. Trading involves significant risk of loss. Always paper trade and validate thoroughly before considering real capital.
