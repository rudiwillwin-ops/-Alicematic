@echo off
rem This batch file starts the trading bot.

rem Change directory to the script's location
cd /d "%~dp0"

echo Starting 'The Bull' trading bot...
C:\Users\Client\AppData\Local\Programs\Python\Python312\python.exe the_bull.py

echo.
echo The script has finished or was stopped. Press any key to close this window.
pause
