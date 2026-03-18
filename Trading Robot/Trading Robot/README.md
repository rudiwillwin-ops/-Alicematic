# 🏦 Institutional Trading Robot

## 1. Setup
Install the dependencies:
```bash
pip install -r requirements.txt
```

Set up your keys:
1. Open `.env`
2. Add your Binance/Bybit API Keys.
3. Add your Google Gemini API Key.

## 2. Validation (Backtesting)
Before trading real money, download data and simulate the last 3 years.

**Step 1: Download History**
```bash
python -m src.utils.downloader
```
*Fetches 3 years of 1h candles for BTC, ETH, SOL, BNB, XRP.*

**Step 2: Run Simulation**
```bash
python -m src.backtest_engine
```
*Outputs an equity report and AI recommendations (Keep/Remove coins).*

## 3. Live Trading
**Option A: Manual Start**
```bash
python -m src.core.engine
```

**Option B: Auto-Pilot (Watchdog)**
*Recommended for 24/7 server usage. Restarts bot if it crashes.*
```bash
python watchdog.py
```

## 4. Configuration
Edit `src/config.py` to change:
- `SANDBOX_MODE`: Set to `False` to trade real money.
- `SYMBOLS`: Which coins to trade.
- `MAX_RISK_PER_TRADE`: Default is 1% ($0.01).
