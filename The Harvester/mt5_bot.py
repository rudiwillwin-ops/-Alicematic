import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime, timedelta
import time
import sys
import json
import traceback
import os
import builtins as _builtins
import requests
import winsound

# --- Logging ---
LOG_PATH = os.path.join(os.path.dirname(__file__), "harvester.log")

def log(*args, sep=" ", end="\n"):
    msg = sep.join(str(a) for a in args)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}"
    _builtins.print(line, end=end)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + end)
    except Exception:
        # Avoid crashing on logging failures
        pass

# Route all prints through logger for live file output
print = log

# --- Configuration Loading ---
def load_config():
    """Loads configuration from config.json."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
            print("Configuration loaded from config.json")
            return config
    except FileNotFoundError:
        print("Error: config.json not found. Please ensure the configuration file exists.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Could not decode config.json. Please check for syntax errors.")
        sys.exit(1)

config = load_config()

# --- MT5 Timeframe Mapping ---
TIMEFRAME_MAP = {
    "TIMEFRAME_M1": mt5.TIMEFRAME_M1,
    "TIMEFRAME_M5": mt5.TIMEFRAME_M5,
    "TIMEFRAME_M15": mt5.TIMEFRAME_M15,
    "TIMEFRAME_M30": mt5.TIMEFRAME_M30,
    "TIMEFRAME_H1": mt5.TIMEFRAME_H1,
    "TIMEFRAME_H4": mt5.TIMEFRAME_H4,
    "TIMEFRAME_D1": mt5.TIMEFRAME_D1,
}

# --- Apply Configuration ---
SYMBOLS = config.get("symbols", ["AUDNZD", "EURGBP"])
TIMEFRAME_STR = config.get("timeframe", "TIMEFRAME_M1")
TIMEFRAME = TIMEFRAME_MAP.get(TIMEFRAME_STR, mt5.TIMEFRAME_M1)
LOT_SIZE = config.get("lot_size", 0.1)
MAGIC_NUMBER = config.get("magic_number", 12345)
CHECK_INTERVAL_SECONDS = config.get("check_interval_seconds", 30)

# Fast profile controls
RSI_BUY = float(config.get("rsi_buy", 30))
RSI_SELL = float(config.get("rsi_sell", 70))
EMA_FAST = int(config.get("ema_fast", 12))
EMA_SLOW = int(config.get("ema_slow", 48))
MIN_BARS = int(config.get("min_bars", 60))
TAKE_PROFIT_PERCENT = float(config.get("take_profit_percent", 1.0))
STOP_LOSS_PERCENT = float(config.get("stop_loss_percent", 1.0))

# Telegram alerts
TELEGRAM_BOT_TOKEN = config.get("telegram_bot_token", "").strip()
TELEGRAM_CHAT_ID = str(config.get("telegram_chat_id", "")).strip()

def send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
    except Exception:
        pass

def handle_telegram_commands():
    """Checks for new Telegram messages and executes commands."""
    global LOT_SIZE
    last_update_id = getattr(_builtins, "_telegram_last_id", 0)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 1}, timeout=5)
        if resp.status_code == 200:
            updates = resp.json().get("result", [])
            for update in updates:
                _builtins._telegram_last_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id != TELEGRAM_CHAT_ID:
                    continue

                if text == "/status":
                    info = mt5.account_info()
                    open_p = get_open_positions()
                    status_msg = f"--- Harvester Status ---\n💰 Balance: ${info.balance:.2f}\n📈 Equity: ${info.equity:.2f}\n🔄 Open Trades: {len(open_p)}"
                    send_telegram(status_msg)
                
                elif text == "/settings":
                    settings_msg = f"--- Harvester Brain ---\n📊 Lot Size: {LOT_SIZE}\n⏱ Timeframe: {TIMEFRAME_STR}\n🎯 RSI: {RSI_BUY}/{RSI_SELL}"
                    send_telegram(settings_msg)

                elif text.startswith("/set_lot "):
                    try:
                        new_lot = float(text.split(" ")[1])
                        if 0.01 <= new_lot <= 1.0:
                            LOT_SIZE = new_lot
                            send_telegram(f"✅ Lot Size updated to: {LOT_SIZE}")
                        else:
                            send_telegram("❌ Error: Lot size must be between 0.01 and 1.0")
                    except Exception:
                        send_telegram("❌ Usage: /set_lot 0.10")

                elif text == "/panic":
                    send_telegram("🚨 PANIC MODE: Closing all Harvester trades...")
                    for pos in get_open_positions():
                        close_position(pos)
                    send_telegram("✅ All trades closed.")

    except Exception:
        pass

def play_success_ping() -> None:
    try:
        winsound.Beep(1200, 250)
        winsound.Beep(1600, 250)
    except Exception:
        pass


# --- MT5 Initialization ---
def initialize_mt5():
    """Initializes connection to MetaTrader 5 terminal."""
    path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    if not mt5.initialize(path=path):
        print("initialize() failed, error code =", mt5.last_error())
        sys.exit(1)
    print("MetaTrader5 initialized successfully.")

def shutdown_mt5():
    """Shuts down connection to MetaTrader 5 terminal."""
    mt5.shutdown()
    print("MetaTrader5 shutdown.")

def ensure_mt5_connection():
    """Ensures MT5 is initialized and connected; attempts reconnect if needed."""
    path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    if not mt5.initialize(path=path):
        print("MT5 not initialized. Attempting to initialize...")
        if not mt5.initialize(path=path):
            print("Re-initialize failed, error code =", mt5.last_error())
            return False

    # Validate terminal/account connectivity
    terminal = mt5.terminal_info()
    account = mt5.account_info()
    if terminal is None or account is None:
        print("MT5 connection lost. Shutting down and reconnecting...")
        mt5.shutdown()
        time.sleep(2)
        if not mt5.initialize():
            print("Reconnect failed, error code =", mt5.last_error())
            return False
        if mt5.terminal_info() is None or mt5.account_info() is None:
            print("Reconnect did not restore terminal/account info.")
            return False
        print("Reconnected to MT5.")
    return True

# --- Trading Functions ---
def execute_buy_order(symbol, lot):
    """Executes a market buy order."""
    if not mt5.symbol_info(symbol).visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select {symbol}, check if it's available in Market Watch.")
            return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(symbol).ask,
        "deviation": 20, # Deviation from the requested price
        "magic": MAGIC_NUMBER,
        "comment": "The Harvester",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC, # Fill Or Kill
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Buy order failed for {symbol}. Error: {result.retcode}")
        print(f"Result: {result}")
    else:
        print(f"Buy order executed for {symbol}. Position #{result.order}")
    return result

def execute_sell_order(symbol, lot):
    """Executes a market sell order."""
    if not mt5.symbol_info(symbol).visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select {symbol}, check if it's available in Market Watch.")
            return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(symbol).bid,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "The Harvester",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Sell order failed for {symbol}. Error: {result.retcode}")
        print(f"Result: {result}")
    else:
        print(f"Sell order executed for {symbol}. Position #{result.order}")
    return result

def close_position(position):
    """Closes a specific open position."""
    symbol = position.symbol
    lot = position.volume
    order_type = mt5.ORDER_TYPE_BUY if position.type == mt5.ORDER_TYPE_SELL else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "The Harvester",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Close order failed for {symbol} (position #{position.ticket}). Error: {result.retcode}")
        print(f"Result: {result}")
    else:
        print(f"Position #{position.ticket} for {symbol} closed.")
    return result

def get_open_positions(symbol=None):
    """Retrieves all open positions, or open positions for a specific symbol."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    return list(positions)

