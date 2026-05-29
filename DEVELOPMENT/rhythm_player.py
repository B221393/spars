import os
import sys
import time
import random
import ctypes
import win32gui
import win32api
import win32con
from PIL import Image

# Prevent console encoding issues on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "CORE"))
from ai_driver import AIDriver

def main():
    print("🎵 Starting AI Rhythm Game Automator...")
    
    # 1. Open the game in Microsoft Edge
    game_url = "file:///C:/Users/yu_ci/Desktop/GENRE_FOLDERS/DEVELOPMENT/rhythm_game.html"
    print(f"Opening browser for: {game_url}")
    os.system(f"start microsoft-edge:{game_url}")
    time.sleep(3.0) # Wait for page loading and window creation
    
    # 2. Connect to the window
    driver = AIDriver("AI Rhythm Training Game")
    if not driver.hwnd:
        print("❌ Could not connect to 'AI Rhythm Training Game' window.")
        return
        
    print("🎮 Successfully connected to game window.")
    
    # Bring to foreground to receive inputs properly
    win32gui.ShowWindow(driver.hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(driver.hwnd)
    time.sleep(0.5)
    
    # 3. Detect the board boundaries dynamically
    print("🔍 Calibrating board coordinates...")
    img = driver.capture()
    if not img:
        print("❌ Screen capture failed.")
        return
        
    width, height = img.size
    print(f"Window Client Area: {width}x{height}")
    
    # Find board top by scanning the center column vertically
    # Look for the transition from body background (very dark) to board background (approx 22, 22, 29)
    board_top = None
    center_x = width // 2
    for y in range(40, height - 100):
        r, g, b = img.getpixel((center_x, y))
        if 18 <= r <= 26 and 18 <= g <= 26 and 24 <= b <= 34:
            board_top = y
            break
            
    if board_top is None:
        # Fallback if detection fails
        board_top = (height - 500) // 2 + 70
        print(f"⚠️ Board boundary detection failed, using fallback: board_top={board_top}")
    else:
        print(f"✅ Board calibrated: board_top={board_top}")
        
    board_left = (width - 360) // 2
    print(f"Board position: left={board_left}, top={board_top}")
    
    # Define sensors for the 4 lanes (D, F, J, K)
    # The notes fall down. Hit line is at board_top + 440.
    # We place the sensors slightly above it (e.g. at board_top + 415) to account for lag.
    sensor_y_start = board_top + 400
    sensor_y_end = board_top + 425
    
    lane_xs = [
        board_left + 45,       # Lane 0 (D)
        board_left + 45 + 90,  # Lane 1 (F)
        board_left + 45 + 180, # Lane 2 (J)
        board_left + 45 + 270  # Lane 3 (K)
    ]
    
    keys = [0x44, 0x46, 0x4A, 0x4B] # Virtual key codes for D, F, J, K
    key_names = ['D', 'F', 'J', 'K']
    
    # 4. Trigger Game Start
    print("🚀 Triggering game start (pressing Enter)...")
    driver.press_key(win32con.VK_RETURN)
    time.sleep(0.5)
    
    # Cooldown array to prevent spamming keys on the same note
    last_hit_time = [0.0, 0.0, 0.0, 0.0]
    cooldown = 0.15 # seconds
    
    print("🔥 AI Play Loop Active! Watching notes...")
    start_time = time.time()
    
    # Play for 25 seconds
    while time.time() - start_time < 25.0:
        loop_img = driver.capture()
        if not loop_img:
            continue
            
        current_time = time.time()
        
        # Scan each lane sensor
        for i in range(4):
            if current_time - last_hit_time[i] < cooldown:
                continue
                
            lane_x = lane_xs[i]
            # Scan a vertical slice to ensure we catch fast-moving notes
            note_detected = False
            for y in range(sensor_y_start, sensor_y_end):
                r, g, b = loop_img.getpixel((lane_x, y))
                
                # Detect Blue Note (#00d4ff) or Red Note (#ff3366)
                # Blue: high blue, low red
                # Red: high red, low blue
                is_blue = (b > 180 and r < 100)
                is_red = (r > 180 and b < 100)
                
                if is_blue or is_red:
                    note_detected = True
                    break
                    
            if note_detected:
                # Press corresponding key
                win32gui.PostMessage(driver.hwnd, win32con.WM_KEYDOWN, keys[i], 0)
                time.sleep(0.02)
                win32gui.PostMessage(driver.hwnd, win32con.WM_KEYUP, keys[i], 0)
                
                last_hit_time[i] = current_time
                print(f"🎯 Lane {i} ({key_names[i]}) note hit!")
                
        # Brief sleep to yield CPU
        time.sleep(0.005)
        
    print("🏁 Rhythm game test complete.")

if __name__ == "__main__":
    main()
