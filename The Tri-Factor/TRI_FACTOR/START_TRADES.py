# TRI_FACTOR/START_TRADES.py

import MetaTrader5 as mt5
import time
import logging
from datetime import datetime, timedelta
import os # For checking if MT5 is running (simplified)

# Import modules from TRI_FACTOR
from TRI_FACTOR.mt5_integration.mt5_utils import (
    initialize_mt5, shutdown_mt5, launch_mt5_terminal,
    get_historical_data, get_current_price
)
from TRI_FACTOR.indicators.technical_indicators import calculate_all_indicators
from TRI_FACTOR.strategies.quiet_strategy import QuietStrategy
from TRI_FACTOR.strategies.volatile_strategy import VolatileStrategy
from TRI_FACTOR.strategies.black_swan_strategy import BlackSwanStrategy
from TRI_FACTOR.utils.utils import (
    setup_logging, play_profit_ping,
    get_simulated_news_sentiment, get_simulated_external_robot_signals,
    get_simulated_market_volatility
)
from TRI_FACTOR.config import (
    MARKET_SCAN_DURATION_SECONDS,
    INDICATORS_LIST,
    PROFIT_TARGET_PER_TRADE,
    BLACK_SWAN_VOLATILITY_THRESHOLD,
    BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD,
    MT5_TERMINAL_PATH
)

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)

def run_market_scan(symbol):
    """
    Performs a mandatory 5-minute market scan.
    Analyzes technical indicators, news, and external robot signals.
    """
    logger.info(f"Initiating mandatory {MARKET_SCAN_DURATION_SECONDS}-second market scan for {symbol}...")
    scan_start_time = time.time()
    
    # Initialize Black Swan strategy for condition checks during scan
    black_swan_strategy = BlackSwanStrategy()

    while (time.time() - scan_start_time) < MARKET_SCAN_DURATION_SECONDS:
        logger.debug("Scanning market data...")

        # 1. Analyze Technical Indicators (Requires historical data)
        # Fetch current M1 data (e.g., last 100 bars) for indicator calculation
        historical_data = get_historical_data(symbol, mt5.TIMEFRAME_M1, 100)
        if historical_data is not None and not historical_data.empty:
            df_with_indicators = calculate_all_indicators(historical_data.copy())
            # For now, we just calculate them. Actual strategy will interpret.
            logger.debug(f"Calculated indicators for last bar: {df_with_indicators.iloc[-1].index.tolist()}")
        else:
            logger.warning(f"Could not retrieve historical data for {symbol} during scan.")

        # 2. Read Live News Feeds (Simulated)
        news_sentiment = get_simulated_news_sentiment(symbol)
        logger.debug(f"Current news sentiment for {symbol}: {news_sentiment:.2f}")

        # 3. Compare signals from 10+ external robot sources (Simulated)
        external_signals = get_simulated_external_robot_signals(symbol)
        logger.debug(f"External robot signals for {symbol}: {sum(external_signals)}/12 buy signals")

        # Check Black Swan conditions during the scan
        if black_swan_strategy.check_black_swan_conditions(symbol):
            logger.critical("Black Swan conditions detected during scan. Trading locked for 24 hours.")
            return False # Black Swan triggered, no trading
        
        time_left = MARKET_SCAN_DURATION_SECONDS - (time.time() - scan_start_time)
        logger.info(f"Market scan in progress... {time_left:.1f} seconds remaining.")
        time.sleep(5) # Scan every 5 seconds

    logger.info("Market scan complete.")
    return True # Scan completed without Black Swan trigger

def monitor_trades(active_trades, mt5_connection_established):
    """
    Monitors active trades for profit target hits and plays audio alert.
    Args:
        active_trades (dict): Dictionary to keep track of trades.
        mt5_connection_established (bool): Is MT5 initialized.
    """
    if not mt5_connection_established:
        logger.warning("MT5 connection not established. Cannot monitor trades.")
        return

    # Get all open positions
    positions = mt5.positions_get()
    if positions is None:
        logger.error(f"Failed to get positions, error code: {mt5.last_error()}")
        return

    for pos in positions:
        ticket = pos.ticket
        current_profit = pos.profit

        # In a real system, you might filter positions by a magic number or comment
        # associated with your strategy. For simplicity, we're checking positions
        # that could be ours based on comments.
        is_our_trade = False
        if "Quiet_" in pos.comment or "Volatile_" in pos.comment:
            is_our_trade = True

        if is_our_trade:
            if ticket not in active_trades:
                active_trades[ticket] = {
                    "symbol": pos.symbol,
                    "type": pos.type,
                    "volume": pos.volume,
                    "entry_price": pos.price_open,
                    "profit_target_actual": pos.tp # TP set by MT5 itself
                }
                logger.info(f"New trade {ticket} detected and added to monitor list. TP: {pos.tp}")

            # Check if profit target has been hit
            # Since SL/TP are attached to the order, MT5 handles closure automatically.
            # We check if the position is no longer open but was previously in active_trades.
            # If the position is closed and profit was hit (or loss), MT5 already handled it.
            # The goal here is to play a ping *when* the profit target is hit.
            # This requires checking the profit on *open* positions.
            
            # Simple check for profit target hit (if position is still open)
            if current_profit >= PROFIT_TARGET_PER_TRADE and active_trades.get(ticket, {}).get("alert_played") != True:
                logger.info(f"Trade {ticket} hit profit target! P/L: {current_profit:.2f}")
                play_profit_ping()
                active_trades[ticket]["alert_played"] = True # Mark alert as played

    # Clean up closed trades from our active_trades dictionary
    closed_tickets = [t for t in active_trades if t not in [p.ticket for p in positions]]
    for ticket in closed_tickets:
        if active_trades[ticket].get("alert_played"):
            logger.info(f"Trade {ticket} (profit alert played) closed and removed from monitoring.")
        else:
            logger.info(f"Trade {ticket} (no profit alert played) closed and removed from monitoring.")
        del active_trades[ticket]


