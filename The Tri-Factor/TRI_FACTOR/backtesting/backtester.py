# TRI_FACTOR/backtesting/backtester.py

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

# Import strategy and utility modules
from TRI_FACTOR.indicators.technical_indicators import calculate_all_indicators
from TRI_FACTOR.strategies.quiet_strategy import QuietStrategy
from TRI_FACTOR.strategies.volatile_strategy import VolatileStrategy
from TRI_FACTOR.strategies.black_swan_strategy import BlackSwanStrategy
from TRI_FACTOR.strategies.risk_management import calculate_lot_size, calculate_sl_tp_prices
from TRI_FACTOR.utils.utils import get_simulated_news_sentiment, get_simulated_market_volatility
from TRI_FACTOR.config import (
    RR_RATIO,
    RISK_PER_TRADE,
    PROFIT_TARGET_PER_TRADE,
    BLACK_SWAN_VOLATILITY_THRESHOLD,
    BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD,
    VOLATILE_STRATEGY_MOMENTUM_THRESHOLD
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Mock MT5 for Backtesting ---
# This is crucial as backtesting happens offline without a live MT5 connection
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
    # Constants used by strategies and risk management
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    TRADE_ACTION_DEAL = 0
    ORDER_FILLING_FOK = 0
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_REJECT = 10004
    
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    # ... add other necessary MT5 constants as needed by the strategies

    def terminal_info(self):
        return True # Always initialized in mock
    def symbol_info(self, symbol):
        if symbol == "EURUSD": # Example symbol
            return MockMt5SymbolInfo(
                point=0.00001, volume_min=0.01, volume_max=50.0, volume_step=0.01,
                tick_value=1.0, tick_size=0.00001
            )
        return None
    def symbol_select(self, symbol, select):
        return True # Always successful in mock
    def order_send(self, request):
        logger.debug(f"Mock MT5: Order sent: {request}")
        # In backtesting, this doesn't actually send an order.
        # It just validates the request and returns a success.
        return MockMt5OrderResult(self.TRADE_RETCODE_DONE, np.random.randint(100000, 999999), "Mock Order OK")
    def symbol_info_tick(self, symbol):
        # Return dummy tick data for current price
        class MockTick:
            def __init__(self, ask, bid):
                self.ask = ask
                self.bid = bid
        return MockTick(1.08500 + np.random.rand()*0.00010, 1.08490 + np.random.rand()*0.00010)

# Temporarily replace mt5 with mock for backtesting environment
original_mt5 = mt5
mt5 = MockMt5()

class SimulatedTrade:
    def __init__(self, strategy_name, ticket, symbol, order_type, volume, entry_price, sl, tp, open_time):
        self.strategy_name = strategy_name
        self.ticket = ticket
        self.symbol = symbol
        self.order_type = order_type
        self.volume = volume
        self.entry_price = entry_price
        self.sl = sl
        self.tp = tp
        self.open_time = open_time
        self.close_time = None
        self.close_price = None
        self.profit_loss = 0.0
        self.status = "OPEN"
        logger.debug(f"Trade {ticket} opened: {strategy_name} {order_type} {symbol} @ {entry_price}")

    def update_and_close(self, current_candle_high, current_candle_low, current_close_price, current_time):
        if self.status != "OPEN":
            return

        # Check SL/TP hit within the candle range
        # For simplicity, assuming if price touches SL/TP within the candle, it closes.
        # More advanced backtesters use tick data or finer granularity for order execution.

        if self.order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT]:
            if current_candle_low <= self.sl: # SL hit
                self.close_price = self.sl
                self.profit_loss = -RISK_PER_TRADE
                self.status = "CLOSED_SL"
                logger.debug(f"Trade {self.ticket} hit SL for {self.strategy_name}. P/L: {self.profit_loss:.2f}")
            elif current_candle_high >= self.tp: # TP hit
                self.close_price = self.tp
                self.profit_loss = PROFIT_TARGET_PER_TRADE
                self.status = "CLOSED_TP"
                logger.debug(f"Trade {self.ticket} hit TP for {self.strategy_name}. P/L: {self.profit_loss:.2f}")
        elif self.order_type in [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL_LIMIT]:
            if current_candle_high >= self.sl: # SL hit
                self.close_price = self.sl
                self.profit_loss = -RISK_PER_TRADE
                self.status = "CLOSED_SL"
                logger.debug(f"Trade {self.ticket} hit SL for {self.strategy_name}. P/L: {self.profit_loss:.2f}")
            elif current_candle_low <= self.tp: # TP hit
                self.close_price = self.tp
                self.profit_loss = PROFIT_TARGET_PER_TRADE
                self.status = "CLOSED_TP"
                logger.debug(f"Trade {self.ticket} hit TP for {self.strategy_name}. P/L: {self.profit_loss:.2f}")
        
        if self.status != "OPEN":
            self.close_time = current_time

