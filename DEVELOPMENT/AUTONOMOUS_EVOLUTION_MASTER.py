import subprocess
import time
import os
import datetime
import sys

# Windows環境での文字コードエラーを防ぐための設定
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# --- 全自動・自律進化マスター・オーケストレーター (V3) ---
# 1. フィードバックループの高速化 (60s)
# 2. 将棋「戦術聖書」と研究「軌跡精緻化」の統合

GENRE_DIR = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS"
INTERVAL = 60 
HARNESS_FILE = os.path.join(GENRE_DIR, "DOCS", "CLARITY_HARNESS.md")

def run_task(name, command):
    print(f"\n🚀 【{name}】タスクを開始します...")
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except Exception as e:
        print(f"❌ 【{name}】エラー: {e}")
        return False

def update_harness(iteration, summary):
    os.makedirs(os.path.dirname(HARNESS_FILE), exist_ok=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"| **Iter {iteration}** | {now} | {summary} | 評価中... |\n"
    if not os.path.exists(HARNESS_FILE):
        with open(HARNESS_FILE, "w", encoding="utf-8") as f:
            f.write("# 📈 Clarity & Evolution Harness\n\n| Iteration | Timestamp | Summary | Evaluation |\n|---|---|---|---|\n")
    with open(HARNESS_FILE, "a", encoding="utf-8") as f:
        f.write(new_entry)

def main_loop():
    iteration = 1
    while True:
        print(f"\n===== 🔄 自律進化サイクル Iteration {iteration} =====")
        
        # 1. 研究解析 & 物理フィルタリング
        run_task("RESEARCH_TRACK", rf"python {GENRE_DIR}\RESEARCH\PRO_TRAJECTORY_TRACKER.py")
        run_task("RESEARCH_REFINE", rf"python {GENRE_DIR}\RESEARCH\TRAJECTORY_REFINER.py")
        run_task("RESEARCH_UNCERTAINTY", rf"python {GENRE_DIR}\RESEARCH\UNCERTAINTY_ANALYZER.py")
        
        # 2. 将棋戦術の深層分析 (V3)
        run_task("SHOGI_ANALYSIS", rf"python {GENRE_DIR}\SHOGI\JOSEKI_ANALYZER.py")
        
        # 3. 成果を音声で報告 (Sageモード)
        run_task("VOICE_REPORT", rf"python {GENRE_DIR}\DEVELOPMENT\RESEARCH_VOICE_INTEGRATOR.py --once")

        # 4. クラリティ・ハーネスの更新
        update_harness(iteration, "研究(V4)/将棋(V3)/統合進化")

        # 5. GitHub同期 (自動バックアップ & 共有)
        # studyフォルダにあるPowershellスクリプトを呼び出す
        sync_script = r"C:\Users\yu_ci\study\auto_github_sync.ps1"
        commit_msg = f"Autonomous Evolution Iteration {iteration}: System sync."
        run_task("GITHUB_SYNC", f"powershell.exe -ExecutionPolicy Bypass -File {sync_script} '{commit_msg}'")

        print(f"\n💤 {iteration}回目のサイクル完了。{INTERVAL}秒間待機します...")
        iteration += 1
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main_loop()
