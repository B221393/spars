import requests
import json
import subprocess
import os
import time

# --- 設定 ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b" 
QUEUE_FILE = "TASK_QUEUE.txt"
LOG_FILE = "EVOLUTION_HISTORY.log"

def log_event(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")

def ask_ai_for_judgment(task_description):
    prompt = f"""
あなたは自律進化システムのマネージャーです。
以下のタスクを実行すべきか判断し、安全で明確な場合のみ実行コマンドを生成してください。

【タスク】
{task_description}

【判断基準】
1. 安全性：システム破壊、重要ファイル削除、無限ループなどはNG。
2. 明確性：何をすべきか具体的に示されていること。

【回答形式 (JSONのみ)】
{{
  "should_execute": true/false,
  "reason": "判断理由",
  "command": "実行するPowerShellコマンド"
}}
"""
    try:
        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        res_text = response.json().get("response", "")
        start = res_text.find('{')
        end = res_text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(res_text[start:end+1])
    except Exception as e:
        return {"should_execute": False, "reason": f"AI通信エラー: {e}"}
    return {"should_execute": False, "reason": "解析不能な回答"}

def run_continuous_loop():
    log_event("🚀 自律進化バックグラウンドループを開始しました。")
    
    while True:
        if not os.path.exists(QUEUE_FILE):
            time.sleep(10)
            continue
            
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if not lines:
            time.sleep(10)
            continue
            
        # 最初の有効なタスクを取り出す
        task = ""
        remaining_lines = []
        for line in lines:
            if not task and line.strip() and not line.startswith("#"):
                task = line.strip()
            else:
                remaining_lines.append(line)
        
        if not task:
            time.sleep(10)
            continue
            
        # キューを更新（実行するタスクを削除）
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            f.writelines(remaining_lines)
            
        log_event(f"🧐 タスクを処理中: {task}")
        decision = ask_ai_for_judgment(task)
        
        if decision.get("should_execute"):
            log_event(f"✅ 実行許可: {decision['reason']}")
            cmd = decision.get("command")
            if cmd:
                log_event(f"💻 実行: {cmd}")
                # コマンド実行 (PowerShell)
                subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], shell=True)
        else:
            log_event(f"❌ 実行拒否: {decision['reason']}")
            
        log_event("待機中 (30秒)... 次のタスクを確認します。")
        time.sleep(30)

if __name__ == "__main__":
    run_continuous_loop()
