@echo off
rem SYNTHESIS launcher - uses bundled venv, no system Python needed
cd /d "%~dp0"
set PYTHON=venv\Scripts\python.exe
if not exist "%PYTHON%" (
    echo [ERROR] venv not found. Recreate it with:
    echo     python -m venv venv
    echo     venv\Scripts\pip install numpy pygame
    pause
    exit /b 1
)
"%PYTHON%" game.py
if errorlevel 1 pause
