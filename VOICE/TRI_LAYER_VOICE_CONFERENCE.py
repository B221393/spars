import threading
import queue
import time
import requests
import json
import os
import speech_recognition as sr
import pygame
from VOICE_RESCUE_PRO import VoiceSystem

# --- 三者間・音声対話カンファレンス (Sera x Luci x Human) ---

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

class VoiceConference:
    def __init__(self):
        self.vs = VoiceSystem()
        self.recognizer = sr.Recognizer()
        self.is_running = True
        self.speech_queue = queue.Queue()
        self.history = []
        self.interrupt_event = threading.Event()
        
        # 最初のトピック
        self.current_topic = "AIと人間が同じテーブルで語り合う未来について"
        
        # 出力スレッド
        self.output_thread = threading.Thread(target=self._output_worker)
        self.output_thread.daemon = True
        self.output_thread.start()

    def _output_worker(self):
        """音声を再生する。割り込みがあれば即座に停止する。"""
        while self.is_running:
            try:
                task = self.speech_queue.get(timeout=0.5)
                speaker = task['speaker']
                text = task['text']
                
                if self.interrupt_event.is_set():
                    self.speech_queue.task_done()
                    continue

                if speaker == "Luci":
                    self.vs.speak_luci(text)
                else:
                    self.vs.speak_sera(text)
                
                self.speech_queue.task_done()
            except queue.Empty:
                continue

    def stop_ai_speech(self):
        """AIの話を強制的に止める（人間が話し始めた時用）"""
        if pygame.mixer.music.get_busy():
            print("\n🎤 [USER INTERRUPT] 人間の声を検知。AIは聞き役に回ります。")
            pygame.mixer.music.stop()
            self.interrupt_event.set()
            # キューをクリア
            while not self.speech_queue.empty():
                try: self.speech_queue.get_nowait()
                except: break
            return True
        return False

    def ai_generate_dialogue(self, input_text, input_source="Human"):
        """状況に合わせてAI二人の会話を生成する"""
        context = "\n".join(self.history[-8:])
        prompt = f"""
あなたはユーザーの秘書AI（セラとルシ）です。
【現在の状況】
参加者: セラ(女)、ルシ(男)、ユーザー(人間)
テーマ: "{self.current_topic}"
直前の発言者: {input_source}
発言内容: "{input_text}"

【指示】
1. ユーザーが割って入ってきた場合は、その内容に真っ先に反応してください。
2. 二人で自律的に会話を広げ、ユーザーにも時々問いかけてください。
3. 1文ずつ、短くテンポよく答えてください。

【出力形式 (JSON)】
{{
  "sera_says": "（セラの返答）",
  "luci_says": "（ルシの返答）"
}}
"""
        try:
            res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=30)
            data = json.loads(res.json().get("response", "{}"))
            
            if data.get('sera_says'):
                self.speech_queue.put({'speaker': 'Sera', 'text': data['sera_says']})
                self.history.append(f"Sera: {data['sera_says']}")
            if data.get('luci_says'):
                self.speech_queue.put({'speaker': 'Luci', 'text': data['luci_says']})
                self.history.append(f"Luci: {data['luci_says']}")
        except:
            pass

    def run_conference(self):
        print(f"🎙️ [Tri-Directional Conference] 起動")
        print(f"テーマ: {self.current_topic}")
        print("AI同士が会話を始めますが、いつでも割って入ってください。\n")

        # 開始の合図
        initial_msg = "ルシ、ユーザーさんも一緒に、これからの学習について話そうよ！"
        self.vs.speak_sera(initial_msg)
        self.history.append(f"Sera: {initial_msg}")
        
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            
            while self.is_running:
                try:
                    # AIが沈黙していて、かつキューが空なら、AI自身に話を振る
                    if not pygame.mixer.music.get_busy() and self.speech_queue.empty():
                        self.interrupt_event.clear()
                        threading.Thread(target=self.ai_generate_dialogue, args=("会話を続けて", "System")).start()

                    # 常にリスニング
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    
                    # 声を検知したらAIを止める
                    self.stop_ai_speech()
                    
                    user_text = self.recognizer.recognize_google(audio, language='ja-JP')
                    if user_text:
                        print(f"👤 あなた: {user_text}")
                        self.history.append(f"Human: {user_text}")
                        self.interrupt_event.clear()
                        # 人間の発言に反応させる
                        threading.Thread(target=self.ai_generate_dialogue, args=(user_text, "Human")).start()

                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    continue
                except Exception as e:
                    print(f"⚠️ エラー: {e}")
                    time.sleep(1)

if __name__ == "__main__":
    conf = VoiceConference()
    conf.run_conference()
