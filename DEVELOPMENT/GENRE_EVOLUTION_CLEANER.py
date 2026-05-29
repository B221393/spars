import os
import shutil
import hashlib

# --- Genre-Aware Workspace Cleaner ---
# Goal: Consolidate everything into GENRE_FOLDERS and remove duplicates.

GENRE_DIR = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS"
SOURCE_DIRS = [
    r"C:\Users\yu_ci\Desktop",
    r"C:\Users\yu_ci\Desktop\codex-vs-local-agent-loop",
    r"C:\Users\yu_ci\Desktop\shogi-ai-nurturing",
    r"C:\Users\yu_ci\Desktop\kennkyuu",
    r"C:\Users\yu_ci\Downloads"
]

GENRE_MAP = {
    "SHOGI": ["shogi", "joseki", "usi", "yaneura"],
    "VOICE": ["voice", "audio", "agent", "dialogue", "stt", "tts"],
    "RESEARCH": ["research", "trajectory", "tracking", "kalman", "uncertainty", "avi", "mp4", "9992025"],
    "EXAM": ["exam", "interview", "civil_service"],
    "DEVELOPMENT": ["codex", "evolution", "benchmark", "harness", "master", "orchestrator"]
}

def get_hash(path):
    hasher = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def identify_genre(filename):
    filename = filename.lower()
    for genre, keywords in GENRE_MAP.items():
        for kw in keywords:
            if kw in filename:
                return genre
    return None

def cleanup():
    print("🚀 Starting Genre-Aware Cleanup...")
    
    # 1. Map existing files in GENRE_FOLDERS
    genre_files = {} # hash -> path
    for root, dirs, files in os.walk(GENRE_DIR):
        for f in files:
            path = os.path.join(root, f)
            try:
                h = get_hash(path)
                genre_files[h] = path
            except: pass

    # 2. Scan source dirs
    for s_dir in SOURCE_DIRS:
        if not os.path.exists(s_dir): continue
        if s_dir == GENRE_DIR: continue
        
        print(f"\n📂 Scanning: {s_dir}")
        for f in os.listdir(s_dir):
            path = os.path.join(s_dir, f)
            if not os.path.isfile(path): continue
            if f.endswith(".lnk") or f == "desktop.ini": continue

            try:
                h = get_hash(path)
                # If duplicate exists in GENRE_FOLDERS, delete this one
                if h in genre_files:
                    print(f"🗑️ Duplicate found, deleting: {f}")
                    os.remove(path)
                else:
                    # If not in GENRE_FOLDERS, identify genre and MOVE
                    genre = identify_genre(f)
                    if genre:
                        dest_dir = os.path.join(GENRE_DIR, genre)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest_path = os.path.join(dest_dir, f)
                        
                        if not os.path.exists(dest_path):
                            print(f"📦 Moving to {genre}: {f}")
                            shutil.move(path, dest_path)
                            genre_files[h] = dest_path
                        else:
                            # Conflict with same name but different content?
                            print(f"⚠️ Conflict: {f} already exists in {genre} (different content).")
            except Exception as e:
                print(f"❌ Error processing {f}: {e}")

    print("\n✨ Cleanup Complete.")

if __name__ == "__main__":
    cleanup()
