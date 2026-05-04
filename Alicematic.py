import streamlit as st
import asyncio
import pandas as pd
import time
from datetime import datetime
from tradingview_ta import TA_Handler, Interval
from metaapi_cloud_sdk import MetaApi

# --- CONFIGURATION & THEME ---
st.set_page_config(page_title="Alicematic Cloud Pro", page_icon="💃", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #0b0f19; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .alicematic-header {
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
    .signal-card {
        padding: 20px;
        border-radius: 15px;
        background: #1c2128;
        border-left: 5px solid #ff0080;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALIZE STATE ---
if "martingale_level" not in st.session_state:
    st.session_state.martingale_level = 1
if "bot_active" not in st.session_state:
    st.session_state.bot_active = False
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "last_signal" not in st.session_state:
    st.session_state.last_signal = {"pair": None, "dir": None, "conf": 0}
if "in_trade" not in st.session_state:
    st.session_state.in_trade = False
if "last_ticket" not in st.session_state:
    st.session_state.last_ticket = None
if "trade_open_time" not in st.session_state:
    st.session_state.trade_open_time = 0
if "account_data" not in st.session_state:
    st.session_state.account_data = {"balance": 0.0, "equity": 0.0}

# --- ALICEMATIC LOGIC (SENTIMENT PRO ENGINE) ---
def get_alicematic_signal(symbol):
    try:
        # Standardize for TradingView
        tv_symbol = symbol.replace("USD", "USDT") if "USD" in symbol and "BTC" in symbol else symbol
        
        # Check M1 (Primary)
        handler_m1 = TA_Handler(
            symbol=tv_symbol,
            screener="forex" if "USD" in symbol else "crypto",
            exchange="FX_IDC" if "USD" in symbol else "BINANCE",
            interval=Interval.INTERVAL_1_MINUTE
        )
        analysis_m1 = handler_m1.get_analysis()
        summary = analysis_m1.summary
        
        buy = summary["BUY"]
        sell = summary["SELL"]
        total = buy + sell + summary["NEUTRAL"]
        
        confidence = max(buy, sell) / total * 100
        direction = "BUY" if buy > sell else "SELL"
        
        return direction, confidence
    except Exception as e:
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
        return info
    except:
        return None

async def close_alicematic_trade(token, account_id, symbol):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        positions = await connection.get_positions()
        for p in positions:
            if p['symbol'] == symbol:
                result = await connection.close_position(p['id'])
                return result
        return {"error": "No open position found"}
    except Exception as e:
        return {"error": str(e)}

async def place_alicematic_trade(token, account_id, symbol, direction, volume):
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        # Determine order
        if direction == "BUY":
            result = await connection.create_market_buy_order(symbol, volume)
        else:
            result = await connection.create_market_sell_order(symbol, volume)
            
        return result
    except Exception as e:
        return {"error": str(e)}

async def check_auto_judge(token, account_id):
    """Automatically check if the last trade was a win or loss."""
    api = MetaApi(token)
    try:
        account = await api.metatrader_account_api.get_account(account_id)
        connection = account.get_rpc_connection()
        await connection.connect()
        await connection.wait_synchronized()
        
        # Check open positions first
        positions = await connection.get_positions()
        if any(p['symbol'] == st.session_state.get('active_symbol') for p in positions):
            return "OPEN"
        
        # Check last deal if no positions open
        deals = await connection.get_history_deals_by_time(datetime.now().timestamp() - 3600, datetime.now().timestamp())
        if not deals:
            return "WAITING"
            
        deals.sort(key=lambda x: x['time'], reverse=True)
        last_deal = deals[0]
        
        if last_deal['ticket'] == st.session_state.last_ticket:
            return "ALREADY_PROCESSED"
            
        st.session_state.last_ticket = last_deal['ticket']
        return "WIN" if last_deal['profit'] > 0 else "LOSS"
    except Exception as e:
        return f"ERROR: {str(e)}"

# --- SIDEBAR: SETTINGS & BRIDGES ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2592/2592225.png", width=100)
st.sidebar.title("Alicematic Control")

with st.sidebar.expander("🔑 CLOUD BRIDGE (MetaApi)", expanded=True):
    # Try to load from secrets first for cloud deployment convenience
    default_token = st.secrets.get("META_TOKEN", "YOUR_TOKEN")
    default_account = st.secrets.get("META_ACCOUNT_ID", "YOUR_ACCOUNT_ID")
    
    meta_token = st.text_input("API Token", value=default_token, type="password")
    meta_account_id = st.text_input("Account ID", value=default_account)

with st.sidebar.expander("🏦 ACCOUNT SETTINGS", expanded=True):
    acc_type = st.radio("Account Type", ["Standard ($)", "Micro (¢/Cents)"])
    env_mode = st.radio("Environment", ["Live", "Demo"])
    auto_stake_demo = st.checkbox("Auto-Stake 1% (Demo Only)", value=True)

with st.sidebar.expander("📈 RUNAMATIX PARAMETERS", expanded=True):
    # Fetch real balance for Demo auto-staking
    current_balance = st.session_state.account_data["balance"]
    
    if env_mode == "Demo" and auto_stake_demo and current_balance > 0:
        # 1% logic: e.g. $10,000 -> 0.10 lots, $1000 -> 0.01 lots
        calc_stake = round((current_balance * 0.01) / 100, 2)
        base_stake = st.number_input("Base Lot (Auto-1%)", value=max(0.01, calc_stake), step=0.01, disabled=True)
    else:
        base_stake = st.number_input("Base Lot Size", 0.01, 1.0, 0.01, step=0.01)
        
    m_multiplier = st.number_input("Martingale Multiplier", 1.0, 3.0, 2.1)
    max_levels = st.slider("Max Martingale Levels", 1, 10, 7)
    min_confidence = st.slider("Min Signal Confidence (%)", 50, 100, 85)

# Update account data periodically
if meta_token and meta_account_id and meta_token != "YOUR_TOKEN":
    acc_info = asyncio.run(get_account_data(meta_token, meta_account_id))
    if acc_info:
        st.session_state.account_data["balance"] = acc_info["balance"]
        st.session_state.account_data["equity"] = acc_info["equity"]

st.sidebar.divider()
if st.sidebar.button("🚀 DEPLOY ALICEMATIC", use_container_width=True, type="primary"):
    if not meta_token or not meta_account_id:
        st.sidebar.error("Missing Cloud Credentials!")
    else:
        st.session_state.bot_active = not st.session_state.bot_active
        st.sidebar.success("Alicematic Logic Engaged!" if st.session_state.bot_active else "Bot Hibernating...")

# --- MAIN INTERFACE ---
st.markdown('<p class="alicematic-header">ALICEMATIC PRO</p>', unsafe_allow_html=True)

# Format Header
header_mode = f"Official Runamatix MT5 Cloud Replica | {env_mode} Mode"
st.markdown(f"<p style='text-align: center; color: #8b949e;'>{header_mode}</p>", unsafe_allow_html=True)

# Top Metrics
m1, m2, m3, m4 = st.columns(4)
current_lot = base_stake * (m_multiplier ** (st.session_state.martingale_level - 1))

# Balance Formatting for Micro Accounts
bal = st.session_state.account_data["balance"]
if acc_type == "Micro (¢/Cents)":
    # If the balance is small (e.g. 50.00), we display it as 5000¢
    display_bal = f"{bal:,.0f} ¢" if bal > 500 else f"{bal*100:,.0f} ¢"
else:
    display_bal = f"${bal:,.2f}"

m1.metric("Account Balance", display_bal)
m2.metric("Current Lot", f"{current_lot:.2f}")
m3.metric("M-Level", f"{st.session_state.martingale_level}/{max_levels}")
m4.metric("Status", "LIVE" if st.session_state.bot_active else "IDLE")

st.divider()

# Core Trading Loop
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📡 Live Market Scanner")
    assets = st.multiselect("Assets to Scan", ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "BTCUSD", "ETHUSD"], default=["EURUSD", "GBPUSD", "USDJPY"])
    
    if st.session_state.bot_active:
        with st.status("Managing Portfolio...", expanded=True) as status:
            # 1. Check for Auto-Close (60 Seconds)
            if st.session_state.in_trade:
                elapsed = time.time() - st.session_state.trade_open_time
                st.write(f"⏱️ Trade Duration: {int(elapsed)}s / 60s")
                
                if elapsed >= 60:
                    st.write("🛑 Timer Expired! Closing trade...")
                    close_res = asyncio.run(close_alicematic_trade(meta_token, meta_account_id, st.session_state.active_symbol))
                    if "error" in close_res:
                        st.write(f"Note: {close_res['error']}")
                    else:
                        st.success("Trade Closed by Timer.")
                    time.sleep(2)
                
                # 2. Check for Results (Auto-Judge)
                st.write(f"Checking status of {st.session_state.get('active_symbol')}...")
                result = asyncio.run(check_auto_judge(meta_token, meta_account_id))
                
                if result == "WIN":
                    st.write("✅ LAST TRADE: WIN! Resetting Martingale.")
                    st.session_state.martingale_level = 1
                    st.session_state.in_trade = False
                    st.balloons()
                elif result == "LOSS":
                    st.write("❌ LAST TRADE: LOSS. Increasing Martingale Level.")
                    if st.session_state.martingale_level < max_levels:
                        st.session_state.martingale_level += 1
                    else:
                        st.write("⚠️ MAX LEVELS REACHED. Resetting to Safety.")
                        st.session_state.martingale_level = 1
                    st.session_state.in_trade = False
                elif result == "OPEN":
                    st.write("⏳ Trade still active. Waiting...")
                else:
                    st.write(f"System: {result}")
            
            # 3. Scan for New Signals across all selected assets
            if not st.session_state.in_trade:
                found_signal = False
                for pair in assets:
                    st.write(f"Scanning {pair}...")
                    direction, confidence = get_alicematic_signal(pair)
                    
                    if confidence >= min_confidence:
                        st.write(f"🔥 {pair} Signal Confirmed! {confidence:.1f}% {direction}")
                        st.write(f"Executing {current_lot:.2f} lot...")
                        
                        # REAL EXECUTION
                        st.session_state.active_symbol = pair
                        trade_res = asyncio.run(place_alicematic_trade(meta_token, meta_account_id, pair, direction, round(current_lot, 2)))
                        
                        if "error" not in trade_res:
                            st.session_state.in_trade = True
                            st.session_state.trade_open_time = time.time() # Start 60s Timer
                            st.session_state.trade_history.insert(0, {
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "pair": pair,
                                "dir": direction,
                                "lots": round(current_lot, 2),
                                "conf": f"{confidence:.1f}%"
                            })
                            status.update(label=f"Trade Executed on {pair}!", state="complete")
                            found_signal = True
                            break 
                        else:
                            st.error(f"Execution Failed on {pair}: {trade_res['error']}")
                
                if not found_signal:
                    status.update(label="Scanning Complete - No valid signals found.", state="running")
        
        time.sleep(5) 
        st.rerun()

    # Manual Progression (Fallback)
    st.subheader("🎮 Manual Override")
    c1, c2, c3 = st.columns(3)
    if c1.button("Force WIN Reset", use_container_width=True):
        st.session_state.martingale_level = 1
        st.rerun()
    if c2.button("Force LOSS Level", use_container_width=True):
        st.session_state.martingale_level += 1
        st.rerun()
    if c3.button("🔄 HARD RESET", use_container_width=True):
        st.session_state.martingale_level = 1
        st.session_state.in_trade = False
        st.rerun()

with col_right:
    st.subheader("📜 Activity Log")
    if not st.session_state.trade_history:
        st.info("No trades executed yet.")
    for trade in st.session_state.trade_history[:10]:
        color = "#23d160" if trade["dir"] == "BUY" else "#ff3860"
        st.markdown(f"""
            <div style="border-bottom: 1px solid #30363d; padding: 5px 0;">
                <small>{trade['time']}</small><br>
                <b style="color: {color};">{trade['dir']} {trade['pair']}</b> | {trade['lots']} Lots | {trade['conf']}
            </div>
        """, unsafe_allow_html=True)

# Footer
st.divider()
st.caption("Alicematic v1.0 | Pure Runamatix Logic | Powered by MetaApi Cloud")
