import asyncio
import aiohttp
import os
from dotenv import load_dotenv

async def test_webhook():
    print(f"CWD: {os.getcwd()}")
    url = None
    try:
        with open(".env", "r") as f:
            lines = f.readlines()
            print(f"Lines in .env: {len(lines)}")
            for line in lines:
                if "WEBHOOK_URL=" in line:
                    url = line.split("=")[1].strip()
                    break
    except Exception as e:
        print(f"Error reading .env manually: {e}")
    
    print(f"Testing Webhook URL: {url}")
    
    if not url:
        print("Error: WEBHOOK_URL not found in .env")
        return

    payload = {
        "embeds": [{
            "title": "📡 CONNECTION TEST",
            "description": "If you see this, your Discord link is working correctly!",
            "color": 0x2ecc71
        }]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                print(f"Status Code: {resp.status}")
                text = await resp.text()
                if resp.status == 204:
                    print("✅ Success! Message sent to Discord.")
                else:
                    print(f"❌ Failed. Discord response: {text}")
    except Exception as e:
        print(f"❌ Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook())
