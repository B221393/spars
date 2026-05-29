import os
import sys
import time
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

    def grab_screen(self):
        """Captures the current client window area using the driver's capture method."""
        if not HAS_CV:
            return None
        try:
            self.update_window_bounds()
            pil_img = self.driver.capture()
            if pil_img is None:
                return None
            frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            return frame
        except Exception as e:
            self.log(f"Screen grab failed: {e}")
            return None

    def query_llm(self, frame, prompt, resize_to=(256, 144)):
        """Generic method to query Gemma4 with a frame and prompt."""
        if frame is None:
            return ""
        try:
            import cv2
            import base64
            import requests
            
            resized = cv2.resize(frame, resize_to)
            _, buffer = cv2.imencode('.jpg', resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            b64_str = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "model": "gemma4",
                "prompt": prompt,
                "images": [b64_str],
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }
            self.log("Querying gemma4 with custom prompt...")
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120.0)
            if res.status_code == 200:
                return res.json().get("response", "").strip()
            else:
                self.log(f"Ollama API returned status code {res.status_code}")
        except Exception as e:
            self.log(f"query_llm failed: {e}")
        return ""

    def detect_game_state_via_llm(self, frame):
        """
        Uses gemma4 via Ollama to detect the game state from the screen image.
        Uses visual hashing and difference threshold to avoid querying on static frames.
        """
        if frame is None:
            return None
            
        import cv2
        
        # 1. Frame difference check to avoid redundant LLM queries
        small_frame = cv2.resize(frame, (64, 36))
        if self.last_frame_small is not None:
            diff = cv2.absdiff(small_frame, self.last_frame_small)
            mean_diff = np.mean(diff)
            # If difference is negligible (< 3.0 mean absolute pixel diff), reuse last state
            if mean_diff < 3.0:
                self.static_cycles_count += 1
                if self.static_cycles_count < 3:
                    return self.last_llm_state
                else:
                    self.log("Screen has been static for 3 cycles. Forcing fresh Gemma 4 query to verify state...")
            else:
                self.static_cycles_count = 0
                
        # Update cached small frame
        self.last_frame_small = small_frame

        try:
            # Resize the image to 256x144 to speed up CPU inference
            resized = cv2.resize(frame, (256, 144))
            _, buffer = cv2.imencode('.jpg', resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            b64_str = base64.b64encode(buffer).decode('utf-8')

            prompt = """Analyze this Slay the Spire game screenshot.
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

            payload = {
                "model": "gemma4",
                "prompt": prompt,
                "images": [b64_str],
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }

            self.log("Querying gemma4 for game state recognition...")
            start_time = time.time()
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=180.0)
            elapsed = time.time() - start_time

            if res.status_code == 200:
                response_text = res.json().get("response", "").strip().upper()
                self.log(f"gemma4 response ({elapsed:.2f}s): {response_text}")
                
                valid_states = ["COMBAT", "REST_SITE", "MAP", "REWARD", "MAIN_MENU", "CHARACTER_SELECT", "DEFEAT_SCREEN", "EVENT", "LOADING"]
                for state in valid_states:
                    if state in response_text:
                        self.last_llm_state = state
                        return state
                self.log(f"gemma4 returned unrecognized response: {response_text}")
            else:
                self.log(f"Ollama API returned status code {res.status_code}")
        except Exception as e:
            self.log(f"Gemma 4 vision check failed: {e}")
        return None

    def detect_game_state(self, frame=None):
        """
        Reflexive/Spinal classification of the current screen.
        First uses fast frame difference caching, optimized pixel heuristics, 
        and state transition memory (< 1ms, 0% CPU).
        Only falls back to OCR on transitions, and local Gemma4 for event dialogues.
        """
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

        # 3. Fast Pixel-based heuristics (Optimized Order to avoid false positives)
        detected_state = "UNKNOWN"
        defeat_region_mean = np.mean(frame[int(h*0.83):int(h*0.93), int(w*0.45):int(w*0.55)])
        char_select_region_mean = np.mean(frame[int(h*0.80):int(h*0.90), int(w*0.78):int(w*0.88)])
        main_menu_region_mean = np.mean(frame[int(h*0.60):int(h*0.70), int(w*0.38):int(w*0.48)]) # shifted left for STS2
        
        # Check Main Menu first to avoid Defeat Screen false positive
        if main_menu_region_mean > 40 and overall_mean > 25:
            detected_state = "MAIN_MENU"
        elif char_select_region_mean > 60 and overall_mean > 35:
            detected_state = "CHARACTER_SELECT"
        elif defeat_region_mean > 60 and overall_mean > 30:
            detected_state = "DEFEAT_SCREEN"
        else:
            # Check for Combat (End Turn button color)
            end_turn_region = frame[int(h*0.50):int(h*0.62), int(w*0.78):int(w*0.92)]
            mean_color = np.mean(end_turn_region, axis=(0,1))
            if mean_color[1] > mean_color[0] * 1.1 and mean_color[1] > 40:
                detected_state = "COMBAT"
            else:
                # Check for Rest Site
                legend_region = frame[0:int(h*0.1), int(w*0.85):w]
                if np.mean(legend_region) < 30 and 15 <= overall_mean <= 50:
                    detected_state = "REST_SITE"
                    
        # State transition memory: if we were in COMBAT, and heuristics did not detect a menu/select/defeat/loading,
        # we are highly likely to still be in COMBAT (e.g. enemy turn or card playing animations)
        if detected_state == "UNKNOWN" and self.last_llm_state == "COMBAT":
            detected_state = "COMBAT"

        if detected_state != "UNKNOWN":
            self.last_llm_state = detected_state
            return detected_state

        # 4. Run Fast OCR-based state detection
        self.log("Running fast OCR-based state detection...")
        words = self.get_all_text_coords(frame)
        full_text = " ".join(w['text'].lower() for w in words)
        
        # Check text anchors for instant state matching
        if any(kw in full_text for kw in ["シングル", "singleplayer", "マルチプレイ", "multiplayer", "プレイ"]):
            detected_state = "MAIN_MENU"
        elif any(kw in full_text for kw in ["挑戦を開始", "embark", "キャラクター選択", "character select", "挑戦"]):
            detected_state = "CHARACTER_SELECT"
        elif any(kw in full_text for kw in ["ターン終了", "end turn", "エンドターン", "コモン", "アンコモン", "レア"]):
            detected_state = "COMBAT"
        elif any(kw in full_text for kw in ["休む", "鍛冶", "rest", "smith"]):
            detected_state = "REST_SITE"
        elif any(kw in full_text for kw in ["マップ", "凡例", "map", "legend"]):
            detected_state = "MAP"
        elif any(kw in full_text for kw in ["カードを選択", "報酬", "選択したカードを追加", "card reward", "take"]):
            detected_state = "REWARD"
        elif any(kw in full_text for kw in ["メインメニューに戻る", "諦める", "defeat", "victory", "return to main"]):
            detected_state = "DEFEAT_SCREEN"

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

    def locate_combat_elements(self, frame):
        """
        Extracts position coordinates for Hand Cards, Enemies, and End Turn Button.
        Uses standardized aspect-ratio relative mapping for extreme speed (spinal reflex).
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
        
        # Detect Hand Cards: Hand is distributed along the bottom center
        # Cards usually sit around Y: 85% of screen height
        card_y = int(h * 0.85)
        # Scan for card presence (usually lighter border pixels against dark combat background)
        # In mock/fallback, we space cards evenly based on hand size
        hand_size = 5 # default assumed hand size
        start_x = int(w * 0.25)
        end_x = int(w * 0.75)
        step = (end_x - start_x) // max(1, hand_size - 1)
        for i in range(hand_size):
            elements["cards"].append((start_x + i * step, card_y))

        # Detect Enemies: Enemies occupy the right side, mid height (Y: 45%)
        # Usually between X: 60% and 85%
        elements["enemies"] = [
            (int(w * 0.72), int(h * 0.45)), # Middle enemy
            (int(w * 0.82), int(h * 0.45))  # Right enemy
        ]
        
        return elements

    def crop_card_at(self, frame, card_coord):
        if frame is None:
            return None
        h, w, _ = frame.shape
        cx, cy = card_coord
        y_start = max(0, cy - int(h * 0.15))
        y_end = min(h, cy - int(h * 0.05))
        x_start = max(0, cx - int(w * 0.04))
        x_end = min(w, cx + int(w * 0.04))
        return frame[y_start:y_end, x_start:x_end]

    def get_reward_card_coords(self):
        w, h = self.window_size
        return [
            (int(w * 0.32), int(h * 0.50)),
            (int(w * 0.50), int(h * 0.50)),
            (int(w * 0.68), int(h * 0.50))
        ]

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
        if self.last_ocr_frame_small is not None and self.last_ocr_words:
            # Check visual difference
            diff = cv2.absdiff(small_frame, self.last_ocr_frame_small)
            mean_diff = np.mean(diff)
            # If screen is static (diff < 1.0) and queried within 1.5 seconds, reuse cache
            if mean_diff < 1.0 and (time.time() - self.last_ocr_time) < 1.5:
                return self.last_ocr_words

        import tempfile
        temp_path = os.path.join(tempfile.gettempdir(), f"temp_ocr_{os.getpid()}.jpg")
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
                    words = json.loads(json_str)
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
                $file = Get-Item "{TEMP_PATH}"
                $dotNetStream = [System.IO.File]::OpenRead($file.FullName)
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
            """.replace("{TEMP_PATH}", temp_path.replace("\\", "\\\\"))
            
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
            
        # グループ化ロジック (同一行にある単語/文字をまとめて1つの要素にする)
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
                line_text = "".join(w['text'] for w in sorted_line)
                min_x = min(w['x'] for w in sorted_line)
                max_x = max(w['x'] + w['w'] for w in sorted_line)
                min_y = min(w['y'] for w in sorted_line)
                max_y = max(w['y'] + w['h'] for w in sorted_line)
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
        実行前後の画像をローカルLLM（gemma4）に送り、
        「なぜ変化が起きなかったのか（隠れたエラー）」を推理させる。
        同時に、その証拠写真を物理保存する。
        """
        if before_frame is None or after_frame is None:
            return "診断不可：画像の取得に失敗しています。"

        try:
            import cv2
            import base64
            import os
            import time
            
            # 2枚の画像を連結して送る (左: Before, 右: After)
            h, w = before_frame.shape[:2]
            combined = np.zeros((h, w*2, 3), dtype=np.uint8)
            combined[:, :w] = before_frame
            combined[:, w:] = after_frame
            
            # --- 証拠写真の保存 (Visual Logging) ---
            error_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves", "silent_errors")
            os.makedirs(error_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            img_path = os.path.join(error_dir, f"{timestamp}_bottleneck.jpg")
            cv2.imwrite(img_path, combined)
            self.log(f"📸 [Visual Log] ボトルネックの証拠写真を回収しました: {img_path}")
            # --------------------------------------
            
            resized = cv2.resize(combined, (512, 144))
            _, buffer = cv2.imencode('.jpg', resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            b64_str = base64.b64encode(buffer).decode('utf-8')

            prompt = f"""Analysis of gameplay action:
I tried to perform the following action in Slay the Spire: {intended_action}
The image shows a combined view with 'BEFORE' (left half) and 'AFTER' (right half) the action.
However, the screen did not change as expected (no response to click).

Look closely at the targets, UI buttons, active overlays, dialog boxes, and state changes.
Why did this click action fail to advance the game state?
Provide a brief, helpful analysis in Japanese explaining the reason and a suggested fix.
Output ONLY the reason and a suggested fix."""

            payload = {
                "model": "gemma4",
                "prompt": prompt,
                "images": [b64_str],
                "stream": False
            }

            self.log("Invoking gemma4 for deep bottleneck diagnosis...")
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120.0)
            
            if res.status_code == 200:
                reason = res.json().get("response", "").strip()
                self.log(f"📝 [Diagnosis Result]: {reason}")
                
                # 推論結果もテキスト保存
                with open(os.path.join(error_dir, f"{timestamp}_bottleneck.txt"), "w", encoding="utf-8") as f:
                    f.write(f"Action: {intended_action}\nLLM Diagnosis: {reason}\n")
                    
                return reason
        except Exception as e:
            self.log(f"Diagnosis failed: {e}")
        
        return "診断プロセスでエラーが発生しました。"
