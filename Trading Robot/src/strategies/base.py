from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    """
    Abstract Base Class for all trading strategies.
    Enforces a standard structure so the Engine can run any strategy.
    """
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Input: Pandas DataFrame with OHLCV data.
        Output: Dictionary with signal details.
        
        Expected Return Format:
        {
            "action": "BUY" | "SELL" | "HOLD",
            "confidence": float (0.0 - 1.0),
            "stop_loss": float (price),
            "take_profit": float (price),
            "reason": str
        }
        """
        pass
