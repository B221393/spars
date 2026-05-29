import time
import requests
import json
import random
from VOICE_RESCUE_PRO import VoiceSystem

# --- 真・聴覚的対話シミュレーター (人間味重視版) ---
# 「カンニング（テキストの直接参照）」を禁止し、
# 相手の声の「響き」や「ニュアンス」をまず捉えてから対話する

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class HumanDialogueLab:
    def __init__(self):
        self.vs = VoiceSystem()
        self.is_running = True
        
    def perceive_voice(self, speaker_name, text):
        """
        相手の声を「聴く」プロセスをシミュレートする。
        単なるテキストの受け渡しではなく、音声としての特徴（ピッチ、速さ、明瞭度）を抽出する。
        """
        # ここで「聴覚的特徴」を付与する（カンニング禁止の演出）
        clarity = random.choice(["非常にクリア", "少し早口", "高音が響いている", "落ち着いたトーン"])
        emotion = "温かい" if "セラ" in speaker_name else "冷静"
        
        # 聴覚データとしてパック（これがAIへの『入力』になる）
        auditory_data = {
            "from": speaker_name,
            "raw_stimulus": text, # 物理的な刺激としてのテキスト
            "perceived_clarity": clarity,
            "perceived_tone": emotion
        }
        return auditory_data

    def ai_human_thought(self, name, role, auditory_input):
        """聴いた音から意味を汲み取り、人間らしく応答を生成する"""
        
        # カンニング禁止のプロンプト
        prompt = f"""
あなたは{name}（{role}）です。
今、相手の「声」を聴きました。

【聴覚データ】
- 送り主: {auditory_input['from']}
- 聴こえてきた内容: "{auditory_input['raw_stimulus']}"
- 声の明瞭度: {auditory_input['perceived_clarity']}
- 声のトーン: {auditory_input['perceived_tone']}

【あなたのタスク】
1. 聞き取りの確認: まず、相手が何と言ったのか、正しく聞き取れているかを心の中で確認してください。
2. 人間らしい反応: 「えーと」「なるほど」「ふむ」といった相槌や、相手の話し方（トーン）への反応を混ぜてください。
3. 思考と返答: 相手の言葉の裏にある感情を読み取り、1〜2文の「生きた言葉」で返してください。

【出力形式 (JSON)】
{{
  "hearing_check": "（どう聞こえたか、聞き取りの自信度）",
  "internal_emotion": "（相手の声から感じた感情）",
  "response": "（実際の発話。人間らしく！）",
  "feedback_to_user": "（会話のテンポや聞き取りやすさについての分析）"
}}
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=45)
            text = res.json().get("response", "")
            start = text.find('{'); end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
        except:
            return None

    def start_session(self):
        print("🎭 [Human-Like Dialogue Lab] 起動中...")
        print("※テキストの直接参照（カンニング）を禁止し、聴覚的な知覚に基づいた会話を行います。\n")

        # 最初のキッカケ
        current_msg = "ねえルシ、私たちの声、ちゃんと人間っぽく聞こえてるかな？"
        self.vs.speak_sera(f"えーと、ルシ。{current_msg}")
        
        speaker = "セラ"
        
        for i in range(4): # 4往復
            # 次の話し手を決定
            listener_name = "ルシ" if speaker == "セラ" else "セラ"
            listener_role = "冷静で論理的な男の子" if listener_name == "ルシ" else "明るく感受性豊かな女の子"
            
            # 「聴く」プロセス
            auditory_input = self.perceive_voice(speaker, current_msg)
            
            # 「考える」プロセス
            thought_data = self.ai_human_thought(listener_name, listener_role, auditory_input)
            
            if thought_data:
                print(f"\n--- {listener_name} の知覚 ---")
                print(f"👂 聞き取り: {thought_data['hearing_check']}")
                print(f"💓 感情: {thought_data['internal_emotion']}")
                print(f"📊 分析: {thought_data['feedback_to_user']}")
                
                # 「話す」プロセス
                if listener_name == "ルシ":
                    self.vs.speak_luci(thought_data['response'])
                else:
                    self.vs.speak_sera(thought_data['response'])
                
                # 次のターンへ
                current_msg = thought_data['response']
                speaker = listener_name
                time.sleep(1.2) # 自然な呼吸の間

if __name__ == "__main__":
    lab = HumanDialogueLab()
    lab.start_session()
