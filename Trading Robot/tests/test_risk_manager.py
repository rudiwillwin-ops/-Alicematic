import unittest
from src.core.risk_manager import RiskManager
from src.config import config

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.risk_manager = RiskManager()
        # Mock global config to 1% risk
        self.risk_manager.max_risk_per_trade = 0.01

    def test_calculate_position_size_normal(self):
        """
        Scenario: 
        Account: $10,000
        Risk: 1% = $100
        Entry: $100
        Stop Loss: $90 (Risk per share = $10)
        Expected Size: $100 risk / $10 per share = 10 shares
        """
        size = self.risk_manager.calculate_position_size(
            account_balance=10000,
            entry_price=100,
            stop_loss_price=90
        )
        self.assertAlmostEqual(size, 10.0)

    def test_calculate_position_size_zero_balance(self):
        size = self.risk_manager.calculate_position_size(0, 100, 90)
        self.assertEqual(size, 0.0)

    def test_calculate_position_size_invalid_stop(self):
        # Stop Loss same as Entry (Division by Zero protection)
        size = self.risk_manager.calculate_position_size(10000, 100, 100)
        self.assertEqual(size, 0.0)

if __name__ == '__main__':
    unittest.main()
