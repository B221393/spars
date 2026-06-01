import os
import sys
import time
import json
import glob
import cv2

def load_current_run_save():
    """Reads the current run's save file dynamically using glob."""
    try:
        paths = glob.glob(r"C:\Users\yu_ci\AppData\Roaming\SlayTheSpire2\steam\*\profile1\saves\current_run.save")
        if not paths:
            return None
        latest_path = max(paths, key=os.path.getmtime)
        with open(latest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ [SaveParser] Error loading save file: {e}")
        return None

def write_reflection(base_dir, loop_count, current_state):
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
        good = "キャラ選択画面の文字を検出し、確定チェックマークへのマッピングに成功。"
        problem = "フォーカスが外れた場合、安全装置が正しく機能するがループが待機に入る。"
        try_text = "OCRテキストマッチングを第一優先とし、ボタン座標を動的に決定し続ける。"
    elif current_state == "MAIN_MENU":
        good = "メインメニュー画面を検知し、シングルプレイボタンを押下。"
        problem = "ゲームの起動状態やサイズ変更によってボタン座標がずれる可能性があったが、DPI修正により改善。"
        try_text = "OCRテキストマッチングを第一優先とし、ボタン座標を動的に決定し続ける。"
    else:
        good = f"現在のゲーム状態 {current_state} を安定して検知。"
        problem = "未知の画面による判定保留が発生しやすい。"
        try_text = "フォールバッククリック座標の精度を高める。"
        
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
            f.write("このファイルは、AIが自動運転の成果を振り返るログです。\n\n")
        f.write(log_entry)
    print(f"📝 [Reflection] evolution_reflections.md に反省会を記録しました。")

def scroll_map(direction, ticks=10):
    import win32api
    import win32con
    import random
    val = 120 if direction == 'up' else -120
    print(f"🖱️ [Scroll] Scrolling map {direction} ({ticks} ticks)...")
    for _ in range(ticks):
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, val, 0)
        time.sleep(random.uniform(0.03, 0.06))
    time.sleep(0.5)

def get_coord(category, key, default_pct, w, h):
    """
    Loads a coordinate from COORDINATES/<category>.json if available,
    otherwise returns the default percentage scaled to current window size.
    """
    try:
        config_path = os.path.join(os.path.dirname(__file__), "COORDINATES", f"{category}.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                if key in config:
                    item = config[key]
                    return (int(w * item["x_pct"]), int(h * item["y_pct"]))
    except Exception as e:
        print(f"⚠️ [Config] Error loading coord {category}.{key}: {e}")
    
    # Fallback to default
    return (int(w * default_pct[0]), int(h * default_pct[1]))

def save_state_analysis(base_dir, state, frame, eye):
    if frame is None: return
    analysis_dir = os.path.join(base_dir, "saves", "state_analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    img_path = os.path.join(analysis_dir, f"{state}_{timestamp}.png")
    html_path = os.path.join(analysis_dir, f"{state}_{timestamp}.html")
    cv2.imwrite(img_path, frame)
    pseudo_html = eye.generate_pseudo_html(frame)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(pseudo_html)

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

def log_and_visualize_current_location(frame, save_data, eye, best_visited_cv, next_coords, scored_next, points, base_dir):
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
            min_y_dist = 9999.0
            y_min = ny_pct - 0.05
            y_max = ny_pct + 0.05
            for nx, ny in nodes:
                cv_x_pct = nx / cw
                cv_y_pct = ny / ch
                if y_min <= cv_y_pct <= y_max:
                    estimated_col = round((cv_x_pct - 0.25) * 12.0)
                    if estimated_col == ncol:
                        y_dist = abs(cv_y_pct - ny_pct)
                        if y_dist < min_y_dist:
                            min_y_dist = y_dist
                            best_cv_node = (nx, ny)
                        
            draw_x, draw_y = (best_cv_node if best_cv_node else (est_nx, est_ny))
            
            cv2.circle(annotated_frame, (draw_x, draw_y), 20, (0, 255, 0), 3) # Green BGR
            label_text = f"{n_type} (Score: {score})"
            cv2.putText(annotated_frame, label_text, (draw_x - 60, draw_y - 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
        saves_dir = os.path.join(base_dir, "saves")
        os.makedirs(saves_dir, exist_ok=True)
        img_path = os.path.join(saves_dir, "map_current_location.png")
        cv2.imwrite(img_path, annotated_frame)
        
        log_path = os.path.join(saves_dir, "map_current_location.txt")
        log_text = f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\nCurrent Node: {current_node_desc}\nNext Valid Paths:\n"
        for next_coord_data, n_type, score in scored_next:
            ncol = next_coord_data.get('col', 0)
            nrow = next_coord_data.get('row', 0)
            log_text += f"- Col {ncol}, Row {nrow} (Type: {n_type}, Priority Score: {score})\n"
            
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_text)
            
    except Exception as e:
        print(f"⚠️ [Map Visualizer] Failed to create map visualization: {e}")
