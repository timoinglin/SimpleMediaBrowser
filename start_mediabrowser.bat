@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env not found.
    echo Please run install.bat first, then edit .env before starting.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python app.py
pause
