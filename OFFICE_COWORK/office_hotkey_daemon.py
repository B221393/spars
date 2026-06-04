import os
import sys
import time
import json
import ctypes
import ctypes.wintypes
import threading

# Adjust system path to import AIDriver and BaseBrain
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENRE_DIR = os.path.dirname(BASE_DIR)
AI_DIR = os.path.join(GENRE_DIR, "AI")
sys.path.append(AI_DIR)

from office_cowork_brain import OfficeCoworkBrain
from CORE.ai_driver import AIDriver

# Load Win32 packages
try:
    import win32gui
    import win32con
    import win32api
    import win32process
except ImportError:
    print("⚠️ Please ensure pywin32 is installed (pip install pywin32)")
    sys.exit(1)

# Global Hotkey configuration
# Modifiers: MOD_WIN (0x0008) | MOD_ALT (0x0001) = 0x0009
MOD_WIN_ALT = 0x0009

HOTKEYS = {
    1: {"vk": 0x41, "label": "Align Selected Elements", "action": "align_center", "key_name": "Win + Alt + A"},
    2: {"vk": 0x44, "label": "Apply Premium Dark Theme", "action": "theme_dark", "key_name": "Win + Alt + D"},
    3: {"vk": 0x46, "label": "Format Typography Hierarchy", "action": "heading_hierarchy", "key_name": "Win + Alt + F"},
    4: {"vk": 0x5A, "label": "Snap Office & Browser Sidebar", "action": "snap_windows", "key_name": "Win + Alt + Z"},
    5: {"vk": 0x51, "label": "Quit Hotkey Daemon", "action": "quit", "key_name": "Win + Alt + Q"},
}

class OfficeHotkeyDaemon:
    def __init__(self):
        self.driver = AIDriver("PowerPoint")
        self.brain = OfficeCoworkBrain(self.driver)
        self.brain.mode = "autoplay" # default to fast click automation
        self.running = True
        
        # Pre-warm WinRT OCR background service
        self.brain.start_ocr_service()
        
    def flash_screen_indicator(self, color=(0, 255, 255)):
        """Flashes a border around the screen boundary to indicate AI processing"""
        def _flash():
            hdc = win32gui.GetDC(0)
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
            
            pen = win32gui.CreatePen(win32con.PS_SOLID, 8, win32api.RGB(*color))
            old_pen = win32gui.SelectObject(hdc, pen)
            old_brush = win32gui.SelectObject(hdc, win32gui.GetStockObject(win32con.NULL_BRUSH))
            
            # Flash 3 times
            for _ in range(3):
                win32gui.Rectangle(hdc, 0, 0, screen_w, screen_h)
                time.sleep(0.08)
                win32gui.InvalidateRect(0, (0, 0, screen_w, screen_h), True)
                time.sleep(0.08)
                
            win32gui.SelectObject(hdc, old_pen)
            win32gui.SelectObject(hdc, old_brush)
            win32gui.DeleteObject(pen)
            win32gui.ReleaseDC(0, hdc)
            
        threading.Thread(target=_flash, daemon=True).start()

    def detect_active_app(self):
        """Detects focus and updates brain target app dynamically"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
            
        title = win32gui.GetWindowText(hwnd).lower()
        if "powerpoint" in title:
            self.brain.active_app = "PowerPoint"
            self.driver.hwnd = hwnd
            return True
        elif "excel" in title:
            self.brain.active_app = "Excel"
            self.driver.hwnd = hwnd
            return True
        elif "word" in title:
            self.brain.active_app = "Word"
            self.driver.hwnd = hwnd
            return True
            
        # Default or fallback
        return False

    def handle_hotkey(self, hotkey_id):
        config = HOTKEYS.get(hotkey_id)
        if not config:
            return
            
        action = config["action"]
        label = config["label"]
        
        print(f"🎯 [Daemon] Hotkey triggered: {config['key_name']} ({label})")
        
        if action == "quit":
            print("🏁 [Daemon] Exiting hotkey loop...")
            self.flash_screen_indicator(color=(255, 0, 0))
            self.running = False
            return
            
        # Detect app
        detected = self.detect_active_app()
        if not detected and action != "snap_windows":
            print("⚠️ [Daemon] Active window is not MS Office (PowerPoint, Excel, Word). Action skipped.")
            self.flash_screen_indicator(color=(255, 80, 0))
            return
            
        self.flash_screen_indicator(color=(0, 212, 255))
        
        # Execute action
        if action == "snap_windows":
            success, msg = self.brain.snap_windows()
            print(f"📊 Snap status: {success} - {msg}")
        else:
            success, msg = self.brain.execute_design_step(action)
            print(f"📊 Action status: {success} - {msg}")
            
        if success:
            self.flash_screen_indicator(color=(0, 255, 0))
        else:
            self.flash_screen_indicator(color=(255, 0, 0))

    def run(self):
        print("💡 [Daemon] Starting Office Hotkey Daemon...")
        user32 = ctypes.windll.user32
        
        # Register keys
        for key_id, cfg in HOTKEYS.items():
            success = user32.RegisterHotKey(None, key_id, MOD_WIN_ALT, cfg["vk"])
            if success:
                print(f"✅ Registered hotkey {cfg['key_name']} for '{cfg['label']}'")
            else:
                print(f"❌ Failed to register hotkey {cfg['key_name']}")
                
        print("\n⚡ [Daemon] Global Hotkeys registered. Focus PowerPoint/Excel/Word and press keys to execute.")
        print("🔌 Press Win + Alt + Q to quit this daemon.\n")
        
        # Message loop
        msg = ctypes.wintypes.MSG()
        try:
            while self.running:
                # Wait for hotkey messages
                if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                    if msg.message == win32con.WM_HOTKEY:
                        self.handle_hotkey(msg.message.value if hasattr(msg.message, 'value') else msg.wParam)
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            # Unregister keys
            for key_id in HOTKEYS:
                user32.UnregisterHotKey(None, key_id)
            print("🔌 [Daemon] Global Hotkeys unregistered.")

if __name__ == "__main__":
    daemon = OfficeHotkeyDaemon()
    daemon.run()
