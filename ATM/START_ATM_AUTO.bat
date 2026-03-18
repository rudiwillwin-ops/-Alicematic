@echo off
set "MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe"
set "CONFIG_PATH=C:\Users\Client\Desktop\robots\ATM\startup_config.ini"

echo Starting MetaTrader 5 with ATM Robot attached...
start "" "%MT5_PATH%" /config:"%CONFIG_PATH%"
exit
