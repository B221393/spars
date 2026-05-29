import asyncio
from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np
import wave
import os
import time

# --- 音声入力・タスク自動追加システム (Whisper版) ---

class VoiceTaskAdder:
    def __init__(self, model_size="base"):
        print(f"Loading Whisper model ({model_size})...")
        # デバイス名で動的に検索
        self.input_device = None
        for i, dev in enumerate(sd.query_devices()):
            if "SoundWire DSP Microphone" in dev['name'] and dev['max_input_channels'] > 0:
                self.input_device = i
                break
        
        if self.input_device is None:
            print("Warning: SoundWire DSP Microphone not found. Using default.")
        else:
            print(f"Using Input Device: {sd.query_devices(self.input_device)['name']}")
            sd.default.device[0] = self.input_device
            
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.task_file = "C:/Users/yu_ci/Desktop/codex-vs-local-agent-loop/INPUT/USER_TASKS.txt"

    def record_audio(self, duration=5, fs=48000):
        print(f"Recording for {duration} seconds...")
        # InputStreamを直接制御して安定させる
        try:
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=2, device=self.input_device)
            sd.wait()
            return recording, fs
        except Exception as e:
            print(f"Recording error: {e}")
            return None, fs

    def save_and_transcribe(self, recording, fs):
        if recording is None: return None
        filename = "temp_task_audio.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(2) # 2チャンネルで保存
            wf.setsampwidth(2)
            wf.setframerate(fs)
            wf.writeframes((recording * 32767).astype(np.int16).tobytes())
        
        print("Transcribing...")
        segments, info = self.model.transcribe(filename, beam_size=5, language="ja")
        
        text = ""
        for segment in segments:
            text += segment.text
        
        text = text.strip()
        if text:
            print(f"Recognized: {text}")
            with open(self.task_file, "a", encoding="utf-8") as f:
                f.write(f"\n[音声入力] {text}")
            print(f"✅ Task added to {self.task_file}")
            return text
        else:
            print("No speech recognized.")
            return None

if __name__ == "__main__":
    vta = VoiceTaskAdder()
    rec, fs = vta.record_audio(duration=5)
    vta.save_and_transcribe(rec, fs)
    if os.path.exists("temp_task_audio.wav"):
        os.remove("temp_task_audio.wav")
