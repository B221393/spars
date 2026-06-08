#!/usr/bin/env python3
import requests
import json
import sys

# Reconfigure stdout/stderr to UTF-8 to prevent CP932 encoding issues on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def pull_model(model_name="gemma2:2b", ollama_url="http://localhost:11434"):
    url = f"{ollama_url}/api/pull"
    payload = {"name": model_name, "stream": True}
    
    print(f"[Ollama] Requesting to pull model: '{model_name}'...")
    try:
        response = requests.post(url, json=payload, stream=True, timeout=600)
        if response.status_code != 200:
            print(f"[Ollama] Failed to request pull: Status code {response.status_code}")
            return False
            
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode('utf-8'))
                status = data.get("status", "")
                completed = data.get("completed", 0)
                total = data.get("total", 0)
                
                if total > 0:
                    pct = (completed / total) * 100
                    sys.stdout.write(f"\r[Ollama] Status: {status} | Progress: {pct:.2f}% ({completed}/{total} bytes)")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r[Ollama] Status: {status}")
                    sys.stdout.flush()
        print("\n[Ollama] Model download and setup complete!")
        return True
    except Exception as e:
        print(f"\n[Ollama] Error contacting Ollama API: {e}")
        return False

if __name__ == "__main__":
    model = "gemma2:2b"
    if len(sys.argv) > 1:
        model = sys.argv[1]
    pull_model(model)
