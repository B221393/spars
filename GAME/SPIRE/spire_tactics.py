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

    def decide_combat_action(self, elements, card_hashes, enemy_intents, energy=3):
        """
        Adaptive spinal reflex choice based on Q-learning card databases and enemy intent.
        """
        cards = elements.get("cards", [])
        enemies = elements.get("enemies", [])
        end_turn_btn = elements.get("end_turn_btn")
        
        if not cards or self.play_count_this_turn >= 5 or energy <= 0:
            return "END_TURN", end_turn_btn, None
            
        target_enemy = enemies[0] if enemies else (600, 350)
        
        # Check if any enemy is attacking
        is_attacked = any(enemy_intents)
        self.log(f"Deciding action. Enemy is attacking: {is_attacked}")
        
        # Sort cards in hand by score and intent matching
        evaluated_cards = []
        for idx, coord in enumerate(cards):
            chash = card_hashes[idx] if idx < len(card_hashes) else None
            if not chash:
                # If no hash available, give neutral priority
                evaluated_cards.append((coord, chash, 0.0, "UNKNOWN"))
                continue
                
            category = self.learning.get_card_category(chash)
            score = self.learning.get_card_score(chash)
            
            # Situation boost
            situational_boost = 0.0
            if is_attacked and category == "DEFEND":
                situational_boost = 100.0  # Prioritize block
            elif not is_attacked and category == "ATTACK":
                situational_boost = 50.0   # Prioritize damage
                
            total_priority = score + situational_boost
            evaluated_cards.append((coord, chash, total_priority, category))
            
        # Sort descending by priority
        evaluated_cards.sort(key=lambda x: x[2], reverse=True)
        
        best_coord, best_hash, best_score, best_cat = evaluated_cards[0]
        
        self.play_count_this_turn += 1
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
