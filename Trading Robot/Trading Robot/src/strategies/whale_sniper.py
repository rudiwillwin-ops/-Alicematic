import pandas_ta as ta
import pandas as pd
import datetime
import numpy as np
from src.strategies.base import BaseStrategy

class WhaleSniper(BaseStrategy):
    """
    APEX INSTITUTIONAL V7.
    The ultimate high-speed ROI strategy.
    Combines Squeeze, Z-Score Volume, and Triple-Trend Confluence.
    """
    def __init__(self):
        super().__init__(name="APEX V7")
        self.bb_length = 20
        self.bb_std = 2.0

    def analyze(self, df: pd.DataFrame) -> dict:
        if len(df) < 200:
            return {"action": "HOLD", "reason": "Warming up..."}

        # 1. TRIPLE-TREND CONFLUENCE (Multi-Length EMAs)
        df['ema_fast'] = ta.ema(df['close'], length=20)
        df['ema_mid'] = ta.ema(df['close'], length=50)
        df['ema_slow'] = ta.ema(df['close'], length=200)
        
        # 2. THE PRESSURE COOKER (Squeeze)
        bb = ta.bbands(df['close'], length=self.bb_length, std=self.bb_std)
        df['bb_upper'] = bb.filter(like='BBU').iloc[:, 0]
        df['bb_lower'] = bb.filter(like='BBL').iloc[:, 0]
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['close']
        df['bb_width_avg'] = df['bb_width'].rolling(window=100).mean()
        
        # 3. THE WHALE FOOTPRINT (Volume Z-Score)
        mean_vol = df['volume'].rolling(window=30).mean()
        std_vol = df['volume'].rolling(window=30).std()
        df['vol_zscore'] = (df['volume'] - mean_vol) / std_vol
        
        # 4. VELOCITY (ADX)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df['ADX_14']
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        current = df.iloc[-1]
        
        # --- INSTITUTIONAL FILTERS ---
        is_squeezed = current['bb_width'] < (current['bb_width_avg'] * 0.80)
        is_whale_vol = current['vol_zscore'] > 2.0
        is_trending = current['adx'] > 25
        
        # Trend Alignment: Fast > Mid > Slow
        is_bullish_stack = current['ema_fast'] > current['ema_mid'] > current['ema_slow']
        is_bearish_stack = current['ema_fast'] < current['ema_mid'] < current['ema_slow']

        action = "HOLD"
        reason = "Apex Scanning"
        stop_loss = 0.0
        take_profit = 0.0

        # --- APEX ENTRY ---
        # BULLISH: Trend is up, market was squeezed, Whale enters with massive volume
        if is_bullish_stack and is_squeezed and is_whale_vol and current['close'] > current['bb_upper']:
            action = "BUY"
            reason = f"APEX Breakout (Z:{current['vol_zscore']:.1f})"
            stop_loss = current['close'] - (1.5 * current['atr'])
            # 2.5:1 RR for high-speed compounding
            take_profit = current['close'] + (3.75 * current['atr'])

        # BEARISH: Trend is down, market was squeezed, Whale exits/shorts
        elif is_bearish_stack and is_squeezed and is_whale_vol and current['close'] < current['bb_lower']:
            action = "SELL"
            reason = f"APEX Breakdown (Z:{current['vol_zscore']:.1f})"
            stop_loss = current['high'] + (1.5 * current['atr'])
            take_profit = current['close'] - (3.75 * current['atr'])

        return {
            "action": action,
            "confidence": min(current['vol_zscore'] / 5.0, 1.0),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "price": current['close']
        }