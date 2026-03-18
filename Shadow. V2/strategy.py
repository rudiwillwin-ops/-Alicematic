# strategy.py
import pandas as pd

import pandas as pd
import config

class Strategy:
    def __init__(self):
        self.rsi_period = config.RSI_PERIOD
        self.rsi_oversold = config.RSI_OVERSOLD
        self.rsi_overbought = config.RSI_OVERBOUGHT

    def get_rsi(self, klines):
        """Calculates the Relative Strength Index (RSI)."""
        closes = [float(k[4]) for k in klines]
        closes.reverse()  # Oldest data first
        df = pd.DataFrame(data=closes, columns=['close'])

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]

    def get_trade_direction(self, rsi):
        """Determines the trade direction based on RSI."""
        if rsi is None:
            return None
            
        if rsi < self.rsi_oversold:
            return "Buy"
        elif rsi > self.rsi_overbought:
            return "Sell"
        else:
            return None
