import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime, timedelta
import time
import sys
import json
import traceback
import os
import atexit
import builtins as _builtins
import requests
import winsound
import msvcrt

import google.generativeai as genai
import os

# --- Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
except Exception as e:
    print(f"Error loading config.json: {e}")
    sys.exit(1)

# Global Settings
SYMBOLS = config.get("symbols", ["EURUSD"])
TIMEFRAME_STR = config.get("timeframe", "TIMEFRAME_M5")
TIMEFRAME = getattr(mt5, TIMEFRAME_STR)
LOT_SIZE = config.get("lot_size", 0.01)
MAGIC_NUMBER = config.get("magic_number", 12345)
CHECK_INTERVAL_SECONDS = config.get("check_interval_seconds", 60)
MAX_OPEN_TRADES_TOTAL = config.get("max_open_trades_total", 20)
MAX_OPEN_TRADES_PER_SYMBOL = config.get("max_open_trades_per_symbol", 1)
MAX_OPEN_TRADES_PER_DIRECTION = config.get("max_open_trades_per_direction", 1)
MAX_OPEN_TRADES_PER_SYMBOL_STRONG = config.get("max_open_trades_per_symbol_strong", 2)
STRONG_SECOND_ENTRY_LOT_MULTIPLIER = config.get("strong_second_entry_lot_multiplier", 0.5)
REQUIRE_RSI_CROSS_FOR_ENTRY = config.get("require_rsi_cross_for_entry", False)
REQUIRE_TREND_ALIGNMENT = config.get("require_trend_alignment", False)
RSI_BUY = config.get("rsi_buy", 30)
RSI_SELL = config.get("rsi_sell", 70)
EMA_FAST = config.get("ema_fast", 12)
EMA_SLOW = config.get("ema_slow", 48)
MIN_BARS = config.get("min_bars", 100)
STRONG_SIGNAL_RSI_BUFFER = config.get("strong_signal_rsi_buffer", 5)
LIQUIDITY_SWEEP_LOOKBACK = config.get("liquidity_sweep_lookback", 5)
TAKE_PROFIT_PIPS = config.get("take_profit_pips", 10)
STOP_LOSS_PIPS = config.get("stop_loss_pips", 10)
DAILY_CLOSE_TIME = config.get("daily_close_time", "23:30")
BREAKEVEN_TRIGGER_PIPS = config.get("breakeven_trigger_pips", 0)
BREAKEVEN_OFFSET_PIPS = config.get("breakeven_offset_pips", 0)
TRAILING_START_PIPS = config.get("trailing_start_pips", 0)
TRAILING_DISTANCE_PIPS = config.get("trailing_distance_pips", 0)
TRAILING_STEP_PIPS = config.get("trailing_step_pips", 0)
PROFILE_SETTINGS = config.get("profile_settings", {})
STOP_DISTANCE_BUFFER_POINTS = config.get("stop_distance_buffer_points", 20)
PAUSE_NEW_ENTRIES = config.get("pause_new_entries", False)
TRADE_SESSION_START_HOUR = config.get("trade_session_start_hour", 8)
TRADE_SESSION_END_HOUR = config.get("trade_session_end_hour", 18)

# Telegram alerts
TELEGRAM_BOT_TOKEN = config.get("telegram_bot_token", "").strip()
TELEGRAM_CHAT_ID = str(config.get("telegram_chat_id", "")).strip()
TELEGRAM_POLLING_ENABLED = config.get("telegram_polling_enabled", True)

# --- Logging ---
LOG_PATH = os.path.join(os.path.dirname(__file__), "harvester.log")
LOCK_PATH = os.path.join(os.path.dirname(__file__), "harvester.lock")
_INSTANCE_LOCK_HANDLE = None

class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        try:
            self.terminal.write(message)
        except OSError:
            pass
        self.log.write(message)
        self.log.flush()

    def flush(self):
        try:
            self.terminal.flush()
        except OSError:
            pass
        self.log.flush()

sys.stdout = Logger(LOG_PATH)
sys.stderr = sys.stdout

def acquire_instance_lock():
    """Prevents multiple Harvester processes from trading simultaneously."""
    global _INSTANCE_LOCK_HANDLE
    if _INSTANCE_LOCK_HANDLE is not None:
        return True

    handle = open(LOCK_PATH, "a+")
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        print("Another Harvester instance is already running. Exiting.")
        return False

    _INSTANCE_LOCK_HANDLE = handle
    atexit.register(release_instance_lock)
    return True