# --- Data Fetching ---
def get_mt5_data(symbol, timeframe, bars_count):
    """Fetches historical market data from MT5 and returns a pandas DataFrame."""
    utc_from = datetime.now() - timedelta(days=bars_count) # Fetch enough data for indicators, using local naive time
    
    # Request historical data
    rates = mt5.copy_rates_from(symbol, timeframe, utc_from, bars_count)
    
    if rates is None:
        print(f"No rates data for {symbol}, error code: {mt5.last_error()}")
        return pd.DataFrame()

    # Create DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    return df

# --- Strategy Placeholder ---
def get_trading_signal(symbol: str, timeframe, bars_df: pd.DataFrame):
    """
    THIS IS WHERE YOU ADD YOUR TRADING STRATEGY LOGIC.

    This function should analyze the 'bars_df' (historical data) for the given 'symbol'
    and return a signal:
    - 'buy' for a buy signal
    - 'sell' for a sell signal
    - None for no signal

    Example: Basic RSI strategy (for demonstration only, not a robust strategy)
    """
    if bars_df.empty:
        return None

    # Calculate RSI
    # Note: Ensure enough data points for RSI calculation (default 14 periods)
    if len(bars_df) < 14:
        return None
        
    # Calculate Standard RSI (Wilder's)
    delta = bars_df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    bars_df['rsi'] = 100 - (100 / (1 + rs))

    if bars_df['rsi'].isnull().all():
        return None

    last_rsi = bars_df['rsi'].iloc[-1]
    print(f"   > {symbol} RSI: {last_rsi:.2f} (Targets: {RSI_BUY}/{RSI_SELL})")
    
    # Get current open positions for this symbol
    open_positions = get_open_positions(symbol)
    has_buy_position = any(p.type == mt5.ORDER_TYPE_BUY for p in open_positions)
    has_sell_position = any(p.type == mt5.ORDER_TYPE_SELL for p in open_positions)

    if last_rsi < RSI_BUY and not has_buy_position: # Oversold, no open buy position
        print(f"{symbol}: RSI ({last_rsi:.2f}) < {RSI_BUY}. Potential BUY signal.")
        return 'buy'
    elif last_rsi > RSI_SELL and not has_sell_position: # Overbought, no open sell position
        print(f"{symbol}: RSI ({last_rsi:.2f}) > {RSI_SELL}. Potential SELL signal.")
        return 'sell'

    # --- Fallback Strategy: EMA Crossover (Buy only) ---
    # Use a fast/slow EMA crossover to generate more frequent entries.
    # Requires enough data points for a stable EMA.
    if len(bars_df) >= MIN_BARS and not has_buy_position:
        fast = bars_df['close'].ewm(span=EMA_FAST, adjust=False).mean()
        slow = bars_df['close'].ewm(span=EMA_SLOW, adjust=False).mean()
        # Crossover detection using last two completed bars
        if fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]:
            print(f"{symbol}: EMA crossover detected ({EMA_FAST}/{EMA_SLOW}). Fallback BUY signal.")
            return 'buy'
        if fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1] and not has_sell_position:
            print(f"{symbol}: EMA crossover detected ({EMA_FAST}/{EMA_SLOW}). Fallback SELL signal.")
            return 'sell'

    return None # No signal


