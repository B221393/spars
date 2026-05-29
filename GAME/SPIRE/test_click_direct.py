import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

import win32gui
import win32con
import win32api
import ctypes

# Add paths
spire_dir = r"c:\Users\yu_ci\Desktop\GENRE_FOLDERS\GAME\SPIRE"
sys.path.append(spire_dir)
AI_DIR = r"c:\Users\yu_ci\Desktop\GENRE_FOLDERS\AI"
sys.path.append(AI_DIR)

from CORE.ai_driver import AIDriver

def main():
    print("Testing direct clicks on Slay the Spire 2...")
    driver = AIDriver("Slay the Spire 2")
    driver.connect()
    if not driver.hwnd:
        print("Slay the Spire 2 window not found!")
        return

    # Focus the window
    print("Focusing window...")
    win32gui.ShowWindow(driver.hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(driver.hwnd)
    time.sleep(1.0)

    # Coordinate of "シングルプレイ"
    tx, ty = 1034, 1023
    print(f"Target coordinate: ({tx}, {ty})")

    # Method 1: PostMessage (Background click)
    print("\n--- Attempting Method 1: PostMessage ---")
    driver.click(tx, ty)
    time.sleep(1.5)
    
    # Capture screen to see if changed
    img = driver.capture()
    if img:
        img.save(os.path.join(spire_dir, "capture_after_postmessage.png"))
        print("Saved capture_after_postmessage.png")

    # Method 2: Hardware click (mouse_event)
    print("\n--- Attempting Method 2: Hardware Click (mouse_event) ---")
    driver.hardware_click(tx, ty, force_focus=True)
    time.sleep(1.5)
    
    img = driver.capture()
    if img:
        img.save(os.path.join(spire_dir, "capture_after_hardware.png"))
        print("Saved capture_after_hardware.png")

if __name__ == "__main__":
    main()