def release_instance_lock():
    global _INSTANCE_LOCK_HANDLE
    if _INSTANCE_LOCK_HANDLE is None:
        return
    try:
        _INSTANCE_LOCK_HANDLE.seek(0)
        msvcrt.locking(_INSTANCE_LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    finally:
        _INSTANCE_LOCK_HANDLE.close()
        _INSTANCE_LOCK_HANDLE = None

# Gemini AI Setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')

def ask_gemini(question):
    """Sends a question to Gemini and returns the response."""
    if not GEMINI_API_KEY:
        return "⚠️ No Gemini API Key found on this laptop."
    try:
        # Provide context about the robot's current state
        account = mt5.account_info()
        positions = get_open_positions()
        context = f"""
        You are an AI assistant analyzing a live trading robot 'The Harvester'.
        Current Account Balance: ${account.balance if account else 'Unknown'}
        Open Positions: {len(positions)}
        
        User Question: {question}
        """
        response = model.generate_content(context)
        return response.text
    except Exception as e:
        return f"⚠️ Error talking to Gemini: {e}"

def send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Error sending telegram: {e}")

def handle_telegram_commands():
    """Checks for new Telegram messages and executes commands."""
    if not TELEGRAM_POLLING_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    global LOT_SIZE
    last_update_id = getattr(_builtins, "_telegram_last_id", 0)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        resp = requests.get(url, params={"offset": last_update_id + 1, "timeout": 1}, timeout=5)
        if resp.status_code == 200:
            updates = resp.json().get("result", [])
            for update in updates:
                _builtins._telegram_last_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id != TELEGRAM_CHAT_ID:
                    continue

                # --- HARVESTER COMMANDS (h_) ---
                if text == "/h_status":
                    info = mt5.account_info()
                    open_p = get_open_positions()
                    status_msg = f"--- 🚜 Harvester Status ---\n💰 Balance: ${info.balance:.2f}\n📈 Equity: ${info.equity:.2f}\n🔄 Open Trades: {len(open_p)}"
                    send_telegram(status_msg)
                
                elif text == "/h_settings":
                    settings_msg = f"--- 🚜 Harvester Brain ---\n📊 Lot Size: {LOT_SIZE}\n⏱ Timeframe: {TIMEFRAME_STR}\n🏆 TP: {TAKE_PROFIT_PIPS} Pips\n🛑 SL: {STOP_LOSS_PIPS} Pips"
                    send_telegram(settings_msg)

                elif text.startswith("/h_lot "):
                    try:
                        new_lot = float(text.split(" ")[1])
                        if 0.01 <= new_lot <= 1.0:
                            LOT_SIZE = new_lot
                            send_telegram(f"✅ Harvester Lot Size updated to: {LOT_SIZE}")
                        else:
                            send_telegram("❌ Error: Lot size must be between 0.01 and 1.0")
                    except Exception:
                        send_telegram("❌ Usage: /h_lot 0.10")

                elif text == "/h_close":
                    send_telegram("🚜 Closing all Harvester trades manually...")
                    for pos in get_open_positions():
                        close_position(pos)
                    send_telegram("✅ All Harvester positions closed.")

                elif text == "/h_panic":
                    send_telegram("🚨 HARVESTER PANIC: Closing all trades...")
                    for pos in get_open_positions():
                        close_position(pos)
                    send_telegram("✅ Harvester trades cleared.")

                # --- ASK GEMINI ---
                elif text.startswith("/ask "):
                    question = text[5:]
                    send_telegram("🤔 Thinking...")
                    answer = ask_gemini(question)
                    send_telegram(f"🤖 Gemini says:\n{answer}")

                # --- QUANTUM FLUX COMMANDS (q_) ---
                elif text == "/q_status":
                    info = mt5.account_info()
                    q_trades = [p for p in mt5.positions_get() if "Quantum" in p.comment]
                    status_msg = f"--- ⚡ Quantum Status ---\n📈 Equity: ${info.equity:.2f}\n🔄 Active Trades: {len(q_trades)}"
                    send_telegram(status_msg)

                elif text.startswith("/q_lot "):
                    try:
                        q_lot = float(text.split(" ")[1])
                        bridge_path = os.path.join(os.path.dirname(__file__), "..", "Quantum Flux", "remote_lot.txt")
                        os.makedirs(os.path.dirname(bridge_path), exist_ok=True)
                        with open(bridge_path, "w") as f:
                            f.write(str(q_lot))
                        send_telegram(f"✅ Quantum Lot command sent: {q_lot}")
                    except Exception as e:
                        send_telegram(f"❌ Error writing Quantum bridge: {e}")

                elif text == "/q_panic":
                    bridge_path = os.path.join(os.path.dirname(__file__), "..", "Quantum Flux", "remote_panic.txt")
                    os.makedirs(os.path.dirname(bridge_path), exist_ok=True)
                    with open(bridge_path, "w") as f:
                        f.write("PANIC")
                    send_telegram("🚨 QUANTUM PANIC command sent to MT5.")

                # --- ATM ROBOT COMMANDS (a_) ---
                elif text == "/a_status":
                    info = mt5.account_info()
                    a_trades = [p for p in mt5.positions_get() if "ATM" in p.comment]
                    status_msg = f"--- 🏦 ATM Robot Status ---\n📈 Equity: ${info.equity:.2f}\n🔄 Active Trades: {len(a_trades)}"
                    send_telegram(status_msg)

                elif text.startswith("/a_lot "):
                    try:
                        a_lot = float(text.split(" ")[1])
                        bridge_path = os.path.join(os.path.dirname(__file__), "..", "ATM", "remote_lot.txt")
                        os.makedirs(os.path.dirname(bridge_path), exist_ok=True)
                        with open(bridge_path, "w") as f:
                            f.write(str(a_lot))
                        send_telegram(f"✅ ATM Lot command sent: {a_lot}")
                    except Exception as e:
                        send_telegram(f"❌ Error writing ATM bridge: {e}")

                elif text == "/a_panic":
                    bridge_path = os.path.join(os.path.dirname(__file__), "..", "ATM", "remote_panic.txt")
                    os.makedirs(os.path.dirname(bridge_path), exist_ok=True)
                    with open(bridge_path, "w") as f:
                        f.write("PANIC")
                    send_telegram("🚨 ATM PANIC command sent to MT5.")

    except Exception as e:
        print(f"Error in handle_telegram_commands: {e}")


def play_success_ping() -> None:
    try:
        winsound.Beep(1200, 250)
        winsound.Beep(1600, 250)
    except Exception:
        pass


# --- MT5 Initialization ---
def initialize_mt5():
    """Initializes connection to MetaTrader 5 terminal."""
    path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    # Prefer attaching to an already-running terminal
    if not mt5.initialize():
        if not mt5.initialize(path=path):
            print("initialize() failed, error code =", mt5.last_error())
            sys.exit(1)
    print("MetaTrader5 initialized successfully.")
    account = mt5.account_info()
    if account:
        print(f"Connected account: {account.login} | {account.company} | {account.server}")

def shutdown_mt5():
    """Shuts down connection to MetaTrader 5 terminal."""
    mt5.shutdown()
    print("MetaTrader5 shutdown.")

def ensure_mt5_connection():
    """Ensures MT5 is initialized and connected; attempts reconnect if needed."""
    path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    if not mt5.initialize():
        print("MT5 not initialized. Attempting to initialize...")
        if not mt5.initialize():
            if not mt5.initialize(path=path):
                print("Re-initialize failed, error code =", mt5.last_error())
                return False

    # Validate terminal/account connectivity
    terminal = mt5.terminal_info()
    account = mt5.account_info()
    if terminal is None or account is None:
        print("MT5 connection lost. Shutting down and reconnecting...")
        mt5.shutdown()
        time.sleep(2)
        if not mt5.initialize():
            print("Reconnect failed, error code =", mt5.last_error())
            return False
        if mt5.terminal_info() is None or mt5.account_info() is None:
            print("Reconnect did not restore terminal/account info.")
            return False
        print("Reconnected to MT5.")
        account = mt5.account_info()
        if account:
            print(f"Connected account: {account.login} | {account.company} | {account.server}")
    return True

# --- Risk Management Helpers ---
def _pip_value(symbol_info):
    point = symbol_info.point
    if symbol_info.digits in (3, 5):
        return point * 10.0
    return point

def _min_stop_distance(symbol_info):
    stops_level = max(symbol_info.trade_stops_level or 0, symbol_info.trade_freeze_level or 0)
    broker_distance = stops_level * symbol_info.point
    extra_buffer = (STOP_DISTANCE_BUFFER_POINTS or 0) * symbol_info.point
    fallback_distance = symbol_info.point * 10.0
    return max(broker_distance + extra_buffer, fallback_distance)

def _profile_for_symbol(symbol: str) -> str:
    sym = symbol.upper()
    if sym == "XAUUSD":
        return "xau"
    if sym.endswith("JPY"):
        return "jpy"
    return "default"

def get_symbol_settings(symbol: str) -> dict:
    base = {
        "rsi_buy": RSI_BUY,
        "rsi_sell": RSI_SELL,
        "stop_loss_pips": STOP_LOSS_PIPS,
        "take_profit_pips": TAKE_PROFIT_PIPS,
        "breakeven_trigger_pips": BREAKEVEN_TRIGGER_PIPS,
        "breakeven_offset_pips": BREAKEVEN_OFFSET_PIPS,
        "trailing_start_pips": TRAILING_START_PIPS,
        "trailing_distance_pips": TRAILING_DISTANCE_PIPS,
        "trailing_step_pips": TRAILING_STEP_PIPS,
    }
    profile = _profile_for_symbol(symbol)
    override = PROFILE_SETTINGS.get(profile, {})
    return {**base, **override}

def calculate_sl_tp(symbol_info, order_type, price_open, sl_pips, tp_pips):
    """Calculate SL/TP price levels for a given order type and open price."""
    pip = _pip_value(symbol_info)
    sl = None
    tp = None

    if sl_pips and sl_pips > 0:
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = price_open - (sl_pips * pip)
        else:
            sl = price_open + (sl_pips * pip)

    if tp_pips and tp_pips > 0:
        if order_type == mt5.ORDER_TYPE_BUY:
            tp = price_open + (tp_pips * pip)
        else:
            tp = price_open - (tp_pips * pip)

    # Respect broker minimum stop distance if defined
    min_dist = _min_stop_distance(symbol_info)
    if min_dist and min_dist > 0:
        if sl is not None:
            if order_type == mt5.ORDER_TYPE_BUY:
                sl = min(sl, price_open - min_dist)
            else:
                sl = max(sl, price_open + min_dist)
        if tp is not None:
            if order_type == mt5.ORDER_TYPE_BUY:
                tp = max(tp, price_open + min_dist)
            else:
                tp = min(tp, price_open - min_dist)

    # Normalize to symbol digits
    digits = symbol_info.digits
    if sl is not None:
        sl = round(sl, digits)
    if tp is not None:
        tp = round(tp, digits)

    return sl, tp

def adjust_sl_tp_to_current(symbol_info, order_type, current_price, sl, tp):
    """Ensure SL/TP respects minimum stop distance from current price."""
    buffer = _min_stop_distance(symbol_info)

    if sl is not None:
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = min(sl, current_price - buffer)
        else:
            sl = max(sl, current_price + buffer)

    if tp is not None:
        if order_type == mt5.ORDER_TYPE_BUY:
            tp = max(tp, current_price + buffer)
        else:
            tp = min(tp, current_price - buffer)

    digits = symbol_info.digits
    if sl is not None:
        sl = round(sl, digits)
    if tp is not None:
        tp = round(tp, digits)
    return sl, tp

def ensure_position_sl_tp(position, settings: dict):
    """Ensure an open position has SL/TP set; add if missing."""
    symbol_info = mt5.symbol_info(position.symbol)
    if symbol_info is None:
        return

    need_sl = position.sl is None or position.sl == 0.0
    need_tp = position.tp is None or position.tp == 0.0
    if not (need_sl or need_tp):
        return

    sl, tp = calculate_sl_tp(
        symbol_info,
        position.type,
        position.price_open,
        settings.get("stop_loss_pips", STOP_LOSS_PIPS),
        settings.get("take_profit_pips", TAKE_PROFIT_PIPS),
    )

    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        return

    current_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

    # Adjust SL/TP to respect minimum stop distance from current price
    sl, tp = adjust_sl_tp_to_current(symbol_info, position.type, current_price, sl, tp)

    # If SL/TP is already behind/over current price, close immediately
    if need_sl and sl is not None:
        if position.type == mt5.ORDER_TYPE_BUY and sl >= current_price:
            print(f"SL already breached for position #{position.ticket}. Closing now.")
            close_position(position)
            return
        if position.type == mt5.ORDER_TYPE_SELL and sl <= current_price:
            print(f"SL already breached for position #{position.ticket}. Closing now.")
            close_position(position)
            return

    if need_tp and tp is not None:
        if position.type == mt5.ORDER_TYPE_BUY and tp <= current_price:
            print(f"TP already reached for position #{position.ticket}. Closing now.")
            close_position(position)
            return
        if position.type == mt5.ORDER_TYPE_SELL and tp >= current_price:
            print(f"TP already reached for position #{position.ticket}. Closing now.")
            close_position(position)
            return

    sl_val = sl if (need_sl and sl is not None) else (position.sl or 0.0)
    tp_val = tp if (need_tp and tp is not None) else (position.tp or 0.0)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "position": position.ticket,
        "sl": sl_val,
        "tp": tp_val,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(
            f"Failed to set SL/TP for position #{position.ticket}. "
            f"Error: {result.retcode} | Comment: {result.comment} | Last: {mt5.last_error()}"
        )

def ensure_all_positions_sl_tp():
    positions = get_open_positions()
    for pos in positions:
        settings = get_symbol_settings(pos.symbol)
        ensure_position_sl_tp(pos, settings)

def update_position_protection(position, settings: dict):
    """Apply break-even and trailing stop rules to an open position."""
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)
    if symbol_info is None or tick is None:
        return

    pip = _pip_value(symbol_info)
    current_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

    # Break-even move
    be_trigger_pips = settings.get("breakeven_trigger_pips", BREAKEVEN_TRIGGER_PIPS)
    be_offset_pips = settings.get("breakeven_offset_pips", BREAKEVEN_OFFSET_PIPS)
    if be_trigger_pips and be_trigger_pips > 0:
        be_trigger = position.price_open + (be_trigger_pips * pip) if position.type == mt5.ORDER_TYPE_BUY \
            else position.price_open - (be_trigger_pips * pip)
        if (position.type == mt5.ORDER_TYPE_BUY and current_price >= be_trigger) or \
           (position.type == mt5.ORDER_TYPE_SELL and current_price <= be_trigger):
            be_sl = position.price_open + (be_offset_pips * pip) if position.type == mt5.ORDER_TYPE_BUY \
                else position.price_open - (be_offset_pips * pip)
            # Only move SL forward
            if position.type == mt5.ORDER_TYPE_BUY and (position.sl is None or position.sl == 0.0 or be_sl > position.sl):
                sl, tp = adjust_sl_tp_to_current(symbol_info, position.type, current_price, be_sl, position.tp or None)
                _send_sltp_update(position, sl, tp)
            elif position.type == mt5.ORDER_TYPE_SELL and (position.sl is None or position.sl == 0.0 or be_sl < position.sl):
                sl, tp = adjust_sl_tp_to_current(symbol_info, position.type, current_price, be_sl, position.tp or None)
                _send_sltp_update(position, sl, tp)

    # Trailing stop
    trail_start_pips = settings.get("trailing_start_pips", TRAILING_START_PIPS)
    trail_dist_pips = settings.get("trailing_distance_pips", TRAILING_DISTANCE_PIPS)
    trail_step_pips = settings.get("trailing_step_pips", TRAILING_STEP_PIPS)
    if trail_start_pips and trail_start_pips > 0 and trail_dist_pips and trail_dist_pips > 0:
        trail_start = position.price_open + (trail_start_pips * pip) if position.type == mt5.ORDER_TYPE_BUY \
            else position.price_open - (trail_start_pips * pip)
        if (position.type == mt5.ORDER_TYPE_BUY and current_price >= trail_start) or \
           (position.type == mt5.ORDER_TYPE_SELL and current_price <= trail_start):
            desired_sl = current_price - (trail_dist_pips * pip) if position.type == mt5.ORDER_TYPE_BUY \
                else current_price + (trail_dist_pips * pip)
            step = trail_step_pips * pip if trail_step_pips and trail_step_pips > 0 else 0.0

            if position.type == mt5.ORDER_TYPE_BUY:
                if position.sl is None or position.sl == 0.0 or desired_sl - position.sl >= step:
                    sl, tp = adjust_sl_tp_to_current(symbol_info, position.type, current_price, desired_sl, position.tp or None)
                    _send_sltp_update(position, sl, tp)
            else:
                if position.sl is None or position.sl == 0.0 or position.sl - desired_sl >= step:
                    sl, tp = adjust_sl_tp_to_current(symbol_info, position.type, current_price, desired_sl, position.tp or None)
                    _send_sltp_update(position, sl, tp)

