@echo off
echo Slay the Spire 2 の起動を待機中...
:loop
python -c "import win32gui; h=[]; win32gui.EnumWindows(lambda w,e: e.append(w) if win32gui.IsWindowVisible(w) and 'spire' in win32gui.GetWindowText(w).lower() else None, h); exit(0 if h else 1)" 2>nul
if %errorlevel%==0 (
    echo ゲームウィンドウを検出！SPIREループを起動します...
    python -u "c:\Users\yu_ci\Desktop\GENRE_FOLDERS\GAME\SPIRE\spire_loop.py" "Slay the Spire 2"
) else (
    timeout /t 3 /nobreak >nul
    goto loop
)
