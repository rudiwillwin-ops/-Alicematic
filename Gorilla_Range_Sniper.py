"""
GORILLA RANGE SNIPER (PYTHON EDITION)
VERSION: 2026.7 DEFINITIVE
ARCHITECTURE: PYTHON STANDALONE EA
STRATEGY: REGIME-SPECIFIC HIGH-PRECISION MEAN REVERSION
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========================================================
# 1. CONFIGURATION (REAL-TIME MARKET CALIBRATED)
# ========================================================
class Config:
    BOT_NAME = "Gorilla Range Sniper"
    MAGIC = 1001
    LOOP_INTERVAL = 10 # Even faster loop
    SYMBOLS = ["EURUSD", "GBPUSD", "GOLD", "BTCUSD", "ETHUSD"]
    SYMBOL_MAP = {} 
    
    # Regime Filter M5
    ADX_PERIOD = 14
    MAX_ADX_THRESHOLD = 18.5
    
    # Precision Engine M1
    BB_WINDOW = 20
    BB_DEV = 2.5
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    
    # Execution Guards (Calibrated to current live logs)
    MIN_BANDWIDTH = {"EURUSD": 15, "GBPUSD": 15, "GOLD": 100, "BTCUSD": 500, "ETHUSD": 100}
    MAX_SPREAD = {"EURUSD": 30, "GBPUSD": 35, "GOLD": 75, "BTCUSD": 6500, "ETHUSD": 650}
    TIME_EXHAUSTION_CANDLES = 15
    
    # Risk Management
    RISK_PER_TRADE = 0.01
    MAX_SIMULTANEOUS_TRADES = 3
    DAILY_PROFIT_TARGET = 150.0
    DAILY_STOP_LOSS = 200.0

    # Credentials
    LOGIN = 0
    PASSWORD = ""
    SERVER = ""
    PATH = ""

def load_credentials():
    creds_path = "Aegis/credentials.json"
    if os.path.exists(creds_path):
        try:
            with open(creds_path, "r") as f:
                data = json.load(f)
                main = data.get("MAIN", {})
                Config.LOGIN = int(main.get("login", 0))
                Config.PASSWORD = main.get("password", "")
                Config.SERVER = main.get("server", "")
                Config.PATH = main.get("path", "")
                return True
        except Exception as e: print(f"Error loading credentials: {e}")
    return False

load_credentials()

# ========================================================
# 2. LOGGING
# ========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    handlers=[logging.FileHandler("gorilla_sniper_precision.log"), logging.StreamHandler()]
)
logger = logging.getLogger("GorillaSniper")

# ========================================================
# 3. INDICATOR ENGINE (WILDER'S EQUIVALENT)
# ========================================================
class IndicatorEngine:
    @staticmethod
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_adx(df, period=14):
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

# ========================================================
# 4. EXECUTION ENGINE
# ========================================================
class GorillaSniper:
    def connect(self):
        if not mt5.initialize(path=Config.PATH, login=Config.LOGIN, password=Config.PASSWORD, server=Config.SERVER):
            return False
        return True

    def get_data(self, symbol, timeframe, count=300):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        return pd.DataFrame(rates) if rates is not None else None

    def calculate_lot(self, symbol, sl_points):
        balance = mt5.account_info().balance
        risk_amt = balance * Config.RISK_PER_TRADE
        tick_val = mt5.symbol_info(symbol).trade_tick_value
        if sl_points <= 0: return 0.1
        lot = risk_amt / (sl_points * tick_val)
        return round(max(0.01, min(lot, 1.0)), 2)

    def run(self):
        if not self.connect():
            logger.error("MT5 Connection Failed.")
            return

        logger.info(f"=== {Config.BOT_NAME} LIVE ===")
        
        while True:
            try:
                today = datetime.now().date()
                history = mt5.history_deals_get(datetime.combine(today, datetime.min.time()), datetime.now())
                pnl = sum([d.profit for d in history if d.magic == Config.MAGIC]) if history else 0
                if pnl >= Config.DAILY_PROFIT_TARGET or pnl <= -Config.DAILY_STOP_LOSS:
                    logger.info(f"Daily Limit reached (${pnl:.2f}). Standing down.")
                    time.sleep(600); continue

                for symbol in Config.SYMBOLS:
                    mt5.symbol_select(symbol, True)
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick: continue
                    spread = (tick.ask - tick.bid) / mt5.symbol_info(symbol).point
                    
                    df_m5 = self.get_data(symbol, mt5.TIMEFRAME_M5)
                    df_m1 = self.get_data(symbol, mt5.TIMEFRAME_M1)
                    if df_m5 is None or df_m1 is None: continue
                    
                    adx_series = IndicatorEngine.calculate_adx(df_m5)
                    adx = adx_series.iloc[-1]
                    rsi_series = IndicatorEngine.calculate_rsi(df_m1['close'])
                    rsi = rsi_series.iloc[-1]
                    
                    sma = df_m1['close'].rolling(Config.BB_WINDOW).mean()
                    std = df_m1['close'].rolling(Config.BB_WINDOW).std()
                    up, low = sma + (Config.BB_DEV * std), sma - (Config.BB_DEV * std)
                    width = (up.iloc[-1] - low.iloc[-1]) / mt5.symbol_info(symbol).point
                    
                    # Heartbeat Diagnostic
                    status_msg = "SCANNING"
                    if np.isnan(adx): status_msg = "ADX WARMUP"
                    elif adx >= Config.MAX_ADX_THRESHOLD: status_msg = f"ADX HIGH ({adx:.1f})"
                    elif spread > Config.MAX_SPREAD.get(symbol, 999): status_msg = f"SPREAD HIGH ({spread:.1f})"
                    elif width < Config.MIN_BANDWIDTH.get(symbol, 0): status_msg = f"THIN BAND ({width:.0f})"
                    
                    print(f"[{symbol}] ADX:{adx:.1f} | Spr:{spread:.1f} | Wid:{width:.0f} | RSI:{rsi:.1f} | {status_msg}")

                    if status_msg != "SCANNING": continue
                    
                    if not mt5.positions_get(symbol=symbol, magic=Config.MAGIC):
                        signal = None
                        p_close, c_close = df_m1['close'].iloc[-2], df_m1['close'].iloc[-1]
                        p_rsi, c_rsi = rsi_series.iloc[-2], rsi_series.iloc[-1]
                        p_low, c_low = low.iloc[-2], low.iloc[-1]
                        p_up, c_up = up.iloc[-2], up.iloc[-1]
                        
                        if (p_close <= p_low or p_rsi <= Config.RSI_OVERSOLD) and (c_close > c_low and c_rsi > Config.RSI_OVERSOLD):
                            signal = "BUY"
                        elif (p_close >= p_up or p_rsi >= Config.RSI_OVERBOUGHT) and (c_close < c_up and c_rsi < Config.RSI_OVERBOUGHT):
                            signal = "SELL"
                        
                        if signal:
                            sl_pts = width * 1.5
                            lot = self.calculate_lot(symbol, sl_pts)
                            price = tick.ask if signal == "BUY" else tick.bid
                            sl = price - (sl_pts * mt5.symbol_info(symbol).point) if signal == "BUY" else price + (sl_pts * mt5.symbol_info(symbol).point)
                            
                            req = {
                                "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lot,
                                "type": mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL,
                                "price": price, "sl": sl, "tp": sma.iloc[-1], "magic": Config.MAGIC,
                                "comment": "Gorilla Precision", "type_filling": mt5.ORDER_FILLING_IOC,
                            }
                            res = mt5.order_send(req)
                            if res.retcode == mt5.TRADE_RETCODE_DONE:
                                logger.info(f"===> TRADE: {signal} {symbol} @ {price} | ADX: {adx:.1f}")

                pos = mt5.positions_get(magic=Config.MAGIC)
                if pos:
                    for p in pos:
                        if (datetime.now() - datetime.fromtimestamp(p.time)).total_seconds() // 60 >= Config.TIME_EXHAUSTION_CANDLES:
                            logger.info(f"Time Exit: {p.symbol}")
                            tick = mt5.symbol_info_tick(p.symbol)
                            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "position": p.ticket, "volume": p.volume,
                                   "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                                   "price": tick.bid if p.type == 0 else tick.ask, "magic": Config.MAGIC, "type_filling": mt5.ORDER_FILLING_IOC}
                            mt5.order_send(req)

                time.sleep(Config.LOOP_INTERVAL)
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = GorillaSniper()
    bot.run()
