
import os
import sys
import time
import json
import math
import queue
import signal
import threading
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import requests
import numpy as np
import pandas as pd
from flask import Flask, jsonify, Response
import winsound
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

try:
    import MetaTrader5 as mt5
except Exception as exc:
    raise ImportError("MetaTrader5 package is required") from exc

try:
    from pybit.unified_trading import HTTP as BybitHTTP
except Exception as exc:
    raise ImportError("pybit package is required") from exc

APP_NAME = "PROP FIRM MACHINE V1"

CONFIG = {
    "loop_interval_seconds": 10,
    "magic_number": 51001,
    "comment": APP_NAME,
    "mode_thresholds": {
        "v1": 0.00,
        "v2": 0.05,
        "v3": 0.10,
        "hard_stop": 0.20
    },
    "risk": {
        "risk_per_trade": 0.01,
        "max_concurrent_trades": 4,
        "cooldown_seconds": 300,
        "reward_to_risk_min": 1.5,
        "soft_drawdown_pause": 0.10
    },
    "forex": {
        "enabled": True,
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"],
        "timeframe": mt5.TIMEFRAME_M1,
        "bias_timeframe": mt5.TIMEFRAME_M5,
        "spread_filter_points": 30,
        "slippage_points": 20,
        "bars": 300
    },
    "crypto": {
        "enabled": True,
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "timeframe": "15",
        "bias_timeframe": "60",
        "category": "linear",
        "use_testnet": False,
        "bars": 300
    },
    "indicators": {
        "ema_fast": 20,
        "ema_slow": 50,
        "rsi_period": 14,
        "rsi_buy": 52,
        "rsi_sell": 48,
        "adx_period": 14,
        "adx_min": 15,
        "atr_period": 14,
        "atr_min": 0.00005,
        "atr_max": 0.0100,
        "pullback_atr": 0.8,
        "breakout_lookback": 10,
        "volatility_window": 50
    },
    "trade_management": {
        "stop_atr": 2.0,
        "trail_atr": 1.5,
        "tp_atr": 4.0,
        "partial_rr": 1.5,
        "partial_close_pct": 0.5
    },
    "session_filter": {
        "forex": {"start_hour_utc": 6, "end_hour_utc": 21},
        "crypto": {"start_hour_utc": 0, "end_hour_utc": 24}
    },
    "news_filter": {
        "enabled": True,
        "window_minutes": 30,
        "calendar_csv": os.getenv("NEWS_CALENDAR_CSV", "news_events.csv")
    },
    "storage": {
        "db_path": "prop_firm_machine.db"
    },
    "dashboard": {
        "host": "0.0.0.0",
        "port": 5001
    }
}

ONLY_CRYPTO = os.getenv("ONLY_CRYPTO", "").strip().lower() in {"1", "true", "yes"}
ONLY_FOREX = os.getenv("ONLY_FOREX", "").strip().lower() in {"1", "true", "yes"}
if ONLY_CRYPTO:
    CONFIG["forex"]["enabled"] = False
if ONLY_FOREX:
    CONFIG["crypto"]["enabled"] = False


@dataclass
class Trade:
    trade_id: str
    market: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    stop_price: float
    take_profit: float
    open_time: str
    status: str = "OPEN"
    close_time: Optional[str] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    partial_taken: int = 0


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    market TEXT,
                    symbol TEXT,
                    side TEXT,
                    qty REAL,
                    entry_price REAL,
                    stop_price REAL,
                    take_profit REAL,
                    open_time TEXT,
                    status TEXT,
                    close_time TEXT,
                    close_price REAL,
                    pnl REAL,
                    partial_taken INTEGER
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS equity (
                    ts TEXT PRIMARY KEY,
                    equity REAL,
                    drawdown REAL
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS alerts (
                    ts TEXT,
                    level TEXT,
                    message TEXT
                )"""
            )
            con.commit()

    def save_trade(self, trade: Trade) -> None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                """INSERT OR REPLACE INTO trades
                (trade_id, market, symbol, side, qty, entry_price, stop_price, take_profit,
                 open_time, status, close_time, close_price, pnl, partial_taken)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade.trade_id, trade.market, trade.symbol, trade.side, trade.qty,
                    trade.entry_price, trade.stop_price, trade.take_profit,
                    trade.open_time, trade.status, trade.close_time, trade.close_price,
                    trade.pnl, trade.partial_taken
                )
            )
            con.commit()

    def update_trade(self, trade_id: str, **kwargs) -> None:
        if not kwargs:
            return
        cols = ", ".join([f"{k}=?" for k in kwargs.keys()])
        vals = list(kwargs.values())
        vals.append(trade_id)
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE trades SET {cols} WHERE trade_id=?", vals)
            con.commit()

    def save_equity(self, equity: float, drawdown: float) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO equity (ts, equity, drawdown) VALUES (?, ?, ?)",
                (ts, equity, drawdown)
            )
            con.commit()

    def set_state(self, key: str, value: str) -> None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                (key, value)
            )
            con.commit()

    def get_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT value FROM state WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

    def load_open_trades(self) -> List[Trade]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM trades WHERE status='OPEN'")
            rows = cur.fetchall()
        trades = []
        for r in rows:
            trades.append(Trade(
                trade_id=r[0], market=r[1], symbol=r[2], side=r[3],
                qty=r[4], entry_price=r[5], stop_price=r[6], take_profit=r[7],
                open_time=r[8], status=r[9], close_time=r[10], close_price=r[11],
                pnl=r[12], partial_taken=r[13]
            ))
        return trades

    def load_recent_trades(self, limit: int = 50) -> List[Dict]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM trades ORDER BY open_time DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
        keys = ["trade_id", "market", "symbol", "side", "qty", "entry_price", "stop_price",
                "take_profit", "open_time", "status", "close_time", "close_price", "pnl", "partial_taken"]
        return [dict(zip(keys, r)) for r in rows]

    def load_equity_curve(self, limit: int = 2000) -> List[Dict]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT ts, equity, drawdown FROM equity ORDER BY ts ASC LIMIT ?", (limit,))
            rows = cur.fetchall()
        return [{"ts": r[0], "equity": r[1], "drawdown": r[2]} for r in rows]

    def save_alert(self, level: str, message: str) -> None:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO alerts (ts, level, message) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), level, message)
            )
            con.commit()

