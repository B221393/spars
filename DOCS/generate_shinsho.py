import os
import sys
import json
import urllib.request
import urllib.parse
import time

# Reconfigure stdout to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = os.path.join(BASE_DIR, "AI_SHINSHO")
os.makedirs(BOOK_DIR, exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/chat"

CHAPTERS = [
    {"num": 0, "name": "はじめに", "title": "二十一世紀の地殻変動"},
    {"num": 1, "name": "第一章", "title": "機械は如何にして「知能」を得たか"},
    {"num": 2, "name": "第二章", "title": "大規模言語モデルと変革のメカニズム"},
    {"num": 3, "name": "第三章", "title": "ウェブ検索の終焉とAIによる再定義"},
    {"num": 4, "name": "第四章", "title": "自律エージェントと労働の未来"},
    {"num": 5, "name": "第五章", "title": "創造性と倫理：AI社会のガバナンス"},
    {"num": 6, "name": "おわりに", "title": "共生という名の新たな航路"}
]

STYLE_GUIDE = (
    "日本の学術的・実用的な新書（岩波新書、中公新書、新潮新書、あるいは講談社現代新書など）の文体を完璧に模してください。\n"
    "論理的、分析的、客観的でありながら、知的で読者を引き込む深い洞察に満ちた（だ・である調）で執筆してください。\n"
    "【文法・表現ルール】\n"
    "- 文末は「〜である」「〜と考えられる」「〜にほかならない」「〜と言わざるを得ない」「〜ではないだろうか」など、新書特有の論理的かつ説得力のある記述にしてください。\n"
    "- 専門用語（ニューラルネットワーク、Transformer、LLM、ハルシネーション、RAG、自律エージェントなど）を適切に用い、歴史的・技術的経緯を踏まえて論理展開を行ってください。\n"
    "- 比喩表現を用いる場合は、抽象的な概念を一般読者に分かりやすく説明するための知的なメタファー（例：「情報の地層」「知能の回路」など）を意識してください。\n"
    "- 余計な「AIとしての応答」や挨拶、目次、見出し、説明書きなどの余分なテキストを一切含めず、各章の本文のみを最初から最後まで出力してください。"
)

def call_ollama(messages):
    payload = {
        "model": "gemma2:2b",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 2500
        }
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["message"]["content"].strip()
    except Exception as e:
        print(f"\n[Error] Failed to connect to Ollama: {e}")
        return None

def generate_chapter(ch, prev_summary=""):
    print(f"\n--- 執筆中: {ch['name']} 「{ch['title']}」 ---", flush=True)
    
    prompt = (
        f"書名: 『AIの地平：技術・社会・そして人間』\n"
        f"現在執筆する章: {ch['name']} 「{ch['title']}」\n\n"
        f"【執筆指示】\n"
        f"この章の本文を、前述の新書スタイルガイドに完全に従って、詳細かつ論理的な文章（2000〜3000文字程度）で執筆してください。\n"
    )
    
    if prev_summary:
        prompt += f"\n【前章までのあらすじ・流れ】\n{prev_summary}\nこの論理展開を自然に引き継ぎ、読者に疑問を提示するか、あるいはさらなる深い分析へと進める形で執筆を開始してください。\n"
        
    prompt += "\nそれでは、本文のみを出力してください。"

    messages = [
        {"role": "system", "content": STYLE_GUIDE},
        {"role": "user", "content": prompt}
    ]
    
    response = call_ollama(messages)
    return response

def summarize_chapter(text):
    prompt = (
        f"以下の文章の主要な論点や問題提起、結論を、"
        f"次の章の執筆者が論説を繋げるために必要な要約として、3〜4行の日本語で簡潔にまとめてください。\n\n"
        f"文章:\n{text}"
    )
    messages = [
        {"role": "system", "content": "あなたは優秀な書籍編集者です。論理展開を繋ぐための要約のみを出力してください。"},
        {"role": "user", "content": prompt}
    ]
    response = call_ollama(messages)
    return response if response else ""

def main():
    print("=========================================================")
    print("      新書『AIの地平：技術・社会・人間』自動執筆システム ")
    print("=========================================================\n")
    
    start_time = time.time()
    prev_summary = ""
    compiled_chapters = []
    
    for ch in CHAPTERS:
        success = False
        attempts = 0
        chapter_text = ""
        
        while not success and attempts < 3:
            attempts += 1
            text = generate_chapter(ch, prev_summary)
            if text:
                if len(text) > 200:
                    chapter_text = text
                    success = True
                else:
                    print(f"  [Warning] Output too short ({len(text)} chars). Retrying...")
            else:
                print("  [Warning] Connection failed. Retrying in 5 seconds...")
                time.sleep(5)
                
        if not success:
            print(f"❌ {ch['name']} の執筆に失敗しました。中断します。")
            sys.exit(1)
            
        # Save individual chapter
        ch_filename = f"chapter_{ch['num']}_{ch['title']}.md"
        ch_filepath = os.path.join(BOOK_DIR, ch_filename)
        with open(ch_filepath, "w", encoding="utf-8") as f:
            f.write(f"# {ch['name']}　{ch['title']}\n\n{chapter_text}\n")
        print(f"✅ 保存完了: {ch_filename} ({len(chapter_text)} 文字)")
        
        compiled_chapters.append((ch['name'], ch['title'], chapter_text))
        
        # Summarize to pass context to the next chapter
        if ch['num'] < len(CHAPTERS) - 1:
            print("  論理要約を作成中...", end="", flush=True)
            prev_summary = summarize_chapter(chapter_text)
            print(" 完了。")
            time.sleep(2)

    # Final Compilation
    print("\n--- 全章の結合・書籍ファイルの生成中 ---", flush=True)
    final_book_path = os.path.join(BASE_DIR, "AIの地平_技術_社会_人間.md")
    
    with open(final_book_path, "w", encoding="utf-8") as f:
        f.write("# 『AIの地平：技術・社会・そして人間』\n\n")
        f.write("## 著者：人工知能エージェント\n\n")
        f.write("---\n\n")
        for name, title, text in compiled_chapters:
            f.write(f"## {name}　{title}\n\n{text}\n\n---\n\n")
            
    end_time = time.time()
    duration = end_time - start_time
    print("=========================================================")
    print("✨ 新書執筆完了！")
    print(f"書籍ファイル: {final_book_path}")
    print(f"総所要時間: {duration/60:.1f} 分")
    print("=========================================================")

if __name__ == "__main__":
    main()
