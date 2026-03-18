# bybit_client.py

from pybit.unified_trading import HTTP
import config

class BybitClient:
    def __init__(self, api_key, api_secret):
        self.session = HTTP(
            testnet=config.BYBIT_TESTNET,
            api_key=api_key,
            api_secret=api_secret,
        )

    def get_wallet_balance(self, account_type="UNIFIED", coin="USDT"):
        """Gets the actual wallet balance from Bybit."""
        try:
            response = self.session.get_wallet_balance(
                accountType=account_type,
                coin=coin,
            )
            if response and response['retCode'] == 0:
                # For UNIFIED account, the balance is often in 'totalEquity' or specific coin 'walletBalance'
                result = response['result']['list'][0]
                # Return the coin's wallet balance
                for coin_data in result.get('coin', []):
                    if coin_data['coin'] == coin:
                        return float(coin_data['walletBalance'])
                
                # Fallback to equity if coin specific balance not found in expected place
                return float(result.get('totalEquity', 0.0))
            else:
                print(f"Failed to get wallet balance: {response}")
                return None
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return None

    def place_limit_order(self, symbol, side, qty, price, stop_loss, take_profit):
        """Places a PostOnly limit order."""
        try:
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Limit",
                qty=qty,
                price=price,
                timeInForce="PostOnly",
                stopLoss=stop_loss,
                takeProfit=take_profit,
            )
            if response and response['retCode'] == 0:
                print(f"Order placed successfully: {response['result']['orderId']}")
                return True
            else:
                print(f"Failed to place order: {response}")
                return False
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def get_ticker_info(self, symbol):
        """Gets ticker information, including 24h volume."""
        try:
            response = self.session.get_tickers(
                category="linear",
                symbol=symbol,
            )
            if response and response['retCode'] == 0:
                return response['result']['list'][0]
            else:
                print(f"Failed to get ticker info: {response}")
                return None
        except Exception as e:
            print(f"Error getting ticker info: {e}")
            return None

    def get_klines(self, symbol, interval, limit):
        """Gets kline data."""
        try:
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                limit=limit,
            )
            if response and response['retCode'] == 0:
                return response['result']['list']
            return None
        except Exception as e:
            print(f"Error getting klines: {e}")
            return None
