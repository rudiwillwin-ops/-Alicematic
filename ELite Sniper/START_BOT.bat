@echo off
title Elite Sniper Centurion Bot

echo ###############################################################
echo #                                                             #
echo #          Starting Elite Sniper Centurion Bot                #
echo #                                                             #
echo ###############################################################

echo.
echo [1] Checking for Python requirements...
pip install -r requirements.txt

echo.
echo [2] Launching the bot...
echo    - Please ensure your MT5 terminal is running.
echo    - Please ensure your credentials in config.py are correct.
echo.

python main.py

echo.
echo ###############################################################
echo #                                                             #
echo #            Bot has been terminated.                         #
echo #            You can close this window.                       #
echo #                                                             #
echo ###############################################################

pause
