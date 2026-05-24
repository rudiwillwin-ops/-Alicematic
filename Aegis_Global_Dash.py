# Aegis_Global_Dash.py

import MetaTrader5 as mt5
import pandas as pd
import time
import os
import json
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

# Load available accounts
def load_accounts():
    creds_path = "Aegis/credentials.json"
    if os.path.exists(creds_path):
        with open(creds_path, "r") as f:
            return json.load(f)
    return {"MAIN": {"label": "MASTER_ACCOUNT"}}

ACCOUNTS = load_accounts()

MAGIC_MAP = {
    777777: "AEGIS ATM (Scalper)",
    777001: "AEGIS HARVESTER",
    999111: "AEGIS BULL",
    555555: "AEGIS GRIDLOCK",
    888888: "AEGIS INSTITUTIONAL",
    666777: "AEGIS PHANTOM (Wick)",
    111222: "AEGIS SENTIMENT",
    888999: "GORILLA PRO SCALPER",
    777111: "INGRID MOMENTUM"
}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_account_summary(acc_key, creds):
    init_params = {}
    if creds and 'path' in creds:
        init_params['path'] = creds['path']
        
    if not mt5.initialize(**init_params): 
        return {"status": "OFFLINE", "label": creds.get('label', acc_key)}
    
    # Login
    login_result = mt5.login(login=int(creds['login']), password=str(creds['password']), server=str(creds['server']))
    
    if not login_result:
        mt5.shutdown()
        return {"status": "OFFLINE", "label": creds.get('label', acc_key), "profit": 0, "balance": 0, "equity": 0, "login": "N/A"}

    acc = mt5.account_info()
    positions = mt5.positions_get()
    
    # Load State from C:\Users\Client\Desktop\robots\state\
    state = {}
    state_filename = f"C:/Users/Client/Desktop/robots/state/aegis_state_{acc_key}.json"
    if os.path.exists(state_filename):
        try:
            with open(state_filename, "r") as f:
                state = json.load(f)
        except: pass

    summary = {
        "status": "ONLINE",
        "label": creds.get('label', acc_key),
        "login": acc.login if acc else "Unknown",
        "balance": acc.balance if acc else 0,
        "equity": acc.equity if acc else 0,
        "profit": acc.profit if acc else 0,
        "drawdown": ((acc.balance - acc.equity) / acc.balance * 100) if acc and acc.balance > 0 else 0,
        "state": state,
        "positions": list(positions) if positions else []
    }
    
    mt5.shutdown()
    return summary

def build_dashboard():
    try:
        while True:
            clear_screen()
            print(Fore.CYAN + "="*70)
            print(Fore.CYAN + f"   AEGIS MULTI-ACCOUNT COMMAND CENTER | {datetime.now().strftime('%H:%M:%S')}")
            print(Fore.CYAN + "="*70)

            for acc_key, creds in ACCOUNTS.items():
                data = get_account_summary(acc_key, creds)
                
                # Account Header
                color = Fore.GREEN if data['profit'] >= 0 else Fore.RED
                print(Fore.WHITE + Style.BRIGHT + f" 🏦 {data['label']:<15} | ID: {data['login']} | Balance: ${data['balance']:.2f}")
                print(f" Status: {Fore.GREEN if data['status'] == 'ONLINE' else Fore.RED}{data['status']}{Fore.WHITE} | Profit: " + color + f"${data['profit']:.2f}")
                
                # Robot Directory
                state = data.get('state', {})
                active_modules = state.get('active_module', "").upper().split(",")
                
                print(Fore.MAGENTA + "  ↳ ROBOT STATUS:")
                for m_id, name in MAGIC_MAP.items():
                    is_active = any(p.magic == m_id for p in data['positions'])
                    status = Fore.GREEN + "[ACTIVE]" if is_active else Fore.WHITE + "[IDLE]"
                    # Check if scanning
                    if any(name.upper() in m for m in active_modules):
                        status = Fore.CYAN + "[SCANNING]"
                    print(f"    {name:<25} {status}")
                print("-" * 70)

            print(Fore.CYAN + "="*70)
            print(" Press Ctrl+C to exit...")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nClosing Dashboard...")

if __name__ == "__main__":
    build_dashboard()