def _send_sltp_update(position, sl, tp):
    if sl is None and tp is None:
        return
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "position": position.ticket,
        "sl": sl if sl is not None else (position.sl or 0.0),
        "tp": tp if tp is not None else (position.tp or 0.0),
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(
            f"Failed to update SL/TP for position #{position.ticket}. "
            f"Error: {result.retcode} | Comment: {result.comment} | Last: {mt5.last_error()}"
        )

# --- Trading Functions ---
def execute_buy_order(symbol, lot, settings: dict):
    """Executes a market buy order."""
    if not mt5.symbol_info(symbol).visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select {symbol}, check if it's available in Market Watch.")
            return

    tick = mt5.symbol_info_tick(symbol)
    symbol_info = mt5.symbol_info(symbol)
    if tick is None or symbol_info is None:
        print(f"Failed to get tick/info for {symbol}.")
        return

    price = tick.ask
    sl, tp = calculate_sl_tp(
        symbol_info,
        mt5.ORDER_TYPE_BUY,
        price,
        settings.get("stop_loss_pips", STOP_LOSS_PIPS),
        settings.get("take_profit_pips", TAKE_PROFIT_PIPS),
    )
    sl, tp = adjust_sl_tp_to_current(symbol_info, mt5.ORDER_TYPE_BUY, price, sl, tp)
    sl = sl if sl is not None else 0.0
    tp = tp if tp is not None else 0.0

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY,
        "price": price,
        "deviation": 20, # Deviation from the requested price
        "magic": MAGIC_NUMBER,
        "comment": "The Harvester",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC, # Fill Or Kill
        "sl": sl,
        "tp": tp,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_INVALID_STOPS:
        print(f"Buy order got invalid stops for {symbol}. Retrying without SL/TP and attaching after fill.")
        request["sl"] = 0.0
        request["tp"] = 0.0
        result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Buy order failed for {symbol}. Error: {result.retcode}")
        print(f"Result: {result}")
    else:
        print(f"Buy order executed for {symbol}. Position #{result.order}")
        # Ensure SL/TP attached to the new position
        pos = None
        if getattr(result, "position", 0):
            found = mt5.positions_get(ticket=result.position)
            pos = found[0] if found else None
        if pos is None and getattr(result, "order", 0):
            found = mt5.positions_get(ticket=result.order)
            pos = found[0] if found else None
        if pos is None:
            found = mt5.positions_get(symbol=symbol)
            candidates = [p for p in (found or []) if p.magic == MAGIC_NUMBER and p.type == mt5.ORDER_TYPE_BUY]
            if candidates:
                pos = sorted(candidates, key=lambda p: p.time, reverse=True)[0]
        if pos is not None:
            ensure_position_sl_tp(pos, settings)
    return result

