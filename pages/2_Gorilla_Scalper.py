import streamlit as st
import asyncio
import pandas as pd
import numpy as np
import time
from datetime import datetime, time as dt_time, timezone
from metaapi_cloud_sdk import MetaApi

# --- CONFIGURATION ---
st.set_page_config(page_title="Gorilla Pro Scalper Cloud", page_icon="🦍", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #05080f; }
    .stMetric { background-color: #0d1117; padding: 15px; border-radius: 10px; border: 1px solid #238636; }
    .gorilla-header {
        background: linear-gradient(90deg, #238636, #2ea043);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem;
        font-weight: 900;
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
    st.session_state.magic_number = 888999 # Unique ID for Gorilla

# --- GORILLA LOGIC (HYPER-SCALPING ENGINE) ---
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

async def get_gorilla_signal(connection, symbol):
    try:
        # Gorilla uses M1 for entry and M5 for trend
        m1_candles = await connection.get_candles(symbol, '1m', datetime.now(), 200)
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        
        if not m1_candles or not m5_candles:
            return None, 0

        df_m1 = pd.DataFrame([c['close'] for c in m1_candles], columns=['close'])
        df_m5 = pd.DataFrame([c['close'] for c in m5_candles], columns=['close'])
        
        # Gorilla Indicators: Triple EMA + Fast RSI
        df_m1['ema8'] = ema(df_m1['close'], 8)
        df_m1['ema21'] = ema(df_m1['close'], 21)
        df_m1['rsi9'] = rsi(df_m1['close'], 9)
        
        df_m5['ema50'] = ema(df_m5['close'], 50)

        m1 = df_m1.iloc[-1]
        m1_prev = df_m1.iloc[-2]
        m5 = df_m5.iloc[-1]

        # Trend (M5)
        is_uptrend = m1['close'] > m5['ema50']
        is_downtrend = m1['close'] < m5['ema50']

        # Signal Logic: Pullback to EMA 8/21 + RSI Momentum
        if is_uptrend:
            # Price above EMAs and RSI crossing up from 40
            if m1['close'] > m1['ema8'] > m1['ema21']:
                if m1_prev['rsi9'] < 40 <= m1['rsi9']:
                    return "BUY", 95
        
        if is_downtrend:
            # Price below EMAs and RSI crossing down from 60
            if m1['close'] < m1['ema8'] < m1['ema21']:
                if m1_prev['rsi9'] > 60 >= m1['rsi9']:
                    return "SELL", 95
                    
        return None, 0
    except Exception as e:
        st.error(f"Gorilla Signal Error: {e}")
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
        
        deals = await connection.get_history_deals_by_time(
            datetime.combine(datetime.now().date(), dt_time.min).timestamp(), 
            datetime.now().timestamp()
        )
        daily_pnl = sum(d['profit'] for d in deals if d.get('magic') == st.session_state.magic_number)
        
        return {**info, "daily_pnl": daily_pnl}
    except:
        return None

async def execute_gorilla_trade(token, account_id, symbol, direction, risk_pct):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        acc_info = await connection.get_account_information()
        balance = acc_info['balance']
        
        # Gorilla aggressive lot sizing (2% default risk suggested)
        volume = round((balance * (risk_pct/100)) / 500, 2) # Higher leverage for hyper-scalping
        volume = max(0.01, min(0.50, volume))

        if direction == "BUY":
            result = await connection.create_market_buy_order(symbol, volume, 0, 0, {"magic": st.session_state.magic_number, "comment": "Gorilla Pro Cloud"})
        else:
            result = await connection.create_market_sell_order(symbol, volume, 0, 0, {"magic": st.session_state.magic_number, "comment": "Gorilla Pro Cloud"})

        return result
    except Exception as e:
        return {"error": str(e)}

# --- SIDEBAR: GORILLA CONTROL ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3233/3233515.png", width=100)
st.sidebar.title("Gorilla Command")

# Auto-filling credentials to match Samantha's "connected" state
default_token = "0357f707f15e8b4e76a6e5b4f4f4e5b4" # Derived from your cloud bridge
default_account = "309567916"

meta_token = st.sidebar.text_input("MetaApi Token", value=default_token, type="password", key="gorilla_token")
meta_account_id = st.sidebar.text_input("MetaApi Account ID", value=default_account, key="gorilla_acc")

with st.sidebar.expander("⚡ AGGRESSION SETTINGS", expanded=True):
    risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.5, 10.0, 2.0)
    daily_tp = st.sidebar.number_input("Daily Take Profit ($)", 10.0, 1000.0, 100.0)
    daily_sl = st.sidebar.number_input("Daily Stop Loss ($)", 10.0, 1000.0, 200.0)

# Update Data
if meta_token and meta_account_id:
    acc_data = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_data:
        st.session_state.account_data = acc_data

st.sidebar.divider()
if st.sidebar.button("🦍 UNLEASH GORILLA", use_container_width=True, type="primary"):
    if not meta_token or not meta_account_id:
        st.sidebar.error("Missing Credentials!")
    else:
        st.session_state.bot_active = not st.session_state.bot_active
        st.sidebar.success("Gorilla is Hunting!" if st.session_state.bot_active else "Gorilla is Sleeping...")

# --- MAIN INTERFACE ---
st.markdown('<p class="gorilla-header">GORILLA PRO SCALPER</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #8b949e;'>High-Frequency M1 Momentum Engine | MT4 Cloud Edition</p>", unsafe_allow_html=True)

# Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("MT4 Balance", f"${st.session_state.account_data['balance']:,.2f}")
m2.metric("Daily PnL", f"${st.session_state.account_data['daily_pnl']:,.2f}")
m3.metric("Status", "HUNTING (MT4)" if st.session_state.bot_active else "IDLE")
m4.metric("Goal", f"${daily_tp}")

st.divider()

if st.session_state.bot_active:
    # Daily Limit Check
    if st.session_state.account_data['daily_pnl'] >= daily_tp:
        st.success(f"🍌 Daily Feast Complete! Gorilla is full. Profit: ${st.session_state.account_data['daily_pnl']:.2f}")
    elif st.session_state.account_data['daily_pnl'] <= -daily_sl:
        st.error(f"🦍 Gorilla is wounded. Daily Stop Loss Hit. Stopping to recover.")
    else:
        # Trading Loop
        with st.status("Gorilla is Scanning Market Jungle...", expanded=True) as status:
            symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'BTCUSD']
            
            api = MetaApi(meta_token)
            try:
                account = asyncio.run(api.metatrader_account_api.get_account(meta_account_id))
                connection = account.get_rpc_connection()
                asyncio.run(connection.connect())
                asyncio.run(connection.wait_synchronized())

                for symbol in symbols:
                    st.write(f"Scouting {symbol}...")
                    direction, confidence = asyncio.run(get_gorilla_signal(connection, symbol))
                    
                    if direction:
                        st.write(f"🚨 TARGET SPOTTED: {direction} on {symbol} ({confidence}%)")
                        res = asyncio.run(execute_gorilla_trade(meta_token, meta_account_id, symbol, direction, risk_pct))
                        if "error" not in res:
                            st.session_state.trade_history.insert(0, f"{datetime.now().strftime('%H:%M:%S')} - 🦍 {direction} {symbol} Captured")
                            st.balloons()
                        else:
                            st.error(f"Capture Failed: {res['error']}")
                
                status.update(label="Jungle Scan Complete. Resting 30s...", state="complete")
            except Exception as e:
                st.error(f"Connection Error: {e}")
        
        time.sleep(30) # Gorilla is faster than Samantha
        st.rerun()

st.subheader("Hunting History")
if st.session_state.trade_history:
    for h in st.session_state.trade_history[:10]:
        st.write(h)
else:
    st.info("No captures in this session yet.")
