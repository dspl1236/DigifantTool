@echo off
python digitool/main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start DigiTool.
    echo Run install.bat first to install dependencies.
    pause
)
