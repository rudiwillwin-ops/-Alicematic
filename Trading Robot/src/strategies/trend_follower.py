import pandas_ta as ta
import pandas as pd
from src.strategies.base import BaseStrategy

class TrendFollowingStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="Institutional Trend Follower")
        # Parameters (Institutional defaults)
        self.ema_period = 200
        self.adx_threshold = 25  # Below 25 = Ranging (Don't trade)
        self.rsi_period = 14
        self.atr_period = 14

    def analyze(self, df: pd.DataFrame) -> dict:
        # 1. Check Data Sufficiency
        if len(df) < 200:
            return {"action": "HOLD", "reason": "Not enough data"}

        # 2. Calculate Indicators (Vectorized - Fast)
        # EMA (Trend Baseline)
        df['ema'] = ta.ema(df['close'], length=self.ema_period)
        # ADX (Trend Strength - The "Regime Filter")
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df['ADX_14']
        # RSI (Momentum)
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        # ATR (Volatility for Stop Loss)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)

        # Get latest values (The last row)
        current = df.iloc[-1]
        
        # 3. Regime Detection (The "Shield")
        if current['adx'] < self.adx_threshold:
            return {
                "action": "HOLD", 
                "reason": f"Market Choppy (ADX: {current['adx']:.2f} < 25)"
            }

        # 4. Logic Execution
        action = "HOLD"
        reason = "No Setup"
        stop_loss = 0.0
        take_profit = 0.0

        # LONG Setup
        # Price > EMA (Uptrend) AND RSI < 70 (Room to grow)
        if current['close'] > current['ema'] and current['rsi'] < 70:
            action = "BUY"
            reason = "Uptrend + Momentum"
            # Dynamic Risk Calculation
            dist = 2.0 * current['atr'] # 2x Volatility distance
            stop_loss = current['close'] - dist
            take_profit = current['close'] + (dist * 1.5) # 1:1.5 RR

        # SHORT Setup
        # Price < EMA (Downtrend) AND RSI > 30 (Room to drop)
        elif current['close'] < current['ema'] and current['rsi'] > 30:
            action = "SELL"
            reason = "Downtrend + Momentum"
            # Dynamic Risk Calculation
            dist = 2.0 * current['atr']
            stop_loss = current['close'] + dist
            take_profit = current['close'] - (dist * 1.5)

        return {
            "action": action,
            "confidence": current['adx'] / 100.0, # Higher trend strength = Higher confidence
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "price": current['close']
        }
