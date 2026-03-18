import aiohttp
import os
from loguru import logger
from datetime import datetime, timezone
from dotenv import load_dotenv

class Notifier:
    def __init__(self):
        load_dotenv()
        self.webhook_url = os.getenv("WEBHOOK_URL")
        self.active = True if self.webhook_url else False

    async def send_message(self, content: str, title: str = "🤖 HedgeBot Alert", color: int = 0x00ff00):
        if not self.active:
            return

        payload = {
            "embeds": [{
                "title": title,
                "description": content,
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status != 204:
                        logger.error(f"Failed to send notification: {resp.status}")
        except Exception as e:
            logger.error(f"Notification Error: {e}")

    async def send_trade_alert(self, symbol, action, price, size, sl, tp):
        color = 0x00ff00 if action == "BUY" else 0xff0000
        msg = (
            f"**Asset:** {symbol}\n"
            f"**Action:** {action}\n"
            f"**Entry:** ${price:.2f}\n"
            f"**Size:** {abs(size):.4f}\n"
            f"**Stop Loss:** ${sl:.2f}\n"
            f"**Take Profit:** ${tp:.2f}"
        )
        await self.send_message(msg, title="🎯 NEW POSITION OPENED", color=color)

    async def send_daily_summary(self, stats):
        color = 0x3498db # Blue
        msg = (
            f"📊 **DAILY PERFORMANCE REPORT**\n"
            f"----------------------------------\n"
            f"**Total Profit/Loss:** {stats['pnl']:.2f}%\n"
            f"**Net Profit:** ${stats['dollar_pnl']:.2f}\n"
            f"**Win Rate:** {stats['win_rate']:.1f}%\n"
            f"**Trades Taken:** {stats['trade_count']}\n"
            f"**Current Balance:** ${stats['balance']:.2f}\n"
            f"**Market Sentiment:** {stats['sentiment']}\n"
            f"----------------------------------\n"
            f"**AI Recommendation:** {stats['action_required']}"
        )
        await self.send_message(msg, title="🏦 INSTITUTIONAL SUMMARY", color=color)
