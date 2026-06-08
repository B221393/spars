#!/usr/bin/env python3
"""
DESIGN PLUGIN - Premium Meta-Prompt & Telemetry Dashboard
A native Tkinter GUI overlay featuring:
1. Glassmorphic premium dark theme UI (Apple/Google style)
2. Meta-Prompt AI Planner (interfaces with local gemma2:2b)
3. Calibration Telemetry (real-time rolling stats parser & radar coordinate target plot)
4. Automated action dispatcher (writes directly to puppet_hints.json)
"""

import os
import sys
import json
import time
import requests
import threading
import tkinter as tk
from tkinter import ttk

# Reconfigure stdout/stderr to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENRE_DIR = os.path.dirname(os.path.dirname(BASE_DIR))

# Paths for files to monitor and write to
SPIRE_SAVES_DIR = os.path.join(GENRE_DIR, "GAME", "SPIRE", "saves")
SPIRE_PUPPET_HINTS = os.path.join(SPIRE_SAVES_DIR, "puppet_hints.json")
SPIRE_CALIBRATION = os.path.join(SPIRE_SAVES_DIR, "click_calibration_data.json")
HARNESS_CALIBRATION = os.path.join(BASE_DIR, "click_calibration_data.json")
SYSTEM_STATUS = os.path.join(GENRE_DIR, "AI", "brain_status.json")

class DesignPluginDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Design Plugin - Cognitive Dashboard")
        self.root.geometry("640x520")
        self.root.configure(bg="#0D0D11")
        self.root.resizable(False, False)
        
        # Windows styling
        self.root.attributes("-alpha", 0.98)
        
        self.ollama_url = "http://localhost:11434"
        self.model = "gemma2:2b"
        
        # State variables
        self.mean_dx = 0.0
        self.mean_dy = 0.0
        self.std_dx = 0.0
        self.std_dy = 0.0
        self.trend = "Calibrator inactive"
        self.click_history = []
        
        self.is_thinking = False
        
        self.build_ui()
        self.start_monitoring()

    def build_ui(self):
        # Header Badge
        header_frame = tk.Frame(self.root, bg="#0D0D11")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        title_label = tk.Label(
            header_frame, 
            text="DESIGN PLUGIN", 
            font=("SF Pro Text", 16, "bold"), 
            fg="#FFFFFF", 
            bg="#0D0D11"
        )
        title_label.pack(side="left")
        
        subtitle_label = tk.Label(
            header_frame, 
            text="COGNITIVE META-PROMPT ENGINE", 
            font=("SF Pro Text", 9, "bold"), 
            fg="#A259FF", 
            bg="#0D0D11"
        )
        subtitle_label.pack(side="left", padx=10, pady=5)

        self.status_dot = tk.Canvas(header_frame, width=12, height=12, bg="#0D0D11", highlightthickness=0)
        self.status_dot.pack(side="right", pady=5)
        self.draw_status_dot("#2979FF") # Blue = Ready

        # Main Layout: Left Panel (Meta-Prompt AI), Right Panel (Telemetry & Radar)
        main_paned = tk.Frame(self.root, bg="#0D0D11")
        main_paned.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left Panel (Width 360)
        left_panel = tk.Frame(main_paned, bg="#121216", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Form Header
        tf_lbl = tk.Label(left_panel, text="Meta-Prompt Planner Agent", font=("SF Pro Text", 10, "bold"), fg="#8A8A9E", bg="#121216")
        tf_lbl.pack(anchor="w", padx=15, pady=10)
        
        # Goal Entry
        goal_lbl = tk.Label(left_panel, text="Target Objective (High-level Goal)", font=("SF Pro Text", 9), fg="#A259FF", bg="#121216")
        goal_lbl.pack(anchor="w", padx=15, pady=(5, 2))
        
        self.goal_entry = tk.Entry(
            left_panel, 
            bg="#1C1C24", 
            fg="#FFFFFF", 
            insertbackground="#FFFFFF",
            font=("SF Pro Text", 10), 
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#2C2C3A", 
            highlightcolor="#A259FF"
        )
        self.goal_entry.pack(fill="x", padx=15, pady=(0, 10), height=26)
        self.goal_entry.insert(0, "Slay the Spire 2: Play card 1 on the left monster")
        
        # Plan Button
        self.plan_btn = tk.Button(
            left_panel, 
            text="Generate Action Plan (AI)", 
            font=("SF Pro Text", 9, "bold"), 
            bg="#A259FF", 
            fg="#FFFFFF", 
            activebackground="#8E44AD", 
            activeforeground="#FFFFFF",
            bd=0, 
            padx=10, 
            pady=5, 
            command=self.trigger_planning
        )
        self.plan_btn.pack(anchor="w", padx=15, pady=5)
        
        # Thought process log
        thought_lbl = tk.Label(left_panel, text="AI Strategic Thoughts & Decision Plan", font=("SF Pro Text", 9), fg="#8A8A9E", bg="#121216")
        thought_lbl.pack(anchor="w", padx=15, pady=(10, 2))
        
        self.thought_text = tk.Text(
            left_panel, 
            height=8, 
            bg="#0D0D11", 
            fg="#E2E8F0", 
            font=("SF Pro Text", 9), 
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#2C2C3A",
            wrap="word"
        )
        self.thought_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self.thought_text.insert(tk.END, "Ready to plan. Enter a goal above and click 'Generate Action Plan (AI)'.\n")
        self.thought_text.config(state="disabled")

        # Action Command Bar
        action_bar = tk.Frame(left_panel, bg="#121216")
        action_bar.pack(fill="x", padx=15, pady=(0, 15))
        
        self.dispatch_btn = tk.Button(
            action_bar, 
            text="Dispatch Command to Game", 
            font=("SF Pro Text", 9, "bold"), 
            bg="#00E676", 
            fg="#121216", 
            activebackground="#00B0FF", 
            activeforeground="#FFFFFF",
            bd=0, 
            padx=10, 
            pady=5, 
            command=self.dispatch_action,
            state="disabled"
        )
        self.dispatch_btn.pack(side="left")
        
        self.planned_action_var = tk.StringVar(value="None")
        self.planned_action_lbl = tk.Label(action_bar, textvariable=self.planned_action_var, font=("SF Pro Text", 9, "bold"), fg="#E2E8F0", bg="#121216")
        self.planned_action_lbl.pack(side="right", padx=10)

        # Right Panel (Width 220)
        right_panel = tk.Frame(main_paned, bg="#121216", bd=1, relief="flat", highlightbackground="#2C2C3A", highlightthickness=1)
        right_panel.pack(side="right", fill="both")
        
        # Calibration Title
        cal_lbl = tk.Label(right_panel, text="Calibration Telemetry", font=("SF Pro Text", 10, "bold"), fg="#8A8A9E", bg="#121216")
        cal_lbl.pack(anchor="w", padx=15, pady=10)
        
        # Target radar chart canvas
        self.radar = tk.Canvas(right_panel, width=160, height=160, bg="#0D0D11", highlightthickness=1, highlightbackground="#2C2C3A")
        self.radar.pack(padx=20, pady=5)
        self.draw_radar_grid()
        
        # Telemetry fields
        self.offset_var = tk.StringVar(value="Offset: dx=0.0px, dy=0.0px")
        self.std_var = tk.StringVar(value="Variance: sx=0.0px, sy=0.0px")
        self.trend_var = tk.StringVar(value="Trend: Calibrating...")
        
        lbl_offset = tk.Label(right_panel, textvariable=self.offset_var, font=("SF Pro Text", 9), fg="#E2E8F0", bg="#121216", anchor="w")
        lbl_offset.pack(fill="x", padx=15, pady=(8, 2))
        
        lbl_std = tk.Label(right_panel, textvariable=self.std_var, font=("SF Pro Text", 9), fg="#8A8A9E", bg="#121216", anchor="w")
        lbl_std.pack(fill="x", padx=15, pady=2)
        
        lbl_trend = tk.Label(right_panel, textvariable=self.trend_var, font=("SF Pro Text", 9, "bold"), fg="#FFC107", bg="#121216", anchor="w")
        lbl_trend.pack(fill="x", padx=15, pady=2)
        
        # Current active brain indicator
        self.active_brain_var = tk.StringVar(value="Active Brain: SPIRE")
        lbl_brain = tk.Label(right_panel, textvariable=self.active_brain_var, font=("SF Pro Text", 9, "bold"), fg="#A259FF", bg="#121216", anchor="w")
        lbl_brain.pack(fill="x", padx=15, pady=(15, 10))

    def draw_status_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 11, 11, fill=color, outline="#121216", width=1.5)

    def draw_radar_grid(self):
        self.radar.delete("all")
        w, h = 160, 160
        cx, cy = w // 2, h // 2
        
        # Target concentric circles (15px, 30px, 45px)
        self.radar.create_oval(cx - 15, cy - 15, cx + 15, cy + 15, outline="#2C2C3A", width=1)
        self.radar.create_oval(cx - 35, cy - 35, cx + 35, cy + 35, outline="#2C2C3A", width=1)
        self.radar.create_oval(cx - 55, cy - 55, cx + 55, cy + 55, outline="#2C2C3A", width=1)
        
        # Crosshair axes
        self.radar.create_line(cx - 70, cy, cx + 70, cy, fill="#2C2C3A", width=1)
        self.radar.create_line(cx, cy - 70, cx, cy + 70, fill="#2C2C3A", width=1)
        
        # Center marker
        self.radar.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#8A8A9E")

    def update_radar_points(self):
        self.draw_radar_grid()
        w, h = 160, 160
        cx, cy = w // 2, h // 2
        
        # Draw past click deltas
        if self.click_history:
            for item in self.click_history[-20:]: # Show last 20 clicks
                dx = item.get("dx", 0)
                dy = item.get("dy", 0)
                
                # Scale coordinate offset (e.g. 1px = 1px on radar)
                px = cx + int(dx)
                py = cy + int(dy)
                
                # Color code points by distance (closer = green, farther = orange/red)
                dist = (dx**2 + dy**2)**0.5
                color = "#00E676" # Green
                if dist > 20:
                    color = "#FF9100" # Orange
                if dist > 40:
                    color = "#FF1744" # Red
                
                self.radar.create_oval(px - 3, py - 3, px + 3, py + 3, fill=color, outline="")
                
        # Draw large cyan average calibration dot
        acx = cx + int(round(self.mean_dx))
        acy = cy + int(round(self.mean_dy))
        self.radar.create_oval(acx - 5, acy - 5, acx + 5, acy + 5, fill="#00E5FF", outline="#FFFFFF", width=1.5)

    def log_thought(self, message):
        self.thought_text.config(state="normal")
        self.thought_text.insert(tk.END, message + "\n")
        self.thought_text.see(tk.END)
        self.thought_text.config(state="disabled")

    def trigger_planning(self):
        if self.is_thinking:
            return
            
        goal = self.goal_entry.get().strip()
        if not goal:
            return
            
        self.is_thinking = True
        self.draw_status_dot("#FF9100") # Pulsing Orange = Thinking
        self.plan_btn.config(state="disabled", text="Thinking...")
        self.thought_text.config(state="normal")
        self.thought_text.delete(1.0, tk.END)
        self.thought_text.config(state="disabled")
        
        threading.Thread(target=self.run_planning_thread, args=(goal,), daemon=True).start()

    def run_planning_thread(self, goal):
        self.log_thought("💡 Initiating Cognitive Meta-Prompt reasoning loop...")
        
        # Read current system status
        active_brain = "SPIRE"
        last_logs = []
        if os.path.exists(SYSTEM_STATUS):
            try:
                with open(SYSTEM_STATUS, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    active_brain = data.get("active_brain", "SPIRE")
                    last_logs = data.get("brains", {}).get(active_brain, {}).get("logs", [])
            except:
                pass
                
        self.log_thought(f"🔍 System Active Brain: {active_brain}")
        if last_logs:
            self.log_thought(f"🔍 Last Action: {last_logs[-1]}")
            
        # Formulate system instruction to the model
        system_instruction = f"""
        あなたはGUI自動化システムの「メタ・プロンプト・プランナーAI」です。
        ユーザーの目標に応じて、次に実行すべき低レイヤーのGUIコマンド（マウスクリック、方向調整、待機など）を考案・決定します。
        
        現在のシステム状態:
        - アクティブブレイン: {active_brain}
        - キャリブレーション補正平均: dx={self.mean_dx:.2f}px, dy={self.mean_dy:.2f}px
        - 補正パターントレンド: '{self.trend}'
        
        次のフォーマットのJSONデータのみで出力してください。マークダウンの```json等の装飾は一切含めないでください。
        {{
            "reason": "1. ユーザーの目的を分析: <目的>。2. 次の行動計画: <理由>。",
            "command": "click" または "nudge" または "none",
            "target_x": 整数 (clickコマンドの場合のX座標),
            "target_y": 整数 (clickコマンドの場合のY座標),
            "nudge_dx": 整数 (nudgeコマンドの場合のX方向ピクセル移動値),
            "nudge_dy": 整数 (nudgeコマンドの場合のY方向ピクセル移動値),
            "text": "テキスト入力欄に入力するテキスト（あれば）"
        }}
        """
        
        payload = {
            "model": self.model,
            "prompt": f"{system_instruction}\nユーザー目標: {goal}",
            "stream": False,
            "format": "json"
        }
        
        try:
            url = f"{self.ollama_url}/api/generate"
            response = requests.post(url, json=payload, timeout=45)
            if response.status_code == 200:
                raw_res = response.json().get("response", "{}")
                plan = json.loads(raw_res)
                
                self.log_thought("\n🤖 [Meta-Prompt AI Plan] Decisions generated:")
                self.log_thought(f"🧠 Reason: {plan.get('reason')}")
                self.log_thought(f"🎮 Command: {plan.get('command')}")
                
                cmd = plan.get("command", "none")
                if cmd == "click":
                    tx = plan.get("target_x", 0)
                    ty = plan.get("target_y", 0)
                    self.log_thought(f"🎯 Target Coordinate: ({tx}, {ty})")
                    self.planned_action_var.set(f"Click ({tx}, {ty})")
                    self.next_action_data = {"type": "click", "x": tx, "y": ty}
                    self.dispatch_btn.config(state="normal")
                elif cmd == "nudge":
                    ndx = plan.get("nudge_dx", 0)
                    ndy = plan.get("nudge_dy", 0)
                    self.log_thought(f"📍 Nudge: dx={ndx}px, dy={ndy}px")
                    self.planned_action_var.set(f"Nudge ({ndx}, {ndy})")
                    self.next_action_data = {"type": "nudge", "dx": ndx, "dy": ndy}
                    self.dispatch_btn.config(state="normal")
                else:
                    self.planned_action_var.set("None")
                    self.next_action_data = None
                    self.dispatch_btn.config(state="disabled")
                    
                self.draw_status_dot("#00E676") # Green = Action ready
            else:
                self.log_thought(f"\n❌ Ollama server error: Status {response.status_code}")
                self.draw_status_dot("#FF3333") # Red = Error
        except Exception as e:
            self.log_thought(f"\n❌ Failed to query Ollama API: {e}")
            self.draw_status_dot("#FF3333") # Red = Error
            
        self.is_thinking = False
        self.root.after(0, lambda: self.plan_btn.config(state="normal", text="Generate Action Plan (AI)"))

    def dispatch_action(self):
        if not hasattr(self, 'next_action_data') or not self.next_action_data:
            return
            
        data = self.next_action_data
        hints = {"dx": 0, "dy": 0, "manual_click": None, "manual_click_pct": None}
        
        # Load existing hints if any
        if os.path.exists(SPIRE_PUPPET_HINTS):
            try:
                with open(SPIRE_PUPPET_HINTS, "r", encoding="utf-8") as f:
                    hints = json.load(f)
            except:
                pass
                
        if data["type"] == "click":
            hints["manual_click"] = [data["x"], data["y"]]
            self.log_thought(f"🚀 Dispatched physical click to coordinates ({data['x']}, {data['y']}).")
        elif data["type"] == "nudge":
            hints["dx"] = data["dx"]
            hints["dy"] = data["dy"]
            self.log_thought(f"🚀 Dispatched nudge adjustment delta: dx={data['dx']}px, dy={data['dy']}px.")
            
        try:
            os.makedirs(os.path.dirname(SPIRE_PUPPET_HINTS), exist_ok=True)
            with open(SPIRE_PUPPET_HINTS, "w", encoding="utf-8") as f:
                json.dump(hints, f)
            self.dispatch_btn.config(state="disabled")
            self.planned_action_var.set("Dispatched")
        except Exception as e:
            self.log_thought(f"❌ Failed to dispatch command: {e}")

    def start_monitoring(self):
        # Start real-time calibration statistics monitoring
        def monitor():
            while True:
                # Search calibration file in both Spire saves and local directory
                target_file = None
                if os.path.exists(SPIRE_CALIBRATION):
                    target_file = SPIRE_CALIBRATION
                elif os.path.exists(HARNESS_CALIBRATION):
                    target_file = HARNESS_CALIBRATION
                    
                if target_file:
                    try:
                        with open(target_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self.mean_dx = data.get("mean_dx", 0.0)
                            self.mean_dy = data.get("mean_dy", 0.0)
                            self.std_dx = data.get("std_dx", 0.0)
                            self.std_dy = data.get("std_dy", 0.0)
                            self.trend = data.get("trend", "Calibrating...")
                            self.click_history = data.get("click_history", [])
                            
                            # Update variables
                            self.offset_var.set(f"Offset: dx={self.mean_dx:.1f}px, dy={self.mean_dy:.1f}px")
                            self.std_var.set(f"Variance: sx={self.std_dx:.1f}px, sy={self.std_dy:.1f}px")
                            self.trend_var.set(f"Trend: {self.trend}")
                            
                            self.update_radar_points()
                    except:
                        pass
                        
                # Update active brain
                if os.path.exists(SYSTEM_STATUS):
                    try:
                        with open(SYSTEM_STATUS, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            active = data.get("active_brain", "SPIRE")
                            self.active_brain_var.set(f"Active Brain: {active}")
                    except:
                        pass
                        
                time.sleep(2.0)
                
        threading.Thread(target=monitor, daemon=True).start()

def main():
    root = tk.Tk()
    app = DesignPluginDashboard(root)
    root.mainloop()

if __name__ == "__main__":
    main()
