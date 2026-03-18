# Part 4: Automation & Safety (main.py)
import MetaTrader5 as mt5
import time
import datetime
import config
from bot_logic import TradingEngine

class MainBot:
    def __init__(self):
        self.engine = None
        self.initialize_mt5()

    def initialize_mt5(self):
        """Initializes the connection to the MetaTrader 5 terminal."""
        if not mt5.initialize(path=config.MT5_PATH, login=config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER):
            print(f"initialize() failed, error code = {mt5.last_error()}")
            quit()
        print("MetaTrader 5 initialized successfully.")
        self.engine = TradingEngine(mt5, config)

    def is_news_event(self):
        """
        Placeholder for News Shield.
        Prevents trades 30 mins before/after Red Folder events.
        This requires an external news source (e.g., an API or a news calendar library).
        """
        # --- Placeholder Logic ---
        # In a real implementation, you would fetch news data from a reliable source.
        # For example:
        # now = datetime.datetime.utcnow()
        # for event in news_calendar:
        #     if event['impact'] == 'High' and (event['time'] - timedelta(minutes=30)) < now < (event['time'] + timedelta(minutes=30)):
        #         print(f"NEWS SHIELD: High impact event {event['title']} upcoming. No new trades.")
        #         return True
        return False

    def consistency_guardian(self):
        """
        If a single trade's profit reaches 30% of the daily target, move SL to BE+1.
        Daily target is not explicitly defined, so we'll base it on DAILY_LOSS_LIMIT.
        Let's assume the daily profit target is the same as the daily loss limit (4%).
        """
        positions = mt5.positions_get(symbol=config.SYMBOL)
        if positions is None or len(positions) == 0:
            return

        account_info = mt5.account_info()
        daily_profit_target_cash = account_info.equity * config.DAILY_LOSS_LIMIT
        profit_threshold = daily_profit_target_cash * 0.30

        for position in positions:
            if position.profit >= profit_threshold and position.sl == 0.0: # Check if SL is not already modified
                new_sl = position.price_open + (1 * mt5.symbol_info(config.SYMBOL).point) if position.type == mt5.ORDER_TYPE_BUY else position.price_open - (1 * mt5.symbol_info(config.SYMBOL).point)
                
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": position.ticket,
                    "sl": new_sl,
                    "tp": position.tp,
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"CONSISTENCY GUARDIAN: Moved SL to Break Even for position #{position.ticket}")
                else:
                    print(f"Failed to modify SL for position #{position.ticket}, retcode={result.retcode}")

    def run(self):
        """The main loop of the trading bot."""
        print("Bot is running...")
        while True:
            try:
                # 1. Check for news
                if self.is_news_event():
                    time.sleep(60)
                    continue

                # 2. Manage open positions
                self.consistency_guardian()

                # 3. Check for new trade signals
                df = self.engine.get_data(config.SYMBOL, config.TIMEFRAME)
                if df is not None:
                    df = self.engine.calculate_indicators(df)
                    signal = self.engine.check_trade_signal(df)
                    
                    if signal and len(mt5.positions_get(symbol=config.SYMBOL)) == 0:
                        # Check spread
                        spread = (mt5.symbol_info_tick(config.SYMBOL).ask - mt5.symbol_info_tick(config.SYMBOL).bid) / mt5.symbol_info(config.SYMBOL).point
                        if spread <= config.MAX_SPREAD:
                            atr_pips = df.iloc[-2]['ATR_14'] / mt5.symbol_info(config.SYMBOL).point
                            lot_size = self.engine.calculate_position_size(config.SYMBOL, 2 * atr_pips)
                            
                            if lot_size:
                                print(f"Signal: {signal}, Lot Size: {lot_size}, ATR pips: {atr_pips:.2f}")
                                self.engine.execute_trade(signal, config.SYMBOL, lot_size, df.iloc[-2]['ATR_14'])
                        else:
                            print(f"Spread is too high: {spread:.2f} pips. No trade.")

                # Wait for the next candle
                time.sleep(self.get_sleep_time(config.TIMEFRAME))

            except Exception as e:
                print(f"An error occurred: {e}")
                mt5.shutdown()
                time.sleep(10)
                self.initialize_mt5() # Re-initialize

    def get_sleep_time(self, timeframe_str):
        """Calculates the time to sleep until the next candle."""
        now = datetime.datetime.now()
        
        if 'M' in timeframe_str:
            minutes = int(timeframe_str.replace('M',''))
            next_candle = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=minutes)
            while next_candle <= now:
                 next_candle += datetime.timedelta(minutes=minutes)

        elif 'H' in timeframe_str:
            hours = int(timeframe_str.replace('H',''))
            next_candle = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=hours)
            while next_candle <= now:
                 next_candle += datetime.timedelta(hours=hours)
        else: # Default to 1 minute
            minutes = 1
            next_candle = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=minutes)
            while next_candle <= now:
                 next_candle += datetime.timedelta(minutes=minutes)

        sleep_seconds = (next_candle - now).total_seconds()
        return sleep_seconds + 1 # Add a small buffer

if __name__ == "__main__":
    bot = MainBot()
    bot.run()
