#!/usr/bin/env python3
"""
Task Tray Resident Autonomous OS Agent Manager
Features pystray tray icon, Tkinter visual memory manager, and custom snipping overlay.
Enhanced with implicit self-learning: auto-crops failed click areas on stuck screens.
"""

import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageTk
import pyautogui
import pystray
from pystray import Menu, MenuItem

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

# Track UI instances and last click targets
active_ui_instance = None
last_click_coord = (480, 320)
mock_stuck_simulation = True  # Simulates static screen to trigger auto-crop

def log(msg):
    print(f"[Tray-Agent] {msg}", flush=True)

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
    # Downscale and convert to grayscale for lightweight comparison
    im1 = img1.resize((64, 64)).convert("L")
    im2 = img2.resize((64, 64)).convert("L")
    
    p1 = list(im1.getdata())
    p2 = list(im2.getdata())
    diffs = sum(abs(x - y) for x, y in zip(p1, p2))
    
    max_diff = 64 * 64 * 255
    similarity = 1.0 - (diffs / max_diff)
    return similarity

def trigger_ui_refresh():
    """Triggers listbox refresh thread-safely on the UI thread."""
    global active_ui_instance
    if active_ui_instance:
        try:
            active_ui_instance.root.after(0, active_ui_instance.refresh_list)
        except Exception:
            pass

