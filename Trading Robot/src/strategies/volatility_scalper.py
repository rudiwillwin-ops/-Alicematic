import pandas_ta as ta
import pandas as pd
from src.strategies.base import BaseStrategy
from src.utils.sessions import SessionManager

class VolatilityScalper(BaseStrategy):
    def __init__(self):
        super().__init__(name="Volatility Scalper")
        self.session_manager = SessionManager()
        self.bb_length = 20
        self.bb_std = 2.0
        self.rsi_length = 14

    def analyze(self, df: pd.DataFrame) -> dict:
        if len(df) < self.bb_length:
            return {"action": "HOLD", "reason": "Not enough data"}

        # --- Session Analysis ---
        session = self.session_manager.get_current_session()
        is_high_vol = self.session_manager.is_high_volatility_window()
        
        # 1. Indicators
        bb = ta.bbands(df['close'], length=self.bb_length, std=self.bb_std)
        df['bb_upper'] = bb.filter(like='BBU').iloc[:, 0]
        df['bb_lower'] = bb.filter(like='BBL').iloc[:, 0]
        df['bb_mid'] = bb.filter(like='BBM').iloc[:, 0]
        
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_length)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        # Added Trend Filter
        df['ema_200'] = ta.ema(df['close'], length=200)

        current = df.iloc[-1]
        action = "HOLD"
        reason = f"Neutral ({session})"
        stop_loss = 0.0
        take_profit = 0.0

        # --- Dynamic Thresholds ---
        rsi_ob = 75 if is_high_vol else 70
        rsi_os = 25 if is_high_vol else 30

        # --- LONG SIGNAL (Only if Price > EMA 200) ---
        if current['close'] <= current['bb_lower'] and current['rsi'] <= rsi_os:
            if current['close'] > current['ema_200']:
                action = "BUY"
                reason = f"Session {session}: Buy the Dip (Trend-Aligned)"
                stop_loss = current['close'] - (1.5 * current['atr'])
                take_profit = current['bb_mid']
            else:
                reason = "Oversold but Trend is DOWN (Skipping)"

        # --- SHORT SIGNAL (Only if Price < EMA 200) ---
        elif current['close'] >= current['bb_upper'] and current['rsi'] >= rsi_ob:
            if current['close'] < current['ema_200']:
                action = "SELL"
                reason = f"Session {session}: Sell the Rip (Trend-Aligned)"
                stop_loss = current['close'] + (1.5 * current['atr'])
                take_profit = current['bb_mid']
            else:
                reason = "Overbought but Trend is UP (Skipping)"

        return {
            "action": action,
            "confidence": 0.8 if is_high_vol else 0.5,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "price": current['close']
        }
