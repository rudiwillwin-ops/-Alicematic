import pandas_ta as ta
import pandas as pd
from src.strategies.base import BaseStrategy
from src.utils.sessions import SessionManager

class PullbackMomentum(BaseStrategy):
    """
    Institutional Pullback Strategy.
    Enters on dips during strong trends. Optimized for high-frequency 15m/5m trading.
    """
    def __init__(self):
        super().__init__(name="Pullback Momentum")
        self.session_manager = SessionManager()
        self.ema_fast = 50
        self.ema_slow = 200
        self.ema_signal = 20 # The "Value" line

    def analyze(self, df: pd.DataFrame) -> dict:
        if len(df) < self.ema_slow:
            return {"action": "HOLD", "reason": "Not enough data"}

        # 1. Indicators
        df['ema_50'] = ta.ema(df['close'], length=self.ema_fast)
        df['ema_200'] = ta.ema(df['close'], length=self.ema_slow)
        df['ema_20'] = ta.ema(df['close'], length=self.ema_signal)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        session = self.session_manager.get_current_session()
        is_high_vol = self.session_manager.is_high_volatility_window()

        action = "HOLD"
        reason = "Scanning for Pullback"
        stop_loss = 0.0
        take_profit = 0.0

        # --- TREND IDENTIFICATION ---
        uptrend = current['ema_50'] > current['ema_200']
        downtrend = current['ema_50'] < current['ema_200']

        # --- LONG SETUP (Buy the Dip in Uptrend) ---
        if uptrend:
            # Condition 1: Price is near the EMA 20 (The "Value" zone)
            near_ema = current['low'] <= current['ema_20']
            # Condition 2: RSI was oversold/dipped and is now turning back up
            rsi_turning = prev['rsi'] < 45 and current['rsi'] > prev['rsi']
            
            if near_ema and rsi_turning:
                action = "BUY"
                reason = f"Pullback to EMA 20 in Uptrend ({session})"
                # SL below the recent swing low (1.5x ATR)
                stop_loss = current['close'] - (1.5 * current['atr'])
                # TP at 2.0 Risk/Reward ratio for aggressive growth
                risk = current['close'] - stop_loss
                take_profit = current['close'] + (risk * 2.0)

        # --- SHORT SETUP (Sell the Rip in Downtrend) ---
        elif downtrend:
            # Condition 1: Price touched EMA 20 from below
            near_ema = current['high'] >= current['ema_20']
            # Condition 2: RSI was overbought/high and is now turning down
            rsi_turning = prev['rsi'] > 55 and current['rsi'] < prev['rsi']
            
            if near_ema and rsi_turning:
                action = "SELL"
                reason = f"Rip to EMA 20 in Downtrend ({session})"
                stop_loss = current['close'] + (1.5 * current['atr'])
                risk = stop_loss - current['close']
                take_profit = current['close'] - (risk * 2.0)

        return {
            "action": action,
            "confidence": 0.85 if is_high_vol else 0.6,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "price": current['close']
        }
