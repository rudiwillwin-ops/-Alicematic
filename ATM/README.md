# ForexMoneyMachineEA

Professional MetaTrader 5 Expert Advisor with an on-chart control panel, multi-pair trading, trend-following logic, risk management, and Telegram alerts.

## Requirements
- MetaTrader 5
- MetaEditor
- Windows

## Files
- `ForexMoneyMachineEA.mq5` — Expert Advisor source code
- `ForexMoneyMachineEA.config.ini` — Example configuration (inputs reference)
- `Roadmap.txt` — Original specification

## How To Install
1. Open MetaEditor.
2. Copy `ForexMoneyMachineEA.mq5` to `MQL5/Experts/`.
3. Compile the EA in MetaEditor.
4. Attach the EA to a chart in MetaTrader 5.

## WebRequest (Telegram)
To enable Telegram alerts:
1. In MetaTrader 5, go to `Tools -> Options -> Expert Advisors`.
2. Check `Allow WebRequest for listed URL`.
3. Add: `https://api.telegram.org`
4. Set your `BotToken` and `ChatID` inputs when attaching the EA.

## Inputs
- `RiskPercent` — Risk percent used in lot calculation.
- `MaxTradesPerPair` — Maximum open trades per symbol.
- `BotToken` — Telegram bot token.
- `ChatID` — Telegram chat ID.

## Strategy Summary
- Timeframe: H1
- Indicators: 10 SMA vs 50 SMA
- BUY when Fast MA > Slow MA
- SELL when Fast MA < Slow MA

## Control Panel
The panel includes:
- START button
- STOP button
- Bot status
- Account balance
- Current lot size
- Total open trades

