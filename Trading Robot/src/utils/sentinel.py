from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from loguru import logger

# Explicitly load .env
load_dotenv()

class NewsSentinel:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("⚠️ No Gemini API Key found in environment. Sentinel is disabled.")
            self.active = False
            return
        
        try:
            self.client = genai.Client(api_key=api_key)
            self.active = True
            logger.info("🧠 Gemini AI Sentinel Active.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            self.active = False

    async def analyze_market_mood(self, headlines: list) -> str:
        """
        Asks Gemini to classify the market mood based on headlines.
        Returns: "BULLISH", "BEARISH", "NEUTRAL", or "CRISIS"
        """
        if not self.active:
            return "NEUTRAL"

        prompt = f"""
        Analyze these crypto market headlines and determine the immediate market sentiment.
        Headlines: {headlines}
        
        Classify into exactly one of these categories:
        - BULLISH (Good news, adoption, pumps)
        - BEARISH (Bad news, regulation, drops)
        - NEUTRAL (Nothing special)
        - CRISIS (Exchange hack, Stablecoin de-peg, War, Ban)
        
        Reply with JUST the category name.
        """
        
        # List of models to try (Institutional fallbacks)
        models_to_try = [
            'gemini-2.0-flash-001', # Priority based on your project configuration
            'gemini-1.5-flash', 
            'gemini-1.5-flash-8b',  # High availability fallback
            'gemini-pro'
        ]

        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name, 
                    contents=prompt
                )
                
                sentiment = response.text.strip().upper()
                
                valid_states = ["BULLISH", "BEARISH", "NEUTRAL", "CRISIS"]
                if sentiment not in valid_states:
                    return "NEUTRAL"
                    
                return sentiment

            except Exception:
                # Silently fail and try the next model to keep logs clean
                continue
        
        # If all fail, return NEUTRAL without crashing
        return "NEUTRAL"