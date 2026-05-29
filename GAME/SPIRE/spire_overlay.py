import os
import sys
import time
import tkinter as tk
from tkinter import ttk
import threading
import json

# Path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AI_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AI"))
GENRE_DIR = os.path.dirname(os.path.dirname(BASE_DIR))

if AI_DIR not in sys.path:
    sys.path.append(AI_DIR)

try:
    from brain_switchboard import BrainSwitchboard
except ImportError:
    # Fallback/simulation mock if not run in correct tree
    class BrainSwitchboard:
        def __init__(self, title):
            self.active_brain_name = "DEMO"
            self.status_file = "brain_status_demo.json"
        def get_active_brain(self):
            class MockBrain:
                def __init__(self):
                    self.name = "DEMO"
                    self.status = "Idle"
                    self.logs = ["[00:00:00] Demo running"]
            return MockBrain()
        def set_active_brain(self, name):
            self.active_brain_name = name
            return True
        def trigger_active_brain(self):
            pass

class AppleGoogleHUDWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("HUD Controller")
        
        # Transparent borderless overlay setup
        self.root.overrideredirect(True)
        self.root.attributes("-transparentcolor", "#000001")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        
        # Geometry: 340x220, anchored in bottom-right corner (just above taskbar)
        self.width = 340
        self.height = 220
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - self.width - 25
        y = screen_h - self.height - 70
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        # Load switchboard
        try:
            self.switchboard = BrainSwitchboard("Slay the Spire 2")
        except Exception as e:
            print(f"Switchboard init failed: {e}")
            self.switchboard = None

        # Build GUI Components
        self.build_ui()
        
        # Dragging handlers variables
        self._drag_x = None
        self._drag_y = None
        
        # Start state polling loop
        self.update_status_data()

    def build_ui(self):
        # Create canvas for transparent rounded window drawing
        self.canvas = tk.Canvas(self.root, bg="#000001", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Draw rounded background card and thin premium border
        self.draw_hud_base()
        
        # Bind window dragging events to the canvas
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<B1-Motion>", self.drag_motion)
        
        # Header Badge & Glowing Indicator Dot
        # Active brain badge (Google/Apple Minimalist style pill)
        self.badge_bg = self.draw_rounded_rectangle(22, 20, 130, 42, 6, fill="#1C1C24", outline="")
        self.brain_badge = self.canvas.create_text(
            76, 31, text="DEVELOPMENT", font=("SF Pro Text", 9, "bold"), fill="#8A8A9E", anchor="center"
        )
        
        # Circular glowing status indicator dot
        self.status_dot = self.canvas.create_oval(
            298, 24, 308, 34, fill="#2979FF", outline="#121216", width=2
        )
        
        # Large active state label
        self.status_label = self.canvas.create_text(
            25, 68, text="System: Active", font=("SF Pro Text", 15, "bold"), fill="#FFFFFF", anchor="w"
        )
        
        # Small scrolling log display
        self.log_label = self.canvas.create_text(
            25, 106, text="Ready for commands.", font=("SF Pro Text", 9), fill="#8A8A9E", anchor="w", width=290
        )
        
        # Feedback flash label (fades out command outcomes)
        self.feedback_label = self.canvas.create_text(
            25, 133, text="", font=("SF Pro Text", 9), fill="#00E676", anchor="w"
        )
        
        # Sleek pill-shaped entry box
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            self.root,
            textvariable=self.entry_var,
            bg="#1C1C24",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            font=("SF Pro Text", 9),
            bd=0,
            highlightthickness=1,
            highlightbackground="#2C2C3A",
            highlightcolor="#4285F4"
        )
        
        # Position the Entry widget inside the pill layout on the canvas
        self.canvas.create_window(170, 172, window=self.entry, width=290, height=26)
        self.entry.bind("<Return>", self.handle_command)
        
        # Hover animations for entry box
        self.entry.bind("<Enter>", lambda e: self.entry.config(highlightbackground="#4285F4"))
        self.entry.bind("<Leave>", lambda e: self.entry.config(highlightbackground="#2C2C3A" if self.root.focus_get() != self.entry else "#4285F4"))
        self.entry.bind("<FocusIn>", self.clear_placeholder)
        self.entry.bind("<FocusOut>", self.restore_placeholder)

        # Placeholder setup
        self.entry.insert(0, "Type a command... (e.g. switch spire)")
        self.entry.config(fg="#5A5A6E")

    def draw_hud_base(self):
        # Premium dark slate card
        self.draw_rounded_rectangle(10, 10, self.width - 10, self.height - 10, 16, fill="#121216", outline="#2C2C3A", width=1.5)
        # Subtle horizontal separator above command entry
        self.canvas.create_line(25, 145, 315, 145, fill="#2C2C3A", width=1)

    def draw_rounded_rectangle(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r,
            x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1
        ]
        return self.canvas.create_polygon(points, **kwargs, smooth=True)

    # Mouse Window Dragging Methods
    def start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def stop_drag(self, event):
        self._drag_x = None
        self._drag_y = None

    def drag_motion(self, event):
        if self._drag_x is not None and self._drag_y is not None:
            dx = event.x - self._drag_x
            dy = event.y - self._drag_y
            new_x = self.root.winfo_x() + dx
            new_y = self.root.winfo_y() + dy
            self.root.geometry(f"+{new_x}+{new_y}")

    # Placeholder Helpers
    def clear_placeholder(self, event):
        if self.entry_var.get() == "Type a command... (e.g. switch spire)":
            self.entry.delete(0, tk.END)
            self.entry.config(fg="#FFFFFF")
            self.entry.config(highlightcolor="#4285F4")

    def restore_placeholder(self, event):
        if not self.entry_var.get():
            self.entry.insert(0, "Type a command... (e.g. switch spire)")
            self.entry.config(fg="#5A5A6E")
            self.entry.config(highlightbackground="#2C2C3A")

    # Command Execution Handler
    def handle_command(self, event):
        cmd = self.entry_var.get().strip()
        if not cmd or cmd == "Type a command... (e.g. switch spire)":
            return
            
        self.entry_var.set("")
        
        parts = cmd.lower().split()
        main_cmd = parts[0]
        
        if main_cmd == "switch":
            if len(parts) < 2:
                self.show_feedback("Error: Specify brain name", is_error=True)
                return
            target_brain = parts[1].upper()
            if self.switchboard and self.switchboard.set_active_brain(target_brain):
                self.show_feedback(f"Switched to {target_brain}")
            else:
                if self.switchboard:
                    self.switchboard.scan_and_register_brains()
                    if self.switchboard.set_active_brain(target_brain):
                        self.show_feedback(f"Switched to {target_brain}")
                        return
                self.show_feedback(f"Brain '{target_brain}' not found", is_error=True)
                
        elif main_cmd in ["run", "start", "go"]:
            if self.switchboard:
                self.switchboard.trigger_active_brain()
                self.show_feedback("Executing Brain...")
                
        elif main_cmd == "create":
            if len(parts) < 2:
                self.show_feedback("Error: Specify folder name", is_error=True)
                return
            new_name = parts[1].upper()
            self.create_new_genre_folder(new_name)
            
        elif main_cmd == "exit":
            self.root.destroy()
            
        else:
            # Fallback check: is it just the name of a brain?
            brain_check = cmd.upper()
            if self.switchboard and brain_check in self.switchboard.brains:
                self.switchboard.set_active_brain(brain_check)
                self.show_feedback(f"Switched to {brain_check}")
            else:
                self.show_feedback("Command unrecognized", is_error=True)

    def create_new_genre_folder(self, name):
        """Creates a new task folder under GAME/ and generates a boilerplate python runner."""
        target_path = os.path.join(GENRE_DIR, "GAME", name)
        try:
            if not os.path.exists(target_path):
                os.makedirs(target_path, exist_ok=True)
                run_py = os.path.join(target_path, "run.py")
                with open(run_py, "w", encoding="utf-8") as f:
                    f.write(f"""import time
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

print("Welcome to the new {name} brain boilerplate!")
for i in range(5):
    print(f"[{name}] Executing cycle {{i+1}}...")
    time.sleep(1.0)
print("Finished boilerplate execution.")
""")
                self.show_feedback(f"Created GAME/{name}")
                if self.switchboard:
                    self.switchboard.scan_and_register_brains()
                    self.switchboard.set_active_brain(name)
            else:
                self.show_feedback(f"Folder GAME/{name} already exists", is_error=True)
        except Exception as e:
            self.show_feedback(f"Creation failed: {e}", is_error=True)

    def show_feedback(self, msg, is_error=False):
        color = "#FF3333" if is_error else "#00E676"
        self.canvas.itemconfig(self.feedback_label, text=msg, fill=color)
        self.root.after(3000, lambda: self.canvas.itemconfig(self.feedback_label, text=""))

    # Dynamic status updater
    def update_status_data(self):
        if self.switchboard:
            status_file = self.switchboard.status_file
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    active = data.get("active_brain", "DEVELOPMENT")
                    brain_info = data.get("brains", {}).get(active, {})
                    status = brain_info.get("status", "Idle")
                    logs = brain_info.get("logs", [])
                    last_log = logs[-1] if logs else "No execution logs yet."
                    
                    # Update badge text and color based on brain genre
                    self.canvas.itemconfig(self.brain_badge, text=active)
                    
                    badge_colors = {
                        "SPIRE": "#34A853",      # Emerald Green
                        "GAME": "#34A853",
                        "DEVELOPMENT": "#EA4335", # Coral Red
                        "OFFICE": "#F9AB00",      # Warm Amber
                        "POWERPOINT": "#F9AB00",
                        "RESEARCH": "#A259FF",    # Royal Purple
                        "SHOGI": "#A259FF",
                    }
                    fill_color = badge_colors.get(active, "#4285F4") # Default Google Blue
                    self.canvas.itemconfig(self.brain_badge, fill=fill_color)
                    
                    # Update status text
                    display_status = f"{active}: {status}"
                    if len(display_status) > 28:
                        display_status = display_status[:25] + "..."
                    self.canvas.itemconfig(self.status_label, text=display_status)
                    
                    # Update log text
                    display_log = last_log
                    if len(display_log) > 42:
                        display_log = display_log[:39] + "..."
                    self.canvas.itemconfig(self.log_label, text=display_log)
                    
                    # Pulse glowing dot based on run state
                    dot_color = "#2979FF" # Blue (Idle)
                    if any(kw in status.lower() for kw in ["running", "autoplay", "analyzing", "compiling", "processing"]):
                        dot_color = "#00E676" # Pulsing Green (Active)
                    elif "error" in status.lower():
                        dot_color = "#FF3333" # Red (Error)
                        
                    self.canvas.itemconfig(self.status_dot, fill=dot_color)
                except Exception as e:
                    pass
        
        # Query again in 500ms
        self.root.after(500, self.update_status_data)

def main():
    root = tk.Tk()
    app = AppleGoogleHUDWidget(root)
    root.mainloop()

if __name__ == "__main__":
    main()
