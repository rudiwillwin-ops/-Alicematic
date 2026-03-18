@echo off
setlocal
cd /d C:\Users\Client\Desktop\Compounder
REM Force MT5 only
set ONLY_FOREX=1
set ONLY_CRYPTO=
set PYEXE=C:\Users\Client\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYEXE%" (
  echo Python not found at %PYEXE%> watchdog.err
  exit /b 1
)
%PYEXE% -u watchdog.py 1>> watchdog.out 2>> watchdog.err
