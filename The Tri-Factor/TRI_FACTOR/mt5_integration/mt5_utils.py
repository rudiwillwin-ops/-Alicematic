# TRI_FACTOR/mt5_integration/mt5_utils.py

import MetaTrader5 as mt5
import pandas as pd
import subprocess
import os
import time
import logging

from TRI_FACTOR.config import (
    MT5_TERMINAL_PATH, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_mt5():
    """Initializes connection to MetaTrader 5 terminal."""
    if not mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        logging.error(f"MT5 initialization failed, error code: {mt5.last_error()}")
        return False
    logging.info("MetaTrader 5 initialized successfully.")
    return True

def shutdown_mt5():
    """Shuts down connection to MetaTrader 5 terminal."""
    mt5.shutdown()
    logging.info("MetaTrader 5 connection shut down.")

def launch_mt5_terminal():
    """Launches the MetaTrader 5 terminal executable."""
    if not os.path.exists(MT5_TERMINAL_PATH):
        logging.error(f"MT5 terminal not found at: {MT5_TERMINAL_PATH}")
        return False
    try:
        # Use Popen to launch without waiting for it to close
        subprocess.Popen(MT5_TERMINAL_PATH)
        logging.info(f"Launched MT5 terminal: {MT5_TERMINAL_PATH}")
        return True
    except Exception as e:
        logging.error(f"Failed to launch MT5 terminal: {e}")
        return False

def get_historical_data(symbol, timeframe, count):
    """
    Retrieves historical price data for a given symbol and timeframe.
    Args:
        symbol (str): Trading symbol (e.g., "EURUSD").
        timeframe (mt5.TIMEFRAME_...): Timeframe (e.g., mt5.TIMEFRAME_M1).
        count (int): Number of bars to retrieve.
    Returns:
        pd.DataFrame: DataFrame with historical data, or None if failed.
    """
    if not mt5.terminal_info(): # Check if MT5 is initialized
        logging.warning("MT5 not initialized. Attempting to initialize...")
        if not initialize_mt5():
            return None

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None:
        logging.error(f"Failed to get historical data for {symbol}, error code: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    logging.debug(f"Retrieved {len(df)} bars for {symbol} {timeframe}")
    return df

def get_current_price(symbol):
    """
    Retrieves the current ask and bid prices for a given symbol.
    Args:
        symbol (str): Trading symbol (e.g., "EURUSD").
    Returns:
        tuple: (ask_price, bid_price) or (None, None) if failed.
    """
    if not mt5.terminal_info():
        logging.warning("MT5 not initialized. Attempting to initialize...")
        if not initialize_mt5():
            return None, None

    symbol_info = mt5.symbol_info_tick(symbol)
    if symbol_info is None:
        logging.error(f"Failed to get tick info for {symbol}, error code: {mt5.last_error()}")
        return None, None

    return symbol_info.ask, symbol_info.bid

def place_order(symbol, order_type, volume, price, sl, tp, deviation=10, comment="The Tri-Factor"):
    """
    Places a trading order (Market or Limit) with Stop Loss and Take Profit.
    Args:
        symbol (str): Trading symbol (e.g., "EURUSD").
        order_type (int): mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY_LIMIT, etc.
        volume (float): Lot size.
        price (float): Price for Limit orders. For Market orders, use current ask/bid.
        sl (float): Stop Loss price.
        tp (float): Take Profit price.
        deviation (int): Permissible deviation from the requested price.
        comment (str): Comment for the order.
    Returns:
        dict: Order result dictionary, or None if initialization failed.
    """
    if not mt5.terminal_info():
        logging.warning("MT5 not initialized. Attempting to initialize...")
        if not initialize_mt5():
            return None

    request = {
        "action": mt5.TRADE_ACTION_DEAL, # For market orders
        "symbol": symbol,
        "volume": volume,
        "deviation": deviation,
        "type_filling": mt5.ORDER_FILLING_FOK, # Fill Or Kill (or other types like IOC, RETURN)
        "comment": comment,
    }

    if order_type == mt5.ORDER_TYPE_BUY:
        request["price"] = mt5.symbol_info_tick(symbol).ask
        request["type"] = mt5.ORDER_TYPE_BUY
        request["type_trade"] = mt5.ORDER_TYPE_BUY
    elif order_type == mt5.ORDER_TYPE_SELL:
        request["price"] = mt5.symbol_info_tick(symbol).bid
        request["type"] = mt5.ORDER_TYPE_SELL
        request["type_trade"] = mt5.ORDER_TYPE_SELL
    elif order_type == mt5.ORDER_TYPE_BUY_LIMIT:
        request["price"] = price
        request["type"] = mt5.ORDER_TYPE_BUY_LIMIT
        request["type_trade"] = mt5.ORDER_TYPE_BUY
        request["type_time"] = mt5.ORDER_TIME_GTC # Good Till Cancel
    elif order_type == mt5.ORDER_TYPE_SELL_LIMIT:
        request["price"] = price
        request["type"] = mt5.ORDER_TYPE_SELL_LIMIT
        request["type_trade"] = mt5.ORDER_TYPE_SELL
        request["type_time"] = mt5.ORDER_TIME_GTC # Good Till Cancel
    else:
        logging.error(f"Unsupported order type: {order_type}")
        return None

    request["sl"] = sl
    request["tp"] = tp

    # Check if the symbol is selectable
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"Symbol '{symbol}' not found or not selectable. Error: {mt5.last_error()}")
        return None
    if not symbol_info.visible:
        logging.info(f"Symbol '{symbol}' is not visible, trying to select it...")
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol '{symbol}', error: {mt5.last_error()}")
            return None

    result = mt5.order_send(request)

    if result is None:
        logging.error(f"Order send failed, error code: {mt5.last_error()}")
        return None
    elif result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed: {result.comment}, retcode={result.retcode}")
        # Request the result and display it in a nice format
        result_dict = result._asdict()
        for field in result_dict:
            logging.error(f"   {field}: {result_dict[field]}")
        return None
    
    logging.info(f"Order placed successfully: {result.comment}, ticket={result.order}")
    return result

if __name__ == "__main__":
    # Example usage for testing
    logging.info("--- Testing mt5_utils.py ---")

    # Launch MT5 terminal (optional, usually done by START_TRADES.py)
    # launch_mt5_terminal()
    # time.sleep(5) # Give MT5 time to start

    # Initialize MT5 connection
    if not initialize_mt5():
        logging.error("Could not initialize MT5. Exiting.")
    else:
        symbol = "EURUSD"
        
        # Test get_current_price
        ask, bid = get_current_price(symbol)
        if ask is not None:
            logging.info(f"Current price for {symbol}: Ask={ask}, Bid={bid}")
        
        # Test get_historical_data
        df = get_historical_data(symbol, mt5.TIMEFRAME_M1, 10)
        if df is not None:
            logging.info(f"Last 10 M1 bars for {symbol}:\n{df.tail()}")

        # Test placing a dummy order (will fail if not connected/real account)
        # For actual trading, ensure MT5_LOGIN, MT5_PASSWORD, MT5_SERVER are correct
        # and symbol is available for trading.
        
        # Example Buy Market Order
        # current_ask, current_bid = get_current_price(symbol)
        # if current_ask is not None:
        #     volume = 0.01 # Smallest lot size
        #     sl_price = current_bid - 0.00030 # Example SL 3 pips below bid
        #     tp_price = current_ask + 0.00090 # Example TP 9 pips above ask
        #     logging.info(f"Attempting to place BUY order for {symbol} at {current_ask}, SL={sl_price}, TP={tp_price}")
        #     order_result = place_order(symbol, mt5.ORDER_TYPE_BUY, volume, current_ask, sl_price, tp_price)
        #     if order_result:
        #         logging.info(f"BUY Order successful, ticket: {order_result.order}")
        #     else:
        #         logging.error("BUY Order failed.")
        
        # Example Buy Limit Order
        # current_ask, current_bid = get_current_price(symbol)
        # if current_ask is not None:
        #     limit_price = current_bid - 0.00010 # Example limit price below current bid
        #     volume = 0.01
        #     sl_price = limit_price - 0.00030
        #     tp_price = limit_price + 0.00090
        #     logging.info(f"Attempting to place BUY LIMIT order for {symbol} at {limit_price}, SL={sl_price}, TP={tp_price}")
        #     order_result = place_order(symbol, mt5.ORDER_TYPE_BUY_LIMIT, volume, limit_price, sl_price, tp_price)
        #     if order_result:
        #         logging.info(f"BUY LIMIT Order successful, ticket: {order_result.order}")
        #     else:
        #         logging.error("BUY LIMIT Order failed.")

        shutdown_mt5()
