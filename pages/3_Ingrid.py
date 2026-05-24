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

# --- INGRID LOGIC (STRICT SPECIFICATION) ---
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
        m1_candles = await connection.get_candles(symbol, '1m', datetime.now(), 100)
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 100)
        
        if not m1_candles or not m5_candles:
            return None, 0

        df1 = pd.DataFrame(m1_candles)
        df5 = pd.DataFrame(m5_candles)
        
        # 1. The Core Indicators (The "Senses")
        # Triple EMA: 8, 21 (on M1) and 50 (on M5)
        df1['ema8'] = ema(df1['close'], 8)
        df1['ema21'] = ema(df1['close'], 21)
        df5['ema50'] = ema(df5['close'], 50)
        
        # Fast RSI: Period 9 (on M1)
        df1['rsi9'] = rsi(df1['close'], 9)

        m1 = df1.iloc[-1]
        m1_prev = df1.iloc[-2]
        m5 = df5.iloc[-1]

        # 2. The Entry Logic (The "Strike")
        
        # BUY Conditions:
        # 1. M5 Trend UP (Price > EMA 50)
        is_trend_up = m1['close'] > m5['ema50']
        # 2. Pullback toward EMA 8/21 area
        is_pullback_buy = m1['low'] <= max(m1['ema8'], m1['ema21'])
        # 3. Trigger: RSI (9) cross back UP from 40
        rsi_trigger_buy = m1_prev['rsi9'] < 40 <= m1['rsi9']

        if is_trend_up and is_pullback_buy and rsi_trigger_buy:
            return "BUY", 100

        # SELL Conditions:
        # 1. M5 Trend DOWN (Price < EMA 50)
        is_trend_down = m1['close'] < m5['ema50']
        # 2. Rally toward EMA 8/21 area
        is_pullback_sell = m1['high'] >= min(m1['ema8'], m1['ema21'])
        # 3. Trigger: RSI (9) cross back DOWN from 60
        rsi_trigger_sell = m1_prev['rsi9'] > 60 >= m1['rsi9']

        if is_trend_down and is_pullback_sell and rsi_trigger_sell:
            return "SELL", 100
            
        return None, 0
    except Exception as e:
        st.error(f"Ingrid Error: {e}")
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

async def execute_ingrid_trade(token, account_id, symbol, direction, risk_pct):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        acc_info = await connection.get_account_information()
        balance = acc_info['balance']
        
        # Risk Management: 2:1 RR Aggression
        volume = round((balance * (risk_pct/100)) / 400, 2) 
        volume = max(0.01, min(0.50, volume))

        if direction == "BUY":
            result = await connection.create_market_buy_order(symbol, volume, 0, 0, {"magic": st.session_state.magic_number, "comment": "Ingrid Momentum"})
        else:
            result = await connection.create_market_sell_order(symbol, volume, 0, 0, {"magic": st.session_state.magic_number, "comment": "Ingrid Momentum"})

        return result
    except Exception as e:
        return {"error": str(e)}

# --- SIDEBAR: INGRID CONTROL ---
st.sidebar.title("Ingrid Terminal")
default_token = "0357f707f15e8b4e76a6e5b4f4f4e5b4"
default_account = "309567916"

meta_token = st.sidebar.text_input("MetaApi Token", value=default_token, type="password")
meta_account_id = st.sidebar.text_input("Account ID", value=default_account)

risk_pct = st.sidebar.slider("Ingrid Risk (%)", 0.5, 5.0, 2.0)
daily_tp = st.sidebar.number_input("Target Profit ($)", 10.0, 500.0, 50.0)

if meta_token and meta_account_id:
    acc_data = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_data: st.session_state.account_data = acc_data

if st.sidebar.button("🚀 ACTIVATE INGRID", use_container_width=True, type="primary"):
    st.session_state.bot_active = not st.session_state.bot_active

# --- MAIN INTERFACE ---
st.markdown('<p class="ingrid-header">INGRID MOMENTUM</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #8b949e;'>Triple EMA + RSI 9 | M1 Execution</p>", unsafe_allow_html=True)

m1, m2, m3 = st.columns(3)
m1.metric("Balance", f"${st.session_state.account_data['balance']:,.2f}")
m2.metric("Ingrid PnL", f"${st.session_state.account_data['daily_pnl']:,.2f}")
m3.metric("Status", "ACTIVE" if st.session_state.bot_active else "IDLE")

st.divider()

if st.session_state.bot_active:
    with st.status("Ingrid is Scouting...", expanded=True) as status:
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']
        
        api = MetaApi(meta_token)
        account = asyncio.run(api.metatrader_account_api.get_account(meta_account_id))
        connection = account.get_rpc_connection()
        asyncio.run(connection.connect())
        asyncio.run(connection.wait_synchronized())

        for symbol in symbols:
            st.write(f"Analyzing {symbol}...")
            direction, conf = asyncio.run(get_ingrid_signal(connection, symbol))
            
            if direction:
                st.write(f"🎯 INGRID SIGNAL: {direction} {symbol}")
                res = asyncio.run(execute_ingrid_trade(meta_token, meta_account_id, symbol, direction, risk_pct))
                if "error" not in res:
                    st.session_state.trade_history.insert(0, f"{datetime.now().strftime('%H:%M:%S')} - Ingrid: {direction} {symbol}")
                    st.balloons()
        
        status.update(label="Scout Complete. Resting 30s...", state="complete")
    
    time.sleep(30)
    st.rerun()

st.subheader("Recent Ingrid Activity")
for h in st.session_state.trade_history[:10]: st.write(h)
