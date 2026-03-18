
"""
Trigger: An Algorithmic Trading Bot for MetaTrader 5 and Pocket Option.

This script implements a trading bot that uses signals from MetaTrader 5 to trade
binary options on the Pocket Option platform.

Disclaimer: Trading is risky. This is a proof-of-concept and should not be used
for live trading without thorough testing and understanding of the risks involved.
"""

import asyncio
import csv
import random
import time
import winsound
from datetime import datetime, timedelta

import MetaTrader5 as mt5
from pocketoption import PocketOption


class Trigger:
    """
    The main class for the Trigger trading bot.

    This class encapsulates all the functionality of the bot, including
    connecting to trading platforms, managing trading state, executing
    trading strategies, and generating reports.
    """

    def __init__(self):
        """
        Initializes the Trigger bot.
        """
        # --- Credentials ---
        # IMPORTANT: Replace these with your actual credentials.
        self.mt5_login = 309567916

        self.mt5_password = Investor8!
        self.mt5_server = XMGlobal-MT5 6
        self.pocket_option_ssid = 
        self.pocket_option_api = None

        # --- Visuals ---
        self.bot_name = "Trigger"
        self.sniper_icon = """
          ██████╗ ██████╗ ██╗██╗   ██╗ ██████╗  ██████╗ ███████╗
          ██╔══██╗██╔══██╗██║╚██╗ ██╔╝██╔════╝ ██╔═══██╗██╔════╝
          ██████╔╝██████╔╝██║ ╚████╔╝ ██║  ███╗██║   ██║█████╗
          ██╔══██╗██╔══██╗██║  ╚██╔╝  ██║   ██║██║   ██║██╔══╝
          ██████╔╝██║  ██║██║   ██║   ╚██████╔╝╚██████╔╝███████╗
          ╚═════╝ ╚═╝  ╚═╝╚═╝   ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝
        """

        # --- Trading State ---
        self.initial_balance = 1000.00  # ZAR
        self.current_balance = self.initial_balance
        self.black_swan_threshold = 240.00  # ZAR ($15)
        self.is_black_swan_mode = False
        self.daily_trade_count = 0
        self.successful_trades = 0

        # --- Control Triggers ---
        self.profit_kill_switch = 15
        self.daily_trade_cap = 50
        self.usd_zar_conversion_rate = 16.01
        self.last_handshake = datetime.now()

        # --- Reporting ---
        self.weekly_report_file = "Trigger_Growth_ZAR.csv"
        self.trade_log = []

    def display_startup_visuals(self):
        """Displays the bot's name and icon."""
        print(self.sniper_icon)
        print(f"Welcome to {self.bot_name}")
        print("=" * 30)

    def connect_to_mt5(self):
        """Connects to the MetaTrader 5 terminal."""
        print("Connecting to MetaTrader 5...")
        if not mt5.initialize():
            print(f"initialize() failed, error code = {mt5.last_error()}")
            return False

        authorized = mt5.login(
            self.mt5_login, self.mt5_password, self.mt5_server
        )
        if authorized:
            print("Successfully connected to MetaTrader 5.")
            return True
        else:
            print(f"Failed to connect to account, error code = {mt5.last_error()}")
            return False

    async def connect_to_pocket_option(self):
        """Connects to the Pocket Option API."""
        print("Connecting to Pocket Option...")
        self.pocket_option_api = PocketOption(ssid=self.pocket_option_ssid)
        await self.pocket_option_api.connect()
        if self.pocket_option_api.check_connect():
            print("Successfully connected to Pocket Option.")
            return True
        else:
            print("Failed to connect to Pocket Option.")
            return False

    async def market_scan(self):
        """Performs a 5-minute market scan."""
        print("Starting 5-minute market scan...")
        await asyncio.sleep(300)
        print("Market scan complete.")

    async def run(self):
        """
        The main loop for the trading bot.

        This method orchestrates the entire trading process, from connecting
        to the trading platforms to executing trades and generating reports.
        """
        self.display_startup_visuals()

        if not self.connect_to_mt5() or not await self.connect_to_pocket_option():
            print("Failed to connect to trading platforms. Exiting.")
            return

        input("Press Enter to start the trading bot...")
        await self.market_scan()

        try:
            while (
                self.daily_trade_count < self.daily_trade_cap
                and self.successful_trades < self.profit_kill_switch
            ):
                if (datetime.now() - self.last_handshake).seconds > 900:  # 15 minutes
                    await self.session_handshake()
                await self.run_trading_strategy()
                await asyncio.sleep(1)
        finally:
            print("Bot shutting down...")
            self.shutdown_mt5()
            await self.shutdown_pocket_option()
            self.generate_weekly_report()
            print("Bot has been shut down.")

    def get_mt5_signal(self):
        """
        Gets a trading signal from MT5.

        NOTE: This is a placeholder. In a real-world scenario, you would
        implement your trading logic here to analyze the market and generate
        signals using data from MT5.
        """
        # For demonstration purposes, we'll return a random signal.
        signals = ["buy", "sell", "wait"]
        return random.choice(signals)

    async def place_trade(self, signal, amount, asset="USDJPY"):
        """
        Places a trade on Pocket Option.

        Args:
            signal (str): The trading signal ('buy' or 'sell').
            amount (int): The amount to trade in USD.
            asset (str): The asset to trade.

        Returns:
            bool: True if the trade was successful, False otherwise.
        """
        if self.pocket_option_api.check_connect():
            print(f"Placing {signal} trade for {asset} with amount ${amount}.")

            # NOTE: The following line is commented out to prevent actual trades.
            # To enable live trading, uncomment the following line and ensure
            # your account is properly configured.
            # trade_result = await self.pocket_option_api.buy(amount, asset, "turbo", signal)

            # For demonstration purposes, we'll simulate a random trade result.
            trade_result = {"win": random.choice([True, False])}
            print(f"Trade result: {'Win' if trade_result['win'] else 'Loss'}")

            self.daily_trade_count += 1
            self.log_trade(signal, amount, asset, trade_result)

            return trade_result["win"]
        else:
            print("Not connected to Pocket Option. Cannot place trade.")
            return False

    async def run_trading_strategy(self):
        """
        Runs the core trading strategy.

        This method determines which trading strategy to use (Quiet Volatile
        or Black Swan), gets a signal from MT5, and places a trade accordingly.
        """
        if self.current_balance <= self.black_swan_threshold:
            self.is_black_swan_mode = True
            print("Black Swan mode activated: Switching to extreme conservative mode.")
        else:
            self.is_black_swan_mode = False

        signal = self.get_mt5_signal()

        if signal != "wait":
            # Randomized latency to mimic human behavior
            latency = random.uniform(2.5, 7.3)
            print(f"Waiting for {latency:.2f} seconds before placing trade.")
            await asyncio.sleep(latency)

            if self.is_black_swan_mode:
                trade_amount = 1  # Lowest possible stake in USD
            else:
                trade_amount = 1  # $1 risk per trade

            trade_successful = await self.place_trade(signal, trade_amount)

            if trade_successful:
                self.successful_trades += 1
                winsound.Beep(1000, 500)  # Play a sound for a successful trade
                print(f"Successful trades today: {self.successful_trades}")

                # Forced 90-second pause after a winning trade
                print("Cooling down for 90 seconds after win...")
                await asyncio.sleep(90)

    def log_trade(self, signal, amount, asset, result):
        """
        Logs a trade to the internal trade log.

        Args:
            signal (str): The trading signal.
            amount (int): The trade amount in USD.
            asset (str): The asset traded.
            result (dict): The result of the trade.
        """
        self.trade_log.append(
            {
                "timestamp": datetime.now(),
                "asset": asset,
                "signal": signal,
                "amount_usd": amount,
                "amount_zar": amount * self.usd_zar_conversion_rate,
                "result": "win" if result["win"] else "loss",
            }
        )

    async def session_handshake(self):
        """
        Mimics a human browser refresh to keep the connection alive and clean.
        """
        print("Performing session handshake...")
        await self.shutdown_pocket_option()
        await self.connect_to_pocket_option()
        self.last_handshake = datetime.now()
        print("Session handshake complete.")

    def shutdown_mt5(self):
        """Shuts down the MetaTrader 5 connection."""
        print("Shutting down MetaTrader 5 connection.")
        mt5.shutdown()

    async def shutdown_pocket_option(self):
        """Shuts down the Pocket Option connection."""
        if self.pocket_option_api and self.pocket_option_api.check_connect():
            print("Shutting down Pocket Option connection.")
            await self.pocket_option_api.close()

    def close_positions(self):
        """
        Closes all open positions.

        NOTE: This functionality is not yet implemented.
        """
        print("Closing all open positions (not yet implemented).")

    def generate_weekly_report(self):
        """
        Generates a weekly CSV report of all trades.
        """
        if not self.trade_log:
            print("No trades to report.")
            return

        with open(self.weekly_report_file, "w", newline="") as csvfile:
            fieldnames = [
                "timestamp",
                "asset",
                "signal",
                "amount_usd",
                "amount_zar",
                "result",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.trade_log)

        print(f"Weekly report generated: {self.weekly_report_file}")


if __name__ == "__main__":
    bot = Trigger()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nBot manually interrupted by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

