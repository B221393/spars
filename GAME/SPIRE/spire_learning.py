import os
import sys
import json
import time
import threading
import cv2
import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVES_DIR = os.path.join(BASE_DIR, "saves")
DB_PATH = os.path.join(SAVES_DIR, "card_db.json")
RUNS_PATH = os.path.join(SAVES_DIR, "run_history.json")
HUMAN_CLICKS_PATH = os.path.join(SAVES_DIR, "human_clicks.json")
EVENT_DB_PATH = os.path.join(SAVES_DIR, "event_dict.json")
EVENT_HTML_PATH = os.path.join(BASE_DIR, "event_dictionary.html")
FAILED_CLICKS_PATH = os.path.join(SAVES_DIR, "failed_clicks.json")

STANDARD_CARDS = {
    # Attack Cards
    "strike": "ATTACK", "打撃": "ATTACK", "攻撃": "ATTACK",
    "bash": "ATTACK", "バッシュ": "ATTACK", "重打": "ATTACK",
    "carnage": "ATTACK", "大虐殺": "ATTACK",
    "cleave": "ATTACK", "劈開": "ATTACK", "なぎ払い": "ATTACK",
    "anger": "ATTACK", "怒り": "ATTACK",
    "thunderclap": "ATTACK", "雷鳴": "ATTACK",
    "clash": "ATTACK", "クラッシュ": "ATTACK",
    "heavy blade": "ATTACK", "ヘビーブレード": "ATTACK",
    "twin strike": "ATTACK", "ツインストライク": "ATTACK",
    "whirlwind": "ATTACK", "旋風刃": "ATTACK",
    "iron wave": "ATTACK", "アイアンウェーブ": "ATTACK",
    "pummel": "ATTACK", "連続打ち": "ATTACK",
    "sever soul": "ATTACK", "ソウルシバー": "ATTACK",
    "fiend fire": "ATTACK", "悪魔の炎": "ATTACK",
    "feed": "ATTACK", "捕食": "ATTACK",
    "reaper": "ATTACK", "死神": "ATTACK",
    "hemid": "ATTACK",
    "eviscerate": "ATTACK", "内臓剥ぎ": "ATTACK",
    "neutralize": "ATTACK", "無力化": "ATTACK",
    "quick slash": "ATTACK", "クイックスラッシュ": "ATTACK",
    "sucker punch": "ATTACK", "不意打ち": "ATTACK",
    "all-out attack": "ATTACK", "全プログラム攻撃": "ATTACK", "オールアウト": "ATTACK",
    "dagger spray": "ATTACK", "短剣の嵐": "ATTACK",
    "choke": "ATTACK", "チョーク": "ATTACK",
    "riddle with holes": "ATTACK", "蜂の巣": "ATTACK",
    "flechettes": "ATTACK", "フレシェット": "ATTACK",
    "die die die": "ATTACK", "ダイ・ダイ・ダイ": "ATTACK",
    "poisoned stab": "ATTACK", "毒刺し": "ATTACK",
    "bane": "ATTACK", "破滅": "ATTACK",
    "bouncing flask": "ATTACK", "跳ね返るフラスコ": "ATTACK",
    "catalyst": "ATTACK", "触媒": "ATTACK",
    "noxious fumes": "ATTACK", "有毒ガス": "ATTACK",
    "corpse explosion": "ATTACK", "死体爆破": "ATTACK",
    "skewer": "ATTACK", "串刺し": "ATTACK",
    "predator": "ATTACK", "捕食者": "ATTACK",
    "dash": "ATTACK", "ダッシュ": "ATTACK",
    
    # Defend / Block Cards
    "defend": "DEFEND", "防御": "DEFEND",
    "block": "DEFEND", "ブロック": "DEFEND",
    "shrug it off": "DEFEND", "受け流し": "DEFEND",
    "dodge and roll": "DEFEND", "ドッジロール": "DEFEND",
    "impervious": "DEFEND", "無敵": "DEFEND",
    "survivor": "DEFEND", "サバイバー": "DEFEND",
    "entrench": "DEFEND", "難攻不落": "DEFEND",
    "barricade": "DEFEND", "バリケード": "DEFEND",
    "power through": "DEFEND", "突破": "DEFEND",
    "flame barrier": "DEFEND", "炎の障壁": "DEFEND",
    "metallicize": "DEFEND", "金属化": "DEFEND",
    "ghostly armor": "DEFEND", "霊体の鎧": "DEFEND",
    "footwork": "DEFEND", "フットワーク": "DEFEND",
    "blur": "DEFEND", "残像": "DEFEND",
    "deflect": "DEFEND", "受け流し": "DEFEND",
    "escape plan": "DEFEND", "脱出計画": "DEFEND",
    "piercing wail": "DEFEND", "耳を裂く悲鳴": "DEFEND",
    "cloak and dagger": "DEFEND", "外套と短剣": "DEFEND",
    "leg sweep": "DEFEND", "足払い": "DEFEND",
    
    # Curses / Status
    "slimed": "CURSE", "スライム": "CURSE",
    "dazed": "CURSE", "めまい": "CURSE",
    "wound": "CURSE", "傷口": "CURSE",
    "burn": "CURSE", "火傷": "CURSE",
    "void": "CURSE", "空虚": "CURSE",
    "decay": "CURSE", "腐敗": "CURSE",
    "doubt": "CURSE", "疑心": "CURSE",
    "shame": "CURSE", "羞恥": "CURSE",
    "regret": "CURSE", "後悔": "CURSE",
    "injury": "CURSE", "怪我": "CURSE",
    "pain": "CURSE", "痛み": "CURSE",
    "parasite": "CURSE", "寄生虫": "CURSE",
    "clumsy": "CURSE", "お荷物": "CURSE",
    "normality": "CURSE", "規格外": "CURSE", "常識": "CURSE",
    "curse": "CURSE", "呪い": "CURSE"
}

