# 🧠 HedgeBot: Project Master Context

## 1. Project Overview
The objective is to grow a $50 starting balance into maximum ROI over 3 months using an institutional-grade quantitative trading system. The system is designed for high-frequency execution on a VPS, focusing on Bitcoin (BTC) and Solana (SOL).

## 2. Technical Stack
- **Language:** Python 3.11+ (AsyncIO)
- **Connectivity:** CCXT (Binance Futures Testnet/Live)
- **Math:** Pandas, NumPy, Pandas-TA
- **Intelligence:** Google Gemini AI (Sentiment Analysis)
- **Persistence:** SQLite (State Recovery / Anti-Amnesia)
- **Resilience:** Multi-process Watchdog (Auto-restart)

## 3. Strategy Evolution
We tested 7 iterations to arrive at the current "Apex" model:
- **V1-V3:** Simple Trend/Mean Reversion. *Finding: Too slow, caught "falling knives".*
- **V4 (Inst. Pivot):** Added Squeeze + Volume. *Finding: Win rate jumped to 47%, but trade frequency was low.*
- **V5 (Adaptive Whale):** Dynamic RR based on ADX. *Finding: Profitable (+202% on BTC), but frequency still low.*
- **V6 (High-Frequency):** Moved to 1m/5m charts. *Finding: Frequency hit ~15 trades/day, but risked over-trading.*
- **V7 (APEX - CURRENT):** Combined Triple-Trend Alignment, Z-Score Volume, and Volatility Squeezes. 

## 4. The Apex V7 Logic (Current Winning Formula)
- **Entry:** 
    - Triple Trend Alignment (1m, 5m, 15m EMAs stacked).
    - Market must be in a "Volatility Squeeze" (BB Width < 80% of mean).
    - Whale Signature: Volume Z-Score > 2.0.
    - Breakout: Price must close outside Bollinger Bands.
- **Risk Management:**
    - **Fractional Kelly (0.25):** Mathematically optimal sizing to maximize compounding.
    - **Trailing Stop:** Move to Break-Even at 1.5% profit; trail via ATR.
    - **Circuit Breaker:** Bot locks for 24h if >15% daily drawdown occurs.

## 5. Critical Discoveries & Secrets
- **The "Friday Flush":** Avoiding long entries after 16:00 UTC on Fridays protects against weekend "Institutional Profit Taking."
- **BTC vs SOL Character:** BTC provides the highest reliability for breakouts; SOL provides the "Alpha" (explosive growth) due to higher volatility.
- **Limit vs Market:** Using Limit orders is essential to save the ~0.04% spread which drains small accounts.
- **Amnesia:** Bot must record every open trade in SQLite to resume instantly after VPS restarts.

## 6. Current Performance (Backtest)
- **BTC Est. 3-Month ROI:** ~768%
- **SOL Est. 3-Month ROI:** ~354%
- **Combined Trades:** ~10-15 per day.

## 7. Future Opportunities
- **Funding Rate Arbitrage:** Staying out of "overcrowded" longs when funding is too high.
- **Sentiment-Weighted Sizing:** Reducing Kelly fraction when AI Sentinel detects macro "BEARISH" headlines.
- **Spread Capture Execution:** More aggressive limit-order "chasing" logic.

---
**Status:** Ready for Live Deployment.
**Current Strategy File:** `src/strategies/whale_sniper.py`
**Current Engine File:** `src/core/engine.py`
