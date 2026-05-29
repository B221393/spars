import os
import re
import json
import sys

# Prevent console encoding issues on Windows Japanese locale
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def learn_new_game(html_path):
    if not os.path.exists(html_path):
        print(f"❌ Error: HTML file not found at: {html_path}")
        return False
        
    filename = os.path.basename(html_path)
    game_id = os.path.splitext(filename)[0].upper()
    game_dir = os.path.join(os.path.dirname(html_path), game_id)
    
    # Create folder dynamically
    os.makedirs(game_dir, exist_ok=True)
    
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Parse Title
    title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else game_id
    
    # Parse Buttons
    buttons = []
    # Match id and text content
    btn_matches = re.finditer(r'<button\s+[^>]*id=["\'](.*?)["\']\s*[^>]*>(.*?)</button>', content, re.IGNORECASE)
    for m in btn_matches:
        btn_id = m.group(1)
        btn_text = re.sub('<[^<]+?>', '', m.group(2)).strip()
        buttons.append({"id": btn_id, "text": btn_text})
        
    # Parse Key events
    key_codes = []
    key_matches = re.finditer(r"['\"](Key[A-Z0-9])['\"]", content)
    for m in key_matches:
        key_codes.append(m.group(1))
    key_codes = list(set(key_codes))
    
    # Create rules.md
    rules_path = os.path.join(game_dir, "rules.md")
    with open(rules_path, "w", encoding="utf-8") as f:
        f.write(f"# 📖 {title} - Rules & Objectives\n\n")
        f.write(f"Autonomously analyzed game from `{html_path}`.\n\n")
        f.write("## 🎮 Core Mechanics\n")
        
        if "score" in content.lower():
            f.write("- **Goal**: Score points by successfully hitting active targets.\n")
        if "random" in content.lower():
            f.write("- **Dynamic Layout**: Target positions or speed randomize dynamically during play.\n")
        if key_codes:
            f.write("- **Inputs**: Responds to key actions: " + ", ".join([f"`{k}`" for k in key_codes]) + ".\n")
        if buttons:
            f.write("- **UI Controls**: Interactable click buttons are present on screen.\n")
            
    # Create controls.json
    controls_path = os.path.join(game_dir, "controls.json")
    controls_data = {
        "game_title": title,
        "source_path": html_path,
        "buttons": buttons,
        "keys": key_codes
    }
    with open(controls_path, "w", encoding="utf-8") as f:
        json.dump(controls_data, f, indent=2, ensure_ascii=False)
        
    # Create play_agent.py template
    agent_path = os.path.join(game_dir, "play_agent.py")
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(f"""# 🤖 Autonomous Play Agent for {title}
import sys
import os
import time

# Reference central AI drivers
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "AI"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "AI", "CORE"))
from ai_driver import AIDriver

def main():
    print("Starting play agent for {title}...")
    driver = AIDriver("{title}")
    
    if not driver.hwnd:
        print("Launching game...")
        os.system("start microsoft-edge:{html_path}")
        time.sleep(3.0)
        driver.connect()
        
    if not driver.hwnd:
        print("❌ Could not connect to game window.")
        return
        
    # Detected control endpoints:
""")
        if buttons:
            f.write("    # Buttons to target:\n")
            for b in buttons:
                f.write(f"    # - Button ID: '{b['id']}' (Text: '{b['text']}')\n")
        if key_codes:
            f.write("    # Keyboard controls to trigger:\n")
            for k in key_codes:
                f.write(f"    # - Key Code: '{k}'\n")
                
        f.write("""
    # Add custom automation play loop here
    print("Agent running...")
    
if __name__ == "__main__":
    main()
""")
        
    print(f"🎉 Game Learner completed learning for: {title}")
    print(f"📂 Created Folder: {game_dir}")
    print(f"📄 Created Files: rules.md, controls.json, play_agent.py")
    return True

if __name__ == "__main__":
    # Test learning on training_game.html
    train_game = r"C:\Users\yu_ci\AI_AUTOMATOR\training_game.html"
    learn_new_game(train_game)
    
    # Test learning on rhythm_game.html
    rhythm_game = r"C:\Users\yu_ci\Desktop\GENRE_FOLDERS\GAME\rhythm_game.html"
    learn_new_game(rhythm_game)
