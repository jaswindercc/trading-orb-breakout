ORB Breakout Strategy (Pine Script v5)
Description
This repository contains a Opening Range Breakout (ORB) strategy built for TradingView using Pine Script v5. The strategy identifies price ranges during the market open and executes trades based on breakouts. It specifically incorporates Inside Bar (IB) logic to refine entries and provides real-time quantity calculations based on fixed dollar risk.

While originally designed for high-growth stocks like AAPL, TSLA, and NVDA, it is a versatile framework that can be adapted for various timeframes and assets.

Key Features
Dynamic ORB Detection: Set custom timeframes for the opening range (defaulted to the first 5 minutes).

Inside Bar Logic: Detects IB patterns within the opening session to identify high-probability "coiled" breakouts.

Automatic Risk Management: Calculates position size based on a fixed risk amount (e.g., $200) relative to the stop-loss distance.

Visual Chart Aids: On-chart labels for Strat patterns (1, 2U, 2D, 3), RSI overbought/oversold signals, and a 5-EMA overlay.

Trade Dashboard: A real-time table displaying required quantity and total capital amount for current and previous bars.

Strategy Logic
Note: This script is optimized for the 15m timeframe on growth stocks but includes flexible inputs for different trading styles.

The Range: The script marks the high and low of the initial opening period.

The Entry:

Standard ORB: Triggers when the price breaks the high/low of the first candle.

IB ORB: Triggers if an Inside Bar forms during the second or third candle of the session, providing a tighter stop-loss.

The Exit: Uses a user-defined Risk-to-Reward (R:R) ratio. It also includes logic to force-close all positions at 3:00 PM to avoid overnight hold risk.
