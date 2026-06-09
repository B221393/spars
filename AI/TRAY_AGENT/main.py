#!/usr/bin/env python3
"""
Task Tray Resident Autonomous OS Agent Manager
Features pystray tray icon, Tkinter visual memory manager, and custom snipping overlay.
Styled after PlayStation Design Specs (Pill buttons, flat color blocks, dark canvas).
Enhanced with multi-scale template matching & self-healing minimized window restoration.
"""

import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw, ImageTk
import pyautogui
import pystray
from pystray import Menu, MenuItem
import cv2
import numpy as np
import ctypes
import ctypes.wintypes

# Reconfigure stdout/stderr to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAINS_DIR = os.path.join(BASE_DIR, "brains")
MEMORIES_DIR = os.path.join(BASE_DIR, "visual_memories")

# Ensure folders exist
os.makedirs(BRAINS_DIR, exist_ok=True)
os.makedirs(MEMORIES_DIR, exist_ok=True)

# Global configuration state
loop_active = False
active_brain = "research_brain"
running = True
global_tray_icon = None

# Background mode states
background_mode = False
target_hwnd = None
target_window_title = "None"

# Track UI instances and last click targets
active_ui_instance = None
last_click_coord = (480, 320)
mock_stuck_simulation = False

# Win32 Constants
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_SHOWNOACTIVATE = 4

