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

    def log_coordinate_event(self, action, intended, actual, offset, label):
        """Logs and outputs targeted (intended) vs. actual clicked coordinates."""
        dx = actual[0] - intended[0]
        dy = actual[1] - intended[1]
        
        # Log to standard console output
        print(f"🎯 [Coordinate Log] {label} ({action}):")
        print(f"  📍 Intended target: ({intended[0]}, {intended[1]})")
        print(f"  🖱️ Actual click:   ({actual[0]}, {actual[1]})")
        print(f"  ⚖️ Offset/Error:   (dx: {dx}, dy: {dy})")
        
        # Log to file for analysis/corrections
        log_dir = os.path.join(BASE_DIR, "saves")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "click_coordinates.log")
        hist_path = os.path.join(log_dir, "coordinate_history.json")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "action": action,
            "intended_x": intended[0],
            "intended_y": intended[1],
            "actual_x": actual[0],
            "actual_y": actual[1],
            "error_dx": dx,
            "error_dy": dy,
            "offset_ox": offset[0],
            "offset_oy": offset[1],
            "label": label
        }
        
        # Read existing or create new list
        log_entries = []
        if os.path.exists(hist_path):
            try:
                import json
                with open(hist_path, "r", encoding="utf-8") as hf:
                    log_entries = json.load(hf)
            except:
                pass
        
        log_entries.append(entry)
        log_entries = log_entries[-200:] # Keep last 200
        
        try:
            import json
            with open(hist_path, "w", encoding="utf-8") as hf:
                json.dump(log_entries, hf, indent=2)
            
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{timestamp}] {action:<18} | Target: ({intended[0]:>4}, {intended[1]:>4}) | Click: ({actual[0]:>4}, {actual[1]:>4}) | Diff: ({dx:>3}, {dy:>3}) | {label}\n")
        except Exception as e:
            print(f"⚠️ [Coordinate Log] Failed to save coordinate log: {e}")

    def flash_comparison_pointers(self, intended, actual, duration=1.5, bounds=None, label=""):
        """Flashes intended (Red) vs. actual clicked (Green) crosshairs and highlights the element range (bounds) on screen."""
        def _burst():
            import win32gui
            import win32api
            import win32con
            
            start = time.time()
            # Save original driver color
            orig_color = getattr(self.driver, 'color', (255, 0, 0))
            
            ix, iy = intended
            ax, ay = actual
            
            # Determine bounds
            bx1, by1, bx2, by2 = 0, 0, 0, 0
            if bounds:
                bx1, by1, bx2, by2 = bounds
            else:
                # Generate smart default bounds based on label/context
                lbl = label.lower()
                if "card" in lbl:
                    # Card size: ~120x180
                    bx1, by1, bx2, by2 = ix - 60, iy - 90, ix + 60, iy + 90
                elif "map" in lbl:
                    # Map node size: ~40x40
                    bx1, by1, bx2, by2 = ix - 20, iy - 20, ix + 20, iy + 20
                else:
                    # Default button size: ~160x40
                    bx1, by1, bx2, by2 = ix - 80, iy - 20, ix + 80, iy + 20
            
            # Get screen positions
            abs_ix, abs_iy = self.driver.get_physical_client_pos(ix, iy)
            abs_ax, abs_ay = self.driver.get_physical_client_pos(ax, ay)
            abs_bx1, abs_by1 = self.driver.get_physical_client_pos(bx1, by1)
            abs_bx2, abs_by2 = self.driver.get_physical_client_pos(bx2, by2)
            
            while time.time() - start < duration:
                # 1. Draw filled range/bounding box (the "Eye" range) using a GDI cross-hatch brush
                try:
                    hdc = win32gui.GetDC(0)
                    
                    # Create an orange transparent-looking hatch brush (HS_DIAGCROSS is a crossed diagonal hatch)
                    brush = win32gui.CreateHatchBrush(win32con.HS_DIAGCROSS, win32api.RGB(255, 80, 0))
                    old_brush = win32gui.SelectObject(hdc, brush)
                    
                    # Create a solid orange pen for the border
                    pen_border = win32gui.CreatePen(win32con.PS_SOLID, 2, win32api.RGB(255, 100, 0))
                    old_pen = win32gui.SelectObject(hdc, pen_border)
                    
                    # Draw the bounding box
                    win32gui.Rectangle(hdc, abs_bx1, abs_by1, abs_bx2, abs_by2)
                    
                    # Cleanup border pen and hatch brush
                    win32gui.SelectObject(hdc, old_pen)
                    win32gui.DeleteObject(pen_border)
                    win32gui.SelectObject(hdc, old_brush)
                    win32gui.DeleteObject(brush)
                    
                    # Draw connecting yellow line
                    pen_line = win32gui.CreatePen(win32con.PS_SOLID, 2, win32api.RGB(255, 255, 0))
                    old_pen = win32gui.SelectObject(hdc, pen_line)
                    win32gui.MoveToEx(hdc, abs_ix, abs_iy)
                    win32gui.LineTo(hdc, abs_ax, abs_ay)
                    win32gui.SelectObject(hdc, old_pen)
                    win32gui.DeleteObject(pen_line)
                    
                    win32gui.ReleaseDC(0, hdc)
                except Exception as e:
                    pass
                
                # 2. Draw dots (Red = Intended, Green = Actual)
                self.driver.color = (255, 30, 30)
                self.driver.draw_pointer(ix, iy, size=8)
                
                self.driver.color = (30, 255, 30)
                self.driver.draw_pointer(ax, ay, size=8)
                
                time.sleep(0.05)
                
            self.driver.color = orig_color
            
            # Clear drawing
            try:
                rect_clear = (
                    min(abs_bx1, abs_ax) - 50,
                    min(abs_by1, abs_ay) - 50,
                    max(abs_bx2, abs_ax) + 50,
                    max(abs_by2, abs_ay) + 50
                )
                win32gui.InvalidateRect(0, rect_clear, True)
            except:
                pass
                
        import threading
        threading.Thread(target=_burst, daemon=True).start()

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

    def _get_client_size(self):
        """Returns (width, height) of the game window client area."""
        import win32gui
        try:
            rect = win32gui.GetClientRect(self.driver.hwnd) if self.driver.hwnd else (0, 0, 1280, 720)
        except Exception:
            rect = (0, 0, 1280, 720)
        w, h = rect[2], rect[3]
        return (w if w > 0 else 1280, h if h > 0 else 720)

    def _get_state_key(self):
        """Returns the current state key for failed click tracking."""
        state = getattr(self.human_observer, '_current_state', 'UNKNOWN')
        if state in ["EVENT", "UNKNOWN"]:
            return getattr(self.human_observer, '_current_screen_hash', state)
        return state

    def _should_skip_click(self, x, y, label):
        """Check if click should be skipped based on failure history. Returns True to skip."""
        state = getattr(self.human_observer, '_current_state', 'UNKNOWN')
        is_ocr = any(kw in label.lower() for kw in ["ocr", "known", "dynamic"])
        is_restricted = state in ["MAP", "EVENT", "UNKNOWN"]
        
        if is_restricted and not is_ocr:
            w, h = self._get_client_size()
            x_pct, y_pct = x / w, y / h
            state_key = self._get_state_key()
            if self.learning and self.learning.is_failed_click(state_key, x_pct, y_pct):
                self.log(f"🚫 [Learning] Skipping click at ({x}, {y}) [pct: ({x_pct:.3f}, {y_pct:.3f})] — marked as failed for state {state_key}.")
                return True
        return False

    def _read_nudge_offset(self):
        """Reads puppet nudge dx/dy from hints file."""
        dx, dy = 0, 0
        hints_path = os.path.join(BASE_DIR, "saves", "puppet_hints.json")
        if os.path.exists(hints_path):
            try:
                import json
                with open(hints_path, "r", encoding="utf-8") as f:
                    hints = json.load(f)
                    dx = hints.get("dx", 0)
                    dy = hints.get("dy", 0)
            except:
                pass
        return dx, dy

    def _read_calibration_offset(self):
        """Reads screen calibration offsets from settings.json."""
        offset_x, offset_y = 0, 0
        settings_path = os.path.join(BASE_DIR, "saves", "settings.json")
        if os.path.exists(settings_path):
            try:
                import json
                with open(settings_path, "r", encoding="utf-8") as sf:
                    settings = json.load(sf)
                    offset_x = settings.get("calibration_offset_x", 0)
                    offset_y = settings.get("calibration_offset_y", 0)
            except:
                pass
        return offset_x, offset_y

    def _fallback_screen_clicks(self, w, h, change_threshold=5.5):
        """Try clicking various screen positions to force a state change. Returns True on success."""
        self.log("⚠️ [Fallback] Trying screen-wide fallback clicks...")
        fallback_points = [
            (int(w * 0.5), int(h * 0.5)),   # Screen Center
            (int(w * 0.5), int(h * 0.8)),   # Bottom Center
            (int(w * 0.8), int(h * 0.8)),   # Bottom Right
            (int(w * 0.2), int(h * 0.8)),   # Bottom Left
            (int(w * 0.5), int(h * 0.2))    # Top Center
        ]
        for idx, (fx, fy) in enumerate(fallback_points):
            before = self._capture_small()
            if before is None:
                continue
            self.log(f"Clicking fallback point {idx+1}/5 at ({fx}, {fy})")
            self.driver.bezier_move(fx, fy)
            time.sleep(random.uniform(0.05, 0.12))
            self.driver.hardware_click(fx, fy)
            for wait_time in [0.15, 0.35]:
                time.sleep(wait_time)
                after = self._capture_small()
                if after is not None:
                    diff = self._pixel_diff(before, after)
                    if diff >= change_threshold:
                        self.log(f"  ✅ Fallback click at ({fx}, {fy}) caused screen change! (diff: {diff:.2f})")
                        return True
        return False

    @bot_action
    def click_position(self, coord, label="Coordinate"):
        """Simple physical click at targeted coordinates."""
        self.wait_for_active_window()
        x, y = coord
        ox, oy = self._read_calibration_offset()
        cx = x + ox
        cy = y + oy
        
        self.log_coordinate_event("click_position", coord, (cx, cy), (ox, oy), label)
        self.flash_comparison_pointers(coord, (cx, cy), label=label)
        
        self.log(f"Clicking {label} at ({cx}, {cy})")
        self.driver.bezier_move(cx, cy)
        time.sleep(random.uniform(0.05, 0.12))
        self.driver.hardware_click(cx, cy)

    def _read_slsw_clicks(self):
        """Reads the latest click data from SLSW watcher."""
        path = os.path.join(BASE_DIR, "saves", "slsw_clicks.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def verify_click_with_slsw(self, target_rel_x, target_rel_y):
        """
        Compares the intended click (percentage) with the last click recorded by SLSW.
        """
        clicks = self._read_slsw_clicks()
        if not clicks:
            return None
            
        last_click = clicks[-1]
        now = time.time()
        
        # Only consider recent clicks (last 3 seconds)
        if now - last_click["timestamp"] > 3.0:
            return None
            
        # Check if the click was roughly where we intended
        dx = last_click["rel_x"] - target_rel_x
        dy = last_click["rel_y"] - target_rel_y
        
        if abs(dx) < 0.1 and abs(dy) < 0.1: # Broad match to identify the specific click
            self.log(f"🎯 [SLSW Verify] Found matching click at ({last_click['rel_x']:.4f}, {last_click['rel_y']:.4f})")
            return dx, dy
        return None

    @bot_action
    def click_and_verify(self, coord, label="Target", max_shifts=5, shift_px=15, change_threshold=5.5):
        """
        クリック → 画面差分確認 → 変化なし なら少しずらして再試行。
        すべて失敗した場合は、画面のいたるところをクリックして進む。
        """
        self.wait_for_active_window()
        x, y = coord
        ox, oy = self._read_calibration_offset()
        x += ox
        y += oy
        
        w, h = self._get_client_size()
        target_rx, target_ry = x / w, y / h

        # Pre-flight: check failure history
        if self._should_skip_click(x, y, label):
            return False

        # Apply puppet nudge offset
        ndx, ndy = self._read_nudge_offset()
        if ndx != 0 or ndy != 0:
            self.log(f"👤 [Puppet Nudge] Applying nudge offset of ({ndx}, {ndy}) to click coordinates.")
            x += ndx
            y += ndy

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
            
            before = self._capture_small()
            before_full = self.driver.capture() if self.cache_manager else None

            self.log_coordinate_event("click_and_verify", coord, (tx, ty), (tx - coord[0], ty - coord[1]), f"{label} (shift {i})")
            self.flash_comparison_pointers(coord, (tx, ty), label=label)

            self.log(f"Clicking {label} at ({tx},{ty})" + (f" [shift #{i}]" if i > 0 else ""))
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.05, 0.12))
            self.driver.hardware_click(tx, ty)

            time.sleep(0.15)
            
            # Check SLSW for ground truth verification
            slsw_offset = self.verify_click_with_slsw(target_rx, target_ry)
            if slsw_offset:
                odx, ody = slsw_offset
                if abs(odx) > 0.001 or abs(ody) > 0.001:
                    self.log(f"⚖️ [SLSW Feedback] Detected systemic offset: ({odx:.4f}, {ody:.4f}). AI will calibrate.")

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
                time.sleep(0.3)

        # Record failure coordinate
        w, h = self._get_client_size()
        state_key = self._get_state_key()
        if self.learning:
            self.learning.record_failed_click(state_key, x / w, y / h)

        # Fallback screen-wide clicks
        if self._fallback_screen_clicks(w, h, change_threshold):
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
        ox, oy = self._read_calibration_offset()
        tx += ox
        ty += oy
        
        if card_idx is not None and 0 <= card_idx < 10:
            # Slay the Spire 2 uses keys '1' through '9' for card selection (and '0' for card 10)
            key_char = str((card_idx + 1) % 10)
            vk_code = 0x30 + ((card_idx + 1) % 10) # 0x30 is '0', 0x31 is '1', etc.
            
            self.log_coordinate_event("play_card_hotkey", target_coord, (tx, ty), (ox, oy), f"Card {card_idx} Target (Hotkey)")
            self.flash_comparison_pointers(target_coord, (tx, ty), label=f"Card {card_idx} Target (Hotkey)")

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
            cx += ox
            cy += oy
            
            self.log_coordinate_event("play_card_drag_start", card_coord[:2], (cx, cy), (ox, oy), "Card Drag Start")
            self.log_coordinate_event("play_card_drag_end", target_coord, (tx, ty), (ox, oy), "Card Drag Target")
            self.flash_comparison_pointers(card_coord[:2], (cx, cy), label="Card Drag Start")
            self.flash_comparison_pointers(target_coord, (tx, ty), label="Card Drag Target")

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
            self.log_coordinate_event("click_end_turn_hotkey", (0, 0), (0, 0), (0, 0), "End Turn via Hotkey E")
            time.sleep(random.uniform(0.5, 0.8))
            return True
            
        self.log(f"⚠️ Hotkey 'E' had no effect (diff: {diff:.2f}). Falling back to physical click on End Turn button.")
        bx, by = btn_coord
        ox, oy = self._read_calibration_offset()
        cx = bx + ox
        cy = by + oy
        
        self.log_coordinate_event("click_end_turn", btn_coord, (cx, cy), (ox, oy), "End Turn Button Click")
        self.flash_comparison_pointers(btn_coord, (cx, cy), label="End Turn Button Click")
        
        self.log(f"Clicking End Turn button at {cx},{cy}")
        self.driver.bezier_move(cx, cy)
        time.sleep(random.uniform(0.05, 0.15))
        self.driver.hardware_click(cx, cy)
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
        ox, oy = self._read_calibration_offset()
        tx += ox
        ty += oy

        # Pre-flight: check failure history
        if self._should_skip_click(tx, ty, label):
            return False, "Already marked as failed"

        # Apply puppet nudge offset
        ndx, ndy = self._read_nudge_offset()
        if ndx != 0 or ndy != 0:
            self.log(f"👤 [Puppet Nudge] Applying nudge offset of ({ndx}, {ndy}) to target.")
            tx += ndx
            ty += ndy
        
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
            
            before_small = self._capture_small()
            if before_small is None:
                return False, "画面の取得に失敗しました（キャプチャ不可）。"
            before_full = self.driver.capture() if self.cache_manager else None
                
            self.log_coordinate_event("confirm_and_push", target_coord, (cx, cy), (cx - target_coord[0], cy - target_coord[1]), f"{label} (shift {i})")
            self.flash_comparison_pointers(target_coord, (cx, cy), label=label)

            self.driver.bezier_move(cx, cy)
            time.sleep(random.uniform(0.08, 0.15))
            self.driver.hardware_click(cx, cy)
            self.log(f"⚡ [Push] 物理入力を送信しました。座標: ({cx}, {cy})" + (f" [シフト #{i}: ({dx}, {dy})]" if i > 0 else ""))
            
            # 0.2秒後、0.5秒後の2段階で変化を追跡
            for wait_time in [0.2, 0.5]:
                time.sleep(wait_time)
                after_small = self._capture_small()
                if after_small is not None:
                    diff = self._pixel_diff(before_small, after_small)
                    if diff > 6.0:
                        self.log(f"✅ [Shosoku] 初速を検知！ 画面変異係数: {diff:.2f}")
                        if self.cache_manager:
                            after_full = self.driver.capture()
                            self.cache_manager.save_click_proof(before_full, after_full, "success")
                        return True, "None"
            
            if self.cache_manager:
                after_full = self.driver.capture()
                self.cache_manager.save_click_proof(before_full, after_full, "no_change")
            self.log(f"⚠️ [Push Failed] 変化なし。次の座標を試します...")
            time.sleep(0.2)
            
        # Record failure coordinate
        w, h = self._get_client_size()
        state_key = self._get_state_key()
        if self.learning:
            self.learning.record_failed_click(state_key, tx / w, ty / h)

        # Fallback screen-wide clicks
        fw, fh = eye_ref.window_size
        if self._fallback_screen_clicks(fw, fh, 6.0):
            return True, "None"
                        
        return False, reason
