import time
import json
import os
import requests
from VOICE_RESCUE_PRO import VoiceSystem

# --- 天使と悪魔の音声対話システム (Edge-TTSアップグレード版) ---

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

vs = VoiceSystem()

def get_agent_response(name, role, context):
    prompt = f"あなたは{name}という名前の{role}です。短く1文で答えてください。\n文脈: {context}"
    try:
        res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": False}, timeout=30)
        return res.json().get("response", "...")
    except:
        return "通信エラーかな？"

def start_angel_demon_dialogue():
    print("✨ 天使（女）と悪魔（男）の対話開始...")
    
    context = "設定が更新され、セラは女の子、ルシは男の子の声になりました。ユーザーに感謝を伝えてください。"
    
    agents = [
        {"name": "セラ", "role": "優しくて明るい天使の女の子", "type": "female"},
        {"name": "ルシ", "role": "少し意地悪だけど冷静な悪魔の男の子", "type": "male"}
    ]

    for i in range(1): # 短く1回ずつ
        for agent in agents:
            response = get_agent_response(agent['name'], agent['role'], context)
            if agent['type'] == "female":
                vs.speak_sera(f"{agent['name']}だよ。{response}")
            else:
                vs.speak_luci(f"{agent['name']}だ。{response}")
            context += f"\n{agent['name']}: {response}"
            time.sleep(0.5)

if __name__ == "__main__":
    start_angel_demon_dialogue()
