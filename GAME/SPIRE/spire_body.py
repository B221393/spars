import os
import sys
import time
import random

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Add AI/CORE to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AI_CORE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AI"))
sys.path.append(AI_CORE_DIR)

class SpireBody:
    def __init__(self, driver):
        self.driver = driver
        
    def log(self, message):
        print(f"💪 [Body] {message}")

    def wait_for_active_window(self):
        """Blocks execution until the game window is the active foreground window."""
        if not self.driver.hwnd:
            return
        import win32gui
        import time
        if win32gui.GetForegroundWindow() != self.driver.hwnd:
            print("⏸️ [Body] Game window lost focus. Pausing cursor action to prevent clicking on other apps...")
            while win32gui.GetForegroundWindow() != self.driver.hwnd:
                time.sleep(0.5)
            print("▶️ [Body] Game window focused. Resuming cursor action.")

    def _capture_small(self):
        """Captures a small (64x36) image for fast diff comparison."""
        try:
            import numpy as np
            img = self.driver.capture()
            if img is None:
                return None
            import cv2
            arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            return cv2.resize(arr, (64, 36))
        except Exception:
            return None

    def _pixel_diff(self, img_a, img_b):
        """Returns mean absolute pixel difference between two small images."""
        try:
            import numpy as np
            import cv2
            if img_a is None or img_b is None:
                return 0.0
            diff = cv2.absdiff(img_a, img_b)
            return float(np.mean(diff))
        except Exception:
            return 0.0

    def click_position(self, coord, label="Coordinate"):
        """Simple physical click at targeted coordinates."""
        self.wait_for_active_window()
        x, y = coord
        self.log(f"Clicking {label} at ({x}, {y})")
        self.driver.bezier_move(x, y)
        time.sleep(random.uniform(0.05, 0.12))
        self.driver.hardware_click(x, y)

    def click_and_verify(self, coord, label="Target", max_shifts=5, shift_px=15, change_threshold=2.5):
        """
        クリック → 0.1秒後に画面差分確認 → 変化なし なら少しずらして再試行。
        Returns True if screen changed, False if all attempts failed.
        """
        self.wait_for_active_window()
        x, y = coord

        # Shift candidates: center, right, left, up, down, then diagonal combos
        shifts = [
            (0, 0),
            (shift_px, 0),
            (-shift_px, 0),
            (0, shift_px),
            (0, -shift_px),
            (shift_px, shift_px),
            (-shift_px, -shift_px),
        ]

        for i, (dx, dy) in enumerate(shifts[:max_shifts + 1]):
            tx = x + dx
            ty = y + dy
            
            # Capture before click
            before = self._capture_small()

            self.log(f"Clicking {label} at ({tx},{ty})" + (f" [shift #{i}]" if i > 0 else ""))
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.05, 0.12))
            self.driver.hardware_click(tx, ty)

            # Wait 0.1s then check if screen changed
            time.sleep(0.15)
            after = self._capture_small()
            diff = self._pixel_diff(before, after)

            self.log(f"  → Screen diff after click: {diff:.2f} (threshold: {change_threshold})")
            if diff >= change_threshold:
                self.log(f"  ✅ Click caused screen change! Proceeding.")
                return True
            else:
                self.log(f"  ⚠️ No screen change detected. {'Trying shifted position...' if i < max_shifts else 'All shifts exhausted.'}")
                time.sleep(0.3)  # brief pause before next attempt

        self.log(f"❌ click_and_verify: Could not trigger screen change at {label} after {max_shifts+1} attempts.")
        return False

    def play_card(self, card_coord, target_coord):
        """
        Drags card from card_coord to target_coord (enemy or field) using smooth Bezier travel.
        """
        self.wait_for_active_window()
        cx, cy = card_coord
        tx, ty = target_coord
        
        self.log(f"Executing card play: dragging from {cx},{cy} to {tx},{ty}")
        
        # Move to card position naturally
        self.driver.bezier_move(cx, cy)
        time.sleep(random.uniform(0.1, 0.2))
        
        # Press down mouse (using pyautogui/ctypes)
        try:
            import pyautogui
            pyautogui.mouseDown()
        except:
            import ctypes
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # MOUSEEVENTF_LEFTDOWN
        time.sleep(random.uniform(0.05, 0.15))
        
        # Drag to target position naturally
        self.driver.bezier_move(tx, ty)
        time.sleep(random.uniform(0.1, 0.2))
        
        # Release mouse to play the card
        try:
            import pyautogui
            pyautogui.mouseUp()
        except:
            import ctypes
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # MOUSEEVENTF_LEFTUP
        time.sleep(random.uniform(0.2, 0.4)) # pause for play animation

    def click_end_turn(self, btn_coord):
        """
        Moves mouse naturally to End Turn button and clicks.
        """
        self.wait_for_active_window()
        bx, by = btn_coord
        self.log(f"Clicking End Turn button at {bx},{by}")
        self.driver.bezier_move(bx, by)
        time.sleep(random.uniform(0.05, 0.15))
        self.driver.hardware_click(bx, by)
        time.sleep(random.uniform(0.5, 0.8)) # wait for enemy turn animation

    def confirm_and_push(self, target_coord, label, eye_ref):
        """
        [初速のシステム - 改良版]
        1. 実行前にターゲットを視認(OCR等)で確認。
        2. 物理的な実行（周辺座標への自動シフト・リトライ付き）。
        3. 実行後の画面変異を検証し、変化があれば成功、なければ少しずらして再試行。
        """
        self.log(f"🚀 [Initial Velocity] 始動準備: '{label}' をターゲットに設定。")
        self.wait_for_active_window()
        
        tx, ty = target_coord
        
        # Shift candidates to try if screen doesn't change
        shifts = [
            (0, 0),
            (35, 0),
            (-35, 0),
            (0, 25),
            (0, -25),
            (45, 20),
            (-45, -20)
        ]
        
        reason = "画面に変異が見られませんでした（静止状態）。"
        
        for i, (dx, dy) in enumerate(shifts):
            cx = tx + dx
            cy = ty + dy
            
            # 1. 実行前のキャプチャ (Pre-flight check)
            before_small = self._capture_small()
            if before_small is None:
                return False, "画面の取得に失敗しました（キャプチャ不可）。"
                
            # 2. 高出力実行 (High-energy Push)
            self.driver.bezier_move(cx, cy)
            time.sleep(random.uniform(0.08, 0.15))
            self.driver.hardware_click(cx, cy)
            self.log(f"⚡ [Push] 物理入力を送信しました。座標: ({cx}, {cy})" + (f" [シフト #{i}: ({dx}, {dy})]" if i > 0 else ""))
            
            # 3. 変化の検証 (Verification of displacement)
            # 0.2秒後、0.5秒後の2段階で変化を追跡
            for wait_time in [0.2, 0.5]:
                time.sleep(wait_time)
                after_small = self._capture_small()
                if after_small is not None:
                    diff = self._pixel_diff(before_small, after_small)
                    if diff > 3.0: # 明確な変異を検知
                        self.log(f"✅ [Shosoku] 初速を検知！ 画面変異係数: {diff:.2f}")
                        return True, "None"
                        
            self.log(f"⚠️ [Push Failed] 変化なし。次の座標を試します...")
            time.sleep(0.2)
            
        return False, reason
