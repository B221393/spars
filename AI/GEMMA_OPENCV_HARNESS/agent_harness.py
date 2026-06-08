#!/usr/bin/env python3
"""
Gemma 4 8B + OpenCV Agent Harness
Bridges local lightweight LLM reasoning, OpenCV visual calibration, and PyAutoGUI execution.
"""

import argparse
import json
import os
import sys
import cv2
import pyautogui
import requests
import time
import win32clipboard

# Reconfigure stdout/stderr to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass


def set_clipboard_text(text):
    """
    Sets text to the Windows clipboard using CF_UNICODETEXT (13) to prevent IME issues.
    """
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, 13)  # 13 = CF_UNICODETEXT
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"[Clipboard-Error] Failed to set clipboard text: {e}")
        try:
            win32clipboard.CloseClipboard()
        except:
            pass
        return False


class LightweightCalibrator:
    """
    Lightweight local spatial calibrator that tracks the error offset (systematic error/習性誤差)
    between where clicks were executed and where the screen actually responded.
    Maintains a rolling history of the last 100 clicks to dynamically compute statistical averages
    and patterns, applying the calculated offsets to self-heal coordinates.
    """
    def __init__(self, max_history=100, report_path="click_calibration_data.json"):
        self.max_history = max_history
        self.report_path = report_path
        self.click_history = []
        self.mean_dx = 0.0
        self.mean_dy = 0.0
        self.std_dx = 0.0
        self.std_dy = 0.0
        self.trend = "No data yet"
        
        # Load persistent stats if file exists
        if os.path.exists(self.report_path):
            try:
                with open(self.report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.click_history = data.get("click_history", [])
                    self.mean_dx = data.get("mean_dx", 0.0)
                    self.mean_dy = data.get("mean_dy", 0.0)
                    self.std_dx = data.get("std_dx", 0.0)
                    self.std_dy = data.get("std_dy", 0.0)
                    self.trend = data.get("trend", "No data yet")
            except Exception as e:
                print(f"[Calibrator-Warning] Failed to load persistent calibration data: {e}")

    def record_click_feedback(self, clicked_x, clicked_y, actual_x, actual_y):
        """
        Record coordinate feedback from visual state change and compute rolling stats.
        """
        dx = actual_x - clicked_x
        dy = actual_y - clicked_y
        
        self.click_history.append({
            "target": [clicked_x, clicked_y],
            "actual": [actual_x, actual_y],
            "dx": dx,
            "dy": dy,
            "timestamp": time.time()
        })
        
        # Maintain rolling buffer of max_history
        if len(self.click_history) > self.max_history:
            self.click_history.pop(0)
            
        self.compute_statistics()
        self.save_calibration_report()

    def compute_statistics(self):
        """
        Compute mean, standard deviation, and detect pattern trends for the rolling buffer.
        """
        import math
        n = len(self.click_history)
        if n == 0:
            return
            
        dxs = [item['dx'] for item in self.click_history]
        dys = [item['dy'] for item in self.click_history]
        
        self.mean_dx = sum(dxs) / n
        self.mean_dy = sum(dys) / n
        
        var_dx = sum((x - self.mean_dx)**2 for x in dxs) / n
        var_dy = sum((y - self.mean_dy)**2 for y in dys) / n
        
        self.std_dx = math.sqrt(var_dx)
        self.std_dy = math.sqrt(var_dy)
        
        # Categorize systematic error pattern
        trends = []
        if self.std_dx < 8.0:
            if self.mean_dx > 10.0:
                trends.append("Constant shift Right")
            elif self.mean_dx < -10.0:
                trends.append("Constant shift Left")
        if self.std_dy < 8.0:
            if self.mean_dy > 10.0:
                trends.append("Constant shift Down")
            elif self.mean_dy < -10.0:
                trends.append("Constant shift Up")
                
        if not trends:
            if self.std_dx < 5.0 and self.std_dy < 5.0 and abs(self.mean_dx) <= 5.0 and abs(self.mean_dy) <= 5.0:
                self.trend = "Centered and accurate"
            else:
                self.trend = "Variable/random errors"
        else:
            self.trend = " & ".join(trends)
            
        print(f"📈 [Calibrator] Stats over {n} points: mean_dx={self.mean_dx:.2f}px, mean_dy={self.mean_dy:.2f}px. "
              f"Pattern trend: '{self.trend}'", flush=True)

    def save_calibration_report(self):
        """
        Saves the stats and history in JSON format.
        """
        try:
            report = {
                "total_clicks": len(self.click_history),
                "mean_dx": self.mean_dx,
                "mean_dy": self.mean_dy,
                "std_dx": self.std_dx,
                "std_dy": self.std_dy,
                "trend": self.trend,
                "click_history": self.click_history
            }
            with open(self.report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Calibrator-Error] Failed to save calibration report: {e}")

    def apply_systematic_correction(self, target_x, target_y):
        """
        Applies the learned systematic correction locally.
        """
        corrected_x = target_x + int(round(self.mean_dx))
        corrected_y = target_y + int(round(self.mean_dy))
        return corrected_x, corrected_y


class AgentHarness:
    def __init__(self, ollama_url="http://localhost:11434", model="gemma3:4b", safety_margin=50):
        self.ollama_url = ollama_url
        self.model = model
        
        # Coordinate correction offsets (measured by OpenCV calibration)
        self.offset_x = 0
        self.offset_y = 0
        
        # Local systematic calibrator for dynamic corrections (習性誤差補正器)
        self.calibrator = LightweightCalibrator()
        
        # Get active screen resolution
        try:
            self.screen_width, self.screen_height = pyautogui.size()
        except Exception:
            # Fallback for headless environments/tests
            self.screen_width, self.screen_height = 1920, 1080
        
        # Safety margin (kill switch boundary near the edges)
        self.safety_margin = safety_margin

    def run_calibration(self, template_image_path, confidence=0.8):
        """
        Runs OpenCV template matching on a screenshot to compute spatial offset.
        Compares the detected marker location with the theoretical/target location.
        """
        if not os.path.exists(template_image_path):
            print(f"[Harness-Warning] Calibration template image not found: {template_image_path}")
            return None

        # Capture a screenshot
        screenshot_path = "harness_temp_screen.png"
        try:
            pyautogui.screenshot(screenshot_path)
        except Exception as e:
            print(f"[Harness-Error] Failed to capture screenshot: {e}")
            return None
        
        # Read images
        screen_img = cv2.imread(screenshot_path)
        template_img = cv2.imread(template_image_path)
        
        if screen_img is None or template_img is None:
            print("[Harness-Error] Failed to load screenshots or templates into OpenCV.")
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            return None

        # Perform template matching
        result = cv2.matchTemplate(screen_img, template_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        # If confidence is high enough, locate coordinates
        if max_val >= confidence:
            t_h, t_w, _ = template_img.shape
            detected_x = max_loc[0] + t_w // 2
            detected_y = max_loc[1] + t_h // 2
            
            print(f"[Harness-Vision] Target found! Position: ({detected_x}, {detected_y}), confidence: {max_val:.4f}")
            
            # Save temporary copy for cropping
            cv2.imwrite("matched_temp_screen.png", screen_img)
            
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            return (detected_x, detected_y)
        
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        print(f"[Harness-Vision] Target match failed. Max confidence was: {max_val:.4f}")
        return None

    def click_template_on_screen(self, template_image_path, confidence_threshold=0.8):
        """
        Takes a screenshot, performs template matching to find the template (e.g. arrow),
        and if match confidence exceeds the threshold, executes a corrected click on its center.
        """
        pos = self.run_calibration(template_image_path, confidence=confidence_threshold)
        if pos:
            detected_x, detected_y = pos
            print(f"[Harness-TemplateClick] Template '{template_image_path}' matched at ({detected_x}, {detected_y}).")
            
            # Crop matched area for visual validation
            if os.path.exists("matched_temp_screen.png"):
                try:
                    screen_img = cv2.imread("matched_temp_screen.png")
                    template_img = cv2.imread(template_image_path)
                    if screen_img is not None and template_img is not None:
                        t_h, t_w, _ = template_img.shape
                        # Reconstruct bounding box
                        x1 = max(0, detected_x - t_w // 2)
                        y1 = max(0, detected_y - t_h // 2)
                        x2 = min(screen_img.shape[1], x1 + t_w)
                        y2 = min(screen_img.shape[0], y1 + t_h)
                        
                        crop = screen_img[y1:y2, x1:x2]
                        os.makedirs("learning_gallery", exist_ok=True)
                        crop_path = f"learning_gallery/matched_button_{int(time.time())}.png"
                        cv2.imwrite(crop_path, crop)
                        print(f"[Harness-TemplateClick] Saved matched crop snippet to: {crop_path}")
                except Exception as e:
                    print(f"[Harness-TemplateClick-Warning] Failed to crop matched button: {e}")
                finally:
                    try: os.remove("matched_temp_screen.png")
                    except: pass
            
            # Execute physical interaction with corrected coordinates
            success = self.execute_safe_action(detected_x, detected_y, action_type="click")
            return success
        else:
            print(f"[Harness-TemplateClick] Match failed for '{template_image_path}'. No click executed.")
            return False

    def execute_safe_action(self, target_x, target_y, action_type="click", input_text=""):
        """
        Validates target coordinates with safety margins, applies offsets, and executes physical interaction.
        """
        # Apply local systematic correction (習性誤差補正) first
        corr_x, corr_y = self.calibrator.apply_systematic_correction(target_x, target_y)
        if corr_x != target_x or corr_y != target_y:
            print(f"[Harness-Local] Applied systematic offset (習性誤差) correction: "
                  f"({target_x}, {target_y}) -> ({corr_x}, {corr_y})", flush=True)

        final_x = corr_x + self.offset_x
        final_y = corr_y + self.offset_y
        
        # FAIL-SAFE: Check boundaries
        if (final_x < self.safety_margin or final_x > self.screen_width - self.safety_margin or
                final_y < self.safety_margin or final_y > self.screen_height - self.safety_margin):
            print(f"[FAIL-SAFE TRIGGERED] Operation blocked! Coordinates ({final_x}, {final_y}) violate safety boundary margin of {self.safety_margin}px.")
            return False
            
        try:
            if action_type == "click":
                # Move naturally and click
                pyautogui.moveTo(final_x, final_y, duration=0.3)
                pyautogui.click()
                print(f"[Harness-Action] Successfully clicked at coordinate ({final_x}, {final_y}).")
                return True
            elif action_type == "type":
                # Move, click to focus, then paste via clipboard to bypass Japanese IME
                pyautogui.moveTo(final_x, final_y, duration=0.3)
                pyautogui.click()
                time.sleep(0.2)
                if set_clipboard_text(input_text):
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(0.15)
                    print(f"[Harness-Action] Successfully pasted text '{input_text}' via clipboard at ({final_x}, {final_y}).")
                else:
                    pyautogui.write(input_text, interval=0.05)
                    print(f"[Harness-Action-Fallback] Successfully typed text '{input_text}' at ({final_x}, {final_y}).")
                return True
            elif action_type == "wait":
                print(f"[Harness-Action] Standby wait triggered.")
                time.sleep(1.0)
                return True
            elif action_type == "done":
                print(f"[Harness-Action] Task completed confirmation received.")
                return True
        except Exception as e:
            print(f"[Harness-Error] Failed to execute desktop actions: {e}")
            return False

    def query_gemma_brain(self, system_instruction, user_request):
        """
        Queries the Ollama server for Gemma 4 8B outputs in structured JSON format.
        """
        structured_prompt = f"""
        {system_instruction}
        
        ユーザーからのリクエスト: {user_request}
        
        応答は必ず以下の純粋なJSONフォーマットのみで回答してください（マークダウンの```json等の装飾は一切不要です）。
        {{
            "reason": "ボタンを押して進めるため",
            "action": "click",
            "target_x": 300,
            "target_y": 450,
            "input_text": ""
        }}
        """
        
        payload = {
            "model": self.model,
            "prompt": structured_prompt,
            "stream": False,
            "format": "json"  # Ollama JSON mode
        }
        
        try:
            url = f"{self.ollama_url}/api/generate"
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                raw_res = response.json().get("response", "{}")
                parsed_json = json.loads(raw_res)
                return parsed_json
            else:
                print(f"[Harness-Error] Ollama server returned status code: {response.status_code}")
        except json.JSONDecodeError:
            print("[Harness-Validator] Failed to decode structured JSON from Gemma output.")
        except Exception as e:
            print(f"[Harness-Error] Communication failure with Ollama API: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Gemma 4 8B + OpenCV Agent Harness Driver CLI")
    parser.add_argument("--ollama", type=str, default="http://localhost:11434", help="Ollama base URL.")
    parser.add_argument("--model", type=str, default="gemma3:4b", help="Model name.")
    parser.add_argument("--template", type=str, default="steam_marker.png", help="Template image path.")
    parser.add_argument("--request", type=str, default="画面の更新ボタンを押してください。", help="User request instruction.")
    
    args = parser.parse_args()

    harness = AgentHarness(ollama_url=args.ollama, model=args.model)
    
    # Load system prompt
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
    system_instruction = ""
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()
    else:
        system_instruction = "You are a desktop automation agent."

    print("--- Running OpenCV Calibration ---")
    marker_pos = harness.run_calibration(args.template)
    if marker_pos:
        # Standard calibration logic (relative to target coord 100, 100)
        harness.offset_x = marker_pos[0] - 100
        harness.offset_y = marker_pos[1] - 100
        print(f"[Harness] Calibration active. Offsets: X={harness.offset_x}px, Y={harness.offset_y}px")

    print("\n--- Querying Gemma 4 Brain via Ollama ---")
    brain_output = harness.query_gemma_brain(system_instruction, args.request)
    
    if brain_output:
        print(f"[Gemma-Brain Output]:\n{json.dumps(brain_output, ensure_ascii=False, indent=2)}")
        action = brain_output.get("action", "wait")
        tx = brain_output.get("target_x", 0)
        ty = brain_output.get("target_y", 0)
        text = brain_output.get("input_text", "")
        
        print("\n--- Validating & Executing Desktop Action ---")
        harness.execute_safe_action(tx, ty, action_type=action, input_text=text)


if __name__ == "__main__":
    main()
