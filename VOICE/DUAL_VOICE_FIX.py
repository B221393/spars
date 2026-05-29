import time
import os
import requests
import json
import win32com.client

# --- 男女ボイス・高低差調整システム ---

class DualVoiceSystem:
    def __init__(self):
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.voices = self.speaker.GetVoices()
        self.female_voice = None
        self.male_voice = None
        
        # ボイスの割り当て
        for i in range(self.voices.Count):
            name = self.voices.Item(i).GetDescription()
            if "Haruka" in name or "Ayumi" in name or "Sayaka" in name:
                self.female_voice = self.voices.Item(i)
            if "Ichiro" in name or "David" in name:
                self.male_voice = self.voices.Item(i)
        
        # デフォルト設定
        if not self.female_voice: self.female_voice = self.voices.Item(0)
        if not self.male_voice: self.male_voice = self.voices.Item(0)

    def speak_female(self, text):
        """女の子の声（高め・速め）"""
        print(f"👧 [高音ボイス] セラ: {text}")
        self.speaker.Voice = self.female_voice
        # Rateを上げるとピッチが上がったように聞こえます
        self.speaker.Rate = 2 
        self.speaker.Speak(text)

    def speak_male(self, text):
        """男の子の声（低め・落ち着いた）"""
        print(f"👦 [低音ボイス] ルシ: {text}")
        self.speaker.Voice = self.male_voice
        self.speaker.Rate = 0
        self.speaker.Speak(text)

def get_ai_response(name, role, context):
    OLLAMA_URL = "http://localhost:11434/api/generate"
    prompt = f"あなたは{name}という名前の{role}です。短く1文で答えてください。\n文脈: {context}"
    try:
        res = requests.post(OLLAMA_URL, json={"model": "gemma3:4b", "prompt": prompt, "stream": False}, timeout=30)
        return res.json().get("response", "...")
    except:
        return "通信エラーかな？"

if __name__ == "__main__":
    vs = DualVoiceSystem()
    print("🎤 音声設定を修正しました（男×女・高低差あり）")
    
    context = "ユーザーが音声設定を『男と女』『女の子はもっと高い声』に変更しました。挨拶してください。"
    
    # 女の子（セラ）
    res_f = get_ai_response("セラ", "明るい女の子のAI", context)
    vs.speak_female(res_f)
    
    # 男の子（ルシ）
    res_m = get_ai_response("ルシ", "落ち着いた男性のAI", context)
    vs.speak_male(res_m)
