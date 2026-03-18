# 🚀 Deployment Guide (VPS)

To run this robot 24/7, you should not use your home PC (internet/power outages).
Use a cheap VPS (Virtual Private Server) like **DigitalOcean** or **Vultr** ($5/mo).

## 1. Get a Server
- OS: **Ubuntu 22.04 LTS** (Standard)
- RAM: **2GB** (Minimum for Python + Pandas)

## 2. Setup (Run these commands on the server)
```bash
# Update System
sudo apt update && sudo apt upgrade -y

# Install Python & Tools
sudo apt install python3-pip python3-venv screen -y

# Clone Your Code (Or upload via SFTP/FileZilla)
mkdir robot
cd robot
# (Upload your files here)

# Create Virtual Env
python3 -m venv venv
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt
```

## 3. Run Forever (Using Screen)
Screen keeps the bot running even if you disconnect SSH.

```bash
# Start a new screen session
screen -S trading_bot

# Start the Watchdog
python watchdog.py
```

**To Detach (Exit without stopping):** Press `Ctrl+A` then `D`.
**To Re-attach (Check on bot):** Type `screen -r trading_bot`.

## 4. Monitoring
Check the logs anytime:
```bash
tail -f logs/app.log
```
