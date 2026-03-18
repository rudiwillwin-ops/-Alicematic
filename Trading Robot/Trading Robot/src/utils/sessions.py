from datetime import datetime, time
import pytz

class SessionManager:
    """
    Tracks Global Financial Sessions in UTC.
    """
    def __init__(self):
        self.utc = pytz.UTC

    def get_current_session(self):
        now_utc = datetime.now(self.utc).time()
        
        # Define Sessions (UTC)
        # London: 08:00 - 16:00
        # New York: 13:00 - 21:00
        # Tokyo: 00:00 - 09:00
        
        is_london = time(8, 0) <= now_utc <= time(16, 0)
        is_ny = time(13, 0) <= now_utc <= time(21, 0)
        is_tokyo = time(0, 0) <= now_utc <= time(9, 0)
        
        if is_london and is_ny:
            return "LONDON_NY_OVERLAP" # Highest Volatility
        elif is_london:
            return "LONDON"
        elif is_ny:
            return "NEW_YORK"
        elif is_tokyo:
            return "TOKYO"
        else:
            return "QUIET_ZONE"

    def is_high_volatility_window(self):
        """Returns True during London or NY opens"""
        session = self.get_current_session()
        return session in ["LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"]
