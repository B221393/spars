#!/usr/bin/env python3
import os
import sys
import time
import json
import requests
import subprocess

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    pass

# Force output encoding to UTF-8 to prevent CP932 emoji crashes
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass

API_URL = "http://localhost:15526/api/v1/singleplayer"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma2:2b"

# Global run variables
running = True
error_history = []
last_state_sig = None
stuck_counter = 0

def log(msg):
    print(f"[AGI-Loop] {msg}", flush=True)

def check_game_running():
    """Checks if Slay the Spire 2 process is active."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == 'slaythespire2.exe':
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

def launch_game():
    """Launches the Slay the Spire 2 game."""
    log("Slay the Spire 2 is not running. Launching game...")
    direct_path = r"C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.exe"
    if os.path.exists(direct_path):
        try:
            subprocess.Popen(direct_path, cwd=os.path.dirname(direct_path))
            log("Direct launch command executed.")
            return True
        except Exception as e:
            log(f"Direct launch failed: {e}")
    
    try:
        subprocess.Popen('start "" "steam://rungameid/2405740"', shell=True)
        log("Steam launch command executed.")
        return True
    except Exception as e:
        log(f"Steam launch failed: {e}")
    return False

def get_game_state():
    """Fetches the game state from the mod API."""
    try:
        r = requests.get(API_URL, params={"format": "json"}, timeout=2.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def build_system_prompt():
    return """You are the AGI Closed-Loop Autonomous Player for Slay the Spire 2.
Your goal is to play Slay the Spire 2 fully autonomously by deciding the next action.
You MUST output JSON ONLY matching this format:
{
  "reasoning": "A brief explanation of why this action is chosen.",
  "action": "action_name",
  "parameters": {
    "card_index": integer,  // Use for card actions (0-based)
    "target": "entity_id",  // Enemy target (e.g. 'JAW_WORM_0')
    "index": integer,       // Index parameter for rewards, map nodes, shop purchase, rest options, event choices
    "option": "option_id",  // Option name for menu_select
    "slot": integer         // Slot index for potions
  }
}

List of valid actions:
1. "combat_play_card" (parameters: card_index (int), target (string, optional))
2. "combat_end_turn" (no parameters)
3. "map_choose_node" (parameters: index (int))
4. "rest_choose_option" (parameters: index (int))
5. "shop_purchase" (parameters: index (int))
6. "event_choose_option" (parameters: index (int))
7. "event_advance_dialogue" (no parameters)
8. "rewards_claim" (parameters: index (int))
9. "rewards_pick_card" (parameters: card_index (int))
10. "rewards_skip_card" (no parameters)
11. "menu_select" (parameters: option (string))
12. "proceed_to_map" (no parameters)
13. "use_potion" (parameters: slot (int), target (string, optional))
14. "discard_potion" (parameters: slot (int))
15. "deck_select_card" (parameters: index (int))
16. "deck_confirm_selection" (no parameters)
17. "deck_cancel_selection" (no parameters)

