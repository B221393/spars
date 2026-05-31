import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
from spire_learning import SpireLearning

import requests
import json

class SpireTactics:
    def __init__(self):
        self.play_count_this_turn = 0
        self.attacks_played_this_turn = 0
        self.learning = SpireLearning()
        self.context_history = []

    def generate_monologue(self, state, details):
        """
        [AIの内省的ナレーション]
        現在のゲーム状態と詳細をローカルLLM（gemma4）に送り、AIの言葉で語らせる。
        """
        prompt = f"""[ACTING AS AI AGENT]
You are a highly intelligent, autonomous AI playing Slay the Spire.
Current Game State: {state}
Situation Details: {details}

Express your current thought or intention in a short, natural Japanese sentence.
Avoid repetitive templates. Show your personality (strategic, cautious, or confident).
Output ONLY the sentence. No quotes, no markdown."""

        try:
            payload = {
                "model": "gemma4",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 50}
            }
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=5.0)
            if res.status_code == 200:
                monologue = res.json().get("response", "").strip()
                return f"🤖 [AI Thought] {monologue}"
        except:
            pass
        return f"🧠 [Reflex] {details}" # Fallback

    def log(self, message, state="GENERAL"):
        # LLMによる動的ナレーションの生成
        thought = self.generate_monologue(state, message)
        print(thought)

    def reset_turn(self):
        self.play_count_this_turn = 0
        self.attacks_played_this_turn = 0

    def decide_combat_action(self, elements, card_hashes, enemy_intents, energy=3, failed_hashes=None, failed_indices=None, enemy_hps=None, player_statuses=None, enemy_statuses=None, player_hp=None, incoming_damage=0, player_block=0, relics=None):
        """
        Adaptive spinal reflex choice based on Q-learning card databases and enemy intent.
        """
        if failed_hashes is None:
            failed_hashes = set()
        if failed_indices is None:
            failed_indices = set()
        if player_statuses is None:
            player_statuses = {"vulnerable": False, "weak": False, "frail": False, "poison": 0}
        if enemy_statuses is None:
            enemy_statuses = []
            
        cards = elements.get("cards", [])
        enemies = elements.get("enemies", [])
        end_turn_btn = elements.get("end_turn_btn")
        
        # Filter cards that have failed to play this turn
        filtered_cards = []
        filtered_hashes = []
        for idx, coord in enumerate(cards):
            chash = card_hashes[idx] if idx < len(card_hashes) else None
            
            # 1. Filter by index
            if idx in failed_indices:
                continue
                
            # 2. Filter by hash similarity (Hamming distance <= 3)
            is_failed_hash = False
            if chash:
                for f_hash in failed_hashes:
                    if f_hash:
                        # Compute Hamming distance
                        dist = sum(c1 != c2 for c1, c2 in zip(chash, f_hash))
                        if dist <= 3:
                            is_failed_hash = True
                            break
            if is_failed_hash:
                continue
                
            filtered_cards.append(coord)
            filtered_hashes.append(chash)
            
        cards = filtered_cards
        card_hashes = filtered_hashes
        
        if self.play_count_this_turn >= 5 or energy <= 0:
            return "END_TURN", end_turn_btn, None
            
        # Check if any enemy is attacking
        is_attacked = any(enemy_intents)
        self.log(f"Deciding action. Enemy is attacking: {is_attacked} (Incoming damage: {incoming_damage}, Player block: {player_block})")
        
        # Sort cards in hand by score and intent matching
        evaluated_cards = []
        for idx, coord in enumerate(cards):
            chash = card_hashes[idx] if idx < len(card_hashes) else None
            
            # Look up cost and name from db (default to 1, "")
            card_cost = 1
            card_name = ""
            if chash and chash in self.learning.card_db:
                card_cost = self.learning.card_db[chash].get("cost", 1)
                card_name = self.learning.card_db[chash].get("name", "").lower()
                
            # Skip if cost exceeds remaining energy
            if card_cost > energy:
                continue
                
            if not chash:
                # If no hash available, give neutral priority
                evaluated_cards.append((coord, chash, 0.0, "UNKNOWN"))
                continue
                
            category = self.learning.get_card_category(chash)
            score = self.learning.get_card_score(chash)
            
            # Dynamic block calculation based on incoming damage and current block
            needed_block = max(0, incoming_damage - player_block)
            
            # Situation boost
            situational_boost = 0.0
            if category == "DEFEND":
                if needed_block > 0:
                    situational_boost = 110.0  # Prioritize block if we are going to take damage
                    if player_statuses.get("frail", False):
                        situational_boost += 20.0  # Boost block priority further because each block card is less effective when Frail!
                else:
                    situational_boost = -30.0  # Save energy if we are already safe!
            elif category == "ATTACK":
                if needed_block == 0:
                    situational_boost = 60.0   # Play attack cards if safe
                else:
                    situational_boost = 30.0   # Lower priority to attacks if we still need block

            # --- Relic Situational Boosts ---
            relics_lower = [r.get("id", "").lower() for r in (relics or [])]
            
            # A. Calipers: keep block, so don't penalize block when safe
            if any("calipers" in r for r in relics_lower):
                if category == "DEFEND" and needed_block == 0:
                    situational_boost = 20.0  # Encourage stacking block
                    
            # B. Orichalcum: if player block is 0 and we are taking <= 6 damage, we don't need to block
            if any("orichalcum" in r for r in relics_lower) and player_block == 0:
                needed_block = max(0, incoming_damage - 6)
                if category == "DEFEND":
                    if needed_block > 0:
                        situational_boost = 110.0
                    else:
                        situational_boost = -30.0
                        
            # C. Kunai / Shuriken combo: encourage hitting 3 attacks
            if category == "ATTACK" and (any("kunai" in r for r in relics_lower) or any("shuriken" in r for r in relics_lower)):
                if self.attacks_played_this_turn in [1, 2]:
                    situational_boost += 40.0  # Push to hit 3-attack combo
                    
            # D. Pen Nib counter checking
            pen_nib_ready = False
            for relic in (relics or []):
                r_id = relic.get("id", "").lower()
                if "pen_nib" in r_id or "pennib" in r_id:
                    props = relic.get("props", {})
                    for int_prop in props.get("ints", []):
                        if int_prop.get("name") in ["PenNibCounter", "Counter", "TimesUsed", "times_used"]:
                            if int_prop.get("value", 0) == 9:
                                pen_nib_ready = True
                                break
                                
            if pen_nib_ready and category == "ATTACK":
                if any(kw in card_name for kw in ["bash", "バッシュ", "carnage", "カルネージ", "hyperbeam", "ハイパービーム", "heavy blade", "ヘビーブレード"]):
                    situational_boost += 100.0
                elif any(kw in card_name for kw in ["strike", "ストライク", "anger", "怒り", "beam cell", "ビームセル"]):
                    situational_boost -= 50.0
                
            # --- Advanced Heuristics for Phase 2 ---
            # A. Play order priority (Bash, Neutralize, Power cards first)
            if self.play_count_this_turn == 0:
                if any(kw in card_name for kw in ["bash", "バッシュ", "無力化", "neutralize"]):
                    situational_boost += 80.0
                elif any(kw in card_name for kw in ["form", "フォーム", "footwork", "フットワーク", "fumes", "毒の", "inflame", "発火", "defragment", "デフラグ", "biased", "認知偏向", "feel no pain", "無痛", "dark embrace", "闇の抱擁", "corruption", "堕落", "loop", "ループ"]):
                    situational_boost += 90.0  # Focus & Exhaust powers first!
                    
            # B. Status Effect interactions
            # 1. Vulnerable (弱体) -> Attacks do 50% more damage
            any_enemy_vulnerable = any(estat.get("vulnerable", False) for estat in enemy_statuses) if enemy_statuses else False
            if any_enemy_vulnerable and category == "ATTACK":
                situational_boost += 30.0
                
            # 2. Player Weak (脱力) -> Player deals 25% less damage
            if player_statuses.get("weak", False) and category == "ATTACK":
                situational_boost -= 20.0
                
            # 3. Enemy Poison (毒) -> If enemy will die from poison, go full turtle (defend only)
            enemy_will_die_from_poison = False
            if enemy_hps and enemy_statuses:
                for e_idx in range(min(len(enemy_hps), len(enemy_statuses))):
                    e_hp = enemy_hps[e_idx]
                    e_poison = enemy_statuses[e_idx].get("poison", 0)
                    if e_poison >= e_hp and e_hp > 0:
                        enemy_will_die_from_poison = True
                        break
            if enemy_will_die_from_poison:
                if category == "DEFEND":
                    situational_boost += 120.0  # Highly prioritize defending!
                elif category == "ATTACK":
                    situational_boost -= 80.0   # Do not waste attacks
                    
            # 4. Defect Orb heuristics (Zap, Frost, etc.)
            if any(kw in card_name for kw in ["zap", "ザップ"]):
                category = "ATTACK"  # Channels lightning (deals damage)
                situational_boost += 10.0
            elif any(kw in card_name for kw in ["frost", "フロスト", "cold snap", "コールドスナップ", "glacier", "グレイシア"]):
                category = "DEFEND"  # Channels frost (gives block)
                situational_boost += 30.0
            elif any(kw in card_name for kw in ["electrodynamics", "エレクトロダイナミクス"]):
                category = "ATTACK"
                if len(enemies) > 1:
                    situational_boost += 80.0  # Highly prioritize electrodynamics for multi-enemy fights
                else:
                    situational_boost += 20.0
                    
            # 5. Player HP heuristic (defend when low)
            if player_hp and category == "DEFEND":
                curr_php, max_php = player_hp
                if curr_php / max_php < 0.35:
                    situational_boost += 40.0  # Safe play boost when health is low
                    
            # 6. Status/Curse cards (Slimed, Wound, etc.) - Dynamic penalty
            if category == "CURSE" or any(kw in card_name for kw in ["slimed", "スライム", "dazed", "めまい", "wound", "傷口", "burn", "火傷", "void", "空虚", "decay", "腐敗", "doubt", "疑心", "shame", "羞恥", "regret", "後悔", "injury", "怪我", "pain", "痛み", "parasite", "寄生虫", "clumsy", "お荷物", "normality", "curse", "呪い"]):
                category = "CURSE"
                situational_boost -= 200.0  # Avoid playing status/curse cards
                
            total_priority = score + situational_boost
            evaluated_cards.append((coord, chash, total_priority, category))
            
        if not evaluated_cards:
            return "END_TURN", end_turn_btn, None
            
        # Sort descending by priority
        evaluated_cards.sort(key=lambda x: x[2], reverse=True)
        
        best_coord, best_hash, best_score, best_cat = evaluated_cards[0]
        
        # Select best target enemy for attacks
        target_enemy = enemies[0] if enemies else (600, 350)
        if best_cat == "ATTACK" and len(enemies) > 1:
            if not enemy_hps or len(enemy_hps) != len(enemies):
                enemy_hps = [50] * len(enemies)
                
            best_target_idx = 0
            best_target_score = -99999.0
            for idx, enemy_coord in enumerate(enemies):
                curr_hp = enemy_hps[idx] if idx < len(enemy_hps) else 50
                is_attacking = enemy_intents[idx] if idx < len(enemy_intents) else False
                
                # Check status for this specific enemy
                e_status = enemy_statuses[idx] if enemy_statuses and idx < len(enemy_statuses) else {}
                is_vulnerable = e_status.get("vulnerable", False)
                e_poison = e_status.get("poison", 0)
                
                score = -curr_hp
                if is_attacking:
                    score += 50.0
                if is_vulnerable:
                    score += 80.0
                if curr_hp < 15:
                    score += 200.0
                if e_poison >= curr_hp:
                    score -= 500.0  # Do not waste attacks on already dying enemies!
                    
                if score > best_target_score:
                    best_target_score = score
                    best_target_idx = idx
            target_enemy = enemies[best_target_idx]
            self.log(f"🎯 Smart Target: Selected enemy index {best_target_idx} at {target_enemy} (HP: {enemy_hps[best_target_idx]}, Attacking: {enemy_intents[best_target_idx]})")
        
        self.play_count_this_turn += 1
        if best_cat == "ATTACK":
            self.attacks_played_this_turn += 1
        self.log(f"Decision: Play card {self.play_count_this_turn} (hash: {best_hash}, category: {best_cat}, priority: {best_score})")
        
        return "PLAY_CARD", best_coord, target_enemy

    def decide_reward_choice(self, reward_hashes):
        """
        Selects the card reward with the highest Q-learning score.
        """
        if not reward_hashes:
            return 0
            
        best_idx = 0
        best_score = -9999.0
        
        for idx, rhash in enumerate(reward_hashes):
            if not rhash:
                score = 0.0
            else:
                score = self.learning.get_card_score(rhash)
            self.log(f"Reward Option {idx} hash: {rhash} has score {score}")
            if score > best_score:
                best_score = score
                best_idx = idx
                
        self.log(f"Decision: Selected reward option {best_idx} with score {best_score}")
        return best_idx

    def decide_map_node(self, nodes):
        """
        Picks the node coordinates for ascent.
        """
        if not nodes:
            return None
        choice = nodes[0]
        self.log(f"Map decision: traversal to node at {choice}")
        return choice
