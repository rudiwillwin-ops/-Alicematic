import pandas as pd
import numpy as np
import os
import glob
from loguru import logger
from src.strategies.whale_sniper import WhaleSniper
import pandas_ta as ta

class Backtester:
    def __init__(self, initial_balance=50):
        self.strategy = WhaleSniper()

    def run(self, data_dir="data/historical"):
        files = glob.glob(f"{data_dir}/*_HF.csv")
        results = {}
        for file in files:
            symbol = os.path.basename(file).split('_')[0]
            logger.info(f"💎 Running APEX V7 FINAL TEST on {symbol}...")
            df = pd.read_csv(file)
            results[symbol] = self.simulate(df)
        self.report(results)

    def simulate(self, df):
        # Indicators
        df['ema_fast'] = ta.ema(df['close'], length=20)
        df['ema_mid'] = ta.ema(df['close'], length=50)
        df['ema_slow'] = ta.ema(df['close'], length=200)
        bb = ta.bbands(df['close'], length=20, std=2.0)
        df['bb_upper'] = bb.filter(like='BBU').iloc[:, 0]
        df['bb_lower'] = bb.filter(like='BBL').iloc[:, 0]
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['close']
        df['bb_width_avg'] = df['bb_width'].rolling(window=100).mean()
        df['vol_sma'] = ta.sma(df['volume'], length=30)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        balance = 50.0
        max_bal = 50.0
        history = []
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            if balance > max_bal: max_bal = balance

            if history and history[-1]['status'] == 'OPEN':
                pos = history[-1]
                if (pos['side'] == 'buy' and row['low'] <= pos['sl']) or \
                   (pos['side'] == 'sell' and row['high'] >= pos['sl']):
                    balance *= 0.97 # 3% Kelly Loss
                    pos['status'] = 'CLOSED'
                    pos['pnl'] = -0.03
                    continue
                if (pos['side'] == 'buy' and row['high'] >= pos['tp']) or \
                   (pos['side'] == 'sell' and row['low'] <= pos['tp']):
                    balance *= 1.075 # 7.5% Kelly Gain (2.5:1 RR)
                    pos['status'] = 'CLOSED'
                    pos['pnl'] = 0.075
                    continue

            # Apex Entry Logic
            is_squeezed = row['bb_width'] < (row['bb_width_avg'] * 0.80)
            is_whale_vol = row['volume'] > (row['vol_sma'] * 2.5)
            is_bullish = row['ema_fast'] > row['ema_mid'] > row['ema_slow']
            is_bearish = row['ema_fast'] < row['ema_mid'] < row['ema_slow']

            if is_bullish and is_squeezed and is_whale_vol and row['close'] > row['bb_upper']:
                history.append({'side': 'buy', 'sl': row['close'] - (1.5 * row['atr']), 'tp': row['close'] + (3.75 * row['atr']), 'status': 'OPEN'})
            elif is_bearish and is_squeezed and is_whale_vol and row['close'] < row['bb_lower']:
                history.append({'side': 'sell', 'sl': row['high'] + (1.5 * row['atr']), 'tp': row['close'] - (3.75 * row['atr']), 'status': 'OPEN'})

        return {"balance": balance, "trades": len(history), "win_rate": len([t for t in history if t.get('pnl', 0) > 0])/len(history)*100 if history else 0}

    def report(self, results):
        print("\n" + "="*85)
        print("🚀 APEX V7: THE FOOL-PROOF ROI MACHINE ($50 Start | 7-Day HF)")
        print("="*85)
        print(f"{ 'SYMBOL':<10} | { 'FINAL $':<10} | { 'ROI %':<10} | { 'TRADES':<8} | { 'EST. 3-MONTH ROI'}")
        print("-" * 85)
        for s, r in results.items():
            roi = (r['balance'] - 50) / 50 * 100
            est_3m = roi * 12 # 12 weeks in 3 months
            print(f"{s:<10} | ${r['balance']:>8.2f} | {roi:>8.1f}% | {r['trades']:>8} | {est_3m:>15.1f}%")
        print("="*85)

if __name__ == "__main__":
    Backtester().run()