def execute_sell_order(symbol, lot, settings: dict):
    """Executes a market sell order."""
    if not mt5.symbol_info(symbol).visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select {symbol}, check if it's available in Market Watch.")
            return

    tick = mt5.symbol_info_tick(symbol)
    symbol_info = mt5.symbol_info(symbol)
    if tick is None or symbol_info is None:
        print(f"Failed to get tick/info for {symbol}.")
        return

    price = tick.bid
    sl, tp = calculate_sl_tp(
        symbol_info,
        mt5.ORDER_TYPE_SELL,
        price,
        settings.get("stop_loss_pips", STOP_LOSS_PIPS),
        settings.get("take_profit_pips", TAKE_PROFIT_PIPS),
    )
    sl, tp = adjust_sl_tp_to_current(symbol_info, mt5.ORDER_TYPE_SELL, price, sl, tp)
    sl = sl if sl is not None else 0.0
    tp = tp if tp is not None else 0.0

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_SELL,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "The Harvester",
        "type_filling": mt5.ORDER_FILLING_IOC,
        "sl": sl,
        "tp": tp,
    }

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_INVALID_STOPS:
        print(f"Sell order got invalid stops for {symbol}. Retrying without SL/TP and attaching after fill.")
        request["sl"] = 0.0
        request["tp"] = 0.0
        result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Sell order failed for {symbol}. Error: {result.retcode}")
        print(f"Result: {result}")
    else:
        print(f"Sell order executed for {symbol}. Position #{result.order}")
        # Ensure SL/TP attached to the new position
        pos = None
        if getattr(result, "position", 0):
            found = mt5.positions_get(ticket=result.position)
            pos = found[0] if found else None
        if pos is None and getattr(result, "order", 0):
            found = mt5.positions_get(ticket=result.order)
            pos = found[0] if found else None
        if pos is None:
            found = mt5.positions_get(symbol=symbol)
            candidates = [p for p in (found or []) if p.magic == MAGIC_NUMBER and p.type == mt5.ORDER_TYPE_SELL]
            if candidates:
                pos = sorted(candidates, key=lambda p: p.time, reverse=True)[0]
        if pos is not None:
            ensure_position_sl_tp(pos, settings)
    return result