def manage_positions(symbol: str, current_price: float):
    """
    Manages open positions for a given symbol based on strategy.
    For example, closes positions at a certain profit/loss or when new signals appear.
    """
    positions = get_open_positions(symbol)

    for pos in positions:
        # Example: Close position if it reaches a certain profit (1% here)
        profit_percent = (current_price - pos.price_open) / pos.price_open * 100 \
                         if pos.type == mt5.ORDER_TYPE_BUY \
                         else (pos.price_open - current_price) / pos.price_open * 100

        if profit_percent >= TAKE_PROFIT_PERCENT: # Close if profit target hit
            print(f"Closing position #{pos.ticket} for {symbol} due to {TAKE_PROFIT_PERCENT}% profit.")
            result = close_position(pos)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE and pos.profit > 0:
                send_telegram(
                    f"✅ Profit closed: {symbol} | Ticket {pos.ticket} | Profit: {pos.profit:.2f}"
                )
                play_success_ping()
            time.sleep(1) # Wait a bit before checking next position
        elif profit_percent <= -STOP_LOSS_PERCENT:
            print(f"Closing position #{pos.ticket} for {symbol} due to {STOP_LOSS_PERCENT}% stop loss.")
            close_position(pos)
            time.sleep(1)

        # Add more sophisticated exit logic here (e.g., stop-loss, take-profit, indicator-based exits)


# --- Main Bot Logic ---
def run_harvester():
    initialize_mt5()
    print("--- The Harvester V2.0 (Active Naming) Starting ---")
    # Select symbols to ensure they are visible in Market Watch
    for symbol in SYMBOLS:
        if not mt5.symbol_select(symbol, True):
            print(f"Warning: Failed to select {symbol}. Check if it's available in Market Watch.")

    last_check_time = {}
    for symbol in SYMBOLS:
        last_check_time[symbol] = datetime.now(pytz.utc) - timedelta(seconds=CHECK_INTERVAL_SECONDS) # Initialize to ensure first check runs

    try:
        while True:
            if not ensure_mt5_connection():
                print("MT5 unavailable. Waiting 10 seconds before retry...")
                time.sleep(10)
                continue

            utc_now = datetime.now(pytz.utc)

            for symbol in SYMBOLS:
                # Check if enough time has passed since the last check
                if (utc_now - last_check_time[symbol]).total_seconds() >= CHECK_INTERVAL_SECONDS:
                    print(f"\nChecking {symbol} at {utc_now.strftime('%H:%M:%S')}")
                    last_check_time[symbol] = utc_now

                    # Fetch data
                    bars_df = get_mt5_data(symbol, TIMEFRAME, 100) # Fetch 100 bars for indicators

                    if not bars_df.empty:
                        current_price = mt5.symbol_info_tick(symbol).last
                        if current_price == 0: # Fallback if last price is 0 (e.g. for non-forex pairs, use bid)
                            current_price = mt5.symbol_info_tick(symbol).bid

                        # Get signal from your strategy
                        signal = get_trading_signal(symbol, TIMEFRAME, bars_df)
                        
                        # Get current open positions for this symbol
                        open_positions = get_open_positions(symbol)
                        has_open_position = bool(open_positions)
                        
                        # --- Execute Trades ---
                        if signal == 'buy' and not has_open_position:
                            print(f"BUY signal detected for {symbol}. Executing order...")
                            result = execute_buy_order(symbol, LOT_SIZE)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                msg = f"The Harvester: BUY opened on {symbol} at {current_price}"
                                print(msg)
                                send_telegram(msg)
                                play_success_ping()
                        elif signal == 'sell' and not has_open_position:
                            print(f"SELL signal detected for {symbol}. Executing order (short position)...")
                            result = execute_sell_order(symbol, LOT_SIZE)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                msg = f"The Harvester: SELL opened on {symbol} at {current_price}"
                                print(msg)
                                send_telegram(msg)
                                play_success_ping()
                        
                        # Manage existing positions (e.g., take profit, stop loss)
                        manage_positions(symbol, current_price)
                    else:
                        print(f"Could not get data for {symbol}. Skipping this interval.")

            time.sleep(1) # Wait 1 second before next loop iteration
            handle_telegram_commands()

    except KeyboardInterrupt:
        print("\nMT5 Trading Bot stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        traceback.print_exc()
    finally:
        shutdown_mt5()

if __name__ == "__main__":
    run_harvester()
