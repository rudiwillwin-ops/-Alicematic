import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from src.config import config
from loguru import logger

class DailyReporter:
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path

    def get_last_24h_stats(self, current_balance, current_sentiment):
        conn = sqlite3.connect(self.db_path)
        
        # Get trades from last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        query = f"SELECT * FROM trades WHERE timestamp >= '{yesterday}' AND status = 'CLOSED'"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return {
                "pnl": 0.0, "dollar_pnl": 0.0, "win_rate": 0.0, 
                "trade_count": 0, "balance": current_balance,
                "sentiment": current_sentiment,
                "action_required": "NO DATA - Keep Current Strategy"
            }

        # Calculate Stats
        trade_count = len(df)
        # Parse PNL from metadata if stored, or calculate from entry/exit
        # For simplicity, we'll assume we stored PNL or calculate a rough estimate
        # In a real app, we'd pull exact PNL from the exchange API
        
        # Mock calculation for the summary format
        wins = len(df[df['id'] % 2 == 0]) # Mock logic for demonstration
        win_rate = (wins / trade_count) * 100
        
        # AI Insight Logic
        action = "MAINTAIN"
        if win_rate < 30: action = "ADJUST: Strategy Volatility Too High"
        elif win_rate > 60: action = "AGGRESSIVE: Increase Kelly Fraction"
        
        return {
            "pnl": 2.5, # Mock
            "dollar_pnl": current_balance * 0.025,
            "win_rate": win_rate,
            "trade_count": trade_count,
            "balance": current_balance,
            "sentiment": current_sentiment,
            "action_required": action
        }
