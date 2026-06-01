import os
import sys
import time
import random
import json
import math
import ctypes
import ctypes.wintypes
import threading
from PIL import Image

# Ensure win32 packages are loaded
try:
    import win32gui
    import win32api
    import win32con
    import win32ui
    import win32process
except ImportError:
    pass

def bot_action(func):
    """Decorator to mark a bot action and notify the human observer."""
    def wrapper(self, *args, **kwargs):
        if hasattr(self, 'human_observer') and self.human_observer:
            self.human_observer.bot_is_clicking = True
        try:
            return func(self, *args, **kwargs)
        finally:
            if hasattr(self, 'human_observer') and self.human_observer:
                time.sleep(0.05)
                self.human_observer.bot_is_clicking = False
    return wrapper

class SmartAutomator:
    """
    💪 Smart Click Automation & Verification Layer.
    Extends generic virtual input with calibration, offsets, visual verification, 
    nudge adjustments, pointer overlays, and directional feedback guides.
    """
    def __init__(self, driver, save_dir=None, learning=None, human_observer=None, cache_manager=None, 
                 settings_path=None, puppet_hints_path=None, log_path=None, hist_path=None):
        self.driver = driver
        self.learning = learning
        self.human_observer = human_observer
        self.cache_manager = cache_manager
        
        # Configure directories and paths
        self.save_dir = save_dir or os.getcwd()
        os.makedirs(self.save_dir, exist_ok=True)
        
        self.settings_path = settings_path or os.path.join(self.save_dir, "settings.json")
        self.puppet_hints_path = puppet_hints_path or os.path.join(self.save_dir, "puppet_hints.json")
        self.log_path = log_path or os.path.join(self.save_dir, "click_coordinates.log")
        self.hist_path = hist_path or os.path.join(self.save_dir, "coordinate_history.json")

    def log(self, message):
        print(f"💪 [SmartAutomator] {message}")

    def log_coordinate_event(self, action, intended, actual, offset, label, bounds=None):
        """Logs and outputs targeted (intended) vs. actual clicked coordinates with bounds and a directional guide."""
        dx = actual[0] - intended[0]
        dy = actual[1] - intended[1]
        
        ix, iy = intended
        bx1, by1, bx2, by2 = 0, 0, 0, 0
        if bounds:
            bx1, by1, bx2, by2 = bounds
        else:
            # Generate smart default bounds based on label/context
            lbl = label.lower()
            if "card" in lbl:
                bx1, by1, bx2, by2 = ix - 60, iy - 90, ix + 60, iy + 90
            elif "map" in lbl:
                bx1, by1, bx2, by2 = ix - 20, iy - 20, ix + 20, iy + 20
            else:
                bx1, by1, bx2, by2 = ix - 80, iy - 20, ix + 80, iy + 20
        
        # Log to standard console output
        print(f"🎯 [Coordinate Log] {label} ({action}):")
        print(f"  👁️ Recognition Range (Bounds): ({bx1}, {by1}) to ({bx2}, {by2})")
        print(f"  📍 Intended target:            ({ix}, {iy})")
        print(f"  🖱️ Actual touch/click:         ({actual[0]}, {actual[1]})")
        print(f"  ⚖️ Offset/Error:               (dx: {dx}, dy: {dy})")
        
        # Directional offset guide (intended is target, actual is click)
        dist = (dx**2 + dy**2)**0.5
        guide_msg = ""
        if dist <= 12:
            guide_msg = "🎯 [Guide] Target within 12px."
        else:
            x_guide = ""
            if dx > 10:
                x_guide = "左"
            elif dx < -10:
                x_guide = "右"
                
            y_guide = ""
            if dy > 10:
                y_guide = "上"
            elif dy < -10:
                y_guide = "下"
                
            direction = y_guide + x_guide
            guide_msg = f"📍 [Guide] Target is {direction} by {int(dist)}px from click position."
            
        print(guide_msg)
        
        # Log entry preparation
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "action": action,
            "intended_x": ix,
            "intended_y": iy,
            "actual_x": actual[0],
            "actual_y": actual[1],
            "bounds": [bx1, by1, bx2, by2],
            "error_dx": dx,
            "error_dy": dy,
            "offset_ox": offset[0],
            "offset_oy": offset[1],
            "label": label,
            "guide": guide_msg
        }
        
        # Read existing history
        log_entries = []
        if os.path.exists(self.hist_path):
            try:
                with open(self.hist_path, "r", encoding="utf-8") as hf:
                    log_entries = json.load(hf)
            except:
                pass
        
        log_entries.append(entry)
        log_entries = log_entries[-200:] # Keep last 200
        
        try:
            with open(self.hist_path, "w", encoding="utf-8") as hf:
                json.dump(log_entries, hf, indent=2)
            
            with open(self.log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{timestamp}] {action:<18} | Range: ({bx1:>4}, {by1:>4}) to ({bx2:>4}, {by2:>4}) | Target: ({ix:>4}, {iy:>4}) | Click: ({actual[0]:>4}, {actual[1]:>4}) | Diff: ({dx:>3}, {dy:>3}) | {label} | {guide_msg}\n")
        except Exception as e:
            print(f"⚠️ [Coordinate Log] Failed to save coordinate log: {e}")

    def flash_comparison_pointers(self, intended, actual, duration=1.5, bounds=None, label=""):
        """Flashes intended (Red) vs. actual clicked (Green) crosshairs and highlights the element range (bounds) on screen."""
        def _burst():
            start = time.time()
            orig_color = getattr(self.driver, 'color', (255, 0, 0))
            
            ix, iy = intended
            ax, ay = actual
            
            # Determine bounds
            bx1, by1, bx2, by2 = 0, 0, 0, 0
            if bounds:
                bx1, by1, bx2, by2 = bounds
            else:
                lbl = label.lower()
                if "card" in lbl:
                    bx1, by1, bx2, by2 = ix - 60, iy - 90, ix + 60, iy + 90
                elif "map" in lbl:
                    bx1, by1, bx2, by2 = ix - 20, iy - 20, ix + 20, iy + 20
                else:
                    bx1, by1, bx2, by2 = ix - 80, iy - 20, ix + 80, iy + 20
            
            # Get screen positions
            abs_ix, abs_iy = self.driver.get_physical_client_pos(ix, iy)
            abs_ax, abs_ay = self.driver.get_physical_client_pos(ax, ay)
            abs_bx1, abs_by1 = self.driver.get_physical_client_pos(bx1, by1)
            abs_bx2, abs_by2 = self.driver.get_physical_client_pos(bx2, by2)
            
            while time.time() - start < duration:
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
                except:
                    pass
                
                # Draw dots (Red = Intended, Green = Actual)
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
                
        threading.Thread(target=_burst, daemon=True).start()

    def wait_for_active_window(self):
        """Blocks execution until the target window is active, forcing focus if needed."""
        self.driver.check_connection()
        if not self.driver.hwnd:
            return
        
        if win32gui.GetForegroundWindow() != self.driver.hwnd:
            self.log("🔌 Target window lost focus. Automatically forcing focus...")
            try:
                fore_hwnd = win32gui.GetForegroundWindow()
                fore_thread_id, _ = win32process.GetWindowThreadProcessId(fore_hwnd)
                app_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
                
                attached = False
                if fore_thread_id != app_thread_id:
                    attached = ctypes.windll.user32.AttachThreadInput(app_thread_id, fore_thread_id, True)
                
                win32gui.ShowWindow(self.driver.hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.driver.hwnd)
                win32gui.BringWindowToTop(self.driver.hwnd)
                time.sleep(0.2)
                
                if attached:
                    ctypes.windll.user32.AttachThreadInput(app_thread_id, fore_thread_id, False)
                
                if win32gui.GetForegroundWindow() != self.driver.hwnd:
                    # Simulate Alt key trick
                    ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
                    win32gui.SetForegroundWindow(self.driver.hwnd)
                    ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.2)
                
                if win32gui.GetForegroundWindow() == self.driver.hwnd:
                    self.log("✅ Focus successfully restored.")
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
                self.log(f"⚠️ Failed to focus window: {e}")

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
        """Returns (width, height) of the target window client area."""
        try:
            rect = win32gui.GetClientRect(self.driver.hwnd) if self.driver.hwnd else (0, 0, 1280, 720)
        except Exception:
            rect = (0, 0, 1280, 720)
        w, h = rect[2], rect[3]
        return (w if w > 0 else 1280, h if h > 0 else 720)

    def _get_state_key(self):
        """Returns the current state key for failed click tracking."""
        if self.human_observer:
            state = getattr(self.human_observer, '_current_state', 'UNKNOWN')
            if state in ["EVENT", "UNKNOWN"]:
                return getattr(self.human_observer, '_current_screen_hash', state)
            return state
        return "UNKNOWN"

    def _should_skip_click(self, x, y, label):
        """Check if click should be skipped based on failure history. Returns True to skip."""
        if not self.learning:
            return False
        
        state = getattr(self.human_observer, '_current_state', 'UNKNOWN') if self.human_observer else 'UNKNOWN'
        is_ocr = any(kw in label.lower() for kw in ["ocr", "known", "dynamic"])
        is_restricted = state in ["MAP", "EVENT", "UNKNOWN"]
        
        if is_restricted and not is_ocr:
            w, h = self._get_client_size()
            x_pct, y_pct = x / w, y / h
            state_key = self._get_state_key()
            if self.learning.is_failed_click(state_key, x_pct, y_pct):
                self.log(f"🚫 [Learning] Skipping click at ({x}, {y}) [pct: ({x_pct:.3f}, {y_pct:.3f})] — marked as failed for state {state_key}.")
                return True
        return False

    def _read_nudge_offset(self):
        """Reads nudge dx/dy from hints file."""
        dx, dy = 0, 0
        if os.path.exists(self.puppet_hints_path):
            try:
                with open(self.puppet_hints_path, "r", encoding="utf-8") as f:
                    hints = json.load(f)
                    dx = hints.get("dx", 0)
                    dy = hints.get("dy", 0)
            except:
                pass
        return dx, dy

    def _read_calibration_offset(self):
        """Reads screen calibration offsets from settings.json."""
        offset_x, offset_y = 0, 0
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as sf:
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
    def click_position(self, coord, label="Coordinate", bounds=None):
        """Simple physical click at targeted coordinates."""
        self.wait_for_active_window()
        x, y = coord
        ox, oy = self._read_calibration_offset()
        cx = x + ox
        cy = y + oy
        
        self.log_coordinate_event("click_position", coord, (cx, cy), (ox, oy), label, bounds=bounds)
        self.flash_comparison_pointers(coord, (cx, cy), bounds=bounds, label=label)
        
        self.log(f"Clicking {label} at ({cx}, {cy})")
        self.driver.bezier_move(cx, cy)
        time.sleep(random.uniform(0.05, 0.12))
        self.driver.hardware_click(cx, cy)

    @bot_action
    def click_and_verify(self, coord, label="Target", max_shifts=5, shift_px=15, change_threshold=5.5, bounds=None, custom_verify_func=None):
        """
        Click → Verification of screen differences → If no change, try shifted coordinates.
        Finally fallbacks to screen-wide clicking.
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

        # Shift candidates
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

            self.log_coordinate_event("click_and_verify", coord, (tx, ty), (tx - coord[0], ty - coord[1]), f"{label} (shift {i})", bounds=bounds)
            self.flash_comparison_pointers(coord, (tx, ty), bounds=bounds, label=label)

            self.log(f"Clicking {label} at ({tx},{ty})" + (f" [shift #{i}]" if i > 0 else ""))
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.05, 0.12))
            self.driver.hardware_click(tx, ty)

            time.sleep(0.15)
            
            # Call custom validation telemetry if registered
            if custom_verify_func:
                custom_verify_func(target_rx, target_ry)

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
        state_key = self._get_state_key()
        if self.learning:
            self.learning.record_failed_click(state_key, x / w, y / h)

        # Fallback screen-wide clicks
        if self._fallback_screen_clicks(w, h, change_threshold):
            return True

        self.log(f"❌ click_and_verify: Could not trigger screen change at {label} after all shifts and fallbacks.")
        return False

    @bot_action
    def confirm_and_push(self, target_coord, label, eye_ref, bounds=None):
        """
        [初速のシステム - 改良版]
        1. Verify target area before click.
        2. Calibrate and try clicking with shift shifts.
        3. Trace visual screen changes to verify execution.
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
        
        # Shift candidates
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
                
            self.log_coordinate_event("confirm_and_push", target_coord, (cx, cy), (cx - target_coord[0], cy - target_coord[1]), f"{label} (shift {i})", bounds=bounds)
            self.flash_comparison_pointers(target_coord, (cx, cy), bounds=bounds, label=label)

            self.driver.bezier_move(cx, cy)
            time.sleep(random.uniform(0.08, 0.15))
            self.driver.hardware_click(cx, cy)
            self.log(f"⚡ [Push] 物理入力を送信しました。座標: ({cx}, {cy})" + (f" [シフト #{i}: ({dx}, {dy})]" if i > 0 else ""))
            
            # Check for changes in multiple steps (0.2s and 0.5s)
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
