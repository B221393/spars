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


class SpireLearning:
    def __init__(self):
        os.makedirs(SAVES_DIR, exist_ok=True)
        os.makedirs(os.path.join(SAVES_DIR, "cards"), exist_ok=True)
        os.makedirs(os.path.join(SAVES_DIR, "events"), exist_ok=True) # イベント画像用
        self.card_db = self.load_json(DB_PATH, {})
        self.run_history = self.load_json(RUNS_PATH, [])
        self.human_clicks = self.load_json(HUMAN_CLICKS_PATH, {})
        self.event_db = self.load_json(EVENT_DB_PATH, {})

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
        except Exception as e:
            print(f"⚠️ Failed to save JSON to {path}: {e}")

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
        """Registers a card hash and saves its visual image crop for reference."""
        if not card_hash:
            return
        if card_hash not in self.card_db:
            self.card_db[card_hash] = {
                "name": "",
                "category": "UNKNOWN",
                "score": 0.0,
                "times_played": 0,
                "times_selected": 0
            }
            crop_path = os.path.join(SAVES_DIR, "cards", f"{card_hash}.png")
            try:
                cv2.imwrite(crop_path, card_crop)
            except Exception:
                pass
            self.save_json(DB_PATH, self.card_db)

    def get_card_name(self, card_hash):
        if card_hash in self.card_db:
            return self.card_db[card_hash].get("name", "")
        return ""

    def update_card_name(self, card_hash, name):
        if not card_hash or card_hash not in self.card_db:
            return
        self.card_db[card_hash]["name"] = name
        self.save_json(DB_PATH, self.card_db)

    def update_card_effect(self, card_hash, block_diff, hp_diff):
        """Learns card category based on state changes (block and enemy HP)."""
        if not card_hash or card_hash not in self.card_db:
            return
        db_entry = self.card_db[card_hash]
        db_entry["times_played"] = db_entry.get("times_played", 0) + 1
        if block_diff > 0:
            db_entry["category"] = "DEFEND"
            print(f"🧠 [Learning] Card {card_hash} learned as DEFEND")
        elif hp_diff < 0:
            db_entry["category"] = "ATTACK"
            print(f"🧠 [Learning] Card {card_hash} learned as ATTACK")
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


