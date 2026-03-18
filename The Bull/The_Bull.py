# The Bull - A Neutral Grid Trading Bot

import ccxt
import pandas as pd
import pandas_ta as ta
import time
import os
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

# API Keys
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

from config import *

# --- Exchange Initialization ---
def initialize_exchange():
    """Initializes the exchange with API keys."""
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'options': {
            'defaultType': 'spot',
        },
        'enableRateLimit': True,
    })
    if not DRY_RUN:
        exchange.load_markets()
    return exchange

# --- Main Bot Logic ---
def run_bot():
    """Main function to run the trading bot."""
    print("Starting 'The Bull' Grid Trading Bot...")
    exchange = initialize_exchange()

    while True:
        try:
            print("\n--- New Iteration ---")
            # Cancel all orders and re-center grid
            cancel_all_orders(exchange)
            
            # Fetch data and calculate indicators
            ohlcv = fetch_ohlcv(exchange, SYMBOL)
            indicators = calculate_indicators(ohlcv)
            
            # Apply risk filters
            if not apply_risk_filters(indicators):
                time.sleep(60) # Wait before next check
                continue

            # Place grid orders
            place_grid_orders(exchange, indicators)

            print(f"Waiting for {HEARTBEAT} seconds for the next cycle...")
            time.sleep(HEARTBEAT)

        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(60)

def fetch_ohlcv(exchange, symbol, timeframe='5m', limit=100):
    """Fetches OHLCV data for a given symbol."""
    print(f"Fetching OHLCV data for {symbol}...")
    if DRY_RUN:
        # In dry run, simulate ohlcv data
        # This part should be replaced with a more realistic simulation for backtesting
        return [
            [int(time.time() * 1000) - i*300000, 40000+i, 40100, 39900, 40050, 10] 
            for i in range(limit)
        ]
    return exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

def calculate_indicators(ohlcv_data):
    """Calculates technical indicators."""
    print("Calculating indicators...")
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # ATR
    atr = df.ta.atr(length=14)
    df['atr'] = atr
    df['atr_avg'] = atr.rolling(window=14).mean()
    
    # ADX
    adx = df.ta.adx(length=14)
    df = pd.concat([df, adx], axis=1)

    # RSI
    df['rsi'] = df.ta.rsi(length=14)
    
    # Current Price
    current_price = df['close'].iloc[-1]
    
    indicators = {
        'current_price': current_price,
        'atr': df['atr'].iloc[-1],
        'atr_avg': df['atr_avg'].iloc[-1],
        'adx': df[f'ADX_14'].iloc[-1],
        'rsi': df['rsi'].iloc[-1],
    }
    print(f"Indicators: {indicators}")
    return indicators

def apply_risk_filters(indicators):
    """Applies risk filters and returns True if trading is allowed."""
    print("Applying risk filters...")
    # Volatility Brake
    if indicators['atr'] > indicators['atr_avg'] * ATR_MULTIPLIER:
        print(f"Risk Filter: Volatility brake triggered. ATR {indicators['atr']} > {indicators['atr_avg']} * {ATR_MULTIPLIER}")
        return False
        
    # Trend Filter
    if indicators['adx'] > ADX_THRESHOLD:
        print(f"Risk Filter: Trend filter triggered. ADX {indicators['adx']} > {ADX_THRESHOLD}")
        return False
        
    print("Risk filters passed.")
    return True

def place_grid_orders(exchange, indicators):
    """Places the grid of buy and sell orders."""
    current_price = indicators['current_price']
    print(f"Positioning 'The Bull' Grid around {current_price}...")
    
    # Place buy orders
    if indicators['rsi'] < RSI_OVERBOUGHT:
        for i in range(1, GRID_LEVELS + 1):
            price = current_price * (1 - (GRID_STEP * i))
            print(f"Placing Buy Order {i}: {STAKE_AMOUNT} {SYMBOL.split('/')[0]} at {price}")
            if not DRY_RUN:
                exchange.create_limit_buy_order(SYMBOL, STAKE_AMOUNT, price, {'postOnly': True})
    else:
        print("RSI is overbought, stopping buy orders.")

    # Place sell orders
    if indicators['rsi'] > RSI_OVERSOLD:
        for i in range(1, GRID_LEVELS + 1):
            price = current_price * (1 + (GRID_STEP * i))
            print(f"Placing Sell Order {i}: {STAKE_AMOUNT} {SYMBOL.split('/')[0]} at {price}")
            if not DRY_RUN:
                exchange.create_limit_sell_order(SYMBOL, STAKE_AMOUNT, price, {'postOnly': True})
    else:
        print("RSI is oversold, stopping sell orders.")

def cancel_all_orders(exchange):
    """Cancels all open orders for the symbol."""
    print(f"Cancelling all open orders for {SYMBOL}...")
    if not DRY_RUN:
        open_orders = exchange.fetch_open_orders(SYMBOL)
        for order in open_orders:
            exchange.cancel_order(order['id'], SYMBOL)
            print(f"Cancelled order {order['id']}")

if __name__ == "__main__":
    run_bot()
