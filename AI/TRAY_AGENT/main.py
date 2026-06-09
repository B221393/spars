#!/usr/bin/env python3
"""
Task Tray Resident Autonomous OS Agent Manager
Features pystray tray icon, Tkinter visual memory manager, and custom snipping overlay.
Enhanced with real OpenCV template matching, image previews, and scrolling logs console.
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

# Background mode states
background_mode = False
target_hwnd = None
target_window_title = "None"

# Track UI instances and last click targets
active_ui_instance = None
last_click_coord = (480, 320)
mock_stuck_simulation = False  # Set False since we have real matching now

# Win32 Constants
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

def log(msg):
    # Print to stdout
    print(f"[Tray-Agent] {msg}", flush=True)
    # Stream to UI Console if active
    global active_ui_instance
    if active_ui_instance:
        try:
            active_ui_instance.root.after(0, lambda: active_ui_instance.append_log(msg))
        except Exception:
            pass

def create_icon_image():
    """Generates a premium PlayStation Blue circular tray icon in-memory."""
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # PlayStation Blue outer ring
    d.ellipse((6, 6, 58, 58), fill=(0, 112, 209), outline=(255, 255, 255), width=3)
    # Stylized inner "A" (Agent symbol)
    d.line([(32, 16), (20, 48)], fill=(255, 255, 255), width=4)
    d.line([(32, 16), (44, 48)], fill=(255, 255, 255), width=4)
    d.line([(24, 38), (40, 38)], fill=(255, 255, 255), width=3)
    return img

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

def find_template_on_screen(screen_pil, template_path, threshold=0.85):
    """Performs template matching using OpenCV. Returns (x, y) center and max confidence value."""
    try:
        screen_np = np.array(screen_pil)
        screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        
        template = cv2.imread(template_path)
        if template is None:
            return None
            
        h, w = template.shape[:2]
        
        res = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= threshold:
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y), max_val
    except Exception as e:
        log(f"OpenCV template search error: {e}")
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
        return pyautogui.screenshot()
        
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
    global background_mode, target_hwnd, target_window_title
    log("Background autonomous worker thread started.")
    
    previous_screenshot = None
    
    while running:
        if loop_active:
            # 1. Capture screen
            if background_mode and target_hwnd and ctypes.windll.user32.IsWindow(target_hwnd):
                current_screenshot = capture_window(target_hwnd)
                target_desc = f"Window '{target_window_title}'"
            else:
                current_screenshot = pyautogui.screenshot()
                target_desc = "Primary Screen"
                
            # 2. Check for stuck state (no visual change after click)
            if previous_screenshot is not None:
                sim = compare_images(current_screenshot, previous_screenshot)
                log(f"Screen state similarity check: {sim:.2%} on {target_desc}")
                
                if sim > 0.995:
                    log("⚠️ [Stuck Detected] Visual verification failed! Auto-capturing struggle zone...")
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
                t_path = os.path.join(MEMORIES_DIR, t_file)
                
                thresh = thresholds.get(t_name, 0.85)
                
                match_result = find_template_on_screen(current_screenshot, t_path, thresh)
                if match_result:
                    coord, val = match_result
                    last_click_coord = coord
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
                
            time.sleep(4.0)
        else:
            previous_screenshot = None
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
        self.root.configure(bg="#121216")
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
        header_frame = tk.Frame(self.root, bg="#121216")
        header_frame.pack(fill="x", padx=20, pady=(15, 5))
        
        title_label = tk.Label(header_frame, text="VISUAL MEMORIES", font=("SF Pro Text", 14, "bold"), fg="#FFFFFF", bg="#121216")
        title_label.pack(side="left")
        
        subtitle_label = tk.Label(header_frame, text="TELEMETRY GRIND CONSOLE", font=("SF Pro Text", 8, "bold"), fg="#A259FF", bg="#121216")
        subtitle_label.pack(side="left", padx=10, pady=5)

        # Main Workspace Panel: Split into Left and Right Columns
        middle_paned = tk.Frame(self.root, bg="#121216")
        middle_paned.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left Column: Templates list and management buttons
        left_col = tk.Frame(middle_paned, bg="#121216")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        list_lbl = tk.Label(left_col, text="OpenCV Templates", font=("SF Pro Text", 9, "bold"), fg="#8A8A9E", bg="#121216")
        list_lbl.pack(anchor="w", pady=(0, 5))
        
        list_frame = tk.Frame(left_col, bg="#1C1C24", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        list_frame.pack(fill="both", expand=True)
        
        self.listbox = tk.Listbox(
            list_frame, bg="#0D0D11", fg="#E2E8F0", selectbackground="#A259FF",
            selectforeground="#FFFFFF", font=("Consolas", 9), bd=0, highlightthickness=0, activestyle="none"
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Template management buttons
        tpl_btn_frame = tk.Frame(left_col, bg="#121216")
        tpl_btn_frame.pack(fill="x", pady=10)
        
        self.add_btn = tk.Button(tpl_btn_frame, text="New Image (Snip)", font=("SF Pro Text", 9, "bold"), bg="#A259FF", fg="#FFFFFF", bd=0, padx=8, pady=4, command=self.start_snipping)
        self.add_btn.pack(side="left")
        
        self.del_btn = tk.Button(tpl_btn_frame, text="Delete", font=("SF Pro Text", 9, "bold"), bg="#FF1744", fg="#FFFFFF", bd=0, padx=8, pady=4, command=self.delete_memory)
        self.del_btn.pack(side="right")
        
        # Right Column: Image Preview + Active Brain Card
        right_col = tk.Frame(middle_paned, bg="#121216", width=250)
        right_col.pack(side="right", fill="both", padx=(10, 0))
        right_col.pack_propagate(False)
        
        # Thumbnail Preview Canvas
        prev_lbl = tk.Label(right_col, text="Template Image Preview", font=("SF Pro Text", 9, "bold"), fg="#8A8A9E", bg="#121216")
        prev_lbl.pack(anchor="w", pady=(0, 5))
        
        self.preview_canvas = tk.Canvas(right_col, width=230, height=130, bg="#0D0D11", highlightbackground="#2C2C3A", highlightthickness=1)
        self.preview_canvas.pack(fill="x")
        self.preview_canvas.create_text(115, 65, text="No image selected", fill="#8A8A9E", font=("SF Pro Text", 8))
        
        # Active Brain configuration details
        brain_card = tk.LabelFrame(right_col, text="Active Task Brain Configuration", font=("SF Pro Text", 9, "bold"), fg="#A259FF", bg="#121216", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        brain_card.pack(fill="both", expand=True, pady=(15, 0), ipady=5)
        
        self.brain_title_lbl = tk.Label(brain_card, text="Brain Name: None", font=("SF Pro Text", 9, "bold"), fg="#E2E8F0", bg="#121216", anchor="w")
        self.brain_title_lbl.pack(fill="x", padx=10, pady=(5, 2))
        
        self.brain_goal_lbl = tk.Label(brain_card, text="Goal: None", font=("SF Pro Text", 8), fg="#8A8A9E", bg="#121216", anchor="w", justify="left", wrap=210)
        self.brain_goal_lbl.pack(fill="x", padx=10, pady=2)
        
        self.brain_prompt_lbl = tk.Label(brain_card, text="Prompt: None", font=("SF Pro Text", 8), fg="#8A8A9E", bg="#121216", anchor="w", justify="left", wrap=210)
        self.brain_prompt_lbl.pack(fill="both", expand=True, padx=10, pady=2)

        # Background Automation Controls
        grind_frame = tk.LabelFrame(self.root, text="Background Grinding & PS Remote Play Controller", font=("SF Pro Text", 9, "bold"), fg="#00E5FF", bg="#121216", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        grind_frame.pack(fill="x", padx=20, pady=5, ipady=5)
        
        self.bg_mode_var = tk.BooleanVar(value=background_mode)
        self.bg_mode_cb = tk.Checkbutton(grind_frame, text="Enable Background Automation (Win32 API)", variable=self.bg_mode_var, font=("SF Pro Text", 9, "bold"), fg="#FFFFFF", bg="#121216", activebackground="#121216", activeforeground="#FFFFFF", selectcolor="#0D0D11", bd=0, command=self.on_bg_toggle)
        self.bg_mode_cb.pack(anchor="w", padx=15, pady=2)
        
        win_select_frame = tk.Frame(grind_frame, bg="#121216")
        win_select_frame.pack(fill="x", padx=15, pady=2)
        
        win_lbl = tk.Label(win_select_frame, text="Target Window:", font=("SF Pro Text", 9), fg="#8A8A9E", bg="#121216")
        win_lbl.pack(side="left")
        
        self.win_dropdown = ttk.Combobox(win_select_frame, state="readonly", width=52)
        self.win_dropdown.pack(side="left", padx=10)
        self.win_dropdown.bind("<<ComboboxSelected>>", self.on_window_select)
        
        self.refresh_win_btn = tk.Button(win_select_frame, text="Scan", font=("SF Pro Text", 8, "bold"), bg="#2C2C3A", fg="#E2E8F0", bd=0, padx=8, pady=3, command=self.refresh_windows_list)
        self.refresh_win_btn.pack(side="left")

        # Scrolling Logging Console Window
        console_frame = tk.LabelFrame(self.root, text="System Console Telemetry Logs", font=("SF Pro Text", 9, "bold"), fg="#FFD54F", bg="#121216", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        console_frame.pack(fill="x", padx=20, pady=5)
        
        self.console = tk.Text(console_frame, height=8, bg="#0D0D11", fg="#00FF66", font=("Consolas", 8), bd=0, wrap="word")
        self.console.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.console.config(state="disabled")
        
        con_scroll = tk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        con_scroll.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.console.config(yscrollcommand=con_scroll.set)
        
        # Bottom exit row
        bottom_frame = tk.Frame(self.root, bg="#121216")
        bottom_frame.pack(fill="x", padx=20, pady=(5, 15))
        
        self.close_btn = tk.Button(bottom_frame, text="Close Console", font=("SF Pro Text", 9, "bold"), bg="#2C2C3A", fg="#E2E8F0", bd=0, padx=12, pady=6, command=self.on_close)
        self.close_btn.pack(side="right")
        
        # Styling hover effects
        self.bind_btn_hover(self.add_btn, "#A259FF", "#B370FF")
        self.bind_btn_hover(self.del_btn, "#FF1744", "#FF4D6A")
        self.bind_btn_hover(self.refresh_win_btn, "#2C2C3A", "#3D3D4E")
        self.bind_btn_hover(self.close_btn, "#2C2C3A", "#3D3D4E")

    def append_log(self, msg):
        """Appends log text directly to the console widget."""
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
                # Resize to fit the canvas (230 x 130)
                img.thumbnail((220, 120))
                
                self.preview_photo = ImageTk.PhotoImage(img)
                self.preview_canvas.delete("all")
                # Center the thumbnail in the canvas
                self.preview_canvas.create_image(115, 65, image=self.preview_photo)
            except Exception as e:
                log(f"Failed to display thumbnail: {e}")

    def refresh_brain_profile(self):
        """Loads active brain config config and updates UI labels."""
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
                    log(f"Auto-selected game/remote play window: '{title}'")
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
        
        save_btn = tk.Button(btn_box, text="Save", font=("SF Pro Text", 9, "bold"), bg="#A259FF", fg="#FFFFFF", bd=0, padx=10, pady=4, command=save_and_close)
        save_btn.pack(side="right")
        
        cancel_btn = tk.Button(btn_box, text="Cancel", font=("SF Pro Text", 9, "bold"), bg="#2C2C3A", fg="#E2E8F0", bd=0, padx=10, pady=4, command=cancel)
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

def clean_exit(icon):
    global running
    log("Exiting application cleanly...")
    running = False
    icon.stop()
    sys.exit(0)

def main():
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
    log("Starting task tray application loop (pystray.Icon.run)...")
    icon.run()

if __name__ == "__main__":
    main()
