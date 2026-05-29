import subprocess
import time

# --- Shogi: USI (Universal Shogi Interface) Connector ---
# This script handles communication with Shogi engines (like YaneuraOu).
# USI is the standard protocol for Shogi engines.

class ShogiEngine:
    def __init__(self, engine_path):
        self.engine_path = engine_path
        self.process = None

    def start(self):
        print(f"⚙️ Starting Shogi Engine: {self.engine_path}")
        try:
            self.process = subprocess.Popen(
                self.engine_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            # Wait for usiok to confirm engine is ready
            return self.send_command("usi", wait_for="usiok")
        except Exception as e:
            print(f"❌ Error starting engine: {e}")
            return None

    def send_command(self, command, wait_for=None):
        if not self.process: return None
        
        print(f"➡️ Command: {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        
        if wait_for:
            output = ""
            while True:
                line = self.process.stdout.readline()
                if not line: break
                output += line
                if wait_for in line: break
            return output
        return None

    def quit(self):
        self.send_command("quit")
        if self.process:
            self.process.terminate()

if __name__ == "__main__":
    # Updated path to the downloaded Suisho5 engine
    ENGINE_PATH = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\SHOGI\engines\Suisho5\YaneuraOu_NNUE-tournament-clang++-avx2.exe"
    
    # This is a test harness. If the engine doesn't exist, it will report an error.
    engine = ShogiEngine(ENGINE_PATH)
    res = engine.start()
    if res:
        print(f"✅ Engine responded:\n{res}")
    engine.quit()
