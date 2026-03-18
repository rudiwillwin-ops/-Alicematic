# TRI_FACTOR/strategies/quiet_strategy.py

import MetaTrader5 as mt5
import pandas as pd
import numpy as np # Added for dummy data generation
import logging

from TRI_FACTOR.mt5_integration.mt5_utils import place_order, get_current_price
from TRI_FACTOR.indicators.technical_indicators import calculate_all_indicators
from TRI_FACTOR.strategies.risk_management import calculate_lot_size, calculate_sl_tp_prices
from TRI_FACTOR.config import (
    QUIET_STRATEGY_DAILY_TRADES_MIN, QUIET_STRATEGY_DAILY_TRADES_MAX,
    RR_RATIO, RISK_PER_TRADE, PROFIT_TARGET_PER_TRADE
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class QuietStrategy:
    def __init__(self, symbol, timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.trades_today = 0
        self.rebates_earned = 0.0 # Simulated
        self.last_trade_time = None
        logging.info(f"Quiet Strategy initialized for {self.symbol} ({self.timeframe})")

    def _interpret_indicator(self, indicator_name, df_last_row):
        """
        Interprets the signal from a single indicator.
        Returns 'buy', 'sell', or 'neutral'.
        This is a simplified interpretation. Real-world indicators have specific thresholds.
        """
        signal = 'neutral'
        try:
            if indicator_name == 'RSI':
                rsi = df_last_row['RSI']
                if rsi < 30: signal = 'buy'
                elif rsi > 70: signal = 'sell'
            elif indicator_name == 'MACD':
                macd = df_last_row['MACD']
                signal_line = df_last_row['MACD_Signal']
                if macd > signal_line and df_last_row['MACD_Hist'] > 0: signal = 'buy'
                elif macd < signal_line and df_last_row['MACD_Hist'] < 0: signal = 'sell'
            elif indicator_name == 'Stoch_K': # Using Stoch_K for signal
                k = df_last_row['Stoch_K']
                if k < 20: signal = 'buy'
                elif k > 80: signal = 'sell'
            elif indicator_name == 'BB_Upper': # Price above/below bands
                close = df_last_row['close']
                upper_band = df_last_row['BB_Upper']
                lower_band = df_last_row['BB_Lower']
                if close < lower_band: signal = 'buy'
                elif close > upper_band: signal = 'sell'
            elif indicator_name == 'SMA_10' or indicator_name == 'EMA_20' or indicator_name == 'SMA_50' or indicator_name == 'EMA_100': # Crossover or price relative to MA
                close = df_last_row['close']
                ma = df_last_row[indicator_name]
                if close > ma: signal = 'buy'
                elif close < ma: signal = 'sell'
            elif indicator_name == 'ATR': # For volatility, not direct signal
                pass # ATR generally not used for direct buy/sell signal in consensus
            elif indicator_name == 'CCI':
                cci = df_last_row['CCI']
                if cci < -100: signal = 'buy'
                elif cci > 100: signal = 'sell'
            elif indicator_name == 'OBV': # OBV rising/falling with price
                obv = df_last_row['OBV']
                prev_obv = df_last_row['OBV'].shift(1) # Needs previous bar
                if obv > prev_obv and df_last_row['close'] > df_last_row['close'].shift(1): signal = 'buy'
                elif obv < prev_obv and df_last_row['close'] < df_last_row['close'].shift(1): signal = 'sell'
            # Ichimoku requires multiple components for signal (Kumo breakout, Tenkan/Kijun cross)
            # For simplicity, if Tenkan > Kijun = buy, else sell
            elif indicator_name == 'Ichimoku_Tenkan':
                tenkan = df_last_row['Ichimoku_Tenkan']
                kijun = df_last_row['Ichimoku_Kijun']
                if tenkan > kijun: signal = 'buy'
                elif tenkan < kijun: signal = 'sell'
            elif indicator_name == 'Momentum':
                momentum = df_last_row['Momentum']
                if momentum > 0: signal = 'buy'
                elif momentum < 0: signal = 'sell'
            elif indicator_name == 'WilliamsR':
                wr = df_last_row['WilliamsR']
                if wr < -80: signal = 'buy'
                elif wr > -20: signal = 'sell'
            elif indicator_name == 'ForceIndex':
                fi = df_last_row['ForceIndex']
                if fi > 0: signal = 'buy'
                elif fi < 0: signal = 'sell'
            elif indicator_name == 'DeMarker':
                dem = df_last_row['DeMarker']
                if dem < 0.3: signal = 'buy'
                elif dem > 0.7: signal = 'sell'
            elif indicator_name == 'StdDev': # For volatility, not direct signal
                pass
            elif indicator_name == 'CMF':
                cmf = df_last_row['CMF']
                if cmf > 0: signal = 'buy'
                elif cmf < 0: signal = 'sell'
            elif indicator_name == 'UltimateOscillator':
                uo = df_last_row['UltimateOscillator']
                if uo < 30: signal = 'buy'
                elif uo > 70: signal = 'sell'
            # Simplified placeholders for complex indicators
            elif indicator_name == 'ADX':
                pass # No direct buy/sell for simplified ADX placeholder
            elif indicator_name == 'ParabolicSAR':
                pass # No direct buy/sell for simplified PSAR placeholder
            elif indicator_name == 'KlingerOscillator':
                pass # No direct buy/sell for simplified KO placeholder

        except KeyError:
            logging.warning(f"Indicator '{indicator_name}' data not found in DataFrame for interpretation.")
            return 'neutral'
        except Exception as e:
            logging.error(f"Error interpreting indicator {indicator_name}: {e}")
            return 'neutral'
        return signal

    def check_consensus_of_20(self, historical_data_df):
        """
        Evaluates the 20 technical indicators for a 'Consensus of 20' signal.
        Args:
            historical_data_df (pd.DataFrame): DataFrame with historical data and calculated indicators.
        Returns:
            str: 'buy', 'sell', or 'neutral' based on consensus.
        """
        if historical_data_df.empty:
            logging.warning("No historical data to check for consensus.")
            return 'neutral'
        
        # Ensure indicators are calculated
        df_with_indicators = calculate_all_indicators(historical_data_df.copy())
        if df_with_indicators.empty:
            logging.error("Failed to calculate indicators for consensus check.")
            return 'neutral'

        last_row = df_with_indicators.iloc[-1]
        
        buy_signals = 0
        sell_signals = 0
        total_directional_indicators = 0

        # Iterate through relevant indicators (from config) and interpret them
        # ATR, StdDev, ADX, ParabolicSAR, KlingerOscillator are more for volatility/trend strength
        # not direct buy/sell, so they won't contribute to 'directional' consensus in this simple check.
        directional_indicators = [
            'RSI', 'MACD', 'Stoch_K', 'BB_Upper', 'SMA_10', 'EMA_20', 'SMA_50', 'EMA_100',
            'CCI', 'OBV', 'Ichimoku_Tenkan', 'Momentum', 'WilliamsR',
            'ForceIndex', 'DeMarker', 'CMF', 'UltimateOscillator'
        ]

        for indicator_name in directional_indicators:
            signal = self._interpret_indicator(indicator_name, last_row)
            if signal == 'buy':
                buy_signals += 1
                total_directional_indicators += 1
            elif signal == 'sell':
                sell_signals += 1
                total_directional_indicators += 1
        
        if total_directional_indicators == 0:
            logging.info("No directional indicators provided a clear signal.")
            return 'neutral'

        buy_ratio = buy_signals / total_directional_indicators
        sell_ratio = sell_signals / total_directional_indicators

        # A "Consensus of 20" for simplicity: more than 70% of directional indicators agree.
        # This threshold can be adjusted.
        CONSENSUS_THRESHOLD = 0.70

        if buy_ratio >= CONSENSUS_THRESHOLD:
            logging.info(f"Quiet Strategy: BUY Consensus of 20 achieved ({buy_signals}/{total_directional_indicators} buy signals).")
            return 'buy'
        elif sell_ratio >= CONSENSUS_THRESHOLD:
            logging.info(f"Quiet Strategy: SELL Consensus of 20 achieved ({sell_signals}/{total_directional_indicators} sell signals).")
            return 'sell'
        else:
            logging.info(f"Quiet Strategy: No strong consensus ({buy_signals} buy, {sell_signals} sell).")
            return 'neutral'

    def execute_trade(self, current_price_ask, current_price_bid):
        """
        Executes a limit order if consensus is met and trade limits allow.
        Args:
            current_price_ask (float): Current ask price.
            current_price_bid (float): Current bid price.
        Returns:
            bool: True if trade was attempted, False otherwise.
        """
        # Ensure MT5 is initialized in the calling context before this.
        
        # In a live trading scenario, `self.trades_today` and `self.last_trade_time`
        # would need to be persisted and updated across runs/days.
        # For this modular component, we assume it's part of a larger loop.
        
        # Placeholder for daily trade limit check
        # if self.trades_today >= QUIET_STRATEGY_DAILY_TRADES_MAX:
        #     logging.info("Quiet Strategy: Daily trade limit reached.")
        #     return False

        # In live trading, this would involve retrieving fresh historical data.
        # For this function, we assume the data is passed to check_consensus_of_20
        # which needs to be called separately before this.
        
        # For now, this function is called after consensus is determined.
        # It needs the signal to proceed.
        logging.error("QuietStrategy.execute_trade called without a specific signal. This function expects signal from Consensus.")
        return False
        
    def generate_and_place_limit_order(self, signal_type, entry_price_for_limit):
        """
        Generates and attempts to place a limit order.
        Args:
            signal_type (str): 'buy' or 'sell'.
            entry_price_for_limit (float): The desired price for the limit order.
        Returns:
            bool: True if order was placed, False otherwise.
        """
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logging.error(f"Cannot get symbol info for {self.symbol}. Exiting trade attempt.")
            return False
        
        point = symbol_info.point
        
        sl_price, tp_price = calculate_sl_tp_prices(
            entry_price=entry_price_for_limit,
            point_size=point,
            trade_type=mt5.ORDER_TYPE_BUY if signal_type == 'buy' else mt5.ORDER_TYPE_SELL
        )
        
        # Calculate lot size based on the determined SL price
        lot_size = calculate_lot_size(self.symbol, entry_price_for_limit, sl_price)

        if lot_size <= 0:
            logging.warning(f"Quiet Strategy: Calculated lot size ({lot_size}) is not valid. Skipping order placement.")
            return False

        order_type = mt5.ORDER_TYPE_BUY_LIMIT if signal_type == 'buy' else mt5.ORDER_TYPE_SELL_LIMIT
        
        logging.info(f"Quiet Strategy: Attempting to place {signal_type.upper()} LIMIT order for {self.symbol} at {entry_price_for_limit:.5f}, Lot: {lot_size:.2f}, SL: {sl_price:.5f}, TP: {tp_price:.5f}")
        
        order_result = place_order(
            symbol=self.symbol,
            order_type=order_type,
            volume=lot_size,
            price=entry_price_for_limit, # Limit price
            sl=sl_price,
            tp=tp_price,
            comment=f"Quiet_{signal_type.upper()}"
        )
        
        if order_result and order_result.retcode == mt5.TRADE_RETCODE_DONE:
            self.trades_today += 1
            self.last_trade_time = pd.Timestamp.now()
            self.rebates_earned += (PROFIT_TARGET_PER_TRADE * 0.05) # Simulate 5% of TP as rebate
            logging.info(f"Quiet Strategy: Successfully placed {signal_type.upper()} LIMIT order. Trades today: {self.trades_today}. Rebates earned: {self.rebates_earned:.2f}")
            return True
        else:
            logging.error(f"Quiet Strategy: Failed to place {signal_type.upper()} LIMIT order.")
            return False


if __name__ == "__main__":
    logging.info("--- Testing quiet_strategy.py ---")

    # Mock MT5 connection and data for testing
    # This assumes mt5_utils and technical_indicators are somewhat functional
    # For a full test, run through START_TRADES.py
    
    # Simulate historical data with required columns for indicator calculation
    dummy_data = {
        'time': pd.to_datetime(pd.date_range(start='2023-01-01', periods=200, freq='min')),
        'open': np.random.rand(200) * 100 + 1000,
        'high': np.random.rand(200) * 100 + 1010,
        'low': np.random.rand(200) * 100 + 990,
        'close': np.random.rand(200) * 100 + 1005,
        'tick_volume': np.random.randint(100, 1000, 200)
    }
    dummy_df = pd.DataFrame(dummy_data).set_index('time')
    
    # Initialize a Quiet Strategy instance
    quiet_strat = QuietStrategy(symbol="EURUSD", timeframe=mt5.TIMEFRAME_M1)

    # Check for consensus using dummy data
    logging.info("Checking for consensus with dummy data...")
    consensus_signal = quiet_strat.check_consensus_of_20(dummy_df.copy())
    logging.info(f"Consensus Signal: {consensus_signal}")

    # To fully test execute_trade, a live MT5 connection and real price data would be needed.
    # The `generate_and_place_limit_order` function relies on `mt5_utils.place_order`
    # which would connect to MT5.
    
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
                return MockMt5OrderResult(mt5.TRADE_RETCODE_DONE, 12345, "Mock Order OK")
            return MockMt5OrderResult(mt5.TRADE_RETCODE_REJECT, 0, "Mock Order Failed")
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

    # Test placing a limit order if a consensus signal was generated
    mock_entry_price_buy = 1.08500
    mock_entry_price_sell = 1.08550

    if consensus_signal == 'buy':
        logging.info("Attempting to place a BUY LIMIT order based on consensus.")
        quiet_strat.generate_and_place_limit_order('buy', mock_entry_price_buy)
    elif consensus_signal == 'sell':
        logging.info("Attempting to place a SELL LIMIT order based on consensus.")
        quiet_strat.generate_and_place_limit_order('sell', mock_entry_price_sell)
    else:
        logging.info("No consensus signal to place an order.")

    # Restore original mt5
    mt5 = original_mt5

    logging.info("--- quiet_strategy.py testing complete ---")