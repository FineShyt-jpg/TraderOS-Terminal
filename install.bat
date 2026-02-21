@echo off
REM TraderOS Terminal - Windows Installer
REM Run this once to install all dependencies

echo ============================================================
echo TraderOS Terminal - Installing Dependencies
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download Python 3.11+ from https://python.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

python --version
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing core dependencies...
python -m pip install PyQt6>=6.6.0
python -m pip install PyQt6-WebEngine>=6.6.0
python -m pip install anthropic>=0.34.0
python -m pip install pandas>=2.1.0
python -m pip install watchdog>=4.0.0
python -m pip install python-dateutil>=2.9.0
python -m pip install numpy>=1.26.0

echo.
echo ============================================================
echo Installation complete!
echo ============================================================
echo.
echo To run TraderOS Terminal:
echo   python main.py
echo.
echo To set your Anthropic API key (optional - can also set in app):
echo   set ANTHROPIC_API_KEY=sk-ant-...
echo   python main.py
echo.
pause
