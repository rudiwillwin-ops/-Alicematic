# 🏆 Trading Strategy Hall of Fame

This document preserves the top-performing strategies discovered during the development of the HedgeBot.

---

## 🥇 1. The Whale Sniper (Original Breakout)
*Status: High Performance (BTC King)*
* **Core Logic:** Classic Price Breakout + Volume Confirmation.
* **Key Indicators:** 20-period High/Low, Volume SMA (1.5x Multiplier), EMA 50/200 Trend Filter.
* **Best Market:** Bitcoin (BTC)
* **Backtest Result:** **+422% Return** over 3 years.
* **Why it worked:** BTC has very clean breakouts. When volume enters BTC, the price rarely "fake-outs," leading to massive trending moves.

## 🥈 2. Aggressive V-BOP (Volatility Breakout)
*Status: High Frequency (SOL Specialist)*
* **Core Logic:** Entering on Bollinger Band breakouts during high-volume surges.
* **Key Indicators:** Bollinger Bands (20, 2), Volume SMA (1.2x), EMA 200.
* **Best Market:** Solana (SOL)
* **Backtest Result:** **+400% Return** on SOL.
* **Why it worked:** SOL is extremely volatile. This strategy captures the "explosive" nature of SOL's movements on the 5-minute chart.

## 🥉 3. Institutional Pivot (V4)
*Status: Most Stable (Safety First)*
* **Core Logic:** Confluence of Macro Trend, Volatility Squeezes, and Institutional Volume Surges.
* **Key Indicators:** EMA 200 (Macro), BB Width (Squeeze Detection), Volume Z-Score / 3x Multiplier.
* **Target:** High-conviction trades with low drawdown.
* **Why it leads:** This strategy outsmarts retail bots by waiting for a "Squeeze" (Whale accumulation) followed by a "Volume Spike" (Whale execution).

---

## 📈 Summary of Findings
| Strategy | Best Market | Character | Risk Profile |
| :--- | :--- | :--- | :--- |
| **Whale Sniper** | BTC | Trend Following | Medium |
| **Aggressive V-BOP** | SOL / BTC | Scalping | High |
| **Inst. Pivot** | All | Multi-TF Confluence | Low (Surgical) |
