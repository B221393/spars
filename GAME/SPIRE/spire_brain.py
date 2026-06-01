import time
import re
import cv2
import os
import spire_utils as utils

class SpireBrain:
    def __init__(self, eye, body, tactics):
        self.eye = eye
        self.body = body
        self.tactics = tactics
        self.last_state = "UNKNOWN"

    def handle_shop(self, frame, save_data):
        print("🛒 [Shop] ショップ画面を検知。購入または退出を検討します...")
        w, h = self.eye.window_size
        words = self.eye.get_all_text_coords(frame)
        
        gold = 0
        if save_data and "players" in save_data and save_data["players"]:
            gold = save_data["players"][0].get("gold", 0)
            print(f"💰 [Shop] Current Gold: {gold}")
        
        leave_coord = None
        for w_data in words:
            txt = w_data['text'].lower().replace(" ", "")
            cx = w_data['x'] + w_data['w'] // 2
            cy = w_data['y'] + w_data['h'] // 2
            if (cx / w > 0.70 and cy / h > 0.70) and any(kw in txt for kw in ["戻る", "leave", "exit", "戻る", "去る"]):
                leave_coord = (cx, cy)
                break
        
        if not leave_coord:
            leave_coord = utils.get_coord("menu", "leave_button", (0.88, 0.85), w, h)

        remove_coord = None
        for w_data in words:
            txt = w_data['text'].lower()
            if any(kw in txt for kw in ["削除", "除去", "remove", "purge"]):
                cx = w_data['x'] + w_data['w'] // 2
                cy = w_data['y'] + w_data['h'] // 2
                if 0.5 < (cx / w) < 0.9 and 0.2 < (cy / h) < 0.6:
                    remove_coord = (cx, cy)
                    break
        
        if remove_coord and gold >= 75:
            print(f"🛒 [Shop] Attempting card removal service at {remove_coord}...")
            self.body.click_position(remove_coord, "Card Removal Service")
            time.sleep(1.0)
            return True

        print("🛒 [Shop] Leaving shop...")
        self.body.confirm_and_push(leave_coord, "Leave Shop Button", self.eye)
        time.sleep(0.5)
        return False

    def handle_rest_site(self, frame, save_data):
        w, h = self.eye.window_size
        words = self.eye.get_all_text_coords(frame)
        
        hp_ratio = 1.0
        if save_data and "players" in save_data and save_data["players"]:
            player = save_data["players"][0]
            current_hp = player.get("current_hp", 80)
            max_hp = max(1, player.get("max_hp", 80))
            hp_ratio = current_hp / max_hp
            print(f"🏕️ [Rest Site] HP: {current_hp}/{max_hp} ({hp_ratio:.0%})")
        
        prefer_rest = hp_ratio < 0.60
        rest_keywords = ["休憩", "休む", "rest", "回復", "heal", "sleep"]
        upgrade_keywords = ["アップグレード", "upgrade", "強化", "鍛冶", "smith"]
        
        rest_coord = None
        upgrade_coord = None
        
        for w_data in words:
            txt = w_data['text'].lower().replace(" ", "")
            cx = w_data['x'] + w_data['w'] // 2
            cy = w_data['y'] + w_data['h'] // 2
            if any(kw in txt for kw in rest_keywords): rest_coord = (cx, cy)
            if any(kw in txt for kw in upgrade_keywords): upgrade_coord = (cx, cy)
        
        target_coord = rest_coord if (prefer_rest and rest_coord) else (upgrade_coord if upgrade_coord else rest_coord)
        if not target_coord:
            target_coord = (int(w * 0.50), int(h * 0.55))
        
        print(f"🏕️ [Rest Site] Clicking campfire option at {target_coord}")
        self.body.confirm_and_push(target_coord, "Rest Site Choice", self.eye)
        time.sleep(0.5)

    def handle_main_menu(self, frame, driver_hwnd):
        words = self.eye.get_all_text_coords(frame)
        w, h = self.eye.window_size
        target_coord = None
        full_text = "".join(w['text'].lower() for w in words).replace(" ", "").replace("　", "")
        
        # Check if we are in the single player submenu
        is_submenu = any(kw in full_text for kw in ["通常", "標準", "本日の挑戦", "デイリー", "カスタム", "standard", "daily", "custom"])
        
        if is_submenu:
            print("👁️ [Submenu] Submenu detected. Looking for 'Standard' button...")
            sub_keywords = ["通常", "標準", "standard", "normal", "スタンダード"]
            for w_data in words:
                text_clean = w_data['text'].lower().replace(" ", "").replace("　", "")
                if any(kw in text_clean for kw in sub_keywords) and not any(ex in text_clean for ex in ["開始", "embark", "出発"]):
                    # If OCR grouped standard, daily, custom together, click standard (left-most third)
                    if "カスタム" in text_clean and ("標準" in text_clean or "standard" in text_clean or "通常" in text_clean):
                        target_coord = (w_data['x'] + w_data['w']//6, w_data['y'] + w_data['h']//2)
                    else:
                        target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                    break
            if not target_coord:
                target_coord = utils.get_coord("menu", "standard_mode", (0.30, 0.52), w, h)
        else:
            # Check for Continue button
            for w_data in words:
                text_clean = w_data['text'].lower().replace(" ", "")
                if any(kw in text_clean for kw in ["続ける", "continue"]) and not any(ex in text_clean for ex in ["保存", "設定"]):
                    target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                    break
            
            if not target_coord:
                # Play button keywords
                for w_data in words:
                    text_clean = w_data['text'].lower().replace(" ", "")
                    if any(kw in text_clean for kw in ["プレイ", "play", "single", "シングル"]):
                        target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                        break
            
            if not target_coord:
                target_coord = utils.get_coord("menu", "play_button", (0.405, 0.64), w, h)
            
        self.body.confirm_and_push(target_coord, "Main Menu Button", self.eye)
        time.sleep(0.5)

    def handle_defeat(self, frame):
        words = self.eye.get_all_text_coords(frame)
        w, h = self.eye.window_size
        target_coord = None
        for w_data in words:
            txt = w_data['text'].lower()
            if any(kw in txt for kw in ["return", "main", "quit", "戻る", "終了"]):
                target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                break
        if not target_coord:
            target_coord = utils.get_coord("menu", "return_to_menu", (0.50, 0.88), w, h)
        self.body.click_and_verify(target_coord, "Return to Menu", max_shifts=4)
        time.sleep(0.5)

    def handle_character_select(self, frame):
        print("👤 [Character Select] キャラクター選択画面を解析します...")
        words = self.eye.get_all_text_coords(frame)
        w, h = self.eye.window_size
        
        # Log all detected text in character select for debugging
        full_text = " ".join(w['text'] for w in words)
        print(f"👁️ [OCR] Detected Text: {full_text}")

        # 1. Select character
        # STS2 names: Ironclad (アイアンクラッド), Silent (サイレント), Regent (リージェント), Necrobinder (ネクロバインダー)
        char_keywords = ["アイアン", "サイレント", "ネクロ", "リージェント", "リージエント", "リジント", "レジェント", "ironclad", "silent", "necro", "regent"]
        selected = False
        for w_data in words:
            text_clean = w_data['text'].lower().replace(" ", "").replace("　", "")
            if any(kw in text_clean for kw in char_keywords) and len(text_clean) < 20:
                char_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                # Ensure we are clicking in the upper half where character portraits/cards are
                if char_coord[1] / h < 0.6:
                    print(f"👤 [Character Select] Found potential character: '{w_data['text']}' at {char_coord}")
                    self.body.click_position(char_coord, f"Character Selection ({w_data['text']})")
                    selected = True
                    time.sleep(1.0)
                    break
        
        if not selected:
            # Try to click the character card from COORDINATES if OCR fails
            char_coord = utils.get_coord("character_select", "ironclad_card", (0.35, 0.35), w, h)
            print(f"👤 [Character Select] OCR failed to find character names. Using fallback coordinate {char_coord}...")
            self.body.click_position(char_coord, "Character Fallback")
            time.sleep(1.0)

        # Refresh frame and words
        frame = self.eye.grab_screen()
        words = self.eye.get_all_text_coords(frame)

        # 2. Handle Ascension Adjustment
        target_asc = 0
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves", "settings.json")
        if os.path.exists(settings_path):
            try:
                import json
                with open(settings_path, "r", encoding="utf-8") as sf:
                    settings = json.load(sf)
                    target_asc = settings.get("target_ascension", 0)
            except Exception as se:
                print(f"⚠️ [Settings] Error loading settings.json: {se}")
        
        print(f"🎯 [Ascension] Target Ascension Level: {target_asc}")

        # Detect arrows
        arrows = self.eye.detect_ascension_arrows(frame)
        left_arrow = arrows.get('left')
        if not left_arrow:
            left_arrow = utils.get_coord("character_select", "ascension_left_arrow", (0.32, 0.715), w, h)
        right_arrow = arrows.get('right')
        if not right_arrow:
            right_arrow = utils.get_coord("character_select", "ascension_right_arrow", (0.65, 0.715), w, h)

        if target_asc == 0:
            # Safest approach for level 0: click left arrow 20 times to force it to minimum
            print("🔽 [Ascension] Resetting Ascension to 0 (clicking left arrow 20 times)...")
            for i in range(20):
                self.body.click_position(left_arrow, f"Reset Ascension to 0 (Click {i+1})")
                time.sleep(0.12)
        else:
            # Attempt to parse current level for dynamic adjustment
            full_text_clean = "".join(wd['text'].lower() for wd in words).replace(" ", "").replace("　", "")
            current_asc = None
            match = re.search(r'(?:アセンション|アセンシヨン|ascension|レベル|level)[^\d]*?(\d+)', full_text_clean)
            if match:
                try:
                    current_asc = int(match.group(1))
                except:
                    pass
            
            # If not detected, check if "ascension" is present but no number (could be level 1 or off)
            if current_asc is None and any(kw in full_text_clean for kw in ["アセンション", "アセンシヨン", "ascension"]):
                current_asc = 1
                
            if current_asc is not None:
                print(f"🔼 [Ascension] Detected current level: {current_asc}, target: {target_asc}")
                diff = current_asc - target_asc
                if diff > 0:
                    print(f"🔽 [Ascension] Lowering level by {diff} steps...")
                    for i in range(min(20, diff)):
                        self.body.click_position(left_arrow, f"Lower Ascension Click {i+1}")
                        time.sleep(0.15)
                elif diff < 0:
                    print(f"▲ [Ascension] Raising level by {abs(diff)} steps...")
                    for i in range(min(20, abs(diff))):
                        self.body.click_position(right_arrow, f"Raise Ascension Click {i+1}")
                        time.sleep(0.15)
            else:
                # OCR failed to detect level. Click left 20 times as safest fallback to at least not start on high level
                print("⚠️ [Ascension] Could not detect current Ascension level. Defaulting to 20 left clicks to ensure 0...")
                for i in range(20):
                    self.body.click_position(left_arrow, f"Ascension Fallback Reset (Click {i+1})")
                    time.sleep(0.12)

        # 3. Click Proceed / Embark
        target_coord = None
        keywords = ["embark", "proceed", "go", "エンバーク", "出発", "開始"]
        for w_data in words:
            text_lower = w_data['text'].lower()
            if any(kw in text_lower for kw in keywords) and "さあ挑戦" not in text_lower and len(w_data['text'].strip()) < 10:
                target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                break
        
        if not target_coord:
            checkmark_coord = self.eye.detect_teal_checkmark(frame)
            if checkmark_coord:
                target_coord = checkmark_coord
            else:
                target_coord = utils.get_coord("character_select", "embark_button", (0.955, 0.70), w, h)
                
        print(f"🚀 [Character Select] Embarking at {target_coord}")
        self.body.confirm_and_push(target_coord, "Embark Button", self.eye)
        time.sleep(0.5)
