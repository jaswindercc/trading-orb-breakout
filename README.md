# ORB Breakout Strategy (Pine Script v5)

## Project Description
This repository features a robust **Opening Range Breakout (ORB)** strategy developed in Pine Script v5. The strategy is designed to capture volatility during the market open by identifying key price levels and executing trades based on breakout momentum. 

A unique aspect of this script is its integration of **The Strat** concepts—specifically identifying **Inside Bars (1)** and **Directional Bars (2U/2D)**—to filter for higher-quality setups. It includes a built-in risk management engine that calculates position sizes dynamically based on a fixed dollar risk, ensuring consistency across different stock prices.

---

## Key Features
* **Hybrid Entry Logic:** Supports standard ORB breakouts and specialized **Inside Bar (IB) ORB** entries for tighter risk.
* **Dynamic Position Sizing:** Automatically calculates `qty` based on a user-defined dollar risk per trade (default: $200).
* **The Strat Integration:** Visual labels for bar types (1, 2U, 2D, 3) to help identify price action patterns.
* **Automated Trade Management:** Includes automatic Stop Loss and Take Profit execution based on customizable Risk-to-Reward ratios.
* **Real-time Dashboard:** On-chart table showing required capital and quantity for current and previous candles.
* **Time-Based Exit:** Automatically closes all open positions at 3:00 PM to avoid EOD volatility and overnight risk.

---

## Strategy Specifications (Defaults)
* **Best Timeframe:** 15 Minute
* **Best Asset Class:** Growth Stocks (TSLA, NVDA, AAPL, AMZN, PLTR, etc.)
* **Target R:R:** 1:3 (Configurable)
* **Session Window:** 09:15 - 10:30 (Designed for the NYSE/NASDAQ open)

---

## Technical Indicators Included
1.  **5 EMA:** For trend direction and "mean reversion" awareness.
2.  **RSI (Relative Strength Index):** Built-in Overbought (80) and Oversold (20) signals.
3.  **Visual Overlays:** Labels for "Inside-Outside" (IO), "Outside-Inside" (OI), and "Outside-Outside" (OO) patterns.

---

## How to Use
1.  **Copy the Code:** Copy the Pine Script code provided in this repository.
2.  **Open TradingView:** Navigate to the **Pine Editor** tab at the bottom of the screen.
3.  **Save & Add:** Paste the code, click **Save**, and then **Add to Chart**.
4.  **Configure:** Click the "Settings" icon on the strategy to adjust your **Risk Reward**, **Risk Per Trade**, and **Session Time**.

---

## Development & Roadmap
### Known Issues
- Currently ignores "Mommy Candles" (where the 2nd bar is an outside bar).
- Can trigger dual losses if price whipsaws rapidly during a Strat 1-3 pattern.

### Planned Improvements
- [ ] Refine Trailing Stop logic (Move to BE after 1:1).
- [ ] Add specific filters for "Gappers" and "Daily Inside Bar" setups.
- [ ] Improved handling of "Boomer" stocks (low volatility).

---

## Disclaimer
This script is provided for educational and research purposes only. Trading involves significant risk. Always backtest strategies thoroughly before considering live deployment.
