import requests
import json
import os
import sys
import subprocess

# Windows環境での文字コードエラーを防ぐための設定
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# --- 将棋定跡・自律弱点分析システム (V3) ---
# 1. ローカルLLM (Ollama) による戦術解説
# 2. 将棋エンジン (Suisho 5) による数値評価 (CP値) の統合

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"
ENGINE_PATH = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\SHOGI\engines\Suisho5\YaneuraOu_NNUE-tournament-clang++-avx2.exe"

class JosekiAnalyzer:
    def __init__(self):
        self.base_dir = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\SHOGI"

    def get_engine_evaluation(self, sfen):
        """将棋エンジンを使用して、特定の局面（SFEN）を評価します。"""
        if not os.path.exists(ENGINE_PATH):
            return "Engine not found."

        try:
            # 簡略化のため、1秒思考して評価値を取得する
            process = subprocess.Popen(
                ENGINE_PATH,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            process.stdin.write("usi\n")
            process.stdin.write(f"position sfen {sfen}\n")
            process.stdin.write("go movetime 1000\n")
            process.stdin.flush()

            eval_val = "0"
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                if "cp" in line:
                    parts = line.split()
                    eval_val = parts[parts.index("cp") + 1]
                if "bestmove" in line:
                    break
            
            process.stdin.write("quit\n")
            process.terminate()
            return eval_val
        except Exception as e:
            return f"Error: {e}"

    def analyze_joseki(self, joseki_name, sfen=None):
        print(f"🔍 戦法『{joseki_name}』を多角的に分析中...")
        
        # 1. AI解説の取得
        prompt = f"""
あなたは将棋AI解析官です。戦法『{joseki_name}』の弱点と対策を、2026年のAIトレンドを踏まえて詳しく解説してください。
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=300)
            ai_report = res.json().get("response", "分析失敗")
        except:
            ai_report = "Ollama Offline."

        # 2. エンジン評価の取得
        engine_eval = "N/A"
        if sfen:
            engine_eval = self.get_engine_evaluation(sfen)

        # 3. レポートの統合保存
        output_file = os.path.join(self.base_dir, f"{joseki_name}_DeepAnalysis_V3.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# 📊 将棋解析レポート: {joseki_name}\n\n")
            f.write(f"## ⚙️ エンジン数値評価 (Suisho 5)\n")
            f.write(f"- **評価値 (cp):** {engine_eval}\n")
            f.write(f"- **局面 (SFEN):** `{sfen if sfen else '初期局面'}`\n\n")
            f.write(f"## 🤖 AI戦術解説 (Ollama)\n")
            f.write(ai_report)
        
        print(f"✅ 解析完了: {output_file}")

if __name__ == "__main__":
    analyzer = JosekiAnalyzer()
    # 三間飛車の代表的な局面 (sfen)
    analyzer.analyze_joseki("三間飛車", "lnsgkg1nl/1r5s1/pppppp1pp/9/9/2P6/PP1PPPPPP/1S5R1/LNSGKGSNL b - 1")
    # 四間飛車の代表的な局面
    analyzer.analyze_joseki("四間飛車", "lnsgkg1nl/1r5s1/pppppp1pp/9/9/5P3/PPPPP1PPP/1S5R1/LNSGKGSNL b - 1")
    # 穴熊 (振飛車穴熊)
    analyzer.analyze_joseki("振飛車穴熊", "lnsgkg1nl/1r5s1/pppppp1pp/9/9/2P6/PP1PPPPPP/1S5R1/LNSGKGSNL b - 1") # SFEN is same for starting, but topic is different
    # 矢倉
    analyzer.analyze_joseki("矢倉", "lnsgkg1nl/1r5s1/pppppp1pp/9/9/8P/PPPPPPP1P/1S5R1/LNSGKGSNL b - 1")
