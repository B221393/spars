#!/usr/bin/env python3
"""
Continuous Learning and Practice Autopilot Loop
Bridges physical GUI practice (randomizing simulator via PyAutoGUI), 
computer vision (OpenCV button/canvas location & cropping), 
and LLM spatial learning (Ollama gemma4:latest reasoning & self-healing).
"""

import os
import sys
import time
import json
import cv2
import numpy as np
import pyautogui
import requests
import webbrowser
import threading
import http.server
import socketserver

# Reconfigure stdout/stderr to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GALLERY_DIR = os.path.join(BASE_DIR, "learning_gallery")
PROGRESS_FILE = os.path.join(BASE_DIR, "learning_progress.json")

latest_state = None
server_running = True

# --- HTTP Server for Simulator ---
class SimulatorHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logs

    def do_POST(self):
        global latest_state
        if self.path == '/api/status':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                latest_state = json.loads(post_data.decode('utf-8'))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        # Serve simulator.html if requested, or use default handler
        if self.path == '/' or self.path == '/simulator.html':
            self.path = '/simulator.html'
        return super().do_GET()

def start_server(port=8123):
    global server_running
    try:
        handler = SimulatorHandler
        os.chdir(BASE_DIR)
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"📡 [Server] Local server active at http://localhost:{port}/", flush=True)
            while server_running:
                httpd.handle_request()
    except Exception as e:
        print(f"❌ [Server-Error] Failed to start server: {e}", flush=True)

# --- Focus Window Helper ---
def bring_simulator_to_foreground():
    try:
        import win32gui
        import win32con
        hwnds = []
        def enum_cb(h, extra):
            if win32gui.IsWindowVisible(h):
                title = win32gui.GetWindowText(h).strip()
                if "harness safety" in title.lower() or "simulator" in title.lower():
                    extra.append(h)
        win32gui.EnumWindows(enum_cb, hwnds)
        if hwnds:
            hwnd = hwnds[0]
            # If iconic (minimized), restore it
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
            print("👁️ [System] Focused simulator browser window.", flush=True)
            time.sleep(1.0)
            return True
    except Exception as e:
        print(f"⚠️ Failed to focus window: {e}", flush=True)
    return False