def main():
    logger.info("--- Starting The Tri-Factor Trading System ---")

    # 1. Manual 'Start' (just by running the script)
    # 2. Launch MT5 Terminal
    if not launch_mt5_terminal():
        logger.critical("Failed to launch MT5 terminal. Exiting.")
        return
    logger.info("Waiting 10 seconds for MT5 terminal to fully load and connect...")
    time.sleep(10) # Give MT5 time to load

    # 3. Initialize MT5 connection
    mt5_connection_established = initialize_mt5()
    if not mt5_connection_established:
        logger.critical("Failed to initialize MT5 connection. Exiting.")
        return

    # Define the symbol to trade (can be configured in config.py or passed as argument)
    trading_symbol = "EURUSD" # Example symbol

    # 4. Mandatory 5-Minute Market Scan
    if not run_market_scan(trading_symbol):
        logger.warning("Market scan failed or Black Swan triggered. Trading will not commence.")
        shutdown_mt5()
        return

    # Re-check Black Swan status AFTER the scan (it might have triggered during the scan)
    black_swan_strategy = BlackSwanStrategy()
    if not black_swan_strategy.is_trading_allowed():
        logger.critical("Black Swan lockout is active. Trading will not commence.")
        shutdown_mt5()
        return

    logger.info("Market scan successful. Engaging authorized strategies.")

    # Initialize strategies
    quiet_strategy = QuietStrategy(symbol=trading_symbol)
    volatile_strategy = VolatileStrategy(symbol=trading_symbol)

    # Dictionary to keep track of active trades (ticket: trade_details)
    active_trades = {}
    
    # Main trading loop
    logger.info("Entering main trading loop. Monitoring for opportunities...")
    try:
        while True:
            # Get latest historical data for strategy analysis
            # Ensure enough bars for all indicators (e.g., Ichimoku needs 52+26 bars)
            historical_data = get_historical_data(trading_symbol, mt5.TIMEFRAME_M1, 200) 
            if historical_data is None or historical_data.empty:
                logger.error(f"Failed to get historical data for {trading_symbol}. Skipping this cycle.")
                time.sleep(10)
                continue
            
            # Check current prices
            current_ask, current_bid = get_current_price(trading_symbol)
            if current_ask is None or current_bid is None:
                logger.error(f"Failed to get current prices for {trading_symbol}. Skipping this cycle.")
                time.sleep(10)
                continue

            # Ensure trading is allowed by Black Swan
            black_swan_strategy.check_black_swan_conditions(trading_symbol) # Re-check periodically
            if not black_swan_strategy.is_trading_allowed():
                logger.warning(f"Trading locked by Black Swan. Waiting until {black_swan_strategy.lockout_until}.")
                time.sleep(60) # Wait longer if locked
                continue
            
            # --- Quiet Strategy Logic ---
            # Quiet strategy needs current bar to calculate consensus, and places limit orders
            consensus_signal = quiet_strategy.check_consensus_of_20(historical_data.copy())
            if consensus_signal != 'neutral':
                # For limit orders, we need a price to place the limit.
                # For simplicity, let's try to place a limit order at a slightly better price than current.
                # e.g., for BUY LIMIT, slightly below current bid. For SELL LIMIT, slightly above current ask.
                symbol_point = mt5.symbol_info(trading_symbol).point
                if consensus_signal == 'buy':
                    limit_entry_price = current_bid - (symbol_point * 5) # 5 points below bid
                    quiet_strategy.generate_and_place_limit_order(consensus_signal, limit_entry_price)
                elif consensus_signal == 'sell':
                    limit_entry_price = current_ask + (symbol_point * 5) # 5 points above ask
                    quiet_strategy.generate_and_place_limit_order(consensus_signal, limit_entry_price)

            # --- Volatile Strategy Logic ---
            # Volatile strategy looks for runaway trends and places market orders
            runaway_signal = volatile_strategy.detect_runaway_trend(historical_data.copy())
            if runaway_signal != 'neutral':
                volatile_strategy.execute_trade(runaway_signal)

            # Monitor active trades and play ping on profit
            monitor_trades(active_trades, mt5_connection_established)

            # Wait before next cycle
            time.sleep(10) # Check every 10 seconds (adjust as needed)

    except KeyboardInterrupt:
        logger.info("Trading system interrupted by user.")
    except Exception as e:
        logger.critical(f"An unhandled error occurred in the main trading loop: {e}", exc_info=True)
    finally:
        logger.info("Shutting down MT5 connection.")
        shutdown_mt5()
        logger.info("The Tri-Factor Trading System stopped.")


if __name__ == "__main__":
    main()

