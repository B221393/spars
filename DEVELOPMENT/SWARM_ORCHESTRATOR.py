import requests
import json
import os
import subprocess
import datetime
import time
import sys

# Windows環境での文字コードエラーを防ぐための設定
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# --- Company Brain: Full Local Multi-Agent Swarm (V6) ---
# 全てを「ローカルLLM (Ollama)」で完結させます。クラウド通信は一切行いません。

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:4b"  # 高速・軽量モデル
THINKING_MODEL = "qwen3:8b" # 深い思考が必要なタスク用

class LocalAgent:
    def __init__(self, role, goal, model=DEFAULT_MODEL):
        self.role = role
        self.goal = goal
        self.model = model

    def ask(self, prompt):
        print(f"🤖 [Local Thinking] {self.role} ({self.model}) is processing...")
        full_prompt = f"あなたは{self.role}です。目標: {self.goal}\n\n{prompt}"
        try:
            # タイムアウトを長めに設定してローカルでの思考を待機
            res = requests.post(OLLAMA_URL, json={"model": self.model, "prompt": full_prompt, "stream": False}, timeout=180)
            return res.json().get("response", "Error: No response")
        except Exception as e:
            return f"Local Engine Error: {e}"

class Dispatcher:
    """タスクの難易度に応じて、ローカルモデルを使い分ける"""
    def __init__(self):
        self.selector = LocalAgent("Dispatcher", "タスクの難易度判定とルーティング")

    def dispatch(self, role, goal, prompt, complexity_level=1):
        # 複雑度が高い場合は 8B 以上のモデルを使用し、それ以外は高速な 4B モデルを使用
        model = THINKING_MODEL if complexity_level >= 3 else DEFAULT_MODEL
        return LocalAgent(role, goal, model=model).ask(prompt)

class CompanyBrainSwarm:
    def __init__(self):
        self.dispatcher = Dispatcher()
        self.iteration = 1
        self.docs_dir = os.path.join("GENRE_FOLDERS", "DOCS")
        self.feedback_dir = os.path.join(self.docs_dir, "FEEDBACK")
        os.makedirs(self.feedback_dir, exist_ok=True)

    def run_cycle(self):
        print(f"\n===== 🏠 Full Local Swarm Iteration {self.iteration} =====")
        
        # 1. Planning (Level 3: ローカルの強力なモデルで戦略を立てる)
        plan = self.dispatcher.dispatch("Planner", "全体戦略", 
                                        "これまでの成果を分析し、ローカルAIだけでプロジェクトを最大限進化させるための計画を立ててください。", 
                                        complexity_level=3)
        print(f"📍 Strategy (Local): {plan[:50]}...")

        # 2. Action (実作業)
        print("🚀 タスク実行中...")
        subprocess.run(f"python {os.path.join('GENRE_FOLDERS', 'RESEARCH', 'PRO_TRAJECTORY_TRACKER.py')}", shell=True)
        subprocess.run(f"python {os.path.join('GENRE_FOLDERS', 'SHOGI', 'JOSEKI_ANALYZER.py')}", shell=True)

        # 3. Audit (Level 2: 品質チェック)
        audit = self.dispatcher.dispatch("Auditor", "品質管理", 
                                        "最新の成果物をCLARITY_HARNESSの基準で評価し、具体的な改善メモを生成してください。", 
                                        complexity_level=2)
        
        # 4. Logging & Memo
        self.log_results(plan, audit)
        self.save_feedback_memo(plan, audit)
        
        self.iteration += 1

    def log_results(self, plan, audit):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        log_entry = f"| **Iter {self.iteration} (Local)** | {now} | {plan[:30]}... | {audit[:20]}... |\n"
        with open(os.path.join(self.docs_dir, 'CLARITY_HARNESS.md'), "a", encoding="utf-8") as f:
            f.write(log_entry)

    def save_feedback_memo(self, plan, audit):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memo_path = os.path.join(self.feedback_dir, f"Iteration_{self.iteration}_LocalMemo.md")
        
        content = f"# 🏠 Iteration {self.iteration} : ローカルAI自律改善メモ\n"
        content += f"**記録日時**: {now}\n"
        content += f"**使用モデル**: {THINKING_MODEL} / {DEFAULT_MODEL}\n\n"
        content += f"## 🎯 1. ローカル戦略計画\n{plan}\n\n"
        content += f"## 🧐 2. ローカル品質監査\n{audit}\n\n"
        content += "---\n*100% Local Evolution via Ollama*"
        
        with open(memo_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📝 ローカルメモを保存しました: {memo_path}")

if __name__ == "__main__":
    swarm = CompanyBrainSwarm()
    while True:
        swarm.run_cycle()
        print("\n💤 次のサイクルまで待機します...")
        time.sleep(300)
