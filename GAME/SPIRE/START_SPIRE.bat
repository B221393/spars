@echo off
title "Waiting for Slay the Spire..."
:loop
python -c "import win32gui; h=[]; win32gui.EnumWindows(lambda w,e: e.append(w) if win32gui.IsWindowVisible(w) and 'spire' in win32gui.GetWindowText(w).lower() else None, h); exit(0 if h else 1)"
if %errorlevel%==0 (
    echo Window found! Starting Spire loop...
    python -u "c:\Users\yu_ci\Desktop\GENRE_FOLDERS\GAME\SPIRE\spire_loop.py" "Slay the Spire 2"
) else (
    python -c "import time; time.sleep(3)"
    goto loop
)
