# The Harvester - MT5 Trading Bot Framework

This project provides a Python framework to connect to MetaTrader 5 (MT5), fetch market data for specified currency pairs, and execute trading orders. It includes placeholders for you to integrate your own trading strategy.

## Prerequisites

1.  **MetaTrader 5 Terminal**: You must have the MT5 terminal installed and running on your computer.
2.  **MT5 Python Integration**: Ensure that the Python integration for MT5 is properly installed and configured. This usually involves enabling "Allow DLL imports" in MT5 terminal's Expert Advisors settings.
3.  **Python 3.x**: Ensure you have Python 3.x installed.

## Setup

1.  **Install Dependencies**: Open your terminal or command prompt in this directory and run the following command to install the required Python libraries:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Bot

1.  **Start MT5 Terminal**: Make sure your MetaTrader 5 terminal is open and logged into your trading account.
2.  **Execute the Bot**: Open your terminal or command prompt in this directory and run:
    ```bash
    python mt5_bot.py
    ```

## Implementing Your Trading Strategy

Open `mt5_bot.py` in a text editor. You will find a function called `find_trading_signal(symbol, timeframe, bars)` and `manage_positions(symbol, current_price)`. This is where you will add your specific buy and sell rules.

*   **`find_trading_signal`**: This function receives market data and should return `True` for a buy signal, `False` for a sell signal, or `None` if no action is needed.
*   **`manage_positions`**: This function will handle closing existing positions based on your strategy.

**Important**: This script is a framework. It does not contain an actual trading strategy. You must implement your own strategy logic before using it for live trading. Always test your strategy extensively in a demo environment before using real money.
