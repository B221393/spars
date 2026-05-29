import os
import json
import subprocess
import time

# --- 音声完全停止スイッチ (Kill-Switch) ---
CONFIG_FILE = "C:/Users/yu_ci/Desktop/codex-vs-local-agent-loop/INPUT/SYSTEM_CONFIG.json"

def kill_voice():
    print("🛑 音声システムを完全停止します...")
    
    # 1. 設定ファイルを強制的に音声OFFに書き換える
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        config["modules"]["voice_output"]["enabled"] = False
        config["modules"]["voice_input"]["enabled"] = False
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ 設定ファイルを無効化（OFF）にしました。")

    # 2. 音声関連の可能性のあるプロセスを強制終了
    voice_keywords = ["CONFERENCE", "DUPLEX", "DIALOGUE", "SHELL", "HARDWARE_FEEDBACK", "SERVICE", "VOICE"]
    
    # PowerShellを使用してプロセスをクリーンアップ
    for kw in voice_keywords:
        cmd = f"Get-Process python | Where-Object {{ $_.CommandLine -like '*{kw}*' }} | Stop-Process -Force"
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)
    
    print("✅ 関連プロセスをすべて終了しました。")
    print("🔇 システムは完全にサイレントな状態です。")

if __name__ == "__main__":
    kill_voice()
