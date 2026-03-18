import MetaTrader5 as mt5
from datetime import datetime
import time
import pandas as pd

# --- CONFIGURATION ---
SYMBOL = "EURUSD"
LOT_SIZE = 0.02          # Total Volume (0.01 for TP1, 0.01 for TP2)
RISK_PIPS = 20           # Stop Loss
TP1_PIPS = 40            # Income Sealer (2:1)
TP2_PIPS = 120           # Wealth Runner (6:1)
DAILY_LOSS_LIMIT = -2.0  # Shut down if account drops 2% today
MAGIC_NUMBER = 123456    # A unique ID for this robot's trades

# --- STRATEGY PARAMETERS ---
TIMEFRAME = mt5.TIMEFRAME_M15
FAST_MA_PERIOD = 50
SLOW_MA_PERIOD = 200

def get_ma_signal():
    """
    Checks for a moving average crossover signal.
    Returns "BUY", "SELL", or None.
    """
    # Get candlestick data
    candles = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, SLOW_MA_PERIOD + 5)
    if candles is None or len(candles) < SLOW_MA_PERIOD:
        print("Could not retrieve enough candle data.")
        return None

    # Create a DataFrame for easier analysis
    df = pd.DataFrame(candles)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # Calculate EMAs
    df['ema_fast'] = df['close'].ewm(span=FAST_MA_PERIOD, adjustment=False).mean()
    df['ema_slow'] = df['close'].ewm(span=SLOW_MA_PERIOD, adjustment=False).mean()

    # Get the last two completed candles for crossover check
    last_candle = df.iloc[-2]
    prev_candle = df.iloc[-3]

    # --- Crossover Logic ---
    # Bullish Crossover (BUY SIGNAL)
    if last_candle['ema_fast'] > last_candle['ema_slow'] and prev_candle['ema_fast'] <= prev_candle['ema_slow']:
        return "BUY"
    
    # Bearish Crossover (SELL SIGNAL)
    if last_candle['ema_fast'] < last_candle['ema_slow'] and prev_candle['ema_fast'] >= prev_candle['ema_slow']:
        return "SELL"

    return None

def place_sovereign_trade(direction):
    """Places two orders: one for steady income, one for the runner."""
    point = mt5.symbol_info(SYMBOL).point
    price = mt5.symbol_info_tick(SYMBOL).ask if direction == "BUY" else mt5.symbol_info_tick(SYMBOL).bid
    
    # Calculate SL and TPs
    sl = price - (RISK_PIPS * point) if direction == "BUY" else price + (RISK_PIPS * point)
    tp1 = price + (TP1_PIPS * point) if direction == "BUY" else price - (TP1_PIPS * point)
    tp2 = price + (TP2_PIPS * point) if direction == "BUY" else price - (TP2_PIPS * point)

    # --- ORDER 1: The Income Sealer ---
    request1 = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE / 2,
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp1,
        "magic": MAGIC_NUMBER,
        "comment": "Forex Forge: Sealer",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # --- ORDER 2: The Wealth Runner ---
    request2 = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE / 2,
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp2,
        "magic": MAGIC_NUMBER,
        "comment": "Forex Forge: Runner",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Send orders
    result1 = mt5.order_send(request1)
    result2 = mt5.order_send(request2)

    if result1.retcode != mt5.TRADE_RETCODE_DONE or result2.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed. Sealer: {result1.comment}, Runner: {result2.comment}")
        print("Check your MT5 connection or balance.")
    else:
        print(f"Sovereign Entry Success: 0.02 Lots @ {price}")

def close_all_positions():
    """Safety Kill: Closes all open positions for this robot's Magic Number."""
    positions = mt5.positions_get(magic=MAGIC_NUMBER)
    if positions:
        for pos in positions:
            # Create a close request
            tick = mt5.symbol_info_tick(pos.symbol)
            type_close = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price_close = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
            
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": type_close,
                "position": pos.ticket,
                "price": price_close,
                "magic": MAGIC_NUMBER,
                "comment": "Forex Forge: SAFETY",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5.order_send(close_request)
    print("All Sovereign positions closed. Shutting down for the day.")

def run_manager():
    """The Session Watchdog: Runs the logic continuously."""
    if not mt5.initialize():
        print("Initial connection to MT5 failed.")
        return

    print("Sovereign Manager Active. Monitoring 24/7 for MA Crossover...")
    
    while True:
        # 1. CIRCUIT BREAKER (If Daily Loss > 2%)
        acc = mt5.account_info()
        if acc and acc.profit < (acc.balance * (DAILY_LOSS_LIMIT / 100)):
            print("Daily Loss Limit reached. Safety shutdown activated.")
            close_all_positions()
            break
        
        # 2. TRADING LOGIC
        # Only check for signals if no positions are currently open for this robot
        if not mt5.positions_get(magic=MAGIC_NUMBER):
            signal = get_ma_signal()
            
            if signal:
                print(f"Signal found: {signal}! Attempting to place trade.")
                place_sovereign_trade(signal)
        
        # Wait for a minute before the next check
        time.sleep(60)

# To start the robot, you simply call:
# run_manager()
if __name__ == "__main__":
    run_manager()