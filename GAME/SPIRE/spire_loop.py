import os
import sys
import time
import json
import cv2
import re
import glob
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
from spire_learning import HumanObserver, STANDARD_CARDS, parse_card_cost_and_clean_name, guess_card_category
from CORE.ai_driver import AIDriver

import spire_utils as utils
from spire_brain import SpireBrain

def scan_and_hash_hand_cards(eye, frame, elements, tactics):
    card_hashes = []
    for coord in elements.get("cards", []):
        crop = eye.crop_card_at(frame, coord)
        chash = tactics.learning.get_card_hash(crop)
        if chash:
            tactics.learning.register_card(chash, crop)
            cached_name = tactics.learning.get_card_name(chash)
            if not cached_name:
                ocr_name = eye.perform_ocr(crop)
                if ocr_name:
                    cost, clean_name = parse_card_cost_and_clean_name(ocr_name)
                    cat = guess_card_category(clean_name)
                    tactics.learning.update_card_name(chash, clean_name, cost, cat)
                    print(f"📖 [OCR In-Hand] Scanned card {chash}: recognized as '{clean_name}' (Cost: {cost}, Cat: {cat})")
        card_hashes.append(chash)
    return card_hashes

def parse_energy_from_ocr(words):
    """OCRテキストリストからエネルギー (X/Y形式、X,Y<=9) を読み取る"""
    for w_data in words:
        text = w_data['text'].strip()
        match = re.search(r'(\d+)/(\d+)', text)
        if match:
            try:
                val1 = int(match.group(1))
                val2 = int(match.group(2))
                if val1 <= 9 and val2 <= 9:
                    return val1
            except:
                pass
    return None

def launch_game_if_needed():
    import win32gui
    import subprocess
    import os
    hwnds = []
    def enum_cb(h, extra):
        if win32gui.IsWindowVisible(h):
            title = win32gui.GetWindowText(h).strip()
            if "spire" in title.lower() or "slay" in title.lower():
                extra.append(h)
    try:
        win32gui.EnumWindows(enum_cb, hwnds)
    except Exception:
        pass
    if not hwnds:
        print("🚀 [System] Slay the Spire 2 is not running. Launching game...")
        direct_path = r"C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.exe"
        if os.path.exists(direct_path):
            try:
                subprocess.Popen(direct_path, cwd=os.path.dirname(direct_path))
                print("🚀 [System] Direct launch command executed.")
            except Exception as e:
                print(f"⚠️ [System] Direct launch failed: {e}")
        else:
            try:
                subprocess.Popen('start "" "steam://rungameid/2405740"', shell=True)
                print("🚀 [System] Steam launch command executed.")
            except Exception as e:
                print(f"⚠️ [System] Steam launch failed: {e}")
        time.sleep(8.0) # Wait for launch resources

def try_claim_central_reward(body, eye):
    """
    Attempts to click central screen coordinates where relics, chests, or card packs appear.
    Returns True if a click caused a screen change (meaning a reward was claimed or chest opened),
    False if no rewards were claimed.
    """
    w, h = eye.window_size
    # Target points in logical coordinates: center (relic/chest), left-center (boss relic 1 / card pack 1),
    # right-center (boss relic 3 / card pack 2), center-middle (boss relic 2)
    reward_coords = [
        (int(w * 0.50), int(h * 0.45)),  # Single relic / Chest
        (int(w * 0.40), int(h * 0.50)),  # Left option (Boss relic 1 / Card pack 1)
        (int(w * 0.60), int(h * 0.50)),  # Right option (Boss relic 3 / Card pack 2)
        (int(w * 0.50), int(h * 0.50)),  # Center option (Boss relic 2)
    ]
    
    for coord in reward_coords:
        x_pct = coord[0] / w
        y_pct = coord[1] / h
        if body.learning and body.learning.is_failed_click("REWARD_CHECK", x_pct, y_pct):
            continue
            
        before = body._capture_small()
        if before is None:
            continue
            
        print(f"🔍 [Reward Check] Clicking potential reward coordinate at {coord}...")
        body.wait_for_active_window()
        body.driver.bezier_move(coord[0], coord[1])
        time.sleep(0.1)
        body.driver.hardware_click(coord[0], coord[1])
        
        # Wait and verify screen change
        time.sleep(0.3)
        after = body._capture_small()
        diff = body._pixel_diff(before, after)
        print(f"🔍 [Reward Check] Screen diff: {diff:.2f}")
        
        if diff >= 7.0:
            print(f"🎁 [Reward Check] Succeeded! Screen changed (diff={diff:.2f}). Claimed reward or opened chest at {coord}.")
            eye.last_frame_small = None
            eye.static_cycles_count = 0
            return True
        else:
            if body.learning:
                body.learning.record_failed_click("REWARD_CHECK", x_pct, y_pct)
                
    return False

