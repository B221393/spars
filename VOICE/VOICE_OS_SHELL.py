import speech_recognition as sr
import pyttsx3
import requests
import time

# --- 🎙️ 完全ハンズフリー：音声対話AIシェル (Voice OS V1) ---
# あなたの声を聴き、AIが考え、声で返します。
# 必要なもの: pip install speech_recognition pyttsx3 PyAudio

class VoiceOS:
    def __init__(self, model="gemma3:4b"):
        self.model = model
        self.ollama_url = "http://localhost:11434/api/generate"
        
        # 声の準備
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        for v in voices:
            if "JP" in v.name or "Japanese" in v.name:
                self.engine.setProperty('voice', v.id)
                break
        self.engine.setProperty('rate', 180) # 少し速めに

        # 耳の準備
        self.recognizer = sr.Recognizer()

    def speak(self, text):
        print(f"🤖 AI: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        with sr.Microphone() as source:
            print("\n👂 聴いています... (話しかけてください)")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                print("🔄 解析中...")
                text = self.recognizer.recognize_google(audio, language="ja-JP")
                print(f"👤 あなた: {text}")
                return text
            except sr.WaitTimeoutError:
                return None
            except Exception as e:
                print(f"🔇 聞き取れませんでした: {e}")
                return None

    def think(self, user_input):
        print(f"🧠 {self.model} が思考中...")
        prompt = f"あなたは音声対話アシスタントです。短く1文で、口頭での会話として自然な返答をしてください。\n入力: {user_input}"
        try:
            res = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False}, timeout=15)
            return res.json().get("response", "すみません、うまく考えられませんでした。")
        except:
            return "Ollamaとの接続を確認してください。"

    def run(self):
        self.speak("音声対話モードを開始しました。何かお手伝いしましょうか？")
        
        while True:
            text = self.listen()
            
            if text:
                if "終了" in text or "ストップ" in text:
                    self.speak("音声対話モードを終了します。さようなら！")
                    break
                
                # 思考して返答
                response = self.think(text)
                self.speak(response)
            
            time.sleep(0.1)

if __name__ == "__main__":
    # 実行前に `pip install PyAudio` が必要です
    vos = VoiceOS()
    vos.run()
