# TRI_FACTOR/strategies/volatile_strategy.py

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
import time

from TRI_FACTOR.mt5_integration.mt5_utils import place_order, get_current_price, get_historical_data
from TRI_FACTOR.strategies.risk_management import calculate_lot_size, calculate_sl_tp_prices
from TRI_FACTOR.config import (
    VOLATILE_STRATEGY_MOMENTUM_THRESHOLD,
    RR_RATIO, RISK_PER_TRADE, PROFIT_TARGET_PER_TRADE
)
from TRI_FACTOR.indicators.technical_indicators import _calculate_ema, _calculate_momentum # Import specific indicators if needed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VolatileStrategy:
    def __init__(self, symbol, timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.trades_executed = 0
        self.last_trade_time = None
        logging.info(f"Volatile Strategy initialized for {self.symbol} ({self.timeframe})")

    def detect_runaway_trend(self, historical_data_df):
        """
        Detects a 'Runaway' trend based on rapid price movement and momentum.
        Args:
            historical_data_df (pd.DataFrame): Historical data (OHLCV).
        Returns:
            str: 'buy', 'sell', or 'neutral'.
        """
        if historical_data_df.empty or len(historical_data_df) < 5: # Need at least a few bars for momentum
            logging.debug("Insufficient historical data for runaway trend detection.")
            return 'neutral'

        # Use the latest bars for detection
        recent_data = historical_data_df.iloc[-5:] # Look at last 5 bars

        # Simplified detection logic:
        # 1. Strong directional movement (e.g., all 5 bars close higher/lower than open)
        # 2. Significant cumulative change over the period
        # 3. High momentum
        
        # Check for consecutive directional closes
        all_bullish = all(recent_data['close'] > recent_data['open'])
        all_bearish = all(recent_data['close'] < recent_data['open'])

        if not (all_bullish or all_bearish):
            return 'neutral' # No clear consecutive directional movement

        # Calculate cumulative price change
        cumulative_change = recent_data['close'].iloc[-1] - recent_data['open'].iloc[0]
        
        # Calculate momentum (e.g., using a short EMA or diff)
        # Using a simple percentage change as momentum
        percentage_change = (cumulative_change / recent_data['open'].iloc[0])

        # Check against a threshold
        if all_bullish and percentage_change > VOLATILE_STRATEGY_MOMENTUM_THRESHOLD:
            logging.info(f"Volatile Strategy: Detected BUY runaway trend (Change: {percentage_change:.4f})")
            return 'buy'
        elif all_bearish and percentage_change < -VOLATILE_STRATEGY_MOMENTUM_THRESHOLD:
            logging.info(f"Volatile Strategy: Detected SELL runaway trend (Change: {percentage_change:.4f})")
            return 'sell'

        return 'neutral'

    def execute_trade(self, signal_type):
        """
        Executes a rapid-fire market order based on the detected runaway trend.
        Args:
            signal_type (str): 'buy' or 'sell'.
        Returns:
            bool: True if order was placed, False otherwise.
        """
        if not mt5.terminal_info():
            logging.error("MT5 not initialized. Cannot execute volatile trade.")
            return False

        current_ask, current_bid = get_current_price(self.symbol)
        if current_ask is None or current_bid is None:
            logging.error(f"Failed to get current price for {self.symbol}. Cannot execute volatile trade.")
            return False

        entry_price = current_ask if signal_type == 'buy' else current_bid
        
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logging.error(f"Cannot get symbol info for {self.symbol}. Exiting trade attempt.")
            return False
        
        point = symbol_info.point
        
        sl_price, tp_price = calculate_sl_tp_prices(
            entry_price=entry_price,
            point_size=point,
            trade_type=mt5.ORDER_TYPE_BUY if signal_type == 'buy' else mt5.ORDER_TYPE_SELL
        )
        
        # Calculate lot size based on the determined SL price
        lot_size = calculate_lot_size(self.symbol, entry_price, sl_price)

        if lot_size <= 0:
            logging.warning(f"Volatile Strategy: Calculated lot size ({lot_size}) is not valid. Skipping order placement.")
            return False

        order_type = mt5.ORDER_TYPE_BUY if signal_type == 'buy' else mt5.ORDER_TYPE_SELL
        
        logging.info(f"Volatile Strategy: Attempting to place {signal_type.upper()} MARKET order for {self.symbol} at {entry_price:.5f}, Lot: {lot_size:.2f}, SL: {sl_price:.5f}, TP: {tp_price:.5f}")
        
        order_result = place_order(
            symbol=self.symbol,
            order_type=order_type,
            volume=lot_size,
            price=0.0, # Market order, price is not set by user
            sl=sl_price,
            tp=tp_price,
            comment=f"Volatile_{signal_type.upper()}"
        )
        
        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
            self.trades_executed += 1
            self.last_trade_time = pd.Timestamp.now()
            logging.info(f"Volatile Strategy: Successfully placed {signal_type.upper()} MARKET order. Trades executed: {self.trades_executed}")
            return True
        else:
            logging.error(f"Volatile Strategy: Failed to place {signal_type.upper()} MARKET order.")
            return False

if __name__ == "__main__":
    logging.info("--- Testing volatile_strategy.py ---")

    # Mock MT5 connection and data for testing
    # Simulate historical data with required columns for indicator calculation
    dummy_data = {
        'time': pd.to_datetime(pd.date_range(start='2023-01-01', periods=200, freq='min')),
        'open': np.zeros(200),
        'high': np.zeros(200),
        'low': np.zeros(200),
        'close': np.zeros(200),
        'tick_volume': np.random.randint(100, 1000, 200)
    }
    
    # Create a bullish runaway trend
    for i in range(5):
        dummy_data['open'][i+195] = 1.05000 + i * 0.00010
        dummy_data['close'][i+195] = 1.05000 + (i + 1) * 0.00010
        dummy_data['high'][i+195] = dummy_data['close'][i+195] + 0.00005
        dummy_data['low'][i+195] = dummy_data['open'][i+195] - 0.00005

    # Create a bearish runaway trend (for another test)
    # for i in range(5):
    #     dummy_data['open'][i+195] = 1.06000 - i * 0.00010
    #     dummy_data['close'][i+195] = 1.06000 - (i + 1) * 0.00010
    #     dummy_data['high'][i+195] = dummy_data['open'][i+195] + 0.00005
    #     dummy_data['low'][i+195] = dummy_data['close'][i+195] - 0.00005

    test_df = pd.DataFrame(dummy_data).set_index('time')
    
    # Initialize Volatile Strategy instance
    volatile_strat = VolatileStrategy(symbol="EURUSD", timeframe=mt5.TIMEFRAME_M1)

    logging.info("Checking for runaway trend with dummy data (bullish)...")
    runaway_signal = volatile_strat.detect_runaway_trend(test_df.copy())
    logging.info(f"Runaway Trend Signal: {runaway_signal}")

    # Mocking MT5 for place_order and symbol_info for isolated testing.
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

    class MockMt5OrderResult:
        def __init__(self, retcode, order, comment=""):
            self.retcode = retcode
            self.order = order
            self.comment = comment
        def _asdict(self):
            return {"retcode": self.retcode, "order": self.order, "comment": self.comment}

    class MockMt5:
        def __init__(self):
            self.initialized = True # Assume initialized for this test
            self._ask = 1.05050
            self._bid = 1.05040
        def terminal_info(self):
            return self.initialized
        def symbol_info(self, symbol):
            if symbol == "EURUSD":
                return MockMt5SymbolInfo(
                    point=0.00001, volume_min=0.01, volume_max=50.0, volume_step=0.01,
                    tick_value=1.0, tick_size=0.00001
                )
            return None
        def symbol_select(self, symbol, select):
            return True # Always successful in mock
        def order_send(self, request):
            if request["symbol"] == "EURUSD":
                logging.info(f"Mock MT5: Order sent: {request}")
                return MockMt5OrderResult(mt5.TRADE_RETCODE_DONE, 54321, "Mock Order OK")
            return MockMt5OrderResult(mt5.TRADE_RETCODE_REJECT, 0, "Mock Order Failed")
        def symbol_info_tick(self, symbol):
            class MockTick:
                def __init__(self, ask, bid):
                    self.ask = ask
                    self.bid = bid
            return MockTick(self._ask, self._bid)

        # Add necessary constants for order types
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        ORDER_TYPE_BUY_LIMIT = 2
        ORDER_TYPE_SELL_LIMIT = 3
        TRADE_ACTION_DEAL = 0
        ORDER_FILLING_FOK = 0
        ORDER_TIME_GTC = 0
        TRADE_RETCODE_DONE = 10009 # Success code
        TRADE_RETCODE_REJECT = 10004 # Rejection code


    # Temporarily replace mt5 with mock for testing
    original_mt5 = mt5
    mt5 = MockMt5()

    # Test executing a trade if runaway signal was generated
    if runaway_signal != 'neutral':
        logging.info(f"Attempting to execute a {runaway_signal.upper()} MARKET order based on runaway trend.")
        volatile_strat.execute_trade(runaway_signal)
    else:
        logging.info("No runaway trend signal to execute a trade.")

    # Restore original mt5
    mt5 = original_mt5

    logging.info("--- volatile_strategy.py testing complete ---")

