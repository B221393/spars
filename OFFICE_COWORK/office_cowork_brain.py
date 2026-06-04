import os
import sys
import time
import json
import re
import subprocess
import threading
import math
import numpy as np

# Adjust system path to import AIDriver and BaseBrain
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENRE_DIR = os.path.dirname(BASE_DIR)
AI_DIR = os.path.join(GENRE_DIR, "AI")
sys.path.append(AI_DIR)

from brain_switchboard import BaseBrain
from CORE.ai_driver import AIDriver

class OfficeCoworkBrain(BaseBrain):
    def __init__(self, driver: AIDriver):
        super().__init__(driver)
        self.name = "OFFICE_COWORK"
        self.status = "Idle"
        self.mode = "guide"  # "guide" or "autoplay"
        self.active_app = "PowerPoint" # "PowerPoint", "Excel", "Word"
        
        self.ocr_process = None
        self.rules = self.load_rules()
        self.log("Office Co-worker Brain initialized.")

    def load_rules(self):
        rules_path = os.path.join(BASE_DIR, "office_layout_rules.json")
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"Error loading design rules: {e}")
        return {}

    def get_target_title(self):
        if self.active_app == "PowerPoint":
            return "PowerPoint"
        elif self.active_app == "Excel":
            return "Excel"
        elif self.active_app == "Word":
            return "Word"
        return "PowerPoint"

    def connect_app(self):
        title = self.get_target_title()
        self.driver.target_title = title
        success = self.driver.connect()
        if success:
            self.log(f"Connected to active Office application: {title} (HWND: {self.driver.hwnd})")
        else:
            self.log(f"Office application '{title}' not found in active windows.")
        return success

    def snap_windows(self):
        """Resizes the active Office application to the left 75% and the browser to the right 25%"""
        import win32gui
        import win32con
        import win32api
        
        if not self.connect_app():
            return False, "Could not find Office application to snap."
            
        screen_w = win32api.GetSystemMetrics(0)
        screen_h = win32api.GetSystemMetrics(1)
        
        left_w = int(screen_w * 0.73)
        right_w = screen_w - left_w
        
        # 1. Resize PowerPoint/Excel/Word to left side
        hwnd_office = self.driver.hwnd
        win32gui.ShowWindow(hwnd_office, win32con.SW_RESTORE)
        win32gui.SetWindowPos(hwnd_office, win32con.HWND_TOP, 0, 0, left_w, screen_h - 40, win32con.SWP_SHOWWINDOW)
        self.log(f"Snapped {self.active_app} to left side (width: {left_w}).")
        
        # 2. Resize browser/sidebar (look for browser window)
        hwnd_browser = None
        browser_keywords = ["chrome", "edge", "mythos", "firefox", "browser", "antigravity"]
        
        def win_enum(h, extra):
            nonlocal hwnd_browser
            if win32gui.IsWindowVisible(h):
                title = win32gui.GetWindowText(h).lower()
                if any(kw in title for kw in browser_keywords) and h != hwnd_office:
                    hwnd_browser = h
                    
        win32gui.EnumWindows(win_enum, None)
        
        if hwnd_browser:
            win32gui.ShowWindow(hwnd_browser, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd_browser, win32con.HWND_TOP, left_w, 0, right_w, screen_h - 40, win32con.SWP_SHOWWINDOW)
            self.log(f"Snapped Browser to right side (width: {right_w}).")
            return True, "Successfully snapped windows side-by-side!"
        else:
            return True, "Office snapped to left. Browser window not found (please manually place browser on the right)."

    # --- OCR service integration ---
    def start_ocr_service(self):
        if self.ocr_process is not None and self.ocr_process.poll() is None:
            return True
            
        # Use existing OCR service in SPIRE directory
        ps_script = os.path.join(GENRE_DIR, "GAME", "SPIRE", "ocr_service.ps1")
        if not os.path.exists(ps_script):
            self.log(f"OCR service script not found at {ps_script}")
            return False
            
        try:
            self.log("Starting WinRT OCR service...")
            self.ocr_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", ps_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1
            )
            ready_line = self.ocr_process.stdout.readline().strip()
            if ready_line == "READY":
                self.log("WinRT OCR service connected.")
                return True
        except Exception as e:
            self.log(f"Failed to start OCR service: {e}")
            self.ocr_process = None
        return False

    def perform_ocr(self):
        """Grabs active Office window screen, runs OCR, returns list of words with coordinates"""
        if not self.driver.hwnd:
            return []
        
        # Capture screen
        img = self.driver.capture()
        if img is None:
            return []
            
        # Save temp file
        temp_path = os.path.join(BASE_DIR, "temp_ocr.png")
        img.save(temp_path)
        
        if not self.start_ocr_service():
            return []
            
        try:
            # Send file path to powershell process
            self.ocr_process.stdin.write(temp_path + "\n")
            self.ocr_process.stdin.flush()
            
            response = self.ocr_process.stdout.readline().strip()
            if response.startswith("OK:"):
                import base64
                b64_data = response[3:]
                json_str = base64.b64decode(b64_data).decode("utf-8")
                words = json.loads(json_str)
                # Cleanup temp file
                try: os.remove(temp_path)
                except: pass
                return words
        except Exception as e:
            self.log(f"OCR transaction failed: {e}")
        return []

    # --- Menu Option Positioning ---
    def find_menu_option(self, keywords):
        """Runs OCR and finds coordinates of the target text (e.g. 'ホーム', '挿入')"""
        words = self.perform_ocr()
        for w_data in words:
            txt = w_data['text'].lower()
            if any(kw in txt for kw in keywords):
                cx = w_data['x'] + w_data['w'] // 2
                cy = w_data['y'] + w_data['h'] // 2
                return (cx, cy)
        return None

    def execute_design_step(self, action_name):
        """Formulates and executes the click instructions based on the selected action"""
        if not self.connect_app():
            return False, "Active window not found. Please open PowerPoint/Excel/Word first."

        self.log(f"Executing design action '{action_name}' in {self.mode.upper()} mode...")
        
        # Recipes mapping
        if self.active_app == "PowerPoint":
            return self.run_pptx_recipe(action_name)
        elif self.active_app == "Excel":
            return self.run_excel_recipe(action_name)
        elif self.active_app == "Word":
            return self.run_word_recipe(action_name)
            
        return False, "Unrecognized application type."

    def trigger_visual_action(self, label, coord, keys_fallback=None):
        """Handles action by either guide overlay or physical click based on mode"""
        if not coord and keys_fallback:
            # If coordinates not found, try sending keyboard keys directly
            self.log(f"Coordinates for '{label}' not found. Using keyboard fallback sequence: {keys_fallback}")
            if self.mode == "autoplay":
                self.driver.type_string(keys_fallback)
                time.sleep(0.5)
            return True
            
        if not coord:
            return False
            
        if self.mode == "guide":
            self.log(f"[GUIDE MODE] Flashing target overlay at {coord} for '{label}'")
            self.driver.flash_pointer(coord[0], coord[1], duration=2.5)
            return True
        else:
            self.log(f"[AUTOPLAY MODE] Clicking '{label}' at {coord}")
            self.driver.execute_and_verify(label, coord[0], coord[1])
            return True

    def run_pptx_recipe(self, action):
        if action == "theme_dark":
            # Dark theme recipe: click Design (デザイン) tab, select dark variant or click format background
            # Fallback keys: Alt + G (Design tab) -> H (Format Background)
            design_coord = self.find_menu_option(["デザイン", "design"])
            self.trigger_visual_action("Design Tab", design_coord, "{ALT}g")
            return True, "Guided to Design Theme option."
            
        elif action == "align_center":
            # Align shapes recipe: click Home (ホーム) -> Arrange (整列/配置) -> Align (配置) -> Center (左右中央揃え)
            # Keyboard fallback: Alt + H -> G -> A -> C
            arrange_coord = self.find_menu_option(["整列", "配置", "arrange", "align"])
            self.trigger_visual_action("Arrange / Align Menu", arrange_coord, "{ALT}hgac")
            return True, "Guided to Arrange & Align Center option."
            
        elif action == "insert_text_box":
            # Insert text box: click Insert (挿入) -> Text Box (テキストボックス)
            # Keyboard fallback: Alt + N -> X
            insert_coord = self.find_menu_option(["挿入", "insert"])
            self.trigger_visual_action("Insert Tab", insert_coord, "{ALT}n")
            return True, "Guided to Insert Tab for Text Box."
            
        return False, f"Unknown PowerPoint action: {action}"

    def run_excel_recipe(self, action):
        if action == "format_table":
            # Format table: Home -> Format as Table
            # Keyboard fallback: Alt + H -> T
            table_coord = self.find_menu_option(["テーブルとして書式設定", "tableformat", "書式設定"])
            self.trigger_visual_action("Format as Table", table_coord, "{ALT}ht")
            return True, "Guided to Table Formatting."
            
        elif action == "insert_chart":
            # Insert chart: Insert -> Recommend Charts
            # Keyboard fallback: Alt + N -> R
            insert_coord = self.find_menu_option(["挿入", "insert"])
            self.trigger_visual_action("Insert Tab", insert_coord, "{ALT}n")
            return True, "Guided to Insert Tab for Charts."
            
        return False, f"Unknown Excel action: {action}"

    def run_word_recipe(self, action):
        if action == "heading_hierarchy":
            # Format title text box style or format font sizes
            # Alt + H -> F -> S (change font size)
            home_coord = self.find_menu_option(["ホーム", "home"])
            self.trigger_visual_action("Home Tab", home_coord, "{ALT}h")
            return True, "Guided to Font formatting menu."
            
        return False, f"Unknown Word action: {action}"

    def execute_step(self):
        # Default BaseBrain step
        self.log("Running BaseBrain execute_step loop...")
        self.status = "Idle"
        
    def __del__(self):
        if self.ocr_process:
            try:
                self.ocr_process.stdin.write("EXIT\n")
                self.ocr_process.stdin.flush()
                self.ocr_process.wait(timeout=1.0)
            except:
                try: self.ocr_process.kill()
                except: pass
