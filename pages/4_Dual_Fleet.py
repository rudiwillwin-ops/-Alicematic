import streamlit as st
import asyncio
import pandas as pd
import numpy as np
import time
from datetime import datetime, time as dt_time
from metaapi_cloud_sdk import MetaApi

# --- CONFIGURATION ---
st.set_page_config(page_title="Triple Fleet Command", page_icon="🚢", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #0b0f19; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .dual-header {
        background: linear-gradient(90deg, #00d2ff, #3a7bd5, #ff0080);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0;
    }
    .bot-card {
        padding: 15px;
        border-radius: 10px;
        background: #1c2128;
        border: 1px solid #30363d;
        margin-bottom: 10px;
    }
    .samantha-accent { border-left: 5px solid #ff0080; }
    .gorilla-accent { border-left: 5px solid #238636; }
    .sniper-accent { border-left: 5px solid #1f6feb; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE STATE ---
if "fleet_active" not in st.session_state:
    st.session_state.fleet_active = False 
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "account_data" not in st.session_state:
    st.session_state.account_data = {"balance": 0.0, "equity": 0.0, "daily_pnl": 0.0}

# Magic Numbers
MAGIC_SAMANTHA = 20260507
MAGIC_GORILLA = 888999
MAGIC_SNIPER = 1001

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

# --- BOT LOGIC: SAMANTHA ---
async def get_samantha_signal(connection, symbol):
    try:
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        m15_candles = await connection.get_candles(symbol, '15m', datetime.now(), 200)
        if not m5_candles or not m15_candles: return None, 0
        df_m5 = pd.DataFrame([c['close'] for c in m5_candles], columns=['close'])
        df_m15 = pd.DataFrame([c['close'] for c in m15_candles], columns=['close'])
        df_m5['ema50'] = ema(df_m5['close'], 50)
        df_m5['ema200'] = ema(df_m5['close'], 200)
        df_m5['rsi'] = rsi_wilder(df_m5['close'], 14)
        df_m15['ema50'] = ema(df_m15['close'], 50)
        df_m15['ema200'] = ema(df_m15['close'], 200)
        m5, m5_prev, m15 = df_m5.iloc[-1], df_m5.iloc[-2], df_m15.iloc[-1]
        if m15['close'] > m15['ema50'] > m15['ema200'] and m5['close'] > m5['ema50'] > m5['ema200'] and m5_prev['rsi'] < 50 <= m5['rsi']:
            return "BUY", 90
        if m15['close'] < m15['ema50'] < m15['ema200'] and m5['close'] < m5['ema50'] < m5['ema200'] and m5_prev['rsi'] > 50 >= m5['rsi']:
            return "SELL", 90
        return None, 0
    except: return None, 0

# --- BOT LOGIC: GORILLA PRO ---
async def get_gorilla_signal(connection, symbol):
    try:
        m1_candles = await connection.get_candles(symbol, '1m', datetime.now(), 200)
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 200)
        if not m1_candles or not m5_candles: return None, 0
        df_m1 = pd.DataFrame([c['close'] for c in m1_candles], columns=['close'])
        df_m5 = pd.DataFrame([c['close'] for c in m5_candles], columns=['close'])
        df_m1['ema8'] = ema(df_m1['close'], 8)
        df_m1['ema21'] = ema(df_m1['close'], 21)
        df_m1['rsi9'] = rsi_wilder(df_m1['close'], 9)
        df_m5['ema50'] = ema(df_m5['close'], 50)
        m1, m1_prev, m5 = df_m1.iloc[-1], df_m1.iloc[-2], df_m5.iloc[-1]
        if m1['close'] > m5['ema50'] and m1['close'] > m1['ema8'] > m1['ema21'] and m1_prev['rsi9'] < 40 <= m1['rsi9']:
            return "BUY", 95
        if m1['close'] < m5['ema50'] and m1['close'] < m1['ema8'] < m1['ema21'] and m1_prev['rsi9'] > 60 >= m1['rsi9']:
            return "SELL", 95
        return None, 0
    except: return None, 0

# --- BOT LOGIC: RANGE SNIPER ---
async def get_sniper_signal(connection, symbol, adx_threshold, bb_dev):
    try:
        m1_candles = await connection.get_candles(symbol, '1m', datetime.now(), 300)
        m5_candles = await connection.get_candles(symbol, '5m', datetime.now(), 300)
        if not m1_candles or not m5_candles: return None, 0
        df_m1 = pd.DataFrame(m1_candles)
        df_m5 = pd.DataFrame(m5_candles)
        adx = adx_wilder(df_m5).iloc[-1]
        if adx >= adx_threshold: return None, 0
        df_m1['rsi'] = rsi_wilder(df_m1['close'])
        df_m1['sma'] = df_m1['close'].rolling(20).mean()
        df_m1['std'] = df_m1['close'].rolling(20).std()
        df_m1['up'] = df_m1['sma'] + (bb_dev * df_m1['std'])
        df_m1['low'] = df_m1['sma'] - (bb_dev * df_m1['std'])
        m1, p_m1 = df_m1.iloc[-1], df_m1.iloc[-2]
        if (p_m1['close'] <= p_m1['low'] or p_m1['rsi'] <= 30) and (m1['close'] > m1['low'] and m1['rsi'] > 30):
            return "BUY", m1['sma']
        elif (p_m1['close'] >= p_m1['up'] or p_m1['rsi'] >= 70) and (m1['close'] < m1['up'] and m1['rsi'] < 70):
            return "SELL", m1['sma']
        return None, 0
    except: return None, 0

# --- MT5 EXECUTION ---
async def get_account_data(token, account_id):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        info = await connection.get_account_information()
        deals = await connection.get_history_deals_by_time(datetime.combine(datetime.now().date(), dt_time.min).timestamp(), datetime.now().timestamp())
        pnl_s = sum(d['profit'] for d in deals if d.get('magic') == MAGIC_SAMANTHA)
        pnl_g = sum(d['profit'] for d in deals if d.get('magic') == MAGIC_GORILLA)
        pnl_n = sum(d['profit'] for d in deals if d.get('magic') == MAGIC_SNIPER)
        return {**info, "pnl_s": pnl_s, "pnl_g": pnl_g, "pnl_n": pnl_n, "daily_pnl": pnl_s + pnl_g + pnl_n}
    except: return None

async def execute_trade(token, account_id, symbol, direction, risk_pct, magic, comment, tp=0):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        acc_info = await connection.get_account_information()
        balance = acc_info['balance']
        divisor = 1000 if magic == MAGIC_SAMANTHA else 500
        volume = max(0.01, min(0.50, round((balance * (risk_pct/100)) / divisor, 2)))
        if direction == "BUY": return await connection.create_market_buy_order(symbol, volume, 0, tp, {"magic": magic, "comment": comment})
        else: return await connection.create_market_sell_order(symbol, volume, 0, tp, {"magic": magic, "comment": comment})
    except Exception as e: return {"error": str(e)}

# --- SIDEBAR: CONTROL ---
st.sidebar.title("Fleet Commander")
default_token = "0357f707f15e8b4e76a6e5b4f4f4e5b4"
default_account = "309567916"
meta_token = st.sidebar.text_input("MetaApi Token", value=default_token, type="password")
meta_account_id = st.sidebar.text_input("MetaApi Account ID", value=default_account)

with st.sidebar.expander("💃 SAMANTHA SETTINGS", expanded=False):
    sam_enabled = st.checkbox("Enable Samantha", value=True)
    sam_risk = st.slider("Samantha Risk %", 0.1, 5.0, 1.0)
with st.sidebar.expander("🦍 GORILLA PRO SETTINGS", expanded=False):
    gor_enabled = st.checkbox("Enable Gorilla", value=True)
    gor_risk = st.slider("Gorilla Risk %", 0.1, 10.0, 2.0)
with st.sidebar.expander("🎯 SNIPER SETTINGS", expanded=True):
    sni_enabled = st.checkbox("Enable Sniper", value=True)
    sni_risk = st.slider("Sniper Risk %", 0.1, 5.0, 1.0)
    sni_adx = st.slider("Sniper ADX limit", 10.0, 30.0, 18.5)

if meta_token and meta_account_id:
    acc_data = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_data: st.session_state.account_data = acc_data

st.sidebar.divider()
if st.sidebar.button("🚀 LAUNCH FLEET", use_container_width=True, type="primary"):
    st.session_state.fleet_active = not st.session_state.fleet_active

# --- MAIN INTERFACE ---
st.markdown('<p class="dual-header">TRIPLE FLEET COMMAND</p>', unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #8b949e;'>Samantha, Gorilla & Range Sniper on Account {meta_account_id}</p>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Balance", f"${st.session_state.account_data['balance']:,.2f}")
c2.metric("Samantha PnL", f"${st.session_state.account_data.get('pnl_s', 0):,.2f}")
c3.metric("Gorilla PnL", f"${st.session_state.account_data.get('pnl_g', 0):,.2f}")
c4.metric("Sniper PnL", f"${st.session_state.account_data.get('pnl_n', 0):,.2f}")

st.divider()

if st.session_state.fleet_active:
    with st.status("Fleet scanning markets...", expanded=True) as status:
        symbols = ['EURUSD', 'GBPUSD', 'GOLD', 'BTCUSD', 'ETHUSD']
        api = MetaApi(meta_token)
        account = asyncio.run(api.metatrader_account_api.get_account(meta_account_id))
        connection = account.get_rpc_connection()
        asyncio.run(connection.connect()); asyncio.run(connection.wait_synchronized())
        for symbol in symbols:
            if sam_enabled:
                st.write(f"💃 Samantha analyzing {symbol}...")
                d, c = asyncio.run(get_samantha_signal(connection, symbol))
                if d: asyncio.run(execute_trade(meta_token, meta_account_id, symbol, d, sam_risk, MAGIC_SAMANTHA, "Sam Fleet")); st.session_state.trade_history.insert(0, f"💃 {datetime.now().strftime('%H:%M:%S')} - {d} {symbol}")
            if gor_enabled:
                st.write(f"🦍 Gorilla scouting {symbol}...")
                d, c = asyncio.run(get_gorilla_signal(connection, symbol))
                if d: asyncio.run(execute_trade(meta_token, meta_account_id, symbol, d, gor_risk, MAGIC_GORILLA, "Gor Fleet")); st.session_state.trade_history.insert(0, f"🦍 {datetime.now().strftime('%H:%M:%S')} - {d} {symbol}")
            if sni_enabled:
                st.write(f"🎯 Sniper targeting {symbol}...")
                d, tp = asyncio.run(get_sniper_signal(connection, symbol, sni_adx, 2.5))
                if d: asyncio.run(execute_trade(meta_token, meta_account_id, symbol, d, sni_risk, MAGIC_SNIPER, "Sniper Fleet", tp)); st.session_state.trade_history.insert(0, f"🎯 {datetime.now().strftime('%H:%M:%S')} - {d} {symbol}")
        status.update(label="Fleet Scan Complete. Resting 15s...", state="complete")
    time.sleep(15); st.rerun()

l, r = st.columns(2)
with l:
    st.subheader("📜 Fleet Log")
    for h in st.session_state.trade_history[:10]: st.write(h)
with r:
    st.subheader("🤖 Deployment Status")
    st.markdown(f"""
    <div class="bot-card sniper-accent"><b>Range Sniper</b>: {'🟢 ONLINE' if sni_enabled and st.session_state.fleet_active else '⚪ IDLE'}<br><small>M1 Mean Reversion</small></div>
    <div class="bot-card samantha-accent"><b>Samantha Pro</b>: {'🟢 ONLINE' if sam_enabled and st.session_state.fleet_active else '⚪ IDLE'}<br><small>M5/M15 Momentum</small></div>
    <div class="bot-card gorilla-accent"><b>Gorilla Pro</b>: {'🟢 ONLINE' if gor_enabled and st.session_state.fleet_active else '⚪ IDLE'}<br><small>M1 Hyper-Scalp</small></div>
    """, unsafe_allow_html=True)
