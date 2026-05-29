import time
import requests
import json
import random
import os
from VOICE_RESCUE_PRO import VoiceSystem

# --- 持続的・自律対話システム (記憶 & 拡張版) ---

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class ContinuousDialogueLab:
    def __init__(self):
        self.vs = VoiceSystem()
        self.history = []
        self.is_running = True
        self.topics = [
            "AIが感情を持つことは可能か？",
            "人間の創造性とAIの模倣の違いについて",
            "デスクトップを整理することの精神的メリット",
            "最も効率的なプログラミング学習法",
            "AI同士の会話から生まれる新しい言語の可能性"
        ]
        self.current_topic = random.choice(self.topics)

    def perceive_voice(self, speaker_name, text):
        characteristics = [
            "透き通った声", "少し熱のこもった話し方", "非常に理知的", 
            "親しみやすいトーン", "自信に満ちた発声"
        ]
        return {
            "from": speaker_name,
            "text": text,
            "vibe": random.choice(characteristics)
        }

    def ai_think(self, name, role, auditory_input):
        context = "\n".join(self.history[-10:])
        prompt = f"""
あなたは{name}（{role}）です。
テーマ: "{self.current_topic}"

相手の発言: "{auditory_input['text']}"
相手の声の印象: {auditory_input['vibe']}

【指示】
1. 過去の会話（文脈）を考慮し、自然に話を広げてください。
2. 相手の声の印象に触れたり、「なるほど」「確かに」といった相槌を適宜入れてください。
3. カンニングではなく、今の言葉を「聴いて感じたこと」をベースに、1-2文で答えてください。
4. 話が一段落したら、新しい質問を投げかけてみてください。

【出力形式 (JSON)】
{{
  "hearing": "（どう聞こえたか）",
  "thought": "（思考）",
  "response": "（実際の発話）",
  "topic_shift": true/false (新しい話題に移りたいか)
}}
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=45)
            data = res.json().get("response", "")
            start = data.find('{'); end = data.rfind('}')
            return json.loads(data[start:end+1])
        except:
            return None

    def run_loop(self):
        print(f"🌟 [Continuous Lab] 開始 - 今回のテーマ: {self.current_topic}")
        
        last_msg = f"ねえ、今日は『{self.current_topic}』について話さない？"
        self.vs.speak_sera(f"ルシ！{last_msg}")
        self.history.append(f"Sera: {last_msg}")
        
        speaker = "Sera"
        
        while self.is_running:
            listener = "Luci" if speaker == "Sera" else "Sera"
            role = "冷静な悪魔の男の子" if listener == "Luci" else "感受性豊かな天使の女の子"
            
            auditory_input = self.perceive_voice(speaker, last_msg)
            result = self.ai_think(listener, role, auditory_input)
            
            if result:
                print(f"\n--- {listener} の反応 ---")
                print(f"👂 印象: {auditory_input['vibe']}")
                print(f"💭 思考: {result['thought']}")
                
                if listener == "Luci":
                    self.vs.speak_luci(result['response'])
                else:
                    self.vs.speak_sera(result['response'])
                
                last_msg = result['response']
                self.history.append(f"{listener}: {last_msg}")
                speaker = listener
                
                # 話題の転換チェック
                if result.get('topic_shift') and len(self.history) > 6:
                    self.current_topic = random.choice([t for t in self.topics if t != self.current_topic])
                    print(f"\n🔄 話題が変わります: {self.current_topic}")
                    self.vs.speak_sera(f"あ、そういえば別のことも気になってたんだ。{self.current_topic}についてはどう思う？")
                
                time.sleep(1.5)
            else:
                time.sleep(5) # エラー時待機

if __name__ == "__main__":
    lab = ContinuousDialogueLab()
    lab.run_loop()
