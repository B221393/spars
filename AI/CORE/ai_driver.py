import win32gui
import win32api
import win32con
import win32ui
import time
import random
import math

import ctypes
import ctypes.wintypes
import threading
from PIL import Image, ImageDraw
import os
from datetime import datetime

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

class AIDriver:
    """
    Generic High-Performance AI Driver for Keyboard, Mouse, and Pointer overlays.
    Supports DPI-awareness, physical fallback clicks, GDI overlays, and before/after verification.
    """
    def __init__(self, target_title="Slay the Spire 2", log_dir=None):
        # Set process-wide DPI awareness
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
            print("👁️ [AIDriver] Process DPI awareness set to PER_MONITOR_AWARE_V2")
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                print("👁️ [AIDriver] Process DPI awareness set to System Aware (fallback)")
            except Exception as e:
                print(f"⚠️ [AIDriver] Failed to set DPI awareness: {e}")
                
        self.target_title = target_title
        self.hwnd = None
        self.log_dir = log_dir if log_dir else os.path.dirname(os.path.abspath(__file__))
        self.log_img_path = os.path.join(self.log_dir, "VERIFICATION_LOG.png")
        self.log_md_path = os.path.join(self.log_dir, "VERIFICATION_LOG.md")
        self.color = (255, 0, 0) # Default overlay color: Red
        self.connect()

    def connect(self):
        """Dynamically finds the window matching target_title"""
        hwnds = []
        def win_enum(h, extra):
            title = win32gui.GetWindowText(h)
            if win32gui.IsWindowVisible(h) and self.target_title.lower() in title.lower():
                extra.append(h)
        win32gui.EnumWindows(win_enum, hwnds)
        if hwnds:
            self.hwnd = hwnds[0]
            print(f"🔌 AIDriver connected to HWND {self.hwnd} ('{win32gui.GetWindowText(self.hwnd)}')")
            return True
        return False

    def check_connection(self):
        if not self.hwnd or not win32gui.IsWindow(self.hwnd):
            return self.connect()
        return True

    def get_physical_client_pos(self, x, y):
        """Converts client coordinates to high-DPI physical screen coordinates"""
        if not self.check_connection(): return x, y
        old_ctx = None
        try:
            old_ctx = ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
        except AttributeError:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except: pass
        try:
            point = ctypes.wintypes.POINT(int(x), int(y))
            ctypes.windll.user32.ClientToScreen(self.hwnd, ctypes.byref(point))
            return point.x, point.y
        finally:
            if old_ctx:
                try: ctypes.windll.user32.SetThreadDpiAwarenessContext(old_ctx)
                except: pass

    # --- Mouse operations ---
    def bezier_move(self, target_x, target_y):
        """Moves the mouse from current position to target client position using a Bezier curve"""
        if not self.check_connection(): return
        
        # Get start position in screen coordinates
        try:
            start_x, start_y = win32api.GetCursorPos()
        except:
            start_x, start_y = 0, 0
            
        # Target screen coordinates
        abs_x, abs_y = self.get_physical_client_pos(target_x, target_y)
        
        dx = abs_x - start_x
        dy = abs_y - start_y
        dist = math.hypot(dx, dy)
        
        if dist < 10:
            ctypes.windll.user32.SetCursorPos(int(abs_x), int(abs_y))
            return
            
        # Generate control points
        # Offset scale creates nice curvature
        offset_scale = dist * random.uniform(0.1, 0.3)
        
        # Control point 1 (near start)
        p1_x = start_x + dx * random.uniform(0.1, 0.4) + random.uniform(-offset_scale, offset_scale)
        p1_y = start_y + dy * random.uniform(0.1, 0.4) + random.uniform(-offset_scale, offset_scale)
        
        # Control point 2 (near end)
        p2_x = start_x + dx * random.uniform(0.6, 0.9) + random.uniform(-offset_scale, offset_scale)
        p2_y = start_y + dy * random.uniform(0.6, 0.9) + random.uniform(-offset_scale, offset_scale)
        
        # Number of steps proportional to distance
        num_steps = int(max(15, min(65, dist / 12)))
        
        for i in range(num_steps):
            t = i / (num_steps - 1)
            # Ease-in-out easing function: t = 3*t^2 - 2*t^3
            t_eased = 3 * (t ** 2) - 2 * (t ** 3)
            
            mt = 1 - t_eased
            curr_x = (mt**3 * start_x) + (3 * mt**2 * t_eased * p1_x) + (3 * mt * t_eased**2 * p2_x) + (t_eased**3 * abs_x)
            curr_y = (mt**3 * start_y) + (3 * mt**2 * t_eased * p1_y) + (3 * mt * t_eased**2 * p2_y) + (t_eased**3 * abs_y)
            
            ctypes.windll.user32.SetCursorPos(int(curr_x), int(curr_y))
            # Natural hover sleep latency
            time.sleep(random.uniform(0.005, 0.012))
            
        # Final set to be exact
        ctypes.windll.user32.SetCursorPos(int(abs_x), int(abs_y))

    def click(self, x, y, duration=0.4):
        """Performs a background click via PostMessage"""
        if not self.check_connection(): return
        lparam = win32api.MAKELONG(int(x), int(y))
        win32gui.PostMessage(self.hwnd, win32con.WM_SETCURSOR, self.hwnd, 
                             win32api.MAKELONG(win32con.HTCLIENT, win32con.WM_LBUTTONDOWN))
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(duration + random.uniform(-0.05, 0.05))
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        win32gui.InvalidateRect(self.hwnd, None, True)

    def hardware_click(self, x, y, duration=0.15, force_focus=False):
        """Performs a hardware-level click using mouse_event with Bézier curve movement"""
        if not self.check_connection(): return
        prev_hwnd = None
        prev_pos = win32api.GetCursorPos()
        
        if force_focus:
            prev_hwnd = win32gui.GetForegroundWindow()
            ctypes.windll.user32.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.2)
            
        abs_x, abs_y = self.get_physical_client_pos(x, y)
        self.bezier_move(x, y)
        time.sleep(random.uniform(0.08, 0.15)) # Small human delay before pressing down
        
        try:
            import pyautogui
            pyautogui.mouseDown()
            time.sleep(duration + random.uniform(-0.02, 0.04))
            pyautogui.mouseUp()
        except Exception as e:
            ctypes.windll.user32.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(duration + random.uniform(-0.02, 0.04))
            ctypes.windll.user32.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(random.uniform(0.1, 0.2)) # Small human delay after release
        
        if force_focus and prev_hwnd and prev_hwnd != self.hwnd:
            try:
                win32gui.SetForegroundWindow(prev_hwnd)
                ctypes.windll.user32.SetCursorPos(prev_pos[0], prev_pos[1])
            except: pass

    # --- Keyboard operations ---
    def press_key(self, key_code):
        if not self.check_connection(): return
        if isinstance(key_code, str):
            key_code = ord(key_code.upper())
        win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, key_code, 0)
        # Randomized duration between keydown and keyup
        time.sleep(random.uniform(0.05, 0.12))
        win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, key_code, 0)

    def type_string(self, text):
        if not self.check_connection(): return
        for char in text:
            win32gui.PostMessage(self.hwnd, win32con.WM_CHAR, ord(char), 0)
            # Randomized latency mimicking human speed (around 150-300 CPM)
            time.sleep(random.uniform(0.03, 0.10))

    # --- GDI Pointer Overlay ---
    def draw_pointer(self, x, y, size=30):
        """Draws a pointer target directly on screen coordinates"""
        abs_x, abs_y = self.get_physical_client_pos(x, y)
        hdc = win32gui.GetDC(0)
        pen = win32gui.CreatePen(win32con.PS_SOLID, 4, win32api.RGB(*self.color))
        old_pen = win32gui.SelectObject(hdc, pen)
        old_brush = win32gui.SelectObject(hdc, win32gui.GetStockObject(win32con.NULL_BRUSH))
        
        win32gui.Ellipse(hdc, abs_x - size, abs_y - size, abs_x + size, abs_y + size)
        
        win32gui.MoveToEx(hdc, abs_x - size - 10, abs_y)
        win32gui.LineTo(hdc, abs_x + size + 10, abs_y)
        win32gui.MoveToEx(hdc, abs_x, abs_y - size - 10)
        win32gui.LineTo(hdc, abs_x, abs_y + size + 10)

        win32gui.SelectObject(hdc, old_pen)
        win32gui.SelectObject(hdc, old_brush)
        win32gui.DeleteObject(pen)
        win32gui.ReleaseDC(0, hdc)

    def flash_pointer(self, x, y, duration=1.0):
        """Flashes the GDI pointer overlay asynchronously"""
        def _burst():
            start = time.time()
            while time.time() - start < duration:
                self.draw_pointer(x, y)
                time.sleep(0.05)
            # Clear drawing
            abs_x, abs_y = self.get_physical_client_pos(x, y)
            rect = (abs_x - 100, abs_y - 100, abs_x + 100, abs_y + 100)
            win32gui.InvalidateRect(0, rect, True)
            
        threading.Thread(target=_burst, daemon=True).start()

    # --- Screen Capture & Hash Verification ---
    def capture(self):
        """Captures the target window client area"""
        if not self.check_connection(): return None
        old_ctx = None
        try:
            old_ctx = ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
        except AttributeError:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except: pass
        try:
            left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
            w = right - left
            h = bot - top
        finally:
            if old_ctx:
                try: ctypes.windll.user32.SetThreadDpiAwarenessContext(old_ctx)
                except: pass

        if w <= 0 or h <= 0: return None
        
        hwndDC = win32gui.GetWindowDC(self.hwnd)
        mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(saveBitMap)
        
        result = ctypes.windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 2)
        if result == 0:
            result = ctypes.windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0)
        if result == 0:
            saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
            
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        
        im = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
        
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwndDC)
        return im

    def get_hash(self, img_pil):
        if img_pil is None: return ""
        small = img_pil.resize((32, 32)).convert("L")
        return list(small.getdata())

    def create_proof(self, before, after, x, y, status_text):
        """Creates a side-by-side visual proof image"""
        if not before or not after: return
        w, h = before.size
        combined = Image.new('RGB', (w * 2, h))
        combined.paste(before, (0, 0))
        combined.paste(after, (w, 0))
        
        draw = ImageDraw.Draw(combined)
        draw.ellipse([x - 15, y - 15, x + 15, y + 15], outline="red", width=3)
        draw.line([x - 25, y, x + 25, y], fill="red", width=2)
        draw.line([x, y - 25, x, y + 25], fill="red", width=2)
        
        color = (0, 255, 0) if "SUCCESS" in status_text else (255, 0, 0)
        draw.text((10, 10), f"BEFORE - {status_text}", fill=color)
        draw.text((w + 10, 10), "AFTER", fill=(255, 255, 255))
        
        combined.save(self.log_img_path)

    def write_verification_log(self, action, coord, method, result, note=""):
        """Appends a new line to the Markdown verification log"""
        if not os.path.exists(self.log_md_path):
            with open(self.log_md_path, "w", encoding="utf-8") as f:
                f.write("# 🧠 AI Verification & Progress Log\n\n")
                f.write("| Timestamp | Action | Target Coord | Input Method | Result | Proof | Note |\n")
                f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        coord_str = f"({coord[0]}, {coord[1]})"
        img_url = self.log_img_path.replace('\\', '/')
        proof_str = f"[img](file:///{img_url})" if result == "SUCCESS" else "-"
        with open(self.log_md_path, "a", encoding="utf-8") as f:
            f.write(f"| {timestamp} | {action} | {coord_str} | {method} | {result} | {proof_str} | {note} |\n")

    def execute_and_verify(self, action_name, x, y):
        """Runs the click operations sequentially with screen state verification"""
        print(f"🔍 [AIDriver] Verifying click at ({x}, {y}) for: {action_name}")
        img_before = self.capture()
        hash_before = self.get_hash(img_before)
        
        self.flash_pointer(x, y, duration=1.0)
        
        methods = [
            ("PostMessage (BG)", lambda: self.click(x, y)),
            ("Hardware Click (BG)", lambda: self.hardware_click(x, y, force_focus=False)),
            ("Hardware Click (Force Focus)", lambda: self.hardware_click(x, y, force_focus=True))
        ]
        
        success = False
        last_method = ""
        for name, method_func in methods:
            last_method = name
            print(f"👉 Attempting {name}...")
            method_func()
            time.sleep(1.5) # Wait for UI response
            
            img_after = self.capture()
            hash_after = self.get_hash(img_after)
            
            if hash_before != hash_after:
                print(f"✅ Click verify SUCCESS via {name}")
                self.create_proof(img_before, img_after, x, y, "SUCCESS")
                self.write_verification_log(action_name, (x, y), name, "SUCCESS")
                success = True
                break
            else:
                print(f"⚠️ Static state after {name}")
                self.create_proof(img_before, img_after, x, y, "STATIC_FAILED")
                self.write_verification_log(action_name, (x, y), name, "STATIC_FAILED", "No visual difference")
                
        if not success:
            print(f"❌ Click verify CRITICAL_FAILED for all methods")
            self.write_verification_log(action_name, (x, y), last_method, "CRITICAL_FAILED", "No visual change detected")
        return success
