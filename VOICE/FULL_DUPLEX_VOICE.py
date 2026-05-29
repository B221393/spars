import threading
import time
import win32com.client
import speech_recognition as sr
import os
import requests

# --- 同時入出力 (Full-Duplex) ボイスシステム ---

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class VoiceSystem:
    def __init__(self):
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.recognizer = sr.Recognizer()
        self.is_running = True
        self.last_user_input = ""

    def speak(self, text):
        """非同期で喋るためのスレッド用関数"""
        print(f"🔊 AI: {text}")
        # SAPI5のフラグ 1 は非同期再生を意味します
        self.speaker.Speak(text, 1)

    def listen_loop(self):
        """常に耳を傾け続けるスレッド"""
        print("👂 あなたの声を聞いています... (いつでも話しかけてください)")
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            while self.is_running:
                try:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    text = self.recognizer.recognize_google(audio, language='ja-JP')
                    print(f"👤 あなた: {text}")
                    self.last_user_input = text
                    # ユーザーの声に反応して天使と悪魔が議論を開始
                    self.trigger_ai_reaction(text)
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    # エラーは無視して聞き続ける
                    continue

    def trigger_ai_reaction(self, user_text):
        prompt = f"ユーザーが『{user_text}』と言いました。天使のセラと悪魔のルシとして、女の子っぽく短く反応してください。"
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False})
            response = res.json().get("response", "聞こえたよ！")
            self.speak(response)
        except:
            self.speak("ちょっと耳が遠いみたい…")

    def run(self):
        # 入力と出力を別スレッドで開始
        listener_thread = threading.Thread(target=self.listen_loop)
        listener_thread.daemon = True
        listener_thread.start()

        print("✨ 同時入出力システム起動完了。")
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.is_running = False

if __name__ == "__main__":
    # 録音デバイスが利用可能か確認してから実行
    vs = VoiceSystem()
    vs.speak("同時入出力の準備ができたよ。いつでも話しかけてね。")
    vs.run()
