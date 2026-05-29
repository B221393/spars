import tkinter as tk
from tkinter import ttk
import requests
import json
import threading
import time
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

class CoworkChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity Co-Worker")
        
        # self.root.overrideredirect(True) # Disabled to fix keyboard focus/typing on Windows
        self.root.attributes("-toolwindow", True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        
        self.width = 320
        self.height = 450
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - self.width - 25
        y = screen_h - self.height - 75
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        self.bg_color = "#0e0e12"
        self.header_bg = "#161622"
        self.text_bg = "#1a1a24"
        self.fg_color = "#e2e8f0"
        self.accent_color = "#00d4ff"
        self.purple_color = "#bb86fc"
        
        self.root.configure(bg=self.bg_color)
        self.server_url = "http://localhost:8080"
        self.setup_ui()
        self.start_status_polling()
        
        self.append_message("System", "Antigravity Cowork Chat has initialized. Speak or type instructions. Try 'switch to GAME' or 'run'.")

    def setup_ui(self):
        self.header = tk.Frame(self.root, bg=self.header_bg, height=40)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)
        
        self.header.bind("<Button-1>", self.start_drag)
        self.header.bind("<B1-Motion>", self.drag)
        
        title_lbl = tk.Label(self.header, text="🚀 ANTIGRAVITY COWORK", bg=self.header_bg, fg=self.accent_color, font=("Segoe UI", 10, "bold"))
        title_lbl.pack(side="left", padx=10)
        title_lbl.bind("<Button-1>", self.start_drag)
        title_lbl.bind("<B1-Motion>", self.drag)
        
        close_btn = tk.Label(self.header, text="✕", bg=self.header_bg, fg="#ff5555", font=("Segoe UI", 11, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=10)
        close_btn.bind("<Button-1>", lambda e: self.root.destroy())
        
        self.status_bar = tk.Frame(self.root, bg="#1e1e2d", height=32)
        self.status_bar.pack(fill="x", side="top")
        self.status_bar.pack_propagate(False)
        
        self.brain_list = ["DEVELOPMENT", "SHOGI", "VOICE", "RESEARCH", "POWERPOINT", "GAME", "OFFICE", "SPIRE"]
        
        style = ttk.Style()
        style.configure("TCombobox", fieldbackground=self.text_bg, background="#161622", foreground="#ffffff")
        
        self.brain_combo = ttk.Combobox(self.status_bar, values=self.brain_list, state="readonly", width=14, font=("Segoe UI", 9, "bold"))
        self.brain_combo.set("DEVELOPMENT")
        self.brain_combo.pack(side="left", padx=10, pady=3)
        self.brain_combo.bind("<<ComboboxSelected>>", self.on_brain_select)
        
        self.trigger_btn = tk.Label(self.status_bar, text="▶ RUN", bg=self.accent_color, fg="#000000", font=("Segoe UI", 8, "bold"), cursor="hand2", padx=6, pady=2)
        self.trigger_btn.pack(side="right", padx=10, pady=3)
        self.trigger_btn.bind("<Button-1>", lambda e: self.trigger_active_brain())

        self.chat_frame = tk.Frame(self.root, bg=self.bg_color)
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.text_area = tk.Text(self.chat_frame, bg=self.text_bg, fg=self.fg_color, font=("Segoe UI", 9), relief="flat", wrap="word", insertbackground=self.accent_color)
        self.text_area.pack(fill="both", expand=True, side="left")
        
        self.text_area.tag_config("User", foreground=self.purple_color, font=("Segoe UI", 9, "bold"))
        self.text_area.tag_config("AI", foreground=self.accent_color, font=("Segoe UI", 9, "bold"))
        self.text_area.tag_config("System", foreground="#94a3b8", font=("Segoe UI", 9, "italic"))
        self.text_area.tag_config("content", foreground=self.fg_color)
        self.text_area.configure(state="disabled")

        scrollbar = ttk.Scrollbar(self.chat_frame, orient="vertical", command=self.text_area.yview)
        scrollbar.pack(fill="y", side="right")
        self.text_area.configure(yscrollcommand=scrollbar.set)

        input_container = tk.Frame(self.root, bg=self.bg_color, height=45)
        input_container.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        input_container.pack_propagate(False)
        
        self.entry = tk.Entry(input_container, bg=self.text_bg, fg="#ffffff", font=("Segoe UI", 10), relief="flat", insertbackground=self.accent_color)
        self.entry.pack(fill="both", expand=True, side="left", ipady=4, padx=(0, 5))
        self.entry.bind("<Return>", lambda e: self.send_message())
        
        send_btn = tk.Button(input_container, text="SEND", bg=self.accent_color, fg="#000000", font=("Segoe UI", 9, "bold"), relief="flat", activebackground=self.purple_color, command=self.send_message)
        send_btn.pack(fill="both", side="right")

    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def drag(self, event):
        x = self.root.winfo_x() + (event.x - self.drag_x)
        y = self.root.winfo_y() + (event.y - self.drag_y)
        self.root.geometry(f"+{x}+{y}")

    def append_message(self, sender, text):
        self.text_area.configure(state="normal")
        if sender == "User":
            self.text_area.insert("end", "👤 You: ", "User")
            self.text_area.insert("end", f"{text}\n\n", "content")
        elif sender == "AI":
            self.text_area.insert("end", "🤖 Co-Worker: ", "AI")
            self.text_area.insert("end", f"{text}\n\n", "content")
        else:
            self.text_area.insert("end", f"⚙️ {text}\n\n", "System")
        self.text_area.configure(state="disabled")
        self.text_area.see("end")

    def send_message(self):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, "end")
        self.append_message("User", msg)
        
        threading.Thread(target=self._api_send_chat, args=(msg,), daemon=True).start()

    def _api_send_chat(self, msg):
        try:
            res = requests.post(f"{self.server_url}/api/cowork/chat", json={"message": msg}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                ai_resp = data.get("response", "No response")
                active = data.get("active_brain", "DEVELOPMENT")
                self.root.after(0, lambda: self.append_message("AI", ai_resp))
                self.root.after(0, lambda: self.brain_combo.set(active))
            else:
                self.root.after(0, lambda: self.append_message("System", f"Server error: {res.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: self.append_message("System", f"Connection failed: {e}"))

    def trigger_active_brain(self):
        self.append_message("System", "Triggering active brain...")
        threading.Thread(target=self._api_trigger_brain, daemon=True).start()

    def _api_trigger_brain(self):
        try:
            res = requests.post(f"{self.server_url}/api/brain/trigger", json={}, timeout=10)
            if res.status_code == 200:
                self.root.after(0, lambda: self.append_message("System", "Brain triggered successfully!"))
            else:
                self.root.after(0, lambda: self.append_message("System", f"Trigger failed: {res.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: self.append_message("System", f"Connection failed: {e}"))

    def start_status_polling(self):
        def _poll():
            while True:
                try:
                    res = requests.get(f"{self.server_url}/api/brain/status", timeout=2)
                    if res.status_code == 200:
                        data = res.json()
                        active = data.get("active_brain", "DEVELOPMENT")
                        self.root.after(0, lambda active=active: self.brain_combo.set(active))
                except:
                    pass
                time.sleep(2)
        threading.Thread(target=_poll, daemon=True).start()

    def on_brain_select(self, event):
        selected_brain = self.brain_combo.get()
        self.append_message("System", f"Switching brain to {selected_brain}...")
        
        def _switch():
            try:
                res = requests.post(f"{self.server_url}/api/brain/switch", json={"brain": selected_brain}, timeout=5)
                if res.status_code == 200:
                    self.root.after(0, lambda: self.append_message("System", f"Brain successfully switched to {selected_brain}."))
                else:
                    self.root.after(0, lambda: self.append_message("System", f"Failed to switch brain: {res.status_code}"))
            except Exception as e:
                self.root.after(0, lambda: self.append_message("System", f"Connection failed during brain switch: {e}"))
                
        threading.Thread(target=_switch, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = CoworkChatApp(root)
    root.mainloop()
