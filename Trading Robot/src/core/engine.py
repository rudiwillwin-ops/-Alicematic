import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
from loguru import logger
from src.config import config
from src.strategies.whale_sniper import WhaleSniper
from src.core.risk_manager import RiskManager
from src.core.database import TradeRepository
from src.utils.sentinel import NewsSentinel
from src.utils.notifications import Notifier
from src.core.reporting import DailyReporter
import sys
import time

class TradingEngine:
    def __init__(self):
        self.exchange = None
        self.is_running = False
        self.strategy = WhaleSniper()
        self.risk_manager = RiskManager()
        self.db = TradeRepository()
        self.sentinel = NewsSentinel()
        self.notifier = Notifier()
        self.reporter = DailyReporter()
        self.active_trades = []
        
        # Tracking
        self.last_sentiment = "NEUTRAL"
        self.last_sentiment_time = 0
        self.last_report_time = time.time()
        self.last_heartbeat_time = time.time()

    async def initialize(self):
        """Setup exchange connection & Load State"""
        try:
            exchange_class = getattr(ccxt, config.EXCHANGE_ID)
            self.exchange = exchange_class({
                'apiKey': config.API_KEY,
                'secret': config.API_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'brokerDemo': True # Enable new Binance Demo Trading
                }
            })
            
            if config.SANDBOX_MODE:
                # Force the exchange to use the new Demo/Mock endpoints
                self.exchange.set_sandbox_mode(True)
                logger.warning("⚠️  RUNNING IN BINANCE DEMO/MOCK TRADING MODE ⚠️")

            await self.exchange.load_markets()
            self.active_trades = self.db.get_open_trades()
            logger.info(f"📂 System Initialized. {len(self.active_trades)} active trades loaded.")
            
        except Exception as e:
            logger.critical(f"Failed to initialize: {e}")
            sys.exit(1)

    async def fetch_market_data(self, symbol, timeframe):
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=200)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"Data Fetch Error ({symbol}): {e}")
            return None

    async def manage_active_trades(self, symbol, current_price, current_atr):
        """Institutional Trailing Stop & Exit Logic"""
        for trade in self.active_trades:
            if trade['symbol'] != symbol: continue

            # 1. Exit Conditions
            if current_price <= trade['stop_loss']:
                await self.close_position(trade, current_price, "Stop Loss Hit")
                continue
            if current_price >= trade['take_profit']:
                await self.close_position(trade, current_price, "Take Profit Hit")
                continue

            # 2. Apex Trailing (Move to Break Even after 1.5% gain)
            if current_price > trade['entry_price'] * 1.015:
                if trade['stop_loss'] < trade['entry_price']:
                    trade['stop_loss'] = trade['entry_price']
                    logger.info(f"🛡️  SL moved to BREAK EVEN for {symbol}")

    async def close_position(self, trade, price, reason):
        try:
            side = 'sell' if trade['size'] > 0 else 'buy'
            await self.exchange.create_order(trade['symbol'], 'market', side, abs(trade['size']))
            self.db.close_trade(trade['id'], price, reason)
            
            # Send Notification
            await self.notifier.send_message(
                f"💰 **POSITION CLOSED: {trade['symbol']}**\nReason: {reason}\nExit Price: ${price:.2f}",
                color=0xf1c40f # Yellow
            )
            
            self.active_trades = [t for t in self.active_trades if t['id'] != trade['id']]
            logger.success(f"💰 Position Closed: {trade['symbol']} ({reason})")
        except Exception as e:
            logger.error(f"Close Position Failed: {e}")

    async def execute_order(self, symbol, signal):
        try:
            balance_resp = await self.exchange.fetch_balance()
            free_balance = balance_resp['free'].get('USDT', 0)
            
            amount = self.risk_manager.calculate_position_size(free_balance, signal['price'], signal['stop_loss'])
            if amount <= 0: return

            side = 'buy' if signal['action'] == "BUY" else 'sell'
            order = await self.exchange.create_order(symbol, 'market', side, amount)
            
            # Save to DB
            self.db.add_trade(
                symbol=symbol,
                entry_price=signal['price'],
                size=amount if side == 'buy' else -amount,
                stop_loss=signal['stop_loss'],
                take_profit=signal['take_profit']
            )
            
            # Send Discord Alert
            await self.notifier.send_trade_alert(
                symbol, signal['action'], signal['price'], amount, 
                signal['stop_loss'], signal['take_profit']
            )
            
            self.active_trades = self.db.get_open_trades()
            logger.success(f"🚀 APEX Position Live: {symbol}")
            
        except Exception as e:
            logger.error(f"Execution Failed: {e}")

    async def execute_strategy(self, symbol, timeframe):
        # 0. AI Sentiment Check (Cached for 10 mins for HF speed)
        now = time.time()
        if now - self.last_sentiment_time > 600:
            self.last_sentiment = await self.sentinel.analyze_market_mood(["Market high frequency scan"])
            self.last_sentiment_time = now
            logger.info(f"🧠 AI Market Mood: {self.last_sentiment}")

        if self.last_sentiment == "CRISIS": return

        # 1. Get Data
        df = await self.fetch_market_data(symbol, timeframe)
        if df is None or len(df) < 200: return
        
        current_price = df['close'].iloc[-1]
        current_atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]

        # 2. Manage Existing
        await self.manage_active_trades(symbol, current_price, current_atr)

        # 3. Entry Logic (Only if no open trade for this symbol)
        if any(t['symbol'] == symbol for t in self.active_trades): return 

        signal = self.strategy.analyze(df)
        
        if signal["action"] in ["BUY", "SELL"]:
            logger.info(f"🎯 APEX SIGNAL: {signal['action']} {symbol} @ {signal['price']}")
            await self.execute_order(symbol, signal)

    async def run(self):
        await self.initialize()
        self.is_running = True
        logger.info(f"🚀 APEX V7 Live Scan Started. Frequency: {config.TIMEFRAMES}")
        
        while self.is_running:
            # Check for Daily Report (Every 24h)
            now = time.time()
            if now - self.last_report_time > 86400:
                balance_resp = await self.exchange.fetch_balance()
                current_bal = balance_resp['total'].get('USDT', 0)
                stats = self.reporter.get_last_24h_stats(current_bal, self.last_sentiment)
                await self.notifier.send_daily_summary(stats)
                self.last_report_time = now

            # Check for Heartbeat (Every 6h)
            if now - self.last_heartbeat_time > 21600:
                await self.notifier.send_message(
                    f"💓 **HEARTBEAT**: Bot is alive and scanning.\n**Sentiment**: {self.last_sentiment}",
                    title="💓 SYSTEM HEARTBEAT",
                    color=0x2ecc71 # Green
                )
                self.last_heartbeat_time = now

            for symbol in config.SYMBOLS:
                for tf in config.TIMEFRAMES:
                    await self.execute_strategy(symbol, tf)
            # 1-minute loop for HFI
            await asyncio.sleep(30)

    async def shutdown(self):
        if self.exchange: await self.exchange.close()

if __name__ == "__main__":
    bot = TradingEngine()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        asyncio.run(bot.shutdown())
