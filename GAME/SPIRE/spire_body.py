import os
import sys
import time
import random
import json

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Add AI/CORE and GENRE_FOLDERS/AI to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AI_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "AI"))
sys.path.append(AI_DIR)

from CORE.smart_automator import SmartAutomator, bot_action

class SpireBody(SmartAutomator):
    """
    💪 Slay the Spire 2 Specific Physical Action Executor.
    Inherits generic click, verification, calibration, and debugging logic from SmartAutomator.
    Handles Spire-specific mechanics like dragging cards and ending turns.
    """
    def __init__(self, driver, human_observer=None, cache_manager=None, learning=None):
        save_dir = os.path.join(BASE_DIR, "saves")
        super().__init__(
            driver=driver,
            save_dir=save_dir,
            learning=learning,
            human_observer=human_observer,
            cache_manager=cache_manager
        )
        
    def log(self, message):
        print(f"💪 [SpireBody] {message}")

    def _read_slsw_clicks(self):
        """Reads the latest click data from SLSW watcher."""
        path = os.path.join(self.save_dir, "slsw_clicks.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def verify_click_with_slsw(self, target_rel_x, target_rel_y):
        """
        Compares the intended click (percentage) with the last click recorded by SLSW.
        """
        clicks = self._read_slsw_clicks()
        if not clicks:
            return None
            
        last_click = clicks[-1]
        now = time.time()
        
        # Only consider recent clicks (last 3 seconds)
        if now - last_click["timestamp"] > 3.0:
            return None
            
        # Check if the click was roughly where we intended
        dx = last_click["rel_x"] - target_rel_x
        dy = last_click["rel_y"] - target_rel_y
        
        if abs(dx) < 0.1 and abs(dy) < 0.1: # Broad match to identify the specific click
            self.log(f"🎯 [SLSW Verify] Found matching click at ({last_click['rel_x']:.4f}, {last_click['rel_y']:.4f})")
            return dx, dy
        return None

    @bot_action
    def click_and_verify(self, coord, label="Target", max_shifts=5, shift_px=15, change_threshold=5.5, bounds=None):
        """Wraps generic click_and_verify with Spire-specific SLSW feedback telemetry check."""
        def custom_verify(target_rx, target_ry):
            slsw_offset = self.verify_click_with_slsw(target_rx, target_ry)
            if slsw_offset:
                odx, ody = slsw_offset
                if abs(odx) > 0.001 or abs(ody) > 0.001:
                    self.log(f"⚖️ [SLSW Feedback] Detected systemic offset: ({odx:.4f}, {ody:.4f}). AI will calibrate.")
                    try:
                        w, h = self._get_client_size()
                        dx_px = int(round(odx * w))
                        dy_px = int(round(ody * h))
                        clicked_x = int(round(target_rx * w))
                        clicked_y = int(round(target_ry * h))
                        self.calibrator.record_click_feedback(
                            clicked_x, clicked_y, clicked_x + dx_px, clicked_y + dy_px
                        )
                    except Exception as e:
                        self.log(f"⚠️ [SLSW Feedback Error] Failed to record calibration feedback: {e}")
                    
        return super().click_and_verify(
            coord, label=label, max_shifts=max_shifts, shift_px=shift_px,
            change_threshold=change_threshold, bounds=bounds,
            custom_verify_func=custom_verify
        )


    @bot_action
    def play_card(self, card_coord, target_coord, card_idx=None):
        """
        Plays card at card_idx (using keyboard hotkey) or drags from card_coord to target_coord.
        """
        self.wait_for_active_window()
        tx, ty = target_coord
        ox, oy = self._read_calibration_offset()
        tx += ox
        ty += oy
        
        if card_idx is not None and 0 <= card_idx < 10:
            # Slay the Spire 2 uses keys '1' through '9' for card selection (and '0' for card 10)
            key_char = str((card_idx + 1) % 10)
            vk_code = 0x30 + ((card_idx + 1) % 10) # 0x30 is '0', 0x31 is '1', etc.
            
            self.log_coordinate_event("play_card_hotkey", target_coord, (tx, ty), (ox, oy), f"Card {card_idx} Target (Hotkey)")
            self.flash_comparison_pointers(target_coord, (tx, ty), label=f"Card {card_idx} Target (Hotkey)")

            self.log(f"Executing card play via Hotkey: Pressing '{key_char}' for card index {card_idx}, then clicking target at ({tx}, {ty})")
            
            # Press selection key
            self.driver.press_key(vk_code)
            time.sleep(random.uniform(0.15, 0.25)) # wait for card to float to center
            
            # Move mouse to target coordinate and click
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.08, 0.15))
            self.driver.hardware_click(tx, ty)
            time.sleep(random.uniform(0.2, 0.4)) # wait for card play animation
        else:
            cx, cy = card_coord[:2]
            cx += ox
            cy += oy
            
            self.log_coordinate_event("play_card_drag_start", card_coord[:2], (cx, cy), (ox, oy), "Card Drag Start")
            self.log_coordinate_event("play_card_drag_end", target_coord, (tx, ty), (ox, oy), "Card Drag Target")
            self.flash_comparison_pointers(card_coord[:2], (cx, cy), label="Card Drag Start")
            self.flash_comparison_pointers(target_coord, (tx, ty), label="Card Drag Target")

            self.log(f"Executing card play via Dragging: dragging from {cx},{cy} to {tx},{ty}")
            
            # Move to card position naturally
            self.driver.bezier_move(cx, cy)
            time.sleep(random.uniform(0.1, 0.2))
            
            # Press down mouse
            import ctypes
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # MOUSEEVENTF_LEFTDOWN
            time.sleep(random.uniform(0.05, 0.15))
            
            # Drag to target position naturally
            self.driver.bezier_move(tx, ty)
            time.sleep(random.uniform(0.1, 0.2))
            
            # Release mouse
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # MOUSEEVENTF_LEFTUP
            time.sleep(random.uniform(0.2, 0.4)) # pause for play animation

    @bot_action
    def click_end_turn(self, btn_coord):
        """
        Ends the turn using the 'E' keyboard shortcut to minimize mouse movement and maximize reliability.
        Falls back to physical click if keyboard press does not transition screen.
        """
        self.wait_for_active_window()
        self.log("Pressing 'E' key to End Turn...")
        
        # Capture before to verify transition
        before_small = self._capture_small()
        
        # Press 'E' key (VK code for 'E' is 0x45)
        self.driver.press_key(0x45)
        time.sleep(0.3)
        
        # Check if screen changed
        after_small = self._capture_small()
        diff = self._pixel_diff(before_small, after_small)
        
        if diff >= 2.0:
            self.log(f"✅ End turn hotkey 'E' succeeded. Screen diff: {diff:.2f}")
            self.log_coordinate_event("click_end_turn_hotkey", (0, 0), (0, 0), (0, 0), "End Turn via Hotkey E")
            time.sleep(random.uniform(0.5, 0.8))
            return True
            
        self.log(f"⚠️ Hotkey 'E' had no effect (diff: {diff:.2f}). Falling back to physical click on End Turn button.")
        bx, by = btn_coord
        ox, oy = self._read_calibration_offset()
        cx = bx + ox
        cy = by + oy
        
        self.log_coordinate_event("click_end_turn", btn_coord, (cx, cy), (ox, oy), "End Turn Button Click")
        self.flash_comparison_pointers(btn_coord, (cx, cy), label="End Turn Button Click")
        
        self.log(f"Clicking End Turn button at {cx},{cy}")
        self.driver.bezier_move(cx, cy)
        time.sleep(random.uniform(0.05, 0.15))
        self.driver.hardware_click(cx, cy)
        time.sleep(random.uniform(0.5, 0.8)) # wait for enemy turn animation
        return True
