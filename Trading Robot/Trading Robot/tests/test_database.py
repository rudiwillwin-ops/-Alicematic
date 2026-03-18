import unittest
import os
import sqlite3
from src.core.database import TradeRepository
from src.config import config

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Use a temporary DB for testing
        self.test_db = "tests/test_trades.db"
        config.DB_PATH = self.test_db
        self.repo = TradeRepository()

    def tearDown(self):
        # Clean up
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_add_and_retrieve_trade(self):
        # 1. Add Trade
        self.repo.add_trade(
            symbol="BTC/USDT",
            entry_price=50000.0,
            size=0.1,
            stop_loss=49000.0,
            take_profit=53000.0
        )
        
        # 2. Retrieve
        trades = self.repo.get_open_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['symbol'], "BTC/USDT")
        self.assertEqual(trades[0]['status'], "OPEN")

    def test_close_trade(self):
        # 1. Add
        self.repo.add_trade("ETH/USDT", 2000, 1.0, 1900, 2200)
        trades = self.repo.get_open_trades()
        trade_id = trades[0]['id']
        
        # 2. Close
        self.repo.close_trade(trade_id, 2100, "Take Profit")
        
        # 3. Verify it's gone from Open Trades
        open_trades = self.repo.get_open_trades()
        self.assertEqual(len(open_trades), 0)
        
        # 4. Verify it exists in DB as CLOSED
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM trades WHERE id=?", (trade_id,))
        status = cursor.fetchone()[0]
        self.assertEqual(status, "CLOSED")
        conn.close()

if __name__ == '__main__':
    unittest.main()
