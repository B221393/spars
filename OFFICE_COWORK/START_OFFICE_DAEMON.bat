@echo off
title Office Co-worker Hotkey Daemon
echo ===================================================
echo 🚀 Starting Office Co-worker OS Hotkey Daemon
echo ===================================================
if exist "%~dp0\dist\OfficeHotkeyDaemon.exe" (
    echo [System] Launching standalone executable...
    "%~dp0\dist\OfficeHotkeyDaemon.exe"
) else (
    echo [System] Standalone binary not found. Launching via Python...
    python "%~dp0\office_hotkey_daemon.py"
)
pause
