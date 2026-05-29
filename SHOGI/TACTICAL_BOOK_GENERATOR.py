import requests
import os
import datetime

# --- Shogi: Tactical Book Generator (V3) ---
# Aggregates AI analysis into a single structured book.

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"
BOOK_PATH = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\SHOGI\TACTICAL_BOOK_2026.md"

def generate_tactical_entry(strategy):
    prompt = f"将棋の戦法『{strategy}』について、2026年のAI研究に基づいた最新の定跡、急所、および対抗策をプロ級の視点で3段落で解説してください。"
    try:
        res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=180)
        return res.json().get("response", "分析失敗")
    except:
        return "Ollama通信エラー"

def update_book():
    strategies = ["エルモ囲い急戦", "藤井システム", "相穴熊の金銀活用"]
    print(f"📖 Updating Tactical Book: {BOOK_PATH}")
    
    with open(BOOK_PATH, "w", encoding="utf-8") as f:
        f.write(f"# ☗ 2026年 将棋定跡・戦術聖書 (Tactical Book)\n")
        f.write(f"最終更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        for s in strategies:
            print(f"  > Analyzing {s}...")
            analysis = generate_tactical_entry(s)
            f.write(f"## 【{s}】\n{analysis}\n\n---\n")
            
    print(f"✅ Tactical Book updated successfully.")

if __name__ == "__main__":
    update_book()
