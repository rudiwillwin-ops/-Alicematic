# news_analyzer.py
import requests
import config

class NewsAnalyzer:
    def __init__(self, news_api_key):
        self.news_api_key = news_api_key
        self.base_url = "https://newsapi.org/v2/everything"
        # Keywords suggesting low volatility or a stable market, as per user instruction.
        self.low_volatility_keywords = ["Low Volatility", "Neutral"]

    def is_low_volatility(self):
        """
        Scans news for keywords indicating a low-volatility or neutral market, as per user instruction.
        This is a simplified implementation. True low-volatility detection is complex.
        """
        if not self.news_api_key:
            print("NEWS_API_KEY not configured. Cannot assess market volatility from news.")
            return False

        # Search for specified low-volatility/neutral keywords.
        query = " OR ".join(self.low_volatility_keywords)
        params = {
            'q': query,
            'apiKey': self.news_api_key,
            'sortBy': 'publishedAt',
            'language': 'en'
        }
        try:
            response = requests.get(self.base_url, params=params)
            articles = response.json().get('articles', [])
            if articles:
                print(f"Keywords '{query}' found in recent news. Safe trading window.")
                return True
            else:
                print(f"No headlines matching '{query}' found. Not entering recovery trade.")
                return False
        except Exception as e:
            print(f"Error scanning for news: {e}")
            return False