class Backtester:
    def __init__(self, symbol, timeframe, start_date, end_date):
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.historical_data = self._load_historical_data()
        self.strategies = {
            "Quiet": QuietStrategy(symbol, timeframe),
            "Volatile": VolatileStrategy(symbol, timeframe),
            "BlackSwan": BlackSwanStrategy()
        }
        self.executed_trades = [] # Stores SimulatedTrade objects
        self.current_open_trades = [] # Trades currently active
        self.trading_lock_active = False
        self.lockout_until = None
        logger.info(f"Backtester initialized for {symbol} from {start_date} to {end_date}")

    def _load_historical_data(self):
        """
        Loads historical data for backtesting.
        For a real backtest, this would load from a CSV or a database.
        For now, we generate dummy data.
        """
        logger.info("Generating dummy historical data for backtesting (replace with actual data for real tests)...")
        num_bars = (self.end_date - self.start_date).days * 24 * 60 # M1 bars per day
        if num_bars < 200: # Ensure enough bars for indicators
            num_bars = 2000
            self.start_date = self.end_date - timedelta(minutes=num_bars)

        dates = pd.to_datetime(pd.date_range(start=self.start_date, periods=num_bars, freq='min'))
        
        open_prices = np.random.rand(num_bars) * 100 + 1000
        close_prices = open_prices + (np.random.rand(num_bars) - 0.5) * 2 # Slight variation
        high_prices = np.maximum(open_prices, close_prices) + np.random.rand(num_bars) * 5
        low_prices = np.minimum(open_prices, close_prices) - np.random.rand(num_bars) * 5
        
        # Ensure high >= low and adjust open/close if needed
        high_prices = np.maximum(high_prices, np.maximum(open_prices, close_prices))
        low_prices = np.minimum(low_prices, np.minimum(open_prices, close_prices))

        df = pd.DataFrame({
            'time': dates,
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'tick_volume': np.random.randint(100, 1000, num_bars)
        }).set_index('time')
        logger.info(f"Generated {len(df)} bars of dummy data.")
        return df

    def _simulate_order_placement(self, strategy_name, order_type, volume, entry_price, sl, tp, current_time):
        """
        Simulates placing an order and registers it.
        This intercepts the actual place_order from mt5_utils which calls the mock.
        """
        # Generate a unique ticket for the simulated trade
        ticket = len(self.executed_trades) + 100000
        trade = SimulatedTrade(strategy_name, ticket, self.symbol, order_type, volume, entry_price, sl, tp, current_time)
        self.executed_trades.append(trade)
        self.current_open_trades.append(trade)
        return trade # Return the simulated trade object

    def _intercept_place_order(self, original_place_order_func):
        """
        Temporarily replace the actual place_order with a wrapper for backtesting.
        """
        def wrapper(symbol, order_type, volume, price, sl, tp, deviation=10, comment="Python Order"):
            # The strategy code will call this. We need to create a simulated trade.
            # `current_time` is the time of the current bar being processed in the backtest loop.
            current_bar_time = self.historical_data.index[self.current_bar_index]
            
            # Need to get current ask/bid price based on the current bar's close price for market orders
            # and to determine if limit order would be filled within the bar.
            current_ask = self.historical_data['close'].iloc[self.current_bar_index] + (mt5.symbol_info(self.symbol).point * 1) # Small spread
            current_bid = self.historical_data['close'].iloc[self.current_bar_index] - (mt5.symbol_info(self.symbol).point * 1)
            
            actual_entry_price = price # For limit orders, this is the desired price
            
            # Check if limit order would be filled within the current bar
            if order_type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT]:
                bar_low = self.historical_data['low'].iloc[self.current_bar_index]
                bar_high = self.historical_data['high'].iloc[self.current_bar_index]
                
                if order_type == mt5.ORDER_TYPE_BUY_LIMIT and actual_entry_price >= bar_low and actual_entry_price <= bar_high:
                    # Limit BUY filled at actual_entry_price
                    pass
                elif order_type == mt5.ORDER_TYPE_SELL_LIMIT and actual_entry_price >= bar_low and actual_entry_price <= bar_high:
                    # Limit SELL filled at actual_entry_price
                    pass
                else:
                    logger.debug(f"Mock MT5: Limit order {comment} at {price} not filled within bar {current_bar_time}")
                    # Simulate non-fill
                    return MockMt5OrderResult(mt5.TRADE_RETCODE_REJECT, 0, "Limit not filled in bar")
            else: # Market order
                actual_entry_price = current_ask if order_type == mt5.ORDER_TYPE_BUY else current_bid

            # The strategies would have already calculated lot_size, sl, tp
            # Here we just record the simulated trade
            trade = self._simulate_order_placement(comment.split('_')[0], order_type, volume, actual_entry_price, sl, tp, current_bar_time)
            # Simulate a successful order result
            return MockMt5OrderResult(mt5.TRADE_RETCODE_DONE, trade.ticket, "Mock Order OK")
        return wrapper
        
    def run(self):
        logger.info("Starting backtest...")
        
        # Intercept place_order from mt5_utils to simulate trades
        # Need to ensure this is temporary and only for the backtest scope
        import TRI_FACTOR.mt5_integration.mt5_utils as mt5_utils_module
        original_place_order = mt5_utils_module.place_order
        mt5_utils_module.place_order = self._intercept_place_order(original_place_order)

        # Intercept get_simulated_news_sentiment and get_simulated_market_volatility
        # to provide values that can trigger Black Swan predictably or with variation
        import TRI_FACTOR.utils.utils as utils_module
        original_get_news = utils_module.get_simulated_news_sentiment
        original_get_vol = utils_module.get_simulated_market_volatility
        
        def mock_backtest_news_sentiment(symbol):
            # Example: inject a negative sentiment every N bars
            if self.current_bar_index % 50 == 0: # Every 50 bars
                return BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD - 0.1
            return 0.1 # Normal sentiment otherwise
        
        def mock_backtest_market_volatility():
            # Example: inject high volatility every M bars
            if self.current_bar_index % 75 == 0: # Every 75 bars
                return BLACK_SWAN_VOLATILITY_THRESHOLD + 0.001
            return 0.001 # Normal volatility otherwise

        utils_module.get_simulated_news_sentiment = mock_backtest_news_sentiment
        utils_module.get_simulated_market_volatility = mock_backtest_market_volatility
        
        # Add indicators to the historical data once
        self.historical_data = calculate_all_indicators(self.historical_data)
        self.historical_data.dropna(inplace=True) # Drop rows with NaN from indicator calculation

        if self.historical_data.empty:
            logger.error("Historical data is empty after indicator calculation. Cannot backtest.")
            return

        for self.current_bar_index, (bar_time, current_bar) in enumerate(self.historical_data.iterrows()):
            logger.debug(f"Processing bar: {bar_time}")

            # Update mock current prices for strategies
            # This is a simplification; in a real backtest, current prices would be dynamic
            # For simplicity, we use the close of the current bar as reference.
            current_ask = current_bar['close'] + (mt5.symbol_info(self.symbol).point * 1) # Small spread
            current_bid = current_bar['close'] - (mt5.symbol_info(self.symbol).point * 1)

            # Check Black Swan conditions (this will update self.trading_lock_active)
            # This needs to be called on the BlackSwanStrategy instance.
            self.strategies["BlackSwan"].check_black_swan_conditions(self.symbol)
            if not self.strategies["BlackSwan"].is_trading_allowed():
                logger.warning(f"Backtest: Trading locked by Black Swan at {bar_time}.")
                # Update current open trades, but don't place new ones
                for trade in list(self.current_open_trades):
                    trade.update_and_close(current_bar['high'], current_bar['low'], current_bar['close'], bar_time)
                    if trade.status != "OPEN":
                        self.current_open_trades.remove(trade)
                continue # Skip strategy execution if locked

            # --- Quiet Strategy ---
            quiet_signal = self.strategies["Quiet"].check_consensus_of_20(self.historical_data.iloc[:self.current_bar_index+1].copy())
            if quiet_signal != 'neutral':
                # For Quiet Strategy, place limit orders relative to current price
                if quiet_signal == 'buy':
                    limit_entry_price = current_bid - (mt5.symbol_info(self.symbol).point * 5) # 5 points below bid
                    self.strategies["Quiet"].generate_and_place_limit_order(quiet_signal, limit_entry_price)
                elif quiet_signal == 'sell':
                    limit_entry_price = current_ask + (mt5.symbol_info(self.symbol).point * 5) # 5 points above ask
                    self.strategies["Quiet"].generate_and_place_limit_order(quiet_signal, limit_entry_price)

            # --- Volatile Strategy ---
            volatile_signal = self.strategies["Volatile"].detect_runaway_trend(self.historical_data.iloc[:self.current_bar_index+1].copy())
            if volatile_signal != 'neutral':
                # For Volatile Strategy, market orders
                self.strategies["Volatile"].execute_trade(volatile_signal)

            # Update all currently open trades with current bar's price info
            for trade in list(self.current_open_trades): # Iterate over a copy to allow modification
                trade.update_and_close(current_bar['high'], current_bar['low'], current_bar['close'], bar_time)
                if trade.status != "OPEN":
                    self.current_open_trades.remove(trade)
        
        # After loop, close any remaining open trades at the last close price
        last_close = self.historical_data['close'].iloc[-1]
        for trade in self.current_open_trades:
            trade.close_time = self.historical_data.index[-1]
            trade.close_price = last_close
            # Calculate P/L for trades closed by end of backtest (not SL/TP)
            if trade.status == "OPEN":
                if trade.order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT]:
                    trade.profit_loss = (last_close - trade.entry_price) / mt5.symbol_info(self.symbol).point * PROFIT_TARGET_PER_TRADE / (PROFIT_TARGET_PER_TRADE / RISK_PER_TRADE) # Simplified P/L
                elif trade.order_type in [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL_LIMIT]:
                    trade.profit_loss = (trade.entry_price - last_close) / mt5.symbol_info(self.symbol).point * PROFIT_TARGET_PER_TRADE / (PROFIT_TARGET_PER_TRADE / RISK_PER_TRADE)
                trade.status = "CLOSED_EOD" # End of Day/Data

        logger.info("Backtest complete. Generating report...")
        self.generate_report()
        
        # Restore original functions after backtest
        mt5_utils_module.place_order = original_place_order
        utils_module.get_simulated_news_sentiment = original_get_news
        utils_module.get_simulated_market_volatility = original_get_vol


    def generate_report(self):
        """Generates and prints a side-by-side performance report."""
        report_data = []
        strategy_names = ["Quiet", "Volatile"] # BlackSwan doesn't trade directly

        for strategy_name in strategy_names:
            strategy_trades = [t for t in self.executed_trades if t.strategy_name == strategy_name]
            
            total_profit_loss = sum(t.profit_loss for t in strategy_trades)
            winning_trades = sum(1 for t in strategy_trades if t.profit_loss > 0)
            total_trades = len(strategy_trades)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Simulated rebates for Quiet Strategy
            rebates_earned = self.strategies["Quiet"].rebates_earned if strategy_name == "Quiet" else 0.0
            fees_saved = 0.0 # Placeholder for actual fee calculation

            report_data.append({
                "Strategy": strategy_name,
                "Total Trades": total_trades,
                "Total P/L": f"${total_profit_loss:.2f}",
                "Win Rate (%)": f"{win_rate:.2f}%",
                "Rebates Earned": f"${rebates_earned:.2f}",
                "Fees Saved": f"${fees_saved:.2f}"
            })

        df_report = pd.DataFrame(report_data)
        print("\n--- SIMULTANEOUS TRIPLE BACKTEST REPORT ---")
        print(df_report.to_string(index=False))
        print("-------------------------------------------\n")

        # Black Swan Summary
        bs_strategy = self.strategies["BlackSwan"]
        print("--- BLACK SWAN STRATEGY SUMMARY ---")
        if bs_strategy.trading_locked:
            print(f"Trading was locked at the end of backtest. Last lockout until: {bs_strategy.lockout_until}")
        else:
            print("Trading was not locked by Black Swan at the end of backtest.")
        # Need to track how many times it triggered and for how long.
        # This current simplified version doesn't track historical lockouts.
        print("-----------------------------------\n")

# Revert mt5 global variable change after module loading for other parts of the system
mt5 = original_mt5 

if __name__ == "__main__":
    logger.info("--- Testing backtester.py ---")

    # Example usage:
    backtest_symbol = "EURUSD"
    backtest_timeframe = mt5.TIMEFRAME_M1
    backtest_start_date = datetime(2023, 1, 1)
    backtest_end_date = datetime(2023, 1, 31)

    backtester = Backtester(backtest_symbol, backtest_timeframe, backtest_start_date, backtest_end_date)
    backtester.run()

    logger.info("--- backtester.py testing complete ---")
