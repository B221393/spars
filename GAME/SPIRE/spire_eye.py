import os
import sys
import time
import re
import numpy as np
import requests
import base64
import json

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Try importing CV libraries, fallback to mock if unavailable
try:
    import cv2
    import pyautogui
    HAS_CV = True
except ImportError:
    HAS_CV = False

class SpireEye:
    def __init__(self, driver):
        self.driver = driver
        self.last_state = "UNKNOWN"
        self.calibration_offset = (0, 0)
        self.window_size = (1280, 720) # standard window fallback
        self.last_frame_small = None
        self.last_llm_state = "UNKNOWN"
        self.static_cycles_count = 0
        self.ocr_process = None
        self.last_ocr_words = []
        self.last_ocr_frame_small = None
        self.last_ocr_time = 0.0
        self.capture_size = None

    def to_logical(self, coord):
        """Converts coordinate from physical capture size to logical client window size."""
        if not hasattr(self, 'capture_size') or self.capture_size is None:
            return coord
        cap_w, cap_h = self.capture_size
        client_w, client_h = self.window_size
        if cap_w <= 0 or cap_h <= 0 or client_w <= 0 or client_h <= 0:
            return coord
        x, y = coord
        logical_x = int(x * client_w / cap_w)
        logical_y = int(y * client_h / cap_h)
        return (logical_x, logical_y)

    def __del__(self):
        if hasattr(self, 'ocr_process') and self.ocr_process is not None:
            try:
                self.ocr_process.stdin.write("EXIT\n")
                self.ocr_process.stdin.flush()
                self.ocr_process.wait(timeout=1.0)
            except:
                try: self.ocr_process.kill()
                except: pass
        
    def log(self, message):
        print(f"👁️ [Eye] {message}")

    def update_window_bounds(self):
        """Binds to target window and updates offset/size."""
        if self.driver.check_connection():
            try:
                import win32gui
                rect = win32gui.GetClientRect(self.driver.hwnd)
                x, y = win32gui.ClientToScreen(self.driver.hwnd, (0, 0))
                self.calibration_offset = (x, y)
                self.window_size = (rect[2], rect[3])
                return True
            except Exception as e:
                self.log(f"Failed to get client rect: {e}")
        return False

    def force_focus(self):
        if not self.driver.hwnd:
            return
        import win32gui
        import win32con
        import ctypes
        if win32gui.GetForegroundWindow() != self.driver.hwnd:
            self.log("🔌 Game window lost focus during capture. Restoring focus...")
            try:
                win32gui.ShowWindow(self.driver.hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32gui.SetForegroundWindow(self.driver.hwnd)
                ctypes.windll.user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.6)
            except Exception as e:
                self.log(f"Failed to force focus: {e}")

    def grab_screen(self):
        """Captures the current client window area using the driver's capture method."""
        if not HAS_CV:
            return None
        try:
            self.force_focus()
            self.update_window_bounds()
            pil_img = self.driver.capture()
            if pil_img is None:
                return None
            self.capture_size = pil_img.size
            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            return frame
        except Exception as e:
            self.log(f"Screen grab failed: {e}")
            return None

    def query_llm_text(self, prompt):
        """Generic method to query Gemma4 with text only."""
        try:
            payload = {
                "model": "gemma3:4b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }
            self.log("Querying gemma3:4b with text only...")
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60.0)
            if res.status_code == 200:
                return res.json().get("response", "").strip()
            else:
                self.log(f"Ollama API returned status code {res.status_code}")
        except Exception as e:
            self.log(f"query_llm_text failed: {e}")
        return ""

    def query_llm(self, frame, prompt, resize_to=(256, 144)):
        """Generic method to query Gemma4. Refactored to text-only fallback to avoid CPU vision lag."""
        # Visual query bypass: we convert the frame to OCR text and append it to the prompt.
        try:
            words = self.get_all_text_coords(frame)
            words_text = " | ".join(w['text'] for w in words)
            full_prompt = f"{prompt}\n\nContext text found on screen:\n{words_text}"
            return self.query_llm_text(full_prompt)
        except Exception as e:
            self.log(f"query_llm fallback failed: {e}")
        return ""

    def detect_game_state_via_llm(self, frame):
        """
        Uses gemma4 via Ollama to detect the game state from the screen text labels.
        """
        if frame is None:
            return None

        try:
            words = self.get_all_text_coords(frame)
            words_text = " | ".join(w['text'] for w in words)
            self.log(f"Extracting screen text for state classification: '{words_text[:100]}...'")

            prompt = f"""Based on these text labels found on the game screen, classify the game state:
'{words_text}'

Identify which of the following states the game is in:
- COMBAT: A combat encounter. Cards are displayed at the bottom, enemies are present on the right/middle, and an "End Turn" button is on the right side of the screen.
- REST_SITE: A campfire scene where you choose options like Rest or Smith.
- MAP: A map showing branching path nodes leading upwards.
- REWARD: A reward screen showing selectable cards, relics, or potions.
- MAIN_MENU: The title screen with options like Play, Standard, or menu buttons.
- CHARACTER_SELECT: The screen to choose your character with an "Embark" button on the bottom-right.
- DEFEAT_SCREEN: The defeat/victory summary screen with a "Return" button at the bottom center.
- EVENT: A story event, Neow's bonus, dialogue, shop, or unknown interaction screen with text options to click.
- LOADING: A completely black, near-black, or empty transition loading screen.

You must respond with EXACTLY one of these words and nothing else:
COMBAT, REST_SITE, MAP, REWARD, MAIN_MENU, CHARACTER_SELECT, DEFEAT_SCREEN, EVENT, LOADING

Do not include any explanation, markdown formatting, or punctuation. Output ONLY the state name in uppercase."""

            response_text = self.query_llm_text(prompt).upper()
            self.log(f"gemma4 state response: {response_text}")
            
            valid_states = ["COMBAT", "REST_SITE", "MAP", "REWARD", "MAIN_MENU", "CHARACTER_SELECT", "DEFEAT_SCREEN", "EVENT", "LOADING", "PAUSE_MENU"]
            for state in valid_states:
                if state in response_text:
                    self.last_llm_state = state
                    return state
            self.log(f"gemma4 returned unrecognized state response: {response_text}")
        except Exception as e:
            self.log(f"Gemma 4 state text check failed: {e}")
        return None

    def get_mcp_state(self):
        """Attempts to fetch current game state from STS2_MCP mod server on localhost:15526."""
        import urllib.request
        import json
        try:
            url = "http://localhost:15526/api/v1/singleplayer?format=json"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    self.last_mcp_state = data
                    return data
        except Exception:
            pass
        self.last_mcp_state = None
        return None

    def detect_game_state(self, frame=None):
        """
        Reflexive/Spinal classification of the current screen.
        First uses fast frame difference caching, optimized pixel heuristics, 
        and state transition memory (< 1ms, 0% CPU).
        Only falls back to OCR on transitions, and local Gemma4 for event dialogues.
        """
        # Try fetching state from STS2_MCP server first (fastest and 100% accurate)
        mcp_data = self.get_mcp_state()
        if mcp_data and "state_type" in mcp_data:
            state_type = mcp_data["state_type"].lower()
            
            mapped_state = None
            if state_type == "menu":
                menu_screen = mcp_data.get("menu_screen", "").lower()
                if "char" in menu_screen:
                    mapped_state = "CHARACTER_SELECT"
                else:
                    mapped_state = "MAIN_MENU"
            elif state_type == "combat":
                mapped_state = "COMBAT"
            elif state_type == "map":
                mapped_state = "MAP"
                if frame is not None:
                    ocr_words = self.get_all_text_coords(frame)
                    full_txt = "".join(w['text'].lower() for w in ocr_words).replace(" ", "").replace("　", "")
                    if any(kw in full_txt for kw in ["ネオー", "neow", "復活の母", "るつぼ", "アーキテクト", "最大hp", "ゴールド", "獲得", "カードを", "レリック", "呪い", "ダメージ", "失う"]):
                        mapped_state = "EVENT"
            elif state_type in ["event", "dialogue"]:
                mapped_state = "EVENT"
            elif state_type == "shop":
                mapped_state = "SHOP"
            elif state_type in ["reward", "rewards"]:
                mapped_state = "REWARD"
            elif state_type in ["campfire", "rest_site", "rest"]:
                mapped_state = "REST_SITE"
            elif state_type in ["game_over", "defeat"]:
                mapped_state = "DEFEAT_SCREEN"
            elif state_type == "pause":
                mapped_state = "PAUSE_MENU"
                
            if mapped_state:
                self.log(f"🔗 [MCP Mod] Detected state via API: {mapped_state} (raw: {state_type})")
                self.last_llm_state = mapped_state
                return mapped_state

        if not HAS_CV or frame is None:
            return "COMBAT"

        # 1. Frame difference check to avoid any processing on static frames
        small_frame = cv2.resize(frame, (64, 36))
        if self.last_frame_small is not None:
            diff = cv2.absdiff(small_frame, self.last_frame_small)
            mean_diff = np.mean(diff)
            if mean_diff < 2.0:  # screen is static, reuse last detected state
                return self.last_llm_state
        self.last_frame_small = small_frame

        # 2. Fast Loading screen check (Heuristics)
        h, w, _ = frame.shape
        overall_mean = np.mean(frame)
        if overall_mean < 15:
            self.last_llm_state = "LOADING"
            return "LOADING"
            
        # 3. Run Fast OCR-based state detection
        self.log("Running fast OCR-based state detection...")
        words = self.get_all_text_coords(frame)
        full_text = " ".join(w['text'].lower() for w in words)
        full_text_clean = full_text.replace(" ", "").replace("　", "")
        
        detected_state = "UNKNOWN"
        # Check text anchors for instant state matching
        if any(kw in full_text_clean for kw in ["再開", "保存して終了", "一時停止", "時停止"]):
            detected_state = "PAUSE_MENU"
        elif any(kw in full_text_clean for kw in ["さあ挑戦を始めよう", "挑戦を始めよう", "ディリチャレンジ", "デイリーチャレンジ", "キャラクター選択", "characterselect", "embark", "挑戦を開始", "出発"]):
            detected_state = "CHARACTER_SELECT"
        elif any(name in full_text_clean for name in ["アイアンクラッド", "アイアンクラド", "サイレント", "ネクロバインダー", "ネクロ", "リージェント", "リージエント", "リジント", "レジェント", "ironclad", "silent", "necrobinder", "regent", "アイアン"]):
            if not any(kw in full_text_clean for kw in ["ターン終了", "endturn", "エンドターン", "ポーション", "potion"]):
                detected_state = "CHARACTER_SELECT"
        elif any(kw in full_text_clean for kw in ["シングル", "singleplayer", "マルチプレイ", "multiplayer", "通常", "本日の挑戦", "カスタム", "standard", "dailychallenge", "custom", "年代記", "実績一覧", "設定", "終了", "megacrit", "slaythespire", "spire"]):
            detected_state = "MAIN_MENU"
        elif any(kw in full_text_clean for kw in ["商人", "購入", "売却", "ショップ", "shop", "merchant", "buy", "purge", "remove", "削除"]):
            # Confirm it's not just a map node or event mention by checking for price-like digits
            if any(re.search(r'\d+', w['text']) for w in words if 0.4 < (w['y']/h) < 0.9):
                detected_state = "SHOP"
            else:
                detected_state = "EVENT"
        elif any(kw in full_text_clean for kw in ["ターン終了", "endturn", "エンドターン"]):
            detected_state = "COMBAT"
        elif any(kw in full_text_clean for kw in ["休む", "鍛冶", "rest", "smith"]):
            detected_state = "REST_SITE"
        elif any(kw in full_text_clean for kw in ["ネオー", "neow", "アーキテクト", "復活の母", "復ラの母", "轟音", "万華鏡", "るつぼ"]):
            detected_state = "EVENT"
        elif any(kw in full_text_clean for kw in ["マップ", "凡例", "map", "legend"]):
            detected_state = "MAP"
        elif any(kw in full_text_clean for kw in ["カードを選択", "報酬", "選択したカードを追加", "cardreward", "take"]):
            detected_state = "REWARD"
        elif any(kw in full_text_clean for kw in ["メインメニューに戻る", "諦める", "defeat", "victory", "returntomain", "敗北", "死亡", "ゲームオーバー"]):
            detected_state = "DEFEAT_SCREEN"
        elif any(kw in full_text_clean for kw in ["進む", "続ける", "proceed", "continue"]):
            detected_state = "EVENT"

        if detected_state != "UNKNOWN":
            self.last_llm_state = detected_state
            return detected_state

        # State transition memory: if we were in COMBAT, and OCR did not detect anything else,
        # we are highly likely to still be in COMBAT (e.g. enemy turn or card playing animations)
        if detected_state == "UNKNOWN" and self.last_llm_state == "COMBAT":
            detected_state = "COMBAT"

        if detected_state != "UNKNOWN":
            self.last_llm_state = detected_state
            return detected_state


        # 5. As a last resort, query the local Gemma 4 model
        self.log("Heuristics and OCR inconclusive. Querying local Gemma 4 model (CPU load active)...")
        llm_state = self.detect_game_state_via_llm(frame)
        if llm_state:
            self.last_llm_state = llm_state
            return llm_state
            
        return "UNKNOWN"

    def locate_combat_elements(self, frame, cards_played=0):
        """
        Extracts position coordinates for Hand Cards, Enemies, and End Turn Button.
        Uses OCR text positions at the bottom area to track cards dynamically.
        Falls back to centered geometric mapping based on cards played if OCR is blank.
        """
        elements = {
            "cards": [],
            "enemies": [],
            "end_turn_btn": None
        }
        
        if frame is None:
            # Mock combat positions for safety/fallback simulation
            elements["end_turn_btn"] = (1050, 400)
            elements["cards"] = [(400, 650), (550, 650), (700, 650), (850, 650)]
            elements["enemies"] = [(950, 280), (1100, 280)]
            return elements

        h, w, _ = frame.shape
        
        # End Turn button coordinate
        elements["end_turn_btn"] = (int(w * 0.85), int(h * 0.56))
        
        # Detect Enemies dynamically via red HP bars in the right half of screen
        # HP bars are bright red (R>150, G<80, B<80) in the right portion (x > 50%)
        # Limit search to middle height (Y: 25% to 75%) to avoid close buttons/UI title bars
        y_start = int(h * 0.25)
        y_end = int(h * 0.75)
        right_half = frame[y_start:y_end, w//2:, :]
        red_mask = (right_half[:, :, 2] > 150) & (right_half[:, :, 1] < 80) & (right_half[:, :, 0] < 80)
        
        detected_enemies = []
        if np.sum(red_mask) > 30:
            # Find red pixel clusters (enemy HP bars)
            y_indices, x_indices = np.where(red_mask)
            x_indices = x_indices + w // 2  # offset back to full frame coords
            y_indices = y_indices + y_start  # offset back to full frame coords
            
            # Cluster by X position to separate multiple enemies
            if len(x_indices) > 0:
                sorted_x = np.sort(x_indices)
                clusters = []
                current_cluster_x = [sorted_x[0]]
                current_cluster_y = [y_indices[np.where(x_indices == sorted_x[0])[0][0]]]
                
                for i in range(1, len(sorted_x)):
                    if sorted_x[i] - sorted_x[i-1] < w * 0.08:
                        current_cluster_x.append(sorted_x[i])
                        orig_idx = np.where(x_indices == sorted_x[i])[0]
                        if len(orig_idx) > 0:
                            current_cluster_y.append(y_indices[orig_idx[0]])
                    else:
                        clusters.append((current_cluster_x, current_cluster_y))
                        current_cluster_x = [sorted_x[i]]
                        orig_idx = np.where(x_indices == sorted_x[i])[0]
                        current_cluster_y = [y_indices[orig_idx[0]] if len(orig_idx) > 0 else 0]
                clusters.append((current_cluster_x, current_cluster_y))
                
                # Filter: only keep clusters with enough pixels (real HP bars)
                for cx_list, cy_list in clusters:
                    if len(cx_list) > 15:
                        enemy_x = int(np.mean(cx_list))
                        enemy_y = int(np.mean(cy_list))
                        # ドロップ先はHPバーの少し上（敵本体の位置）
                        drop_y = max(0, enemy_y - int(h * 0.05))
                        detected_enemies.append((enemy_x, drop_y))
        
        # Player HP bar filtering: remove any detected "enemy" in the left 40% (that's the player)
        detected_enemies = [(ex, ey) for ex, ey in detected_enemies if ex > w * 0.5]
        
        if detected_enemies:
            elements["enemies"] = detected_enemies
            print(f"🎯 [Eye] 敵{len(detected_enemies)}体検出: {detected_enemies}")
        else:
            # Fallback: single enemy at center-right
            elements["enemies"] = [(int(w * 0.72), int(h * 0.40))]

        # 1. OCR-based hand card detection
        words = self.get_all_text_coords(frame)
        card_words = []
        for w_data in words:
            cx = w_data['x'] + w_data['w'] // 2
            cy = w_data['y'] + w_data['h'] // 2
            x_pct = cx / w
            y_pct = cy / h
            # Card region filtering (y_pct between 0.72 and 0.95, x_pct between 0.15 and 0.85)
            if 0.72 <= y_pct <= 0.95 and 0.15 <= x_pct <= 0.85:
                text = w_data['text'].strip()
                # Exclude energy indicators (like '2/3', '0/3') and end turn button texts
                if text and not text.isdigit() and "ターン" not in text and "終了" not in text and "end" not in text and "/" not in text:
                    card_words.append(w_data)
                    
        # Group words that are close horizontally to identify individual cards
        card_words = sorted(card_words, key=lambda cw: cw['x'])
        
        detected_coords = []
        if card_words:
            current_group = [card_words[0]]
            for cw in card_words[1:]:
                prev_cw = current_group[-1]
                avg_h = sum(item['h'] for item in current_group) / len(current_group)
                gap_threshold = max(20, avg_h * 1.8)
                avg_y = sum(item['y'] for item in current_group) / len(current_group)
                
                # Check horizontal gap and Y coordinate proximity
                if (cw['x'] - (prev_cw['x'] + prev_cw['w'])) < gap_threshold and abs(cw['y'] - avg_y) < avg_h * 1.5:
                    current_group.append(cw)
                else:
                    min_x = min(item['x'] for item in current_group)
                    max_x = max(item['x'] + item['w'] for item in current_group)
                    center_x = (min_x + max_x) // 2
                    avg_y = sum(item['y'] + item['h']//2 for item in current_group) // len(current_group)
                    avg_h = sum(item['h'] for item in current_group) // len(current_group)
                    detected_coords.append((center_x, avg_y, avg_h))
                    current_group = [cw]
            min_x = min(item['x'] for item in current_group)
            max_x = max(item['x'] + item['w'] for item in current_group)
            center_x = (min_x + max_x) // 2
            avg_y = sum(item['y'] + item['h']//2 for item in current_group) // len(current_group)
            avg_h = sum(item['h'] for item in current_group) // len(current_group)
            detected_coords.append((center_x, avg_y, avg_h))
            
        # 2. Geometric fallback if OCR detected 0 cards (point to card title area)
        if not detected_coords:
            hand_size = max(1, 5 - cards_played)
            spacing = int(w * 0.08)
            center_y = int(h * 0.78) # Points directly to title area
            fallback_h = int(h * 0.025)
            for i in range(hand_size):
                offset = (i - (hand_size - 1) / 2) * spacing
                center_x = int(w * 0.5) + int(offset)
                detected_coords.append((center_x, center_y, fallback_h))
                
        elements["cards"] = detected_coords
        return elements

    def generate_pseudo_html(self, frame):
        """
        Parses OCR words and builds a structured text/pseudo-HTML representation of the screen.
        """
        if frame is None:
            return "<screen></screen>"
            
        h, w, _ = frame.shape
        words = self.get_all_text_coords(frame)
        
        # Build DOM elements
        html_lines = []
        html_lines.append(f'<screen width="{w}" height="{h}">')
        
        for i, w_data in enumerate(words):
            x1 = w_data['x']
            y1 = w_data['y']
            x2 = w_data['x'] + w_data['w']
            y2 = w_data['y'] + w_data['h']
            
            left_pct = round(x1 / w, 3)
            top_pct = round(y1 / h, 3)
            right_pct = round(x2 / w, 3)
            bottom_pct = round(y2 / h, 3)
            
            text = w_data['text'].strip()
            if not text:
                continue
                
            # Classify: width > height * 2 is likely interactive button/option line
            if w_data['w'] > w_data['h'] * 2:
                html_lines.append(f'  <button id="{i}" text="{text}" left_pct="{left_pct}" top_pct="{top_pct}" right_pct="{right_pct}" bottom_pct="{bottom_pct}" />')
            else:
                html_lines.append(f'  <text content="{text}" left_pct="{left_pct}" top_pct="{top_pct}" right_pct="{right_pct}" bottom_pct="{bottom_pct}" />')
                
        html_lines.append('</screen>')
        return "\n".join(html_lines)

    def crop_card_at(self, frame, card_coord):
        if frame is None:
            return None
        h, w, _ = frame.shape
        if len(card_coord) == 3:
            cx, cy, ch = card_coord
            h_scale = max(15, min(40, ch))
            y_start = max(0, cy - int(h_scale * 1.5))
            y_end = min(h, cy + int(h_scale * 2.0))
            x_start = max(0, cx - int(h_scale * 4.5))
            x_end = min(w, cx + int(h_scale * 4.5))
        else:
            cx, cy = card_coord[:2]
            y_start = max(0, cy - int(h * 0.15))
            y_end = min(h, cy - int(h * 0.05))
            x_start = max(0, cx - int(w * 0.04))
            x_end = min(w, cx + int(w * 0.04))
        return frame[y_start:y_end, x_start:x_end]

    def visualize_sight(self, frame, words, elements, state="UNKNOWN"):
        """
        Generates an annotated screenshot with bounding boxes and labels for all detected elements.
        Saves to assets/debug_sight.png and returns the path.
        """
        if frame is None: return None
        vis_frame = frame.copy()
        h, w, _ = frame.shape
        
        # 1. Draw all OCR words in blue
        for wd in words:
            x, y, ww, hh = wd['x'], wd['y'], wd['w'], wd['h']
            cv2.rectangle(vis_frame, (x, y), (x + ww, y + hh), (255, 100, 0), 1)
            # Draw text above (small)
            txt = wd['text']
            if len(txt) > 10: txt = txt[:8] + ".."
            cv2.putText(vis_frame, txt, (x, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 150, 0), 1)

        # 2. Draw enemies in red
        for ex, ey in elements.get("enemies", []):
            cv2.circle(vis_frame, (ex, ey), 30, (0, 0, 255), 3)
            cv2.putText(vis_frame, "ENEMY", (ex - 20, ey - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # 3. Draw hand cards in green
        for card_coord in elements.get("cards", []):
            cx, cy = card_coord[:2]
            cv2.rectangle(vis_frame, (cx - 40, cy - 60), (cx + 40, cy + 60), (0, 255, 0), 2)
            cv2.putText(vis_frame, "CARD", (cx - 20, cy - 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 4. Draw interactive buttons/nodes (Checkmarks, etc.) in yellow
        checkmark = self.detect_teal_checkmark(frame)
        if checkmark:
            cv2.circle(vis_frame, checkmark, 25, (0, 255, 255), 3)
            cv2.putText(vis_frame, "CONFIRM", (checkmark[0] - 40, checkmark[1] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 5. Header info
        cv2.rectangle(vis_frame, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.putText(vis_frame, f"STATE: {state} | TIME: {time.strftime('%H:%M:%S')} | DPI: {self.driver.hwnd is not None}", 
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        os.makedirs(assets_dir, exist_ok=True)
        save_path = os.path.join(assets_dir, "debug_sight.png")
        cv2.imwrite(save_path, vis_frame)
        
        # Save a timestamped copy for historical analysis if UNKNOWN or failure
        if state == "UNKNOWN":
            history_path = os.path.join(assets_dir, f"unknown_sight_{time.strftime('%Y%m%d_%H%M%S')}.png")
            cv2.imwrite(history_path, vis_frame)
            
        return save_path

    def detect_ascension_arrows(self, frame):
        """
        Detects left and right arrows for Ascension adjustment on the character selection screen.
        Returns a dict with 'left' and 'right' coordinates if found.
        """
        if frame is None: return {}
        h, w, _ = frame.shape
        # Ascension area is usually in the bottom-middle region: Y: 75-90%, X: 30-70%
        roi_y1, roi_y2 = int(h * 0.75), int(h * 0.95)
        roi_x1, roi_x2 = int(w * 0.30), int(w * 0.70)
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Use template matching or contour detection for arrow shapes '<' and '>'
        # For now, let's use OCR words to find 'Ascension' or 'アセンション' and look nearby
        arrows = {}
        words = self.get_all_text_coords(roi)
        
        asc_words = [wd for wd in words if any(kw in wd['text'].lower() for kw in ["ascension", "アセンション", "アセンシヨン", "レベル"])]
        if asc_words:
            # Sort by X to find the label
            asc_words.sort(key=lambda x: x['x'])
            label_wd = asc_words[0]
            # Estimate arrow positions relative to the label
            # Left arrow is usually to the left of the number, right arrow to the right
            # But let's look for small square-ish buttons nearby
            for wd in words:
                if len(wd['text']) <= 2 and (wd['text'] in ["<", ">", "«", "»", "く", "〉"]):
                    cx = roi_x1 + wd['x'] + wd['w'] // 2
                    cy = roi_y1 + wd['y'] + wd['h'] // 2
                    if wd['text'] in ["<", "«", "く"]:
                        arrows['left'] = (cx, cy)
                    else:
                        arrows['right'] = (cx, cy)
            
            # Fallback based on relative positioning if OCR fails to read arrows but finds label
            if not arrows.get('left'):
                arrows['left'] = (roi_x1 + label_wd['x'] - 40, roi_y1 + label_wd['y'] + label_wd['h']//2)
            if not arrows.get('right'):
                arrows['right'] = (roi_x1 + label_wd['x'] + label_wd['w'] + 60, roi_y1 + label_wd['y'] + label_wd['h']//2)
                
        return arrows

    def get_reward_card_coords(self):
        w, h = self.window_size
        return [
            (int(w * 0.32), int(h * 0.50)),
            (int(w * 0.50), int(h * 0.50)),
            (int(w * 0.68), int(h * 0.50))
        ]

    def get_potion_coords(self, frame):
        """Detects potion slots in the top-left area by scanning for circular icons."""
        if frame is None: return []
        h, w, _ = frame.shape
        # Potions are in top-left: X < 30%, Y < 15%
        roi_h = int(h * 0.15)
        roi_w = int(w * 0.30)
        roi = frame[0:roi_h, 0:roi_w]
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Use Hough Circles or simple contour detection for potion circles
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                                   param1=50, param2=30, minRadius=10, maxRadius=40)
        
        potion_points = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                potion_points.append((x, y))
        
        # Sort by X position
        potion_points = sorted(potion_points, key=lambda p: p[0])
        return potion_points

    def detect_teal_checkmark(self, frame):
        """
        Detects if the teal confirm checkmark button is visible in the bottom-right region.
        Returns the (x, y) coordinates if found, else None.
        """
        if frame is None:
            return None
        h, w, _ = frame.shape
        # The checkmark button is always in the bottom-right region
        cx_start = int(w * 0.9)
        cy_start = int(h * 0.6)
        cy_end = int(h * 0.9) # Exclude Windows taskbar at the bottom
        
        region = frame[cy_start:cy_end, cx_start:w]
        if region.size == 0:
            return None
            
        # Teal color criteria (relative check): B and G must be significantly higher than R, with minimum brightness
        mask = (region[:, :, 0] > 100) & (region[:, :, 1] > 100) & (region[:, :, 0] > region[:, :, 2] + 45) & (region[:, :, 1] > region[:, :, 2] + 45)
        
        y_indices, x_indices = np.where(mask)
        if len(x_indices) > 50:
            center_x = cx_start + int(np.mean(x_indices))
            center_y = cy_start + int(np.mean(y_indices))
            # Double check to ensure coordinates are within client size
            if 0 < center_x < w and 0 < center_y < h:
                return (center_x, center_y)
        return None

    def get_player_block_present(self, frame):
        if frame is None:
            return False
        h, w, _ = frame.shape
        bx_start = int(w * 0.15)
        bx_end = int(w * 0.25)
        by_start = int(h * 0.85)
        by_end = int(h * 0.92)
        
        region = frame[by_start:by_end, bx_start:bx_end]
        if region.size == 0:
            return False
        blue_mask = (region[:, :, 0] > 180) & (region[:, :, 2] < 120)
        return bool(np.any(blue_mask))

    def get_enemy_hp_percentage(self, frame, enemy_coord):
        if frame is None:
            return 0.0
        h, w, _ = frame.shape
        ex, ey = enemy_coord
        hx_start = max(0, int(ex - w * 0.04))
        hx_end = min(w, int(ex + w * 0.04))
        hy_start = max(0, int(ey + h * 0.08))
        hy_end = min(h, int(ey + h * 0.12))
        
        region = frame[hy_start:hy_end, hx_start:hx_end]
        if region.size == 0:
            return 0.0
        red_mask = (region[:, :, 2] > 150) & (region[:, :, 0] < 100) & (region[:, :, 1] < 100)
        return float(np.sum(red_mask)) / region.size

    def get_enemy_attacking(self, frame, enemy_coord):
        if frame is None:
            return False
        h, w, _ = frame.shape
        ex, ey = enemy_coord
        ix_start = max(0, int(ex - w * 0.03))
        ix_end = min(w, int(ex + w * 0.03))
        iy_start = max(0, int(ey - h * 0.12))
        iy_end = min(h, int(ey - h * 0.06))
        
        region = frame[iy_start:iy_end, ix_start:ix_end]
        if region.size == 0:
            return False
        red_mask = (region[:, :, 2] > 180) & (region[:, :, 0] < 120) & (region[:, :, 1] < 120)
        return bool(np.any(red_mask))

    def get_player_hp(self, words):
        """Extracts player HP from OCR words."""
        import re
        screen_w = self.window_size[0]
        for w_data in words:
            cx = w_data['x'] + w_data['w'] // 2
            # Only consider the left 45% of the screen to avoid parsing enemy HP as player HP
            if cx > screen_w * 0.45:
                continue
            text = w_data['text'].strip()
            match = re.search(r'(\d+)/(\d+)', text)
            if match:
                try:
                    curr_hp = int(match.group(1))
                    max_hp = int(match.group(2))
                    if 30 <= max_hp <= 250:
                        return curr_hp, max_hp
                except: pass
        return None

    def get_enemy_hp_from_ocr(self, words, enemy_coord, frame_shape):
        """Finds the HP text (e.g. 15/38 or 24/24) close to the enemy coordinates."""
        import re
        import math
        ex, ey = enemy_coord[:2]
        h, w = frame_shape[:2]
        best_hp = None
        min_dist = 999999.0
        
        for w_data in words:
            text = w_data['text'].strip()
            match = re.search(r'(\d+)\s*/\s*(\d+)', text)
            if match:
                try:
                    curr_hp = int(match.group(1))
                    max_hp = int(match.group(2))
                    
                    cx = w_data['x'] + w_data['w'] // 2
                    cy = w_data['y'] + w_data['h'] // 2
                    dist = math.hypot(cx - ex, cy - ey)
                    
                    if dist < min_dist and dist < w * 0.20:
                        min_dist = dist
                        best_hp = (curr_hp, max_hp)
                except: pass
        return best_hp

    def get_enemy_intent_damage(self, words, enemy_coord, frame_shape):
        """Extracts the attack damage from the enemy's intent (e.g. '10', '5x3') if visible."""
        import re
        import math
        ex, ey = enemy_coord[:2]
        h, w = frame_shape[:2]
        min_dist = 999999.0
        best_dmg = 0
        
        for w_data in words:
            text = w_data['text'].strip()
            # Look for digits or multiplication patterns (e.g., 6, 10, 5x3)
            match = re.search(r'^(\d+)\s*(?:x|X)\s*(\d+)$', text)
            if match:
                try:
                    dmg = int(match.group(1)) * int(match.group(2))
                    cx = w_data['x'] + w_data['w'] // 2
                    cy = w_data['y'] + w_data['h'] // 2
                    dist = math.hypot(cx - ex, cy - ey)
                    # Intent is usually above the enemy center (cy < ey)
                    if dist < w * 0.15 and cy < ey and dist < min_dist:
                        min_dist = dist
                        best_dmg = dmg
                except: pass
            else:
                match_single = re.search(r'^\b(\d+)\b$', text)
                if match_single:
                    try:
                        dmg = int(match_single.group(1))
                        if dmg < 90:
                            cx = w_data['x'] + w_data['w'] // 2
                            cy = w_data['y'] + w_data['h'] // 2
                            dist = math.hypot(cx - ex, cy - ey)
                            if dist < w * 0.15 and cy < ey and dist < min_dist:
                                min_dist = dist
                                best_dmg = dmg
                    except: pass
        return best_dmg

    def get_player_block_from_ocr(self, words):
        """Extracts the player's current block value from OCR words."""
        import re
        screen_w = self.window_size[0]
        
        # Player block icon is near the player HP bar (X: 10% to 25%, Y: 70% to 85%)
        # It is usually a single number, e.g. '5' or '12'
        for w_data in words:
            cx = w_data['x'] + w_data['w'] // 2
            cy = w_data['y'] + w_data['h'] // 2
            x_pct = cx / screen_w
            y_pct = cy / self.window_size[1]
            if 0.10 <= x_pct <= 0.25 and 0.70 <= y_pct <= 0.85:
                text = w_data['text'].strip()
                if text.isdigit():
                    val = int(text)
                    if 0 < val < 999:
                        return val
        return 0

    def detect_map_nodes(self, frame):
        """Detects map node coordinates by looking for dark icons on the light parchment background."""
        if frame is None:
            return []
        h, w, _ = frame.shape
        y_start, y_end = int(h * 0.20), int(h * 0.94)
        x_start, x_end = int(w * 0.20), int(w * 0.80)
        
        region = frame[y_start:y_end, x_start:x_end]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        
        # Slay the Spire map background is parchment (light, e.g. > 150)
        # Nodes are dark icons (e.g. < 90)
        _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        nodes = []
        for c in contours:
            area = cv2.contourArea(c)
            min_area = (h * w) * 0.0001
            max_area = (h * w) * 0.002
            if min_area <= area <= max_area:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"]) + x_start
                    cy = int(M["m01"] / M["m00"]) + y_start
                    nodes.append((cx, cy))
                    
        # Sort nodes from bottom to top (Y descending)
        nodes = sorted(nodes, key=lambda n: n[1], reverse=True)
        return nodes

    def get_player_statuses(self, words, screen_w, screen_h):
        """Finds status effects on the player (Vulnerable, Weak, Poison, Frail, etc.)."""
        import re
        statuses = {
            "vulnerable": False,
            "weak": False,
            "frail": False,
            "poison": 0
        }
        # Player is typically on the left side of the screen (X: 10% to 45%, Y: 40% to 80%)
        for w_data in words:
            cx = w_data['x'] + w_data['w'] // 2
            cy = w_data['y'] + w_data['h'] // 2
            x_pct = cx / screen_w
            y_pct = cy / screen_h
            if 0.10 <= x_pct <= 0.45 and 0.40 <= y_pct <= 0.85:
                text = w_data['text'].lower()
                if any(kw in text for kw in ["vulnerable", "脆弱", "脆弱化", "弱体", "弱体化"]):
                    statuses["vulnerable"] = True
                elif any(kw in text for kw in ["weak", "脱力", "脱力化"]):
                    statuses["weak"] = True
                elif any(kw in text for kw in ["frail", "脆い", "脆さ"]):
                    statuses["frail"] = True
                elif any(kw in text for kw in ["poison", "毒"]):
                    statuses["poison"] = 1
                    num_match = re.search(r'(\d+)', text)
                    if num_match:
                        statuses["poison"] = int(num_match.group(1))
        return statuses

    def get_enemy_statuses(self, words, enemy_coord, frame_shape):
        """Finds status effects (Vulnerable, Weak, Poison, Frail) near the enemy coordinate."""
        import re
        import math
        ex, ey = enemy_coord[:2]
        h, w = frame_shape[:2]
        statuses = {
            "vulnerable": False,
            "weak": False,
            "frail": False,
            "poison": 0
        }
        
        for w_data in words:
            text = w_data['text'].lower()
            cx = w_data['x'] + w_data['w'] // 2
            cy = w_data['y'] + w_data['h'] // 2
            dist = math.hypot(cx - ex, cy - ey)
            
            # Status indicators are directly below the HP bar, usually within 15% screen height/width
            if dist < w * 0.15:
                if any(kw in text for kw in ["vulnerable", "脆弱", "脆弱化", "弱体", "弱体化"]):
                    statuses["vulnerable"] = True
                elif any(kw in text for kw in ["weak", "脱力", "脱力化"]):
                    statuses["weak"] = True
                elif any(kw in text for kw in ["frail", "脆い", "脆さ"]):
                    statuses["frail"] = True
                elif any(kw in text for kw in ["poison", "毒"]):
                    statuses["poison"] = 1
                    num_match = re.search(r'(\d+)', text)
                    if num_match:
                        statuses["poison"] = int(num_match.group(1))
        return statuses

    def _start_ocr_service(self):
        if self.ocr_process is not None and self.ocr_process.poll() is None:
            return True
            
        import subprocess
        import os
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ps_script = os.path.join(script_dir, "ocr_service.ps1")
        
        if not os.path.exists(ps_script):
            self.log(f"OCR service script not found at: {ps_script}")
            return False
            
        try:
            self.log("Starting persistent OCR background service...")
            self.ocr_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", ps_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1
            )
            ready_line = self.ocr_process.stdout.readline().strip()
            if ready_line == "READY":
                self.log("Persistent OCR background service is READY.")
                return True
            else:
                self.log(f"OCR service failed to initialize: {ready_line}")
                err_text = self.ocr_process.stderr.read()
                if err_text:
                    self.log(f"OCR service stderr: {err_text}")
                self.ocr_process.kill()
                self.ocr_process = None
        except Exception as e:
            self.log(f"Failed to start persistent OCR service: {e}")
            self.ocr_process = None
        return False

    def perform_ocr(self, cv_image):
        """Runs OCR on the given image and returns the joined text string."""
        words = self.get_all_text_coords(cv_image)
        if not words:
            return ""
        # Sort words primarily by y, then by x to read left-to-right, top-to-bottom
        sorted_words = sorted(words, key=lambda w: (w['y'], w['x']))
        return " ".join(w['text'] for w in sorted_words).strip()

    def get_all_text_coords(self, cv_image):
        """
        WinRT OCRを使用して、画像内のすべてのテキストとその境界ボックス（座標）を取得します。
        水平方向に並んだ単語/文字を自動的に同じ行としてグループ化し、結合したテキストとバウンディングボックスを返します。
        戻り値: [{'text': 'Play', 'x': 100, 'y': 200, 'w': 50, 'h': 20}, ...]
        """
        if not HAS_CV or cv_image is None or cv_image.size == 0:
            return []
            
        import os
        import subprocess
        import json
        import base64
        
        # 1. OCR Caching check
        small_frame = cv2.resize(cv_image, (64, 36))
        
        # Optimize threshold: if the persistent OCR service is unavailable/dead,
        # we relax the cache conditions to avoid freezing on tiny animations.
        is_fallback_mode = (self.ocr_process is None or self.ocr_process.poll() is not None)
        diff_threshold = 2.5 if is_fallback_mode else 1.0
        time_threshold = 3.0 if is_fallback_mode else 1.5
        
        if self.last_ocr_frame_small is not None and self.last_ocr_words:
            # Check visual difference
            diff = cv2.absdiff(small_frame, self.last_ocr_frame_small)
            mean_diff = np.mean(diff)
            # If screen is static and queried within threshold, reuse cache
            if mean_diff < diff_threshold and (time.time() - self.last_ocr_time) < time_threshold:
                return self.last_ocr_words

        saves_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
        os.makedirs(saves_dir, exist_ok=True)
        import random
        temp_path = os.path.join(saves_dir, f"temp_ocr_{os.getpid()}_{random.randint(1000, 9999)}.jpg")
        try:
            cv2.imwrite(temp_path, cv_image, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        except Exception as e:
            self.log(f"OCR write failed: {e}")
            return []
            
        words = []
        used_service = False
        
        # 2. Try utilizing the persistent background OCR service (extremely fast ~7ms)
        if self._start_ocr_service():
            try:
                # Write path to service stdin
                self.ocr_process.stdin.write(temp_path + "\n")
                self.ocr_process.stdin.flush()
                
                # Read response
                response_line = self.ocr_process.stdout.readline().strip()
                if response_line.startswith("OK:"):
                    b64_data = response_line[3:]
                    json_str = base64.b64decode(b64_data).decode('utf-8')
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        words = [data]
                    elif isinstance(data, list):
                        words = data
                    else:
                        words = []
                    used_service = True
                elif response_line.startswith("ERROR:"):
                    err_msg = base64.b64decode(response_line[6:]).decode('utf-8')
                    self.log(f"OCR Service returned error: {err_msg}")
                else:
                    self.log(f"OCR Service returned unexpected response: {response_line}")
                    # Process died or returned invalid output, restart next time
                    self.ocr_process.kill()
                    self.ocr_process = None
            except Exception as e:
                self.log(f"Failed to communicate with OCR service: {e}")
                try: self.ocr_process.kill()
                except: pass
                self.ocr_process = None

        # 3. Fallback to synchronous one-shot PowerShell subprocess if service failed
        if not used_service:
            self.log("Falling back to synchronous one-shot PowerShell OCR execution...")
            temp_path_b64 = base64.b64encode(temp_path.encode('utf-8')).decode('utf-8')
            ps_script = """
            # Load required assemblies
            [System.Reflection.Assembly]::Load("System.Runtime.WindowsRuntime, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089") | Out-Null

            [void][Windows.Media.Ocr.OcrEngine, Windows.Media, ContentType=WindowsRuntime]
            [void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime]
            [void][Windows.Storage.Streams.IRandomAccessStream, Windows.Storage, ContentType=WindowsRuntime]
            [void][Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType=WindowsRuntime]
            [void][Windows.Media.Ocr.OcrResult, Windows.Media, ContentType=WindowsRuntime]

            $asTaskMethods = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
                $_.Name -eq 'AsTask' -and 
                $_.GetParameters().Count -eq 1 -and
                $_.GetParameters()[0].ParameterType.Name.StartsWith('IAsyncOperation`1')
            }
            $asTaskMethod = $asTaskMethods[0]

            function Get-AsyncResult($asyncOp, $resultType) {
                $genericMethod = $global:asTaskMethod.MakeGenericMethod($resultType)
                $task = $genericMethod.Invoke($null, @($asyncOp))
                return $task.Result
            }

            try {
                $tempPathB64 = "{TEMP_PATH_B64}"
                $tempPathBytes = [System.Convert]::FromBase64String($tempPathB64)
                $tempPath = [System.Text.Encoding]::UTF8.GetString($tempPathBytes)
                $dotNetStream = [System.IO.File]::OpenRead($tempPath)
                $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($dotNetStream)
                
                $asyncOp3 = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
                $decoder = Get-AsyncResult $asyncOp3 ([Windows.Graphics.Imaging.BitmapDecoder])
                
                $asyncOp4 = $decoder.GetSoftwareBitmapAsync()
                $bitmap = Get-AsyncResult $asyncOp4 ([Windows.Graphics.Imaging.SoftwareBitmap])
                
                $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
                if ($engine -ne $null) {
                    $asyncOp5 = $engine.RecognizeAsync($bitmap)
                    $result = Get-AsyncResult $asyncOp5 ([Windows.Media.Ocr.OcrResult])
                    
                    $output = @()
                    foreach ($line in $result.Lines) {
                        foreach ($word in $line.Words) {
                            $rect = $word.BoundingRect
                            $output += [PSCustomObject]@{
                                text = $word.Text
                                x = [int]$rect.X
                                y = [int]$rect.Y
                                w = [int]$rect.Width
                                h = [int]$rect.Height
                            }
                        }
                    }
                    $output | ConvertTo-Json -Compress
                }
                $dotNetStream.Close()
            } catch {
                if ($dotNetStream -ne $null) { $dotNetStream.Close() }
                Write-Error $_.Exception.ToString()
            }
            """.replace("{TEMP_PATH_B64}", temp_path_b64)
            
            try:
                res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, encoding="cp932", errors="replace")
                output_str = res.stdout.strip()
                if output_str:
                    data = json.loads(output_str)
                    if isinstance(data, dict):
                        words = [data]
                    elif isinstance(data, list):
                        words = data
            except Exception as e:
                self.log(f"Synchronous OCR execution failed: {e}")
                
        # Clean up temp file
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass

        if not words:
            return []
            
        # グループ化ロジック (同一行にある単語/文字をまとめて1つの要素にする - 水平方向の距離が遠い場合は分割)
        def group_words_into_lines(word_list, y_threshold=15):
            sorted_words = sorted(word_list, key=lambda w: (w['y'], w['x']))
            lines = []
            for w in sorted_words:
                placed = False
                for line in lines:
                    avg_y = sum(item['y'] for item in line) / len(line)
                    if abs(w['y'] - avg_y) < y_threshold:
                        line.append(w)
                        placed = True
                        break
                if not placed:
                    lines.append([w])
                    
            grouped_lines = []
            for line in lines:
                sorted_line = sorted(line, key=lambda w: w['x'])
                
                # 水平方向の距離が一定以上離れている場合は別のサブグループに分割する
                sub_groups = []
                current_sub = [sorted_line[0]]
                for w in sorted_line[1:]:
                    prev_w = current_sub[-1]
                    # 単語の高さの2.5倍、または最低50ピクセルの隙間があれば別グループとする
                    gap_threshold = max(50, prev_w['h'] * 2.5)
                    if (w['x'] - (prev_w['x'] + prev_w['w'])) < gap_threshold:
                        current_sub.append(w)
                    else:
                        sub_groups.append(current_sub)
                        current_sub = [w]
                sub_groups.append(current_sub)
                
                for sub in sub_groups:
                    line_text = " ".join(item['text'] for item in sub)
                    min_x = min(item['x'] for item in sub)
                    max_x = max(item['x'] + item['w'] for item in sub)
                    min_y = min(item['y'] for item in sub)
                    max_y = max(item['y'] + item['h'] for item in sub)
                    grouped_lines.append({
                        'text': line_text,
                        'x': min_x,
                        'y': min_y,
                        'w': max_x - min_x,
                        'h': max_y - min_y
                    })
            return grouped_lines
            
        try:
            grouped_words = group_words_into_lines(words)
            
            h_f, w_f, _ = cv_image.shape
            if w_f >= 600 and h_f >= 350:
                filtered_words = []
                import win32gui
                hud_hwnd = win32gui.FindWindow(None, "HUD Controller")
                game_rect = None
                if self.driver.hwnd:
                    try: game_rect = win32gui.GetWindowRect(self.driver.hwnd)
                    except: pass
                    
                hud_rect = None
                if hud_hwnd:
                    try: hud_rect = win32gui.GetWindowRect(hud_hwnd)
                    except: pass
                    
                if game_rect and hud_rect:
                    gl, gt, gr, gb = game_rect
                    hl, ht, hr, hb = hud_rect
                    
                    x_min = hl - gl
                    y_min = ht - gt
                    x_max = hr - gl
                    y_max = hb - gt
                    
                    for w in grouped_words:
                        cx = w['x'] + w['w'] / 2
                        cy = w['y'] + w['h'] / 2
                        if x_min <= cx <= x_max and y_min <= cy <= y_max:
                            continue
                        filtered_words.append(w)
                    grouped_words = filtered_words
                else:
                    # Keep all words if HUD Controller is not active, allowing bottom-right buttons to be detected
                    filtered_words = grouped_words

            # Update cache
            self.last_ocr_frame_small = small_frame
            self.last_ocr_words = grouped_words
            self.last_ocr_time = time.time()
            return grouped_words
        except Exception as e:
            self.log(f"Line grouping failed: {e}")
            return words

    def dump_silent_error(self, frame, context_msg):
        """
        [常識のシステム: フライトレコーダー]
        エラー（クラッシュ）にはならないが、論理的にスタックした状況の「証拠写真」を保存する。
        """
        if frame is None: return
        try:
            import cv2
            import os
            import time
            error_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves", "silent_errors")
            os.makedirs(error_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            img_path = os.path.join(error_dir, f"{timestamp}_stuck.jpg")
            txt_path = os.path.join(error_dir, f"{timestamp}_log.txt")
            
            cv2.imwrite(img_path, frame)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"[{timestamp}] Context: {context_msg}\n")
            
            self.log(f"📸 [Visual Log] サイレントエラーの証拠写真を回収しました: {img_path}")
        except Exception as e:
            self.log(f"📸 Failed to dump silent error: {e}")

    def diagnose_bottleneck(self, before_frame, after_frame, intended_action):
        """
        [自己診断回路]
        実行前後のUI構造（擬似HTML）を比較し、
        「なぜ変化が起きなかったのか（隠れたエラー）」を推理させる。
        同時に、その証拠写真を物理保存する。
        """
        if before_frame is None or after_frame is None:
            return "診断不可：画像の取得に失敗しています。"

        try:
            import cv2
            import os
            import time
            
            # 2枚の画像を連結して証拠写真としてローカル保存（人間のデバッグ用）
            h, w = before_frame.shape[:2]
            combined = np.zeros((h, w*2, 3), dtype=np.uint8)
            combined[:, :w] = before_frame
            combined[:, w:] = after_frame
            
            error_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves", "silent_errors")
            os.makedirs(error_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            img_path = os.path.join(error_dir, f"{timestamp}_bottleneck.jpg")
            cv2.imwrite(img_path, combined)
            self.log(f"📸 [Visual Log] ボトルネックの証拠写真を回収しました: {img_path}")
            
            # 擬似HTMLの生成
            html_before = self.generate_pseudo_html(before_frame)
            html_after = self.generate_pseudo_html(after_frame)
            
            prompt = f"""Gameplay Action Diagnosis:
I tried to perform the following action in Slay the Spire: {intended_action}
However, the screen did not change (screen difference was negligible, indicating a failed click or blocked action).

Here is the UI structure before the action:
{html_before}

Here is the UI structure after the action:
{html_after}

Look at the elements, text options, button coordinates, and decide:
Why did this action fail to change the screen? (e.g., is there a blocking popup, an overlay, a confirmation check needed, or is the coordinate off?)
Provide a brief, helpful analysis in Japanese explaining the reason and a suggested fix.
Output ONLY the reason and a suggested fix."""

            self.log("Invoking gemma4 for deep text-based bottleneck diagnosis...")
            reason = self.query_llm_text(prompt)
            self.log(f"📝 [Diagnosis Result]: {reason}")
            
            # 推論結果もテキスト保存
            with open(os.path.join(error_dir, f"{timestamp}_bottleneck.txt"), "w", encoding="utf-8") as f:
                f.write(f"Action: {intended_action}\nLLM Diagnosis: {reason}\n")
                
            return reason
        except Exception as e:
            self.log(f"Diagnosis failed: {e}")
        
        return "診断プロセスでエラーが発生しました。"

    def get_deck_size(self, frame):
        """
        Crops the top-right deck icon region and runs OCR to extract the current total deck size.
        """
        if frame is None:
            return None
        h, w, _ = frame.shape
        # Deck count is typically at x_pct ~ 0.93, y_pct ~ 0.09
        x_start = int(w * 0.90)
        x_end = int(w * 0.96)
        y_start = int(h * 0.05)
        y_end = int(h * 0.13)
        
        crop = frame[y_start:y_end, x_start:x_end]
        if crop.size == 0:
            return None
            
        words = self.get_all_text_coords(crop)
        
        import re
        for w_data in words:
            text = w_data['text'].strip()
            digits = re.findall(r'\d+', text)
            if digits:
                try:
                    return int(digits[0])
                except: pass
        return None
