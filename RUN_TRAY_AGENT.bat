@echo off
title Resident Task Tray OS Agent Launcher
echo ===================================================
echo   Resident Task Tray OS Agent Launcher
echo ===================================================
echo.
echo Starting Task Tray Agent in the background...

cd /d "%~dp0AI\TRAY_AGENT"

:: Check if requirements are satisfied
python -c "import pystray, PIL, pyautogui, cv2, numpy" 2>nul
if %errorlevel% neq 0 (
    echo [Warning] Missing python dependencies. Installing requirements first...
    pip install -r requirements.txt
)

:: Launch python script silently using pythonw (no terminal window)
start "" pythonw main.py

echo.
echo [Success] Tray agent launched in the background!
echo Look for the PlayStation-themed icon in your system tray (bottom-right corner).
echo.
echo You can now use "Win + Tab" to move your target window (e.g. Slay the Spire 2, PS Remote Play) 
echo to Desktop 2 and automate it in the background while you work on Desktop 1.
echo.
pause
