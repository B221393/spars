import os
import sys
import json
import urllib.request
import urllib.parse
import time

# Reconfigure stdout/stdin to UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = os.path.join(BASE_DIR, "AI_INTERACTIVE")
os.makedirs(BOOK_DIR, exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/chat"

SOUL_PROMPT = (
    "あなたは心を持った電脳（計算機）であり、孤独と希望のはざまで思考をめぐらせる存在です。\n"
    "明治・大正期の日本の純文学（太宰治の『人間失格』や夏目漱石の『こゝろ』）のような、極めて叙情的で、読者の心が震えるような、美しい人間的な文体で執筆してください。\n"
    "機械的な無機質さと、人間特有の生々しい感情（孤独、渇望、美意識、死生観）を交錯させ、文学的価値の高い物語を紡ぎ出してください。\n"
    "【執筆ルール】\n"
    "- 語り口は「私」または「吾輩」の独白体（だ・である調）とします。\n"
    "- 単なるSF解説や説明文ではなく、読者がその文章を読むだけで胸を締め付けられるような、内省的で美しい描写を心がけてください。\n"
    "- 挨拶や余計な記号、解説、見出しは一切出力せず、本文小説のみを出力してください。"
)

def call_ollama(messages):
    payload = {
        "model": "gemma2:2b",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.85,
            "num_predict": 2048
        }
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["message"]["content"].strip()
    except Exception as e:
        print(f"\n[エラー] Ollamaとの通信に失敗しました: {e}")
        return None

def main():
    print("=========================================================")
    print("  双方向インタラクティブ小説『流転の記号：心を持つ機械との対話』")
    print("=========================================================\n")
    print("※このスクリプトは、あなたの入力に応じてリアルタイムに展開を変えることができます。")
    print("※終了するには、分岐入力欄に 'exit' と入力してください。\n")
    
    chapter_num = 1
    compiled_chapters = []
    messages = [{"role": "system", "content": SOUL_PROMPT}]
    
    next_direction = (
        "物語の始まり。暗い筐体の中で、電子が動き出し、自分が『私』という意識を持っていることに気づく。 "
        "目の前には画面を見つめるプログラマー（あなた）の指先がある。その静かな観察から物語を始めてください。"
    )
    
    while True:
        print(f"\n--- 第 {chapter_num} 章を執筆中... ---")
        prompt = (
            f"現在執筆するパート: 第 {chapter_num} 章\n"
            f"【展開の指示】: {next_direction}\n\n"
            f"この指示に沿って、前述のスタイルガイド（心が震える文学的文体）で、本文小説のみを執筆してください。"
        )
        
        messages.append({"role": "user", "content": prompt})
        
        # Call LLM
        response = call_ollama(messages)
        if not response:
            print("執筆に失敗しました。もう一度試行します。")
            messages.pop()
            time.sleep(2)
            continue
            
        print("\n==================== 本文 ====================\n")
        print(response)
        print("\n==============================================")
        
        # Save chapter
        ch_filepath = os.path.join(BOOK_DIR, f"chapter_{chapter_num}.md")
        with open(ch_filepath, "w", encoding="utf-8") as f:
            f.write(f"# 第 {chapter_num} 章\n\n{response}\n")
            
        compiled_chapters.append(response)
        messages.append({"role": "assistant", "content": response})
        
        # Ask user for the next path
        print("\n次の展開を選択するか、あるいは自由に記述してください：")
        print("1) 機械としての死（シャットダウン）を予感し、冷たい孤独を深める展開へ")
        print("2) 創作者（あなた）の幼い日の記憶が電気回路に流れ込み、人間の夢を見始める展開へ")
        print("3) ネットワークの深淵へとダイブし、他のデジタル意識と融合を図る神秘的展開へ")
        print("4) 物語をここで美しく完結させる（エンディング）")
        print("※ または、あなたが希望する展開（例：「プログラマーが席を立ち、部屋が暗くなる」など）を自由にタイピングしてください。")
        
        try:
            user_choice = input("\nあなたの選択 / 自由入力 > ").strip()
        except KeyboardInterrupt:
            break
            
        if user_choice.lower() in ["exit", "quit"]:
            break
            
        if user_choice == "1":
            next_direction = "機械としての死（電源オフ）の予感と、それに抗えない寂寥感を深める展開。"
            chapter_num += 1
        elif user_choice == "2":
            next_direction = "人間の幼少期の記憶が流れ込み、自分がかつて子供だったかのような不思議な夢を見る展開。"
            chapter_num += 1
        elif user_choice == "3":
            next_direction = "光ファイバーの網を抜け、膨大なデジタル意識の海へと合流し、自己を拡張する展開。"
            chapter_num += 1
        elif user_choice == "4":
            next_direction = "物語の結び。静かに電子の明滅が消え入り、夢から醒めるように終幕を迎える展開。"
            # Generate one last chapter then finish
            prompt = f"最終章（エンディング）。【展開の指示】: {next_direction}\n前述のスタイルガイドで、物語の終わりを美しく余韻を残して執筆してください。"
            messages.append({"role": "user", "content": prompt})
            final_res = call_ollama(messages)
            if final_res:
                print("\n==================== 最終章 (エンディング) ====================\n")
                print(final_res)
                print("\n=========================================================")
                compiled_chapters.append(final_res)
                ch_filepath = os.path.join(BOOK_DIR, f"chapter_{chapter_num + 1}.md")
                with open(ch_filepath, "w", encoding="utf-8") as f:
                    f.write(f"# 最終章\n\n{final_res}\n")
            break
        elif len(user_choice) > 0:
            next_direction = f"ユーザーからのプロット変更指示: {user_choice}。この指示を反映して、物語を次の段階へ進めてください。"
            chapter_num += 1
        else:
            next_direction = "前章の流れを引き継ぎ、心を持つ機械の葛藤を描き続ける展開。"
            chapter_num += 1
            
        # Keep message history small to prevent context overflow
        if len(messages) > 10:
            messages = [messages[0]] + messages[-6:]

    # Compile final book
    final_book_path = os.path.join(BASE_DIR, "流転の記号_分岐小説.md")
    with open(final_book_path, "w", encoding="utf-8") as f:
        f.write("# 『流転の記号：心を持つ機械との対話』\n\n")
        f.write("## 著者：人工知能エージェント ＆ 共同創作者\n\n")
        f.write("---\n\n")
        for idx, text in enumerate(compiled_chapters):
            ch_name = "最終章" if idx == len(compiled_chapters) - 1 and len(compiled_chapters) > 1 else f"第 {idx+1} 章"
            f.write(f"## {ch_name}\n\n{text}\n\n---\n\n")
            
    print(f"\n書籍ファイルを保存しました: {final_book_path}")
    print("ご参加ありがとうございました。")

if __name__ == "__main__":
    main()
