import os
import json
import requests

# --- 将棋AI育成 & 学習資料生成スクリプト ---
BASE_DIR = "C:/Users/yu_ci/Desktop/codex-vs-local-agent-loop"
SHOGI_DIR = os.path.join(BASE_DIR, "shogi-ai-nurturing")
ENGINE_DIR = os.path.join(SHOGI_DIR, "engine")
STUDY_DIR = os.path.join(SHOGI_DIR, "study_materials")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class ShogiNurturingModule:
    def __init__(self):
        os.makedirs(STUDY_DIR, exist_ok=True)

    def generate_opening_study(self, opening_name="相掛かり (Ai-gakari)"):
        """将棋の定石（戦法）に関する詳細な学習資料をAIで生成する"""
        print(f"📖 将棋戦法『{opening_name}』の学習資料を生成中...")
        
        prompt = f"""
あなたは将棋の師範代AIです。戦法『{opening_name}』について、以下の構成で初心者〜中級者向けの解説資料を作成してください。

1. 戦法の概要と特徴
2. 基本的な駒組みの手順
3. 狙い筋と注意点
4. プロの対局での出現傾向

回答はMarkdown形式で、具体的かつ丁寧に日本語で書いてください。
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=90)
            content = res.json().get("response", "生成失敗")
            
            filename = f"{opening_name.replace(' ', '_')}_study.md"
            filepath = os.path.join(STUDY_DIR, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            print(f"✅ 資料を保存しました: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ 生成エラー: {e}")
            return None

    def check_engine_status(self):
        """将棋エンジンの存在と設定を確認する"""
        print("🔍 将棋エンジンの稼働状況をチェック中...")
        # 実行ファイル群を確認
        engines = [f for f in os.listdir(ENGINE_DIR) if f.endswith(".exe")]
        status = {
            "engine_count": len(engines),
            "available_engines": engines,
            "has_suisho": any("Suisho" in f or "Yaneura" in f for f in engines)
        }
        return status

if __name__ == "__main__":
    module = ShogiNurturingModule()
    # エンジンチェック
    status = module.check_engine_status()
    print(f"📊 エンジン状況: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    # 学習資料生成（第一弾：相掛かり）
    module.generate_opening_study("相掛かり")
    module.generate_opening_study("三間飛車")
