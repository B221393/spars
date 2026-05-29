import os
import sys
import time
import random
import math
from datetime import datetime

# Prevent console encoding issues on Windows Japanese locale
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except:
    pass

# Import AIDriver
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "CORE"))
from ai_driver import AIDriver

# Target doc path for report
REPORT_PATH = os.path.join(os.path.dirname(BASE_DIR), "DOCS", "COWORK_BENCHMARK_REPORT.md")

class CoworkBenchmark:
    def __init__(self):
        self.driver = AIDriver("AI Training Game", log_dir=BASE_DIR)
        if not self.driver.hwnd:
            self.driver = AIDriver("Program Manager", log_dir=BASE_DIR)
            
        self.results = {}
        
    def run_all(self):
        print("🚀 Starting Cowork Input & Self-Healing Benchmark...")
        
        self.test_mouse_movement()
        self.test_typing()
        self.test_clicks_with_self_healing()
        self.save_report()
        
    def test_mouse_movement(self):
        print("\n--- Test 1: Bezier Mouse Movement ---")
        import win32api
        start_pos = win32api.GetCursorPos()
        
        t0 = time.time()
        targets = [(100, 100), (400, 200), (200, 400), start_pos]
        for tx, ty in targets:
            print(f"Moving to ({tx}, {ty})...")
            self.driver.bezier_move(tx, ty)
            time.sleep(0.1)
            
        elapsed = time.time() - t0
        total_dist = 0
        curr = start_pos
        for tx, ty in targets:
            abs_tx, abs_ty = self.driver.get_physical_client_pos(tx, ty)
            total_dist += math.hypot(abs_tx - curr[0], abs_ty - curr[1])
            curr = (abs_tx, abs_ty)
            
        speed = total_dist / elapsed if elapsed > 0 else 0
        print(f"Bezier Movement test finished. Distance: {total_dist:.1f}px in {elapsed:.2f}s (Speed: {speed:.1f} px/sec)")
        
        self.results["mouse"] = {
            "elapsed": elapsed,
            "distance": total_dist,
            "speed": speed
        }
        
    def test_typing(self):
        print("\n--- Test 2: Typing Simulation ---")
        test_text = "Antigravity Cowork System Initialized 2026."
        
        t0 = time.time()
        self.driver.type_string(test_text)
        elapsed = time.time() - t0
        
        char_count = len(test_text)
        cpm = (char_count / elapsed) * 60 if elapsed > 0 else 0
        wpm = cpm / 5
        
        print(f"Typing test finished. Text length: {char_count} chars in {elapsed:.2f}s ({wpm:.1f} WPM / {cpm:.1f} CPM)")
        self.results["typing"] = {
            "elapsed": elapsed,
            "wpm": wpm,
            "cpm": cpm
        }
        
    def test_clicks_with_self_healing(self):
        print("\n--- Test 3: Clicks & Self-Healing Verification ---")
        
        test_actions = [
            {"name": "Trigger Workspace Switcher", "x": 120, "y": 80},
            {"name": "Open Sidebar Settings", "x": 50, "y": 200},
            {"name": "Click Outside Window (Static Fail Case)", "x": 10, "y": 10}
        ]
        
        self.results["clicks"] = []
        
        for act in test_actions:
            name = act["name"]
            x, y = act["x"], act["y"]
            
            print(f"\nTargeting click action: {name} at ({x}, {y})")
            
            success = self.driver.execute_and_verify(name, x, y)
            
            if success:
                print(f"✅ Action '{name}' succeeded on first attempt!")
                self.results["clicks"].append({
                    "name": name,
                    "attempts": 1,
                    "healed": False,
                    "result": "SUCCESS"
                })
            else:
                print(f"⚠️ Action '{name}' failed. Triggering Self-Healing Loop...")
                healed_success = self.run_self_healing_loop(name, x, y)
                
                self.results["clicks"].append({
                    "name": name,
                    "attempts": 2 if healed_success else 3,
                    "healed": healed_success,
                    "result": "SUCCESS" if healed_success else "FAILED"
                })
                
    def run_self_healing_loop(self, action_name, x, y):
        calibrations = [
            {"name": "Force Foreground Window Focus", "adjust": lambda: self.driver.connect(), "force_focus": True, "duration": 0.3},
            {"name": "Increase Click Hold Duration & Wait Latency", "adjust": lambda: None, "force_focus": True, "duration": 0.8}
        ]
        
        for step, cal in enumerate(calibrations, 1):
            print(f"🔧 Self-Healing Step {step}: {cal['name']}...")
            cal["adjust"]()
            
            img_before = self.driver.capture()
            hash_before = self.driver.get_hash(img_before)
            
            self.driver.flash_pointer(x, y, duration=1.0)
            self.driver.hardware_click(x, y, duration=cal["duration"], force_focus=cal["force_focus"])
            time.sleep(2.0)
            
            img_after = self.driver.capture()
            hash_after = self.driver.get_hash(img_after)
            
            if hash_before != hash_after:
                print(f"🎉 Calibration SUCCESS! Action '{action_name}' verified visually.")
                self.driver.create_proof(img_before, img_after, x, y, "HEALED_SUCCESS")
                self.driver.write_verification_log(action_name + " (HEALED)", (x, y), "Hardware Click (Self-Healed)", "SUCCESS", f"Calibrated via: {cal['name']}")
                return True
                
        print(f"❌ Self-Healing could not resolve action: '{action_name}'")
        return False

    def save_report(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(f"# 📊 Antigravity Cowork Self-Healing & Input Benchmark Report\n")
            f.write(f"Generated at: {timestamp}\n\n")
            
            f.write("## 1. Mouse Movement Performance (Bezier Path)\n")
            m = self.results.get("mouse", {})
            f.write(f"- **Total Distance Traveled**: {m.get('distance', 0):.1f} px\n")
            f.write(f"- **Total Duration**: {m.get('elapsed', 0):.2f} seconds\n")
            f.write(f"- **Emulation Speed**: {m.get('speed', 0):.1f} px/sec\n\n")
            
            f.write("## 2. Typing Performance (Randomized Latency)\n")
            t = self.results.get("typing", {})
            f.write(f"- **Typing WPM**: {t.get('wpm', 0):.1f} WPM\n")
            f.write(f"- **Typing CPM**: {t.get('cpm', 0):.1f} characters/min\n")
            f.write(f"- **Mode**: Simulated Key-Down Hold & Character Delays\n\n")
            
            f.write("## 3. Visual Click Verification & Self-Healing Log\n")
            f.write("| Action Name | Attempts | Self-Healed? | Final Result |\n")
            f.write("| :--- | :---: | :---: | :--- |\n")
            for c in self.results.get("clicks", []):
                healed_str = "✅ Yes" if c["healed"] else ("-" if c["result"] == "SUCCESS" else "❌ No")
                f.write(f"| {c['name']} | {c['attempts']} | {healed_str} | {c['result']} |\n")
                
        print(f"✨ Benchmark report written to: {REPORT_PATH}")

if __name__ == "__main__":
    bm = CoworkBenchmark()
    bm.run_all()
