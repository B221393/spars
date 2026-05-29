import os
import json
import time
import requests
from VOICE_RESCUE_PRO import VoiceSystem
from MODULE_MANAGER import ModuleManager
from AI_MENTAL_MODEL_VISUALIZER import generate_mental_model_svg

# --- 統合・自己進化オーケストレーター (イメージ具現化対応版) ---

BASE_DIR = "C:/Users/yu_ci/Desktop/codex-vs-local-agent-loop"
FINAL_LOG = os.path.join(BASE_DIR, "OUTPUT/FINAL_LOG.json")
ERROR_LOG = os.path.join(BASE_DIR, "OUTPUT/ERROR_LOG.json")
VOICE_HISTORY = os.path.join(BASE_DIR, "OUTPUT/VOICE_CLARITY_HISTORY.json")
FEEDBACK_REPORT = os.path.join(BASE_DIR, "OUTPUT/SYSTEM_FEEDBACK_REPORT.json")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class SelfEvolutionFramework:
    def __init__(self):
        self.vs = VoiceSystem()
        self.mm = ModuleManager()

    def gather_all_data(self):
        data = {"tasks": [], "errors": [], "voice": []}
        try:
            if os.path.exists(FINAL_LOG):
                with open(FINAL_LOG, "r", encoding="utf-8") as f: data["tasks"] = json.load(f)[:10]
            if os.path.exists(ERROR_LOG):
                with open(ERROR_LOG, "r", encoding="utf-8") as f: data["errors"] = json.load(f)[:5]
            if os.path.exists(VOICE_HISTORY):
                with open(VOICE_HISTORY, "r", encoding="utf-8") as f: data["voice"] = json.load(f)[:5]
        except: pass
        return data

    def generate_meta_feedback(self):
        print("🧠 具現化されたイメージと稼働データをメタ分析中...")
        all_logs = self.gather_all_data()
        
        prompt = f"""
あなたは自律進化型AI OSの「最高評価官」です。
現在、あなたは自分自身の「メンタルモデル（内部イメージ）」を具現化した図面を確認しています。
以下の全稼働データに基づき、自分自身の「仕事の質」を厳しく評価し、さらなる進化のためのフィードバックを行ってください。

【稼働データ】
{json.dumps(all_logs, indent=2, ensure_ascii=False)}

【フィードバックの要件】
1. 具現化されたイメージ（AI_MENTAL_MODEL.svg）から読み取れる「弱点」を指摘する。
2. 自己改善のための具体的な「物理的修正（コード変更）」を1つ以上決定してください。

【出力形式 (JSON)】
{{
  "overall_status": "（現在のシステムの総合評価）",
  "sera_thought": "（セラの褒め・提案）",
  "luci_thought": "（ルシの厳しい指摘）",
  "improvement_directive": "（即座に適用すべき改善命令）",
  "target_file": "（修正対象のファイル）"
}}
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "format": "json", "stream": False}, timeout=90)
            feedback = json.loads(res.json().get("response", "{}"))
            
            feedback["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(FEEDBACK_REPORT, "w", encoding="utf-8") as f:
                json.dump(feedback, f, indent=2, ensure_ascii=False)
            
            return feedback
        except Exception as e:
            print(f"❌ メタ分析エラー: {e}")
            return None

    def execute_evolution_cycle(self):
        # 1. まず現在のシステムの状態を「イメージ」として具現化する
        generate_mental_model_svg()
        
        # 2. 具現化したイメージとログをメタ分析する
        feedback = self.generate_meta_feedback()
        if not feedback: return

        print(f"\n✨ 自己フィードバック完了: {feedback['overall_status']}")
        
        if self.mm.is_enabled("voice_output"):
            self.vs.speak_sera(f"今回の自己評価だよ！{feedback['sera_thought']}")
            time.sleep(0.5)
            self.vs.speak_luci(f"俺からのダメ出しだ。{feedback['luci_thought']}")
        else:
            print(f"🔇 音声停止モード: {feedback['sera_thought']}")

        # 改善命令をタスクキューに登録
        directive = feedback.get('improvement_directive')
        if directive:
            print(f"🚀 改善命令を発令: {directive}")
            task_entry = f"[AUTO-EVOLVE] {directive}"
            with open(os.path.join(BASE_DIR, "INPUT/USER_TASKS.txt"), "a", encoding="utf-8") as f:
                f.write(f"\n{task_entry}")

    def run_forever(self):
        print("🚀 自己進化フレームワーク（イメージ具現化型）稼働開始。")
        while True:
            self.execute_evolution_cycle()
            print("💤 次の自己反省まで300秒待機...")
            time.sleep(300)

if __name__ == "__main__":
    framework = SelfEvolutionFramework()
    framework.run_forever()
