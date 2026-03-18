# TRI_FACTOR/utils/utils.py

import logging
import sys
import winsound
import random
import time

from TRI_FACTOR.config import (
    LOG_FILE, LOG_LEVEL,
    PROFIT_PING_FREQUENCY, PROFIT_PING_DURATION,
    BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD
)

def setup_logging():
    """Configures logging for the application."""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    logging.info(f"Logging configured. Output to {LOG_FILE} and console at {LOG_LEVEL} level.")

def play_profit_ping():
    """Plays a loud ping sound using the internal motherboard buzzer (winsound)."""
    try:
        winsound.Beep(PROFIT_PING_FREQUENCY, PROFIT_PING_DURATION)
        logging.info("Played profit ping sound.")
    except Exception as e:
        logging.error(f"Failed to play profit ping sound: {e}. Ensure speakers are active and winsound is supported.")

def get_simulated_news_sentiment(symbol="X"):
    """
    Simulates real-time news sentiment for a given symbol.
    Returns a float between -1.0 (very negative) and 1.0 (very positive).
    """
    # For a real system, this would integrate with a news API and NLP.
    # For simulation, we'll return a random value that can occasionally trigger Black Swan.
    sentiment = random.uniform(-1.0, 1.0)
    logging.debug(f"Simulated news sentiment for {symbol}: {sentiment:.2f}")
    return sentiment

def get_simulated_external_robot_signals(symbol="X"):
    """
    Simulates signals from 10+ external robot sources.
    Returns a list of boolean signals (True for buy/strong, False for sell/weak/neutral).
    """
    # In a real system, this would involve APIs or parsing external data sources.
    # For simulation, we'll generate random boolean signals.
    signals = [random.choice([True, False]) for _ in range(12)] # Simulating 12 sources
    logging.debug(f"Simulated external robot signals for {symbol}: {signals}")
    return signals

def get_simulated_market_volatility():
    """
    Simulates current market volatility (e.g., as a percentage change or ATR multiple).
    Returns a float representing volatility.
    """
    # In a real system, this would be derived from real-time price data (e.g., current ATR, implied volatility).
    # For simulation, return a random value that can occasionally trigger Black Swan.
    volatility = random.uniform(0.001, 0.01) # e.g., 0.1% to 1% price movement
    logging.debug(f"Simulated market volatility: {volatility:.4f}")
    return volatility

if __name__ == "__main__":
    setup_logging()
    logging.info("--- Testing utils.py ---")

    logging.info("Testing profit ping...")
    play_profit_ping()
    time.sleep(1)

    logging.info("Testing simulated news sentiment...")
    for _ in range(3):
        sentiment = get_simulated_news_sentiment("EURUSD")
        logging.info(f"News sentiment: {sentiment:.2f}")
        if sentiment < BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD:
            logging.warning(f"Simulated news sentiment ({sentiment:.2f}) below Black Swan threshold ({BLACK_SWAN_NEWS_SENTIMENT_THRESHOLD})!")
        time.sleep(0.5)

    logging.info("Testing simulated external robot signals...")
    for _ in range(3):
        signals = get_simulated_external_robot_signals("EURUSD")
        logging.info(f"External signals count (True): {signals.count(True)}")
        time.sleep(0.5)

    logging.info("Testing simulated market volatility...")
    for _ in range(3):
        volatility = get_simulated_market_volatility()
        logging.info(f"Market volatility: {volatility:.4f}")
        time.sleep(0.5)

    logging.info("--- utils.py testing complete ---")