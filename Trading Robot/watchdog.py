import subprocess
import time
import sys
from loguru import logger

BOT_SCRIPT = "src/core/engine.py"
RESTART_DELAY = 5 # Seconds

def start_bot():
    """Starts the trading bot as a subprocess"""
    logger.info("🚀 Watchdog is launching the Trading Bot...")
    # Use the current python interpreter with -m to fix import paths
    return subprocess.Popen([sys.executable, "-m", "src.core.engine"])

def main():
    logger.info("🐶 Watchdog Active. Monitoring Bot Health...")
    
    process = start_bot()
    
    while True:
        try:
            # Check if bot is still running
            status = process.poll()
            
            if status is not None:
                # Bot has died
                logger.error(f"⚠️ Bot crashed with exit code {status}!")
                logger.info(f"♻️ Restarting in {RESTART_DELAY} seconds...")
                time.sleep(RESTART_DELAY)
                process = start_bot()
            
            # Heartbeat check every 10s
            time.sleep(10)
            
        except KeyboardInterrupt:
            logger.info("🛑 Watchdog stopping. Killing bot...")
            process.terminate()
            break

if __name__ == "__main__":
    main()
