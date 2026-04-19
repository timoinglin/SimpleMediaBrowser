@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ================================================
echo   SimpleMediaBrowser - One-click installer (Windows)
echo ================================================
echo.

:: ---- 1. Check for Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [1/4] Python not found. Installing via winget...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo.
        echo ERROR: winget is not available on this system.
        echo Install Python 3.10+ manually from https://www.python.org and rerun install.bat.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Python has been installed. Please CLOSE this window and open a NEW
    echo command prompt, then run install.bat again so PATH picks up Python.
    echo.
    pause
    exit /b 0
) else (
    echo [1/4] Python detected:
    python --version
)

:: ---- 2. Create virtual environment ----
if not exist ".venv" (
    echo.
    echo [2/4] Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: failed to create venv.
        pause
        exit /b 1
    )
) else (
    echo.
    echo [2/4] Virtual environment already exists.
)

:: ---- 3. Install dependencies ----
echo.
echo [3/4] Installing dependencies ...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

:: ---- 4. Seed .env ----
echo.
echo [4/4] Preparing configuration ...
if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo Created .env from .env.example.

    :: Replace SECRET_KEY placeholder with a real random key
    for /f "usebackq delims=" %%K in (`python -c "import secrets; print(secrets.token_hex(32))"`) do (
        set "NEWKEY=%%K"
    )
    if defined NEWKEY (
        python -c "import pathlib; p=pathlib.Path('.env'); t=p.read_text(); t=t.replace('change-me-to-a-random-64-char-hex-string', '!NEWKEY!'); p.write_text(t)"
        echo Generated a random SECRET_KEY in .env.
    )
) else (
    echo .env already exists - leaving it untouched.
)

echo.
echo ================================================
echo   Install complete.
echo.
echo   Next steps:
echo     1. Edit .env to set MEDIA_ROOTS and USERS.
echo     2. Run start_mediabrowser.bat
echo ================================================
pause
endlocal
