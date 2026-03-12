@echo off
echo ============================================================
echo  DigiTool — Digifant 1 G60/G40 ECU Editor
echo  Dependency installer
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install PyQt5

echo.
echo ============================================================
echo  Done! Run DigiTool with:  run.bat
echo ============================================================
pause
