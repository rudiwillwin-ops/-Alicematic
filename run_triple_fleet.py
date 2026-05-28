import asyncio
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, time as dt_time
from metaapi_cloud_sdk import MetaApi
from colorama import init, Fore, Style

init(autoreset=True)

# --- CONFIGURATION ---
TOKEN = "0357f707f15e8b4e76a6e5b4f4f4e5b4"
ACCOUNT_ID = "309567916" # Primary Fleet Account

MAGIC_SAMANTHA = 20260507
MAGIC_GORILLA = 888999
MAGIC_SNIPER = 1001

SYMBOLS = ['EURUSD', 'GBPUSD', 'XAUUSD', 'BTCUSD', 'ETHUSD']

# --- INDICATORS ---
def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def rsi_wilder(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def adx_wilder(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    smoothed_plus_dm = pd.Series(plus_dm).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    smoothed_minus_dm = pd.Series(minus_dm).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (smoothed_plus_dm / atr)
    minus_di = 100 * (smoothed_minus_dm / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return adx

# --- SIGNALS ---
async def get_samantha_signal(connection, symbol):
    try:
        m5 = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        m15 = await connection.get_candles(symbol, '15m', datetime.now(), 200)
        if not m5 or not m15: return None
        df5 = pd.DataFrame([c['close'] for c in m5], columns=['close'])
        df15 = pd.DataFrame([c['close'] for c in m15], columns=['close'])
        df5['ema50'], df5['ema200'], df5['rsi'] = ema(df5['close'], 50), ema(df5['close'], 200), rsi_wilder(df5['close'], 14)
        df15['ema50'], df15['ema200'] = ema(df15['close'], 50), ema(df15['close'], 200)
        c5, p5, c15 = df5.iloc[-1], df5.iloc[-2], df15.iloc[-1]
        if c15['close'] > c15['ema50'] > c15['ema200'] and c5['close'] > c5['ema50'] > c5['ema200'] and p5['rsi'] < 50 <= c5['rsi']: return "BUY"
        if c15['close'] < c15['ema50'] < c15['ema200'] and c5['close'] < c5['ema50'] < c5['ema200'] and p5['rsi'] > 50 >= c5['rsi']: return "SELL"
    except: pass
    return None

async def get_gorilla_signal(connection, symbol):
    try:
        m1 = await connection.get_candles(symbol, '1m', datetime.now(), 200)
        m5 = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        if not m1 or not m5: return None
        df1, df5 = pd.DataFrame([c['close'] for c in m1], columns=['close']), pd.DataFrame([c['close'] for c in m5], columns=['close'])
        df1['ema8'], df1['ema21'], df1['rsi9'], df5['ema50'] = ema(df1['close'], 8), ema(df1['close'], 21), rsi_wilder(df1['close'], 9), ema(df5['close'], 50)
        c1, p1, c5 = df1.iloc[-1], df1.iloc[-2], df5.iloc[-1]
        if c1['close'] > c5['ema50'] and c1['close'] > c1['ema8'] > c1['ema21'] and p1['rsi9'] < 40 <= c1['rsi9']: return "BUY"
        if c1['close'] < c5['ema50'] and c1['close'] < c1['ema8'] < c1['ema21'] and p1['rsi9'] > 60 >= c1['rsi9']: return "SELL"
    except: pass
    return None

async def get_sniper_signal(connection, symbol):
    try:
        m1 = await connection.get_candles(symbol, '1m', datetime.now(), 300)
        m5 = await connection.get_candles(symbol, '5m', datetime.now(), 300)
        if not m1 or not m5: return None, 0
        df1, df5 = pd.DataFrame(m1), pd.DataFrame(m5)
        adx = adx_wilder(df5).iloc[-1]
        if adx >= 18.5: return None, 0
        df1['rsi'], df1['sma'], df1['std'] = rsi_wilder(df1['close']), df1['close'].rolling(20).mean(), df1['close'].rolling(20).std()
        df1['up'], df1['low'] = df1['sma'] + (2.5 * df1['std']), df1['sma'] - (2.5 * df1['std'])
        c1, p1 = df1.iloc[-1], df1.iloc[-2]
        if (p1['close'] <= p1['low'] or p1['rsi'] <= 30) and (c1['close'] > c1['low'] and c1['rsi'] > 30): return "BUY", c1['sma']
        if (p1['close'] >= p1['up'] or p1['rsi'] >= 70) and (c1['close'] < c1['up'] and c1['rsi'] < 70): return "SELL", c1['sma']
    except: pass
    return None, 0

# --- EXECUTION ---
async def trade(connection, symbol, direction, risk, magic, comment, tp=0):
    try:
        acc = await connection.get_account_information()
        vol = max(0.01, min(0.50, round((acc['balance'] * (risk/100)) / 500, 2)))
        print(Fore.YELLOW + f"  [EXEC] {comment}: {direction} {symbol} | {vol} lots")
        if direction == "BUY": await connection.create_market_buy_order(symbol, vol, 0, tp, {"magic": magic, "comment": comment})
        else: await connection.create_market_sell_order(symbol, vol, 0, tp, {"magic": magic, "comment": comment})
    except Exception as e: print(Fore.RED + f"  [ERROR] Trade Failed: {e}")

async def run_fleet():
    api = MetaApi(TOKEN)
    try:
        account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        print(Fore.CYAN + "="*60)
        print(Fore.CYAN + " 🚢 TRIPLE FLEET ENGINE | SAMANTHA + GORILLA + SNIPER")
        print(Fore.CYAN + f" ACCOUNT: {ACCOUNT_ID} | STATUS: ONLINE")
        print(Fore.CYAN + "="*60)

        while True:
            for symbol in SYMBOLS:
                print(Fore.WHITE + f"[{datetime.now().strftime('%H:%M:%S')}] Scanning {symbol}...")
                
                # Samantha (M5/M15 Momentum)
                s_sig = await get_samantha_signal(connection, symbol)
                if s_sig: await trade(connection, symbol, s_sig, 1.0, MAGIC_SAMANTHA, "Sam Fleet")
                
                # Gorilla (M1 Scalper)
                g_sig = await get_gorilla_signal(connection, symbol)
                if g_sig: await trade(connection, symbol, g_sig, 2.0, MAGIC_GORILLA, "Gor Fleet")
                
                # Sniper (M1 Range)
                n_sig, tp = await get_sniper_signal(connection, symbol)
                if n_sig: await trade(connection, symbol, n_sig, 1.0, MAGIC_SNIPER, "Sniper Fleet", tp)
                
            print(Fore.BLUE + "Scan Complete. Resting 30s...")
            await asyncio.sleep(30)
            
    except Exception as e:
        print(Fore.RED + f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(run_fleet())
