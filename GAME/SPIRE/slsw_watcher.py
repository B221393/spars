import os
import sys
import time
import json
import threading
from pynput import mouse
import win32gui
import win32process
import ctypes

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES_DIR = os.path.join(BASE_DIR, "saves")
LOG_PATH = os.path.join(SAVES_DIR, "slsw_clicks.json")

if not os.path.exists(SAVES_DIR):
    os.makedirs(SAVES_DIR)

class SLSWWatcher:
    """
    Slay the Spire Watcher (SLSW)
    An external mod-like tool to monitor and verify click locations.
    """
    def __init__(self):
        self.clicks = []
        self.active = True
        self.target_window_title = "Slay the Spire 2"
        self.lock = threading.Lock()
        
    def get_relative_coord(self, x, y, hwnd):
        """Converts screen coordinates to client window percentage."""
        rect = win32gui.GetClientRect(hwnd)
        client_x, client_y = win32gui.ClientToScreen(hwnd, (0, 0))
        
        w = rect[2]
        h = rect[3]
        
        if w <= 0 or h <= 0:
            return None
            
        rel_x = (x - client_x) / w
        rel_y = (y - client_y) / h
        
        return rel_x, rel_y, w, h

    def on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            
            if self.target_window_title in title:
                rel = self.get_relative_coord(x, y, hwnd)
                if rel:
                    rx, ry, w, h = rel
                    click_data = {
                        "timestamp": time.time(),
                        "screen_x": x,
                        "screen_y": y,
                        "rel_x": round(rx, 4),
                        "rel_y": round(ry, 4),
                        "window_w": w,
                        "window_h": h,
                        "title": title
                    }
                    print(f"🖱️ [SLSW] Click detected: ({click_data['rel_x']}, {click_data['rel_y']}) in {title}")
                    
                    with self.lock:
                        self.clicks.append(click_data)
                        self.save_clicks()

    def save_clicks(self):
        try:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.clicks[-100:], f, indent=2) # Keep last 100
        except Exception as e:
            print(f"Error saving clicks: {e}")

    def start(self):
        print(f"🚀 SLSW Watcher started. Monitoring '{self.target_window_title}'...")
        with mouse.Listener(on_click=self.on_click) as listener:
            listener.join()

if __name__ == "__main__":
    watcher = SLSWWatcher()
    watcher.start()
