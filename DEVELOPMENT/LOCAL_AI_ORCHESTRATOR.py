import requests
import json
import os
import time

# --- ローカルAI (Ollama) によるタスク自動処理コア ---
# 将棋フィードバック、公務員試験対策、システム管理などを自律的に実行

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"
BASE_DIR = "C:/Users/yu_ci/Desktop/codex-vs-local-agent-loop"
QUEUE_FILE = os.path.join(BASE_DIR, "output/LOCAL_TASK_QUEUE.json")

def get_ollama_response(prompt):
    try:
        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
        response = requests.post(OLLAMA_URL, json=payload, timeout=300) # 5分に延長
        return response.json().get("response", "")
    except Exception as e:
        print(f"Ollama Error: {e}")
        return ""

def process_tasks():
    if not os.path.exists(QUEUE_FILE):
        print("作業キューが見つかりません。")
        return

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    for task in queue:
        if task.get("progress", 0) >= 100:
            continue

        print(f"🤖 ローカルAIがタスクを処理中: {task['task']}")
        
        # タスクの種類に応じたプロンプト構築
        prompt = f"""
あなたは優秀な自律エージェントです。以下のタスクを遂行してください。
タスク名: {task['task']}
指示内容: {task['original']}

【出力形式】
1. 実行した内容の要約
2. 生成したファイル名（あれば）
3. 次のステップへの提案
"""
        response = get_ollama_response(prompt)
        
        # 簡易的な「実行」シミュレーション（実際には各モジュールを呼び出す）
        if "将棋" in task['task'] or "将棋" in task['original']:
            from SHOGI_NURTURING_MODULE import ShogiNurturingModule
            snm = ShogiNurturingModule()
            snm.generate_opening_study("中飛車")
        
        if "公務員" in task['task'] or "面接" in task['original']:
            from INTERVIEW_SIMULATOR import InterviewSimulator
            sim = InterviewSimulator()
            sim.generate_interview_questions("国家公務員（一般職）")

        # 進捗を更新
        task["progress"] = 100
        task["result"] = response
        
        # キューを保存（1つずつ更新）
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 処理完了: {task['task']}")

if __name__ == "__main__":
    print(f"🚀 ローカルAIタスク自動委譲モード起動 (Model: {MODEL_NAME})")
    process_tasks()
