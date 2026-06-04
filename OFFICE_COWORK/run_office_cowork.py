import os
import sys
import time

# Adjust system path to import AIDriver and BaseBrain
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENRE_DIR = os.path.dirname(BASE_DIR)
AI_DIR = os.path.join(GENRE_DIR, "AI")
sys.path.append(AI_DIR)

from office_cowork_brain import OfficeCoworkBrain
from CORE.ai_driver import AIDriver

def main():
    print("🚀 [Office Co-worker Test] Initializing test runner...")
    driver = AIDriver("PowerPoint")
    brain = OfficeCoworkBrain(driver)
    
    print("🔄 [Office Co-worker Test] Attempting window snapping...")
    success, msg = brain.snap_windows()
    print(f"📊 Result: {success} - {msg}")
    
    if success:
        print("🔍 [Office Co-worker Test] Fetching screen elements via OCR...")
        words = brain.perform_ocr()
        print(f"✅ Found {len(words)} words on screen.")
        # Log first 5 words
        for wd in words[:5]:
            print(f"  - '{wd['text']}' at ({wd['x']}, {wd['y']})")
            
    print("🏁 [Office Co-worker Test] Test runner complete.")

if __name__ == "__main__":
    main()
