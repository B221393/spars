import speech_recognition as sr
import pyttsx3
import threading

# --- 完璧な音声入出力統合アプリ ---
# 環境に依存するマイクエラーを回避し、安全に会話できる統合アプリです。

class PerfectVoiceApp:
    def __init__(self):
        print("⚙️ システムを初期化中...")
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        
        # 音声の調整（日本語の声を検索）
        voices = self.engine.getProperty('voices')
        for v in voices:
            if "Haruka" in v.name or "Nanami" in v.name or "JP" in v.name or "Zira" in v.name:
                self.engine.setProperty('voice', v.id)
                break
        
        # 読み上げ速度を少し速くする
        self.engine.setProperty('rate', 150)
        
    def speak(self, text):
        print(f"\n🗣️ AI: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        with sr.Microphone() as source:
            print("\n🎤 マイクに向かって話してください (環境音を調整中...)")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("🟢 録音開始！")
            try:
                # タイムアウトを設定し、フリーズを防止
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                print("🔄 音声を解析中...")
                text = self.recognizer.recognize_google(audio, language="ja-JP")
                print(f"👤 あなた: {text}")
                return text
            except sr.WaitTimeoutError:
                print("⚠️ 無音が続いたためタイムアウトしました。")
                return None
            except sr.UnknownValueError:
                print("❌ 音声を認識できませんでした。もう一度お願いします。")
                return None
            except Exception as e:
                print(f"❌ マイクエラー発生: {e}\n(※Windowsのプライバシー設定でマイクが許可されているか確認してください)")
                return None

    def run(self):
        self.speak("こんにちは！完璧な音声入出力アプリが起動しました。何でも話しかけてください。終了したいときは「終了」と言ってください。")
        while True:
            text = self.listen()
            if text:
                if "終了" in text or "ストップ" in text:
                    self.speak("システムを終了します。お疲れ様でした。")
                    break
                else:
                    self.speak(f"なるほど、「{text}」ですね。しっかりと記録しました。")
                    # 必要に応じてここでファイルに書き込んだり、タスクに連携させます

if __name__ == "__main__":
    app = PerfectVoiceApp()
    app.run()