import re

def parse_card_cost_and_clean_name(ocr_name):
    match = re.search(r'\b([0-9xX])\b', ocr_name)
    if match:
        cost_str = match.group(1)
        cost = int(cost_str) if cost_str.isdigit() else 0
        clean_name = ocr_name.replace(cost_str, "").strip()
        return cost, clean_name
    return 1, ocr_name

def guess_card_category(ocr_name):
    # Normalize by removing all spaces (half-width, full-width, full-width space ideograph) and common punctuation
    normalized = re.sub(r'[\s\u3000\uff0c\u3001;、]', '', ocr_name).lower().strip()
    if not normalized:
        return "UNKNOWN"
        
    # Check Japanese starting cards and generic card types
    if any(kw in normalized for kw in ["防御", "スキル", "しゅご", "ブロック", "受け流し", "ドッジ", "無敵", "サバイバー", "フットワーク"]):
        return "DEFEND"
    if any(kw in normalized for kw in ["打撃", "攻撃", "ストライク", "ストライイ", "アタック", "バッシュ", "劈開", "なぎ払い", "怒り", "クラッシュ", "連続打ち"]):
        return "ATTACK"
    if any(kw in normalized for kw in ["スライム", "めまい", "傷口", "火傷", "空虚", "呪い", "寄生虫", "後悔", "痛み"]):
        return "CURSE"
        
    # Check normalized standard card keys
    for k, v in STANDARD_CARDS.items():
        k_normalized = re.sub(r'[\s\u3000\uff0c\u3001;、]', '', k).lower()
        if k_normalized and (k_normalized in normalized or normalized in k_normalized):
            return v
            
    return "UNKNOWN"



