import streamlit as st
import asyncio
import pandas as pd
import numpy as np
import time
from datetime import datetime, time as dt_time, timezone
from metaapi_cloud_sdk import MetaApi

# --- CONFIGURATION ---
st.set_page_config(page_title="Samantha Cloud Pro", page_icon="💃", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #0b0f19; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .samantha-header {
        background: linear-gradient(90deg, #ff0080, #7928ca);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0;
    }
    .status-active { color: #23d160; font-weight: bold; }
    .status-inactive { color: #ff3860; font-weight: bold; }
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
    st.session_state.magic_number = 20260507

# --- SAMANTHA LOGIC (SCALPING ENGINE) ---
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

async def get_samantha_signal(connection, symbol):
    try:
        # Fetch M5 and M15 data
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        m15_candles = await connection.get_candles(symbol, '15m', datetime.now(), 200)
        
        if not m5_candles or not m15_candles:
            return None, 0

        df_m5 = pd.DataFrame([c['close'] for c in m5_candles], columns=['close'])
        df_m15 = pd.DataFrame([c['close'] for c in m15_candles], columns=['close'])
        
        # Calculate Indicators
        df_m5['ema50'] = ema(df_m5['close'], 50)
        df_m5['ema200'] = ema(df_m5['close'], 200)
        df_m5['rsi'] = rsi(df_m5['close'], 14)
        
        df_m15['ema50'] = ema(df_m15['close'], 50)
        df_m15['ema200'] = ema(df_m15['close'], 200)

        m5 = df_m5.iloc[-1]
        m5_prev = df_m5.iloc[-2]
        m15 = df_m15.iloc[-1]

        # Trend Confirmation (M15)
        m15_uptrend = m15['close'] > m15['ema50'] > m15['ema200']
        m15_downtrend = m15['close'] < m15['ema50'] < m15['ema200']

        # Signal Logic
        if m15_uptrend:
            if m5['close'] > m5['ema50'] > m5['ema200']:
                if m5_prev['rsi'] < 50 <= m5['rsi']:
                    return "BUY", 90
        
        if m15_downtrend:
            if m5['close'] < m5['ema50'] < m5['ema200']:
                if m5_prev['rsi'] > 50 >= m5['rsi']:
                    return "SELL", 90
                    
        return None, 0
    except Exception as e:
        st.error(f"Signal Error: {e}")
        return None, 0

# --- MT5 CLOUD EXECUTION (METAAPI) ---
async def get_account_data(token, account_id):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        info = await connection.get_account_information()
        
        # Calculate daily PnL (Simplified for Cloud)
        deals = await connection.get_history_deals_by_time(datetime.combine(datetime.now().date(), dt_time.min).timestamp(), datetime.now().timestamp())
        daily_pnl = sum(d['profit'] for d in deals if d.get('magic') == st.session_state.magic_number)
        
        return {**info, "daily_pnl": daily_pnl}
    except:
        return None

async def execute_samantha_trade(token, account_id, symbol, direction, risk_pct):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        acc_info = await connection.get_account_information()
        balance = acc_info['balance']
        
        # Samantha Lot Sizing (1% default)
        volume = round((balance * (risk_pct/100)) / 1000, 2) # Simplified for cloud scalability
        volume = max(0.01, volume)

        if direction == "BUY":
            result = await connection.create_market_buy_order(symbol, volume, 0, 0, {"magic": st.session_state.magic_number, "comment": "Samantha Cloud"})
        else:
            result = await connection.create_market_sell_order(symbol, volume, 0, 0, {"magic": st.session_state.magic_number, "comment": "Samantha Cloud"})

        return result
    except Exception as e:
        return {"error": str(e)}

# --- SIDEBAR: SETTINGS ---
st.sidebar.title("Samantha Cloud Control")

meta_token = st.sidebar.text_input("MetaApi Token", type="password")
meta_account_id = st.sidebar.text_input("MetaApi Account ID")

with st.sidebar.expander("⚙️ STRATEGY SETTINGS", expanded=True):
    risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.1, 5.0, 1.0)
    daily_tp = st.sidebar.number_input("Daily Take Profit ($)", 5.0, 500.0, 50.0)
    daily_sl = st.sidebar.number_input("Daily Stop Loss ($)", 5.0, 500.0, 100.0)

# Update data
if meta_token and meta_account_id:
    acc_data = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_data:
        st.session_state.account_data = acc_data

st.sidebar.divider()
if st.sidebar.button("🚀 DEPLOY TO CLOUD", use_container_width=True, type="primary"):
    if not meta_token or not meta_account_id:
        st.sidebar.error("Missing Credentials!")
    else:
        st.session_state.bot_active = not st.session_state.bot_active
        st.sidebar.success("Samantha Cloud Engaged!" if st.session_state.bot_active else "Bot Hibernating...")

# --- MAIN INTERFACE ---
st.markdown('<p class="samantha-header">SAMANTHA CLOUD PRO</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #8b949e;'>PC-Independent Scalping | Momentum Engine</p>", unsafe_allow_html=True)

# Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Balance", f"${st.session_state.account_data['balance']:,.2f}")
m2.metric("Daily PnL", f"${st.session_state.account_data['daily_pnl']:,.2f}")
m3.metric("Status", "LIVE" if st.session_state.bot_active else "IDLE")
m4.metric("Goal", f"${daily_tp}")

st.divider()

if st.session_state.bot_active:
    # Daily Limit Check
    if st.session_state.account_data['daily_pnl'] >= daily_tp:
        st.success(f"🏆 Daily Target Reached! Samantha is resting. Profit: ${st.session_state.account_data['daily_pnl']:.2f}")
    elif st.session_state.account_data['daily_pnl'] <= -daily_sl:
        st.error(f"🛑 Daily Stop Loss Hit. Samantha is protecting your capital.")
    else:
        # Trading Loop
        with st.status("Samantha is Scanning Markets...", expanded=True) as status:
            symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'BTCUSD']
            
            api = MetaApi(meta_token)
            account = asyncio.run(api.metatrader_account_api.get_account(meta_account_id))
            connection = account.get_rpc_connection()
            asyncio.run(connection.connect())
            asyncio.run(connection.wait_synchronized())

            for symbol in symbols:
                st.write(f"Analyzing {symbol}...")
                direction, confidence = asyncio.run(get_samantha_signal(connection, symbol))
                
                if direction:
                    st.write(f"🔥 SIGNAL: {direction} on {symbol} ({confidence}%)")
                    res = asyncio.run(execute_samantha_trade(meta_token, meta_account_id, symbol, direction, risk_pct))
                    if "error" not in res:
                        st.session_state.trade_history.insert(0, f"{datetime.now().strftime('%H:%M:%S')} - {direction} {symbol} Executed")
                        st.balloons()
                    else:
                        st.error(f"Trade Failed: {res['error']}")
            
            status.update(label="Scan Complete. Waiting 60s...", state="complete")
        
        time.sleep(60)
        st.rerun()

st.subheader("Recent Activity")
if st.session_state.trade_history:
    for h in st.session_state.trade_history[:10]:
        st.write(h)
else:
    st.info("No trades executed on cloud session yet.")