def close_position(position):
    """Closes a specific open position."""
    symbol = position.symbol
    lot = position.volume
    order_type = mt5.ORDER_TYPE_BUY if position.type == mt5.ORDER_TYPE_SELL else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "The Harvester",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Close order failed for {symbol} (position #{position.ticket}). Error: {result.retcode}")
        print(f"Result: {result}")
    else:
        print(f"Position #{position.ticket} for {symbol} closed.")
    return result

def get_open_positions(symbol=None):
    """Retrieves all open positions for The Harvester specifically (Magic Number check)."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    # Filter to only show trades belonging to THIS robot
    return [p for p in positions if p.magic == MAGIC_NUMBER]

def get_entry_lot(symbol: str, direction: str, signal_strength: str = "normal"):
    """Allows only one Harvester trade per symbol."""
    if PAUSE_NEW_ENTRIES:
        print("New entries are paused. Skipping new trade.")
        return None

    all_positions = get_open_positions()
    if MAX_OPEN_TRADES_TOTAL and len(all_positions) >= MAX_OPEN_TRADES_TOTAL:
        print(f"Max total open trades reached ({MAX_OPEN_TRADES_TOTAL}). Skipping new entry.")
        return None

    symbol_positions = [p for p in all_positions if p.symbol == symbol]
    if symbol_positions:
        print(f"{symbol} already has an open Harvester trade. Skipping new entry.")
        return None

    return LOT_SIZE

def close_extra_positions():
    """Keeps the oldest Harvester position per symbol and closes any extras."""
    all_positions = get_open_positions()
    positions_by_symbol = {}
    closed_positions = []

    for position in all_positions:
        positions_by_symbol.setdefault(position.symbol, []).append(position)

    for symbol, symbol_positions in positions_by_symbol.items():
        if len(symbol_positions) <= 1:
            continue

        ordered_positions = sorted(symbol_positions, key=lambda p: (p.time, p.ticket))
        keep_position = ordered_positions[0]
        extra_positions = ordered_positions[1:]

        print(
            f"{symbol}: keeping position #{keep_position.ticket} "
            f"and closing {len(extra_positions)} extra trade(s)."
        )
        for position in extra_positions:
            result = close_position(position)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                closed_positions.append(position.ticket)

    if closed_positions:
        send_telegram(
            "The Harvester cleanup closed extra positions: "
            + ", ".join(str(ticket) for ticket in closed_positions)
        )
    else:
        print("No extra Harvester positions found.")

    return closed_positions

# --- Data Fetching ---
def get_mt5_data(symbol, timeframe, bars_count):
    """Fetches historical market data from MT5 and returns a pandas DataFrame."""
    utc_from = datetime.now() - timedelta(days=bars_count) # Fetch enough data for indicators, using local naive time
    
    # Request historical data
    rates = mt5.copy_rates_from(symbol, timeframe, utc_from, bars_count)
    
    if rates is None:
        print(f"No rates data for {symbol}, error code: {mt5.last_error()}")
        return pd.DataFrame()

    # Create DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    return df

def detect_liquidity_sweep(data: pd.DataFrame, lookback: int = 5):
    """Detect a buy/sell liquidity sweep on the latest completed candle."""
    if data.empty or len(data) < max(lookback + 1, 3):
        return None

    recent_window = data.iloc[-(lookback + 1):-1]
    current_bar = data.iloc[-1]

    recent_high = recent_window["high"].max()
    recent_low = recent_window["low"].min()
    current_high = current_bar["high"]
    current_low = current_bar["low"]
    current_close = current_bar["close"]

    if current_low < recent_low and current_close > recent_low:
        return "buy"
    if current_high > recent_high and current_close < recent_high:
        return "sell"
    return None

# --- Strategy Placeholder ---
def get_trading_signal(symbol: str, timeframe, bars_df: pd.DataFrame, settings: dict):
    """
    THIS IS WHERE YOU ADD YOUR TRADING STRATEGY LOGIC.

    This function should analyze the 'bars_df' (historical data) for the given 'symbol'
    and return a signal:
    - 'buy' for a buy signal
    - 'sell' for a sell signal
    - None for no signal

    Example: Basic RSI strategy (for demonstration only, not a robust strategy)
    """
    if bars_df.empty:
        return (None, "normal", None)

    # Calculate RSI
    # Note: Ensure enough data points for RSI calculation (default 14 periods)
    if len(bars_df) < max(EMA_SLOW + 2, 16):
        return (None, "normal", None)

    # Use only completed candles so the same forming bar cannot retrigger every scan.
    closed_bars = bars_df.iloc[:-1].copy()
    if len(closed_bars) < max(EMA_SLOW + 1, LIQUIDITY_SWEEP_LOOKBACK + 1, 15):
        return (None, "normal", None)

    # Calculate Standard RSI (Wilder's)
    delta = closed_bars['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    closed_bars['rsi'] = 100 - (100 / (1 + rs))

    if closed_bars['rsi'].isnull().all():
        return (None, "normal", None)

    last_rsi = closed_bars['rsi'].iloc[-1]
    prev_rsi = closed_bars['rsi'].iloc[-2]
    rsi_buy = settings.get("rsi_buy", RSI_BUY)
    rsi_sell = settings.get("rsi_sell", RSI_SELL)
    print(f"   > {symbol} RSI: {last_rsi:.2f} (Targets: {rsi_buy}/{rsi_sell})")

    # Trend filter using slow EMA
    fast_ema = closed_bars['close'].ewm(span=EMA_FAST, adjust=False).mean()
    slow_ema = closed_bars['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    in_uptrend = closed_bars['close'].iloc[-1] > slow_ema.iloc[-1]
    in_downtrend = closed_bars['close'].iloc[-1] < slow_ema.iloc[-1]
    fast_above_slow = fast_ema.iloc[-1] > slow_ema.iloc[-1]
    fast_below_slow = fast_ema.iloc[-1] < slow_ema.iloc[-1]
    strong_rsi_buffer = settings.get("strong_signal_rsi_buffer", STRONG_SIGNAL_RSI_BUFFER)
    signal_bar_time = closed_bars.index[-1]
    sweep_signal = detect_liquidity_sweep(closed_bars, settings.get("liquidity_sweep_lookback", LIQUIDITY_SWEEP_LOOKBACK))

    if sweep_signal:
        print(f"{symbol}: liquidity sweep detected for {sweep_signal.upper()}.")
    
    if not sweep_signal:
        return (None, "normal", signal_bar_time)

    entry_requires_rsi_cross = settings.get("require_rsi_cross_for_entry", REQUIRE_RSI_CROSS_FOR_ENTRY)
    entry_requires_trend = settings.get("require_trend_alignment", REQUIRE_TREND_ALIGNMENT)

    if sweep_signal == "buy":
        rsi_cross_ok = prev_rsi < rsi_buy and last_rsi >= rsi_buy
        trend_ok = in_uptrend
        strength = "strong" if last_rsi <= max(0, rsi_buy - strong_rsi_buffer) else "normal"

        if entry_requires_rsi_cross and not rsi_cross_ok:
            print(f"{symbol}: BUY sweep ignored because RSI did not cross up {rsi_buy}.")
            return (None, "normal", signal_bar_time)
        if entry_requires_trend and not trend_ok:
            print(f"{symbol}: BUY sweep ignored because trend filter is not aligned.")
            return (None, "normal", signal_bar_time)

        if rsi_cross_ok and fast_above_slow:
            strength = "strong"
        print(f"{symbol}: {strength.upper()} BUY signal from liquidity sweep.")
        return ("buy", strength, signal_bar_time)

    rsi_cross_ok = prev_rsi > rsi_sell and last_rsi <= rsi_sell
    trend_ok = in_downtrend
    strength = "strong" if last_rsi >= min(100, rsi_sell + strong_rsi_buffer) else "normal"

    if entry_requires_rsi_cross and not rsi_cross_ok:
        print(f"{symbol}: SELL sweep ignored because RSI did not cross down {rsi_sell}.")
        return (None, "normal", signal_bar_time)
    if entry_requires_trend and not trend_ok:
        print(f"{symbol}: SELL sweep ignored because trend filter is not aligned.")
        return (None, "normal", signal_bar_time)

    if rsi_cross_ok and fast_below_slow:
        strength = "strong"
    print(f"{symbol}: {strength.upper()} SELL signal from liquidity sweep.")
    return ("sell", strength, signal_bar_time)


def is_daily_close_time():
    """Checks if current local time matches DAILY_CLOSE_TIME (HH:MM)."""
    now_str = datetime.now().strftime("%H:%M")
    if not DAILY_CLOSE_TIME:
        return False
    return now_str == DAILY_CLOSE_TIME

def is_trade_session_open():
    """Allow new entries only during the configured local trading window."""
    if TRADE_SESSION_START_HOUR == TRADE_SESSION_END_HOUR:
        return True

    hour = datetime.now().hour
    if TRADE_SESSION_START_HOUR < TRADE_SESSION_END_HOUR:
        return TRADE_SESSION_START_HOUR <= hour < TRADE_SESSION_END_HOUR
    return hour >= TRADE_SESSION_START_HOUR or hour < TRADE_SESSION_END_HOUR

def manage_positions(symbol: str, settings: dict):
    """
    Ensures SL/TP are attached to open positions for a given symbol.
    """
    positions = get_open_positions(symbol)
    for pos in positions:
        ensure_position_sl_tp(pos, settings)
        update_position_protection(pos, settings)


# --- Main Bot Logic ---
def run_harvester():
    if not acquire_instance_lock():
        return
    initialize_mt5()
    print("--- The Harvester V2.0 (Active Naming) Starting ---")
    now_local = datetime.now()
    print(
        f"Local time: {now_local.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Entry session: {TRADE_SESSION_START_HOUR:02d}:00-{TRADE_SESSION_END_HOUR:02d}:00"
    )
    # Select symbols to ensure they are visible in Market Watch
    for symbol in SYMBOLS:
        if not mt5.symbol_select(symbol, True):
            print(f"Warning: Failed to select {symbol}. Check if it's available in Market Watch.")

    last_check_time = {}
    last_signal_candle = {}
    for symbol in SYMBOLS:
        last_check_time[symbol] = datetime.now(pytz.utc) - timedelta(seconds=CHECK_INTERVAL_SECONDS) # Initialize to ensure first check runs
        last_signal_candle[symbol] = None

    try:
        while True:
            if not ensure_mt5_connection():
                print("MT5 unavailable. Waiting 10 seconds before retry...")
                time.sleep(10)
                continue

            utc_now = datetime.now(pytz.utc)

            # Always enforce SL/TP on open positions
            ensure_all_positions_sl_tp()

            # --- DAILY CLOSE CHECK ---
            if is_daily_close_time():
                harvester_positions = get_open_positions()
                if harvester_positions:
                    print(f"\n--- {DAILY_CLOSE_TIME} Daily Close Time Reached ---")
                    send_telegram(f"⏰ Daily Close Time ({DAILY_CLOSE_TIME}): Closing all trades.")
                    for pos in harvester_positions:
                        close_position(pos)
                    time.sleep(65) # Wait past the minute to avoid double triggering
                    continue

            for symbol in SYMBOLS:
                # Check if enough time has passed since the last check
                if (utc_now - last_check_time[symbol]).total_seconds() >= CHECK_INTERVAL_SECONDS:
                    print(f"\nChecking {symbol} at {utc_now.strftime('%H:%M:%S')}")
                    last_check_time[symbol] = utc_now

                    # Fetch data
                    bars_df = get_mt5_data(symbol, TIMEFRAME, 100) # Fetch 100 bars for indicators

                    if not bars_df.empty:
                        current_price = mt5.symbol_info_tick(symbol).last
                        if current_price == 0: # Fallback if last price is 0 (e.g. for non-forex pairs, use bid)
                            current_price = mt5.symbol_info_tick(symbol).bid

                        # Get signal from your strategy
                        settings = get_symbol_settings(symbol)
                        signal, signal_strength, signal_bar_time = get_trading_signal(symbol, TIMEFRAME, bars_df, settings)
                        if signal and signal_bar_time is not None and last_signal_candle.get(symbol) == signal_bar_time:
                            print(f"{symbol}: signal on candle {signal_bar_time} already processed. Skipping duplicate entry.")
                            signal = None
                        
                        # --- Execute Trades ---
                        if signal and not is_trade_session_open():
                            print(f"{symbol}: signal found outside trading session. Skipping new entry.")
                            signal = None

                        buy_lot = get_entry_lot(symbol, "buy", signal_strength) if signal == 'buy' else None
                        sell_lot = get_entry_lot(symbol, "sell", signal_strength) if signal == 'sell' else None

                        if signal == 'buy' and buy_lot is not None:
                            print(f"BUY signal detected for {symbol}. Executing order...")
                            result = execute_buy_order(symbol, buy_lot, settings)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                last_signal_candle[symbol] = signal_bar_time
                                msg = f"The Harvester: BUY opened on {symbol} at {current_price}"
                                print(msg)
                                send_telegram(msg)
                                play_success_ping()
                        elif signal == 'sell' and sell_lot is not None:
                            print(f"SELL signal detected for {symbol}. Executing order (short position)...")
                            result = execute_sell_order(symbol, sell_lot, settings)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                last_signal_candle[symbol] = signal_bar_time
                                msg = f"The Harvester: SELL opened on {symbol} at {current_price}"
                                print(msg)
                                send_telegram(msg)
                                play_success_ping()
                        
                        # Ensure SL/TP on existing positions
                        manage_positions(symbol, settings)
                    else:
                        print(f"Could not get data for {symbol}. Skipping this interval.")

            time.sleep(1) # Wait 1 second before next loop iteration
            handle_telegram_commands()

    except KeyboardInterrupt:
        print("\nMT5 Trading Bot stopped by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        traceback.print_exc()
    finally:
        shutdown_mt5()

if __name__ == "__main__":
    if "--close-extra-trades" in sys.argv:
        initialize_mt5()
        try:
            close_extra_positions()
        finally:
            shutdown_mt5()
    else:
        run_harvester()
