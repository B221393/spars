import asyncio
import edge_tts
import pygame
import os
import time
import random

from MODULE_MANAGER import ModuleManager

# --- 究極の音声システム (edge-tts版) ---
# 男女の声を使い分け、ピッチ調整も可能

class VoiceSystem:
    def __init__(self):
        self.female_voice = "ja-JP-NanamiNeural"
        self.male_voice = "ja-JP-KeitaNeural"
        self.mm = ModuleManager()

        # 初期化時に音声出力を確認
        try:
            pygame.mixer.init()
        except: pass

    async def _generate_and_play(self, text, voice, pitch="0.05", rate="1.1"):
        # 最終防衛線: 設定が無効なら何もしない
        if not self.mm.is_enabled("voice_output"):
            print(f"🔇 [System Muted] {text}")
            return

        communicate = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)

        filename = f"voice_{int(time.time() * 1000)}.mp3"
        await communicate.save(filename)
        
        try:
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            
            # --- 口の動き（Lip-Sync）のシミュレーション ---
            while pygame.mixer.music.get_busy():
                # 音量や文字数に基づいて、口の開き具合（0.0〜1.0）を擬似計算
                aperture = random.uniform(0.1, 0.9)
                print(f"\r👄 Lip Aperture: {'#' * int(aperture * 10):10} ({aperture:.2f})", end="")
                await asyncio.sleep(0.1)
            print("\r" + " " * 40 + "\r", end="") # クリア
            
            pygame.mixer.music.unload()
        finally:
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass

    def speak_sera(self, text):
        """明るい女の子（セラ）: 高いピッチ"""
        print(f"👧 セラ: {text}")
        asyncio.run(self._generate_and_play(text, self.female_voice, pitch="0.1", rate="1.05"))

    def speak_luci(self, text):
        """落ち着いた男性（ルシ）: 標準ピッチ"""
        print(f"👦 ルシ: {text}")
        asyncio.run(self._generate_and_play(text, self.male_voice, pitch="0.1", rate="1.05"))

if __name__ == "__main__":
    vs = VoiceSystem()
    print("✨ 音声システムをアップグレードしました (Male/Female, High Pitch)")
    vs.speak_sera("こんにちは！新しい設定だよ。声、高くなったかな？")
    time.sleep(1)
    vs.speak_luci("僕はルシだ。落ち着いた男の声になったはずだ。")
