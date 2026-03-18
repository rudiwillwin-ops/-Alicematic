
import time
from valr_python import Client
import requests

# CONFIGURATION
API_KEY = "YOUR_VALR_KEY"
API_SECRET = "YOUR_VALR_SECRET"
SYMBOL = "BTCUSDC"
DAILY_CAP = 100
BLACK_SWAN_LVL = 15.00

client = Client(api_key=API_KEY, api_secret=API_SECRET)

def play_ping():
    print("\a") # Laptop sound

def get_balance():




    balances = client.get_balances()
    return next((float(b['available']) for b in balances if b['currency'] == 'USDC'), 0.0)

def main():
    print(">>> Bot Started. Waiting 5 minutes for scan...")
    time.sleep(300)
    trades = 0
    while trades < DAILY_CAP:
        bal = get_balance()
        if bal <= BLACK_SWAN_LVL:
            print("BLACK SWAN ACTIVE")
            # Recovery logic...
            break
        # Trading execution...
        print(f"Trade {trades+1} success. Bal: ${bal}")
        play_ping()
        trades += 1
        time.sleep(10)

if __name__ == "__main__":
    main()
