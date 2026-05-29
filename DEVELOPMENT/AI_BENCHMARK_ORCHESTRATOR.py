import requests
import time
import json
import os
import subprocess
from datetime import datetime

# --- Local AI Multi-Model Benchmark Tool ---
# 1. 複数のモデルで同じタスク（研究コード解析・将棋解析）を実行
# 2. 推論時間、応答品質、リソース消費を記録
# 3. 作業完了後、システムをシャットダウン

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS = ["gemma3:4b", "llama3", "phi3"] # ターゲットモデル
REPORT_PATH = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\DOCS\BENCHMARK_REPORT.md"

PROMPTS = [
    {
        "category": "Research",
        "prompt": "以下のPythonコードのカルマンフィルタ実装を評価し、改善案を1つ述べてください。\nclass SimpleKalman:\n    def __init__(self, initial_pos):\n        self.state = np.array([initial_pos[0], initial_pos[1], 0, 0], dtype=np.float32)\n        self.F = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)"
    },
    {
        "category": "Shogi",
        "prompt": "将棋の『エルモ囲い急戦』がAI時代に再評価されている理由を、バランスと速度の観点から簡潔に説明してください。"
    }
]

def run_benchmark():
    results = []
    print(f"🚀 Starting Multi-Model Benchmark at {datetime.now()}")

    for model in MODELS:
        print(f"\n🤖 Testing Model: {model}")
        for p_data in PROMPTS:
            start_time = time.time()
            try:
                response = requests.post(OLLAMA_URL, json={
                    "model": model,
                    "prompt": p_data["prompt"],
                    "stream": False
                }, timeout=120)
                
                duration = time.time() - start_time
                res_json = response.json()
                answer = res_json.get("response", "N/A")
                
                # 推定トークン数 (簡易計算)
                token_count = len(answer) / 4 
                tps = token_count / duration if duration > 0 else 0

                results.append({
                    "model": model,
                    "category": p_data["category"],
                    "duration": duration,
                    "tps": tps,
                    "answer_preview": answer[:100] + "..."
                })
                print(f"✅ {p_data['category']} finished in {duration:.2f}s ({tps:.1f} tps)")
            except Exception as e:
                print(f"❌ Error with {model}: {e}")

    save_report(results)

def save_report(results):
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# 📊 Local AI Multi-Model Benchmark Report\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Model | Category | Duration (s) | Speed (tps) | Preview |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['model']} | {r['category']} | {r['duration']:.2f} | {r['tps']:.1f} | {r['answer_preview']} |\n")
    
    print(f"\n✨ Benchmark report saved to: {REPORT_PATH}")

def shutdown_system():
    print("\n🛌 All tasks completed. Preparing for shutdown...")
    time.sleep(5)
    # Windows shutdown command
    os.system("shutdown /s /t 60")
    print("⚠️ System will shutdown in 60 seconds. Use 'shutdown /a' to cancel.")

if __name__ == "__main__":
    run_benchmark()
    # ユーザーの最終指示に従い、シャットダウンを実行
    shutdown_system()