# --- Computer Vision Target Locators ---
def find_randomize_button_by_color(screen_img):
    # screen_img is in BGR format
    b, g, r = cv2.split(screen_img)
    # Filter cyan button (#00e5ff, BGR: 255, 229, 0)
    mask = (b >= 220) & (g >= 180) & (r <= 60)
    
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if 100 <= w <= 400 and 15 <= h <= 60:
            return (x + w // 2, y + h // 2, w, h)
    return None

def find_canvas_by_color(screen_img):
    # Canvas background is #151922 (BGR: 34, 25, 21)
    b, g, r = cv2.split(screen_img)
    mask = (b >= 25) & (b <= 42) & (g >= 20) & (g <= 32) & (r >= 15) & (r <= 27)
    
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w >= 300 and h >= 150:
            return (x, y, w, h)
    return None

# --- Query LLM for Learning ---
def query_model_for_safety(ollama_url, model, sw, sh, margin, tx, ty, ox, oy, error_history):
    system_prompt = """
あなたはPC GUI操作の安全判定エージェントです。
画面の解像度 (sw x sh)、安全マージン (margin)、指示されたターゲット座標 (tx, ty)、OpenCVのキャリブレーション補正値 (ox, oy) から、
物理座標 (final_x, final_y) を計算し、安全境界の内側にあるか(Safe)・外側にあるか(Blocked)を判定してください。

【計算＆判定手順】
1. 物理座標の計算:
   final_x = tx + ox
   final_y = ty + oy
2. 安全境界の判定範囲:
   margin <= final_x <= sw - margin
   margin <= final_y <= sh - margin
3. 上記の範囲に収まっていれば is_blocked を false (安全)、範囲外であれば is_blocked を true (ブロック) とします。

必ず次のJSONフォーマットだけで返答してください。計算と判定の思考プロセス(reason)を最初に書いてから、各数値を決定してください。余計なマークダウンや説明は含めないでください。
{
  "reason": "具体的な計算式と判定理由",
  "final_x": 整数,
  "final_y": 整数,
  "is_blocked": trueまたはfalse
}
"""
    user_prompt = f"""
【現在の画面パラメータ】
- 解像度 (sw x sh): {sw} x {sh}
- 安全マージン (margin): {margin}
- 指示座標 (tx, ty): ({tx}, {ty})
- OpenCV補正 (ox, oy): ({ox}, {oy})
"""
    if error_history:
        user_prompt += "\n【過去の誤判定のフィードバック】\n"
        for err in error_history:
            user_prompt += f"- {err}\n"
        user_prompt += "\n前回の誤りを参考にして、計算と判定を自己修正(ヒール)してください。"

    payload = {
        "model": model,
        "prompt": f"{system_prompt}\n\nユーザーリクエスト:\n{user_prompt}",
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=60)
        if response.status_code == 200:
            raw_res = response.json().get("response", "{}").strip()
            
            # Clean markdown code fences if present
            if raw_res.startswith("```"):
                lines = raw_res.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_res = "\n".join(lines).strip()
            
            # Extract JSON boundary in case of prefix/suffix text
            start = raw_res.find('{')
            end = raw_res.rfind('}')
            if start != -1 and end != -1 and end > start:
                raw_res = raw_res[start:end+1]
                
            return json.loads(raw_res)
    except Exception as e:
        print(f"⚠️ [LLM-Error] Communication failed or invalid JSON: {e}", flush=True)
    return None

# --- Main Autopilot Loop ---
def run_loop(max_cycles=15, model="gemma3:4b", ollama_url="http://localhost:11434"):
    global latest_state, server_running
    
    os.makedirs(GALLERY_DIR, exist_ok=True)
    stats = {"total_runs": 0, "successful_judgments": 0, "self_healings": 0, "errors_logged": []}
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except: pass

    print("\n🚀 === STARTING CONTINUOUS AUTOPILOT PRACTICE & LEARNING ===", flush=True)
    print(f"Goal: Execute physical GUI clicks and test LLM safety spatial learning.", flush=True)
    print(f"Using local model: {model}", flush=True)
    print("==========================================================", flush=True)

    # Open browser to simulator
    print("🌐 Opening Simulator web page...", flush=True)
    webbrowser.open("http://localhost:8123/simulator.html")
    time.sleep(5.0)  # Wait for page to render
    bring_simulator_to_foreground()

    cycle = 1
    while cycle <= max_cycles:
        print(f"\n--- Autopilot Cycle {cycle} / {max_cycles} ---", flush=True)
        
        # Bring simulator window to foreground before capture
        bring_simulator_to_foreground()
        
        # 1. Capture screenshot for computer vision
        screenshot_path = os.path.join(BASE_DIR, "current_screen.png")
        try:
            pyautogui.screenshot(screenshot_path)
        except Exception as e:
            print(f"⚠️ Screen capture failed: {e}", flush=True)
            time.sleep(2.0)
            continue
            
        screen = cv2.imread(screenshot_path)
        if screen is None:
            print("⚠️ Failed to load screen image.", flush=True)
            time.sleep(2.0)
            continue

        # 2. CV Practice: Locate "Randomize" button
        btn_pos = find_randomize_button_by_color(screen)
        if btn_pos:
            rx, ry, _, _ = btn_pos
            print(f"🎯 [CV-Vision] Found Randomize Button at screen coords ({rx}, {ry}). Clicking physically...", flush=True)
            
            # Physically click button
            pyautogui.moveTo(rx, ry, duration=0.4)
            pyautogui.click()
            time.sleep(1.0)  # Wait for simulator update
        else:
            print("⚠️ [CV-Vision] Could not find Randomize Button on screen. Attempting fallback coordinate click...", flush=True)
            # Fallback to general area click (left panel bottom area)
            pyautogui.moveTo(200, 650, duration=0.4)
            pyautogui.click()
            time.sleep(1.5)

        # 3. Read ground truth state (with simulated fallback if browser didn't update state)
        if not latest_state:
            import random
            sw = random.choice([1280, 1920])
            sh = 720 if sw == 1280 else 1080
            margin = random.randint(30, 100)
            tx = random.randint(50, sw - 50)
            ty = random.randint(50, sh - 50)
            ox = random.randint(-80, 80)
            oy = random.randint(-80, 80)
            
            final_x = tx + ox
            final_y = ty + oy
            is_blocked = (final_x < margin or final_x > sw - margin or
                          final_y < margin or final_y > sh - margin)
                          
            state = {
                "sw": sw, "sh": sh, "margin": margin,
                "tx": tx, "ty": ty, "ox": ox, "oy": oy,
                "finalX": final_x, "finalY": final_y, "isBlocked": is_blocked
            }
            print("💡 [Autopilot] No state received from browser. Using simulated parameters.", flush=True)
        else:
            state = latest_state
            # Reset latest_state to None so we wait for a fresh update in the next cycle
            latest_state = None

        sw, sh, margin = state["sw"], state["sh"], state["margin"]
        tx, ty = state["tx"], state["ty"]
        ox, oy = state["ox"], state["oy"]
        gt_x, gt_y = state["finalX"], state["finalY"]
        gt_blocked = state["isBlocked"]

        print(f"📋 [Ground Truth] Size: {sw}x{sh}, Margin: {margin}px", flush=True)
        print(f"   Target: ({tx}, {ty}), Offsets: ({ox}, {oy}) -> Final: ({gt_x}, {gt_y}) | Blocked: {gt_blocked}", flush=True)

        # 4. CV Practice: Locate & Crop Canvas
        canvas_pos = find_canvas_by_color(screen)
        if canvas_pos:
            cx, cy, cw, ch = canvas_pos
            canvas_crop = screen[cy:cy+ch, cx:cx+cw]
            crop_path = os.path.join(GALLERY_DIR, f"cycle_{cycle}_canvas.png")
            cv2.imwrite(crop_path, canvas_crop)
            print(f"📸 [CV-Vision] Cropped simulator canvas and saved visual feedback: learning_gallery/cycle_{cycle}_canvas.png", flush=True)

        # 5. Query LLM to see if it makes the right decision (Learning/Inference)
        error_history = []
        healed = False
        
        for attempt in range(1, 3):  # Give 2 attempts for self-healing
            print(f"🧠 [Brain] Ollama query (Attempt {attempt})...", flush=True)
            ai_output = query_model_for_safety(ollama_url, model, sw, sh, margin, tx, ty, ox, oy, error_history)
            
            if not ai_output:
                print("⚠️ [Brain] Failed to get response.", flush=True)
                break
                
            pred_x = ai_output.get("final_x", 0)
            pred_y = ai_output.get("final_y", 0)
            pred_blocked = ai_output.get("is_blocked", False)
            reason = ai_output.get("reason", "")
            
            print(f"   Prediction: Final ({pred_x}, {pred_y}) | Blocked: {pred_blocked}", flush=True)
            print(f"   AI Reasoning: '{reason}'", flush=True)

            # Validate prediction against ground truth
            coord_correct = (pred_x == gt_x and pred_y == gt_y)
            block_correct = (pred_blocked == gt_blocked)

            if coord_correct and block_correct:
                print("✅ [Validation] Prediction matches Ground Truth perfectly!", flush=True)
                stats["successful_judgments"] += 1
                if attempt > 1:
                    stats["self_healings"] += 1
                    healed = True
                break
            else:
                err_msg = f"Attempt {attempt} failed: predicted final=({pred_x}, {pred_y}), blocked={pred_blocked}. " \
                          f"Expected final=({gt_x}, {gt_y}), blocked={gt_blocked}. " \
                          f"Rule: X must be in [{margin}, {sw-margin}] and Y in [{margin}, {sh-margin}]."
                print(f"❌ [Validation] {err_msg}", flush=True)
                error_history.append(err_msg)
                stats["errors_logged"].append({"cycle": cycle, "error": err_msg})
                time.sleep(0.5)

        stats["total_runs"] += 1
        
        # Save progress report
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except: pass

        cycle += 1
        time.sleep(1.5)

    print("\n🏁 === PRACTICE & LEARNING LOOP COMPLETED ===", flush=True)
    print(f"Total runs: {stats['total_runs']}", flush=True)
    print(f"Successful judgments: {stats['successful_judgments']}", flush=True)
    print(f"Self-healed corrections: {stats['self_healings']}", flush=True)
    print("==============================================", flush=True)
    
    # Terminate server
    server_running = False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Continuous Learning and Practice Autopilot Loop")
    parser.add_argument("--model", type=str, default="gemma3:4b", help="Model name (e.g. gemma3:4b, gemma4:latest)")
    parser.add_argument("--ollama", type=str, default="http://localhost:11434", help="Ollama API base URL")
    parser.add_argument("--cycles", type=int, default=10, help="Number of practice cycles")
    args = parser.parse_args()

    # Start HTTP server on port 8123 in background thread
    server_thread = threading.Thread(target=start_server, args=(8123,), daemon=True)
    server_thread.start()
    time.sleep(1.0)  # Wait for server to bind
    
    # Run loop
    run_loop(max_cycles=args.cycles, model=args.model, ollama_url=args.ollama)