class Indicators:
    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        ma_up = up.ewm(alpha=1 / period, adjust=False).mean()
        ma_down = down.ewm(alpha=1 / period, adjust=False).mean()
        rs = ma_up / ma_down
        return 100 - (100 / (1 + rs))

    @staticmethod
    def atr(df: pd.DataFrame, period: int) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def adx(df: pd.DataFrame, period: int) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        tr = pd.concat([
            (high - low),
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(period).sum() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(period).sum() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        return dx.rolling(period).mean()


class NewsFilter:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        self.events = []
        self._load_events()

    def _load_events(self) -> None:
        path = self.cfg["calendar_csv"]
        if not self.cfg.get("enabled"):
            self.events = []
            return
        if not os.path.exists(path):
            self.events = []
            return
        df = pd.read_csv(path)
        events = []
        for _, row in df.iterrows():
            try:
                ts = str(row["ts"])
                currency = str(row["currency"]).upper()
                impact = str(row.get("impact", "medium")).lower()
                title = str(row.get("title", ""))
                events.append({"ts": ts, "currency": currency, "impact": impact, "title": title})
            except Exception:
                continue
        self.events = events

    def is_blocked(self, symbol: str) -> bool:
        if not self.cfg.get("enabled") or not self.events:
            return False
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=self.cfg["window_minutes"])
        currencies = [symbol[:3], symbol[3:]] if len(symbol) == 6 else []
        for e in self.events:
            try:
                ts = datetime.fromisoformat(e["ts"])
            except Exception:
                continue
            if abs(now - ts) <= window:
                if e["currency"] in currencies or e["currency"] == "ALL":
                    return True
        return False


class RiskEngine:
    def __init__(self, cfg: Dict, storage: Storage):
        self.cfg = cfg
        self.storage = storage
        self.mode = "V1"

    def update_mode(self, drawdown: float) -> None:
        if drawdown >= self.cfg["mode_thresholds"]["hard_stop"]:
            self.mode = "HARD_STOP"
        elif drawdown >= self.cfg["mode_thresholds"]["v3"]:
            self.mode = "V3"
        elif drawdown >= self.cfg["mode_thresholds"]["v2"]:
            self.mode = "V2"
        else:
            self.mode = "V1"
        self.storage.set_state("mode", self.mode)

    def allow_trade(self, open_trades_count: int, last_trade_time: Optional[float]) -> bool:
        if self.mode == "HARD_STOP":
            return False
        if open_trades_count >= self.cfg["risk"]["max_concurrent_trades"]:
            return False
        if last_trade_time and (time.time() - last_trade_time) < self.cfg["risk"]["cooldown_seconds"]:
            return False
        return True

    def risk_per_trade(self) -> float:
        base = self.cfg["risk"]["risk_per_trade"]
        if self.mode == "V2":
            return base * 0.6
        if self.mode == "V3":
            return base * 1.3
        if self.mode == "HARD_STOP":
            return 0.0
        return base


class StrategyEngine:
    def __init__(self, cfg: Dict):
        self.cfg = cfg

    def evaluate(self, df: pd.DataFrame, bias_df: pd.DataFrame) -> Optional[str]:
        ind = self.cfg["indicators"]
        df = df.copy()
        df["ema_fast"] = Indicators.ema(df["close"], ind["ema_fast"])
        df["ema_slow"] = Indicators.ema(df["close"], ind["ema_slow"])
        df["rsi"] = Indicators.rsi(df["close"], ind["rsi_period"])
        df["atr"] = Indicators.atr(df, ind["atr_period"])
        df["adx"] = Indicators.adx(df, ind["adx_period"])

        bias_df = bias_df.copy()
        bias_df["ema_fast"] = Indicators.ema(bias_df["close"], ind["ema_fast"])
        bias_df["ema_slow"] = Indicators.ema(bias_df["close"], ind["ema_slow"])

        last = df.iloc[-1]
        bias_last = bias_df.iloc[-1]

        bullish_bias = bias_last["ema_fast"] > bias_last["ema_slow"]
        bearish_bias = bias_last["ema_fast"] < bias_last["ema_slow"]

        trend_up = last["ema_fast"] > last["ema_slow"]
        trend_down = last["ema_fast"] < last["ema_slow"]

        rsi_buy = last["rsi"] >= ind["rsi_buy"]
        rsi_sell = last["rsi"] <= ind["rsi_sell"]

        adx_ok = True
        atr_ok = True

        pullback_buy = (last["close"] <= last["ema_fast"] + last["atr"] * ind["pullback_atr"]) and trend_up
        pullback_sell = (last["close"] >= last["ema_fast"] - last["atr"] * ind["pullback_atr"]) and trend_down

        breakout_high = df["high"].rolling(ind["breakout_lookback"]).max().iloc[-2]
        breakout_low = df["low"].rolling(ind["breakout_lookback"]).min().iloc[-2]
        breakout_buy = last["close"] > breakout_high
        breakout_sell = last["close"] < breakout_low

        if bullish_bias and trend_up and rsi_buy and adx_ok and atr_ok and (pullback_buy or breakout_buy):
            return "BUY"
        if bearish_bias and trend_down and rsi_sell and adx_ok and atr_ok and (pullback_sell or breakout_sell):
            return "SELL"
        return None


class Alerts:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.queue = queue.Queue()
        self.webhook = os.getenv("ALERT_WEBHOOK_URL", "").strip()

    def send(self, level: str, message: str) -> None:
        logging.log(getattr(logging, level, logging.INFO), message)
        self.storage.save_alert(level, message)
        self.queue.put({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "message": message})
        if self.webhook:
            try:
                requests.post(
                    self.webhook,
                    json={"level": level, "message": message, "ts": datetime.now(timezone.utc).isoformat()},
                    timeout=5
                )
            except Exception:
                pass


def ping_success() -> None:
    try:
        winsound.Beep(1200, 350)
    except Exception:
        pass


class ForexBroker:
    def __init__(self, cfg: Dict, alerts: Alerts):
        self.cfg = cfg
        self.alerts = alerts

    def connect(self, login: Optional[int], password: Optional[str], server: Optional[str]) -> None:
        path = os.getenv("MT5_PATH", "C:\\Program Files\\MetaTrader 5\\terminal64.exe")
        self.alerts.send("INFO", f"Initializing MT5 at {path}...")
        
        if not mt5.initialize(path=path):
            err = mt5.last_error()
            self.alerts.send("ERROR", f"MT5 initialize failed: {err}")
            # Try without explicit path as fallback
            if not mt5.initialize():
                raise RuntimeError(f"MT5 initialize failed (default path): {mt5.last_error()}")
        
        if login and password and server:
            self.alerts.send("INFO", f"Logging into MT5 Account {login} on {server}...")
            authorized = mt5.login(login=login, password=password, server=server)
            if not authorized:
                err = mt5.last_error()
                self.alerts.send("ERROR", f"MT5 login failed: {err}")
                raise RuntimeError(f"MT5 login failed for account {login}: {err}")
            self.alerts.send("INFO", "MT5 Login Successful")
        else:
            self.alerts.send("INFO", "Using current MT5 terminal account (no credentials provided)")

    def ensure_symbol(self, symbol: str) -> None:
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"MT5 symbol not found: {symbol}")
        if not info.visible:
            mt5.symbol_select(symbol, True)

    def account_info(self):
        info = mt5.account_info()
        if info is None:
            raise RuntimeError("MT5 account_info failed")
        return info

    def get_rates(self, symbol: str, timeframe, bars: int = 300) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None:
            raise RuntimeError(f"MT5 rates failed for {symbol}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df[["time", "open", "high", "low", "close", "tick_volume"]]

    def spread_ok(self, symbol: str) -> bool:
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None:
            return False
        spread_points = (tick.ask - tick.bid) / info.point
        return spread_points <= self.cfg["forex"]["spread_filter_points"]

    def place_order(self, symbol: str, side: str, volume: float, price: float, sl: float, tp: float):
        order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
        
        # Determine filling mode
        info = mt5.symbol_info(symbol)
        filling = mt5.ORDER_FILLING_IOC # Default to IOC
        if info:
            # Using numeric values for flags as some MT5 versions miss the SYMBOL_FILLING constants
            if info.filling_mode & 1: # SYMBOL_FILLING_FOK
                filling = mt5.ORDER_FILLING_FOK
            elif info.filling_mode & 2: # SYMBOL_FILLING_IOC
                filling = mt5.ORDER_FILLING_IOC
            else:
                filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.cfg["forex"]["slippage_points"],
            "magic": self.cfg["magic_number"],
            "comment": self.cfg["comment"],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        
        self.alerts.send("INFO", f"Sending {side} order for {symbol}: {volume} lots at {price}")
        result = mt5.order_send(request)
        if result is None:
            err = mt5.last_error()
            raise RuntimeError(f"MT5 order_send returned None. Error: {err}")
            
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order failed. Retcode: {result.retcode}, Comment: {result.comment}")
            
        return result

    def modify_sl(self, symbol: str, ticket: int, new_sl: float):
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": new_sl
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 modify SL failed {result}")

    def close_partial(self, symbol: str, ticket: int, volume: float):
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return
        p = pos[0]
        order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": self.cfg["forex"]["slippage_points"],
            "magic": self.cfg["magic_number"],
            "comment": self.cfg["comment"]
        }
        mt5.order_send(request)

    def open_positions(self):
        return mt5.positions_get()

    def history_deals(self, from_days: int = 2):
        utc_from = datetime.now(timezone.utc) - timedelta(days=from_days)
        utc_to = datetime.now(timezone.utc)
        return mt5.history_deals_get(utc_from, utc_to)

