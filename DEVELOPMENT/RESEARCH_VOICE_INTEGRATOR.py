import cv2
import numpy as np
import pyttsx3
import speech_recognition as sr
import threading
import queue
import time
import os
import csv
import requests

# --- Research & Voice Integrator (Perpetual Evolution V5) ---
# 1. 画像解析 (Tracking) の進捗を音声で報告
# 2. ローカルLLM (Ollama) による解析結果の要約
# 3. 音声コマンドによる解析の開始/停止

class VoiceAssistant:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        self.speech_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # 日本語ボイスの設定
        voices = self.engine.getProperty('voices')
        for v in voices:
            if "JP" in v.name or "Japanese" in v.name or "Haruka" in v.name:
                self.engine.setProperty('voice', v.id)
                break
        self.engine.setProperty('rate', 170)

        # 読み上げスレッドの開始
        self.tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
        self.tts_thread.start()

    def _tts_loop(self):
        while not self.stop_event.is_set():
            try:
                text = self.speech_queue.get(timeout=0.5)
                print(f"🗣️ AI: {text}")
                self.engine.say(text)
                self.engine.runAndWait()
                self.speech_queue.task_done()
            except queue.Empty:
                continue

    def say(self, text):
        self.speech_queue.put(text)

    def listen(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                print("🎤 待機中...")
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio, language="ja-JP")
                print(f"👤 User: {text}")
                return text
            except:
                return None

class ResearchBrain:
    def __init__(self, model="gemma3:4b"): # より高速なモデルに変更
        self.model = model
        self.ollama_url = "http://localhost:11434/api/generate"

    def summarize_results(self, data_summary):
        prompt = f"""あなたは画像計測工学の専門家です。以下のトラッキング解析結果を深く洞察し、
計測の不確かさや物理的な整合性の観点から、1文で高度なフィードバックを述べてください。

データ: {data_summary}"""
        try:
            res = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False}, timeout=60)
            return res.json().get("response", "データの解析が完了しました。")
        except:
            return "Ollama (Sage) との接続に失敗しました。"

class IntegratedSystem:
    def __init__(self):
        self.assistant = VoiceAssistant()
        self.brain = ResearchBrain()
        self.is_running = True

    def run(self, once=False):
        if once:
            self.execute_tracking_analysis()
            # 音声再生が終わるのを待つ
            while not self.assistant.speech_queue.empty():
                time.sleep(1)
            time.sleep(2) # 最後のバッファ
            return

        self.assistant.say("システムを起動しました。研究データの解析を開始しますか？")
        
        while self.is_running:
            command = self.assistant.listen()
            
            if command:
                if "開始" in command or "やって" in command:
                    self.assistant.say("承知いたしました。トラッキング解析を実行します。")
                    self.execute_tracking_analysis()
                elif "終了" in command or "ストップ" in command:
                    self.assistant.say("システムを終了します。お疲れ様でした。")
                    self.is_running = False
            
            time.sleep(0.1)

    def execute_tracking_analysis(self):
        # 整理後の解析データパス
        csv_path = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\RESEARCH\tracking_data_pro.csv"
        if os.path.exists(csv_path):
            self.assistant.say("既存の解析データを読み込んでいます。")
            
            velocities = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # ヘッダー名が異なる可能性を考慮
                        v = float(row.get('velocity_px_sec', row.get('velocity', 0)))
                        if v > 0: velocities.append(v)
                    except: pass
            
            if velocities:
                avg_v = np.mean(velocities)
                max_v = np.max(velocities)
                summary_data = f"平均速度: {avg_v:.2f} px/sec, 最大速度: {max_v:.2f} px/sec"
                
                # LLMによる要約
                ai_comment = self.brain.summarize_results(summary_data)
                self.assistant.say(f"解析結果の要約です。{ai_comment}")
            else:
                self.assistant.say("有効な速度データが見つかりませんでした。")
        else:
            self.assistant.say("解析対象のCSVファイルが見つかりません。")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    
    system = IntegratedSystem()
    system.run(once=args.once)
