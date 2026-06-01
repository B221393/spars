import os
import sys
import time
import math
import random
import win32gui
import win32api
import win32con
import ctypes
from PIL import Image

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from CORE.ai_driver import AIDriver
from CORE.smart_automator import SmartAutomator, bot_action

class Eye:
    """
    👁️ The Vision & State Sensor Layer.
    Responsible for capturing frames, analyzing screen colors, and verifying state transitions.
    """
    def __init__(self, driver: AIDriver):
        self.driver = driver

    def capture_frame(self) -> Image.Image:
        """Captures the current window screen state"""
        return self.driver.capture()

    def get_pixel(self, img: Image.Image, x: int, y: int) -> tuple:
        """Reads RGB value of a pixel in a captured PIL image"""
        if not img:
            return (0, 0, 0)
        try:
            return img.getpixel((int(x), int(y)))
        except IndexError:
            return (0, 0, 0)

    def scan_vertical_range(self, img: Image.Image, x: int, y_start: int, y_end: int, color_condition) -> bool:
        """Scans a vertical pixel slice to check if any pixel satisfies color_condition(r, g, b)"""
        if not img:
            return False
        for y in range(y_start, y_end):
            r, g, b = self.get_pixel(img, x, y)
            if color_condition(r, g, b):
                return True
        return False

    def detect_state_change(self, img_before: Image.Image, img_after: Image.Image) -> bool:
        """Compares two screenshots using low-resolution image hashing to verify if screen changed"""
        hash_before = self.driver.get_hash(img_before)
        hash_after = self.driver.get_hash(img_after)
        return hash_before != hash_after


class Body(SmartAutomator):
    """
    💪 The Physical Action Executor Layer.
    Responsible for translating coordinates into human-like cursor movements and keyboard strokes.
    Inherits robust click automation, calibration offsets, GDI overlays, and watermelon-splitting guide.
    """
    def __init__(self, driver: AIDriver, save_dir=None, learning=None, human_observer=None, cache_manager=None):
        super().__init__(
            driver=driver,
            save_dir=save_dir,
            learning=learning,
            human_observer=human_observer,
            cache_manager=cache_manager
        )

    def move_to(self, x: int, y: int):
        """Moves cursor along a smooth cubic Bezier curve (human-like speed profiles)"""
        self.driver.bezier_move(x, y)

    def click(self, x: int, y: int, hold_duration=0.15, force_focus=False):
        """Executes a natural hardware click after moving the cursor along a Bezier path"""
        self.driver.hardware_click(x, y, duration=hold_duration, force_focus=force_focus)

    def type_text(self, text: str):
        """Types characters with randomized human-like typing delays"""
        self.driver.type_string(text)

    def press_key(self, key_code: int):
        """Presses a virtual key with natural key-down hold duration"""
        self.driver.press_key(key_code)


class Head:
    """
    🧠 The Central Decision & Brain Switchboard Coordinator.
    Binds Eye and Body together, dynamically switches folder brains, and executes decision tasks.
    """
    def __init__(self, target_title="AI Rhythm"):
        self.driver = AIDriver(target_title)
        self.eye = Eye(self.driver)
        self.body = Body(self.driver)
        self.active_brain_name = "GAME"

    def execute_rhythm_game_step(self):
        """Coordinates Head-Eye-Body to play the rhythm game"""
        print("🧠 [Head] Coordinating Eye & Body to play rhythm game...")
        
        # 1. Start browser and connect
        game_url = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\GAME\RHYTHM\rhythm_game.html"
        import webbrowser
        webbrowser.open(f"file:///{game_url}")
        
        # Connect & focus
        for _ in range(10):
            if self.driver.connect():
                break
            time.sleep(1.0)
            
        if not self.driver.hwnd:
            print("🧠 [Head] Could not find window. Aborting.")
            return
            
        win32gui.SetForegroundWindow(self.driver.hwnd)
        time.sleep(1.0)
        
        # 2. Calibrate board top using Eye
        print("👁️ [Eye] Scanning screen to locate game board boundaries...")
        img = self.eye.capture_frame()
        width, height = img.size
        
        board_top = None
        center_x = width // 2
        for y in range(40, height - 100):
            r, g, b = self.eye.get_pixel(img, center_x, y)
            if 18 <= r <= 26 and 18 <= g <= 26 and 24 <= b <= 34:
                board_top = y
                break
                
        if not board_top:
            board_top = (height - 500) // 2 + 70
            
        board_left = (width - 360) // 2
        
        # Sensor points configuration
        sensor_y_start = board_top + 400
        sensor_y_end = board_top + 425
        lane_xs = [board_left + 45 + i*90 for i in range(4)]
        keys = [0x44, 0x46, 0x4A, 0x4B] # D, F, J, K
        
        # 3. Trigger Game Start using Body
        print("💪 [Body] Pressing Enter to start game...")
        self.body.press_key(win32con.VK_RETURN)
        time.sleep(0.5)
        
        # 4. Play Loop
        last_hit = [0.0] * 4
        start_time = time.time()
        
        print("🧠 [Head] Loop active: scanning notes and playing...")
        while time.time() - start_time < 15.0:
            loop_img = self.eye.capture_frame()
            if not loop_img:
                continue
                
            curr_time = time.time()
            for i in range(4):
                if curr_time - last_hit[i] < 0.15:
                    continue
                
                # Eye detects if note is present (Blue or Red color condition)
                blue_cond = lambda r, g, b: (b > 180 and r < 100)
                red_cond = lambda r, g, b: (r > 180 and b < 100)
                
                detected = self.eye.scan_vertical_range(
                    loop_img, lane_xs[i], sensor_y_start, sensor_y_end, 
                    lambda r, g, b: blue_cond(r, g, b) or red_cond(r, g, b)
                )
                
                if detected:
                    # Body executes key stroke
                    self.body.press_key(keys[i])
                    last_hit[i] = curr_time
                    print(f"🎯 [Head -> Body] Target hit in Lane {i}!")
            
            time.sleep(0.005)
            
        print("🧠 [Head] Rhythm game play complete.")

if __name__ == "__main__":
    controller = Head()
    controller.execute_rhythm_game_step()
