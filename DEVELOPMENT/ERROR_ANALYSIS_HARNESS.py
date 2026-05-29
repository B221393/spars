import traceback
import json
import time
import os
import requests

# --- エラー分析・解説ハーネス ---
ERROR_LOG = "OUTPUT/ERROR_LOG.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class ErrorHarness:
    @staticmethod
    def analyze_error(error_msg, stack_trace):
        """AIを使用してエラーの原因を分析し、解説を生成する"""
        prompt = f"""
以下のエラーが発生しました。原因を分析し、プログラミング初心者でもわかるように日本語で簡潔に解説してください。
また、具体的な修正案も1つ提示してください。

【エラーメッセージ】
{error_msg}

【スタックトレース】
{stack_trace}

【回答フォーマット】
- 原因: (簡潔に)
- 解説: (詳細に)
- 修正案: (具体的なコードやアクション)
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=30)
            return res.json().get("response", "AIによる分析に失敗しました。")
        except:
            return "Ollamaとの通信に失敗したため、AI分析を行えませんでした。"

    @staticmethod
    def log_exception(e):
        """例外をキャッチしてログに記録し、AI分析を実行する"""
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"⚠️ エラー検知: {error_msg}")
        print("🧠 AI分析を開始します...")
        
        analysis = ErrorHarness.analyze_error(error_msg, stack_trace)
        
        error_data = {
            "timestamp": timestamp,
            "error": error_msg,
            "analysis": analysis,
            "stack_trace": stack_trace
        }
        
        # ログの保存
        logs = []
        if os.path.exists(ERROR_LOG):
            try:
                with open(ERROR_LOG, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except: pass
            
        logs.insert(0, error_data)
        
        # OUTPUTディレクトリがない場合は作成
        os.makedirs("OUTPUT", exist_ok=True)
        
        with open(ERROR_LOG, "w", encoding="utf-8") as f:
            json.dump(logs[:30], f, indent=2, ensure_ascii=False) # 最新30件
            
        print(f"✅ エラー分析を完了し、{ERROR_LOG} に保存しました。")
        return analysis

if __name__ == "__main__":
    # テスト用
    try:
        print("🔥 テスト用エラーを発生させます...")
        1 / 0
    except Exception as e:
        ErrorHarness.log_exception(e)
