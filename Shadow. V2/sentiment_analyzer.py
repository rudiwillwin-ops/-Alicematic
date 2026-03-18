# sentiment_analyzer.py
import requests
import config

class SentimentAnalyzer:
    """
    Simulates a sentiment feed from the 'CRYPTOFEAR satellite'.
    It scans news for FUD (Fear, Uncertainty, and Doubt) keywords.
    """
    def __init__(self, news_api_key):
        self.news_api_key = news_api_key
        self.keywords = config.FUD_KEYWORDS
        self.base_url = "https://newsapi.org/v2/everything"

    def get_sentiment(self):
        """
        Scans news for FUD keywords.
        Returns 'FUD' if keywords are found, otherwise 'Neutral'.
        """
        if not self.news_api_key:
            print("Warning: NEWS_API_KEY not configured. Sentiment analysis is disabled, returning 'Neutral'.")
            return 'Neutral'

        query = " OR ".join(self.keywords)
        params = {
            'q': query,
            'apiKey': self.news_api_key,
            'sortBy': 'publishedAt',
            'language': 'en',
            'pageSize': 10 # Check the 10 most recent articles
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status() # Raise an exception for bad status codes
            articles = response.json().get('articles', [])
            
            if articles:
                print(f"FUD detected in recent news. Sentiment: FUD")
                return 'FUD'
            else:
                # The absence of FUD is Neutral
                return 'Neutral'
        except requests.exceptions.RequestException as e:
            print(f"Error scanning news for sentiment: {e}")
            # In case of API error, default to Neutral to avoid halting trades unnecessarily
            return 'Neutral'

