from src.config import config
from loguru import logger
import time

class RiskManager:
    def __init__(self):
        self.kelly_fraction = 0.25 
        self.win_rate_est = 0.45 
        self.win_loss_ratio = 2.5 
        
        # --- THE VAULT PROTOCOL ---
        self.max_daily_drawdown = 0.15 # 15% Max loss per day
        self.daily_start_balance = 50.0
        self.last_balance_check = time.time()
        self.is_locked = False

    def calculate_position_size(self, balance: float, entry: float, stop: float) -> float:
        # Reset daily check every 24h
        if time.time() - self.last_balance_check > 86400:
            self.daily_start_balance = balance
            self.last_balance_check = time.time()
            self.is_locked = False

        # CIRCUIT BREAKER: Stop if balance dropped 15% today
        if balance < (self.daily_start_balance * (1 - self.max_daily_drawdown)):
            logger.critical("🚨 CIRCUIT BREAKER TRIGGERED: Daily loss limit reached. Locking bot.")
            self.is_locked = True
            return 0.0

        if self.is_locked or balance <= 0: return 0.0

        # Kelly Sizing
        p = self.win_rate_est
        b = self.win_loss_ratio
        kelly_pct = (p * (b + 1) - 1) / b
        risk_pct = max(0.01, min(kelly_pct * self.kelly_fraction, 0.05)) 
        
        risk_amount = balance * risk_pct
        risk_per_unit = abs(entry - stop)
        if risk_per_unit == 0: return 0.0
        
        size = risk_amount / risk_per_unit
        logger.info(f"⚖️ APEX Size: {size:.4f} | Risking {risk_pct*100:.1f}%")
        return size