CRITICAL rules for Combat:
- Read your hand and enemy intents carefully.
- Playing a card shifts remaining card indices left! Think about this when queuing plays.
- If you can kill all enemies, do it. Else, balance defense (block) and offense.
- Target enemies using their exact 'entity_id' (e.g., 'MINION_0' or 'JAW_WORM_0').
- Buff and defense cards do not require a target. Single-target attack cards DO require a target.
"""

def generate_state_description(state):
    state_type = state.get("state_type", "UNKNOWN")
    menu_screen = state.get("menu_screen")
    
    desc = f"State Type: {state_type}\n"
    if menu_screen:
        desc += f"Menu Screen: {menu_screen}\n"
        
    player = state.get("player", {})
    if player:
        desc += f"Player HP: {player.get('hp', 0)}/{player.get('max_hp', 0)} | Gold: {player.get('gold', 0)} | Block: {player.get('block', 0)}\n"
        desc += f"Deck Size: {len(player.get('master_deck', []))}\n"
        potions = player.get("potions", [])
        if potions:
            desc += "Potions:\n"
            for idx, p in enumerate(potions):
                desc += f"  Slot {idx}: name='{p.get('name')}', description='{p.get('description')}'\n"

    # Specific room details
    if state_type in ["monster", "elite", "boss"]:
        battle = state.get("battle", {})
        if battle:
            desc += f"Combat Turn Energy: {battle.get('energy', 0)}\n"
            desc += "Hand Cards:\n"
            for idx, c in enumerate(battle.get("hand", [])):
                desc += f"  Index {idx}: name='{c.get('name')}', type='{c.get('type')}', cost={c.get('cost')}, desc='{c.get('description')}'\n"
            desc += "Enemies:\n"
            for e in state.get("enemies", []):
                desc += f"  ID: '{e.get('entity_id')}' | name='{e.get('name')}' | HP: {e.get('hp')}/{e.get('max_hp')} | Block: {e.get('block')}\n"
                intents = e.get("intents", [])
                for i in intents:
                    desc += f"    Intent: label='{i.get('label')}'\n"
                    
    elif state_type == "map":
        map_data = state.get("map", {})
        if map_data:
            desc += f"Current Floor: {map_data.get('floor', 0)}\n"
            desc += "Available Path Options (choose index from this list):\n"
            for idx, opt in enumerate(map_data.get("next_options", [])):
                desc += f"  Index {idx}: col={opt.get('col')}, row={opt.get('row')}, type='{opt.get('type')}'\n"
                
    elif state_type == "rest_site":
        rest_data = state.get("rest_site", {})
        if rest_data:
            desc += "Campfire Options:\n"
            for idx, opt in enumerate(rest_data.get("options", [])):
                desc += f"  Index {idx}: id='{opt.get('id')}', enabled={opt.get('is_enabled')}\n"
            desc += f"Can Proceed to Map: {rest_data.get('can_proceed', False)}\n"
            
    elif state_type == "shop":
        shop_data = state.get("shop", {})
        if shop_data:
            desc += "Shop Items:\n"
            for idx, item in enumerate(shop_data.get("items", [])):
                name = item.get("card_name") or item.get("relic_name") or item.get("potion_name") or item.get("category", "")
                price = item.get("price", 0)
                afford = item.get("can_afford", False)
                desc += f"  Index {idx}: category='{item.get('category')}', name='{name}', price={price}, can_afford={afford}\n"
            desc += f"Can Proceed to Map: {shop_data.get('can_proceed', False)}\n"
            
    elif state_type == "event":
        event_data = state.get("event", {})
        if event_data:
            desc += f"Event Name: {event_data.get('name')}\n"
            desc += f"In Dialogue: {event_data.get('in_dialogue', False)}\n"
            desc += "Options:\n"
            for idx, opt in enumerate(event_data.get("options", [])):
                desc += f"  Index {idx}: title='{opt.get('title')}', locked={opt.get('is_locked')}\n"
                
    elif state_type == "rewards":
        rewards_data = state.get("rewards", {})
        if rewards_data:
            desc += "Rewards Available:\n"
            for idx, item in enumerate(rewards_data.get("items", [])):
                desc += f"  Index {idx}: type='{item.get('type')}', desc='{item.get('description')}'\n"
            desc += f"Can Proceed to Map: {rewards_data.get('can_proceed', False)}\n"
            
    elif state_type == "card_reward":
        reward_data = state.get("card_reward", {})
        if reward_data:
            desc += "Offered Cards:\n"
            for idx, card in enumerate(reward_data.get("cards", [])):
                desc += f"  Index {idx}: name='{card.get('name')}', type='{card.get('type')}', desc='{card.get('description')}'\n"
            desc += f"Can Skip Reward: {reward_data.get('can_skip', False)}\n"
            
    elif state_type in ["card_select", "hand_select"]:
        select_data = state.get(state_type, {})
        if select_data:
            desc += f"Prompt: '{select_data.get('prompt')}'\n"
            desc += f"Screen Type: '{select_data.get('screen_type')}'\n"
            desc += "Cards List:\n"
            for idx, card in enumerate(select_data.get("cards", [])):
                desc += f"  Index {idx}: name='{card.get('name')}', selected={card.get('is_selected')}\n"
            desc += f"Can Confirm: {select_data.get('can_confirm', False)}\n"
            desc += f"Can Cancel: {select_data.get('can_cancel', False)}\n"
            desc += f"Preview Showing: {select_data.get('preview_showing', False)}\n"
            
    elif menu_screen == "main":
        desc += "Main Menu Options:\n"
        for opt in state.get("options", []):
            desc += f"  option='{opt}'\n"
            
    elif menu_screen == "character_select":
        desc += "Character Select Options:\n"
        for char in state.get("characters", []):
            desc += f"  option='{char.get('id')}', locked={char.get('locked')}\n"
            
    return desc

def query_gemma(prompt):
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=45.0)
        if r.status_code == 200:
            resp_str = r.json().get("response", "{}")
            return json.loads(resp_str)
    except Exception as e:
        log(f"Failed to query Ollama: {e}")
    return None

def execute_action(action, params):
    payload = {"action": ""}
    
    if action == "combat_play_card":
        payload["action"] = "play_card"
        payload["card_index"] = params.get("card_index", 0)
        if params.get("target"):
            payload["target"] = params["target"]
            
    elif action == "combat_end_turn":
        payload["action"] = "end_turn"
        
    elif action == "map_choose_node":
        payload["action"] = "choose_map_node"
        payload["index"] = params.get("index", 0)
        
    elif action == "rest_choose_option":
        payload["action"] = "choose_rest_option"
        payload["index"] = params.get("index", 0)
        
    elif action == "shop_purchase":
        payload["action"] = "shop_purchase"
        payload["index"] = params.get("index", 0)
        
    elif action == "event_choose_option":
        payload["action"] = "choose_event_option"
        payload["index"] = params.get("index", 0)
        
    elif action == "event_advance_dialogue":
        payload["action"] = "advance_dialogue"
        
    elif action == "rewards_claim":
        payload["action"] = "claim_reward"
        payload["index"] = params.get("index", 0)
        
    elif action == "rewards_pick_card":
        payload["action"] = "select_card_reward"
        payload["card_index"] = params.get("card_index", 0)
        
    elif action == "rewards_skip_card":
        payload["action"] = "skip_card_reward"
        
    elif action == "menu_select":
        payload["action"] = "menu_select"
        payload["option"] = params.get("option", "")
        
    elif action == "proceed_to_map":
        payload["action"] = "proceed"
        
    elif action == "use_potion":
        payload["action"] = "use_potion"
        payload["slot"] = params.get("slot", 0)
        if params.get("target"):
            payload["target"] = params["target"]
            
    elif action == "discard_potion":
        payload["action"] = "discard_potion"
        payload["slot"] = params.get("slot", 0)
        
    elif action == "deck_select_card":
        payload["action"] = "select_card"
        payload["index"] = params.get("index", 0)
        
    elif action == "deck_confirm_selection":
        payload["action"] = "confirm_selection"
        
    elif action == "deck_cancel_selection":
        payload["action"] = "cancel_selection"
        
    else:
        log(f"Unknown AGI action type: {action}")
        return False

    try:
        r = requests.post(API_URL, json=payload, timeout=2.0)
        if r.status_code == 200:
            res_json = r.json()
            if res_json.get("status") == "ok":
                log(f"Successfully executed: {action} with parameters: {params}")
                return True
            else:
                log(f"Action rejected by API: {res_json.get('message', 'No error message')}")
                error_history.append(f"Rejected: {action} | API response: {res_json.get('message')}")
        else:
            log(f"Action POST returned HTTP {r.status_code}")
            error_history.append(f"HTTP Error: {r.status_code} for action {action}")
    except Exception as e:
        log(f"Failed to post action: {e}")
        error_history.append(f"POST failure: {e}")
    return False

def make_state_signature(state):
    state_type = state.get("state_type")
    menu_screen = state.get("menu_screen")
    player = state.get("player", {})
    hp = player.get("hp")
    gold = player.get("gold")
    floor = state.get("run", {}).get("floor", 0)
    
    battle = state.get("battle", {})
    energy = battle.get("energy")
    hand_len = len(battle.get("hand", []))
    
    return (state_type, menu_screen, hp, gold, floor, energy, hand_len)

def run_loop():
    global stuck_counter, last_state_sig, running, error_history
    
    log("Autonomous MCP Player Loop started.")
    
    while running:
        # 1. Verify game is running
        if not check_game_running():
            launch_game()
            time.sleep(10.0)
            continue
            
        # 2. Fetch game state
        state = get_game_state()
        if not state:
            log("Waiting for game and mod API on port 15526...")
            time.sleep(3.0)
            continue
            
        # Check stuck status
        sig = make_state_signature(state)
        if sig == last_state_sig:
            stuck_counter += 1
            if stuck_counter >= 3:
                log(f"[STUCK WARNING] State signature has not changed for {stuck_counter} cycles. Injecting warning to LLM.")
                if f"Stuck in state signature: {sig}" not in error_history:
                     error_history.append(f"Stuck in state signature: {sig}. Please choose a different action to break the loop.")
        else:
            last_state_sig = sig
            stuck_counter = 0
            # If state changed, clear error history to keep prompt context clean
            error_history = []
            
        # 3. Build prompts
        sys_prompt = build_system_prompt()
        state_desc = generate_state_description(state)
        
        user_prompt = f"""
{sys_prompt}

【CURRENT GAME STATE】
{state_desc}
"""
        if error_history:
            user_prompt += "\n【PREVIOUS FAILURES / STUCK WARNINGS】\n"
            for err in error_history[-5:]:
                user_prompt += f"- {err}\n"
            user_prompt += "\nAvoid repeating the errors above. Correct your choice or choose a different valid action (e.g. end turn, skip reward, select another option) to break the loop!"

        # 4. Query gemma
        log("Thinking...")
        decision = query_gemma(user_prompt)
        
        if not decision:
            log("LLM generated empty response. Retrying...")
            time.sleep(2.0)
            continue
            
        reasoning = decision.get("reasoning", "No reasoning provided")
        action = decision.get("action")
        params = decision.get("parameters", {})
        
        log(f"Decided action: '{action}' | Reason: {reasoning}")
        
        # 5. Execute action
        success = execute_action(action, params)
        
        # Dynamic delay based on state transitions
        if action == "combat_end_turn":
            time.sleep(2.0)  # Wait for enemies to take their turn
        else:
            time.sleep(1.2)  # Normal transition delay

if __name__ == "__main__":
    try:
        run_loop()
    except KeyboardInterrupt:
        log("Loop stopped by user.")