def log_and_visualize_current_location(frame, save_data, eye, best_visited_cv, next_coords, scored_next, points):
    """
    Saves a debug screenshot of the map screen showing the current location (red circle)
    and the valid next moves (green circles) with their scores, and logs the current status.
    """
    if frame is None:
        return
        
    try:
        annotated_frame = frame.copy()
        current_node_desc = "Start of Act (No visited nodes yet)"
        visited = []
        
        if save_data:
            visited = save_data.get('visited_map_coords', [])
            if visited:
                curr_node = visited[-1]
                col = curr_node.get('col', 0)
                row = curr_node.get('row', 0)
                node_type = "unknown"
                for p in points:
                    if p.get('coord') == curr_node:
                        node_type = p.get('type', 'unknown')
                        break
                current_node_desc = f"Row {row}, Column {col} (Type: {node_type})"
                
        ch, cw, _ = frame.shape
        
        if best_visited_cv:
            cv2.circle(annotated_frame, best_visited_cv, 25, (0, 0, 255), 4) # Red BGR
            cv2.putText(annotated_frame, "YOU ARE HERE", (best_visited_cv[0] - 80, best_visited_cv[1] - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            if save_data and visited:
                curr_node = visited[-1]
                col = curr_node.get('col', 0)
                curr_x_pct = 0.25 + 0.50 * (col / 6.0)
                curr_y_pct = 0.58
                est_x = int(cw * curr_x_pct)
                est_y = int(ch * curr_y_pct)
                cv2.circle(annotated_frame, (est_x, est_y), 25, (0, 0, 255), 4)
                cv2.putText(annotated_frame, "YOU ARE HERE (EST)", (est_x - 100, est_y - 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                            
        print(f"🗺️ [Map Visualizer] Next choices to draw: {scored_next}")
        for next_coord_data, n_type, score in scored_next:
            ncol = next_coord_data.get('col', 0)
            nrow = next_coord_data.get('row', 0)
            nx_pct = 0.25 + 0.50 * (ncol / 6.0)
            
            if not visited:
                ny_pct = 0.91
            else:
                curr_row = visited[-1].get('row', 0)
                row_diff = nrow - curr_row
                curr_y_pct_detected = 0.58
                if best_visited_cv:
                    curr_y_pct_detected = best_visited_cv[1] / ch
                ny_pct = curr_y_pct_detected - 0.08 - (row_diff - 1) * 0.13
                
            est_nx = int(cw * nx_pct)
            est_ny = int(ch * ny_pct)
            
            nodes = eye.detect_map_nodes(frame)
            best_cv_node = None
            min_x_dist = 9999.0
            y_min = ny_pct - 0.04
            y_max = ny_pct + 0.04
            for nx, ny in nodes:
                cv_x_pct = nx / cw
                cv_y_pct = ny / ch
                if y_min <= cv_y_pct <= y_max:
                    x_dist = abs(cv_x_pct - nx_pct)
                    if x_dist < 0.08 and x_dist < min_x_dist:
                        min_x_dist = x_dist
                        best_cv_node = (nx, ny)
                        
            draw_x, draw_y = (best_cv_node if best_cv_node else (est_nx, est_ny))
            
            cv2.circle(annotated_frame, (draw_x, draw_y), 20, (0, 255, 0), 3) # Green BGR
            label_text = f"{n_type} (Score: {score})"
            cv2.putText(annotated_frame, label_text, (draw_x - 60, draw_y - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
        saves_dir = os.path.join(BASE_DIR, "saves")
        os.makedirs(saves_dir, exist_ok=True)
        img_path = os.path.join(saves_dir, "map_current_location.png")
        cv2.imwrite(img_path, annotated_frame)
        print(f"📸 [Map Visualizer] Saved annotated map screen to: saves/map_current_location.png")
        
        log_path = os.path.join(saves_dir, "map_current_location.txt")
        log_text = f"""=========================================
Slay the Spire 2 Map Status Log
=========================================
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}
Current Node: {current_node_desc}
Next Valid Paths:
"""
        for next_coord_data, n_type, score in scored_next:
            ncol = next_coord_data.get('col', 0)
            nrow = next_coord_data.get('row', 0)
            log_text += f"- Col {ncol}, Row {nrow} (Type: {n_type}, Priority Score: {score})\n"
            
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_text)
        print(f"📝 [Map Visualizer] Wrote location details to: saves/map_current_location.txt")
        
    except Exception as e:
        print(f"⚠️ [Map Visualizer] Failed to create map visualization: {e}")

def run_spire_automator(target_title="Slay the Spire", max_loops=100000):
    global PENDING_CARD_PLAY
    print("🎵 Starting Autonomous Slay the Spire Infinite Loop (SPIRE)...")
    print("=" * 55)
    print("  ⌨️  キーボード操作ガイド:")
    print("  [ 1 + 2 ] → AUTO ↔ WATCH 切替（一時停止/再開）")
    print("  [ 1 + 3 ] → WATCH モード（監視・学習専用）")
    print("  [ 1 + 4 ] → COOP  モード（人間+ボット協力）")
    print("  ─────────────────────────────────────────────")
    print("  [ テンキー 1〜9 ] → その番号 of カードを敵中央にドラッグ")
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
        print("🔍 Slay the Spire window not found! Waiting for game to be launched manually...")
        while not driver.hwnd:
            time.sleep(2.0)
            for title in ["Slay the Spire 2", "Slay the Spire"]:
                driver.target_title = title
                if driver.connect():
                    target_title = title
                    print(f"✅ Bound to game window: '{title}'")
                    break
        
    eye = SpireEye(driver)
    tactics = SpireTactics()
    brain = SpireBrain(eye, None, tactics)
    
    # Run startup pre-scanning of card templates in database folder
    tactics.learning.initialize_card_categories(eye=eye)
    
    # 人間操作の観察・学習スレッドを起動
    human_observer = HumanObserver(driver, tactics.learning)
    human_observer.start()
    
    # 毎秒スクショ&1分削除の管理クラスを起動
    from spire_learning import ScreenshotCacheManager
    cache_manager = ScreenshotCacheManager(driver)
    cache_manager.start()
    
    body = SpireBody(driver, human_observer, cache_manager, learning=tactics.learning)
    # Re-link brain to body with the now-initialized body
    brain.body = body
    
    loop_count = 0
    consecutive_unknowns = 0
    selected_card_hashes = []
    last_reflection_time = time.time()
    last_state = "UNKNOWN"
    map_scroll_initialized = False
    
    # Spinal quick loop
    try:
        while loop_count < max_loops:
            try:
                import win32api
                mx, my = win32api.GetCursorPos()
                print(f"📍 Current Mouse Position: ({mx}, {my})")
            except Exception:
                pass

            # Check window connection — 再接続を試みる（自動起動は行いません）
            if not driver.check_connection() or not driver.hwnd:
                print("⚠️ Slay the Spire ウィンドウが見つかりません。再接続を試みます...")
                reconnected = False
                for attempt in range(30):
                    _orig_sleep(2.0)
                    for title in ["Slay the Spire 2", "Slay the Spire"]:
                        driver.target_title = title
                        if driver.connect():
                            print(f"✅ 再接続成功: '{title}'")
                            reconnected = True
                            break
                    if reconnected:
                        break
                    print(f"  再接続試行 {attempt+1}/30...")
                if not reconnected:
                    print("❌ 再接続できませんでした。ゲームウィンドウが起動されるのを待機します...")
                    while not reconnected:
                        _orig_sleep(5.0)
                        for title in ["Slay the Spire 2", "Slay the Spire"]:
                            driver.target_title = title
                            if driver.connect():
                                print(f"✅ 接続成功: '{title}'")
                                reconnected = True
                                break


            loop_count += 1
            print(f"\n🔄 --- Loop Cycle {loop_count} [{CURRENT_MODE}] ---")
            
            # ─── Puppet Command Check ───
            hints_path = os.path.join(BASE_DIR, "saves", "puppet_hints.json")
            if os.path.exists(hints_path):
                try:

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

            # Load current run save data
            save_data = utils.load_current_run_save()
            relics = []
            if save_data and "players" in save_data and save_data["players"]:
                relics = save_data["players"][0].get("relics", [])

            # 1. Eye: grab screen frame
            frame = eye.grab_screen()
            state = eye.detect_game_state(frame)
            print(f"👁️ Detected Game State: {state}")
            
            # --- Visual Debug Trigger (Photo Analysis Mode) ---
            if state != last_state or state == "UNKNOWN":
                words = eye.get_all_text_coords(frame)
                elements = eye.locate_combat_elements(frame) if state == "COMBAT" else {}
                vis_path = eye.visualize_sight(frame, words, elements, state)
                if vis_path:
                    print(f"📸 [Vision] Analysis Map saved to: assets/debug_sight.png (State: {state})")
            
            # --- Deck Size Tracker ---
            if save_data and "players" in save_data and save_data["players"]:
                try:
                    deck_size = len(save_data["players"][0].get("deck", []))
                    print(f"🃏 [Deck Tracker] Current Deck Size from save: {deck_size}")
                    tactics.learning.record_deck_size(state, deck_size)
                except Exception as e:
                    print(f"⚠️ [Deck Tracker] Error tracking deck: {e}")
            
            # --- State Transition Watcher & Failed Clicks Reset ---
            if state != last_state:
                if last_state == "MAP":
                    map_scroll_initialized = False
                
                # Clear failed clicks for the previous state or screen hash to prevent permanent blockages
                if last_state in ["UNKNOWN", "EVENT"]:
                    prev_hash = getattr(human_observer, '_current_screen_hash', None)
                    if prev_hash:
                        tactics.learning.clear_failed_clicks(prev_hash)
                else:
                    tactics.learning.clear_failed_clicks(last_state)
                tactics.learning.clear_failed_clicks("REWARD_CHECK")
                    
                try:
                    utils.save_state_analysis(BASE_DIR, state, frame, eye)
                except Exception as ex:
                    print(f"⚠️ [Analysis] Error in state analysis: {ex}")
            
            if state == "MAP" and not map_scroll_initialized:
                print("🗺️ [Map Transition] Entered MAP screen. Performing path inspection scroll (Top then Bottom)...")
                try:
                    w, h = eye.window_size
                    body.driver.bezier_move(int(w * 0.5), int(h * 0.5))
                    time.sleep(0.3)
                    utils.scroll_map('down', ticks=60) # Scroll all the way to the top (boss)
                    time.sleep(2.0)
                    utils.scroll_map('up', ticks=80) # Scroll all the way back to the bottom (start)
                    time.sleep(1.0)
                    map_scroll_initialized = True
                except Exception as e:
                    print(f"⚠️ [Map Transition] Scroll failed: {e}")
            
            last_state = state
            
            # --- 1分ごとの反省会ログ記録 ---
            if time.time() - last_reflection_time >= 60.0:
                try:
                    utils.write_reflection(BASE_DIR, loop_count, state)
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
                        body.play_card(_ccoord, (_tx, _ty), card_idx=_cidx)
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

            # ─── GLOBAL HIGH PRIORITY: Check for "進む" / "Proceed" / "続ける" / "Continue" ───
            if state not in ["MAIN_MENU", "CHARACTER_SELECT", "MAP"]:
                words = eye.get_all_text_coords(frame)
                proceed_coord = None
                proceed_text = ""
                proceed_bounds = None
                for w_data in words:
                    text_clean = w_data['text'].strip().replace(" ", "").replace("　", "")
                    text_clean_lower = text_clean.lower()
                    
                    # Calculate Y-percentage of the text box center
                    cy = w_data['y'] + w_data['h']//2
                    cap_h = eye.capture_size[1] if (hasattr(eye, 'capture_size') and eye.capture_size) else 1600
                    y_pct = cy / cap_h
                    
                    if "進む" in text_clean or "続ける" in text_clean or "proceed" in text_clean_lower or "continue" in text_clean_lower:
                        # Only click if in the bottom region and short length, avoiding main story paragraphs
                        if y_pct > 0.55 and len(text_clean) < 15:
                            proceed_coord = (w_data['x'] + w_data['w']//2, cy)
                            proceed_text = w_data['text']
                            w_x1, w_y1 = eye.to_logical((w_data['x'], w_data['y']))
                            w_x2, w_y2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                            proceed_bounds = (w_x1, w_y1, w_x2, w_y2)
                            break
                
                if proceed_coord:
                    # Before pushing Proceed, check if there is an unclaimed central reward (relic/chest/pack)
                    if utils.try_claim_central_reward(body, eye):
                        continue
                    logical_coord = eye.to_logical(proceed_coord)
                    print(f"🎯 [Priority Proceed] Detected '{proceed_text}' on screen at {proceed_coord} -> logical {logical_coord}. Clicking immediately!")
                    success, reason = body.confirm_and_push(logical_coord, f"Priority Proceed Click OCR ({proceed_text})", eye, bounds=proceed_bounds)
                    if success:
                        print("🌟 [Priority Proceed] Successfully pressed Proceed button!")
                        eye.last_frame_small = None
                        eye.static_cycles_count = 0
                        time.sleep(0.4)
                        continue
                    else:
                        print("⚠️ [Priority Proceed] Click on Proceed button failed. Continuing to state-specific handling.")

            if state in ["UNKNOWN", "EVENT"]:
                # Before selecting dialogue options, check if there is a central reward to claim
                if utils.try_claim_central_reward(body, eye):
                    continue
                # [王道原理] まず記憶（イベント辞書）を探る
                screen_hash = tactics.learning.get_screen_hash(eye.last_frame_small)
                human_observer.set_current_screen_hash(screen_hash)
                known_solution = tactics.learning.get_event_solution(screen_hash)
                
                if known_solution:
                    target_text = known_solution['text']
                    target_coord = (int(eye.window_size[0] * known_solution['x_pct']), int(eye.window_size[1] * known_solution['y_pct']))
                    tactics.log(f"この画面は記憶にあります。過去の成功体験に従い '{target_text}' を選択します。", state=state)
                    
                    success, reason = body.confirm_and_push(target_coord, f"Known Event ({target_text})", eye)
                    if success:
                        eye.last_frame_small = None
                        eye.static_cycles_count = 0
                        time.sleep(0.4)
                        continue
                    else:
                        tactics.log("記憶の座標が機能しませんでした。再度推論を実行します。", state=state)
                


                # ─── FAST HEURISTIC OPTIONS PICKER ───
                # Look for buttons in the event choice region: Y: 0.60 to 0.95, X: 0.15 to 0.75
                words = eye.get_all_text_coords(frame)
                event_options = []
                w_screen, h_screen = eye.window_size
                cap_w = eye.capture_size[0] if (hasattr(eye, 'capture_size') and eye.capture_size) else w_screen
                cap_h = eye.capture_size[1] if (hasattr(eye, 'capture_size') and eye.capture_size) else h_screen
                for w_data in words:
                    cx = w_data['x'] + w_data['w'] // 2
                    cy = w_data['y'] + w_data['h'] // 2
                    x_pct = cx / cap_w
                    y_pct = cy / cap_h
                    
                    if 0.60 <= y_pct <= 0.95 and 0.15 <= x_pct <= 0.75:
                        text = w_data['text'].strip()
                        if len(text) >= 2 and not text.isdigit():
                            p1 = eye.to_logical((w_data['x'], w_data['y']))
                            p2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                            logical_coord = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                            logical_bounds = (p1[0], p1[1], p2[0], p2[1])
                            event_options.append({
                                'text': text,
                                'coord': logical_coord,
                                'bounds': logical_bounds,
                                'x_pct': x_pct,
                                'y_pct': y_pct
                            })
                
                event_options = sorted(event_options, key=lambda opt: opt['y_pct'])
                target_coord = None
                target_text = None
                target_bounds = None
                
                if event_options:
                    print(f"🗺️ [Event Heuristics] Found {len(event_options)} event option candidates: {[opt['text'] for opt in event_options]}")
                    positive_kws = ["ゴールド", "獲得", "入手", "得", "レリック", "カード", "最大", "アップグレード", "強化", "スキップ", "進む", "続ける", "戻る", "確認", "了解", "同意", "次へ", "leave", "skip", "proceed", "continue", "next", "confirm", "ok"]
                    negative_kws = ["呪い", "失う", "ダメージ", "怪我", "痛み", "羞恥", "後悔", "めまい"]
                    
                    best_option = None
                    for opt in event_options:
                        txt_lower = opt['text'].lower()
                        has_pos = any(pw in txt_lower for pw in positive_kws)
                        has_neg = any(nw in txt_lower for nw in negative_kws)
                        if has_pos and not has_neg:
                            best_option = opt
                            break
                            
                    if not best_option:
                        for opt in event_options:
                            txt_lower = opt['text'].lower()
                            if not any(nw in txt_lower for nw in negative_kws):
                                best_option = opt
                                break
                                
                    if not best_option:
                        best_option = event_options[0]
                        
                    target_coord = best_option['coord']
                    target_text = best_option['text']
                    target_bounds = best_option['bounds']
                    print(f"🎯 [Event Heuristics] Selected best event option: '{target_text}' at {target_coord}")
                
                if not target_coord:
                    tactics.log(f"未知の画面 ({state}) です。擬似HTMLから次に押すべきボタンを推論し、記憶します。", state=state)
                    pseudo_html = eye.generate_pseudo_html(frame)
                    prompt = f"""This is an event, dialogue, shop, or unknown screen in Slay the Spire.
Analyze the following screen structure (represented as pseudo-HTML of visible elements):
{pseudo_html}

Tell me the exact text label of the most logical button or option I should click to proceed (e.g., 'Leave', 'Talk', 'Choose', 'Skip', 'Next', 'Continue', 'Proceed', 'Max HP'). Output ONLY the exact text string. Do not include tags, coordinates, or any explanation."""
                    target_text = eye.query_llm_text(prompt)
                    print(f"🧠 [Vision] LLMが推論した対象テキスト: '{target_text}'")
                    
                    if target_text and target_text.lower() not in ["診断不可", "error", "unknown"]:
                        for w_data in words:
                            search_words = target_text.lower().split()
                            if any(sw in w_data['text'].lower() for sw in search_words) or target_text.lower() in w_data['text'].lower():
                                p1 = eye.to_logical((w_data['x'], w_data['y']))
                                p2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                                target_coord = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                                target_bounds = (p1[0], p1[1], p2[0], p2[1])
                                break
                                
                    if not target_coord:
                        print(f"⚠️ [Vision] 推論されたテキスト '{target_text}' がOCRで見つかりません。汎用キーワードを探します...")
                        fallbacks = [
                            "leave", "skip", "proceed", "continue", "next", "confirm", "ok", 
                            "戻る", "スキップ", "次へ", "確認", "了解", "同意", "進む",
                            "変化させる", "追加する", "入手する", "獲得", "失う", "削除", 
                            "ゴールド", "レリック", "カード", "マックス", "呪い", "アップグレード", "強化"
                        ]
                        for w_data in words:
                            if any(fb in w_data['text'].lower() for fb in fallbacks):
                                p1 = eye.to_logical((w_data['x'], w_data['y']))
                                p2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                                target_coord = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                                target_text = w_data['text']
                                target_bounds = (p1[0], p1[1], p2[0], p2[1])
                                break
                
                if target_coord:
                    success, reason = body.confirm_and_push(target_coord, f"Dynamic Event ({target_text})", eye, bounds=target_bounds)
                    if success:
                        print("🌟 [AI feeling good] Screen successfully transitioned! Feeling extremely pleased!")
                        # 推論が成功（初速獲得）したので、辞書に記憶する
                        x_pct = target_coord[0] / eye.window_size[0]
                        y_pct = target_coord[1] / eye.window_size[1]
                        tactics.learning.record_event_solution(screen_hash, frame, target_text, x_pct, y_pct)
                        
                        eye.last_frame_small = None
                        eye.static_cycles_count = 0
                        time.sleep(0.4)
                    else:
                        print("💔 [AI frustrated] Click had no response! Giving minus/negative reward penalty.")
                        tactics.learning.record_event_failure(screen_hash, target_text)
                        print(f"⚠️ [Event] {target_text} のクリックに失敗しました。")
                else:
                    # Try checking for active teal confirm checkmark button as a visual fallback
                    checkmark_coord = eye.detect_teal_checkmark(frame)
                    if checkmark_coord:
                        logical_checkmark = eye.to_logical(checkmark_coord)
                        print(f"🎯 [Event] Teal checkmark detected at {checkmark_coord} -> logical {logical_checkmark}. Confirming selection...")
                        success, reason = body.confirm_and_push(logical_checkmark, "Confirm Checkmark Button", eye)
                        if success:
                            eye.last_frame_small = None
                            eye.static_cycles_count = 0
                            time.sleep(0.4)
                            continue

                    # フォールバック: OCR/LLMで見つからない場合、典型的な「進む」ボタン位置を順次試す
                    w, h = eye.window_size
                    proceed_candidates = [
                        ("画面下部中央 (進む/Proceed)", int(w * 0.50), int(h * 0.75)),
                        ("画面中央下 (確認)", int(w * 0.50), int(h * 0.65)),
                        ("画面右下 (チェックマーク)", int(w * 0.85), int(h * 0.70)),
                        ("画面中央 (OK/Next)", int(w * 0.50), int(h * 0.55)),
                    ]
                    
                    clicked_proceed = False
                    for label, px, py in proceed_candidates:
                        # 失敗済みの座標はスキップ
                        x_pct = px / w
                        y_pct = py / h
                        if tactics.learning.is_failed_click(state, x_pct, y_pct):
                            continue
                        
                        print(f"🔍 [Event] OCR/LLMで見つからず。{label} ({px},{py}) をフォールバッククリック...")
                        success, reason = body.confirm_and_push((px, py), f"Fallback Proceed ({label})", eye)
                        if success:
                            print(f"✅ [Event] {label} でのクリックが成功しました！")
                            tactics.learning.record_event_solution(screen_hash, frame, label, x_pct, y_pct)
                            eye.last_frame_small = None
                            eye.static_cycles_count = 0
                            clicked_proceed = True
                            time.sleep(0.4)
                            break
                        else:
                            tactics.learning.record_failed_click(state, x_pct, y_pct)
                    
                    if not clicked_proceed:
                        tactics.log("押すべきボタンが見つかりません。証拠写真を残し、待機します。", state=state)
                        eye.dump_silent_error(frame, f"Stuck in {state}: No logical buttons found by OCR/LLM or fallback clicks.")
                        time.sleep(1.5)
                continue

                
            consecutive_unknowns = 0
            
            # 2. Reflex Action based on state
            if state == "COMBAT":
                tactics.reset_turn()
                failed_hashes_this_turn = set()
                failed_indices_this_turn = set()
                
                # Perform a fresh OCR scan to update eye.last_ocr_words
                eye.get_all_text_coords(frame)
                
                # Read actual energy from OCR
                actual_energy = parse_energy_from_ocr(eye.last_ocr_words)
                if actual_energy is not None:
                    print(f"⚡ [OCR] Detected current energy: {actual_energy}")
                energy = actual_energy if actual_energy is not None else 3
                cards_played_this_turn = 0
                
                elements = eye.locate_combat_elements(frame, cards_played=cards_played_this_turn)
                
                # Fetch visual card hashes from hand crops
                card_hashes = scan_and_hash_hand_cards(eye, frame, elements, tactics)
                    
                # Fetch enemy attack intents
                enemy_intents = []
                for enemy_coord in elements.get("enemies", []):
                    enemy_intents.append(eye.get_enemy_attacking(frame, enemy_coord))
                
                # Simple card-playing reflex loop
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
                        body.play_card(card_coord, (target_x, target_y), card_idx=card_idx)
                        human_observer.bot_is_clicking = False
                        
                        cards_played_this_turn += 1
                        PENDING_CARD_PLAY = None
                        _orig_sleep(0.3)
                        # 手札を再スキャンとエネルギー検出
                        new_frame = eye.grab_screen()
                        if new_frame is not None:
                            new_words = eye.get_all_text_coords(new_frame)
                            actual_energy = parse_energy_from_ocr(new_words)
                            if actual_energy is not None:
                                energy = actual_energy
                                print(f"⚡ [OCR] Energy updated to: {energy}")
                            else:
                                energy = max(0, energy - 1)
                            elements = eye.locate_combat_elements(new_frame, cards_played=cards_played_this_turn)
                            card_hashes = scan_and_hash_hand_cards(eye, new_frame, elements, tactics)
                            frame = new_frame
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
                    
                    # Compile enemy HPs, statuses, and incoming damage
                    enemy_hps = []
                    enemy_statuses = []
                    incoming_damage = 0
                    for idx, e in enumerate(elements.get("enemies", [])):
                        ocr_hp = eye.get_enemy_hp_from_ocr(eye.last_ocr_words, e, frame.shape)
                        if ocr_hp:
                            enemy_hps.append(ocr_hp[0]) # current HP
                        else:
                            pct = eye.get_enemy_hp_percentage(frame, e)
                            enemy_hps.append(int(pct * 50))
                            
                        # Compile status effects for this enemy
                        enemy_statuses.append(eye.get_enemy_statuses(eye.last_ocr_words, e, frame.shape))
                        
                        # Compile incoming damage from enemy intent
                        dmg = eye.get_enemy_intent_damage(eye.last_ocr_words, e, frame.shape)
                        if dmg > 0:
                            incoming_damage += dmg
                        elif idx < len(enemy_intents) and enemy_intents[idx]:
                            incoming_damage += 10 # fallback default damage if attacking
                        
                    # Compile player status effects
                    player_statuses = eye.get_player_statuses(eye.last_ocr_words, frame.shape[1], frame.shape[0])
                    
                    # Compile player HP & Block
                    player_hp = eye.get_player_hp(eye.last_ocr_words)
                    if player_hp:
                        print(f"❤️ [OCR] Detected player HP: {player_hp[0]}/{player_hp[1]}")

                    player_block = eye.get_player_block_from_ocr(eye.last_ocr_words)
                    print(f"🛡️ [OCR] Detected player block: {player_block} (Incoming enemy damage: {incoming_damage})")

                    # --- Potion Logic ---
                    if player_hp and (player_hp[0] / player_hp[1] < 0.40 or (incoming_damage - player_block >= 25)):
                        potion_coords = eye.get_potion_coords(frame)
                        if potion_coords:
                            p_coord = eye.to_logical(potion_coords[0])
                            print(f"🧪 [Potion] Player in danger! Attempting to use potion at {p_coord}...")
                            body.click_position(p_coord, "Use Potion")
                            time.sleep(0.5)
                            # After clicking potion, we may need to click a target (first enemy)
                            if elements.get("enemies"):
                                target = elements.get("enemies")[0]
                                body.click_position(target, "Potion Target")
                                time.sleep(0.5)
                            # Re-scan after potion usage
                            frame = eye.grab_screen()
                            eye.get_all_text_coords(frame)
                            elements = eye.locate_combat_elements(frame, cards_played=cards_played_this_turn)
                            card_hashes = scan_and_hash_hand_cards(eye, frame, elements, tactics)
                            continue
                    # Decide action using learning heuristics and passing failed hashes, indices, enemy HPs, statuses, player HP, damage, and block
                    action, p1, p2 = tactics.decide_combat_action(
                        elements, card_hashes, enemy_intents, energy,
                        failed_hashes=failed_hashes_this_turn,
                        failed_indices=failed_indices_this_turn,
                        enemy_hps=enemy_hps,
                        player_statuses=player_statuses,
                        enemy_statuses=enemy_statuses,
                        player_hp=player_hp,
                        incoming_damage=incoming_damage,
                        player_block=player_block,
                        relics=relics
                    )
                    
                    if action == "PLAY_CARD":
 
                        # Record state before playing
                        card_idx = elements.get("cards", []).index(p1) if p1 in elements.get("cards", []) else -1
                        played_hash = card_hashes[card_idx] if (card_idx != -1 and card_idx < len(card_hashes)) else None
                        
                        before_cards_count = len(elements.get("cards", []))
                        
                        # Execute physical play
                        body.play_card(p1, p2, card_idx=card_idx)
                        cards_played_this_turn += 1
                        time.sleep(0.2)
                        
                        # Observe state changes after playing
                        new_frame = eye.grab_screen()
                        if new_frame is not None:
                            new_elements = eye.locate_combat_elements(new_frame, cards_played=cards_played_this_turn)
                            after_cards_count = len(new_elements.get("cards", []))
                            
                            # Check if card play failed or card remained/returned to hand
                            if after_cards_count >= before_cards_count:
                                print(f"⚠️ [Combat] Card play failed or card returned to hand. (played_hash: {played_hash})")
                                if played_hash:
                                    failed_hashes_this_turn.add(played_hash)
                                if card_idx != -1:
                                    failed_indices_this_turn.add(card_idx)
                            else:
                                # Successful card play logic
                                failed_indices_this_turn.clear()
                                block_before = eye.get_player_block_present(frame)
                                block_after = eye.get_player_block_present(new_frame)
                                enemy_hps_before = [eye.get_enemy_hp_percentage(frame, e) for e in elements.get("enemies", [])]
                                enemy_hps_after = [eye.get_enemy_hp_percentage(new_frame, e) for e in new_elements.get("enemies", [])]
                                
                                # Differential learning logic
                                block_diff = 1 if (block_after and not block_before) else 0
                                hp_diff = 0.0
                                if enemy_hps_before and enemy_hps_after:
                                    hp_diff = enemy_hps_after[0] - enemy_hps_before[0]
                                    
                                if played_hash:
                                    tactics.learning.update_card_effect(played_hash, block_diff, hp_diff)
                                    if played_hash not in selected_card_hashes:
                                        selected_card_hashes.append(played_hash)
                            
                            # Re-detect energy from OCR
                            new_words = eye.get_all_text_coords(new_frame)
                            actual_energy = parse_energy_from_ocr(new_words)
                            if actual_energy is not None:
                                energy = actual_energy
                                print(f"⚡ [OCR] Energy updated to: {energy}")
                            else:
                                if after_cards_count < before_cards_count:
                                    energy = max(0, energy - 1)
                                
                            elements = new_elements
                            
                            # Re-evaluate card hashes from hand crops for the next decision step
                            card_hashes = scan_and_hash_hand_cards(eye, new_frame, elements, tactics)
                                
                            frame = new_frame # update frame reference
                    elif action == "END_TURN":
                        body.click_end_turn(p1)
                        cards_played_this_turn = 0
                        break
                    else:
                        break
                        
            elif state == "REST_SITE":
                brain.handle_rest_site(frame, save_data)
                
            elif state == "MAP":
                # Map navigation screen
                w, h = eye.window_size # logical window size
                
                # Make sure mouse is centered so map doesn't drift, but do not scroll in cycles
                try:
                    body.driver.bezier_move(int(w * 0.5), int(h * 0.5))
                except: pass
                
                clicked_successfully = False
                if save_data:
                    try:
                        visited = save_data.get('visited_map_coords', [])
                        act_idx = save_data.get('current_act_index', 0)
                        acts = save_data.get('acts', [])
                        if act_idx < len(acts):
                            sm = acts[act_idx].get('saved_map', {})
                            points = sm.get('points', [])
                            start_coords = sm.get('start_coords', [])
                            
                            current_node = visited[-1] if visited else None
                            
                            # Crop and save current visited node (the top-most traversed black circle)
                            if current_node:
                                try:
                                    curr_col = current_node.get('col', 0)
                                    curr_row = current_node.get('row', 0)
                                    curr_x_pct = 0.25 + 0.50 * (curr_col / 6.0)
                                    curr_y_pct = 0.58
                                    
                                    best_visited_cv = None
                                    min_v_dist = 9999.0
                                    nodes = eye.detect_map_nodes(frame)
                                    for nx, ny in nodes:
                                        cv_x_pct = nx / eye.capture_size[0] if (hasattr(eye, 'capture_size') and eye.capture_size) else nx / 2560
                                        cv_y_pct = ny / eye.capture_size[1] if (hasattr(eye, 'capture_size') and eye.capture_size) else ny / 1600
                                        
                                        if 0.48 <= cv_y_pct <= 0.68:
                                            estimated_col = round((cv_x_pct - 0.25) * 12.0)
                                            if estimated_col == curr_col:
                                                dist = abs(cv_y_pct - curr_y_pct)
                                                if dist < min_v_dist:
                                                    min_v_dist = dist
                                                    best_visited_cv = (nx, ny)
                                                
                                    if best_visited_cv:



                                        vnx, vny = best_visited_cv
                                        ch, cw, _ = frame.shape
                                        x1 = max(0, vnx - 40)
                                        x2 = min(cw, vnx + 40)
                                        y1 = max(0, vny - 40)
                                        y2 = min(ch, vny + 40)
                                        
                                        vcrop = frame[y1:y2, x1:x2]
                                        assets_dir = os.path.join(BASE_DIR, "assets")
                                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                                        asset_path = os.path.join(assets_dir, f"visited_current_col{curr_col}_row{curr_row}_{timestamp}.png")
                                        cv2.imwrite(asset_path, vcrop)
                                        print(f"📸 [Assets] Saved visited current node crop to: assets/{os.path.basename(asset_path)}")
                                except Exception as v_err:
                                    print(f"⚠️ [Assets] Failed to save visited node crop: {v_err}")
                            
                            # Find connected next nodes
                            next_coords = []
                            if current_node:
                                start_node = sm.get('start', {})
                                if start_node and start_node.get('coord') == current_node:
                                    next_coords = start_node.get('children', [])
                                else:
                                    curr_points = [p for p in points if p.get('coord') == current_node]
                                    if curr_points:
                                        next_coords = curr_points[0].get('children', [])
                            else:
                                next_coords = start_coords
                                
                            print(f"🗺️ [Smart Map] Current Node: {current_node}, Next Valid Paths: {next_coords}")
                            
                            if next_coords:
                                player = save_data["players"][0]
                                gold = player.get("gold", 99)
                                hp_ratio = player.get("current_hp", 80) / max(1, player.get("max_hp", 80))
                                
                                scored_next = []
                                for coord in next_coords:
                                    node_pt = [p for p in points if p.get('coord') == coord]
                                    node_type = node_pt[0].get('type', 'monster') if node_pt else 'monster'
                                    
                                    # Score mapping
                                    score = 50
                                    if node_type == 'rest_site':
                                        score = 100 if hp_ratio < 0.6 else 80
                                    elif node_type == 'treasure':
                                        score = 95
                                    elif node_type == 'shop':
                                        score = 85 if gold >= 150 else (40 if gold >= 75 else 10)
                                    elif node_type == 'elite':
                                        score = 75 if hp_ratio >= 0.5 else 15
                                    elif node_type == 'unknown':
                                        score = 70
                                    elif node_type == 'monster':
                                        score = 50
                                    elif node_type == 'super_elite':
                                        score = 60 if hp_ratio >= 0.7 else 10
                                    elif node_type in ('boss', 'boss_chest'):
                                        score = 999  # Boss is always the final goal
                                        
                                    scored_next.append((coord, node_type, score))
                                    
                                scored_next.sort(key=lambda x: x[2], reverse=True)
                                print(f"🗺️ [Smart Map] Scored next options: {scored_next}")
                                try:
                                    log_and_visualize_current_location(frame, save_data, eye, best_visited_cv, next_coords, scored_next, points)
                                except Exception as e_vis:
                                    print(f"⚠️ Failed to visualize map location: {e_vis}")
                                
                                for target_coord_data, target_type, target_score in scored_next:
                                    target_col = target_coord_data.get('col', 0)
                                    target_row = target_coord_data.get('row', 0)
                                    
                                    # Target X-pct is calculated by dividing horizontal space
                                    x_pct = 0.25 + 0.50 * (target_col / 6.0)
                                    
                                    # Y range based on whether we are clicking the starting row
                                    if not visited:
                                        y_min, y_max = 0.70, 0.95
                                        fallback_y = 0.91
                                    else:
                                        curr_row = current_node.get('row', 0)
                                        row_diff = target_row - curr_row
                                        
                                        curr_y_pct_detected = 0.58
                                        if best_visited_cv:
                                            vnx, vny = best_visited_cv
                                            curr_y_pct_detected = vny / frame.shape[0]
                                            
                                        expected_y_pct = curr_y_pct_detected - 0.08 - (row_diff - 1) * 0.13
                                        y_min = expected_y_pct - 0.05
                                        y_max = expected_y_pct + 0.05
                                        fallback_y = expected_y_pct
                                    
                                    # Search matching CV node
                                    nodes = eye.detect_map_nodes(frame)
                                    best_cv_node = None
                                    min_y_dist = 9999.0
                                    
                                    for nx, ny in nodes:
                                        cv_x_pct = nx / eye.capture_size[0] if (hasattr(eye, 'capture_size') and eye.capture_size) else nx / 2560
                                        cv_y_pct = ny / eye.capture_size[1] if (hasattr(eye, 'capture_size') and eye.capture_size) else ny / 1600
                                        
                                        if y_min <= cv_y_pct <= y_max:
                                            # Map CV x_pct to logical column (0-6)
                                            estimated_col = round((cv_x_pct - 0.25) * 12.0)
                                            if estimated_col == target_col:
                                                y_dist = abs(cv_y_pct - fallback_y)
                                                if y_dist < min_y_dist:
                                                    min_y_dist = y_dist
                                                    best_cv_node = (nx, ny)
                                                
                                    if best_cv_node:
                                        target_click_coord = eye.to_logical(best_cv_node)
                                        print(f"🗺️ [Smart Map] Matched CV node {best_cv_node} -> logical {target_click_coord} for col {target_col}, row {target_row} ({target_type})")
                                    else:
                                        target_click_coord = (int(w * x_pct), int(h * fallback_y))
                                        print(f"🗺️ [Smart Map] Estimate direct coordinate {target_click_coord} for col {target_col}, row {target_row} ({target_type})")
                                        
                                    click_x_pct = target_click_coord[0] / w
                                    click_y_pct = target_click_coord[1] / h
                                    if tactics.learning.is_failed_click("MAP", click_x_pct, click_y_pct):
                                        print(f"🗺️ [Smart Map] Skipping click at {target_click_coord} because it previously failed.")
                                        continue
                                        
                                    human_observer.bot_is_clicking = True
                                    success = body.click_and_verify(target_click_coord, f"Smart Map Node (col {target_col}, row {target_row})", max_shifts=2, shift_px=10, change_threshold=2.0)
                                    human_observer.bot_is_clicking = False
                                    
                                    if success:
                                        print(f"✅ [Smart Map] Successfully clicked target node col {target_col}, row {target_row} ({target_type})!")
                                        
                                        # Crop and save target node asset
                                        if best_cv_node:
                                            try:



                                                nx, ny = best_cv_node
                                                ch, cw, _ = frame.shape
                                                x1 = max(0, nx - 40)
                                                x2 = min(cw, nx + 40)
                                                y1 = max(0, ny - 40)
                                                y2 = min(ch, ny + 40)
                                                
                                                tcrop = frame[y1:y2, x1:x2]
                                                assets_dir = os.path.join(BASE_DIR, "assets")
                                                timestamp = time.strftime("%Y%m%d_%H%M%S")
                                                asset_path = os.path.join(assets_dir, f"{target_type}_col{target_col}_row{target_row}_{timestamp}.png")
                                                cv2.imwrite(asset_path, tcrop)
                                                print(f"📸 [Assets] Saved target node crop to: assets/{os.path.basename(asset_path)}")
                                            except Exception as asset_err:
                                                print(f"⚠️ [Assets] Failed to save target node crop: {asset_err}")
                                                
                                        clicked_successfully = True
                                        eye.last_frame_small = None
                                        eye.static_cycles_count = 0
                                        time.sleep(0.4)
                                        break
                                    else:
                                        print(f"⚠️ [Smart Map] Click failed for node col {target_col}, row {target_row} ({target_type}).")
                    except Exception as ex:
                        print(f"⚠️ [Smart Map] Exception in smart map logic: {ex}")
                        
                if not clicked_successfully:
                    print("⚠️ [Smart Map] Current location or valid next paths could not be determined from game save files.")
                    print("🛑 [Smart Map] Blind CV clicking is disabled to prevent the bot from wandering to incorrect rooms.")
                    try:
                        saves_dir = os.path.join(BASE_DIR, "saves")
                        cv2.imwrite(os.path.join(saves_dir, "map_location_error.png"), frame)
                        print("📸 [Smart Map] Saved error screenshot to: saves/map_location_error.png")
                    except Exception as e:
                        print(f"⚠️ Failed to save error screenshot: {e}")
                        
                    print("👤 Please click the next map node manually. Waiting for room transition...")
                    while True:
                        time.sleep(2.0)
                        chk_frame = eye.grab_screen()
                        chk_state = eye.detect_game_state(chk_frame)
                        if chk_state != "MAP":
                            print(f"✅ Screen transitioned to state: {chk_state}. Resuming autopilot.")
                            break
                
            elif state == "REWARD":
                # Differentiate between Reward List Screen and Card/Relic Choice Screen
                w, h = eye.window_size
                words = eye.get_all_text_coords(frame)
                
                # Check for horizontal side-by-side layout in the middle height region to identify Choice Screens
                middle_words = [wd for wd in words if 0.30 <= (wd['y'] + wd['h']//2)/h <= 0.70]
                
                # Check if there is an exit/proceed button at the bottom right
                has_bottom_right_btn = False
                for wd in words:
                    cx = wd['x'] + wd['w'] // 2
                    cy = wd['y'] + wd['h'] // 2
                    x_pct = cx / w
                    y_pct = cy / h
                    if x_pct > 0.70 and y_pct > 0.75:
                        txt = wd['text'].lower().replace(" ", "")
                        if any(kw in txt for kw in ["スキップ", "skip", "進む", "proceed", "続ける", "continue", "戻る", "確認", "ok"]):
                            has_bottom_right_btn = True
                            break
                            
                has_left_option = any((wd['x'] + wd['w']//2)/w < 0.42 for wd in middle_words)
                has_right_option = any((wd['x'] + wd['w']//2)/w > 0.58 for wd in middle_words)
                is_choice_screen = (has_left_option and has_right_option) and not has_bottom_right_btn
                
                if is_choice_screen:
                    print("🎁 [Reward] Choice Screen detected (horizontal options side-by-side).")
                    reward_coords = eye.get_reward_card_coords()
                    
                    # Refine reward coordinates dynamically using middle_words columns (e.g. for boss relics)
                    x_coords = [wd['x'] + wd['w']//2 for wd in middle_words]
                    if len(x_coords) >= 3:
                        left_group = [x for x in x_coords if x / w < 0.44]
                        right_group = [x for x in x_coords if x / w > 0.56]
                        mid_group = [x for x in x_coords if 0.44 <= x / w <= 0.56]
                        if left_group and right_group and mid_group:
                            left_x = int(sum(left_group) / len(left_group))
                            right_x = int(sum(right_group) / len(right_group))
                            mid_x = int(sum(mid_group) / len(mid_group))
                            reward_coords = [
                                (left_x, int(h * 0.50)),
                                (mid_x, int(h * 0.50)),
                                (right_x, int(h * 0.50))
                            ]
                            print(f"🎁 [Reward] Dynamic columns: Left={left_x/w:.2f}, Mid={mid_x/w:.2f}, Right={right_x/w:.2f}")
                            
                    reward_hashes = []
                    for coord in reward_coords:
                        crop = eye.crop_card_at(frame, coord)
                        rhash = tactics.learning.get_card_hash(crop)
                        if rhash:
                            tactics.learning.register_card(rhash, crop)
                            
                            # OCR text caching
                            cached_name = tactics.learning.get_card_name(rhash)
                            if not cached_name:
                                ocr_name = eye.perform_ocr(crop)
                                if ocr_name:
                                    cost, clean_name = parse_card_cost_and_clean_name(ocr_name)
                                    cat = guess_card_category(clean_name)
                                    tactics.learning.update_card_name(rhash, clean_name, cost, cat)
                                    print(f"📖 [OCR] First-time scan: took photo of card {rhash} and recognized name as '{clean_name}' (Cost: {cost}, Cat: {cat})")
                            else:
                                print(f"📖 [OCR Cache] Instantly recognized card {rhash} as '{cached_name}'")
                                
                        reward_hashes.append(rhash)
                        
                    choice_idx = tactics.decide_reward_choice(reward_hashes)
                    if choice_idx < len(reward_coords):
                        chosen_coord = reward_coords[choice_idx]
                        chosen_hash = reward_hashes[choice_idx] if choice_idx < len(reward_hashes) else None
                        if chosen_hash and chosen_hash not in selected_card_hashes:
                            selected_card_hashes.append(chosen_hash)
                        body.click_position(chosen_coord, f"Reward Choice Option {choice_idx}")
                    else:
                        body.click_position(reward_coords[0], "Reward Choice Option 0 (Fallback)")
                    time.sleep(0.4)
                else:
                    # Reward List Screen (vertical items to claim)
                    print("🎁 [Reward] Reward List Screen detected (vertical items to claim).")
                    reward_items = []
                    cap_w = eye.capture_size[0] if (hasattr(eye, 'capture_size') and eye.capture_size) else w
                    cap_h = eye.capture_size[1] if (hasattr(eye, 'capture_size') and eye.capture_size) else h
                    for w_data in words:
                        cx = w_data['x'] + w_data['w'] // 2
                        cy = w_data['y'] + w_data['h'] // 2
                        x_pct = cx / cap_w
                        y_pct = cy / cap_h
                        
                        # Reward items are centered vertically stacked (X: 25% to 75%, Y: 20% to 75%)
                        if 0.25 <= x_pct <= 0.75 and 0.20 <= y_pct <= 0.75:
                            text_clean = w_data['text'].strip().lower()
                            # Exclude header labels AND skip/proceed buttons from being treated as reward items
                            skip_keywords = ["報酬", "reward", "凡例", "マップ", "legend",
                                             "スキップ", "skip", "進む", "proceed", "続ける", "continue",
                                             "戻る", "確認", "ok", "次へ", "next"]
                            if text_clean and not any(kw in text_clean for kw in skip_keywords):
                                p1 = eye.to_logical((w_data['x'], w_data['y']))
                                p2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                                logical_coord = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                                logical_bounds = (p1[0], p1[1], p2[0], p2[1])
                                reward_items.append((w_data, logical_coord, logical_bounds))
                                
                    # Sort items from top to bottom
                    reward_items.sort(key=lambda x: x[0]['y'])
                    
                    if reward_items:
                        # Click the first unclaimed reward row
                        target_w, target_coord, target_bounds = reward_items[0]
                        print(f"🎁 [Reward List] Claiming item '{target_w['text']}' at {target_coord}")
                        body.click_position(target_coord, f"Reward List Item ({target_w['text']})", bounds=target_bounds)
                        time.sleep(1.5) # Wait for animation/screen load
                    else:
                        # No reward items left, click Proceed/Skip button to exit
                        print("🎁 [Reward List] No rewards left. Looking for exit Proceed/Skip button...")
                        skip_coord = None
                        skip_bounds = None
                        for w_data in words:
                            txt = w_data['text'].lower().replace(" ", "")
                            cx = w_data['x'] + w_data['w'] // 2
                            cy = w_data['y'] + w_data['h'] // 2
                            x_pct = cx / cap_w
                            y_pct = cy / cap_h
                            if x_pct > 0.50 and y_pct > 0.75:
                                if any(kw in txt for kw in ["スキップ", "skip", "進む", "proceed", "続ける", "continue", "戻る", "確認", "ok"]):
                                    p1 = eye.to_logical((w_data['x'], w_data['y']))
                                    p2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                                    skip_coord = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                                    skip_bounds = (p1[0], p1[1], p2[0], p2[1])
                                    print(f"🎯 [Reward List] Found exit button: '{w_data['text']}' at {skip_coord}")
                                    break
                        if skip_coord:
                            body.confirm_and_push(skip_coord, "Reward List Exit Button", eye, bounds=skip_bounds)
                        else:
                            print("⚠️ [Reward List] Exit button not found. Clicking default Proceed coordinate...")
                            body.click_position((int(w * 0.85), int(h * 0.85)), "Reward List Fallback Exit")
                        time.sleep(0.4)

            elif state == "SHOP":
                brain.handle_shop(frame, save_data)

            elif state == "MAIN_MENU":
                brain.handle_main_menu(frame, driver.hwnd)
                
            elif state == "CHARACTER_SELECT":
                brain.handle_character_select(frame)
                
            elif state == "DEFEAT_SCREEN":
                brain.handle_defeat(frame)

            elif state == "PAUSE_MENU":
                print("⏸️ [Pause Menu] ポーズメニューを検知。'再開' ボタンを探してクリックします...")
                words = eye.get_all_text_coords(frame)
                target_coord = None
                target_bounds = None
                for w_data in words:
                    if "再開" in w_data['text']:
                        p1 = eye.to_logical((w_data['x'], w_data['y']))
                        p2 = eye.to_logical((w_data['x'] + w_data['w'], w_data['y'] + w_data['h']))
                        target_coord = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                        target_bounds = (p1[0], p1[1], p2[0], p2[1])
                        print(f"🎯 '再開' ボタンを検出: 座標 {target_coord} 範囲 {target_bounds}")
                        break
                if target_coord:
                    human_observer.bot_is_clicking = True
                    body.click_position(target_coord, "Resume Button", bounds=target_bounds)
                    human_observer.bot_is_clicking = False
                    time.sleep(1.5)
                else:
                    print("⚠️ '再開' ボタンの文字が見つからないため、ESCキーでメニューを閉じます。")
                    driver.press_key(0x1B) # VK_ESCAPE
                    time.sleep(1.5)
                
            # Short delay between cycles to let animations settle
            time.sleep(0.1)
    finally:
        # Record final run outcome in visual Q-learning database
        print("\n💾 Recording learning run outcome in database...")
        tactics.learning.record_run_outcome(victory=False, max_floor=loop_count // 5 + 1, selected_cards=selected_card_hashes)
        print("🏁 Infinite Spire loop completed.")

if __name__ == "__main__":
    # Check if a custom title is passed (e.g. Slay the Spire 2)
    title = sys.argv[1] if len(sys.argv) > 1 else "Slay the Spire"
    run_spire_automator(title)