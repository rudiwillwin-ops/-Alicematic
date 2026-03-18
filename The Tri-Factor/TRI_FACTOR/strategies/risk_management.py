# TRI_FACTOR/strategies/risk_management.py

import MetaTrader5 as mt5
import logging

from TRI_FACTOR.config import (
    ACCOUNT_BASE, RISK_PER_TRADE, PROFIT_TARGET_PER_TRADE, RR_RATIO
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_lot_size(symbol, entry_price, stop_loss_price):
    """
    Calculates the appropriate lot size based on risk per trade and distance to Stop Loss.
    Args:
        symbol (str): Trading symbol (e.g., "EURUSD").
        entry_price (float): The price at which the order is expected to be opened.
        stop_loss_price (float): The price at which the Stop Loss is placed.
    Returns:
        float: The calculated lot size.
    """
    if not mt5.terminal_info():
        logging.warning("MT5 not initialized for lot size calculation. Cannot get symbol info.")
        return 0.0

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logging.error(f"Failed to get symbol info for {symbol}, error code: {mt5.last_error()}")
        return 0.0
    
    # Get symbol properties
    point = symbol_info.point
    currency_profit = symbol_info.currency_profit
    
    # Calculate stop loss in points
    sl_in_points = abs(entry_price - stop_loss_price) / point
    
    if sl_in_points == 0:
        logging.warning("Stop Loss distance is zero, cannot calculate lot size. Returning 0.0.")
        return 0.0

    # Calculate value per lot for 1 point movement
    # This is a simplification; in real MT5, it depends on contract size, tick value, etc.
    # For common forex pairs, 1 standard lot (100,000 units) means 1 pip is $10.
    # A point is typically 1/10 of a pip. So 1 point is $1.
    # We'll use a simplified calculation based on account currency for simplicity.
    
    # Let's try to get more accurate tick_value from MT5.
    tick_value = symbol_info.tick_value() # Value of a tick in deposit currency
    tick_size = symbol_info.tick_size # Size of a tick

    if tick_value == 0 or tick_size == 0:
        logging.error(f"Could not retrieve accurate tick_value or tick_size for {symbol}. Cannot calculate lot size. Returning 0.0.")
        return 0.0

    # Value of 1 point movement for 1 unit of volume (e.g. 1 USD per 100,000 units for EURUSD)
    value_per_point_per_unit = tick_value / tick_size if tick_size != 0 else 0
    if value_per_point_per_unit == 0:
        logging.error(f"Cannot determine value per point for {symbol}. Returning 0.0 for lot size.")
        return 0.0

    # Total risk in currency if 1 unit of volume hits SL
    risk_per_unit = sl_in_points * value_per_point_per_unit

    if risk_per_unit == 0:
        logging.warning("Calculated risk per unit is zero, cannot determine lot size. Returning 0.0.")
        return 0.0

    # Desired lot size
    lot_size = RISK_PER_TRADE / risk_per_unit

    # Adjust for minimum and maximum volume allowed by broker
    min_volume = symbol_info.volume_min
    max_volume = symbol_info.volume_max
    volume_step = symbol_info.volume_step

    lot_size = max(min_volume, round(lot_size / volume_step) * volume_step)
    lot_size = min(lot_size, max_volume)
    
    if lot_size == 0.0:
        logging.warning(f"Calculated lot size for {symbol} is 0.0. Check inputs or symbol info.")

    logging.info(f"Calculated lot size for {symbol}: {lot_size:.2f} (entry={entry_price}, SL={stop_loss_price}, sl_points={sl_in_points:.2f}, risk_per_trade={RISK_PER_TRADE})")
    return lot_size

def calculate_sl_tp_prices(entry_price, point_size, trade_type):
    """
    Calculates Stop Loss and Take Profit prices based on entry price and fixed RR ratio.
    Args:
        entry_price (float): The price at which the order is opened.
        point_size (float): The point size of the symbol (mt5.symbol_info(symbol).point).
        trade_type (int): mt5.ORDER_TYPE_BUY or mt5.ORDER_TYPE_SELL.
    Returns:
        tuple: (sl_price, tp_price)
    """
    # The problem statement fixes RR_RATIO to 1:3 and risk $0.30 to target $0.90.
    # This implies a fixed monetary value for SL and TP for any position.
    # We need to determine how many "points" this translates to.
    
    # Assuming for 0.01 lot, 1 point = $0.01 for EURUSD (a common approximation for simplicity)
    # So, $0.30 risk corresponds to 30 points.
    # And $0.90 profit corresponds to 90 points.
    
    sl_points_distance = RISK_PER_TRADE / 0.01 # Assuming $0.01 per point for 0.01 lot
    tp_points_distance = PROFIT_TARGET_PER_TRADE / 0.01 # Assuming $0.01 per point for 0.01 lot

    # Convert points to price units using point_size
    sl_price = 0.0
    tp_price = 0.0

    if trade_type == mt5.ORDER_TYPE_BUY:
        sl_price = entry_price - (sl_points_distance * point_size)
        tp_price = entry_price + (tp_points_distance * point_size)
    elif trade_type == mt5.ORDER_TYPE_SELL:
        sl_price = entry_price + (sl_points_distance * point_size)
        tp_price = entry_price - (tp_points_distance * point_size)
    else:
        logging.error(f"Unsupported trade type for SL/TP calculation: {trade_type}")
        return 0.0, 0.0

    logging.info(f"Calculated SL={sl_price:.5f}, TP={tp_price:.5f} for entry={entry_price:.5f} (trade_type={trade_type})")
    return sl_price, tp_price

if __name__ == "__main__":
    logging.info("--- Testing risk_management.py ---")
    
    # Mock MT5 initialization for testing
    class MockMt5SymbolInfo:
        def __init__(self, point, volume_min, volume_max, volume_step, tick_value, tick_size):
            self.point = point
            self.volume_min = volume_min
            self.volume_max = volume_max
            self.volume_step = volume_step
            self._tick_value = tick_value
            self._tick_size = tick_size

        def tick_value(self):
            return self._tick_value
        def tick_size(self):
            return self._tick_size

    class MockMt5:
        def __init__(self):
            self.initialized = False
        def terminal_info(self):
            return self.initialized
        def symbol_info(self, symbol):
            if symbol == "EURUSD":
                # Typical values for EURUSD (5-digit broker)
                return MockMt5SymbolInfo(
                    point=0.00001, 
                    volume_min=0.01, 
                    volume_max=50.0, 
                    volume_step=0.01,
                    tick_value=1.0, # Value of 1 tick in account currency for 1 standard lot
                    tick_size=0.00001 # Size of 1 tick (point)
                )
            return None
        # Add necessary constants for order types
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1

    # Temporarily replace mt5 with mock for testing
    original_mt5 = mt5
    mt5 = MockMt5()
    mt5.initialized = True # Simulate MT5 being initialized

    symbol_test = "EURUSD"
    entry_test_buy = 1.08500
    entry_test_sell = 1.08550
    point_test = mt5.symbol_info(symbol_test).point

    # Test calculate_sl_tp_prices for BUY
    sl_buy, tp_buy = calculate_sl_tp_prices(entry_test_buy, point_test, mt5.ORDER_TYPE_BUY)
    logging.info(f"BUY Order: Entry={entry_test_buy:.5f}, SL={sl_buy:.5f}, TP={tp_buy:.5f}")
    
    # Verify distances (approx)
    expected_sl_dist_points = RISK_PER_TRADE / 0.01
    expected_tp_dist_points = PROFIT_TARGET_PER_TRADE / 0.01
    logging.info(f"Expected SL distance: {expected_sl_dist_points * point_test:.5f}, Calculated: {entry_test_buy - sl_buy:.5f}")
    logging.info(f"Expected TP distance: {expected_tp_dist_points * point_test:.5f}, Calculated: {tp_buy - entry_test_buy:.5f}")

    # Test calculate_sl_tp_prices for SELL
    sl_sell, tp_sell = calculate_sl_tp_prices(entry_test_sell, point_test, mt5.ORDER_TYPE_SELL)
    logging.info(f"SELL Order: Entry={entry_test_sell:.5f}, SL={sl_sell:.5f}, TP={tp_sell:.5f}")

    # Test calculate_lot_size (requires a valid SL price)
    # For a BUY order, SL is below entry. Let's use sl_buy calculated above.
    calculated_lot = calculate_lot_size(symbol_test, entry_test_buy, sl_buy)
    logging.info(f"Calculated Lot Size for BUY (SL at {sl_buy:.5f}): {calculated_lot:.2f}")

    # For a SELL order, SL is above entry. Let's use sl_sell calculated above.
    calculated_lot_sell = calculate_lot_size(symbol_test, entry_test_sell, sl_sell)
    logging.info(f"Calculated Lot Size for SELL (SL at {sl_sell:.5f}): {calculated_lot_sell:.2f}")

    # Restore original mt5
    mt5 = original_mt5
    
    logging.info("--- risk_management.py testing complete ---")