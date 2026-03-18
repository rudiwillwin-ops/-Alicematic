# This is the main bot file.

# Please add your API keys here
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"

from valr_python import Client

def main():
    """
    Main function to start the trading bot.
    """
    print("Starting the trading bot...")
    
    # Create a VALR client
    c = Client(api_key=API_KEY, api_secret=API_SECRET)
    
    # Get market summary for BTC/USDC
    try:
        market_summary = c.get_market_summary(currency_pair="BTCUSDC")
        last_traded_price = market_summary['lastTradedPrice']
        print(f"The last traded price for BTC/USDC is: {last_traded_price}")
    except Exception as e:
        print(f"An error occurred: {e}")

    print("Trading bot finished.")

if __name__ == "__main__":
    main()
