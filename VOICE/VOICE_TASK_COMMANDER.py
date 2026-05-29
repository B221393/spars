import speech_recognition as sr
import pyttsx3
import requests
import time
import subprocess
import os

# --- 🎙️ 進化版：タスク実行型・音声OS (Voice OS V2) ---
# 声で「研究を開始して」「将棋を分析して」と命じると、実際のスクリプトが動きます。

class VoiceTaskOS:
    def __init__(self, model="gemma4:latest"):
        self.model = model
        self.ollama_url = "http://localhost:11434/api/generate"
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        
        # 声の設定
        voices = self.engine.getProperty('voices')
        for v in voices:
            if "JP" in v.name: self.engine.setProperty('voice', v.id)
        self.engine.setProperty('rate', 180)

        # パス設定
        self.genre_dir = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS"

    def speak(self, text):
        print(f"🤖 AI: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        with sr.Microphone() as source:
            print("\n👂 指令待機中...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                text = self.recognizer.recognize_google(audio, language="ja-JP")
                print(f"👤 User: {text}")
                return text
            except: return None

    def execute_command(self, text):
        # 1. 実行系コマンド
        if "研究" in text or "解析" in text or "トラッキング" in text:
            self.speak("了解しました。研究データのトラッキングと精緻化を開始します。")
            subprocess.run(rf"python {self.genre_dir}\RESEARCH\PRO_TRAJECTORY_TRACKER.py", shell=True)
            subprocess.run(rf"python {self.genre_dir}\RESEARCH\TRAJECTORY_REFINER.py", shell=True)
            self.speak("解析と精緻化が完了しました。")
            
        elif "将棋" in text or "定跡" in text:
            self.speak("最新の将棋定跡を分析し、戦術聖書を更新します。")
            subprocess.run(rf"python {self.genre_dir}\SHOGI\TACTICAL_BOOK_GENERATOR.py", shell=True)
            self.speak("戦術聖書の更新が完了しました。")
            
        elif "終了" in text or "お疲れ様" in text:
            self.speak("承知しました。システムを休止します。またいつでもお呼びください。")
            return False
        
        # 2. 解説・メンター系コマンド (New)
        elif "教えて" in text or "何" in text or "解説" in text or "説明" in text:
            prompt = f"あなたはプログラミングと画像工学の優しい先生です。初心者が「{text}」と聞いています。難しい言葉を使わず、1文で例え話を使って教えてください。"
            try:
                res = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False})
                ans = res.json().get("response", "...")
                self.speak(ans)
            except:
                self.speak("すみません、今は少し考えがまとまりません。")
            
        else:
            # 通常の会話
            # 通常の会話（Gemma 4）
            prompt = f"あなたは研究室のアシスタントです。短く返答してください。入力: {text}"
            try:
                res = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False})
                ans = res.json().get("response", "...")
                self.speak(ans)
            except:
                self.speak("申し訳ありません、思考回路にノイズが混じりました。")
        return True

    def run(self):
        self.speak("自律進化システム、音声コマンドモード起動。指令をどうぞ。")
        while True:
            cmd = self.listen()
            if cmd:
                if not self.execute_command(cmd): break
            time.sleep(0.1)

if __name__ == "__main__":
    vos = VoiceTaskOS()
    vos.run()