class HumanObserver:
    """
    バックグラウンドスレッドで人間のマウス操作を監視し、学習データとして保存する。
    ボットが操作していない間に画面変化が起きた場合、その直前のマウス位置を記録する。
    """
    def __init__(self, driver, learning):
        self.driver = driver
        self.learning = learning
        self.bot_is_clicking = False  # ボットがクリック中はTrueに設定する
        self._running = False
        self._thread = None
        self._last_screen_small = None
        self._last_mouse_pos = None

    def start(self):
        """バックグラウンド監視スレッドを起動する"""
        self._running = True
        self._thread = threading.Thread(target=self._observe_loop, daemon=True)
        self._thread.start()
        print("👀 [HumanObserver] 人間操作の監視を開始しました")

    def stop(self):
        self._running = False

    def _capture_small(self):
        """高速差分用の小さいスクリーンショット (64x36) を取得"""
        try:
            img = self.driver.capture()
            if img is None:
                return None
            arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            return cv2.resize(arr, (64, 36))
        except Exception:
            return None

    def _screen_diff(self, img_a, img_b):
        """2つの画像の平均絶対差分を返す"""
        if img_a is None or img_b is None:
            return 0.0
        diff = cv2.absdiff(img_a, img_b)
        return float(np.mean(diff))

    def _get_mouse_pos(self):
        try:
            import win32api
            return win32api.GetCursorPos()
        except Exception:
            return None

    def _is_left_button_down(self):
        try:
            import win32api
            return (win32api.GetAsyncKeyState(0x01) & 0x8000) != 0
        except Exception:
            return False

    def _observe_loop(self):
        """人間のクリックを監視するメインループ"""
        prev_screen = self._capture_small()
        prev_mouse = self._get_mouse_pos()
        was_clicking = False
        click_pos = None
        click_screen_before = None

        while self._running:
            try:
                time.sleep(0.08)  # 約12FPSで監視

                # ボットがクリック中はスキップ
                if self.bot_is_clicking:
                    prev_screen = self._capture_small()
                    prev_mouse = self._get_mouse_pos()
                    was_clicking = False
                    continue

                curr_mouse = self._get_mouse_pos()
                is_clicking = self._is_left_button_down()

                # クリックを開始した瞬間を検出
                if is_clicking and not was_clicking:
                    click_pos = curr_mouse
                    click_screen_before = prev_screen
                    was_clicking = True

                # クリックを離した瞬間を検出
                elif not is_clicking and was_clicking:
                    was_clicking = False

                    if click_pos is not None:
                        # 少し待ってから画面変化をチェック
                        time.sleep(0.2)
                        curr_screen = self._capture_small()
                        diff = self._screen_diff(click_screen_before, curr_screen)

                        if diff >= 3.0:
                            # 人間のクリックが画面変化を引き起こした！
                            self._record_human_click(click_pos)
                            prev_screen = curr_screen
                        
                        click_pos = None
                        click_screen_before = None
                else:
                    curr_screen = self._capture_small()
                    if curr_screen is not None:
                        prev_screen = curr_screen
                    prev_mouse = curr_mouse

            except Exception as e:
                time.sleep(0.5)

    def _record_human_click(self, screen_pos):
        """
        人間がクリックした画面座標を、ゲームウィンドウの相対比率で保存する。
        """
        try:
            import win32gui, ctypes, ctypes.wintypes
            hwnd = self.driver.hwnd
            if not hwnd:
                return

            # 画面絶対座標 → クライアント座標に変換
            point = ctypes.wintypes.POINT(int(screen_pos[0]), int(screen_pos[1]))
            ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(point))
            cx, cy = point.x, point.y

            # クライアントサイズを取得して比率計算
            rect = win32gui.GetClientRect(hwnd)
            w, h = rect[2], rect[3]
            if w <= 0 or h <= 0:
                return

            x_pct = cx / w
            y_pct = cy / h

            # 範囲外は除外
            if not (0.0 <= x_pct <= 1.0 and 0.0 <= y_pct <= 1.0):
                return

            # 現在認識中のゲーム状態を取得（eye が接続されていれば）
            state = getattr(self, '_current_state', 'UNKNOWN')

            record = {
                "state": state,
                "x_pct": round(x_pct, 4),
                "y_pct": round(y_pct, 4),
                "abs_x": cx,
                "abs_y": cy,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            print(f"👤 [HumanObserver] 人間操作を学習: 状態={state} 座標=({cx},{cy}) 比率=({x_pct:.3f}, {y_pct:.3f})")
            self.learning.record_human_click(state, x_pct, y_pct, cx, cy)

        except Exception as e:
            print(f"⚠️ [HumanObserver] 記録エラー: {e}")

    def set_current_state(self, state):
        """現在のゲーム状態をセット（ループから呼び出す）"""
        self._current_state = state

    def set_current_screen_hash(self, screen_hash):
        self._current_screen_hash = screen_hash


class SpireLearning:
    def __init__(self):
        os.makedirs(SAVES_DIR, exist_ok=True)
        os.makedirs(os.path.join(SAVES_DIR, "cards"), exist_ok=True)
        # Create category subfolders for organized card storage
        for cat_folder in ["ATTACK", "DEFEND", "POWER", "SKILL", "CURSE", "STATUS", "UNKNOWN"]:
            os.makedirs(os.path.join(SAVES_DIR, "cards", cat_folder), exist_ok=True)
        os.makedirs(os.path.join(SAVES_DIR, "events"), exist_ok=True) # イベント画像用
        self.card_db = self.load_json(DB_PATH, {})
        self.run_history = self.load_json(RUNS_PATH, [])
        self.human_clicks = self.load_json(HUMAN_CLICKS_PATH, {})
        self.event_db = self.load_json(EVENT_DB_PATH, {})
        self.failed_clicks = self.load_json(FAILED_CLICKS_PATH, {})
        self.initialize_card_categories()

    def initialize_card_categories(self, eye=None):
        """System-level initialization: Recover card categories and names for all visual card screenshots at startup.
        
        Scans saves/cards/<CATEGORY>/ subfolders. The folder name IS the category.
        Also recovers categories from STANDARD_CARDS dictionary for any UNKNOWN entries.
        """
        modified = False
        
        # Phase 1: Recover categories from STANDARD_CARDS for existing DB entries
        for chash, info in self.card_db.items():
            name = info.get("name", "")
            cat = info.get("category", "UNKNOWN")
            if name and cat == "UNKNOWN":
                new_cat = guess_card_category(name)
                if new_cat != "UNKNOWN":
                    info["category"] = new_cat
                    modified = True
                    print(f"🔧 [Initialization] Restored card category for '{name}' to {new_cat}")

        # Phase 2: Scan category subfolders and register any cards not in DB
        cards_dir = os.path.join(SAVES_DIR, "cards")
        total_found = 0
        subfolder_restored = 0
        if os.path.exists(cards_dir):
            for cat_folder in os.listdir(cards_dir):
                cat_path = os.path.join(cards_dir, cat_folder)
                if not os.path.isdir(cat_path):
                    continue
                folder_category = cat_folder.upper()  # e.g. "ATTACK", "DEFEND"
                files = [f for f in os.listdir(cat_path) if f.endswith(".png")]
                total_found += len(files)
                for filename in files:
                    chash = os.path.splitext(filename)[0]
                    if chash not in self.card_db:
                        self.card_db[chash] = {
                            "name": "",
                            "cost": 1,
                            "category": folder_category,
                            "score": 0.0,
                            "times_played": 0,
                            "times_selected": 0
                        }
                        modified = True
                        subfolder_restored += 1
                    else:
                        # If DB has UNKNOWN category but folder says otherwise, trust folder
                        if self.card_db[chash].get("category", "UNKNOWN") == "UNKNOWN" and folder_category != "UNKNOWN":
                            self.card_db[chash]["category"] = folder_category
                            modified = True
                            subfolder_restored += 1
            print(f"📁 [Initialization] Scanned {total_found} card crops across category subfolders. Restored {subfolder_restored} entries.")

        # Phase 3: OCR scan for any remaining unresolved cards (if eye is available)
        if eye is not None and os.path.exists(cards_dir):
            resolved_count = 0
            for cat_folder in os.listdir(cards_dir):
                cat_path = os.path.join(cards_dir, cat_folder)
                if not os.path.isdir(cat_path):
                    continue
                for filename in os.listdir(cat_path):
                    if not filename.endswith(".png"):
                        continue
                    chash = os.path.splitext(filename)[0]
                    if chash not in self.card_db:
                        continue
                    info = self.card_db[chash]
                    name = info.get("name", "")
                    if not name:  # Only OCR if name is missing
                        crop_path = os.path.join(cat_path, filename)
                        crop_img = cv2.imread(crop_path)
                        if crop_img is not None:
                            ocr_name = eye.perform_ocr(crop_img)
                            if ocr_name:
                                cost, clean_name = parse_card_cost_and_clean_name(ocr_name)
                                new_cat = guess_card_category(clean_name)
                                info["name"] = clean_name
                                info["cost"] = cost
                                # If OCR gives a valid category and current is UNKNOWN, update
                                if new_cat != "UNKNOWN" and info.get("category", "UNKNOWN") == "UNKNOWN":
                                    info["category"] = new_cat
                                modified = True
                                resolved_count += 1
                                print(f"🔧 [Initialization] Resolved card '{chash}' to '{clean_name}' (Cost: {cost}, Cat: {new_cat}) via OCR.")
            if resolved_count > 0:
                print(f"✅ [Initialization] Resolved {resolved_count} card templates via startup OCR scan.")

        if modified:
            self.save_json(DB_PATH, self.card_db)

    def load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def save_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if path == DB_PATH:
                self.save_card_csv()
        except Exception as e:
            print(f"⚠️ Failed to save JSON to {path}: {e}")

    def save_card_csv(self):
        csv_path = os.path.join(SAVES_DIR, "card_db.csv")
        try:
            import csv
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Hash", "Name", "Category", "Score", "Times Played", "Times Selected"])
                for chash, info in self.card_db.items():
                    writer.writerow([
                        chash,
                        info.get("name", ""),
                        info.get("category", "UNKNOWN"),
                        info.get("score", 0.0),
                        info.get("times_played", 0),
                        info.get("times_selected", 0)
                    ])
            print(f"📊 [CSV Export] Exported card database to {csv_path}")
        except Exception as e:
            print(f"⚠️ Failed to save CSV to {csv_path}: {e}")

    # ────────────────────────────────────────────────────────────
    # イベント辞書（王道原理：推論の記憶と再利用）
    # ────────────────────────────────────────────────────────────

    def get_screen_hash(self, frame_small):
        """画面全体(64x36)から状態を識別するハッシュを生成"""
        if frame_small is None: return "0"
        return str(hash(frame_small.tobytes()))

    def get_event_solution(self, screen_hash):
        """記憶されているイベントの解答（座標とテキスト）を取得"""
        return self.event_db.get(screen_hash, None)

    def record_event_solution(self, screen_hash, frame, text, x_pct, y_pct, reward=10000.0):
        """
        [変異至上主義: 初速報酬システム]
        画面を変化させることに成功したアクションに対し、あり得ないほどの巨大報酬（デフォルト+10000）を与えて強烈に記憶する。
        画像は容量削減のため極小サムネイルとして保存する。
        """
        if screen_hash not in self.event_db:
            self.event_db[screen_hash] = {
                "text": text,
                "x_pct": round(x_pct, 4),
                "y_pct": round(y_pct, 4),
                "score": 0.0,
                "image": "",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 容量削減：極小サムネイル(256x144)として保存
            if frame is not None:
                img_path = f"saves/events/{screen_hash}_thumb.jpg"
                try:
                    thumb = cv2.resize(frame, (256, 144), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(os.path.join(BASE_DIR, img_path), thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                    self.event_db[screen_hash]["image"] = img_path
                except Exception as e:
                    print(f"⚠️ Thumbnail save failed: {e}")

        # 巨大報酬の付与
        self.event_db[screen_hash]["score"] += reward
        current_score = self.event_db[screen_hash]["score"]
        print(f"🎁 [Massive Reward] 画面変異に成功！ '{text}' に超巨大報酬 +{reward} (Total: {current_score}) を付与し、記憶に刻みました。")
        
        self.save_json(EVENT_DB_PATH, self.event_db)
        self.generate_html_dictionary()

    def record_event_failure(self, screen_hash, text, penalty=-500.0):
        """
        If a click had no response (no screen change), give a negative reward (minus)
        to that state-action pair in the database.
        """
        if screen_hash not in self.event_db:
            self.event_db[screen_hash] = {
                "text": text,
                "x_pct": 0.0,
                "y_pct": 0.0,
                "score": 0.0,
                "image": "",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        self.event_db[screen_hash]["score"] += penalty
        current_score = self.event_db[screen_hash]["score"]
        print(f"💔 [Penalty] 画面変異に失敗！ '{text}' にペナルティ {penalty} (Total: {current_score}) を与えました。")
        self.save_json(EVENT_DB_PATH, self.event_db)
        self.generate_html_dictionary()

    def generate_html_dictionary(self):
        """イベント辞書を視覚化する軽量HTMLを生成"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Event Memory & Action Dictionary (軽量版)</title>
            <style>
                body { background: #050505; color: #00ffcc; font-family: 'Segoe UI', sans-serif; padding: 20px; }
                h1 { border-bottom: 2px solid #00ffcc; padding-bottom: 10px; }
                .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }
                .card { background: #111; padding: 10px; border-radius: 6px; border: 1px solid #333; position: relative; }
                .card img { width: 100%; border-radius: 4px; margin-bottom: 8px; image-rendering: pixelated; }
                .btn { background: #00ffcc; color: #000; padding: 3px 8px; border-radius: 3px; font-weight: bold; font-size: 14px; }
                .score { position: absolute; top: 15px; right: 15px; background: #ff0055; color: #fff; padding: 2px 6px; border-radius: 3px; font-weight: bold; font-size: 12px; box-shadow: 0 0 10px #ff0055; }
                .meta { color: #888; font-size: 11px; margin-top: 5px; }
            </style>
        </head>
        <body>
            <h1>📚 Fast-Vision Event Dictionary (画面変異・初速記憶)</h1>
            <p>画面に変化（初速）をもたらした「正解のアクション」を超軽量サムネイルと共にカタログ化しています。</p>
            <div class="grid">
        """
        for shash, data in self.event_db.items():
            img_tag = f"<img src='{data.get('image', '')}'>" if data.get('image') else "<div style='height:144px; background:#222; text-align:center; line-height:144px;'>No Thumb</div>"
            score = data.get('score', 0.0)
            html += f"""
                <div class="card">
                    <div class="score">+{score}</div>
                    {img_tag}
                    <div>Target: <span class="btn">{data['text']}</span></div>
                    <div class="meta">Coord: (W*{data['x_pct']}, H*{data['y_pct']})</div>
                    <div class="meta">Learned: {data['timestamp']}</div>
                </div>
            """
        html += """
            </div>
        </body>
        </html>
        """
        try:
            with open(EVENT_HTML_PATH, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as e:
            print(f"⚠️ Failed to write HTML dict: {e}")

    # ────────────────────────────────────────────────────────────
    # 不適クリック（変化なし座標）の学習・回避
    # ────────────────────────────────────────────────────────────

    def record_failed_click(self, state_or_hash, x_pct, y_pct):
        if not state_or_hash:
            return
        state_or_hash = str(state_or_hash)
        if state_or_hash not in self.failed_clicks:
            self.failed_clicks[state_or_hash] = []
            
        # Avoid duplicate clicks within 0.5% screen distance
        for entry in self.failed_clicks[state_or_hash]:
            if abs(entry["x_pct"] - x_pct) < 0.005 and abs(entry["y_pct"] - y_pct) < 0.005:
                return
                
        self.failed_clicks[state_or_hash].append({
            "x_pct": round(x_pct, 4),
            "y_pct": round(y_pct, 4),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_json(FAILED_CLICKS_PATH, self.failed_clicks)
        print(f"💔 [Learning] Recorded failed click coordinate for state/hash {state_or_hash}: ({x_pct:.3f}, {y_pct:.3f})")

    def is_failed_click(self, state_or_hash, x_pct, y_pct, threshold=0.04):
        if not state_or_hash:
            return False
        state_or_hash = str(state_or_hash)
        if state_or_hash not in self.failed_clicks:
            return False
        for entry in self.failed_clicks[state_or_hash]:
            dist = ((entry["x_pct"] - x_pct)**2 + (entry["y_pct"] - y_pct)**2)**0.5
            if dist < threshold:
                return True
        return False

    def clear_failed_clicks(self, state_or_hash):
        if not state_or_hash:
            return
        state_or_hash = str(state_or_hash)
        if state_or_hash in self.failed_clicks:
            self.failed_clicks[state_or_hash] = []
            self.save_json(FAILED_CLICKS_PATH, self.failed_clicks)
            print(f"🧹 [Learning] Cleared failed click coordinates for state/hash {state_or_hash}")

    # ────────────────────────────────────────────────────────────
    # 人間操作の学習
    # ────────────────────────────────────────────────────────────

    def record_human_click(self, state, x_pct, y_pct, abs_x, abs_y):
        """
        人間がクリックした座標を状態ごとに記録する。
        直近10件の平均を「推奨座標」として保持する。
        """
        if state not in self.human_clicks:
            self.human_clicks[state] = {"history": [], "best_x_pct": None, "best_y_pct": None}

        entry = self.human_clicks[state]
        entry["history"].append({
            "x_pct": x_pct,
            "y_pct": y_pct,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        # 直近10件だけ保持
        entry["history"] = entry["history"][-10:]

        # 平均座標を計算して「推奨座標」として保存
        xs = [h["x_pct"] for h in entry["history"]]
        ys = [h["y_pct"] for h in entry["history"]]
        entry["best_x_pct"] = sum(xs) / len(xs)
        entry["best_y_pct"] = sum(ys) / len(ys)

        self.save_json(HUMAN_CLICKS_PATH, self.human_clicks)
        print(f"💾 [Learning] 人間推奨座標を保存: {state} → ({entry['best_x_pct']:.3f}, {entry['best_y_pct']:.3f})")

    def get_human_click_coord(self, state, window_w, window_h):
        """
        指定した状態で人間が学習済みのクリック座標を返す。
        未学習なら None を返す（デフォルト座標にフォールバック）。
        直近3件以上のデータがある場合のみ信頼する。
        """
        if state not in self.human_clicks:
            return None
        entry = self.human_clicks[state]
        if len(entry.get("history", [])) < 3:
            return None  # データが少ない場合は信頼しない
        x_pct = entry.get("best_x_pct")
        y_pct = entry.get("best_y_pct")
        if x_pct is None or y_pct is None:
            return None
        return (int(window_w * x_pct), int(window_h * y_pct))

    # ────────────────────────────────────────────────────────────
    # カード学習（既存機能）
    # ────────────────────────────────────────────────────────────

    def get_card_hash(self, card_crop):
        """Computes a robust dhash (difference hash) for the card crop."""
        if card_crop is None or card_crop.size == 0:
            return None
        try:
            gray = cv2.cvtColor(card_crop, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
            diff = resized[:, 1:] > resized[:, :-1]
            return "".join(f"{val:02x}" for val in np.packbits(diff))
        except Exception:
            return None

    def register_card(self, card_hash, card_crop):
        """Registers a card hash and saves its visual image crop into the appropriate category subfolder."""
        if not card_hash:
            return
        if card_hash not in self.card_db:
            self.card_db[card_hash] = {
                "name": "",
                "cost": 1,
                "category": "UNKNOWN",
                "score": 0.0,
                "times_played": 0,
                "times_selected": 0
            }
            # Save into category subfolder (UNKNOWN by default for new cards)
            cat = self.card_db[card_hash].get("category", "UNKNOWN")
            cat_dir = os.path.join(SAVES_DIR, "cards", cat)
            os.makedirs(cat_dir, exist_ok=True)
            crop_path = os.path.join(cat_dir, f"{card_hash}.png")
            try:
                cv2.imwrite(crop_path, card_crop)
            except Exception:
                pass
            self.save_json(DB_PATH, self.card_db)

    def get_card_name(self, card_hash):
        if card_hash in self.card_db:
            return self.card_db[card_hash].get("name", "")
        return ""

    def update_card_name(self, card_hash, name, cost=1, category="UNKNOWN"):
        if not card_hash or card_hash not in self.card_db:
            return
        old_cat = self.card_db[card_hash].get("category", "UNKNOWN")
        self.card_db[card_hash]["name"] = name
        self.card_db[card_hash]["cost"] = cost
        if category != "UNKNOWN" or old_cat == "UNKNOWN":
            self.card_db[card_hash]["category"] = category
            if category != old_cat:
                self._move_card_to_category_folder(card_hash, old_cat, category)
        self.save_json(DB_PATH, self.card_db)

    def _move_card_to_category_folder(self, card_hash, old_cat, new_cat):
        """Move card crop file from old category subfolder to new one."""
        try:
            old_path = os.path.join(SAVES_DIR, "cards", old_cat, f"{card_hash}.png")
            new_dir = os.path.join(SAVES_DIR, "cards", new_cat)
            os.makedirs(new_dir, exist_ok=True)
            new_path = os.path.join(new_dir, f"{card_hash}.png")
            if os.path.exists(old_path) and not os.path.exists(new_path):
                import shutil
                shutil.move(old_path, new_path)
                print(f"📂 [CardOrganizer] Moved {card_hash}.png from {old_cat}/ to {new_cat}/")
        except Exception as e:
            print(f"⚠️ [CardOrganizer] Failed to move card file: {e}")

    def update_card_effect(self, card_hash, block_diff, hp_diff):
        """Learns card category based on state changes (block and enemy HP)."""
        if not card_hash or card_hash not in self.card_db:
            return
        db_entry = self.card_db[card_hash]
        old_cat = db_entry.get("category", "UNKNOWN")
        db_entry["times_played"] = db_entry.get("times_played", 0) + 1
        new_cat = old_cat
        if block_diff > 0:
            new_cat = "DEFEND"
            db_entry["category"] = new_cat
            print(f"🧠 [Learning] Card {card_hash} learned as DEFEND")
        elif hp_diff < 0:
            new_cat = "ATTACK"
            db_entry["category"] = new_cat
            print(f"🧠 [Learning] Card {card_hash} learned as ATTACK")
        if new_cat != old_cat:
            self._move_card_to_category_folder(card_hash, old_cat, new_cat)
        self.save_json(DB_PATH, self.card_db)

    def record_run_outcome(self, victory, max_floor, selected_cards):
        """Reinforces card scores based on run outcomes (Q-learning update)."""
        self.run_history.append({
            "victory": victory,
            "max_floor": max_floor,
            "selected_cards": selected_cards,
            "timestamp": time.strftime("%H:%M:%S")
        })
        self.save_json(RUNS_PATH, self.run_history)
        reward = max_floor if not victory else 50.0
        for card_hash in selected_cards:
            if card_hash in self.card_db:
                entry = self.card_db[card_hash]
                entry["times_selected"] = entry.get("times_selected", 0) + 1
                alpha = 0.2
                entry["score"] = (1 - alpha) * entry.get("score", 0.0) + alpha * reward
        self.save_json(DB_PATH, self.card_db)

    def get_card_category(self, card_hash):
        if card_hash in self.card_db:
            return self.card_db[card_hash].get("category", "UNKNOWN")
        return "UNKNOWN"

    def get_card_score(self, card_hash):
        if card_hash in self.card_db:
            return self.card_db[card_hash].get("score", 0.0)
        return 0.0

    def record_deck_size(self, state, deck_size):
        """Records deck size to saves/deck_history.json."""
        if deck_size is None:
            return
        history_path = os.path.join(SAVES_DIR, "deck_history.json")
        history = self.load_json(history_path, [])
        
        # Check if the last entry is the same to avoid spamming duplicates
        if history and history[-1].get("deck_size") == deck_size and history[-1].get("state") == state:
            history[-1]["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            history.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "state": state,
                "deck_size": deck_size
            })
            print(f"📖 [Learning] Saved deck size: {deck_size} (State: {state})")
            
        self.save_json(history_path, history)


class ScreenshotCacheManager:
    def __init__(self, driver):
        self.driver = driver
        self.cache_dir = os.path.join(SAVES_DIR, "screenshot_cache")
        self.click_history_dir = os.path.join(SAVES_DIR, "click_history")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.click_history_dir, exist_ok=True)
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._cache_loop, daemon=True)
        self._thread.start()
        print("📸 [ScreenshotCacheManager] Started 1-second screen capture cache loop.")

    def stop(self):
        self._running = False

    def _cache_loop(self):
        last_cleanup = time.time()
        while self._running:
            try:
                # Capture screen and save
                img = self.driver.capture()
                if img is not None:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filepath = os.path.join(self.cache_dir, f"sec_{timestamp}.jpg")
                    # Resize to 640x400 and save with low quality to compress storage size
                    img_small = img.resize((640, 400))
                    img_small.save(filepath, "JPEG", quality=30)
                
                # Cleanup files older than 60 seconds every 15 seconds
                now = time.time()
                if now - last_cleanup >= 15.0:
                    self.cleanup_old_files()
                    last_cleanup = now
            except Exception as e:
                print(f"⚠️ [ScreenshotCacheManager] Error in cache loop: {e}")
            time.sleep(1.0)

    def cleanup_old_files(self):
        now = time.time()
        count = 0
        try:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    # Delete if file is older than 60 seconds
                    file_mtime = os.path.getmtime(filepath)
                    if now - file_mtime > 60.0:
                        os.remove(filepath)
                        count += 1
            if count > 0:
                print(f"🧹 [ScreenshotCacheManager] Cleaned up {count} cached screenshots older than 60s.")
        except Exception as e:
            print(f"⚠️ [ScreenshotCacheManager] Cleanup failed: {e}")

    def save_click_proof(self, before_img, after_img, status):
        """Saves highly-compressed before and after images to click_history folder."""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            # Highly compressed and resized to save disk space as requested
            if before_img is not None:
                before_path = os.path.join(self.click_history_dir, f"{timestamp}_before_{status}.jpg")
                before_small = before_img.resize((640, 400))
                before_small.save(before_path, "JPEG", quality=30)
            if after_img is not None:
                after_path = os.path.join(self.click_history_dir, f"{timestamp}_after_{status}.jpg")
                after_small = after_img.resize((640, 400))
                after_small.save(after_path, "JPEG", quality=30)
            print(f"💾 [ScreenshotCacheManager] Saved highly-compressed click proof before/after: {status}")
        except Exception as e:
            print(f"⚠️ [ScreenshotCacheManager] Failed to save click proof: {e}")



