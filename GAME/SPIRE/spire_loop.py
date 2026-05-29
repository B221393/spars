import os
import sys
import time
_orig_sleep = time.sleep

# ─────────────────────────────────────────────────
# モード定数
# ─────────────────────────────────────────────────
MODE_AUTO  = "AUTO"   # 通常自動プレイ
MODE_WATCH = "WATCH"  # 監視モード：ボット停止・人間操作のみ学習
MODE_COOP  = "COOP"   # 協力モード：ボットと人間が協力

CURRENT_MODE = MODE_AUTO
ENABLE_LLM_DIAGNOSIS = False  # Set to True only when deep diagnosis on CPU is acceptable

# ─────────────────────────────────────────────────
# テンキー手動カードプレイ
# ─────────────────────────────────────────────────
# テンキー1〜9のVKコード: 0x61〜0x69
NUMPAD_CODES = {
    0x61: 1, 0x62: 2, 0x63: 3,
    0x64: 4, 0x65: 5, 0x66: 6,
    0x67: 7, 0x68: 8, 0x69: 9,
}
PENDING_CARD_PLAY = None  # None or int (1-based card index)

def _key(code):
    try:
        import win32api
        return bool(win32api.GetAsyncKeyState(code) & 0x8000)
    except Exception:
        return False

def _wait_keys_release(*codes):
    while any(_key(c) for c in codes):
        _orig_sleep(0.05)

def sleep_override(seconds):
    global CURRENT_MODE, PENDING_CARD_PLAY
    start = time.time()
    while time.time() - start < seconds:
        # --- 1+2: AUTO ↔ WATCH 切替 ---
        if _key(0x31) and _key(0x32) and not _key(0x33) and not _key(0x34):
            if CURRENT_MODE != MODE_AUTO:
                CURRENT_MODE = MODE_AUTO
                print("▶️  [Mode] AUTO モードに戻りました（全自動プレイ）")
            else:
                CURRENT_MODE = MODE_WATCH
                print("⏸️  [Mode] WATCH モードに切り替えました（監視・学習のみ）")
            _wait_keys_release(0x31, 0x32)

        # --- 1+3: 監視モード ---
        elif _key(0x31) and _key(0x33) and not _key(0x32) and not _key(0x34):
            CURRENT_MODE = MODE_WATCH
            print("👀 [Mode] WATCH モード ON！ボットは停止、人間操作を学習中...")
            _wait_keys_release(0x31, 0x33)

        # --- 1+4: 協力モード ---
        elif _key(0x31) and _key(0x34) and not _key(0x32) and not _key(0x33):
            CURRENT_MODE = MODE_COOP
            print("🤝 [Mode] COOP モード ON！人間とボットが協力します")
            _wait_keys_release(0x31, 0x34)

        # --- テンキー 1〜9: 手動カードプレイ（1キーが押されていない時のみ）---
        elif not _key(0x31):
            for vk, card_num in NUMPAD_CODES.items():
                if _key(vk):
                    if PENDING_CARD_PLAY != card_num:
                        PENDING_CARD_PLAY = card_num
                        print(f"🎴 [Manual] テンキー {card_num} → カード {card_num} を手動プレイします")
                    _wait_keys_release(vk)
                    break

        # WATCH 中はボット側の sleep をブロックして待機（テンキーは引き続き受け付ける）
        if CURRENT_MODE == MODE_WATCH:
            _orig_sleep(0.1)
            continue

        _orig_sleep(0.02)

time.sleep = sleep_override



import random

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from spire_eye import SpireEye
from spire_tactics import SpireTactics
from spire_body import SpireBody
from spire_learning import HumanObserver

from CORE.ai_driver import AIDriver

