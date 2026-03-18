# risk_manager.py

class RiskManager:
    def __init__(self, daily_trade_limit, trade_risk_percent, rr_ratio, safety_freeze_limit, stop_loss_percent):
        self.daily_trade_limit = daily_trade_limit
        self.trade_risk_percent = trade_risk_percent
        self.rr_ratio = rr_ratio
        self.safety_freeze_limit = safety_freeze_limit
        self.stop_loss_percent = stop_loss_percent
        self.trades_today = 0

    def can_trade(self):
        """Checks if the daily trade limit has been reached."""
        return self.trades_today < self.daily_trade_limit

    def increment_trade_count(self):
        """Increments the daily trade count."""
        self.trades_today += 1

    def calculate_position_size(self, balance):
        """Calculates the position size based on 1% of equity."""
        return balance * self.trade_risk_percent

    def calculate_sl_tp(self, entry_price, side):
        """Calculates stop-loss and take-profit prices."""
        if side == "Buy":
            sl = entry_price * (1 - (self.stop_loss_percent / 100))
            tp = entry_price * (1 + (self.stop_loss_percent * self.rr_ratio / 100))
        elif side == "Sell":
            sl = entry_price * (1 + (self.stop_loss_percent / 100))
            tp = entry_price * (1 - (self.stop_loss_percent * self.rr_ratio / 100))
        else:
            return None, None
        return sl, tp

    def check_safety_freeze(self, current_balance):
        """Triggers a safety freeze if the balance hits the safety_freeze_limit."""
        if current_balance <= self.safety_freeze_limit:
            print(f"!!! BLACK SWAN ALERT !!! Balance ${current_balance} is below safety limit ${self.safety_freeze_limit}. Initiating safety freeze.")
            return True
        return False