class BybitBroker:
    def __init__(self, cfg: Dict):
        self.cfg = cfg
        self.session = BybitHTTP(
            testnet=cfg["crypto"]["use_testnet"],
            api_key=os.getenv("BYBIT_API_KEY", ""),
            api_secret=os.getenv("BYBIT_API_SECRET", "")
        )
        self._instrument_cache = {}

    def account_balance(self) -> float:
        try:
            resp = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
            if "result" not in resp or "list" not in resp["result"]:
                raise RuntimeError(f"Bybit balance failed: {resp}")
            return float(resp["result"]["list"][0]["coin"][0]["walletBalance"])
        except Exception as e:
            if "401" in str(e):
                raise RuntimeError(f"Bybit 401 Unauthorized: Check your API Key and Secret. {e}")
            raise RuntimeError(f"Bybit balance error: {e}")

    def get_kline(self, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        resp = self.session.get_kline(
            category=self.cfg["crypto"]["category"],
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        if "result" not in resp or "list" not in resp["result"]:
            raise RuntimeError("Bybit kline failed")
        data = resp["result"]["list"]
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "turnover"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
        return df.sort_values("time")

    def _instrument_info(self, symbol: str) -> Dict:
        if symbol in self._instrument_cache:
            return self._instrument_cache[symbol]
        resp = self.session.get_instruments_info(category=self.cfg["crypto"]["category"], symbol=symbol)
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit instruments failed {resp}")
        info = resp["result"]["list"][0]
        self._instrument_cache[symbol] = info
        return info

    def place_order(self, symbol: str, side: str, qty: float, sl: float, tp: float):
        resp = self.session.place_order(
            category=self.cfg["crypto"]["category"],
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(qty),
            stopLoss=str(sl),
            takeProfit=str(tp),
            timeInForce="GoodTillCancel"
        )
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit order failed {resp}")
        return resp

    def get_positions(self, symbol: str):
        resp = self.session.get_positions(category=self.cfg["crypto"]["category"], symbol=symbol)
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit positions failed {resp}")
        return resp["result"]["list"]

    def set_trading_stop(self, symbol: str, sl: float):
        resp = self.session.set_trading_stop(
            category=self.cfg["crypto"]["category"],
            symbol=symbol,
            stopLoss=str(sl)
        )
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit set stop failed {resp}")

    def close_partial(self, symbol: str, side: str, qty: float):
        close_side = "Sell" if side == "Buy" else "Buy"
        resp = self.session.place_order(
            category=self.cfg["crypto"]["category"],
            symbol=symbol,
            side=close_side,
            orderType="Market",
            qty=str(qty),
            reduceOnly=True,
            timeInForce="GoodTillCancel"
        )
        if resp.get("retCode") != 0:
            raise RuntimeError(f"Bybit partial close failed {resp}")

    def get_closed_pnl(self, symbol: str, limit: int = 50):
        resp = self.session.get_closed_pnl(category=self.cfg["crypto"]["category"], symbol=symbol, limit=limit)
        if resp.get("retCode") != 0:
            return []
        return resp["result"]["list"]


class PerformanceTracker:
    def __init__(self, storage: Storage):
        self.storage = storage

    def compute_stats(self) -> Dict:
        with sqlite3.connect(self.storage.db_path) as con:
            df = pd.read_sql("SELECT * FROM trades", con)
        if df.empty:
            return {
                "total_trades": 0, "win_rate": 0, "profit_factor": 0,
                "monthly": {}, "weekly": {}
            }
        df["pnl"] = df["pnl"].fillna(0)
        total_trades = len(df)
        wins = len(df[df["pnl"] > 0])
        win_rate = (wins / total_trades) * 100 if total_trades else 0
        gross_profit = df[df["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(df[df["pnl"] < 0]["pnl"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        df["open_time"] = pd.to_datetime(df["open_time"])
        df["month"] = df["open_time"].dt.to_period("M").astype(str)
        df["week"] = df["open_time"].dt.to_period("W").astype(str)
        monthly = df.groupby("month")["pnl"].sum().to_dict()
        weekly = df.groupby("week")["pnl"].sum().to_dict()

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "monthly": monthly,
            "weekly": weekly
        }


class Backtester:
    def __init__(self, cfg: Dict, strategy: StrategyEngine):
        self.cfg = cfg
        self.strategy = strategy

    def run(self, df: pd.DataFrame, bias_df: pd.DataFrame, initial_equity: float = 10000.0) -> Dict:
        ind = self.cfg["indicators"]
        eq = initial_equity
        equity_curve = []
        open_trade = None

        df = df.copy().reset_index(drop=True)
        bias_df = bias_df.copy().reset_index(drop=True)

        for i in range(100, len(df)):
            window = df.iloc[:i + 1]
            bias_window = bias_df.iloc[:i + 1]
            signal = self.strategy.evaluate(window, bias_window)
            price = window.iloc[-1]["close"]
            atr = Indicators.atr(window, ind["atr_period"]).iloc[-1]

            if open_trade:
                side = open_trade["side"]
                entry = open_trade["entry"]
                sl = open_trade["sl"]
                tp = open_trade["tp"]
                if (side == "BUY" and price <= sl) or (side == "SELL" and price >= sl):
                    pnl = (price - entry) if side == "BUY" else (entry - price)
                    eq += pnl * open_trade["size"]
                    open_trade = None
                elif (side == "BUY" and price >= tp) or (side == "SELL" and price <= tp):
                    pnl = (price - entry) if side == "BUY" else (entry - price)
                    eq += pnl * open_trade["size"]
                    open_trade = None

            if not open_trade and signal:
                stop_dist = atr * self.cfg["trade_management"]["stop_atr"]
                if stop_dist <= 0:
                    continue
                if signal == "BUY":
                    sl = price - stop_dist
                    tp = price + stop_dist * self.cfg["risk"]["reward_to_risk_min"]
                else:
                    sl = price + stop_dist
                    tp = price - stop_dist * self.cfg["risk"]["reward_to_risk_min"]
                size = (eq * self.cfg["risk"]["risk_per_trade"]) / max(stop_dist, 1e-8)
                open_trade = {"side": signal, "entry": price, "sl": sl, "tp": tp, "size": size}

            equity_curve.append({"ts": str(window.iloc[-1]["time"]), "equity": eq})

        return {"equity_curve": equity_curve}

class TradingEngine:
    def __init__(self):
        self.storage = Storage(CONFIG["storage"]["db_path"])
        self.alerts = Alerts(self.storage)
        self.news = NewsFilter(CONFIG["news_filter"])
        self.risk_engine = RiskEngine(CONFIG, self.storage)
        self.strategy = StrategyEngine(CONFIG)
        self.performance = PerformanceTracker(self.storage)
        self.backtester = Backtester(CONFIG, self.strategy)
        self.forex: Optional[ForexBroker] = None
        self.bybit: Optional[BybitBroker] = None
        self.open_trades: Dict[str, Trade] = {}
        self.last_trade_time: Optional[float] = None
        self.equity_high: float = 0.0
        self.running = True
        self.initialized = False

    def _load_api_keys_txt(self, path: str) -> Dict[str, str]:
        if not os.path.exists(path):
            return {}
        data = {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                l = s.lower()
                if l.startswith("login"):
                    parts = s.split()
                    if len(parts) >= 2:
                        data["MT5_LOGIN"] = parts[-1]
                if "mt5 password" in l:
                    parts = s.split()
                    if parts:
                        data["MT5_PASSWORD"] = parts[-1]
                if l.startswith("server") or l.startswith("mt5 server"):
                    parts = s.split(maxsplit=1)
                    if len(parts) == 2:
                        data["MT5_SERVER"] = parts[1]
                if l.startswith("api key") or l.startswith("bybit api key"):
                    parts = s.split()
                    if len(parts) >= 3:
                        data["BYBIT_API_KEY"] = parts[-1]
                if l.startswith("api secret") or l.startswith("bybit api secret"):
                    parts = s.split()
                    if len(parts) >= 3:
                        data["BYBIT_API_SECRET"] = parts[-1]
        return data

    def _load_credentials(self) -> None:
        # Search in CWD and script directory
        search_paths = [
            os.path.join(os.getcwd(), "API keys.txt"),
            os.path.join(os.path.dirname(__file__), "API keys.txt")
        ]
        found_any = False
        for api_file in search_paths:
            if os.path.exists(api_file):
                self.alerts.send("INFO", f"Loading credentials from {api_file}...")
                creds = self._load_api_keys_txt(api_file)
                for k, v in creds.items():
                    if not os.getenv(k):
                        os.environ[k] = v
                found_any = True
                self.alerts.send("INFO", f"Successfully loaded credentials from {api_file}")
        
        if not found_any:
            self.alerts.send("WARNING", "No 'API keys.txt' found in CWD or script directory.")

    def init(self) -> None:
        self.alerts.send("INFO", "Initializing Trading Engine...")
        self._load_credentials()
        
        # Initialize Forex if enabled
        if CONFIG["forex"]["enabled"]:
            self.alerts.send("INFO", "Forex module enabled. Connecting to MT5...")
            self.forex = ForexBroker(CONFIG, self.alerts)
            login = os.getenv("MT5_LOGIN")
            password = os.getenv("MT5_PASSWORD")
            server = os.getenv("MT5_SERVER")
            login_i = int(login) if login and login.isdigit() else None
            
            try:
                self.forex.connect(login_i, password, server)
                for sym in CONFIG["forex"]["symbols"]:
                    self.forex.ensure_symbol(sym)
            except Exception as e:
                self.alerts.send("ERROR", f"Forex initialization failed: {e}")
                CONFIG["forex"]["enabled"] = False # Disable if failed
        
        # Initialize Bybit if enabled
        if CONFIG["crypto"]["enabled"]:
            self.alerts.send("INFO", "Crypto module enabled. Connecting to Bybit...")
            try:
                self.bybit = BybitBroker(CONFIG)
                # Test connection
                self.bybit.account_balance()
                self.alerts.send("INFO", "Bybit connection successful")
            except Exception as e:
                self.alerts.send("ERROR", f"Crypto initialization failed: {e}. Disabling crypto module.")
                CONFIG["crypto"]["enabled"] = False
                self.bybit = None

        self.open_trades = {t.trade_id: t for t in self.storage.load_open_trades()}
        self.alerts.send("INFO", f"Loaded {len(self.open_trades)} open trades from storage.")
        
        eq_high = self.storage.get_state("equity_high")
        self.equity_high = float(eq_high) if eq_high else 0.0
        
        self.initialized = True
        self.alerts.send("INFO", "Engine successfully initialized and ready.")

    def _session_ok(self, market: str) -> bool:
        now_utc = datetime.now(timezone.utc)
        cfg = CONFIG["session_filter"]["forex"] if market == "FOREX" else CONFIG["session_filter"]["crypto"]
        return cfg["start_hour_utc"] <= now_utc.hour < cfg["end_hour_utc"]

    def _calculate_drawdown(self, equity: float) -> float:
        if equity > self.equity_high:
            self.equity_high = equity
            self.storage.set_state("equity_high", str(self.equity_high))
        if self.equity_high <= 0:
            return 0.0
        return max(0.0, (self.equity_high - equity) / self.equity_high)

    def _volatility_scale(self, atr_series: pd.Series) -> float:
        window = CONFIG["indicators"]["volatility_window"]
        if len(atr_series) < window + 1:
            return 1.0
        atr = atr_series.iloc[-1]
        med = atr_series.rolling(window).median().iloc[-1]
        if med <= 0:
            return 1.0
        ratio = atr / med
        scale = 1.0 / max(0.5, min(2.0, ratio))
        return max(0.5, min(1.5, scale))

    def _calc_forex_position_size(self, symbol: str, stop_distance: float, equity: float, atr_series: pd.Series) -> float:
        info = mt5.symbol_info(symbol)
        if info is None or stop_distance <= 0:
            return 0.0
        risk_amt = equity * self.risk_engine.risk_per_trade()
        risk_amt *= self._volatility_scale(atr_series)
        tick_value = info.trade_tick_value
        tick_size = info.trade_tick_size
        if tick_size == 0:
            return 0.0
        value_per_point = tick_value / tick_size
        points = stop_distance / info.point
        if points == 0:
            return 0.0
        volume = risk_amt / (points * value_per_point)
        volume = max(info.volume_min, min(info.volume_max, volume))
        volume = round(volume / info.volume_step) * info.volume_step
        return float(volume)

    def _calc_crypto_qty(self, symbol: str, stop_distance: float, equity: float, atr_series: pd.Series) -> float:
        if stop_distance <= 0 or not self.bybit:
            return 0.0
        risk_amt = equity * self.risk_engine.risk_per_trade()
        risk_amt *= self._volatility_scale(atr_series)
        qty = risk_amt / stop_distance
        info = self.bybit._instrument_info(symbol)
        min_qty = float(info["lotSizeFilter"]["minOrderQty"])
        step = float(info["lotSizeFilter"]["qtyStep"])
        qty = max(min_qty, qty)
        qty = math.floor(qty / step) * step
        return float(qty)

    def _should_trade(self, symbol: str, market: str) -> bool:
        if not self._session_ok(market):
            return False
        if market == "FOREX" and self.news.is_blocked(symbol):
            return False
        return True

    def update_equity(self) -> Tuple[float, float]:
        equity = 0.0
        if CONFIG["forex"]["enabled"] and self.forex:
            try:
                equity += self.forex.account_info().equity
            except Exception as e:
                self.alerts.send("ERROR", f"Failed to get MT5 equity: {e}")
        
        if CONFIG["crypto"]["enabled"] and self.bybit:
            try:
                equity += self.bybit.account_balance()
            except Exception as e:
                self.alerts.send("ERROR", f"Failed to get Bybit balance: {e}")
                # If crypto fails, we just don't add its balance, but keep going
        
        drawdown = self._calculate_drawdown(equity)
        self.storage.save_equity(equity, drawdown)
        return equity, drawdown

    def _sync_closed_trades_forex(self) -> None:
        if not self.forex: return
        deals = self.forex.history_deals()
        if deals is None:
            return
        deal_map = {}
        for d in deals:
            if d.magic != CONFIG["magic_number"]:
                continue
            deal_map.setdefault(d.position_id, []).append(d)
        for trade_id, trade in list(self.open_trades.items()):
            if trade.market != "FOREX":
                continue
            position_id = int(trade_id)
            if position_id in deal_map:
                pnl = sum([d.profit for d in deal_map[position_id]])
                close_time = max([d.time for d in deal_map[position_id]])
                self.storage.update_trade(trade_id, status="CLOSED", pnl=pnl, close_time=str(close_time))
                self.open_trades.pop(trade_id, None)
                self.alerts.send("INFO", f"Trade closed: {trade.symbol} pnl={pnl}")
                if pnl > 0:
                    ping_success()

    def _sync_closed_trades_crypto(self) -> None:
        if not self.bybit: return
        for trade_id, trade in list(self.open_trades.items()):
            if trade.market != "CRYPTO":
                continue
            try:
                closed = self.bybit.get_closed_pnl(trade.symbol, limit=100)
                for c in closed:
                    if c.get("orderId") == trade_id or c.get("execId") == trade_id:
                        pnl = float(c.get("closedPnl", 0))
                        self.storage.update_trade(trade_id, status="CLOSED", pnl=pnl, close_time=str(c.get("createdTime")))
                        self.open_trades.pop(trade_id, None)
                        self.alerts.send("INFO", f"Trade closed: {trade.symbol} pnl={pnl}")
                        if pnl > 0:
                            ping_success()
                        break
            except Exception:
                continue

    def manage_open_trades(self) -> None:
        for trade_id, trade in list(self.open_trades.items()):
            try:
                if trade.market == "FOREX" and self.forex:
                    positions = mt5.positions_get(ticket=int(trade_id))
                    if not positions:
                        continue
                    pos = positions[0]
                    df = self.forex.get_rates(trade.symbol, CONFIG["forex"]["timeframe"], 200)
                    atr_series = Indicators.atr(df, CONFIG["indicators"]["atr_period"])
                    atr = atr_series.iloc[-1]
                    if trade.side == "BUY":
                        new_sl = max(trade.stop_price, pos.price_current - atr * CONFIG["trade_management"]["trail_atr"])
                        if new_sl > trade.stop_price:
                            self.forex.modify_sl(trade.symbol, pos.ticket, new_sl)
                            self.storage.update_trade(trade_id, stop_price=new_sl)
                    else:
                        new_sl = min(trade.stop_price, pos.price_current + atr * CONFIG["trade_management"]["trail_atr"])
                        if new_sl < trade.stop_price:
                            self.forex.modify_sl(trade.symbol, pos.ticket, new_sl)
                            self.storage.update_trade(trade_id, stop_price=new_sl)

                    if trade.partial_taken == 0:
                        risk = abs(trade.entry_price - trade.stop_price)
                        if risk > 0:
                            if trade.side == "BUY" and pos.price_current >= trade.entry_price + risk * CONFIG["trade_management"]["partial_rr"]:
                                self.forex.close_partial(trade.symbol, pos.ticket, trade.qty * CONFIG["trade_management"]["partial_close_pct"])
                                self.storage.update_trade(trade_id, partial_taken=1)
                            if trade.side == "SELL" and pos.price_current <= trade.entry_price - risk * CONFIG["trade_management"]["partial_rr"]:
                                self.forex.close_partial(trade.symbol, pos.ticket, trade.qty * CONFIG["trade_management"]["partial_close_pct"])
                                self.storage.update_trade(trade_id, partial_taken=1)

                if trade.market == "CRYPTO" and self.bybit:
                    df = self.bybit.get_kline(trade.symbol, CONFIG["crypto"]["timeframe"], 200)
                    atr_series = Indicators.atr(df, CONFIG["indicators"]["atr_period"])
                    atr = atr_series.iloc[-1]
                    pos_list = self.bybit.get_positions(trade.symbol)
                    if not pos_list:
                        continue
                    pos = pos_list[0]
                    price = float(pos["markPrice"])
                    if trade.side == "BUY":
                        new_sl = max(trade.stop_price, price - atr * CONFIG["trade_management"]["trail_atr"])
                        if new_sl > trade.stop_price:
                            self.bybit.set_trading_stop(trade.symbol, new_sl)
                            self.storage.update_trade(trade_id, stop_price=new_sl)
                    else:
                        new_sl = min(trade.stop_price, price + atr * CONFIG["trade_management"]["trail_atr"])
                        if new_sl < trade.stop_price:
                            self.bybit.set_trading_stop(trade.symbol, new_sl)
                            self.storage.update_trade(trade_id, stop_price=new_sl)

                    if trade.partial_taken == 0:
                        risk = abs(trade.entry_price - trade.stop_price)
                        if risk > 0:
                            if trade.side == "BUY" and price >= trade.entry_price + risk * CONFIG["trade_management"]["partial_rr"]:
                                self.bybit.close_partial(trade.symbol, "Buy", trade.qty * CONFIG["trade_management"]["partial_close_pct"])
                                self.storage.update_trade(trade_id, partial_taken=1)
                            if trade.side == "SELL" and price <= trade.entry_price - risk * CONFIG["trade_management"]["partial_rr"]:
                                self.bybit.close_partial(trade.symbol, "Sell", trade.qty * CONFIG["trade_management"]["partial_close_pct"])
                                self.storage.update_trade(trade_id, partial_taken=1)
            except Exception as exc:
                self.alerts.send("ERROR", f"Trade management error: {exc}")

    def scan_and_trade_forex(self, equity: float) -> None:
        if not CONFIG["forex"]["enabled"] or not self.forex:
            return
        for symbol in CONFIG["forex"]["symbols"]:
            try:
                # Check if we already have an open trade for this symbol
                if any(t.symbol == symbol for t in self.open_trades.values()):
                    continue

                if not self._should_trade(symbol, "FOREX"):
                    continue
                if not self.forex.spread_ok(symbol):
                    continue
                df = self.forex.get_rates(symbol, CONFIG["forex"]["timeframe"], CONFIG["forex"]["bars"])
                bias_df = self.forex.get_rates(symbol, CONFIG["forex"]["bias_timeframe"], CONFIG["forex"]["bars"])
                signal = self.strategy.evaluate(df, bias_df)
                if not signal:
                    continue
                if not self.risk_engine.allow_trade(len(self.open_trades), self.last_trade_time):
                    continue
                atr_series = Indicators.atr(df, CONFIG["indicators"]["atr_period"])
                atr = atr_series.iloc[-1]
                stop_dist = atr * CONFIG["trade_management"]["stop_atr"]
                if signal == "BUY":
                    entry = df.iloc[-1]["close"]
                    sl = entry - stop_dist
                    tp = entry + stop_dist * CONFIG["risk"]["reward_to_risk_min"]
                else:
                    entry = df.iloc[-1]["close"]
                    sl = entry + stop_dist
                    tp = entry - stop_dist * CONFIG["risk"]["reward_to_risk_min"]

                volume = self._calc_forex_position_size(symbol, stop_dist, equity, atr_series)
                if volume <= 0:
                    continue
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    continue
                price = tick.ask if signal == "BUY" else tick.bid
                result = self.forex.place_order(symbol, signal, volume, price, sl, tp)
                trade_id = str(result.order)
                trade = Trade(
                    trade_id=trade_id,
                    market="FOREX",
                    symbol=symbol,
                    side=signal,
                    qty=volume,
                    entry_price=price,
                    stop_price=sl,
                    take_profit=tp,
                    open_time=datetime.now(timezone.utc).isoformat()
                )
                self.open_trades[trade_id] = trade
                self.storage.save_trade(trade)
                self.last_trade_time = time.time()
                self.alerts.send("INFO", f"Prop Firm Machine: Trade opened: {symbol} {signal} {volume}")
            except Exception as exc:
                self.alerts.send("ERROR", f"Prop Firm Machine: Forex scan error {symbol}: {exc}")

    def scan_and_trade_crypto(self, equity: float) -> None:
        if not CONFIG["crypto"]["enabled"] or not self.bybit:
            return
        for symbol in CONFIG["crypto"]["symbols"]:
            try:
                if not self._should_trade(symbol, "CRYPTO"):
                    continue
                df = self.bybit.get_kline(symbol, CONFIG["crypto"]["timeframe"], CONFIG["crypto"]["bars"])
                bias_df = self.bybit.get_kline(symbol, CONFIG["crypto"]["bias_timeframe"], CONFIG["crypto"]["bars"])
                signal = self.strategy.evaluate(df, bias_df)
                if not signal:
                    continue
                if not self.risk_engine.allow_trade(len(self.open_trades), self.last_trade_time):
                    continue
                atr_series = Indicators.atr(df, CONFIG["indicators"]["atr_period"])
                atr = atr_series.iloc[-1]
                stop_dist = atr * CONFIG["trade_management"]["stop_atr"]
                if signal == "BUY":
                    entry = df.iloc[-1]["close"]
                    sl = entry - stop_dist
                    tp = entry + stop_dist * CONFIG["risk"]["reward_to_risk_min"]
                else:
                    entry = df.iloc[-1]["close"]
                    sl = entry + stop_dist
                    tp = entry - stop_dist * CONFIG["risk"]["reward_to_risk_min"]

                qty = self._calc_crypto_qty(symbol, stop_dist, equity, atr_series)
                if qty <= 0:
                    continue
                side = "Buy" if signal == "BUY" else "Sell"
                result = self.bybit.place_order(symbol, side, qty, sl, tp)
                trade_id = result["result"]["orderId"]
                trade = Trade(
                    trade_id=trade_id,
                    market="CRYPTO",
                    symbol=symbol,
                    side=signal,
                    qty=qty,
                    entry_price=entry,
                    stop_price=sl,
                    take_profit=tp,
                    open_time=datetime.now(timezone.utc).isoformat()
                )
                self.open_trades[trade_id] = trade
                self.storage.save_trade(trade)
                self.last_trade_time = time.time()
                self.alerts.send("INFO", f"Prop Firm Machine: Trade opened: {symbol} {signal} {qty}")
            except Exception as exc:
                self.alerts.send("ERROR", f"Prop Firm Machine: Crypto scan error {symbol}: {exc}")

    def run_cycle(self) -> None:
        equity, drawdown = self.update_equity()
        self.risk_engine.update_mode(drawdown)
        if drawdown >= CONFIG["risk"]["soft_drawdown_pause"]:
            self.alerts.send("WARNING", f"Soft drawdown pause active: {drawdown:.2%}")
            return
        self.scan_and_trade_forex(equity)
        self.scan_and_trade_crypto(equity)
        self.manage_open_trades()
        self._sync_closed_trades_forex()
        self._sync_closed_trades_crypto()

    def run(self) -> None:
        while self.running:
            try:
                if not self.initialized:
                    try:
                        self.init()
                    except Exception as exc:
                        self.alerts.send("ERROR", f"Init failed: {exc}")
                        time.sleep(5)
                        continue
                self.run_cycle()
                time.sleep(CONFIG["loop_interval_seconds"])
            except Exception as exc:
                self.alerts.send("ERROR", f"System error: {exc}")
                time.sleep(5)

class DashboardServer:
    def __init__(self, engine: TradingEngine):
        self.engine = engine
        self.app = Flask(APP_NAME)
        self._init_routes()

    def _init_routes(self) -> None:
        @self.app.route("/")
        def index():
            html = """<!doctype html>
<html>
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Prop Firm Machine</title>
<style>
:root { --bg: #0b0f1a; --card: #141b2d; --accent: #4ee1a0; --text: #e8eefc; }
body { margin:0; font-family: Arial, sans-serif; background: var(--bg); color: var(--text); }
.header { padding: 16px; font-weight: bold; letter-spacing: 1px; }
.card { background: var(--card); margin: 12px; padding: 14px; border-radius: 12px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
@media(max-width: 600px){ .grid { grid-template-columns: 1fr; } }
.small { font-size: 12px; opacity: 0.8; }
</style>
</head>
<body>
<div class=\"header\">CORE ENGINE PROP FIRM MACHINE</div>
<div class=\"card\" id=\"status\">Loading...</div>
<div class=\"card\" id=\"risk\"></div>
<div class=\"card\" id=\"trades\"></div>
<script>
async function refresh(){
  const s = await fetch('/status').then(r=>r.json());
  const r = await fetch('/risk_state').then(r=>r.json());
  const t = await fetch('/open_trades').then(r=>r.json());
  document.getElementById('status').innerHTML =
    `<div>Equity: ${s.equity.toFixed(2)}</div><div>Drawdown: ${(s.drawdown*100).toFixed(2)}%</div><div>Mode: ${s.mode}</div>`;
  document.getElementById('risk').innerHTML =
    `<div>Risk per trade: ${(r.risk_per_trade*100).toFixed(2)}%</div>`;
  document.getElementById('trades').innerHTML =
    `<div>Open trades: ${t.length}</div><div class='small'>${t.map(x=>x.symbol+' '+x.side).join(', ')}</div>`;
}
refresh(); setInterval(refresh, 5000);
</script>
</body>
</html>"""
            return Response(html, mimetype="text/html")

        @self.app.route("/status")
        def status():
            eq_curve = self.engine.storage.load_equity_curve(1)
            eq = eq_curve[-1]["equity"] if eq_curve else 0
            dd = eq_curve[-1]["drawdown"] if eq_curve else 0
            return jsonify({
                "app": APP_NAME,
                "mode": self.engine.risk_engine.mode,
                "equity": eq,
                "drawdown": dd,
                "open_trades": len(self.engine.open_trades)
            })

        @self.app.route("/equity")
        def equity():
            return jsonify(self.engine.storage.load_equity_curve())

        @self.app.route("/crypto_balance")
        def crypto_balance():
            try:
                bal = self.engine.bybit.account_balance()
                return jsonify({"usdt": bal})
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @self.app.route("/mode")
        def mode():
            return jsonify({"mode": self.engine.risk_engine.mode})

        @self.app.route("/risk_state")
        def risk_state():
            eq_curve = self.engine.storage.load_equity_curve(1)
            dd = eq_curve[-1]["drawdown"] if eq_curve else 0
            return jsonify({
                "drawdown": dd,
                "risk_per_trade": self.engine.risk_engine.risk_per_trade()
            })

        @self.app.route("/open_trades")
        def open_trades():
            return jsonify([t.__dict__ for t in self.engine.open_trades.values()])

        @self.app.route("/recent_trades")
        def recent_trades():
            return jsonify(self.engine.storage.load_recent_trades())

        @self.app.route("/backtest")
        def backtest():
            stats = self.engine.performance.compute_stats()
            eq = self.engine.storage.load_equity_curve()
            return jsonify({
                "equity_curve": eq,
                "monthly_results": stats["monthly"],
                "weekly_results": stats["weekly"],
                "win_rate": stats["win_rate"],
                "drawdown": [x["drawdown"] for x in eq]
            })


class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            # Replace problematic arrow character with a plain ASCII version
            if isinstance(record.msg, str):
                record.msg = record.msg.replace("\u2192", "->")
            super().emit(record)
        except Exception:
            self.handleError(record)

def main() -> None:
    log_path = os.path.join(os.getcwd(), "run.log")
    
    # Configure handlers with explicit UTF-8 encoding for file
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    stream_handler = SafeStreamHandler(sys.stdout)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[file_handler, stream_handler],
        force=True
    )
    print("Starting engine", flush=True)
    logging.info("Starting engine")
    engine = TradingEngine()
    dashboard = DashboardServer(engine)

    server_thread = threading.Thread(
        target=lambda: dashboard.app.run(
            host=CONFIG["dashboard"]["host"],
            port=CONFIG["dashboard"]["port"],
            threaded=True
        ),
        daemon=True
    )
    server_thread.start()

    def handle_signal(sig, frame):
        engine.running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    engine.run()


if __name__ == "__main__":
    main()
