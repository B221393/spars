import time
import requests
import json
import os
from VOICE_RESCUE_PRO import VoiceSystem

# --- 音声システム専用・自己フィードバックループ ---
# セラとルシが自分たちの声の掛け合いを自分たちで評価する

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class VoiceFeedbackLoop:
    def __init__(self):
        self.vs = VoiceSystem()
        self.history = []

    def run_feedback_cycle(self):
        print("🎙️ [Voice Feedback Loop] 開始...")
        
        # 1. まずは通常の会話を一往復させる（テストデータ生成）
        print("🤖 ステップ1: テスト会話の実行")
        test_msg_sera = "ルシ、今の私たちの声のバランス、どうかな？ちゃんと聞き取りやすいかな？"
        self.vs.speak_sera(test_msg_sera)
        self.history.append(f"Sera: {test_msg_sera}")
        
        time.sleep(0.5)
        
        test_msg_luci = "フン、悪くないが、もう少しテンポを上げてもいいかもしれんな。"
        self.vs.speak_luci(test_msg_luci)
        self.history.append(f"Luci: {test_msg_luci}")

        # 2. AI自身に今の「やり取り」を客観的に評価させる
        print("🧠 ステップ2: AIによる自己分析中...")
        prompt = f"""
あなたは音声インタラクションの専門家です。以下のAI二人の会話（セラとルシ）を分析し、
「音声入出力のテスト」として成功しているか、改善点はどこかを評価してください。

【会話ログ】
{json.dumps(self.history, indent=2, ensure_ascii=False)}

【分析のポイント】
- 男（ルシ）と女（セラ）の声の対比は明確か？
- 会話のテンポ（間隔）は自然か？
- フィードバックループとして、自己改善の兆しが見えるか？

【出力形式 (JSON)】
{{
  "sera_feedback": "（セラからの前向きな改善案）",
  "luci_feedback": "（ルシからの厳格な改善案）",
  "technical_score": 0-100
}}
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=60)
            text = res.json().get("response", "")
            start = text.find('{'); end = text.rfind('}')
            result = json.loads(text[start:end+1])
            
            print(f"\n📊 音声システム評価スコア: {result.get('technical_score')}点")
            
            # 3. 分析結果を自分たちの声でフィードバックする
            self.vs.speak_sera(f"自分たちで振り返ってみたよ！{result.get('sera_feedback')}")
            time.sleep(0.5)
            self.vs.speak_luci(f"俺たちの今の限界はここだな。{result.get('luci_feedback')}")
            
            # 4. 改善タスクを登録（実際にループを回す）
            print("🚀 フィードバックを次回の動作に反映します。")
            with open("INPUT/USER_TASKS.txt", "a", encoding="utf-8") as f:
                f.write(f"\n[VOICE-IMPROVEMENT] スコア {result.get('technical_score')}点に基づく自動調整案の適用")

        except Exception as e:
            print(f"❌ フィードバックループ実行中にエラー: {e}")

if __name__ == "__main__":
    loop = VoiceFeedbackLoop()
    loop.run_feedback_cycle()
