# shadow.py
import time
import config
import webbrowser
import simpleaudio as sa
from bybit_client import BybitClient
from strategy import Strategy
from risk_manager import RiskManager
from sentiment_analyzer import SentimentAnalyzer
from dotenv import load_dotenv

def play_sound(filename):
    """Plays a sound file."""
    try:
        wave_obj = sa.WaveObject.from_wave_file(filename)
        play_obj = wave_obj.play()
        play_obj.wait_done()
    except Exception as e:
        print(f"Error playing sound: {e}")

def main():
    """
    Main function to run the Shadow trading bot with Profit-Maker Brain.
    """
    print("Initializing Shadow: Profit-Maker Brain...")
    load_dotenv()

    # --- API Key Validation ---
    if not config.BYBIT_API_KEY or not config.BYBIT_API_SECRET:
        print("Error: Bybit API credentials not found in .env file.")
        return
    
    # --- Initialize Components ---
    bybit_client = BybitClient(config.BYBIT_API_KEY, config.BYBIT_API_SECRET)
    strategy = Strategy() # Uses RSI, no params needed
    risk_manager = RiskManager(
        config.DAILY_TRADE_LIMIT,
        config.TRADE_RISK_PERCENT,
        config.RR_RATIO,
        config.SAFETY_FREEZE_LIMIT,
        config.STOP_LOSS_PERCENT
    )
    sentiment_analyzer = SentimentAnalyzer(config.NEWS_API_KEY)
    
    print("\nShadow Bot Initialization Complete.")
    print("--- STRATEGY: MEAN REVERSION (RSI) ---")
    print(f"Bybit Testnet: {config.BYBIT_TESTNET}")
    print(f"Symbol: {config.SYMBOL}")
    print(f"Risk per Trade: {config.TRADE_RISK_PERCENT * 100}%")
    print(f"Stop-Loss: {config.STOP_LOSS_PERCENT}%")
    print(f"Risk/Reward Ratio: 1:{config.RR_RATIO}")
    print(f"RSI Period: {config.RSI_PERIOD} (Oversold: <{config.RSI_OVERSOLD}, Overbought: >{config.RSI_OVERBOUGHT})")
    print(f"Min 24h Volume: ${config.MIN_VOLUME_USDT:,.0f}")
    print(f"Recovery Sync Balance: ${config.RECOVERY_SYNC_BALANCE}")
    print("------------------------------------------")

    input("Press Enter to start the Shadow trading bot...")

    print("Executing Pre-Scan Protocol (5 minutes)...")
    time.sleep(300)
    print("Pre-Scan Protocol complete.")

    # --- Open Bybit Webpage ---
    if config.BYBIT_TESTNET:
        print("Opening Bybit Testnet in your browser...")
        base_url = "https://testnet.bybit.com"
    else:
        print("Opening Bybit in your browser...")
        base_url = "https://www.bybit.com"
    
    url_symbol = config.SYMBOL.replace("/", "")
    trade_url = f"{base_url}/trade/usdt/{url_symbol}"
    webbrowser.open(trade_url)

    while True:
        # 1. Get current balance and check for major freezes
        current_balance = bybit_client.get_wallet_balance()
        if current_balance is None:
            print("Could not retrieve wallet balance. Retrying in 1 minute.")
            time.sleep(60)
            continue

        # 2. RECOVERY SYNC PROTOCOL
        if current_balance < config.RECOVERY_SYNC_BALANCE:
            print(f"RECOVERY SYNC: Balance ${current_balance:.2f} is below threshold of ${config.RECOVERY_SYNC_BALANCE}.")
            is_fud = True
            while is_fud:
                print("RECOVERY SYNC: Paused. Waiting for 1-hour of 'Neutral' sentiment...")
                time.sleep(3600) # Wait an hour
                sentiment = sentiment_analyzer.get_sentiment()
                if sentiment == 'Neutral':
                    is_fud = False
                    print("RECOVERY SYNC: 'Neutral' sentiment confirmed. Resuming operations.")
            continue # Restart the main loop after recovery

        if risk_manager.check_safety_freeze(current_balance):
            print("SAFETY FREEZE: Portfolio value dropped significantly. Shutting down Shadow.")
            break

        if not risk_manager.can_trade():
            print("Daily trade limit reached. Shutting down Shadow for today.")
            break

        print(f"Balance: {current_balance:.2f} USDT | Trades: {risk_manager.trades_today}/{risk_manager.daily_trade_limit}")

        # 3. SELECTIVITY: Get Market Data (Volume & Klines)
        ticker_info = bybit_client.get_ticker_info(config.SYMBOL)
        klines = bybit_client.get_klines(config.SYMBOL, "1", 200) # 1-minute interval, 200 candles

        if not ticker_info or not klines:
            print("Could not retrieve market data. Retrying in 1 minute.")
            time.sleep(60)
            continue
        
        # 4. SELECTIVITY: Apply Filters (Volume & RSI)
        volume_24h = float(ticker_info.get('volume24h', 0))
        if volume_24h < config.MIN_VOLUME_USDT:
            print(f"Volume check failed: ${volume_24h:,.0f} is below minimum of ${config.MIN_VOLUME_USDT:,.0f}. Waiting.")
            time.sleep(60)
            continue
            
        rsi = strategy.get_rsi(klines)
        trade_direction = strategy.get_trade_direction(rsi)
        
        latest_price = float(klines[-1][4])

        if trade_direction:
            print(f"Signal found: RSI({rsi:.2f}) indicates {trade_direction} at price {latest_price:.2f}")
            
            # 5. RISK MANAGEMENT: Calculate position size, SL and TP
            position_size = risk_manager.calculate_position_size(current_balance)
            sl, tp = risk_manager.calculate_sl_tp(latest_price, trade_direction)

            if sl is None or tp is None:
                print("Could not calculate Stop Loss or Take Profit. Skipping trade.")
                time.sleep(10)
                continue

            print(f"Calculated: Position Size={position_size:.4f}, SL={sl:.2f}, TP={tp:.2f}")

            # Simplistic quantity calculation - requires refinement for live trading.
            qty = 0.001 # Placeholder for BTCUSDT. Needs to be dynamic.

            # 6. Place Order
            print(f"Attempting to place {trade_direction} order for {qty} {config.SYMBOL}...")
            order_placed = bybit_client.place_limit_order(
                config.SYMBOL, trade_direction, qty, latest_price, sl, tp
            )

            if order_placed:
                risk_manager.increment_trade_count()
                play_sound(config.SUCCESS_SOUND)
                print("Order placed successfully. Waiting for next cycle.")
            else:
                print("Order failed to place.")
        else:
            print(f"No signal: RSI is {rsi:.2f}. Waiting for overbought/oversold conditions.")
        
        time.sleep(10)

if __name__ == "__main__":
    main()
