import threading
import queue
import time
import requests
import json
import os
import asyncio
import edge_tts
import pygame
import speech_recognition as sr
from VOICE_RESCUE_PRO import VoiceSystem

# --- 究極の同時入出力 (Full-Duplex) ボイスシステム Pro (バランス調整版) ---

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class FullDuplexAI:
    def __init__(self):
        self.vs = VoiceSystem()
        self.recognizer = sr.Recognizer()
        self.is_running = True
        self.speech_queue = queue.Queue()
        self.is_ai_speaking = False  # AIが発話中かどうかのフラグ
        
        # 音声出力用スレッドの開始
        self.output_thread = threading.Thread(target=self._output_worker)
        self.output_thread.daemon = True
        self.output_thread.start()

    def stop_current_speech(self):
        """現在再生中の音声を強制停止する (ユーザーの割り込み用)"""
        if pygame.mixer.music.get_busy():
            print("🛑 割り込み検知: AIの発話を停止します。")
            pygame.mixer.music.stop()
            # キューもクリアして、新しい話題に集中する
            while not self.speech_queue.empty():
                try: self.speech_queue.get_nowait()
                except: break

    def _output_worker(self):
        """音声出力をバックグラウンドで処理する"""
        while self.is_running:
            try:
                task = self.speech_queue.get(timeout=1)
                self.is_ai_speaking = True
                
                speaker = task.get('speaker', 'Sera')
                text = task.get('text', '')
                
                if speaker == 'Luci':
                    self.vs.speak_luci(text)
                else:
                    self.vs.speak_sera(text)
                
                self.is_ai_speaking = False
                self.speech_queue.task_done()
            except queue.Empty:
                self.is_ai_speaking = False
                continue
            except Exception as e:
                print(f"❌ 出力ワーカーエラー: {e}")
                self.is_ai_speaking = False

    def ai_think_and_queue(self, user_input):
        """ユーザーの入力を分析し、応答をキューに入れる"""
        # バランスを考えたプロンプト：簡潔に、かつ相手を尊重する
        prompt = f"""
あなたはユーザーの秘書AI（セラとルシ）です。
ユーザーが話しかけてきました。会話のバランスを考え、一言二言で簡潔に、かつ親身に答えてください。
二人の掛け合いで、ユーザーの話を遮りすぎないように注意してください。

【ユーザーの入力】
"{user_input}"

【出力形式 (JSON)】
{{
  "thought": "（AIの内部思考：ユーザーの意図をどう汲み取ったか）",
  "sera_says": "（セラの返答、1文。明るく簡潔に）",
  "luci_says": "（ルシの返答、1文。冷静に短く）"
}}
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=30)
            data = res.json().get("response", "")
            
            start = data.find('{'); end = data.rfind('}')
            if start != -1 and end != -1:
                result = json.loads(data[start:end+1])
                
                # 新しい応答をキューに入れる
                if result.get('sera_says'):
                    self.speech_queue.put({'speaker': 'Sera', 'text': result['sera_says']})
                if result.get('luci_says'):
                    self.speech_queue.put({'speaker': 'Luci', 'text': result['luci_says']})
        except Exception as e:
            print(f"❌ AI思考エラー: {e}")

    def listen_loop(self):
        """耳を傾け続け、声を検知したら思考スレッドを立ち上げる"""
        print("\n👂 [Balanced Duplex] 聞いています... (話しかけるとAIは話を止めて聞き役に回ります)")
        with sr.Microphone() as source:
            # 雑音抑制を強めに設定（バランス重視）
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            self.recognizer.energy_threshold = 300 # 感度調整
            
            while self.is_running:
                try:
                    # 音声入力を検知
                    audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=5)
                    
                    # 声が入った瞬間、AIが喋っていたら止める (Barge-in)
                    self.stop_current_speech()
                    
                    text = self.recognizer.recognize_google(audio, language='ja-JP')
                    
                    if text:
                        print(f"👤 あなた: {text}")
                        threading.Thread(target=self.ai_think_and_queue, args=(text,)).start()
                        
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except Exception as e:
                    print(f"⚠️ リスニングエラー: {e}")
                    time.sleep(1)

    def run(self):
        print("🚀 会話バランス調整済みシステム 起動。")
        self.speech_queue.put({'speaker': 'Sera', 'text': 'こんにちは！会話のバランスを考えて、もっと自然にお話しできるように調整したよ。私が喋ってる時でも、いつでも遮って教えてね！'})
        
        try:
            self.listen_loop()
        except KeyboardInterrupt:
            print("\n🛑 終了します...")
            self.is_running = False

if __name__ == "__main__":
    ai = FullDuplexAI()
    ai.run()
