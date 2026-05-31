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

def bot_action(func):
    def wrapper(self, *args, **kwargs):
        if hasattr(self, 'human_observer') and self.human_observer:
            self.human_observer.bot_is_clicking = True
        try:
            return func(self, *args, **kwargs)
        finally:
            if hasattr(self, 'human_observer') and self.human_observer:
                import time
                time.sleep(0.05)
                self.human_observer.bot_is_clicking = False
    return wrapper

class SpireBody:
    def __init__(self, driver, human_observer=None, cache_manager=None, learning=None):
        self.driver = driver
        self.human_observer = human_observer
        self.cache_manager = cache_manager
        self.learning = learning
        
    def log(self, message):
        print(f"💪 [Body] {message}")

    def wait_for_active_window(self):
        """Blocks execution until the game window is the active foreground window, automatically forcing focus if lost."""
        self.driver.check_connection()
        if not self.driver.hwnd:
            return
        import win32gui
        import win32con
        import win32process
        import ctypes
        import time
        
        if win32gui.GetForegroundWindow() != self.driver.hwnd:
            self.log("🔌 Game window lost focus. Automatically forcing focus...")
            try:
                # 1. Attach thread input of foreground window to ours
                fore_hwnd = win32gui.GetForegroundWindow()
                fore_thread_id, _ = win32process.GetWindowThreadProcessId(fore_hwnd)
                app_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
                
                attached = False
                if fore_thread_id != app_thread_id:
                    attached = ctypes.windll.user32.AttachThreadInput(app_thread_id, fore_thread_id, True)
                
                # 2. Show and set foreground
                win32gui.ShowWindow(self.driver.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.driver.hwnd)
                win32gui.BringWindowToTop(self.driver.hwnd)
                time.sleep(0.2)
                
                # Detach
                if attached:
                    ctypes.windll.user32.AttachThreadInput(app_thread_id, fore_thread_id, False)
                
                # 3. Double check and fallback click
                if win32gui.GetForegroundWindow() != self.driver.hwnd:
                    # Simulate Alt key trick
                    ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
                    win32gui.SetForegroundWindow(self.driver.hwnd)
                    ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.2)
                
                if win32gui.GetForegroundWindow() == self.driver.hwnd:
                    self.log("✅ Focus successfully restored to game window.")
                else:
                    self.log("⚠️ SetForegroundWindow did not succeed, trying fallback click.")
                    rect = win32gui.GetWindowRect(self.driver.hwnd)
                    click_x = rect[0] + 200
                    click_y = rect[1] + 15
                    ctypes.windll.user32.SetCursorPos(click_x, click_y)
                    time.sleep(0.1)
                    ctypes.windll.user32.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.1)
                    ctypes.windll.user32.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    time.sleep(0.2)
            except Exception as e:
                self.log(f"⚠️ Failed to automatically focus game window: {e}")

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

    @bot_action
    def click_position(self, coord, label="Coordinate"):
        """Simple physical click at targeted coordinates."""
        self.wait_for_active_window()
        x, y = coord
        self.log(f"Clicking {label} at ({x}, {y})")
        self.driver.bezier_move(x, y)
        time.sleep(random.uniform(0.05, 0.12))
        self.driver.hardware_click(x, y)

    @bot_action
    def click_and_verify(self, coord, label="Target", max_shifts=5, shift_px=15, change_threshold=2.5):
        """
        クリック → 0.1秒後に画面差分確認 → 変化なし なら少しずらして再試行。
        すべて失敗した場合は、画面のいたるところをクリックして進む。
        """
        self.wait_for_active_window()
        x, y = coord

        import win32gui
        try:
            rect = win32gui.GetClientRect(self.driver.hwnd) if self.driver.hwnd else (0, 0, 1280, 720)
        except Exception:
            rect = (0, 0, 1280, 720)
        w, h = rect[2], rect[3]

        state = getattr(self.human_observer, '_current_state', 'UNKNOWN')
        state_key = state
        if state in ["EVENT", "UNKNOWN"]:
            state_key = getattr(self.human_observer, '_current_screen_hash', state)

        # Only check/skip if it's MAP or EVENT/UNKNOWN and NOT an OCR-confirmed click
        is_ocr = any(kw in label.lower() for kw in ["ocr", "known", "dynamic"])
        is_restricted_state = state in ["MAP", "EVENT", "UNKNOWN"]
        
        if is_restricted_state and not is_ocr:
            if w > 0 and h > 0:
                x_pct = x / w
                y_pct = y / h
                if self.learning and self.learning.is_failed_click(state_key, x_pct, y_pct):
                    self.log(f"🚫 [Learning] Skipping click at ({x}, {y}) [pct: ({x_pct:.3f}, {y_pct:.3f})] because it is marked as failed/unsuitable for state {state_key}.")
                    return False

        # Read nudge offset
        dx, dy = 0, 0
        hints_path = os.path.join(BASE_DIR, "saves", "puppet_hints.json")
        if os.path.exists(hints_path):
            try:
                import json
                with open(hints_path, "r", encoding="utf-8") as f:
                    hints = json.load(f)
                    dx = hints.get("dx", 0)
                    dy = hints.get("dy", 0)
            except: pass
        if dx != 0 or dy != 0:
            self.log(f"👤 [Puppet Nudge] Applying nudge offset of ({dx}, {dy}) to click coordinates.")
            x += dx
            y += dy

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
            before_full = self.driver.capture() if self.cache_manager else None

            self.log(f"Clicking {label} at ({tx},{ty})" + (f" [shift #{i}]" if i > 0 else ""))
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.05, 0.12))
            self.driver.hardware_click(tx, ty)

            # Wait 0.15s then check if screen changed
            time.sleep(0.15)
            after = self._capture_small()
            after_full = self.driver.capture() if self.cache_manager else None
            diff = self._pixel_diff(before, after)

            self.log(f"  → Screen diff after click: {diff:.2f} (threshold: {change_threshold})")
            if diff >= change_threshold:
                self.log(f"  ✅ Click caused screen change! Proceeding.")
                if self.cache_manager:
                    self.cache_manager.save_click_proof(before_full, after_full, "success")
                return True
            else:
                self.log(f"  ⚠️ No screen change detected. {'Trying shifted position...' if i < max_shifts else 'All shifts exhausted.'}")
                if self.cache_manager:
                    self.cache_manager.save_click_proof(before_full, after_full, "no_change")
                time.sleep(0.3)  # brief pause before next attempt

        # Record failure coordinate since specific clicks failed
        if w > 0 and h > 0:
            base_x_pct = x / w
            base_y_pct = y / h
            if self.learning:
                self.learning.record_failed_click(state_key, base_x_pct, base_y_pct)

        # Fallback: click various parts of the screen to advance (e.g. for defeat/transition screens)
        self.log("⚠️ [Click Fallback] Specific target clicks failed. Trying screen-wide fallback clicks...")
        import win32gui
        try:
            rect = win32gui.GetClientRect(self.driver.hwnd) if self.driver.hwnd else (0, 0, 1280, 720)
        except Exception:
            rect = (0, 0, 1280, 720)
        w, h = rect[2], rect[3]
        if w <= 0 or h <= 0:
            w, h = 1280, 720
            
        fallback_points = [
            (int(w * 0.5), int(h * 0.5)),   # Screen Center
            (int(w * 0.5), int(h * 0.8)),   # Bottom Center
            (int(w * 0.8), int(h * 0.8)),   # Bottom Right
            (int(w * 0.2), int(h * 0.8)),   # Bottom Left
            (int(w * 0.5), int(h * 0.2))    # Top Center
        ]
        
        for idx, (fx, fy) in enumerate(fallback_points):
            before = self._capture_small()
            self.log(f"Clicking fallback point {idx+1}/5 at ({fx}, {fy})")
            self.driver.bezier_move(fx, fy)
            time.sleep(random.uniform(0.05, 0.12))
            self.driver.hardware_click(fx, fy)
            time.sleep(0.15)
            after = self._capture_small()
            diff = self._pixel_diff(before, after)
            if diff >= change_threshold:
                self.log(f"  ✅ Fallback click at ({fx}, {fy}) caused screen change! Proceeding.")
                return True

        self.log(f"❌ click_and_verify: Could not trigger screen change at {label} after all shifts and fallbacks.")
        return False

    @bot_action
    def play_card(self, card_coord, target_coord, card_idx=None):
        """
        Plays card at card_idx (using keyboard hotkey) or drags from card_coord to target_coord.
        """
        self.wait_for_active_window()
        tx, ty = target_coord
        
        if card_idx is not None and 0 <= card_idx < 10:
            # Slay the Spire 2 uses keys '1' through '9' for card selection (and '0' for card 10)
            key_char = str((card_idx + 1) % 10)
            vk_code = 0x30 + ((card_idx + 1) % 10) # 0x30 is '0', 0x31 is '1', etc.
            self.log(f"Executing card play via Hotkey: Pressing '{key_char}' for card index {card_idx}, then clicking target at ({tx}, {ty})")
            
            # Press selection key
            self.driver.press_key(vk_code)
            time.sleep(random.uniform(0.15, 0.25)) # wait for card to float to center
            
            # Move mouse to target coordinate and click
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.08, 0.15))
            self.driver.hardware_click(tx, ty)
            time.sleep(random.uniform(0.2, 0.4)) # wait for card play animation
        else:
            cx, cy = card_coord[:2]
            self.log(f"Executing card play via Dragging: dragging from {cx},{cy} to {tx},{ty}")
            
            # Move to card position naturally
            self.driver.bezier_move(cx, cy)
            time.sleep(random.uniform(0.1, 0.2))
            
            # Press down mouse
            import ctypes
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # MOUSEEVENTF_LEFTDOWN
            time.sleep(random.uniform(0.05, 0.15))
            
            # Drag to target position naturally
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.1, 0.2))
            
            # Release mouse
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # MOUSEEVENTF_LEFTUP
            time.sleep(random.uniform(0.2, 0.4)) # pause for play animation

    @bot_action
    def click_end_turn(self, btn_coord):
        """
        Ends the turn using the 'E' keyboard shortcut to minimize mouse movement and maximize reliability.
        Falls back to physical click if keyboard press does not transition screen.
        """
        self.wait_for_active_window()
        self.log("Pressing 'E' key to End Turn...")
        
        # Capture before to verify transition
        before_small = self._capture_small()
        
        # Press 'E' key (VK code for 'E' is 0x45)
        self.driver.press_key(0x45)
        time.sleep(0.3)
        
        # Check if screen changed
        after_small = self._capture_small()
        diff = self._pixel_diff(before_small, after_small)
        
        if diff >= 2.0:
            self.log(f"✅ End turn hotkey 'E' succeeded. Screen diff: {diff:.2f}")
            time.sleep(random.uniform(0.5, 0.8))
            return True
            
        self.log(f"⚠️ Hotkey 'E' had no effect (diff: {diff:.2f}). Falling back to physical click on End Turn button.")
        bx, by = btn_coord
        self.log(f"Clicking End Turn button at {bx},{by}")
        self.driver.bezier_move(bx, by)
        time.sleep(random.uniform(0.05, 0.15))
        self.driver.hardware_click(bx, by)
        time.sleep(random.uniform(0.5, 0.8)) # wait for enemy turn animation
        return True

    @bot_action
    def confirm_and_push(self, target_coord, label, eye_ref):
        """
        [初速のシステム - 改良版]
        1. 実行前にターゲットを視認(OCR等)で確認。
        2. 物理的な実行（周辺座標への自動シフト・リトライ付き）。
        3. 実行後の画面変異を検証し、変化があれば成功、なければ少しずらして再試行。
        4. それでも変化がない場合は、画面のいたるところをクリックして進む。
        """
        self.log(f"🚀 [Initial Velocity] 始動準備: '{label}' をターゲットに設定。")
        self.wait_for_active_window()
        
        tx, ty = target_coord

        import win32gui
        try:
            rect = win32gui.GetClientRect(self.driver.hwnd) if self.driver.hwnd else (0, 0, 1280, 720)
        except Exception:
            rect = (0, 0, 1280, 720)
        w, h = rect[2], rect[3]

        state = getattr(self.human_observer, '_current_state', 'UNKNOWN')
        state_key = state
        if state in ["EVENT", "UNKNOWN"]:
            state_key = getattr(self.human_observer, '_current_screen_hash', state)

        # Only check/skip if it's MAP or EVENT/UNKNOWN and NOT an OCR-confirmed click
        is_ocr = any(kw in label.lower() for kw in ["ocr", "known", "dynamic"])
        is_restricted_state = state in ["MAP", "EVENT", "UNKNOWN"]
        
        if is_restricted_state and not is_ocr:
            if w > 0 and h > 0:
                x_pct = tx / w
                y_pct = ty / h
                if self.learning and self.learning.is_failed_click(state_key, x_pct, y_pct):
                    self.log(f"🚫 [Learning] Skipping push at ({tx}, {ty}) [pct: ({x_pct:.3f}, {y_pct:.3f})] because it is marked as failed/unsuitable for state {state_key}.")
                    return False, "Already marked as failed"

        # Read nudge offset
        dx, dy = 0, 0
        hints_path = os.path.join(BASE_DIR, "saves", "puppet_hints.json")
        if os.path.exists(hints_path):
            try:
                import json
                with open(hints_path, "r", encoding="utf-8") as f:
                    hints = json.load(f)
                    dx = hints.get("dx", 0)
                    dy = hints.get("dy", 0)
            except: pass
        if dx != 0 or dy != 0:
            self.log(f"👤 [Puppet Nudge] Applying nudge offset of ({dx}, {dy}) to target.")
            tx += dx
            ty += dy
        
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
            before_full = self.driver.capture() if self.cache_manager else None
                
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
                        if self.cache_manager:
                            after_full = self.driver.capture()
                            self.cache_manager.save_click_proof(before_full, after_full, "success")
                        return True, "None"
            
            # 変化がなかった場合
            if self.cache_manager:
                after_full = self.driver.capture()
                self.cache_manager.save_click_proof(before_full, after_full, "no_change")
            self.log(f"⚠️ [Push Failed] 変化なし。次の座標を試します...")
            time.sleep(0.2)
            
        # Record failure coordinate
        if w > 0 and h > 0:
            base_x_pct = tx / w
            base_y_pct = ty / h
            if self.learning:
                self.learning.record_failed_click(state_key, base_x_pct, base_y_pct)

        # Fallback: click various parts of the screen to force state change
        self.log("⚠️ [Push Fallback] Standard shifts had no effect. Trying screen-wide fallback clicks...")
        w, h = eye_ref.window_size
        fallback_points = [
            (int(w * 0.5), int(h * 0.5)),   # Screen Center
            (int(w * 0.5), int(h * 0.8)),   # Bottom Center
            (int(w * 0.8), int(h * 0.8)),   # Bottom Right
            (int(w * 0.2), int(h * 0.8)),   # Bottom Left
            (int(w * 0.5), int(h * 0.2))    # Top Center
        ]
        
        for i, (fx, fy) in enumerate(fallback_points):
            before_small = self._capture_small()
            if before_small is None:
                continue
            self.driver.bezier_move(fx, fy)
            time.sleep(random.uniform(0.08, 0.15))
            self.driver.hardware_click(fx, fy)
            self.log(f"⚡ [Fallback Push] Clicked fallback point {i+1}/5 at ({fx}, {fy})")
            
            for wait_time in [0.2, 0.5]:
                time.sleep(wait_time)
                after_small = self._capture_small()
                if after_small is not None:
                    diff = self._pixel_diff(before_small, after_small)
                    if diff > 3.0:
                        self.log(f"✅ [Shosoku] Fallback click succeeded! Screen diff: {diff:.2f}")
                        return True, "None"
                        
        return False, reason
