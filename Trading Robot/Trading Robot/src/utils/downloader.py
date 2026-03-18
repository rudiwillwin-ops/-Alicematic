import ccxt.async_support as ccxt
import asyncio
import pandas as pd
from loguru import logger
import os
from datetime import datetime, timedelta

SYMBOLS = ["BTC/USDT", "SOL/USDT"]
TIMEFRAME = "1m"
DAYS = 7 # Start with 7 days to ensure speed and bypass rate limits

async def download_data():
    # Use TESTNET for data since mainnet is blocked/unreachable
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True) # IMPORTANT: Switch to Testnet
    
    start_date = datetime.now() - timedelta(days=DAYS)
    since = int(start_date.timestamp() * 1000)
    
    data_dir = "data/historical"
    os.makedirs(data_dir, exist_ok=True)

    logger.info(f"⏳ Downloading {DAYS} days of 1m TESTNET data for BTC and SOL...")

    for symbol in SYMBOLS:
        filename = f"{data_dir}/{symbol.replace('/', '_')}_HF.csv"
        all_candles = []
        current_since = since
        
        try:
            # Testnet has smaller limits, fetch in chunks of 500
            while current_since < datetime.now().timestamp() * 1000:
                candles = await exchange.fetch_ohlcv(symbol, TIMEFRAME, since=current_since, limit=500)
                if not candles:
                    break
                
                all_candles += candles
                current_since = candles[-1][0] + 1
                
                if len(all_candles) % 2000 == 0:
                    logger.debug(f"Fetched {len(all_candles)} candles...")
                
                await asyncio.sleep(0.2)
                
            if all_candles:
                df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df.to_csv(filename, index=False)
                logger.success(f"✅ Saved {len(df)} 1m Testnet candles for {symbol}")
            else:
                logger.error(f"❌ No Testnet data found for {symbol}")
                
        except Exception as e:
            logger.error(f"Testnet Fetch Error: {e}")

    await exchange.close()

if __name__ == "__main__":
    asyncio.run(download_data())