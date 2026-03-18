import os
import sys
import time
import subprocess
from datetime import datetime

LOG_PATH = os.path.join(os.getcwd(), "watchdog.log")


def log(msg: str) -> None:
    line = f"{datetime.utcnow().isoformat()} {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    log("watchdog start")
    env = os.environ.copy()
    while True:
        try:
            log("starting main.py")
            proc = subprocess.Popen(
                [sys.executable, "-u", "main.py"],
                env=env,
                cwd=os.getcwd()
            )
            code = proc.wait()
            log(f"main.py exited with code {code}, restarting in 5s")
        except Exception as exc:
            log(f"watchdog error: {exc}")
        time.sleep(5)


if __name__ == "__main__":
    main()
