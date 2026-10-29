@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check your Python installation and internet connection.
    pause
    exit /b 1
)
py -3 main.py
if errorlevel 1 pause
