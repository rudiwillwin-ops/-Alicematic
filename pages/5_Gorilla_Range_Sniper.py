import streamlit as st
import asyncio
import pandas as pd
import numpy as np
import time
from datetime import datetime, time as dt_time, timezone
from metaapi_cloud_sdk import MetaApi

# --- CONFIGURATION ---
st.set_page_config(page_title="Gorilla Range Sniper Cloud", page_icon="🎯", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #05080f; }
    .stMetric { background-color: #0d1117; padding: 15px; border-radius: 10px; border: 1px solid #1f6feb; }
    .sniper-header {
        background: linear-gradient(90deg, #1f6feb, #58a6ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 0;
    }
    .status-active { color: #23d160; font-weight: bold; }
    .status-scanning { color: #58a6ff; font-weight: bold; }
    .status-shield { color: #f85149; font-weight: bold; }
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
    st.session_state.magic_number = 1001

# --- INDICATOR ENGINE (WILDER'S EQUIVALENT) ---
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

async def get_sniper_signal(connection, symbol, adx_threshold, bb_dev):
    try:
        m1_candles = await connection.get_candles(symbol, '1m', datetime.now(), 300)
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 300)
        if not m1_candles or not m5_candles: return None, 0, 0, 0
        
        df_m1 = pd.DataFrame(m1_candles)
        df_m5 = pd.DataFrame(m5_candles)
        
        # M5 ADX
        adx_series = adx_wilder(df_m5)
        adx = adx_series.iloc[-1]
        
        if adx >= adx_threshold:
            return "SHIELD", adx, 0, 0
            
        # M1 BB & RSI
        df_m1['rsi'] = rsi_wilder(df_m1['close'])
        df_m1['sma'] = df_m1['close'].rolling(20).mean()
        df_m1['std'] = df_m1['close'].rolling(20).std()
        df_m1['upper'] = df_m1['sma'] + (bb_dev * df_m1['std'])
        df_m1['lower'] = df_m1['sma'] - (bb_dev * df_m1['std'])
        
        m1 = df_m1.iloc[-1]
        p_m1 = df_m1.iloc[-2]
        
        # Signal Logic
        if (p_m1['close'] <= p_m1['lower'] or p_m1['rsi'] <= 30) and (m1['close'] > m1['lower'] and m1['rsi'] > 30):
            return "BUY", adx, m1['rsi'], m1['sma']
        elif (p_m1['close'] >= p_m1['upper'] or p_m1['rsi'] >= 70) and (m1['close'] < m1['upper'] and m1['rsi'] < 70):
            return "SELL", adx, m1['rsi'], m1['sma']
            
        return "SCANNING", adx, m1['rsi'], 0
    except Exception as e:
        return f"ERROR: {e}", 0, 0, 0

# --- METAAPI CLOUD HELPERS ---
async def get_account_data(token, account_id):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        info = await connection.get_account_information()
        deals = await connection.get_history_deals_by_time(datetime.combine(datetime.now().date(), dt_time.min).timestamp(), datetime.now().timestamp())
        pnl = sum(d['profit'] for d in deals if d.get('magic') == st.session_state.magic_number)
        return {**info, "daily_pnl": pnl}
    except: return None

async def execute_trade(token, account_id, symbol, direction, risk_pct, tp_price):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        acc_info = await connection.get_account_information()
        balance = acc_info['balance']
        
        # 1% Risk Volume calculation (Simplified)
        volume = round((balance * (risk_pct/100)) / 1000, 2)
        volume = max(0.01, min(0.50, volume))

        if direction == "BUY":
            return await connection.create_market_buy_order(symbol, volume, 0, tp_price, {"magic": st.session_state.magic_number, "comment": "Sniper Cloud"})
        else:
            return await connection.create_market_sell_order(symbol, volume, 0, tp_price, {"magic": st.session_state.magic_number, "comment": "Sniper Cloud"})
    except Exception as e: return {"error": str(e)}

# --- SIDEBAR ---
st.sidebar.title("🎯 Sniper Control")
default_token = "0357f707f15e8b4e76a6e5b4f4f4e5b4"
default_account = "309567916"
meta_token = st.sidebar.text_input("MetaApi Token", value=default_token, type="password")
meta_account_id = st.sidebar.text_input("MetaApi Account ID", value=default_account)

with st.sidebar.expander("⚙️ STRATEGY SETTINGS", expanded=True):
    adx_limit = st.slider("ADX Max Threshold", 10.0, 40.0, 18.5)
    bb_dev = st.slider("Bollinger Deviation", 1.5, 3.5, 2.5)
    risk_pct = st.slider("Risk Per Trade %", 0.1, 5.0, 1.0)
    universe = st.multiselect("Asset Universe", ["EURUSD", "GBPUSD", "GOLD", "BTCUSD", "ETHUSD"], default=["EURUSD", "GOLD", "BTCUSD"])

if st.sidebar.button("🚀 TOGGLE SNIPER", use_container_width=True, type="primary"):
    st.session_state.bot_active = not st.session_state.bot_active

# --- MAIN DASHBOARD ---
st.markdown('<p class="sniper-header">GORILLA RANGE SNIPER</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #8b949e;'>Regime-Specific Precision Scalping on Account {meta_account_id}</p>", unsafe_allow_html=True)

if meta_token and meta_account_id:
    acc_data = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_data: st.session_state.account_data = acc_data

c1, c2, c3 = st.columns(3)
c1.metric("Account Balance", f"${st.session_state.account_data['balance']:,.2f}")
c2.metric("Daily Sniper PnL", f"${st.session_state.account_data['daily_pnl']:,.2f}")
c3.metric("Bot Status", "🎯 ACTIVE" if st.session_state.bot_active else "⚪ STANDBY")

st.divider()

if st.session_state.bot_active:
    with st.status("Sniper scanning markets...", expanded=True) as status:
        api = MetaApi(meta_token)
        account = asyncio.run(api.metatrader_account_api.get_account(meta_account_id))
        connection = account.get_rpc_connection()
        asyncio.run(connection.connect())
        asyncio.run(connection.wait_synchronized())

        for symbol in universe:
            st.write(f"🔍 Analyzing {symbol}...")
            state, adx, rsi, tp = asyncio.run(get_sniper_signal(connection, symbol, adx_limit, bb_dev))
            
            if state == "BUY" or state == "SELL":
                st.write(f"🔥 **SIGNAL DETECTED: {state} {symbol}**")
                res = asyncio.run(execute_trade(meta_token, meta_account_id, symbol, state, risk_pct, tp))
                if "error" not in res:
                    st.session_state.trade_history.insert(0, f"✅ {datetime.now().strftime('%H:%M:%S')} - {state} {symbol} Executed")
            elif state == "SHIELD":
                st.write(f"🛡️ {symbol} Shield Active: ADX {adx:.1f}")
            else:
                st.write(f"📡 {symbol} Scanning... ADX:{adx:.1f} RSI:{rsi:.1f}")

        status.update(label="Scan Complete. Resting 15s...", state="complete")
    time.sleep(15)
    st.rerun()

st.subheader("📜 Execution Log")
if st.session_state.trade_history:
    for log in st.session_state.trade_history[:10]: st.write(log)
else: st.info("No trades executed yet.")
