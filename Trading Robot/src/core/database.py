import sqlite3
from src.config import config
from loguru import logger
from datetime import datetime
import json

class TradeRepository:
    def __init__(self):
        self.db_path = config.DB_PATH
        self._init_db()

    def _init_db(self):
        """Create the table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # We store: Symbol, Entry Price, Size, Stop Loss, Status
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL,
                status TEXT DEFAULT 'OPEN',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_trade(self, symbol, entry_price, size, stop_loss, take_profit, metadata=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (symbol, entry_price, size, stop_loss, take_profit, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, entry_price, size, stop_loss, take_profit, json.dumps(metadata or {})))
        conn.commit()
        conn.close()
        logger.info(f"💾 Trade saved to DB: {symbol} @ {entry_price}")

    def get_open_trades(self):
        """Recover 'Amnesia' - Get all active trades"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append(dict(row))
        return trades

    def close_trade(self, trade_id, exit_price, reason):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trades 
            SET status = 'CLOSED', 
                metadata = json_patch(metadata, ?) 
            WHERE id = ?
        ''', (json.dumps({"exit_price": exit_price, "reason": reason, "closed_at": str(datetime.now())}), trade_id))
        conn.commit()
        conn.close()
        logger.info(f"💾 Trade {trade_id} marked CLOSED in DB.")