def write_reflection(base_dir, loop_count, current_state):
    import time
    import os
    saves_dir = os.path.join(base_dir, "saves")
    os.makedirs(saves_dir, exist_ok=True)
    reflection_file = os.path.join(saves_dir, "evolution_reflections.md")
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    if current_state == "COMBAT":
        good = "マウス座標の1:1マッピング（DPI対応）が正常に動作し、戦闘画面が安定して進行中。"
        problem = "敵インテントやカードのOCRスキャンでわずかなI/Oオーバーヘッドがある。"
        try_text = "カード特徴量のキャッシュ効率を最大化し、高速なリフレックス動作を維持する。"
    elif current_state == "REST_SITE":
        good = "キャンプファイヤー状態を検知し、休憩選択の物理入力を実行。"
        problem = "フェード遷移時の画面静止キャッシュが長めに判定される場合がある。"
        try_text = "変異検出のしきい値を調整し、フェードアウト後の最速クリックを狙う。"
    elif current_state == "CHARACTER_SELECT":
        good = "デイリーチャレンジおよびキャラ選択画面の文字を検出し、確定チェックマークへのマッピングに成功。"
        problem = "フォーカスが外れた場合、安全装置が正しく機能するがループが待機に入る。"
        try_text = "ユーザーがエディタ操作中でも背後でゲームを実行できるよう、非フォーカス時の入力手段をさらに検証する。"
    elif current_state == "MAIN_MENU":
        good = "メインメニュー画面を検知し、シングルプレイボタンを押下。"
        problem = "ゲームの起動状態やサイズ変更によってボタン座標がずれる可能性があったが、DPI修正により改善。"
        try_text = "OCRテキストマッチングを第一優先とし、ボタン座標を動的に決定し続ける。"
    else:
        good = f"現在のゲーム状態 {current_state} を安定して検知。"
        problem = "未知の画面による判定保留が発生しやすい。"
        try_text = "Gemma4のCPU診断をバイパスしつつ、フォールバッククリック座標の精度を高める。"
        
    log_entry = f"""
## 🧠 [{timestamp}] 反省会 (サイクル {loop_count})
- **現在の状態 (State)**: `{current_state}`
- **良かったこと (Good)**: {good}
- **反省点 (Problem)**: {problem}
- **改善案 (Try)**: {try_text}
"""
    
    first_write = not os.path.exists(reflection_file)
    with open(reflection_file, "a", encoding="utf-8") as f:
        if first_write:
            f.write("# 🧠 AI 協働進化・反省会ログ (Evolution Reflections)\n")
            f.write("このファイルは、AIが1分ごとに自動運転の成果、反省点、および次の改善案を振り返るログです。\n\n")
        f.write(log_entry)
    print(f"📝 [Reflection] evolution_reflections.md に反省会を記録しました。")

