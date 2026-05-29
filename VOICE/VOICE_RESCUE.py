import time
import os
import requests
import json
import win32com.client # SAPI5 (Windows Native)

# --- 音声出力・救済システム (絶対鳴らすVer) ---

def speak_native(text):
    print(f"🔊 [SAPI5] AI: {text}")
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # 日本語環境なら日本語で喋ります
        speaker.Speak(text)
        return True
    except Exception as e:
        print(f"❌ SAPI5エラー: {e}")
        return False

def get_agent_response(name, role, context):
    OLLAMA_URL = "http://localhost:11434/api/generate"
    prompt = f"あなたは{name}という名前の{role}です。女の子のような話し方で、もう一人のAIと会話してください。短く1文で答えてください。\n文脈: {context}"
    try:
        res = requests.post(OLLAMA_URL, json={"model": "gemma3:4b", "prompt": prompt, "stream": False}, timeout=30)
        return res.json().get("response", "...")
    except:
        return "通信エラーかな？"

def start_rescue_dialogue():
    print("🆘 音声救済モード：天使と悪魔の対話開始...")
    
    context = "音声が出ない問題を解決するために、Windowsの標準機能(SAPI5)を直接叩いています。"
    
    agents = [
        {"name": "セラ", "role": "天使 (SAPI5直叩き)"},
        {"name": "ルシ", "role": "悪魔 (SAPI5直叩き)"}
    ]

    for i in range(2): 
        for agent in agents:
            response = get_agent_response(agent['name'], agent['role'], context)
            print(f"【{agent['name']}】: {response}")
            # 強制的にWindows標準の声で喋らせる
            speak_native(f"{agent['name']}だよ。{response}")
            context += f"\n{agent['name']}: {response}"
            time.sleep(1)

if __name__ == "__main__":
    start_rescue_dialogue()
