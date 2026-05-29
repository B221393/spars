import sounddevice as sd
import numpy as np
import time

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    # 入力音量の実効値 (RMS) を計算
    volume_norm = np.linalg.norm(indata) * 10
    print(f"\r🎤 Mic Input Level: {'█' * int(min(volume_norm, 50)):50} ({volume_norm:.2f})", end="")

def monitor_mic():
    print("--- Microphone Volume Monitor (Press Ctrl+C to stop) ---")
    try:
        with sd.InputStream(callback=audio_callback):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    monitor_mic()
