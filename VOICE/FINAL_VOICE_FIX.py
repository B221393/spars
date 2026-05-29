from VOICE_RESCUE_PRO import VoiceSystem
import requests
import time

# --- Edge-TTSを使用した究極の男女ボイス分離システム ---

if __name__ == "__main__":
    vs = VoiceSystem()
    print("✅ 音声人格の分離（男×女）を Edge-TTS で再構成しました。")
    
    # セラ (女)
    vs.speak_sera("新しい声だよ！ピッチも高く調整して、もっと女の子らしくなったかな？")
    
    time.sleep(0.5)
    
    # ルシ (男)
    vs.speak_luci("僕はルシだ。冷静で落ち着いた男性の声になっているはずだ。")
