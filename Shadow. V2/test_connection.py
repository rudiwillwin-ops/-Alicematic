# test_connection.py
from bybit_client import BybitClient
import config
import json

def test_bybit_connection():
    print(f"Testing Bybit connection (Testnet: {config.BYBIT_TESTNET})...")
    
    if not config.BYBIT_API_KEY or not config.BYBIT_API_SECRET:
        print("Error: BYBIT_API_KEY or BYBIT_API_SECRET not found in .env file.")
        return

    client = BybitClient(config.BYBIT_API_KEY, config.BYBIT_API_SECRET)
    
    try:
        # 1. Test Public API (No authentication needed)
        print("1. Testing Public API (Klines)...")
        klines = client.get_klines(symbol="BTCUSDT", interval="1", limit=1)
        if klines:
            print("Successfully fetched public kline data!")
            print(f"Latest BTC Price: {klines[-1][4]}")
        else:
            print("Failed to fetch public kline data.")

        # 2. Test Private API (Authentication needed)
        print("\n2. Testing Private API (Wallet Balance)...")
        balance = client.get_wallet_balance()
        
        if balance is not None:
            print(f"Successfully connected to Bybit Private API!")
            print(f"Current USDT Balance: {balance}")
        else:
            print("Failed to connect to Private API. Check your API Key and Secret.")
            print(f"Current configuration: Testnet={config.BYBIT_TESTNET}")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_bybit_connection()