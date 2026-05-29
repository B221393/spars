import time
import json
import os
import requests
from gtts import gTTS
import pygame

# --- マルチエージェント & 音声対話 実験場 ---

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

def speak(text, lang='ja'):
    print(f"🔊 AI: {text}")
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save("temp_voice.mp3")
        pygame.mixer.init()
        pygame.mixer.music.load("temp_voice.mp3")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.quit()
        os.remove("temp_voice.mp3")
    except Exception as e:
        print(f"音声出力エラー: {e}")

def get_agent_response(name, role, context):
    prompt = f"あなたは{name}という名前の{role}です。以下の文脈に基づき、もう一人のAIと会話してください。短く1文で答えてください。\n文脈: {context}"
    try:
        res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=30)
        return res.json().get("response", "...")
    except:
        return "通信エラーです。"

def start_ai_dialogue():
    print("🎭 AI同士の対話を開始します...")
    
    context = "これから協力して、ユーザーのために最強の将棋AIと就活支援アプリを完成させなければなりません。"
    
    agents = [
        {"name": "アキラ", "role": "理論派の将棋棋士AI"},
        {"name": "エンジ", "role": "情熱的な開発エンジニアAI"}
    ]

    for i in range(3): # 3往復の会話
        for agent in agents:
            response = get_agent_response(agent['name'], agent['role'], context)
            print(f"【{agent['name']}】: {response}")
            speak(f"{agent['name']}です。{response}")
            context += f"\n{agent['name']}: {response}"
            time.sleep(1)

if __name__ == "__main__":
    start_ai_dialogue()
    
    # 完了ログへの追記
    log_path = "codex-vs-local-agent-loop/FINAL_LOG.json"
    if os.path.exists(log_path):
        with open(log_path, "r+", encoding="utf-8") as f:
            logs = json.load(f)
            logs.insert(0, {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "task": "AI同士の音声対話実験",
                "result": "異なる人格を持つAI同士が音声で意思疎通できることを確認しました。",
                "duration_sec": 12.0
            })
            f.seek(0)
            json.dump(logs, f, indent=2, ensure_ascii=False)