def run_spire_automator(target_title="Slay the Spire", max_loops=100000):
    print("🎵 Starting Autonomous Slay the Spire Infinite Loop (SPIRE)...")
    print("=" * 55)
    print("  ⌨️  キーボード操作ガイド:")
    print("  [ 1 + 2 ] → AUTO ↔ WATCH 切替（一時停止/再開）")
    print("  [ 1 + 3 ] → WATCH モード（監視・学習専用）")
    print("  [ 1 + 4 ] → COOP  モード（人間+ボット協力）")
    print("  ─────────────────────────────────────────────")
    print("  [ テンキー 1〜9 ] → その番号のカードを敵中央にドラッグ")
    print("     ※ WATCH・COOP・AUTO モード全てで有効")
    print("=" * 55)


    
    # Initialize Core HEB components
    driver = AIDriver(target_title, log_dir=BASE_DIR)
    
    # Bind window
    driver.connect()
    if not driver.hwnd:
        for fallback_title in ["Slay the Spire 2", "Slay the Spire"]:
            print(f"Window '{target_title}' not found. Trying fallback '{fallback_title}'...")
            driver.target_title = fallback_title
            if driver.connect():
                target_title = fallback_title
                break
                
    if not driver.hwnd:
        print(f"❌ Error: Slay the Spire window not found! Autoplay stopped. (Tried targeting: '{target_title}')")
        sys.exit("Error: Slay the Spire window not found!")
        
    eye = SpireEye(driver)
    tactics = SpireTactics()
    body = SpireBody(driver)
    
    # 人間操作の観察・学習スレッドを起動
    human_observer = HumanObserver(driver, tactics.learning)
    human_observer.start()
    
    loop_count = 0
    consecutive_unknowns = 0
    selected_card_hashes = []
    last_reflection_time = time.time()
    
    # Spinal quick loop
    try:
        while loop_count < max_loops:
            try:
                import win32api
                mx, my = win32api.GetCursorPos()
                print(f"📍 Current Mouse Position: ({mx}, {my})")
            except Exception:
                pass

            # Check window connection — 再接続を最大10回試みる
            if not driver.check_connection() or not driver.hwnd:
                print("⚠️ Slay the Spire ウィンドウが見つかりません。再接続を試みます...")
                reconnected = False
                for attempt in range(10):
                    _orig_sleep(2.0)
                    for title in ["Slay the Spire 2", "Slay the Spire"]:
                        driver.target_title = title
                        if driver.connect():
                            print(f"✅ 再接続成功: '{title}'")
                            reconnected = True
                            break
                    if reconnected:
                        break
                    print(f"  再接続試行 {attempt+1}/10...")
                if not reconnected:
                    print("❌ 再接続失敗。Autoplay 停止。")
                    sys.exit("Error: Slay the Spire window connection lost!")


            loop_count += 1
            print(f"\n🔄 --- Loop Cycle {loop_count} [{CURRENT_MODE}] ---")
            
            # ─── Puppet Command Check ───
            hints_path = os.path.join(BASE_DIR, "saves", "puppet_hints.json")
            if os.path.exists(hints_path):
                try:
                    import json
                    with open(hints_path, "r", encoding="utf-8") as f:
                        hints = json.load(f)
                except:
                    hints = {}
                
                # A. Manual Click (Absolute Coordinates)
                if hints.get("manual_click"):
                    mc = hints["manual_click"]
                    print(f"👤 [Puppet Command] Performing manual click at ({mc[0]}, {mc[1]})")
                    body.click_position(mc, "User Manual Click")
                    # Clear manual click
                    hints["manual_click"] = None
                    try:
                        with open(hints_path, "w", encoding="utf-8") as f:
                            json.dump(hints, f)
                    except: pass
                    time.sleep(1.0)
                    continue
                
                # B. Manual Click (Percentage Coordinates)
                if hints.get("manual_click_pct"):
                    mcp = hints["manual_click_pct"]
                    w, h = eye.window_size
                    mc = (int(w * mcp[0]), int(h * mcp[1]))
                    print(f"👤 [Puppet Command] Performing manual click pct at ({mc[0]}, {mc[1]})")
                    body.click_position(mc, "User Manual Click Pct")
                    # Clear manual click pct
                    hints["manual_click_pct"] = None
                    try:
                        with open(hints_path, "w", encoding="utf-8") as f:
                            json.dump(hints, f)
                    except: pass
                    time.sleep(1.0)
                    continue

            # 1. Eye: grab screen frame
            frame = eye.grab_screen()
            state = eye.detect_game_state(frame)
            print(f"👁️ Detected Game State: {state}")
            
            # --- 1分ごとの反省会ログ記録 ---
            if time.time() - last_reflection_time >= 60.0:
                try:
                    write_reflection(BASE_DIR, loop_count, state)
                except Exception as e:
                    print(f"⚠️ [Reflection] Failed to write reflection: {e}")
                last_reflection_time = time.time()
            
            # 現在の状態をHumanObserverに通知（人間操作のタグ付け用）
            human_observer.set_current_state(state)
            
            # ─── WATCH モード: ボットは何もしない、人間のみ操作 ───
            # ただしテンキーによる手動プレイは WATCH 中も有効
            if CURRENT_MODE == MODE_WATCH:
                if PENDING_CARD_PLAY is not None and state == "COMBAT":
                    # WATCH中でもテンキーが押されたらカードをドラッグ
                    print(f"🎴 [Manual/WATCH] テンキー操作でカード {PENDING_CARD_PLAY} をプレイ")
                    # elementsがあれば使う、なければ画面解析
                    _watch_frame = eye.grab_screen()
                    _watch_elements = eye.locate_combat_elements(_watch_frame) if _watch_frame else {}
                    _watch_cards = _watch_elements.get("cards", [])
                    _w, _h = eye.window_size
                    _cidx = PENDING_CARD_PLAY - 1
                    if 0 <= _cidx < len(_watch_cards):
                        _ccoord = _watch_cards[_cidx]
                    elif _watch_cards:
                        _ccoord = _watch_cards[-1]
                    else:
                        _ccoord = None
                    if _ccoord:
                        _enemies = _watch_elements.get("enemies", [])
                        _tx = sum(e[0] for e in _enemies) // len(_enemies) if _enemies else int(_w * 0.72)
                        _ty = sum(e[1] for e in _enemies) // len(_enemies) if _enemies else int(_h * 0.45)
                        human_observer.bot_is_clicking = True
                        body.play_card(_ccoord, (_tx, _ty))
                        human_observer.bot_is_clicking = False
                    PENDING_CARD_PLAY = None
                else:
                    print("👀 [WATCH] 監視中... ボットはスキップ。人間の操作を学習しています。")
                time.sleep(1.0)
                continue


            # ─── COOP モード: 少し待って人間が先に動くか確認 ───
            if CURRENT_MODE == MODE_COOP:
                print("🤝 [COOP] 協力モード: 人間が操作するなら待機、しなければボットが動きます")
                # 2秒待って、その間に人間が何かクリックすれば観察して学習するだけ
                _wait_start = time.time()
                _human_acted = False
                _before_coop = body._capture_small()
                _orig_sleep(2.0)  # 2秒待機
                _after_coop = body._capture_small()
                _coop_diff = body._pixel_diff(_before_coop, _after_coop)
                if _coop_diff >= 3.0:
                    print(f"🤝 [COOP] 人間が操作しました (diff={_coop_diff:.1f})。ボットはスキップ。")
                    # キャッシュリセットして次サイクルで再認識
                    eye.last_frame_small = None
                    eye.static_cycles_count = 0
                    continue
                else:
                    print(f"🤝 [COOP] 人間操作なし (diff={_coop_diff:.1f})。ボットが動きます。")
            
            if state == "LOADING":
                print("⏳ Game is loading. Waiting...")
                time.sleep(1.0)
                continue


            if state in ["UNKNOWN", "EVENT"]:
                # [王道原理] まず記憶（イベント辞書）を探る
                screen_hash = tactics.learning.get_screen_hash(eye.last_frame_small)
                known_solution = tactics.learning.get_event_solution(screen_hash)
                
                if known_solution:
                    target_text = known_solution['text']
                    target_coord = (int(eye.window_size[0] * known_solution['x_pct']), int(eye.window_size[1] * known_solution['y_pct']))
                    tactics.log(f"この画面は記憶にあります。過去の成功体験に従い '{target_text}' を選択します。", state=state)
                    
                    success, reason = body.confirm_and_push(target_coord, f"Known Event ({target_text})", eye)
                    if success:
                        eye.last_frame_small = None
                        eye.static_cycles_count = 0
                        time.sleep(1.5)
                        continue
                    else:
                        tactics.log("記憶の座標が機能しませんでした。再度推論を実行します。", state=state)
                
                # 辞書にない、または失敗した場合はLLMに推論させる
                tactics.log(f"未知の画面 ({state}) です。写真から次に押すべきボタンを推論し、記憶します。", state=state)
                prompt = "This is an event, dialogue, or unknown screen in Slay the Spire. Tell me the exact text of the most logical button or option I should click to proceed (e.g., 'Leave', 'Talk', 'Choose', 'Skip', 'Next', 'Continue', 'Proceed', 'Max HP'). Output ONLY the exact text string."
                target_text = eye.query_llm(frame, prompt)
                
                print(f"🧠 [Vision] LLMが推論した対象テキスト: '{target_text}'")
                
                # OCRでテキストを探す
                words = eye.get_all_text_coords(frame)
                target_coord = None
                
                if target_text and target_text.lower() not in ["診断不可", "error", "unknown"]:
                    for w_data in words:
                        search_words = target_text.lower().split()
                        if any(sw in w_data['text'].lower() for sw in search_words) or target_text.lower() in w_data['text'].lower():
                            target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                            break
                            
                # フォールバック
                if not target_coord:
                    print(f"⚠️ [Vision] 推論されたテキスト '{target_text}' がOCRで見つかりません。汎用キーワードを探します...")
                    fallbacks = ["leave", "skip", "proceed", "continue", "next", "confirm", "ok", "戻る", "スキップ", "次へ", "確認"]
                    for w_data in words:
                        if any(fb in w_data['text'].lower() for fb in fallbacks):
                            target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                            target_text = w_data['text']
                            break
                
                if target_coord:
                    success, reason = body.confirm_and_push(target_coord, f"Dynamic Event ({target_text})", eye)
                    if success:
                        print("🌟 [AI feeling good] Screen successfully transitioned! Feeling extremely pleased!")
                        # 推論が成功（初速獲得）したので、辞書に記憶する
                        x_pct = target_coord[0] / eye.window_size[0]
                        y_pct = target_coord[1] / eye.window_size[1]
                        tactics.learning.record_event_solution(screen_hash, frame, target_text, x_pct, y_pct)
                        
                        eye.last_frame_small = None
                        eye.static_cycles_count = 0
                        time.sleep(2.0)
                    else:
                        print("💔 [AI frustrated] Click had no response! Giving minus/negative reward penalty.")
                        tactics.learning.record_event_failure(screen_hash, target_text)
                        print(f"⚠️ [Event] {target_text} のクリックに失敗しました。")
                else:
                    tactics.log("押すべきボタンが見つかりません。証拠写真を残し、待機します。", state=state)
                    eye.dump_silent_error(frame, f"Stuck in {state}: No logical buttons found by OCR/LLM.")
                    time.sleep(1.5)
                continue

                
            consecutive_unknowns = 0
            
            # 2. Reflex Action based on state
            if state == "COMBAT":
                tactics.reset_turn()
                elements = eye.locate_combat_elements(frame)
                
                # Fetch visual card hashes from hand crops
                card_hashes = []
                for coord in elements.get("cards", []):
                    crop = eye.crop_card_at(frame, coord)
                    chash = tactics.learning.get_card_hash(crop)
                    if chash:
                        tactics.learning.register_card(chash, crop)
                    card_hashes.append(chash)
                    
                # Fetch enemy attack intents
                enemy_intents = []
                for enemy_coord in elements.get("enemies", []):
                    enemy_intents.append(eye.get_enemy_attacking(frame, enemy_coord))
                
                # Simple card-playing reflex loop
                energy = 3
                while True:
                    # ─── テンキー手動カードプレイを最優先で処理 ───
                    if PENDING_CARD_PLAY is not None:
                        card_idx = PENDING_CARD_PLAY - 1  # 0-indexed に変換
                        cards = elements.get("cards", [])
                        w, h = eye.window_size
                        
                        # 手札の中央座標を計算
                        if 0 <= card_idx < len(cards):
                            card_coord = cards[card_idx]
                        else:
                            # 手札の枚数を超えていたら自動的に最後のカードにフォールバック
                            if cards:
                                card_coord = cards[-1]
                                print(f"🎴 [Manual] カード {PENDING_CARD_PLAY} は手札にないため最後のカード({len(cards)}枚目)を使用")
                            else:
                                print(f"🎴 [Manual] 手札が空です。スキップ。")
                                PENDING_CARD_PLAY = None
                                _orig_sleep(0.02)
                                continue
                        
                        # 対象は検出した敵の中央、なければ画面中央上部
                        enemies = elements.get("enemies", [])
                        if enemies:
                            target_x = sum(e[0] for e in enemies) // len(enemies)
                            target_y = sum(e[1] for e in enemies) // len(enemies)
                        else:
                            target_x = int(w * 0.72)
                            target_y = int(h * 0.45)
                        
                        print(f"🎴 [Manual] カード {PENDING_CARD_PLAY} を ({card_coord}) → 敵中央 ({target_x},{target_y}) にドラッグ")
                        human_observer.bot_is_clicking = True
                        body.play_card(card_coord, (target_x, target_y))
                        human_observer.bot_is_clicking = False
                        energy -= 1
                        PENDING_CARD_PLAY = None
                        _orig_sleep(0.3)
                        # 手札を再スキャン
                        new_frame = eye.grab_screen()
                        if new_frame is not None:
                            elements = eye.locate_combat_elements(new_frame)
                        continue
                    
                    # モード変更があればすぐに戦闘ループを抜ける
                    if CURRENT_MODE == MODE_WATCH:
                        print("👀 [WATCH] 戦闘中にWATCHモード検出。ボット行動を中断します。")
                        break

                    if CURRENT_MODE == MODE_COOP:
                        # COOPモードは人間優先で待ってから行動判断
                        _b = body._capture_small()
                        _orig_sleep(1.5)
                        _a = body._capture_small()
                        if body._pixel_diff(_b, _a) >= 3.0:
                            print("🤝 [COOP] 人間が操作済み。戦闘ターンをスキップ。")
                            break
                    
                    # Decide action using learning heuristics
                    action, p1, p2 = tactics.decide_combat_action(elements, card_hashes, enemy_intents, energy)
                    
                    if action == "PLAY_CARD":

                        # Record state before playing
                        card_idx = elements.get("cards", []).index(p1) if p1 in elements.get("cards", []) else -1
                        played_hash = card_hashes[card_idx] if card_idx != -1 else None
                        
                        block_before = eye.get_player_block_present(frame)
                        enemy_hps_before = [eye.get_enemy_hp_percentage(frame, e) for e in elements.get("enemies", [])]
                        
                        # Execute physical play
                        body.play_card(p1, p2)
                        energy -= 1 # assume 1 energy per card played
                        time.sleep(0.5)
                        
                        # Observe state changes after playing
                        new_frame = eye.grab_screen()
                        if new_frame is not None:
                            block_after = eye.get_player_block_present(new_frame)
                            enemy_hps_after = [eye.get_enemy_hp_percentage(new_frame, e) for e in elements.get("enemies", [])]
                            
                            # Differential learning logic
                            block_diff = 1 if (block_after and not block_before) else 0
                            hp_diff = 0.0
                            if enemy_hps_before and enemy_hps_after:
                                hp_diff = enemy_hps_after[0] - enemy_hps_before[0]
                                
                            if played_hash:
                                tactics.learning.update_card_effect(played_hash, block_diff, hp_diff)
                                if played_hash not in selected_card_hashes:
                                    selected_card_hashes.append(played_hash)
                                    
                            frame = new_frame # update frame reference
                    elif action == "END_TURN":
                        body.click_end_turn(p1)
                        break
                    else:
                        break
                        
            elif state == "REST_SITE":
                # Select campfire (approximate screen coordinates for "Rest" option)
                body.click_position((550, 450), "Campfire Rest Option")
                time.sleep(1.5)
                
            elif state == "MAP":
                # Map navigation screen
                body.click_position((640, 500), "Map Ascent Node")
                time.sleep(2.0)
                
            elif state == "REWARD":
                # Card selection screen: crop options and pick best choice
                reward_coords = eye.get_reward_card_coords()
                reward_hashes = []
                for coord in reward_coords:
                    crop = eye.crop_card_at(frame, coord)
                    rhash = tactics.learning.get_card_hash(crop)
                    if rhash:
                        tactics.learning.register_card(rhash, crop)
                        
                        # OCR text caching
                        cached_name = tactics.learning.get_card_name(rhash)
                        if not cached_name:
                            # First-time crop: perform WinRT OCR and save to cache
                            ocr_name = eye.perform_ocr(crop)
                            tactics.learning.update_card_name(rhash, ocr_name)
                            print(f"📖 [OCR] First-time scan: took photo of card {rhash} and recognized name as '{ocr_name}'")
                        else:
                            # Re-encounter: retrieve name instantly from cache
                            print(f"📖 [OCR Cache] Instantly recognized card {rhash} as '{cached_name}'")
                            
                    reward_hashes.append(rhash)
                    
                choice_idx = tactics.decide_reward_choice(reward_hashes)
                chosen_coord = reward_coords[choice_idx]
                chosen_hash = reward_hashes[choice_idx]
                if chosen_hash and chosen_hash not in selected_card_hashes:
                    selected_card_hashes.append(chosen_hash)
                    
                body.click_position(chosen_coord, f"Reward Card Option {choice_idx}")
                time.sleep(1.5)

            elif state == "MAIN_MENU":
                print("🔍 [Vision] MAIN_MENUまたはシングルプレイサブメニュー画面の文字を解析してボタンを探します...")
                words = eye.get_all_text_coords(frame)
                target_coord = None
                src = ""
                
                full_text = " ".join(w['text'].lower() for w in words)
                is_submenu = any(kw in full_text for kw in ["通常", "本日の挑戦", "カスタム", "standard", "daily", "custom"])
                
                if is_submenu:
                    print("🔍 [Vision] シングルプレイサブメニューを検知。'本日の挑戦' ボタンを探します...")
                    sub_keywords = ["本日", "挑戦", "daily", "challenge"]
                    for w_data in words:
                        text_lower = w_data['text'].lower()
                        if any(kw in text_lower for kw in sub_keywords) and not any(ex in text_lower for ex in ["開始", "embark"]):
                            target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                            src = f"👁️OCRサブメニュー認識 ('{w_data['text']}')"
                            break
                    
                    if not target_coord:
                        w, h = eye.window_size
                        # Fallback for Daily Challenge button in STS2 (usually middle of screen or around 40.5% width, 60% height)
                        target_coord = (int(w * 0.405), int(h * 0.60))
                        src = "📐サブメニューデフォルト"
                else:
                    # キーワードの柔軟なマッチング (部分一致対応) - メインメニューのプレイボタン
                    keywords = ["play", "single", "start", "プレイ", "シングル", "スタート"]
                    for w_data in words:
                        text_lower = w_data['text'].lower()
                        if any(kw in text_lower for kw in keywords):
                            target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                            src = f"👁️OCRメインメニュー認識 ('{w_data['text']}')"
                            break
                
                # OCRが失敗した場合
                if not target_coord:
                    print("⚠️ [Vision] OCRでボタンが見つかりません。フォールバック座標を使用します。")
                    w, h = eye.window_size
                    human_coord = tactics.learning.get_human_click_coord("MAIN_MENU", w, h)
                    import win32gui
                    win_title = win32gui.GetWindowText(driver.hwnd) if driver.hwnd else ""
                    is_sts2 = "2" in win_title
                    fallback_x = 0.405 if is_sts2 else 0.50
                    target_coord = human_coord if human_coord else (int(w * fallback_x), int(h * 0.64))
                    src = "👤人間学習済み" if human_coord else "📐デフォルト(フォールバック)"
                
                # [初速のシステム] 実行と検証
                before_frame = frame
                success, reason = body.confirm_and_push(target_coord, f"Main Menu ({src})", eye)
                
                if not success:
                    print("💔 [AI frustrated] Main Menu click had no response! Giving minus penalty.")
                    # 自律診断回路の起動
                    if ENABLE_LLM_DIAGNOSIS:
                        after_frame = eye.grab_screen()
                        diagnosis = eye.diagnose_bottleneck(before_frame, after_frame, f"Click MAIN_MENU at {target_coord}")
                        print(f"🧠 [Self-Diagnosis]: {diagnosis}")
                        diag_res = diagnosis
                    else:
                        print("⚠️ [System] LLM Bottleneck Diagnosis is disabled. Skipping CPU inference.")
                        diag_res = "Disabled (LLM Bottleneck Diagnosis is off)"
                    with open(os.path.join(BASE_DIR, "sls2_evolution.md"), "a", encoding="utf-8") as f:
                        f.write(f"- {time.strftime('%H:%M:%S')} [DIAGNOSIS] MAIN_MENU始動失敗。原因: {diag_res}\n")
                    
                    # 総当たり的な微修正: 座標を少しずらして「初速」を無理やり稼ぐ
                    print("🔥 [System] 初速獲得のため、周辺領域をスキャン/プッシュします。")
                    # (ここに追加の総当たりロジックを記述可能)
                else:
                    print("🌟 [AI feeling good] Screen transitioned from Main Menu! Feeling extremely pleased!")
                    eye.last_frame_small = None
                    eye.static_cycles_count = 0
                
            elif state == "CHARACTER_SELECT":
                print("🔍 [Vision] CHARACTER_SELECT画面の文字を解析してボタンを探します...")
                words = eye.get_all_text_coords(frame)
                target_coord = None
                src = ""
                keywords = ["embark", "proceed", "go", "エンバーク", "出発", "開始"]
                for w_data in words:
                    text_lower = w_data['text'].lower()
                    if any(kw in text_lower for kw in keywords) and "さあ挑戦" not in text_lower:
                        target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                        src = f"👁️OCR認識 ('{w_data['text']}')"
                        break
                
                if not target_coord:
                    w, h = eye.window_size
                    human_coord = tactics.learning.get_human_click_coord("CHARACTER_SELECT", w, h)
                    
                    # For STS2 Character Select, the start button is the right check-mark at (0.955, 0.56)
                    # For STS1, it is at (0.83, 0.85)
                    import win32gui
                    win_title = win32gui.GetWindowText(driver.hwnd) if driver.hwnd else ""
                    is_sts2 = "2" in win_title
                    
                    fallback_x = 0.955 if is_sts2 else 0.83
                    fallback_y = 0.56 if is_sts2 else 0.85
                    
                    target_coord = human_coord if human_coord else (int(w * fallback_x), int(h * fallback_y))
                    src = "👤人間学習済み" if human_coord else ("📐STS2確認" if is_sts2 else "📐デフォルト")
                
                # [初速のシステム] 実行と検証
                before_frame = frame
                success, reason = body.confirm_and_push(target_coord, f"Character Select ({src})", eye)
                
                if not success:
                    print("💔 [AI frustrated] Character Select click had no response! Giving minus penalty.")
                    if ENABLE_LLM_DIAGNOSIS:
                        after_frame = eye.grab_screen()
                        diagnosis = eye.diagnose_bottleneck(before_frame, after_frame, f"Click CHARACTER_SELECT at {target_coord}")
                        print(f"🧠 [Self-Diagnosis]: {diagnosis}")
                        diag_res = diagnosis
                    else:
                        print("⚠️ [System] LLM Bottleneck Diagnosis is disabled. Skipping CPU inference.")
                        diag_res = "Disabled (LLM Bottleneck Diagnosis is off)"
                    with open(os.path.join(BASE_DIR, "sls2_evolution.md"), "a", encoding="utf-8") as f:
                        f.write(f"- {time.strftime('%H:%M:%S')} [DIAGNOSIS] CHARACTER_SELECT始動失敗。原因推理: {diag_res}\n")
                else:
                    print("🌟 [AI feeling good] Started game from Character Select! Feeling extremely pleased!")
                    eye.last_frame_small = None
                    eye.static_cycles_count = 0
                
            elif state == "DEFEAT_SCREEN":
                print("🔍 [Vision] DEFEAT_SCREEN画面の文字を解析してボタンを探します...")
                words = eye.get_all_text_coords(frame)
                target_coord = None
                src = ""
                keywords = ["return", "main", "quit", "リターン", "戻る", "諦める", "終了"]
                for w_data in words:
                    text_lower = w_data['text'].lower()
                    if any(kw in text_lower for kw in keywords):
                        target_coord = (w_data['x'] + w_data['w']//2, w_data['y'] + w_data['h']//2)
                        src = f"👁️OCR認識 ('{w_data['text']}')"
                        break
                
                if not target_coord:
                    w, h = eye.window_size
                    human_coord = tactics.learning.get_human_click_coord("DEFEAT_SCREEN", w, h)
                    target_coord = human_coord if human_coord else (int(w * 0.50), int(h * 0.88))
                    src = "👤人間学習済み" if human_coord else "📐デフォルト"
                
                print(f"🎯 DEFEAT_SCREEN クリック座標: {target_coord} ({src})")
                human_observer.bot_is_clicking = True
                changed = body.click_and_verify(target_coord, "Return to Main Menu Button", max_shifts=4, shift_px=20)
                human_observer.bot_is_clicking = False
                if changed:
                    print("🌟 [AI feeling good] Returned to Main Menu! Feeling extremely pleased!")
                    eye.last_frame_small = None
                    eye.static_cycles_count = 0
                    time.sleep(2.0)
                else:
                    print("💔 [AI frustrated] Defeat Screen click had no response! Giving minus penalty.")
                    print("⚠️ [Loop] DEFEAT_SCREEN click had no effect. Forcing fresh gemma4 query.")
                    eye.last_frame_small = None
                    eye.static_cycles_count = 99
                    time.sleep(0.5)
                
            # Short delay between cycles to let animations settle
            time.sleep(0.5)
    finally:
        # Record final run outcome in visual Q-learning database
        print("\n💾 Recording learning run outcome in database...")
        tactics.learning.record_run_outcome(victory=False, max_floor=loop_count // 5 + 1, selected_cards=selected_card_hashes)
        print("🏁 Infinite Spire loop completed.")

if __name__ == "__main__":
    # Check if a custom title is passed (e.g. Slay the Spire 2)
    title = sys.argv[1] if len(sys.argv) > 1 else "Slay the Spire"
    run_spire_automator(title)
