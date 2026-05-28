import streamlit as st
import asyncio
import pandas as pd
import numpy as np
import time
from datetime import datetime, time as dt_time
from metaapi_cloud_sdk import MetaApi

# --- CONFIGURATION ---
st.set_page_config(page_title="Ingrid Momentum Pro", page_icon="⚡", layout="wide")

# --- CUSTOM CSS (Ingrid's Purple Theme) ---
st.markdown("""
    <style>
    .main { background-color: #0d0221; }
    .stMetric { background-color: #1b065e; padding: 15px; border-radius: 10px; border: 1px solid #7a00ff; }
    .ingrid-header {
        background: linear-gradient(90deg, #7a00ff, #ff007a);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE STATE ---
if "bot_active" not in st.session_state:
    st.session_state.bot_active = False
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "account_data" not in st.session_state:
    st.session_state.account_data = {"balance": 0.0, "equity": 0.0, "daily_pnl": 0.0}
if "magic_number" not in st.session_state:
    st.session_state.magic_number = 777111 # Ingrid's Unique Magic Number

# --- INGRID LOGIC (GORILLA REPLICA) ---
def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def rsi(series, length=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

async def get_ingrid_signal(connection, symbol):
    try:
        m1_candles = await connection.get_candles(symbol, '1m', datetime.now(), 200)
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        
        if not m1_candles or not m5_candles:
            return None, 0

        df1 = pd.DataFrame(m1_candles)
        df5 = pd.DataFrame(m5_candles)
        
        # Triple EMA + Fast RSI (Gorilla Spec)
        df1['ema8'] = ema(df1['close'], 8)
        df1['ema21'] = ema(df1['close'], 21)
        df5['ema50'] = ema(df5['close'], 50)
        df1['rsi9'] = rsi(df1['close'], 9)

        m1 = df1.iloc[-1]
        m1_prev = df1.iloc[-2]
        m5 = df5.iloc[-1]

        # Trend (M5)
        is_trend_up = m1['close'] > m5['ema50']
        is_trend_down = m1['close'] < m5['ema50']

        # BUY: Trend UP + EMAs Stacked + RSI Snap-back from 40
        if is_trend_up and m1['close'] > m1['ema8'] > m1['ema21']:
            if m1_prev['rsi9'] < 40 <= m1['rsi9']:
                return "BUY", 95

        # SELL: Trend DOWN + EMAs Stacked + RSI Snap-back from 60
        if is_trend_down and m1['close'] < m1['ema8'] < m1['ema21']:
            if m1_prev['rsi9'] > 60 >= m1['rsi9']:
                return "SELL", 95
            
        return None, 0
    except Exception as e:
        st.error(f"Ingrid Logic Error: {e}")
        return None, 0

# --- MT4 CLOUD EXECUTION ---
async def get_account_data(token, account_id):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        info = await connection.get_account_information()
        deals = await connection.get_history_deals_by_time(datetime.combine(datetime.now().date(), dt_time.min).timestamp(), datetime.now().timestamp())
        daily_pnl = sum(d['profit'] for d in deals if d.get('magic') == st.session_state.magic_number)
        return {**info, "daily_pnl": daily_pnl}
    except:
        return None

async def execute_ingrid_trade(token, account_id, symbol, direction, risk_pct, sl_pips, tp_pips):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        acc_info = await connection.get_account_information()
        symbol_info = await connection.get_symbol_specification(symbol)
        
        balance = acc_info['balance']
        point = symbol_info['pipSize'] # Standard Pip Size
        
        # Gorilla Risk Math (Divisor 500)
        volume = round((balance * (risk_pct/100)) / 500, 2) 
        volume = max(0.01, min(0.50, volume))

        # Hard SL/TP Calculation
        price = (await connection.get_symbol_price(symbol))['ask' if direction == "BUY" else 'bid']
        sl = price - (sl_pips * point) if direction == "BUY" else price + (sl_pips * point)
        tp = price + (tp_pips * point) if direction == "BUY" else price - (tp_pips * point)

        if direction == "BUY":
            result = await connection.create_market_buy_order(symbol, volume, sl, tp, {"magic": st.session_state.magic_number, "comment": "Ingrid Pro (Gorilla Replica)"})
        else:
            result = await connection.create_market_sell_order(symbol, volume, sl, tp, {"magic": st.session_state.magic_number, "comment": "Ingrid Pro (Gorilla Replica)"})

        return result
    except Exception as e:
        return {"error": str(e)}

# --- SIDEBAR: INGRID CONTROL ---
st.sidebar.title("Ingrid Terminal")
default_token = "0357f707f15e8b4e76a6e5b4f4f4e5b4"
default_account = "309567916"

meta_token = st.sidebar.text_input("MetaApi Token", value=default_token, type="password")
meta_account_id = st.sidebar.text_input("Account ID", value=default_account)

with st.sidebar.expander("🛡️ GORILLA-GRADE SAFEGUARDS", expanded=True):
    risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.5, 5.0, 2.0)
    daily_tp = st.sidebar.number_input("Daily Profit Target ($)", 10.0, 1000.0, 100.0)
    daily_sl = st.sidebar.number_input("Daily Stop Loss ($)", 10.0, 1000.0, 200.0)
    max_spread = st.sidebar.slider("Max Spread (Pips)", 1.0, 10.0, 3.0)
    sl_pips = st.sidebar.number_input("Stop Loss (Pips)", 5, 100, 15)
    tp_pips = st.sidebar.number_input("Take Profit (Pips)", 5, 200, 30)
    use_velocity = st.sidebar.toggle("Velocity Filter", value=True)
    use_governor = st.sidebar.toggle("Trend Governor (H1)", value=True)

if meta_token and meta_account_id:
    acc_data = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_data: st.session_state.account_data = acc_data

if st.sidebar.button("🚀 ACTIVATE INGRID PRO", use_container_width=True, type="primary"):
    st.session_state.bot_active = not st.session_state.bot_active

# --- MAIN INTERFACE ---
st.markdown('<p class="ingrid-header">INGRID PRO SCALPER</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #8b949e;'>Triple EMA + RSI 9 | Gorilla-Grade Replica | Cloud Edition</p>", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Balance", f"${st.session_state.account_data['balance']:,.2f}")
m2.metric("Daily PnL", f"${st.session_state.account_data['daily_pnl']:,.2f}")
m3.metric("Status", "HUNTING" if st.session_state.bot_active else "IDLE")
m4.metric("Circuit Breaker", f"-${daily_sl}")

st.divider()

if st.session_state.bot_active:
    # 1. CIRCUIT BREAKER CHECK
    if st.session_state.account_data['daily_pnl'] >= daily_tp:
        st.success(f"🍌 Daily Feast Complete! Ingrid has secured ${st.session_state.account_data['daily_pnl']:.2f}.")
        st.session_state.bot_active = False
        st.stop()
    
    if st.session_state.account_data['daily_pnl'] <= -daily_sl:
        st.error(f"🚨 CIRCUIT BREAKER: Daily Stop Loss reached. Stopping to recover.")
        st.session_state.bot_active = False
        st.stop()

    with st.status("Ingrid is Scanning Market Jungle...", expanded=True) as status:
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']
        
        api = MetaApi(meta_token)
        account = asyncio.run(api.metatrader_account_api.get_account(meta_account_id))
        connection = account.get_rpc_connection()
        asyncio.run(connection.connect())
        asyncio.run(connection.wait_synchronized())

        # Check existing positions to prevent stacking
        positions = await connection.get_positions()
        active_symbols = [p['symbol'] for p in positions if p.get('magic') == st.session_state.magic_number]

        for symbol in symbols:
            if symbol in active_symbols:
                st.write(f"Skipping {symbol}: Position already open.")
                continue

            st.write(f"Scouting {symbol}...")
            
            # Spread Filter
            price_info = await connection.get_symbol_price(symbol)
            spread = (price_info['ask'] - price_info['bid']) / (await connection.get_symbol_specification(symbol))['pipSize']
            if spread > max_spread:
                st.warning(f"  ∟ Spread: {spread:.1f} pips exceeds limit. Skipping.")
                continue

            # Trend Governor (H1 Alignment)
            if use_governor:
                h1_candles = await connection.get_candles(symbol, '1h', datetime.now(), 2)
                if h1_candles:
                    h1_trend = "BUY" if h1_candles[-1]['close'] > h1_candles[-1]['open'] else "SELL"
                    st.write(f"  ∟ Governor: H1 Trend is {h1_trend}")
                else:
                    h1_trend = "UNKNOWN"

            # Velocity Filter (Volatility Spike Protection)
            if use_velocity:
                m1_v = await connection.get_candles(symbol, '1m', datetime.now(), 5)
                v_range = abs(m1_v[-1]['high'] - m1_v[-1]['low'])
                avg_v = sum(abs(c['high'] - c['low']) for c in m1_v[:-1]) / 4
                if v_range > (avg_v * 3):
                    st.warning(f"  ∟ Velocity: High volatility detected. Skipping.")
                    continue

            direction, conf = await get_ingrid_signal(connection, symbol)
            
            if direction:
                # Governor Check
                if use_governor and direction != h1_trend:
                    st.info(f"  ∟ Trade Blocked: {direction} against H1 Trend.")
                    continue

                st.write(f"🚨 TARGET SPOTTED: {direction} on {symbol} ({conf}%)")
                res = await execute_ingrid_trade(meta_token, meta_account_id, symbol, direction, risk_pct, sl_pips, tp_pips)
                if "error" not in res:
                    st.session_state.trade_history.insert(0, f"{datetime.now().strftime('%H:%M:%S')} - 🎯 {direction} {symbol} Captured")
                    st.balloons()
                else:
                    st.error(f"Capture Failed: {res['error']}")
        
        status.update(label="Jungle Scan Complete. Resting 30s...", state="complete")
    
    time.sleep(30)
    st.rerun()

st.subheader("Recent Ingrid Activity")
for h in st.session_state.trade_history[:10]: st.write(h)
