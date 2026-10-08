@echo off
REM ============================================================
REM  Geospatial File Measurement API - one-click starter (Windows)
REM  Just double-click this file. First run installs everything.
REM ============================================================
title Geospatial File Measurement API
cd /d "%~dp0"

echo.
echo  ================================================
echo   Geospatial File Measurement API
echo  ================================================
echo.

REM --- Step 1: check Python is installed ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python was not found.
    echo  Install Python 3.10 or newer from https://www.python.org/downloads/
    echo  IMPORTANT: tick "Add python.exe to PATH" during installation,
    echo  then double-click this file again.
    echo.
    pause
    exit /b 1
)

REM --- Step 2: create virtual environment on first run only ---
if not exist ".venv\Scripts\python.exe" (
    echo  [1/3] First run: creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Could not create the virtual environment.
        echo.
        pause
        exit /b 1
    )
) else (
    echo  [1/3] Virtual environment found, skipping.
)

REM --- Step 3: install dependencies ---
echo  [2/3] Installing dependencies, please wait...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Installing dependencies failed. Check your internet connection,
    echo  then double-click this file again.
    echo.
    pause
    exit /b 1
)

REM --- Step 4: start the server ---
echo  [3/3] Starting the server...
echo.
echo   Docs - try the API here:  http://127.0.0.1:8000/docs
echo   Health check:              http://127.0.0.1:8000/health
echo.
echo   Opening the docs in your browser now.
echo   If the page loads before the server is ready, just refresh it once.
echo   Press CTRL+C in this window to stop the server.
echo.
start "" "http://127.0.0.1:8000/docs"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo  Server stopped.
pause
