"""
Card prediction logic for Joker's Telegram Bot - final version with cooldown and fixed rules
"""
import re
import logging
import time
import os
from datetime import datetime
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Fixed prediction rules
PREDICTION_RULES = {
    "10♦️": "♠️",
    "10♠️": "❤️",
    "9♣️": "❤️",
    "9♦️": "♠️",
    "8♣️": "♠️",
    "8♠️": "♣️",
    "7♠️": "♠️",
    "7♣️": "♣️",
    "6♦️": "♣️",
    "6♣️": "♦️"
}

TARGET_CHANNEL_ID = -1002682552255
PREDICTION_CHANNEL_ID = -1002875505624

class CardPredictor:
    def __init__(self):
        self.predictions = {}
        self.processed_messages = set()
        self.sent_predictions = {}
        self.temporary_messages = {}
        self.pending_edits = {}
        self.position_preference = 1
        self.redirect_channels = {}
        self.last_prediction_time = self._load_last_prediction_time()
        self.prediction_cooldown = 300  # 5 minutes par défaut

    def _load_last_prediction_time(self) -> float:
        try:
            if os.path.exists('.last_prediction_time'):
                with open('.last_prediction_time', 'r') as f:
                    return float(f.read().strip())
        except Exception as e:
            logger.warning(f"Impossible de charger le timestamp: {e}")
        return 0

    def _save_last_prediction_time(self):
        try:
            with open('.last_prediction_time', 'w') as f:
                f.write(str(self.last_prediction_time))
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder le timestamp: {e}")

    def extract_game_number(self, message: str) -> Optional[int]:
        match = re.search(r'#[nN](\d+)', message)
        return int(match.group(1)) if match else None

    def extract_card_from_first_parentheses(self, message: str) -> Optional[str]:
        match = re.search(r'\(([^)]+)\)', message)
        if not match:
            return None
        content = match.group(1)
        for card in PREDICTION_RULES.keys():
            if card in content:
                return card
        return None

    def has_completion_indicators(self, text: str) -> bool:
        return any(ind in text for ind in ['✅', '🔰'])

    def can_make_prediction(self) -> bool:
        current_time = time.time()
        if self.last_prediction_time == 0:
            return True
        time_since_last = current_time - self.last_prediction_time
        if time_since_last < self.prediction_cooldown:
            logger.info(f"⏰ Cooldown actif - {int(self.prediction_cooldown - time_since_last)}s restantes")
            return False
        return True

    def should_predict(self, message: str) -> Tuple[bool, Optional[int], Optional[str]]:
        game_number = self.extract_game_number(message)
        if not game_number:
            return False, None, None

        if not self.has_completion_indicators(message):
            return False, None, None

        card = self.extract_card_from_first_parentheses(message)
        if not card:
            return False, None, None

        predicted_costume = PREDICTION_RULES.get(card)
        if not predicted_costume:
            return False, None, None

        if not self.can_make_prediction():
            return False, None, None

        message_hash = hash(message)
        if message_hash in self.processed_messages:
            return False, None, None

        self.processed_messages.add(message_hash)
        self.last_prediction_time = time.time()
        self._save_last_prediction_time()

        target_game = game_number + 2
        logger.info(f"🎯 Prédiction déclenchée pour jeu {target_game} : {predicted_costume}")
        return True, game_number, predicted_costume

    def make_prediction(self, game_number: int, predicted_costume: str) -> str:
        target_game = game_number + 2
        prediction_text = f"🔵{target_game}🔵:{predicted_costume}statut :⏳"
        self.predictions[target_game] = {
            'predicted_costume': predicted_costume,
            'status': 'pending',
            'predicted_from': game_number,
            'verification_count': 0,
            'message_text': prediction_text
        }
        return prediction_text

    def _verify_prediction_common(self, text: str, is_edited: bool = False) -> Optional[Dict]:
        game_number = self.extract_game_number(text)
        if not game_number:
            return None

        if not self.has_completion_indicators(text):
            return None

        for predicted_game in sorted(self.predictions.keys()):
            prediction = self.predictions[predicted_game]
            if prediction.get('status') != 'pending':
                continue

            predicted_costume = prediction.get('predicted_costume')
            if not predicted_costume:
                continue

            for offset in range(0, 4):
                target_game = predicted_game + offset
                if game_number == target_game:
                    if self.check_costume_in_first_parentheses(text, predicted_costume):
                        status_symbol = f"✅{offset}️⃣"
                        original_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :⏳"
                        updated_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :{status_symbol}"
                        prediction['status'] = 'correct'
                        prediction['final_message'] = updated_message
                        logger.info(f"✅ Mise à jour : {updated_message}")
                        return {
                            'type': 'edit_message',
                            'predicted_game': predicted_game,
                            'new_message': updated_message,
                            'original_message': original_message
                        }

            original_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :⏳"
            updated_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :❌"
            prediction['status'] = 'failed'
            prediction['final_message'] = updated_message
            logger.info(f"❌ Échec : {updated_message}")
            return {
                'type': 'edit_message',
                'predicted_game': predicted_game,
                'new_message': updated_message,
                'original_message': original_message
            }

        return None

    def check_costume_in_first_parentheses(self, message: str, predicted_costume: str) -> bool:
        message = message.replace("❤️", "♥️")
        predicted_costume = predicted_costume.replace("❤️", "♥️")
        match = re.search(r'\(([^)]+)\)', message)
        if not match:
            return False
        first_content = match.group(1)
        return predicted_costume in first_content

# Global instance
card_predictor = CardPredictor()