# --- Custom PlayStation Pill Button Widget ---
class PillButton(tk.Canvas):
    def __init__(self, parent, text, command, bg_color="#0070d1", active_color="#0064b7", fg_color="#ffffff", width=120, height=36, font=("SF Pro Text", 9, "bold"), border_color=None, **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"), highlightthickness=0, **kwargs)
        self.text = text
        self.command = command
        self.bg_color = bg_color
        self.active_color = active_color
        self.fg_color = fg_color
        self.border_color = border_color
        self.font = font
        self.width = width
        self.height = height
        
        self.btn_state = "normal"
        self.state = "normal"
        self.bg_color_current = self.bg_color
        self.fg_color_current = self.fg_color
        
        self.draw_button()
        
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        
    def draw_button(self):
        self.delete("all")
        w = self.width
        h = self.height
        r = h  # Corner radius matches height for pill shape
        
        fill_color = self.active_color if (self.state == "active" and self.btn_state != "disabled") else self.bg_color_current
        
        self.create_oval(0, 0, r, h, fill=fill_color, outline="")
        self.create_oval(w - r, 0, w, h, fill=fill_color, outline="")
        self.create_rectangle(r // 2, 0, w - r // 2, h, fill=fill_color, outline="")
        
        if self.border_color and self.btn_state != "disabled":
            self.create_arc(0, 0, r, h, start=90, extent=180, outline=self.border_color, style="arc", width=1.5)
            self.create_arc(w - r, 0, w, h, start=270, extent=180, outline=self.border_color, style="arc", width=1.5)
            self.create_line(r // 2, 0, w - r // 2, 0, fill=self.border_color, width=1.5)
            self.create_line(r // 2, h - 1, w - r // 2, h - 1, fill=self.border_color, width=1.5)
            
        self.create_text(w // 2, h // 2, text=self.text, fill=self.fg_color_current, font=self.font)

    def on_press(self, event):
        if self.btn_state == "disabled":
            return
        self.state = "active"
        self.draw_button()
        
    def on_release(self, event):
        if self.btn_state == "disabled":
            return
        self.state = "normal"
        self.draw_button()
        if 0 <= event.x <= self.width and 0 <= event.y <= self.height:
            if self.command:
                self.command()
                
    def on_enter(self, event):
        if self.btn_state == "disabled":
            return
        self.state = "active"
        self.draw_button()
        
    def on_leave(self, event):
        if self.btn_state == "disabled":
            return
        self.state = "normal"
        self.draw_button()

    def config(self, **kwargs):
        """Overrides config to stay compatible with Tkinter button config calls."""
        if "state" in kwargs:
            self.set_state(kwargs["state"])
        if "text" in kwargs:
            self.text = kwargs["text"]
            self.draw_button()
        super().config(**{k: v for k, v in kwargs.items() if k not in ["state", "text"]})

    def configure(self, **kwargs):
        self.config(**kwargs)

    def set_state(self, state):
        self.btn_state = state
        if state == "disabled":
            self.bg_color_current = "#1C1C24"
            self.fg_color_current = "#6b6b6b"
        else:
            self.bg_color_current = self.bg_color
            self.fg_color_current = self.fg_color
        self.draw_button()

def log(msg):
    print(f"[Tray-Agent] {msg}", flush=True)
    global active_ui_instance
    if active_ui_instance:
        try:
            active_ui_instance.root.after(0, lambda: active_ui_instance.append_log(msg))
        except Exception:
            pass

def compare_images(img1, img2):
    """Compares two PIL images and returns similarity ratio (0.0 to 1.0)."""
    if img1.size != img2.size:
        return 0.0
    im1 = img1.resize((64, 64)).convert("L")
    im2 = img2.resize((64, 64)).convert("L")
    
    p1 = list(im1.getdata())
    p2 = list(im2.getdata())
    diffs = sum(abs(x - y) for x, y in zip(p1, p2))
    
    max_diff = 64 * 64 * 255
    similarity = 1.0 - (diffs / max_diff)
    return similarity

def find_template_multi_scale(screen_pil, template_path, threshold=0.85):
    """Searches for a template at multiple scales to accommodate window resizing. Returns (x, y) center and max confidence."""
    try:
        screen_np = np.array(screen_pil)
        screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        
        template = cv2.imread(template_path)
        if template is None:
            return None
            
        t_h, t_w = template.shape[:2]
        s_h, s_w = screen_bgr.shape[:2]
        
        best_val = 0.0
        best_loc = None
        best_w, best_h = t_w, t_h
        
        # Scan scales from 0.6 to 1.4 in steps of 0.1
        for scale in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]:
            sw = int(t_w * scale)
            sh = int(t_h * scale)
            
            if sw > s_w or sh > s_h or sw < 5 or sh < 5:
                continue
                
            scaled_template = cv2.resize(template, (sw, sh), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(screen_bgr, scaled_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_w = sw
                best_h = sh
                
        if best_val >= threshold:
            center_x = best_loc[0] + best_w // 2
            center_y = best_loc[1] + best_h // 2
            return (center_x, center_y), best_val
    except Exception as e:
        log(f"Multi-scale OpenCV template search error: {e}")
    return None

def scan_visible_windows():
    """Scans running applications for user-interactive visible windows."""
    windows = []
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    
    def enum_win_proc(hwnd, lparam):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                
                class_len = 256
                class_buff = ctypes.create_unicode_buffer(class_len)
                ctypes.windll.user32.GetClassNameW(hwnd, class_buff, class_len)
                class_name = class_buff.value
                
                ignore_titles = ["settings", "overlay", "nvidia", "microsoft", "task host", "input indicator"]
                if not any(k in title.lower() for k in ignore_titles) and class_name not in ["Windows.UI.Core.CoreWindow", "ApplicationFrameWindow"]:
                    windows.append((hwnd, title))
        return True
        
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_win_proc), 0)
    return windows

def capture_window(hwnd):
    """Captures a screenshot of a specific window handle, even if covered by other windows."""
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    
    if width <= 0 or height <= 0:
        return None
        
    hwndDC = ctypes.windll.user32.GetDC(hwnd)
    mfcDC = ctypes.windll.gdi32.CreateCompatibleDC(hwndDC)
    saveBitMap = ctypes.windll.gdi32.CreateCompatibleBitmap(hwndDC, width, height)
    ctypes.windll.gdi32.SelectObject(mfcDC, saveBitMap)
    
    result = ctypes.windll.user32.PrintWindow(hwnd, mfcDC, 2)
    if not result:
        ctypes.windll.gdi32.BitBlt(mfcDC, 0, 0, width, height, hwndDC, 0, 0, 0x00CC0020)
        
    bmpinfo = ctypes.wintypes.BITMAP()
    ctypes.windll.gdi32.GetObjectW(saveBitMap, ctypes.sizeof(bmpinfo), ctypes.byref(bmpinfo))
    
    bmpstr = ctypes.create_string_buffer(width * height * 4)
    ctypes.windll.gdi32.GetBitmapBits(saveBitMap, width * height * 4, bmpstr)
    
    img = Image.frombuffer("RGBA", (width, height), bmpstr, "raw", "BGRA", 0, 1)
    
    ctypes.windll.gdi32.DeleteObject(saveBitMap)
    ctypes.windll.gdi32.DeleteDC(mfcDC)
    ctypes.windll.user32.ReleaseDC(hwnd, hwndDC)
    
    return img.convert("RGB")

def send_background_click(hwnd, x, y):
    """Sends mouse click messages directly into the target window's queue."""
    if not hwnd or not ctypes.windll.user32.IsWindow(hwnd):
        return
    lParam = (y << 16) | (x & 0xFFFF)
    ctypes.windll.user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lParam)
    time.sleep(0.05)
    ctypes.windll.user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lParam)

# --- Background Worker ---
def autonomous_loop():
    """Background worker thread executing real template matching loops."""
    global loop_active, running, active_brain, last_click_coord, mock_stuck_simulation
    global background_mode, target_hwnd, target_window_title, global_tray_icon
    log("Background autonomous worker thread started.")
    
    previous_screenshot = None
    consecutive_stuck_count = 0
    last_matched_template = None
    temporary_blacklist = {}
    
    while running:
        if loop_active:
            # 1. Self-healing minimized window restoration
            current_screenshot = None
            if background_mode and target_hwnd and ctypes.windll.user32.IsWindow(target_hwnd):
                if ctypes.windll.user32.IsIconic(target_hwnd):
                    log(f"Target window is minimized. Restoring silently in background...")
                    ctypes.windll.user32.ShowWindow(target_hwnd, SW_SHOWNOACTIVATE)
                    time.sleep(0.5)
                
                current_screenshot = capture_window(target_hwnd)
                
                is_failed = False
                if current_screenshot is None:
                    is_failed = True
                else:
                    img_np = np.array(current_screenshot)
                    if img_np.size > 0 and np.std(img_np) < 1.0:
                        is_failed = True
                        log("⚠️ [Blank Frame Detected] GDI capture returned solid/black. Attempting self-healing fallback...")

                if is_failed:
                    # Self-healing: try temporary foreground mapping
                    log("Attempting self-healing: bringing target window to foreground and capturing via ClientToScreen...")
                    ctypes.windll.user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(target_hwnd)
                    time.sleep(0.4)
                    
                    rect = ctypes.wintypes.RECT()
                    ctypes.windll.user32.GetClientRect(target_hwnd, ctypes.byref(rect))
                    
                    pt_topleft = ctypes.wintypes.POINT(rect.left, rect.top)
                    ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt_topleft))
                    pt_bottomright = ctypes.wintypes.POINT(rect.right, rect.bottom)
                    ctypes.windll.user32.ClientToScreen(target_hwnd, ctypes.byref(pt_bottomright))
                    
                    scr_w = pt_bottomright.x - pt_topleft.x
                    scr_h = pt_bottomright.y - pt_topleft.y
                    
                    if scr_w > 0 and scr_h > 0:
                        try:
                            current_screenshot = pyautogui.screenshot(region=(pt_topleft.x, pt_topleft.y, scr_w, scr_h))
                            log("✅ Self-healing capture succeeded!")
                        except Exception as e:
                            log(f"❌ Screen region capture failed: {e}")
                            current_screenshot = None
                    else:
                        log("❌ Invalid client coordinates on mapped screen.")
                        current_screenshot = None
                        
                if current_screenshot is None:
                    log("❌ [Autopilot Blocked] Window screenshot failed. Skipping this cycle.")
                    time.sleep(3.0)
                    continue
                
                target_desc = f"Window '{target_window_title}'"
            else:
                current_screenshot = pyautogui.screenshot()
                target_desc = "Primary Screen"
                
            # 2. Check for stuck state (no visual change after click)
            if previous_screenshot is not None:
                sim = compare_images(current_screenshot, previous_screenshot)
                log(f"Screen state similarity check: {sim:.2%} on {target_desc}")
                
                if sim > 0.995:
                    consecutive_stuck_count += 1
                    log(f"⚠️ [Stuck Detected] Visual verification failed! Consecutive stuck count: {consecutive_stuck_count}/5")
                    
                    # Phase 2: Window Focus / Foregrounding (Cycles 3, 4)
                    if consecutive_stuck_count in [3, 4] and background_mode and target_hwnd and ctypes.windll.user32.IsWindow(target_hwnd):
                        log("⚠️ [Stuck Recovery] Restoring and bringing target window to foreground to ensure focus...")
                        ctypes.windll.user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(target_hwnd)
                        time.sleep(0.4)
                    
                    # Phase 3: Temporary Template Blacklisting (Cycle 5)
                    if consecutive_stuck_count >= 5:
                        if last_matched_template:
                            log(f"🚨 [Stuck Recovery] Template '{last_matched_template}' failed repeatedly. Blacklisting it for 3 cycles.")
                            temporary_blacklist[last_matched_template] = 3
                        else:
                            log("🚨 [Stuck Recovery] Stuck state detected, but no template name was recorded.")
                        
                        consecutive_stuck_count = 0
                    
                    cx, cy = last_click_coord
                    sw, sh = current_screenshot.size
                    
                    x1 = max(0, cx - 50)
                    y1 = max(0, cy - 50)
                    x2 = min(sw, cx + 50)
                    y2 = min(sh, cy + 50)
                    
                    if (x2 - x1) > 10 and (y2 - y1) > 10:
                        cropped = current_screenshot.crop((x1, y1, x2, y2))
                        timestamp = int(time.time())
                        filename = f"auto_struggle_{active_brain}_{timestamp}.png"
                        target_path = os.path.join(MEMORIES_DIR, filename)
                        
                        try:
                            cropped.save(target_path)
                            log(f"🧠 [Implicit Auto-Learning] Saved failed region visual memory: {filename}")
                            trigger_ui_refresh()
                        except Exception as e:
                            log(f"Failed to auto-save struggle crop: {e}")
                else:
                    consecutive_stuck_count = 0
            
            previous_screenshot = current_screenshot
            
            # 3. Load active brain config
            brain_file = os.path.join(BRAINS_DIR, f"{active_brain}.json")
            brain_name = active_brain
            goal = "No goal set"
            thresholds = {}
            
            if os.path.exists(brain_file):
                try:
                    with open(brain_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        brain_name = cfg.get("brain_name", active_brain)
                        goal = cfg.get("goal", goal)
                        thresholds = cfg.get("visual_template_thresholds", {})
                except Exception as e:
                    log(f"Error loading brain config: {e}")
            
            log(f"Autonomous Loop active | Task Brain: {brain_name} | Goal: {goal}")
            
            # Scan memories
            templates = [f for f in os.listdir(MEMORIES_DIR) if f.endswith(".png")]
            match_found = False
            
            for t_file in templates:
                t_name = t_file.replace(".png", "")
                
                # Skip blacklisted templates
                if t_name in temporary_blacklist:
                    continue
                    
                t_path = os.path.join(MEMORIES_DIR, t_file)
                thresh = thresholds.get(t_name, 0.85)
                
                # Multi-scale robust template matching
                match_result = find_template_multi_scale(current_screenshot, t_path, thresh)
                if match_result:
                    coord, val = match_result
                    
                    # Stuck Recovery Phase 1: Coordinate Nudging (Cycles 1, 2)
                    if consecutive_stuck_count in [1, 2]:
                        import random
                        dx = random.choice([-10, -8, -6, 6, 8, 10])
                        dy = random.choice([-10, -8, -6, 6, 8, 10])
                        nudged_coord = (coord[0] + dx, coord[1] + dy)
                        log(f"⚠️ [Stuck Recovery] Nudging click coordinates from {coord} to {nudged_coord} (delta: {dx}, {dy})")
                        coord = nudged_coord
                        
                    last_click_coord = coord
                    last_matched_template = t_name
                    match_found = True
                    log(f"🎯 Match found: '{t_name}' at client coordinate {coord} with confidence {val:.2f}.")
                    
                    if background_mode and target_hwnd and ctypes.windll.user32.IsWindow(target_hwnd):
                        log(f"Sending background click to {target_desc} at client coordinate {coord}")
                        send_background_click(target_hwnd, coord[0], coord[1])
                    else:
                        log(f"Sending physical click at coordinate {coord}")
                        pyautogui.click(coord[0], coord[1])
                    break
            
            if not match_found:
                log("No matching visual templates detected on screen. Autopilot waiting...")
            
            # Decrement blacklist counters
            expired_keys = []
            for k in list(temporary_blacklist.keys()):
                temporary_blacklist[k] -= 1
                if temporary_blacklist[k] <= 0:
                    expired_keys.append(k)
            for k in expired_keys:
                del temporary_blacklist[k]
                log(f"🔓 Blacklist expired for template '{k}'. Re-enabling search.")
                
            time.sleep(4.0)
        else:
            previous_screenshot = None
            consecutive_stuck_count = 0
            last_matched_template = None
            temporary_blacklist = {}
            time.sleep(1.0)

# --- Snipping Tool Overlay ---
class SnippingTool:
    def __init__(self, parent_win, on_save_callback):
        self.parent_win = parent_win
        self.on_save_callback = on_save_callback
        
        self.parent_win.withdraw()
        time.sleep(0.3)
        
        self.screenshot = pyautogui.screenshot()
        
        self.overlay = tk.Toplevel()
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.config(cursor="cross")
        
        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        
        self.canvas = tk.Canvas(self.overlay, cursor="cross", bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        
        self.rect_id = None
        self.start_x = 0
        self.start_y = 0
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.overlay.bind("<Escape>", lambda e: self.close())
        
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#00E5FF", width=2)
        
    def on_drag(self, event):
        cur_x = event.x
        cur_y = event.y
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
        
    def on_release(self, event):
        end_x = event.x
        end_y = event.y
        self.close()
        
        x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
        y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)
        
        if (x2 - x1) > 6 and (y2 - y1) > 6:
            cropped_img = self.screenshot.crop((x1, y1, x2, y2))
            self.on_save_callback(cropped_img)
        else:
            self.parent_win.deiconify()
            
    def close(self):
        self.overlay.destroy()

# --- Visual Memory Manager Settings Window ---
class MemoryManagerUI:
    def __init__(self, root):
        global active_ui_instance
        self.root = root
        active_ui_instance = self
        
        self.root.title("Visual Memory Manager & Telemetry Console")
        self.root.geometry("620x680")
        # PlayStation colors: Canvas Dark (#000000)
        self.root.configure(bg="#000000")
        self.root.resizable(False, False)
        self.root.attributes("-alpha", 0.98)
        
        self.preview_photo = None
        self.build_widgets()
        self.refresh_list()
        self.refresh_windows_list()
        self.refresh_brain_profile()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def build_widgets(self):
        # Header Badge
        header_frame = tk.Frame(self.root, bg="#000000")
        header_frame.pack(fill="x", padx=20, pady=(15, 5))
        
        title_label = tk.Label(header_frame, text="VISUAL MEMORIES", font=("SF Pro Text", 14, "bold"), fg="#FFFFFF", bg="#000000")
        title_label.pack(side="left")
        
        subtitle_label = tk.Label(header_frame, text="TELEMETRY GRIND CONSOLE", font=("SF Pro Text", 8, "bold"), fg="#0070d1", bg="#000000")
        subtitle_label.pack(side="left", padx=10, pady=5)

        # Main Workspace Panel: Split into Left and Right Columns (Surface Dark Elevated #121314)
        middle_paned = tk.Frame(self.root, bg="#121314", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        middle_paned.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left Column: Templates list and management buttons
        left_col = tk.Frame(middle_paned, bg="#121314")
        left_col.pack(side="left", fill="both", expand=True, padx=(15, 10), pady=15)
        
        list_lbl = tk.Label(left_col, text="OpenCV Templates", font=("SF Pro Text", 9, "bold"), fg="#cccccc", bg="#121314")
        list_lbl.pack(anchor="w", pady=(0, 5))
        
        # Surface Dark Card (#181818)
        list_frame = tk.Frame(left_col, bg="#181818", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        list_frame.pack(fill="both", expand=True)
        
        self.listbox = tk.Listbox(
            list_frame, bg="#0D0D11", fg="#E2E8F0", selectbackground="#0070d1",
            selectforeground="#FFFFFF", font=("Consolas", 9), bd=0, highlightthickness=0, activestyle="none"
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Template management buttons (PlayStation Pill buttons)
        tpl_btn_frame = tk.Frame(left_col, bg="#121314")
        tpl_btn_frame.pack(fill="x", pady=(10, 0))
        
        # Primary Action (PlayStation Blue #0070d1)
        self.add_btn = PillButton(tpl_btn_frame, "New Image", self.start_snipping, bg_color="#0070d1", active_color="#0064b7", width=100, height=32)
        self.add_btn.pack(side="left")
        
        # Commerce/Destructive Action (Store Orange #d53b00)
        self.del_btn = PillButton(tpl_btn_frame, "Delete", self.delete_memory, bg_color="#d53b00", active_color="#aa2f00", width=80, height=32)
        self.del_btn.pack(side="right")
        
        # Right Column: Image Preview + Active Brain Card
        right_col = tk.Frame(middle_paned, bg="#121314", width=250)
        right_col.pack(side="right", fill="both", padx=(10, 15), pady=15)
        right_col.pack_propagate(False)
        
        # Thumbnail Preview Canvas
        prev_lbl = tk.Label(right_col, text="Template Preview", font=("SF Pro Text", 9, "bold"), fg="#cccccc", bg="#121314")
        prev_lbl.pack(anchor="w", pady=(0, 5))
        
        self.preview_canvas = tk.Canvas(right_col, width=230, height=130, bg="#0D0D11", highlightbackground="#2C2C3A", highlightthickness=1)
        self.preview_canvas.pack(fill="x")
        self.preview_canvas.create_text(115, 65, text="No image selected", fill="#8A8A9E", font=("SF Pro Text", 8))
        
        # Active Brain configuration details (Surface Dark Card #181818)
        brain_card = tk.LabelFrame(right_col, text="Active Task Brain Profile", font=("SF Pro Text", 9, "bold"), fg="#0070d1", bg="#181818", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        brain_card.pack(fill="both", expand=True, pady=(15, 0), ipady=5)
        
        self.brain_title_lbl = tk.Label(brain_card, text="Brain Name: None", font=("SF Pro Text", 9, "bold"), fg="#E2E8F0", bg="#181818", anchor="w")
        self.brain_title_lbl.pack(fill="x", padx=10, pady=(5, 2))
        
        self.brain_goal_lbl = tk.Label(brain_card, text="Goal: None", font=("SF Pro Text", 8), fg="#cccccc", bg="#181818", anchor="w", justify="left", wrap=210)
        self.brain_goal_lbl.pack(fill="x", padx=10, pady=2)
        
        self.brain_prompt_lbl = tk.Label(brain_card, text="Prompt: None", font=("SF Pro Text", 8), fg="#cccccc", bg="#181818", anchor="w", justify="left", wrap=210)
        self.brain_prompt_lbl.pack(fill="both", expand=True, padx=10, pady=2)

        # Background Automation Controls (Surface Dark Elevated #121314)
        grind_frame = tk.LabelFrame(self.root, text="Background Grinding & Remote Play", font=("SF Pro Text", 9, "bold"), fg="#00E5FF", bg="#121314", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        grind_frame.pack(fill="x", padx=20, pady=5, ipady=5)
        
        self.bg_mode_var = tk.BooleanVar(value=background_mode)
        self.bg_mode_cb = tk.Checkbutton(grind_frame, text="Enable Background Automation (Win32)", variable=self.bg_mode_var, font=("SF Pro Text", 9, "bold"), fg="#FFFFFF", bg="#121314", activebackground="#121314", activeforeground="#FFFFFF", selectcolor="#0D0D11", bd=0, command=self.on_bg_toggle)
        self.bg_mode_cb.pack(anchor="w", padx=15, pady=2)
        
        win_select_frame = tk.Frame(grind_frame, bg="#121314")
        win_select_frame.pack(fill="x", padx=15, pady=2)
        
        win_lbl = tk.Label(win_select_frame, text="Target Window:", font=("SF Pro Text", 9), fg="#8A8A9E", bg="#121314")
        win_lbl.pack(side="left")
        
        self.win_dropdown = ttk.Combobox(win_select_frame, state="readonly", width=52)
        self.win_dropdown.pack(side="left", padx=10)
        self.win_dropdown.bind("<<ComboboxSelected>>", self.on_window_select)
        
        self.refresh_win_btn = PillButton(win_select_frame, "Scan", self.refresh_windows_list, bg_color="#2C2C3A", active_color="#3D3D4E", width=60, height=26, font=("SF Pro Text", 8, "bold"))
        self.refresh_win_btn.pack(side="left")

        # Scrolling Logging Console Window
        console_frame = tk.LabelFrame(self.root, text="System Console Telemetry Logs", font=("SF Pro Text", 9, "bold"), fg="#FFD54F", bg="#121314", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        console_frame.pack(fill="x", padx=20, pady=5)
        
        self.console = tk.Text(console_frame, height=8, bg="#0D0D11", fg="#00FF66", font=("Consolas", 8), bd=0, wrap="word")
        self.console.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.console.config(state="disabled")
        
        con_scroll = tk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        con_scroll.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.console.config(yscrollcommand=con_scroll.set)
        
        # Bottom exit row
        bottom_frame = tk.Frame(self.root, bg="#000000")
        bottom_frame.pack(fill="x", padx=20, pady=(5, 15))
        
        # Secondary Action: transparent background outline
        self.close_btn = PillButton(bottom_frame, "Close Console", self.on_close, bg_color="#121314", active_color="#1C1C24", border_color="#2C2C3A", width=120, height=32)
        self.close_btn.pack(side="right")

    def append_log(self, msg):
        self.console.config(state="normal")
        self.console.insert(tk.END, f"{msg}\n")
        self.console.see(tk.END)
        self.console.config(state="disabled")

    def on_listbox_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return
            
        selected_text = self.listbox.get(selection[0]).strip()
        filename = f"{selected_text}.png"
        filepath = os.path.join(MEMORIES_DIR, filename)
        
        if os.path.exists(filepath):
            try:
                img = Image.open(filepath)
                img.thumbnail((220, 120))
                self.preview_photo = ImageTk.PhotoImage(img)
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(115, 65, image=self.preview_photo)
            except Exception as e:
                log(f"Failed to display thumbnail: {e}")

    def refresh_brain_profile(self):
        brain_file = os.path.join(BRAINS_DIR, f"{active_brain}.json")
        name = active_brain
        goal = "No goal set."
        prompt = "No system prompt configured."
        
        if os.path.exists(brain_file):
            try:
                with open(brain_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    name = cfg.get("brain_name", name)
                    goal = cfg.get("goal", goal)
                    prompt = cfg.get("system_prompt", prompt)
            except Exception:
                pass
                
        self.brain_title_lbl.config(text=f"Brain Profile: {name}")
        self.brain_goal_lbl.config(text=f"Goal: {goal}")
        self.brain_prompt_lbl.config(text=f"System Prompt:\n{prompt}")

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        files = [f for f in os.listdir(MEMORIES_DIR) if f.endswith(".png")]
        if not files:
            self.listbox.insert(tk.END, "  No visual templates found.")
            self.listbox.config(state="disabled")
            self.del_btn.config(state="disabled")
        else:
            self.listbox.config(state="normal")
            self.del_btn.config(state="normal")
            for f in sorted(files):
                self.listbox.insert(tk.END, f"  {f.replace('.png', '')}")

    def refresh_windows_list(self):
        self.win_list = scan_visible_windows()
        titles = [f"{title} (HWND: {hwnd})" for hwnd, title in self.win_list]
        self.win_dropdown["values"] = titles
        
        global target_hwnd, target_window_title
        found = False
        if target_hwnd:
            for idx, (hwnd, title) in enumerate(self.win_list):
                if hwnd == target_hwnd:
                    self.win_dropdown.current(idx)
                    found = True
                    break
        
        if not found:
            for idx, (hwnd, title) in enumerate(self.win_list):
                if any(k in title.lower() for k in ["remote play", "chiaki", "spire 2"]):
                    self.win_dropdown.current(idx)
                    target_hwnd = hwnd
                    target_window_title = title
                    found = True
                    log(f"Auto-selected window: '{title}'")
                    break
                    
        if not found and titles:
            self.win_dropdown.set("Select target background window...")

    def on_window_select(self, event):
        global target_hwnd, target_window_title
        idx = self.win_dropdown.current()
        if idx >= 0:
            target_hwnd, target_window_title = self.win_list[idx]
            log(f"Target background window set to: '{target_window_title}' (HWND: {target_hwnd})")

    def on_bg_toggle(self):
        global background_mode
        background_mode = self.bg_mode_var.get()
        log(f"Background automation mode set to: {background_mode}")
        if background_mode and not target_hwnd:
            messagebox.showwarning(
                "Warning", 
                "Background mode enabled, but no target window has been selected.\n"
                "Please scan and select a target window to send background inputs.",
                parent=self.root
            )

    def start_snipping(self):
        SnippingTool(self.root, self.save_snipped_image)
        
    def save_snipped_image(self, pil_image):
        self.root.deiconify()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Visual Memory")
        dialog.geometry("360x150")
        dialog.configure(bg="#121216")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        lbl = tk.Label(dialog, text="Enter unique name for this visual memory key:", font=("SF Pro Text", 9), fg="#E2E8F0", bg="#121216")
        lbl.pack(pady=(15, 5))
        
        entry = tk.Entry(dialog, bg="#1C1C24", fg="#FFFFFF", insertbackground="#FFFFFF", font=("SF Pro Text", 10), bd=0, highlightthickness=1, highlightbackground="#2C2C3A", highlightcolor="#A259FF")
        entry.pack(fill="x", padx=20, pady=5)
        entry.insert(0, "visual_template")
        entry.focus_set()
        
        def save_and_close():
            name = entry.get().strip().replace(" ", "_")
            if not name:
                messagebox.showerror("Error", "Name cannot be empty.", parent=dialog)
                return
            
            target_path = os.path.join(MEMORIES_DIR, f"{name}.png")
            try:
                pil_image.save(target_path)
                log(f"Saved new visual memory: {target_path}")
                dialog.destroy()
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}", parent=dialog)
                
        def cancel():
            dialog.destroy()
            
        btn_box = tk.Frame(dialog, bg="#121216")
        btn_box.pack(fill="x", padx=20, pady=10)
        
        # Save button as PillButton inside dialog
        save_btn = PillButton(btn_box, "Save", save_and_close, bg_color="#0070d1", active_color="#0064b7", width=80, height=28)
        save_btn.pack(side="right")
        
        cancel_btn = PillButton(btn_box, "Cancel", cancel, bg_color="#2C2C3A", active_color="#3D3D4E", width=80, height=28)
        cancel_btn.pack(side="right", padx=10)
        
        dialog.wait_window()

    def delete_memory(self):
        selection = self.listbox.curselection()
        if not selection:
            return
            
        selected_text = self.listbox.get(selection[0]).strip()
        filename = f"{selected_text}.png"
        filepath = os.path.join(MEMORIES_DIR, filename)
        
        if os.path.exists(filepath):
            if messagebox.askyesno("Confirm Delete", f"Delete visual memory '{selected_text}'?", parent=self.root):
                try:
                    os.remove(filepath)
                    log(f"Deleted visual memory: {filepath}")
                    self.refresh_list()
                    self.preview_canvas.delete("all")
                    self.preview_canvas.create_text(115, 65, text="No image selected", fill="#8A8A9E", font=("SF Pro Text", 8))
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete file: {e}", parent=self.root)

    def on_close(self):
        global active_ui_instance
        active_ui_instance = None
        self.root.destroy()

# --- Tkinter Window Spawn Handler ---
def open_settings_ui():
    """Spawns Tkinter GUI on secondary thread."""
    global active_ui_instance
    if active_ui_instance is not None:
        try:
            active_ui_instance.root.lift()
            return
        except Exception:
            active_ui_instance = None
            
    def run_gui():
        root = tk.Tk()
        app = MemoryManagerUI(root)
        root.mainloop()
    threading.Thread(target=run_gui, daemon=True).start()

# --- Tray Right-Click Actions ---
def toggle_loop(icon, item):
    global loop_active, mock_stuck_simulation
    loop_active = not item.checked
    if loop_active:
        mock_stuck_simulation = False
    log(f"Autonomous Loop master switch toggled to: {loop_active}")
    # Dynamic tray icon visual update
    try:
        icon.icon = create_icon_image()
    except Exception as e:
        log(f"Failed to update tray icon: {e}")

def set_brain(icon, item):
    global active_brain
    active_brain = item.text
    log(f"Task Brain profile switched to: {active_brain}")
    global active_ui_instance
    if active_ui_instance:
        try:
            active_ui_instance.root.after(0, active_ui_instance.refresh_brain_profile)
        except Exception:
            pass

def get_brain_menu():
    brains = []
    if os.path.exists(BRAINS_DIR):
        for f in os.listdir(BRAINS_DIR):
            if f.endswith(".json"):
                brains.append(f.replace(".json", ""))
    
    if not brains:
        brains = ["research_brain", "files_brain"]
        
    menu_items = []
    for b in sorted(brains):
        menu_items.append(MenuItem(
            b,
            set_brain,
            checked=lambda item, b_name=b: active_brain == b_name,
            radio=True
        ))
    return menu_items

def trigger_ui_refresh():
    global active_ui_instance
    if active_ui_instance:
        try:
            active_ui_instance.root.after(0, active_ui_instance.refresh_list)
        except Exception:
            pass

def create_icon_image():
    """Generates a premium PlayStation-themed resident agent task tray icon."""
    # 64x64 transparent canvas
    image = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    
    # Choose core color based on loop activity
    global loop_active
    status_color = (0, 230, 118, 255) if loop_active else (255, 213, 79, 255) # Green if active, Yellow/amber if idle
    
    # PlayStation Dark Surface (#121314) rounded base
    dc.rounded_rectangle([2, 2, 62, 62], radius=16, fill=(18, 19, 20, 255), outline=(44, 44, 58, 255), width=2)
    # Stylized PlayStation Blue (#0070d1) inner ring
    dc.ellipse([14, 14, 50, 50], fill=None, outline=(0, 112, 209, 255), width=4)
    # A glowing status core dot for "Agent Status"
    dc.ellipse([25, 25, 39, 39], fill=status_color)
    return image

def clean_exit(icon):
    global running
    log("Exiting application cleanly...")
    running = False
    icon.stop()
    sys.exit(0)

def main():
    global global_tray_icon
    # Start background loop thread
    threading.Thread(target=autonomous_loop, daemon=True).start()
    
    # Setup pystray task tray icon
    icon_image = create_icon_image()
    
    tray_menu = Menu(
        MenuItem("自律ループ (Autonomous Loop)", toggle_loop, checked=lambda item: loop_active),
        MenuItem("タスク脳の切り替え (Brain Switch)", Menu(lambda: get_brain_menu())),
        MenuItem("視覚記憶マネージャー (Visual Memory Manager)", lambda: open_settings_ui()),
        MenuItem("終了 (Exit)", lambda icon, item: clean_exit(icon))
    )
    
    icon = pystray.Icon("TrayOSAgent", icon_image, "OS Autonomous Agent", menu=tray_menu)
    global_tray_icon = icon
    log("Starting task tray application loop (pystray.Icon.run)...")
    icon.run()

if __name__ == "__main__":
    main()
