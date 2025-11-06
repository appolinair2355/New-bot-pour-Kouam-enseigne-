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
            logger.info(f"✅ PREMIÈRE PRÉDICTION - Aucun cooldown actif")
            return True
        time_since_last = current_time - self.last_prediction_time
        if time_since_last < self.prediction_cooldown:
            remaining = int(self.prediction_cooldown - time_since_last)
            logger.warning(f"🚫 COOLDOWN ACTIF - {remaining}s restantes (délai configuré: {int(self.prediction_cooldown)}s)")
            logger.warning(f"💡 Pour tester immédiatement, envoyez la commande: /att 0")
            return False
        logger.info(f"✅ COOLDOWN TERMINÉ - Prédiction autorisée (dernière prédiction il y a {int(time_since_last)}s)")
        return True

    def should_predict(self, message: str) -> Tuple[bool, Optional[int], Optional[str]]:
        logger.info(f"🔎 Analyse message pour prédiction...")
        
        game_number = self.extract_game_number(message)
        if not game_number:
            logger.debug("❌ Numéro de partie non trouvé")
            return False, None, None

        logger.info(f"📍 Partie détectée: #{game_number}")

        if not self.has_completion_indicators(message):
            logger.debug("❌ Pas d'indicateur de complétion (✅/🔰)")
            return False, None, None

        card = self.extract_card_from_first_parentheses(message)
        if not card:
            logger.debug("❌ Aucune carte trouvée dans les parenthèses")
            return False, None, None

        logger.info(f"🃏 Carte détectée: {card}")

        predicted_costume = PREDICTION_RULES.get(card)
        if not predicted_costume:
            logger.debug(f"❌ Pas de règle de prédiction pour {card}")
            return False, None, None

        logger.info(f"🎲 Règle trouvée: {card} → {predicted_costume}")

        if not self.can_make_prediction():
            logger.warning("⏰ Cooldown actif - prédiction refusée")
            return False, None, None

        message_hash = hash(message)
        if message_hash in self.processed_messages:
            logger.debug("⚠️ Message déjà traité")
            return False, None, None

        self.processed_messages.add(message_hash)
        self.last_prediction_time = time.time()
        self._save_last_prediction_time()

        target_game = game_number + 2
        logger.info(f"🎯 ✅ PRÉDICTION VALIDÉE - Partie {game_number} → Prédit {target_game}: {predicted_costume}")
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
            logger.debug("❌ Aucun numéro de partie trouvé dans le message")
            return None

        if not self.has_completion_indicators(text):
            logger.debug(f"❌ Partie #{game_number} sans indicateur de complétion")
            return None

        logger.info(f"🔍 VÉRIFICATION PARTIE #{game_number}")
        logger.info(f"📝 Message reçu: {text[:150]}...")

        for predicted_game in sorted(self.predictions.keys()):
            prediction = self.predictions[predicted_game]
            if prediction.get('status') != 'pending':
                logger.debug(f"⏭️ Partie {predicted_game} déjà vérifiée (statut: {prediction.get('status')})")
                continue

            predicted_costume = prediction.get('predicted_costume')
            if not predicted_costume:
                continue

            logger.info(f"📊 PRÉDICTION EN ATTENTE: Partie {predicted_game} → {predicted_costume}")

            # Vérifier prédit+0, prédit+1, prédit+2, prédit+3
            for offset in range(0, 4):
                target_game = predicted_game + offset
                if game_number == target_game:
                    logger.info(f"🎯 MATCH! Partie #{game_number} = Prédit+{offset} (base: #{predicted_game})")
                    
                    if self.check_costume_in_first_parentheses(text, predicted_costume):
                        status_symbol = f"✅{offset}️⃣"
                        original_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :⏳"
                        updated_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :{status_symbol}"
                        prediction['status'] = 'correct'
                        prediction['final_message'] = updated_message
                        prediction['verified_at_offset'] = offset
                        logger.info(f"✅ SUCCÈS +{offset}! Mise à jour: {updated_message}")
                        return {
                            'type': 'edit_message',
                            'predicted_game': predicted_game,
                            'new_message': updated_message,
                            'original_message': original_message
                        }
                    else:
                        logger.info(f"⏭️ Costume '{predicted_costume}' non trouvé à prédit+{offset}, continue vérification...")
                        # Ne pas arrêter, continuer à chercher jusqu'à +3
                        if offset < 3:
                            continue
                        else:
                            # Si on a vérifié jusqu'à +3 sans succès, c'est un échec
                            logger.warning(f"❌ Costume non trouvé après vérification +0 à +3")
            
            # Si game_number > predicted_game + 3, la prédiction a échoué
            if game_number > predicted_game + 3:
                original_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :⏳"
                updated_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :❌"
                prediction['status'] = 'failed'
                prediction['final_message'] = updated_message
                logger.info(f"❌ ÉCHEC CONFIRMÉ: Partie #{game_number} dépasse prédit+3 (#{predicted_game}+3)")
                logger.info(f"📝 Mise à jour finale: {updated_message}")
                return {
                    'type': 'edit_message',
                    'predicted_game': predicted_game,
                    'new_message': updated_message,
                    'original_message': original_message
                }

        logger.debug(f"ℹ️ Aucune prédiction à vérifier pour partie #{game_number}")
        return None

    def check_costume_in_first_parentheses(self, message: str, predicted_costume: str) -> bool:
        message = message.replace("❤️", "♥️")
        predicted_costume = predicted_costume.replace("❤️", "♥️")
        match = re.search(r'\(([^)]+)\)', message)
        if not match:
            return False
        first_content = match.group(1)
        return predicted_costume in first_content

    def reset_all_predictions(self) -> None:
        """Reset all predictions and clear all tracking data"""
        self.predictions.clear()
        self.processed_messages.clear()
        self.sent_predictions.clear()
        self.temporary_messages.clear()
        self.pending_edits.clear()
        logger.info("🔄 All predictions reset")

# Global instance
card_predictor = CardPredictor()
