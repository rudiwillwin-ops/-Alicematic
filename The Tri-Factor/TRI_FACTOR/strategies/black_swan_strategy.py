# TRI_FACTOR/strategies/black_swan_strategy.py

import logging
import time
from datetime import datetime, timedelta

from TRI_FACTOR.utils.utils import get_simulated_news_sentiment, get_simulated_market_volatility
from TRI_FACTOR.config import (
    BLACK_SWAN_VOLATILITY_THRESHOLD,
    BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD,
    BLACK_SWAN_LOCKOUT_DURATION_HOURS
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BlackSwanStrategy:
    def __init__(self):
        self.trading_locked = False
        self.lockout_until = None
        logging.info("Black Swan Strategy initialized.")

    def check_black_swan_conditions(self, symbol="X"):
        """
        Checks for Black Swan conditions (high volatility or extreme news sentiment).
        Args:
            symbol (str): The symbol being monitored (for news sentiment).
        Returns:
            bool: True if Black Swan conditions are met, False otherwise.
        """
        if self.trading_locked:
            if datetime.now() < self.lockout_until:
                logging.warning(f"Black Swan: Trading is currently locked. Resumes at {self.lockout_until}.")
                return True # Conditions still met (due to lockout)
            else:
                self.trading_locked = False
                self.lockout_until = None
                logging.info("Black Swan: Trading lockout expired. Resuming normal operations.")

        # Simulate market volatility
        market_volatility = get_simulated_market_volatility()
        if market_volatility > BLACK_SWAN_VOLATILITY_THRESHOLD:
            logging.critical(f"BLACK SWAN ALERT: Market volatility ({market_volatility:.4f}) exceeds threshold ({BLACK_SWAN_VOLATILITY_THRESHOLD:.4f}).")
            self._activate_lockout("high market volatility")
            return True

        # Simulate news sentiment
        news_sentiment = get_simulated_news_sentiment(symbol)
        if news_sentiment < BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD:
            logging.critical(f"BLACK SWAN ALERT: News sentiment ({news_sentiment:.2f}) below threshold ({BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD:.2f}).")
            self._activate_lockout("extreme negative news sentiment")
            return True
            
        logging.info("Black Swan: No critical conditions detected.")
        return False

    def _activate_lockout(self, reason):
        """Activates the trading lockout for a specified duration."""
        self.trading_locked = True
        self.lockout_until = datetime.now() + timedelta(hours=BLACK_SWAN_LOCKOUT_DURATION_HOURS)
        logging.critical(f"BLACK SWAN: Trading locked for {BLACK_SWAN_LOCKOUT_DURATION_HOURS} hours due to {reason}. Will resume at {self.lockout_until}.")

    def is_trading_allowed(self):
        """
        Checks if trading is currently allowed based on Black Swan conditions.
        Returns:
            bool: True if trading is allowed, False if locked.
        """
        # Re-check in case time has passed since last check
        if self.trading_locked and datetime.now() >= self.lockout_until:
            self.trading_locked = False
            self.lockout_until = None
            logging.info("Black Swan: Trading lockout expired. Resuming normal operations.")
            
        return not self.trading_locked

if __name__ == "__main__":
    logging.info("--- Testing black_swan_strategy.py ---")

    bs_strategy = BlackSwanStrategy()
    test_symbol = "EURUSD"

    # Test 1: No Black Swan conditions (initial state)
    logging.info("\n--- Test 1: No Black Swan conditions ---")
    if bs_strategy.is_trading_allowed():
        logging.info("Trading allowed (initial state).")
    else:
        logging.error("Trading unexpectedly locked.")

    # Test 2: Trigger Black Swan via volatility (simulated high volatility)
    logging.info("\n--- Test 2: Trigger Black Swan via high volatility ---")
    # Temporarily modify config values for predictable testing if needed, or rely on random.
    # For this test, we'll assume random might hit the threshold or just log the check.
    
    # Force a trigger by temporarily overriding the simulated functions
    original_get_vol = get_simulated_market_volatility
    original_get_news = get_simulated_news_sentiment

    def mock_high_volatility():
        return BLACK_SWAN_VOLATILITY_THRESHOLD + 0.001
    def mock_normal_news():
        return 0.5
    
    # Replace global functions for this test block
    from TRI_FACTOR.utils import utils
    utils.get_simulated_market_volatility = mock_high_volatility
    utils.get_simulated_news_sentiment = mock_normal_news

    if bs_strategy.check_black_swan_conditions(test_symbol):
        logging.info("Black Swan conditions detected. Trading should be locked.")
        if not bs_strategy.is_trading_allowed():
            logging.info("Trading confirmed locked.")
        else:
            logging.error("Trading unexpectedly allowed after Black Swan trigger.")
    else:
        logging.info("No Black Swan conditions detected (might be random variation).")
        
    # Test 3: Trading is locked
    logging.info("\n--- Test 3: Trading remains locked ---")
    if not bs_strategy.is_trading_allowed():
        logging.info(f"Trading still locked. Resumes at {bs_strategy.lockout_until}.")
    else:
        logging.error("Trading unexpectedly allowed while in lockout period.")

    # Test 4: Lockout expiration (simulate time passing)
    logging.info(f"\n--- Test 4: Simulating lockout expiration ({BLACK_SWAN_LOCKOUT_DURATION_HOURS} hours later) ---")
    # Manually advance time for the test
    bs_strategy.lockout_until = datetime.now() - timedelta(minutes=1) # Set to 1 min in the past
    
    if bs_strategy.is_trading_allowed():
        logging.info("Trading allowed after lockout expiration.")
    else:
        logging.error("Trading still locked after lockout expiration.")

    # Test 5: Trigger Black Swan via news sentiment (simulated extreme negative news)
    logging.info("\n--- Test 5: Trigger Black Swan via extreme negative news ---")
    def mock_low_volatility():
        return BLACK_SWAN_VOLATILITY_THRESHOLD - 0.001
    def mock_extreme_news():
        return BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD - 0.1
    
    utils.get_simulated_market_volatility = mock_low_volatility
    utils.get_simulated_news_sentiment = mock_extreme_news

    if bs_strategy.check_black_swan_conditions(test_symbol):
        logging.info("Black Swan conditions detected (news). Trading should be locked.")
        if not bs_strategy.is_trading_allowed():
            logging.info("Trading confirmed locked (news).")

    # Restore original functions
    utils.get_simulated_market_volatility = original_get_vol
    utils.get_simulated_news_sentiment = original_get_news


    logging.info("--- black_swan_strategy.py testing complete ---")
