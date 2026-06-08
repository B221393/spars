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

# Reconfigure stdout/stderr to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass


class AgentHarness:
    def __init__(self, ollama_url="http://localhost:11434", model="gemma4:8b", safety_margin=50):
        self.ollama_url = ollama_url
        self.model = model
        
        # Coordinate correction offsets (measured by OpenCV calibration)
        self.offset_x = 0
        self.offset_y = 0
        
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
            
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            return (detected_x, detected_y)
        
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        print(f"[Harness-Vision] Target match failed. Max confidence was: {max_val:.4f}")
        return None

    def execute_safe_action(self, target_x, target_y, action_type="click", input_text=""):
        """
        Validates target coordinates with safety margins, applies offsets, and executes physical interaction.
        """
        final_x = target_x + self.offset_x
        final_y = target_y + self.offset_y
        
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
                # Move, click to focus, then type
                pyautogui.moveTo(final_x, final_y, duration=0.3)
                pyautogui.click()
                time.sleep(0.1)
                pyautogui.write(input_text, interval=0.05)
                print(f"[Harness-Action] Successfully typed text '{input_text}' at ({final_x}, {final_y}).")
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
        
        応答は必ず以下の純粋なJSONフォーマットのみで出力してください（マークダウンの```json等の装飾は一切不要です）。
        {{
            "action": "click",
            "target_x": 300,
            "target_y": 450,
            "input_text": "",
            "reason": "ボタンを押して進めるため"
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
    parser.add_argument("--model", type=str, default="gemma4:8b", help="Model name.")
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
