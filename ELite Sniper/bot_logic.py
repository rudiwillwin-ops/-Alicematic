# Part 3: Trading Engine (bot_logic.py)
import pandas as pd
import pandas_ta as ta
import numpy as np

class TradingEngine:
    def __init__(self, mt5, config):
        self.mt5 = mt5
        self.config = config

    def get_data(self, symbol, timeframe, bars=300):
        """Fetches historical data from MT5."""
        rates = self.mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None:
            print(f"Failed to get rates for {symbol}")
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df

    def calculate_indicators(self, df):
        """Calculates all necessary technical indicators."""
        df.ta.ema(length=200, append=True, col_names=('EMA_200',))
        df.ta.donchian(lower_length=20, upper_length=20, append=True, col_names=('DCL_20_20', 'DCU_20_20'))
        df.ta.atr(length=14, append=True, col_names=('ATR_14',))
        return df

    def check_trade_signal(self, df):
        """Checks for a trend-following sniper signal."""
        last_candle = df.iloc[-2]  # Use the last closed candle
        
        # Filter 1: Trend Filter
        is_uptrend = last_candle['close'] > last_candle['EMA_200']
        is_downtrend = last_candle['close'] < last_candle['EMA_200']

        # Trigger 2: Donchian Channel Breakout
        buy_signal = is_uptrend and last_candle['close'] > last_candle['DCU_20_20']
        sell_signal = is_downtrend and last_candle['close'] < last_candle['DCL_20_20']

        if buy_signal:
            return 'BUY'
        elif sell_signal:
            return 'SELL'
        else:
            return None

    def calculate_position_size(self, symbol, stop_loss_pips):
        """Calculates lot size based on fixed fractional risk."""
        account_info = self.mt5.account_info()
        if account_info is None:
            print("Failed to get account info.")
            return None

        equity = account_info.equity
        risk_amount = equity * self.config.RISK_PER_TRADE
        
        # Get symbol info
        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"Failed to get symbol info for {symbol}")
            return None
            
        # Calculate pip value
        if not self.mt5.symbol_select(symbol, True):
            print(f"Failed to select symbol {symbol}")
            return None

        tick_value = self.mt5.symbol_info_tick(symbol).trade_tick_value
        tick_size = self.mt5.symbol_info_tick(symbol).trade_tick_size
        
        pip_value = tick_value
        if "JPY" in symbol:
             pip_value = tick_value / (tick_size * 100)
        else:
             pip_value = tick_value / (tick_size * 10)


        # Calculate Lot Size
        lot_size = risk_amount / (stop_loss_pips * pip_value)
        
        # Normalize lot size to broker's allowed volume steps
        volume_step = symbol_info.volume_step
        lot_size = np.floor(lot_size / volume_step) * volume_step
        
        # Ensure lot size is within min/max limits
        min_volume = symbol_info.volume_min
        max_volume = symbol_info.volume_max
        lot_size = max(min_volume, min(lot_size, max_volume))

        return lot_size if lot_size >= min_volume else None

    def execute_trade(self, signal, symbol, lot_size, atr):
        """Executes a trade on MT5."""
        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            return
        
        point = symbol_info.point
        price = self.mt5.symbol_info_tick(symbol).ask if signal == 'BUY' else self.mt5.symbol_info_tick(symbol).bid
        
        sl_pips = 2 * atr / point
        tp_pips = sl_pips * self.config.RR_RATIO

        if signal == 'BUY':
            sl = price - sl_pips * point
            tp = price + tp_pips * point
            action = self.mt5.TRADE_ACTION_DEAL
            request = {
                "action": action,
                "symbol": symbol,
                "volume": lot_size,
                "type": self.mt5.ORDER_TYPE_BUY,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 23400,
                "comment": "ELite Sniper: BUY",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
        elif signal == 'SELL':
            sl = price + sl_pips * point
            tp = price - tp_pips * point
            action = self.mt5.TRADE_ACTION_DEAL
            request = {
                "action": action,
                "symbol": symbol,
                "volume": lot_size,
                "type": self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 23400,
                "comment": "ELite Sniper: SELL",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
        else:
            return

        result = self.mt5.order_send(request)
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            print(f"Order send failed, retcode={result.retcode}")
        else:
            print(f"Order sent successfully: {signal} {lot_size} {symbol} @ {price}")

        return result
