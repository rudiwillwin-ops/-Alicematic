# Shadow Trading Bot

Shadow is a high-frequency trading robot that operates on the Bybit Unified Trading Account.

## Core Directives

### Strategy Persona: Quiet Volatile
- Operates as a market maker chasing exchange rebates through PostOnly limit orders.
- No taker fees allowed.
- **Black Swan:** A high-alert state that triggers a safety freeze if the balance hits $15.

### Execution Intelligence
- **Pre-Scan Protocol:** A mandatory 5-minute market observation phase before any trades are placed.
- **The EMA 20 Filter:** Trade only in the direction of the 20-period Exponential Moving Average (Buy if Price > EMA; Sell if Price < EMA).
- **Sentiment Guard:** Scans news for "Black Swan" keywords (Hack, Scam, Crash). If detected, stands down.

### Professional Risk Management
- **Dynamic 1% Compounding:** Audits the live Bybit wallet balance before every single trade. Risks exactly 1% of the current total equity.
- **The 1:2 Ratio:** Every trade must have a Stop-Loss and a Take-Profit set at a 1:2 Risk-to-Reward ratio (e.g., 1.5% SL vs 3% TP).
- **Daily Trade Cap:** Hard shut-down after exactly 50 trades.

## Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Create a `.env` file** and add your Bybit and News API keys:
    ```
    BYBIT_API_KEY="YOUR_BYBIT_API_KEY"
    BYBIT_API_SECRET="YOUR_BYBIT_API_SECRET"
    NEWS_API_KEY="YOUR_NEWS_API_KEY"
    ```
3.  **(Optional) Provide a `ping.wav` file** for the success sound.

## Run

```bash
python shadow.py
```
