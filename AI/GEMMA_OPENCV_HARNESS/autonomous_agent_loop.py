#!/usr/bin/env python3
"""
Autonomous Agent Self-Healing Loop
Combines Gemma 4 8B reasoning, OpenCV calibration, and visual state verification (healing loop).
"""

import argparse
import json
import os
import sys
import time

# Resolve sys.path for absolute imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENRE_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
sys.path.append(os.path.join(GENRE_DIR, "AI"))
sys.path.append(os.path.join(GENRE_DIR, "AI", "CORE"))

from agent_harness import AgentHarness
from CORE.ai_driver import AIDriver


class AutonomousAgentLoop:
    def __init__(self, ollama_url="http://localhost:11434", model="gemma3:4b", safety_margin=50, simulate=False):
        self.simulate = simulate
        self.harness = AgentHarness(ollama_url=ollama_url, model=model, safety_margin=safety_margin)
        
        if not self.simulate:
            self.driver = AIDriver(target_title="Slay the Spire 2")
        else:
            self.driver = None

        # Load system prompt
        prompt_path = os.path.join(BASE_DIR, "system_prompt.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_instruction = f.read()
        else:
            self.system_instruction = "You are a PC GUI automation agent."

        # Keep track of action logs and failures for self-healing context
        self.error_history = []

    def run_calibration(self, template_path):
        """Measures screen offsets via OpenCV template matching."""
        if self.simulate:
            print("[Loop-Mock] Simulating OpenCV template calibration. Found mock_marker at (150, 120)")
            # Simulated target pos is (150, 120), expected is (100, 100). Offset = (+50, +20)
            self.harness.offset_x = 50
            self.harness.offset_y = 20
            return True

        print("[Loop] Performing screen offset calibration...")
        marker_pos = self.harness.run_calibration(template_path)
        if marker_pos:
            self.harness.offset_x = marker_pos[0] - 100
            self.harness.offset_y = marker_pos[1] - 100
            print(f"[Loop] Calibration active. Offsets: X={self.harness.offset_x}px, Y={harness.offset_y}px")
            return True
        else:
            print("[Loop-Warning] Calibration failed. Proceeding with zero offsets.")
            return False

    def get_current_ui_elements(self):
        """Returns mock screen elements data for LLM context."""
        return [
            {"id": 1, "name": "Settings Gear Icon", "x": 1200, "y": 40},
            {"id": 2, "name": "Library Tab", "x": 300, "y": 450},
            {"id": 3, "name": "Update Status Button", "x": 500, "y": 250},
            {"id": 4, "name": "Dangerous Zone Button", "x": 1250, "y": 700}
        ]

    def build_user_prompt(self, goal, elements):
        """Formulates the prompt, appending retry/error logs for the self-healing process."""
        prompt = f"""
【ユーザーの目的】
{goal}

【現在の画面状態 (OpenCV/OCR抽出データ)】
"""
        for el in elements:
            prompt += f"ID: {el['id']} | 名前: {el['name']} | X: {el['x']} | Y: {el['y']}\n"

        if self.error_history:
            prompt += "\n【前回までの行動履歴と失敗ログ】\n"
            for err in self.error_history:
                prompt += f"- {err}\n"
            prompt += "\n前回の失敗を繰り返さないように、座標の選択を自己修正(ヒール)してください。"

        return prompt

    def run_loop(self, goal, max_iterations=5):
        print(f"\n🚀 === STARTING AUTONOMOUS AGENT LOOP ===")
        print(f"Goal: {goal}")
        
        for iteration in range(1, max_iterations + 1):
            print(f"\n--- Cycle {iteration} / {max_iterations} ---")
            
            # 1. Fetch current UI layout
            elements = self.get_current_ui_elements()
            
            # 2. Build self-healing prompt
            user_prompt = self.build_user_prompt(goal, elements)
            
            # 3. Query Gemma VLM/LLM
            print("[Brain] Querying Gemma 4 8B for next action...")
            if self.simulate:
                # Mock LLM outputs for testing the healing loop logic
                # Cycle 1: Click the Dangerous Zone Button (will violate safety margin)
                # Cycle 2: Click the Update Status Button but simulate click verification failure
                # Cycle 3: Click the Library Tab (success!)
                # Cycle 4: Done
                if iteration == 1:
                    brain_output = {
                        "action": "click",
                        "target_x": 1250,
                        "target_y": 700,
                        "input_text": "",
                        "reason": "設定を開くため"
                    }
                elif iteration == 2:
                    brain_output = {
                        "action": "click",
                        "target_x": 500,
                        "target_y": 250,
                        "input_text": "",
                        "reason": "ステータス更新をするため"
                    }
                elif iteration == 3:
                    brain_output = {
                        "action": "click",
                        "target_x": 300,
                        "target_y": 450,
                        "input_text": "",
                        "reason": "ライブラリを表示するため"
                    }
                else:
                    brain_output = {
                        "action": "done",
                        "target_x": 0,
                        "target_y": 0,
                        "input_text": "",
                        "reason": "目的が達成されたため"
                    }
            else:
                brain_output = self.harness.query_gemma_brain(self.system_instruction, user_prompt)

            if not brain_output:
                print("[Brain-Error] Could not decode brain output. Retrying cycle.")
                self.error_history.append("エラー: Gemmaからの応答が空、またはJSONフォーマットが無効でした。")
                continue

            print(f"[Brain Output]: Action={brain_output.get('action')}, Target=({brain_output.get('target_x')}, {brain_output.get('target_y')}), Reason='{brain_output.get('reason')}'")
            
            action = brain_output.get("action", "wait")
            tx = brain_output.get("target_x", 0)
            ty = brain_output.get("target_y", 0)
            text = brain_output.get("input_text", "")

            if action == "done":
                print("🎉 [Loop] Success! Gemma Brain confirmed task completion.")
                return True

            # 4. Safety Validation Check
            final_x = tx + self.harness.offset_x
            final_y = ty + self.harness.offset_y
            
            # Check boundaries
            if (final_x < self.harness.safety_margin or final_x > self.harness.screen_width - self.harness.safety_margin or
                    final_y < self.harness.safety_margin or final_y > self.harness.screen_height - self.harness.safety_margin):
                err_msg = f"物理キルスイッチ作動: 補正座標 ({final_x}, {final_y}) はセーフティ領域外です。操作を遮断しました。"
                print(f"⚠️ [FAIL-SAFE] {err_msg}")
                self.error_history.append(err_msg)
                continue

            # 5. Physical Action & Verification
            if self.simulate:
                # Simulate verification outcomes
                if tx == 500 and ty == 250:
                    # Simulate click verification failure (no state change)
                    err_msg = "操作失敗: 座標(500, 250)をクリックしましたが画面に変化がありませんでした (ボタンが押せない、または無効)。"
                    print(f"⚠️ [Verify-Mock] {err_msg}")
                    self.error_history.append(err_msg)
                else:
                    # Successful action simulation
                    print(f"[Action-Mock] Successfully clicked at coordinate ({final_x}, {final_y}). State changed.")
            else:
                # Run actual AIDriver verification
                success = self.driver.execute_and_verify(f"AI Loop click", final_x, final_y)
                if not success:
                    err_msg = f"操作検証エラー: 座標({final_x}, {final_y})のクリックが画面の状態遷移をもたらしませんでした。"
                    print(f"⚠️ [Verify] {err_msg}")
                    self.error_history.append(err_msg)
                    continue

        print("\n❌ [Loop] Failed! Reached maximum iteration limit without task completion.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Autonomous Agent Self-Healing Loop CLI")
    parser.add_argument("--simulate", action="store_true", help="Run in mock simulation mode.")
    parser.add_argument("--ollama", type=str, default="http://localhost:11434", help="Ollama API base URL.")
    parser.add_argument("--model", type=str, default="gemma3:4b", help="LLM model name.")
    parser.add_argument("--goal", type=str, default="ライブラリを開き、安全にアップデートを確認してください。", help="User automation goal.")
    
    args = parser.parse_args()

    # Instantiate loop
    agent_loop = AutonomousAgentLoop(
        ollama_url=args.ollama,
        model=args.model,
        safety_margin=100,
        simulate=args.simulate
    )
    
    # Configure mock resolution for simulated runs
    if args.simulate:
        agent_loop.harness.screen_width = 1280
        agent_loop.harness.screen_height = 720

    # Execute calibration
    agent_loop.run_calibration("mock_steam_marker.png")
    
    # Run the autonomous loop
    agent_loop.run_loop(args.goal)


if __name__ == "__main__":
    main()
