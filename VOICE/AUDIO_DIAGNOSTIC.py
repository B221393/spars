import sounddevice as sd
import numpy as np
import pygame
import time
import os

def list_devices():
    print("--- Audio Devices ---")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        print(f"[{i}] {dev['name']} (In: {dev['max_input_channels']}, Out: {dev['max_output_channels']})")
    
    default_in = sd.default.device[0]
    default_out = sd.default.device[1]
    print(f"\nDefault Input: [{default_in}] {devices[default_in]['name']}")
    print(f"Default Output: [{default_out}] {devices[default_out]['name']}")

def test_input():
    print("\n--- Testing Input (Mic) ---")
    print("Talk into the mic for 5 seconds...")
    duration = 5
    fs = 44100
    try:
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        start_time = time.time()
        while time.time() - start_time < duration:
            level = np.linalg.norm(recording[int((time.time()-start_time)*fs):int((time.time()-start_time+0.1)*fs)])
            print(f"\rLevel: {'█' * int(min(level * 50, 50)):50}", end="")
            time.sleep(0.1)
        sd.wait()
        print("\nInput test complete.")
    except Exception as e:
        print(f"\nInput Error: {e}")

def test_output():
    print("\n--- Testing Output (Speaker) ---")
    pygame.mixer.init()
    # Create a simple beep sound
    fs = 44100
    duration = 1.0
    f = 440.0
    samples = (np.sin(2 * np.pi * np.arange(fs * duration) * f / fs)).astype(np.float32)
    
    # Save as wav to play with pygame (or just play with sounddevice)
    import wave
    wav_file = "test_beep.wav"
    with wave.open(wav_file, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes((samples * 32767).astype(np.int16).tobytes())
    
    try:
        print("Playing a beep...")
        pygame.mixer.music.load(wav_file)
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        print("Output test complete.")
    finally:
        if os.path.exists(wav_file):
            os.remove(wav_file)

if __name__ == "__main__":
    list_devices()
    test_input()
    test_output()