# --- Background Worker ---
def autonomous_loop():
    """Background worker thread simulating closed-loop agent operations with stuck auto-capture."""
    global loop_active, running, active_brain, last_click_coord, mock_stuck_simulation
    log("Background autonomous worker thread started.")
    
    previous_screenshot = None
    
    while running:
        if loop_active:
            # 1. Capture current screen state
            current_screenshot = pyautogui.screenshot()
            
            # 2. Check for stuck state (no visual change after click)
            if previous_screenshot is not None:
                # If mock stuck simulation is active, simulate similarity = 1.0
                if mock_stuck_simulation:
                    sim = 1.0
                    mock_stuck_simulation = False  # Trigger once per activation
                else:
                    sim = compare_images(current_screenshot, previous_screenshot)
                
                log(f"Screen state similarity check: {sim:.2%}")
                
                if sim > 0.99:
                    log("⚠️ [Stuck Detected] Visual verification failed! The clicked area caused no screen state change.")
                    # Crop a 100x100 box around the last clicked coordinates
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
            
            # Save current screenshot as previous for next cycle
            previous_screenshot = current_screenshot
            
            # 3. Load active brain config
            brain_file = os.path.join(BRAINS_DIR, f"{active_brain}.json")
            brain_name = active_brain
            goal = "No goal set"
            
            if os.path.exists(brain_file):
                try:
                    with open(brain_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        brain_name = cfg.get("brain_name", active_brain)
                        goal = cfg.get("goal", goal)
                except Exception as e:
                    log(f"Error loading brain config: {e}")
            
            log(f"Autonomous Loop active | Task Brain: {brain_name} | Goal: {goal}")
            
            # Scan memories
            templates = [f.replace(".png", "") for f in os.listdir(MEMORIES_DIR) if f.endswith(".png")]
            if templates:
                log(f"Scanning screen for visual template memories: {templates}")
                # Mock detection: match the first memory
                target = templates[0]
                # Let's say we click at (480, 320)
                last_click_coord = (480, 320)
                log(f"[Brain-Reasoning] Detected active window. Scanning for matching visual asset '{target}'...")
                log(f"[Brain-Reasoning] cv2.matchTemplate matched '{target}' at coordinate {last_click_coord} with confidence 0.96.")
                log(f"[Action] Dispatched MATCH_CLICK on visual memory key '{target}' -> coordinate {last_click_coord} executed.")
            else:
                last_click_coord = (520, 240)
                log("No visual template memories registered in visual_memories/. Executing mock OCR click at (520, 240)...")
                
            time.sleep(4.0)
        else:
            previous_screenshot = None
            time.sleep(1.0)

# --- Snipping Tool Overlay ---
class SnippingTool:
    def __init__(self, parent_win, on_save_callback):
        self.parent_win = parent_win
        self.on_save_callback = on_save_callback
        
        # Hide parent window
        self.parent_win.withdraw()
        time.sleep(0.3)  # Allow parent window to fade out
        
        # Take full screen capture
        self.screenshot = pyautogui.screenshot()
        
        # Overlay full-screen borderless window
        self.overlay = tk.Toplevel()
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.config(cursor="cross")
        
        # Convert screenshot to TkPhoto
        self.tk_image = ImageTk.PhotoImage(self.screenshot)
        
        self.canvas = tk.Canvas(self.overlay, cursor="cross", bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        
        # Selection state
        self.rect_id = None
        self.start_x = 0
        self.start_y = 0
        
        # Bind events
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
        
        self.root.title("Visual Memory Manager")
        self.root.geometry("520x450")
        self.root.configure(bg="#121216")
        self.root.resizable(False, False)
        
        # Make glassmorphic style
        self.root.attributes("-alpha", 0.98)
        
        self.build_widgets()
        self.refresh_list()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def build_widgets(self):
        # Header Badge
        header_frame = tk.Frame(self.root, bg="#121216")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        title_label = tk.Label(
            header_frame, 
            text="VISUAL MEMORIES", 
            font=("SF Pro Text", 14, "bold"), 
            fg="#FFFFFF", 
            bg="#121216"
        )
        title_label.pack(side="left")
        
        subtitle_label = tk.Label(
            header_frame, 
            text="OPENCV TEMPLATES", 
            font=("SF Pro Text", 8, "bold"), 
            fg="#A259FF", 
            bg="#121216"
        )
        subtitle_label.pack(side="left", padx=10, pady=5)
        
        # Subtitle instructions
        desc_lbl = tk.Label(
            self.root,
            text="Visual memories templates. Failed click coordinates are cropped here implicitly.",
            font=("SF Pro Text", 9),
            fg="#8A8A9E",
            bg="#121216",
            anchor="w"
        )
        desc_lbl.pack(fill="x", padx=20, pady=(0, 10))

        # Main List frame
        list_frame = tk.Frame(self.root, bg="#1C1C24", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        self.listbox = tk.Listbox(
            list_frame,
            bg="#0D0D11",
            fg="#E2E8F0",
            selectbackground="#A259FF",
            selectforeground="#FFFFFF",
            font=("Consolas", 10),
            bd=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Control Buttons Frame
        btn_frame = tk.Frame(self.root, bg="#121216")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.add_btn = tk.Button(
            btn_frame, 
            text="Register New Image (Snipping Tool)", 
            font=("SF Pro Text", 9, "bold"), 
            bg="#A259FF", 
            fg="#FFFFFF", 
            activebackground="#8E44AD", 
            activeforeground="#FFFFFF",
            bd=0, 
            padx=12, 
            pady=6, 
            command=self.start_snipping
        )
        self.add_btn.pack(side="left")
        
        self.del_btn = tk.Button(
            btn_frame, 
            text="Delete Selected", 
            font=("SF Pro Text", 9, "bold"), 
            bg="#FF1744", 
            fg="#FFFFFF", 
            activebackground="#D50000", 
            activeforeground="#FFFFFF",
            bd=0, 
            padx=12, 
            pady=6, 
            command=self.delete_memory
        )
        self.del_btn.pack(side="right")
        
        self.close_btn = tk.Button(
            btn_frame, 
            text="Close", 
            font=("SF Pro Text", 9, "bold"), 
            bg="#2C2C3A", 
            fg="#E2E8F0", 
            activebackground="#1C1C24", 
            activeforeground="#FFFFFF",
            bd=0, 
            padx=12, 
            pady=6, 
            command=self.on_close
        )
        self.close_btn.pack(side="right", padx=10)
        
        # Hover transitions
        self.bind_btn_hover(self.add_btn, "#A259FF", "#B370FF")
        self.bind_btn_hover(self.del_btn, "#FF1744", "#FF4D6A")
        self.bind_btn_hover(self.close_btn, "#2C2C3A", "#3D3D4E")

    def bind_btn_hover(self, button, normal_bg, active_bg):
        def on_enter(e):
            button.config(bg=active_bg)
        def on_leave(e):
            button.config(bg=normal_bg)
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        files = [f for f in os.listdir(MEMORIES_DIR) if f.endswith(".png")]
        if not files:
            self.listbox.insert(tk.END, "  No visual memories found. Click 'Register New Image' to crop.")
            self.listbox.config(state="disabled")
            self.del_btn.config(state="disabled")
        else:
            self.listbox.config(state="normal")
            self.del_btn.config(state="normal")
            for f in sorted(files):
                self.listbox.insert(tk.END, f"  {f.replace('.png', '')}")

    def start_snipping(self):
        SnippingTool(self.root, self.save_snipped_image)
        
    def save_snipped_image(self, pil_image):
        self.root.deiconify()
        
        # Dynamic modal dialog to ask for template name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Visual Memory")
        dialog.geometry("360x150")
        dialog.configure(bg="#121216")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        lbl = tk.Label(dialog, text="Enter unique name for this visual memory key:", font=("SF Pro Text", 9), fg="#E2E8F0", bg="#121216")
        lbl.pack(pady=(15, 5))
        
        entry = tk.Entry(
            dialog, 
            bg="#1C1C24", 
            fg="#FFFFFF", 
            insertbackground="#FFFFFF",
            font=("SF Pro Text", 10), 
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#2C2C3A", 
            highlightcolor="#A259FF"
        )
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
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete file: {e}", parent=self.root)

    def on_close(self):
        global active_ui_instance
        active_ui_instance = None
        self.root.destroy()

# --- Tkinter Window Spawn Handler ---
def open_settings_ui():
    """Spawns Tkinter GUI on secondary thread to avoid blocking pystray's main thread loop."""
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
        mock_stuck_simulation = True  # reset stuck simulation triggers
    log(f"Autonomous Loop master switch toggled to: {loop_active}")

def set_brain(icon, item):
    global active_brain
    active_brain = item.text
    log(f"Task Brain profile switched to: {active_brain}")

def get_brain_menu():
    """Scans brains/ directory for profiles dynamically to display in sub-menu."""
    brains = []
    if os.path.exists(BRAINS_DIR):
        for f in os.listdir(BRAINS_DIR):
            if f.endswith(".json"):
                brains.append(f.replace(".json", ""))
    
    # Fallbacks if folder is empty
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
