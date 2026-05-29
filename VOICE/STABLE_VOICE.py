from VOICE_RESCUE_PRO import VoiceSystem
import time
import requests

# --- pyttsx3からEdge-TTSへアップグレードした安定版 ---

if __name__ == "__main__":
    vs = VoiceSystem()
    ctx = "設定変更の挨拶をしてください。"
    
    # 女の子
    vs.speak_sera("設定を最新のEdge-TTSに変更しました！声が綺麗になったでしょ？")
    # 男の子
    vs.speak_luci("これからは僕たちがこの声でサポートするよ。")
