import tkinter as tk
from tkinter import ttk
import json
import os
import threading
import requests
from VOICE_RESCUE_PRO import VoiceSystem
from MODULE_MANAGER import ModuleManager

# --- Unified Task Manager GUI ---
# すべてのタスク（音声・学習・整理）を一元管理し、優先度を調整可能にする

BASE_DIR = "C:/Users/yu_ci/Desktop/codex-vs-local-agent-loop"
QUEUE_FILE = os.path.join(BASE_DIR, "OUTPUT/AI_WORK_QUEUE.json")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class TaskManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Task Orchestrator")
        self.root.geometry("800x600")
        self.root.configure(bg="#0a0a0a")
        
        self.mm = ModuleManager()
        self.vs = VoiceSystem()
        self.setup_ui()
        self.refresh_queue()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#0a0a0a")
        header.pack(fill="x", padx=20, pady=10)
        
        tk.Label(header, text="UNIFIED TASK QUEUE", bg="#0a0a0a", fg="#00d4ff", font=("Segoe UI", 12, "bold")).pack(side="left")
        
        btn_refresh = tk.Button(header, text="REFRESH", bg="#222", fg="#eee", relief="flat", command=self.refresh_queue)
        btn_refresh.pack(side="right", padx=5)

        # Task Table
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#111", foreground="#eee", fieldbackground="#111", borderwidth=0)
        style.map("Treeview", background=[('selected', '#007acc')])
        
        self.tree = ttk.Treeview(self.root, columns=("Task", "Priority", "Progress"), show="headings")
        self.tree.heading("Task", text="TASK NAME")
        self.tree.heading("Priority", text="PRIORITY (0-100)")
        self.tree.heading("Progress", text="PROGRESS (%)")
        
        self.tree.column("Task", width=400)
        self.tree.column("Priority", width=120, anchor="center")
        self.tree.column("Progress", width=120, anchor="center")
        
        self.tree.pack(fill="both", expand=True, padx=20, pady=5)
        self.tree.bind("<Double-1>", self.on_double_click)

        # Quick Task Input
        input_frame = tk.Frame(self.root, bg="#0a0a0a")
        input_frame.pack(fill="x", padx=20, pady=20)
        
        self.ent_input = tk.Entry(input_frame, bg="#111", fg="#fff", font=("Segoe UI", 11), relief="flat", insertbackground="#fff")
        self.ent_input.pack(side="left", fill="x", expand=True, ipady=5)
        self.ent_input.bind("<Return>", lambda e: self.add_task())
        
        btn_add = tk.Button(input_frame, text="ADD TASK", bg="#00d4ff", fg="#000", font=("Segoe UI", 10, "bold"), relief="flat", width=12, command=self.add_task)
        btn_add.pack(side="right", padx=(10, 0))

        # Bottom Bar
        bottom = tk.Frame(self.root, bg="#0a0a0a")
        bottom.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(bottom, text="* Double-click a priority to edit.", bg="#0a0a0a", fg="#666", font=("Segoe UI", 9)).pack(side="left")

    def refresh_queue(self):
        # 既存リストのクリア
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)
                    # 優先度順にソート
                    queue.sort(key=lambda x: x.get('priority', 0), reverse=True)
                    for item in queue:
                        self.tree.insert("", "end", values=(item['task'], item['priority'], item['progress']))
            except: pass
        
        # 5秒ごとに自動更新
        self.root.after(5000, self.refresh_queue)

    def add_task(self):
        task_desc = self.ent_input.get().strip()
        if not task_desc: return
        self.ent_input.delete(0, 'end')
        
        # USER_TASKS.txt 経由で AI OS に渡す
        task_file = os.path.join(BASE_DIR, "INPUT/USER_TASKS.txt")
        try:
            with open(task_file, "a", encoding="utf-8") as f:
                f.write(f"\n{task_desc}")
            print(f"✅ New Task Added: {task_desc}")
        except: pass

    def on_double_click(self, event):
        """優先度をダブルクリックして変更する"""
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        if item_id and column == "#2": # 優先度列
            task_name = self.tree.item(item_id, "values")[0]
            current_priority = self.tree.item(item_id, "values")[1]
            
            # 簡易入力ダイアログ
            new_val = self.ask_priority(task_name, current_priority)
            if new_val is not None:
                self.update_priority_in_file(task_name, new_val)

    def ask_priority(self, task_name, current_val):
        # Tkinterの簡易入力（ここでは本来ダイアログを出すべきだが、簡略化のためコンソールか固定値でシミュレート）
        # 今回は +10 するだけの簡易トグルに
        try:
            val = int(current_val)
            return (val + 10) % 110 # 0-100の間でループ
        except: return 50

    def update_priority_in_file(self, task_name, new_priority):
        if not os.path.exists(QUEUE_FILE): return
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)
            
            for item in queue:
                if item['task'] == task_name:
                    item['priority'] = new_priority
                    break
            
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)
            self.refresh_queue()
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = TaskManagerGUI(root)
    root.mainloop()
