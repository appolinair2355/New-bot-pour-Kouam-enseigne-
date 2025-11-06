"""
Card prediction logic for Joker's Telegram Bot - simplified for webhook deployment
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import time
import os
import json

logger = logging.getLogger(__name__)

# Configuration constants
VALID_CARD_COMBINATIONS = [
    "♠️♥️♦️", "♠️♥️♣️", "♠️♦️♣️", "♥️♦️♣️"
]

CARD_SYMBOLS = ["♠️", "♥️", "♦️", "♣️", "❤️"]  # Include both ♥️ and ❤️ variants

# NOUVELLES RÈGLES DE PRÉDICTION BASÉES SUR LES CARTES
# La carte doit être détectée dans les PREMIÈRES parenthèses du message.
# Normalisation: ❤️ est traité comme ♥️.
PREDICTION_RULES = {
    "10♦️": "♠️",
    "10♠️": "♥️",  # ❤️ est remplacé par ♥️ pour cohérence
    "9♣️": "♥️",
    "9♦️": "♠️",
    "8♣️": "♠️",
    "8♠️": "♣️",
    "7♠️": "♠️",
    "7♣️": "♣️",
    "6♦️": "♣️",
    "6♣️": "♦️",
}

# Target channel ID for Baccarat Kouamé
TARGET_CHANNEL_ID = -1002682552255

# Target channel ID for predictions and updates
PREDICTION_CHANNEL_ID = -1002875505624

class CardPredictor:
    """Handles card prediction logic for webhook deployment"""

    def __init__(self):
        self.predictions = {}  # Store predictions for verification
        self.processed_messages = set()  # Avoid duplicate processing
        self.sent_predictions = {}  # Store sent prediction messages for editing
        self.temporary_messages = {}  # Store temporary messages waiting for final edit
        self.pending_edits = {}  # Store messages waiting for edit with indicators
        self.position_preference = 1  # Default position preference (1 = first card, 2 = second card)
        self.redirect_channels = {}  # Store redirection channels for different chats
        self.last_prediction_time = self._load_last_prediction_time()  # Load persisted timestamp
        self.prediction_cooldown = 30   # Cooldown period in seconds between predictions

    def _load_last_prediction_time(self) -> float:
        """Load last prediction timestamp from file"""
        try:
            if os.path.exists('.last_prediction_time'):
                with open('.last_prediction_time', 'r') as f:
                    timestamp = float(f.read().strip())
                    logger.info(f"⏰ PERSISTANCE - Dernière prédiction chargée: {time.time() - timestamp:.1f}s écoulées")
                    return timestamp
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger le timestamp: {e}")
        return 0

    def _save_last_prediction_time(self):
        """Save last prediction timestamp to file"""
        try:
            with open('.last_prediction_time', 'w') as f:
                f.write(str(self.last_prediction_time))
        except Exception as e:
            logger.warning(f"⚠️ Impossible de sauvegarder le timestamp: {e}")

    def reset_predictions(self):
        """Reset all prediction states - useful for recalibration"""
        self.predictions.clear()
        self.processed_messages.clear()
        self.sent_predictions.clear()
        self.temporary_messages.clear()
        self.pending_edits.clear()
        self.last_prediction_time = 0
        self._save_last_prediction_time()
        logger.info("🔄 Système de prédictions réinitialisé")

    def set_position_preference(self, position: int):
        """Set the position preference for card selection (1 or 2)"""
        if position in [1, 2]:
            self.position_preference = position
            logger.info(f"🎯 Position de carte mise à jour : {position}")
        else:
            logger.warning(f"⚠️ Position invalide : {position}. Utilisation de la position par défaut (1).")

    def set_redirect_channel(self, source_chat_id: int, target_chat_id: int):
        """Set redirection channel for predictions from a source chat"""
        self.redirect_channels[source_chat_id] = target_chat_id
        logger.info(f"📤 Redirection configurée : {source_chat_id} → {target_chat_id}")

    def get_redirect_channel(self, source_chat_id: int) -> int:
        """Get redirect channel for a source chat, fallback to PREDICTION_CHANNEL_ID"""
        return self.redirect_channels.get(source_chat_id, PREDICTION_CHANNEL_ID)

    def reset_all_predictions(self):
        """Reset all predictions and redirect channels"""
        self.predictions.clear()
        self.processed_messages.clear()
        self.sent_predictions.clear()
        self.temporary_messages.clear()
        self.pending_edits.clear()
        self.redirect_channels.clear()
        self.last_prediction_time = 0
        self._save_last_prediction_time()
        logger.info("🔄 Toutes les prédictions et redirections ont été supprimées")

    def extract_game_number(self, message: str) -> Optional[int]:
        """Extract game number from message like #n744 or #N744"""
        pattern = r'#[nN](\d+)'
        match = re.search(pattern, message)
        if match:
            return int(match.group(1))
        return None

    def has_pending_indicators(self, text: str) -> bool:
        """Check if message contains indicators suggesting it will be edited"""
        indicators = ['⏰', '▶', '🕐', '➡️']
        return any(indicator in text for indicator in indicators)

    def has_completion_indicators(self, text: str) -> bool:
        """Check if message contains completion indicators after edit - ✅ OR 🔰 indicates completion"""
        completion_indicators = ['✅', '🔰']
        has_indicator = any(indicator in text for indicator in completion_indicators)
        if has_indicator:
            indicator_found = next(ind for ind in completion_indicators if ind in text)
            logger.info(f"🔍 FINALISATION DÉTECTÉE - Indicateur {indicator_found} trouvé dans: {text[:100]}...")
        return has_indicator

    def extract_card_number_and_costume(self, message: str) -> Optional[str]:
        """
        Extracts the first card that matches the PREDICTION_RULES keys 
        from the FIRST parentheses.
        Format: "10♦️" or "8♠️"
        """
        # 1. Normalize message (replace ❤️ with ♥️)
        normalized_message = message.replace("❤️", "♥️")

        # 2. Extract only the content of the FIRST parentheses
        pattern_parentheses = r'\(([^)]+)\)'
        matches = re.findall(pattern_parentheses, normalized_message)

        if not matches:
            logger.info(f"🔍 Carte - Aucun parenthèses trouvé.")
            return None

        first_parentheses_content = matches[0]
        logger.info(f"🔍 Carte - Contenu première parenthèse: {first_parentheses_content}")

        # 3. Search for the relevant cards directly based on the PREDICTION_RULES keys
        
        # NOTE: Using direct searches to ensure we only look for the *exact* required cards 
        # in the PREMIER groupe de parenthèses.

        # Order of search matters if one card is a substring of another, but here 
        # card strings are unique. We search for the 10 specific keys.

        for card_key in PREDICTION_RULES.keys():
            if card_key in first_parentheses_content:
                logger.info(f"🔍 Carte - Correspondance trouvée pour la règle: {card_key}")
                return card_key
        
        logger.info("🔍 Carte - Aucune des 10 cartes de prédiction trouvée dans la première parenthèse.")
        return None
        

    def can_make_prediction(self) -> bool:
        """Check if enough time has passed since last prediction (30 seconds cooldown)"""
        current_time = time.time()

        if self.last_prediction_time == 0:
            logger.info(f"⏰ PREMIÈRE PRÉDICTION: Aucune prédiction précédente, autorisation accordée")
            return True

        time_since_last = current_time - self.last_prediction_time

        if time_since_last >= self.prediction_cooldown:
            logger.info(f"⏰ COOLDOWN OK: {time_since_last:.1f}s écoulées depuis dernière prédiction (≥{self.prediction_cooldown}s)")
            return True
        else:
            remaining = self.prediction_cooldown - time_since_last
            logger.info(f"⏰ COOLDOWN ACTIF: Encore {remaining:.1f}s à attendre avant prochaine prédiction")
            return False

    def should_predict(self, message: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        RÈGLES DE PRÉDICTION FINALES:
        1. Exclure #R, #X
        2. Le message DOIT être un message de finalisation (✅ ou 🔰)
        3. Règle des 10 Cartes Spécifiques (vérifiée dans la première parenthèse)
        4. Vérification du cooldown
        Returns: (should_predict, game_number, predicted_costume)
        """
        # Extract game number
        game_number = self.extract_game_number(message)
        if not game_number:
            return False, None, None

        logger.debug(f"🔮 PRÉDICTION - Analyse du jeu {game_number}")

        # EXCLUSIONS PRIORITAIRES
        if '#R' in message:
            logger.info(f"🔮 EXCLUSION - Jeu {game_number}: Contient #R, pas de prédiction")
            return False, None, None

        if '#X' in message:
            logger.info(f"🔮 EXCLUSION - Jeu {game_number}: Contient #X (match nul), pas de prédiction")
            return False, None, None

        # Le message DOIT être un message de finalisation (✅ ou 🔰)
        if not self.has_completion_indicators(message):
             logger.info(f"🔮 Jeu {game_number}: Message non finalisé, pas de prédiction")
             return False, None, None

        # Skip if we already have a prediction for target game number (+2)
        target_game = game_number + 2
        if target_game in self.predictions and self.predictions[target_game].get('status') == 'pending':
            logger.info(f"🔮 Jeu {game_number}: Prédiction N{target_game} déjà existante, éviter doublon")
            return False, None, None

        # NOUVELLE RÈGLE : Détecter la carte spécifique dans la première parenthèse
        detected_card = self.extract_card_number_and_costume(message)
        predicted_costume = PREDICTION_RULES.get(detected_card)

        if predicted_costume:
            logger.info(f"🔮 RÈGLE APPLIQUÉE: Carte {detected_card} détectée → Prédire {predicted_costume} pour jeu {target_game}")

            # CHECK COOLDOWN BEFORE FINAL PREDICTION
            if not self.can_make_prediction():
                logger.info(f"🔮 COOLDOWN - Jeu {game_number}: Attente cooldown de {self.prediction_cooldown}s, prédiction différée")
                return False, None, None
                
            # Prevent duplicate processing
            message_hash = hash(message)
            if message_hash not in self.processed_messages:
                self.processed_messages.add(message_hash)
                # Update last prediction timestamp and save
                self.last_prediction_time = time.time()
                self._save_last_prediction_time()
                logger.info(f"🔮 PREDICTION - Game {game_number}: GENERATING prediction for game {target_game} with costume {predicted_costume}")
                logger.info(f"⏰ COOLDOWN - Next prediction possible in {self.prediction_cooldown}s")
                return True, game_number, predicted_costume
            else:
                logger.info(f"🔮 PREDICTION - Game {game_number}: ⚠️ Already processed")
                return False, None, None
        else:
            logger.info(f"🔮 AUCUNE RÈGLE - Jeu {game_number}: Carte {detected_card} non listée ou non trouvée.")
            return False, None, None

    def make_prediction(self, game_number: int, predicted_costume: str) -> str:
        """Make a prediction for game +2 with the predicted costume"""
        target_game = game_number + 2

        # Simplified prediction message format
        prediction_text = f"🔵{target_game}🔵:{predicted_costume}statut :⏳"

        # Store the prediction for later verification
        self.predictions[target_game] = {
            'predicted_costume': predicted_costume,
            'status': 'pending',
            'predicted_from': game_number,
            'verification_count': 0,
            'message_text': prediction_text
        }

        logger.info(f"Made prediction for game {target_game} based on costume {predicted_costume}")
        return prediction_text

    def get_costume_text(self, costume_emoji: str) -> str:
        """Convert costume emoji to text representation"""
        costume_map = {
            "♠️": "pique",
            "♥️": "coeur",
            "♦️": "carreau",
            "♣️": "trèfle"
        }
        return costume_map.get(costume_emoji, "inconnu")

    def verify_prediction(self, message: str) -> Optional[Dict]:
        """Verify if a prediction was correct (regular messages)"""
        return self._verify_prediction_common(message, is_edited=False)

    def verify_prediction_from_edit(self, message: str) -> Optional[Dict]:
        """Verify if a prediction was correct from edited message (enhanced verification)"""
        return self._verify_prediction_common(message, is_edited=True)

    def check_costume_in_first_parentheses(self, message: str, predicted_costume: str) -> bool:
        """Vérifier si le costume prédit apparaît dans le PREMIER parenthèses"""
        # Normaliser ❤️ vers ♥️ pour cohérence
        normalized_message = message.replace("❤️", "♥️")
        normalized_costume = predicted_costume.replace("❤️", "♥️")

        # Extraire SEULEMENT le contenu du PREMIER parenthèses
        pattern = r'\(([^)]+)\)'
        matches = re.findall(pattern, normalized_message)

        if not matches:
            logger.info(f"🔍 Aucun parenthèses trouvé dans le message")
            return False

        first_parentheses_content = matches[0]  # SEULEMENT le premier
        logger.info(f"🔍 VÉRIFICATION PREMIER PARENTHÈSES SEULEMENT: {first_parentheses_content}")

        costume_found = normalized_costume in first_parentheses_content
        logger.info(f"🔍 Recherche costume {normalized_costume} dans PREMIER parenthèses: {costume_found}")
        return costume_found

    def _verify_prediction_common(self, text: str, is_edited: bool = False) -> Optional[Dict]:
        """SYSTÈME DE VÉRIFICATION ÉTENDU - Vérifie décalage +0, +1, +2, +3, puis ❌"""
        game_number = self.extract_game_number(text)
        if not game_number:
            return None

        logger.info(f"🔍 VÉRIFICATION ÉTENDUE - Jeu {game_number} (édité: {is_edited})")

        has_success_symbol = self.has_completion_indicators(text)
        if not has_success_symbol:
            logger.info(f"🔍 ⏸️ Pas de vérification - Aucun symbole de succès (✅ ou 🔰) trouvé")
            return None

        # Si aucune prédiction stockée, pas de vérification possible
        if not self.predictions:
            logger.info(f"🔍 ✅ VÉRIFICATION TERMINÉE - Aucune prédiction éligible pour le jeu {game_number}")
            return None

        # VÉRIFICATION SÉQUENTIELLE: offset 0 → +1 → +2 → +3 → ❌
        for predicted_game in sorted(self.predictions.keys()):
            prediction = self.predictions[predicted_game]

            # Vérifier seulement les prédictions en attente
            if prediction.get('status') != 'pending':
                logger.info(f"🔍 ⏭️ Prédiction {predicted_game} déjà traitée (statut: {prediction.get('status')})")
                continue

            verification_offset = game_number - predicted_game
            logger.info(f"🔍 🎯 VÉRIFICATION - Prédiction {predicted_game} vs jeu actuel {game_number}, décalage: {verification_offset}")

            predicted_costume = prediction.get('predicted_costume')
            if not predicted_costume:
                logger.info(f"🔍 ❌ Pas de costume prédit stocké pour le jeu {predicted_game}")
                continue
                
            # Définir le statut par défaut et le symbole de succès
            status_symbol = None
            should_fail = False

            if verification_offset == 0:
                status_symbol = "✅0️⃣"
            elif verification_offset == 1:
                status_symbol = "✅1️⃣"
            elif verification_offset == 2:
                status_symbol = "✅2️⃣"
            elif verification_offset == 3:
                status_symbol = "✅3️⃣"
            elif verification_offset > 3:
                # Si le jeu actuel est au-delà du dernier offset à vérifier (+3), la prédiction a échoué.
                status_symbol = "❌"
                should_fail = True
            else:
                # Décalage négatif (jeu plus ancien que la prédiction) ou autre cas non pertinent
                logger.info(f"🔍 ⏭️ OFFSET {verification_offset} ignoré (hors plage de vérification)")
                continue

            # Vérification du costume (si ce n'est pas déjà un échec dû à l'offset > +3)
            costume_found = False
            if not should_fail:
                costume_found = self.check_costume_in_first_parentheses(text, predicted_costume)

            if costume_found:
                # SUCCÈS - Mise à jour et arrêt pour cette prédiction
                original_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :⏳"
                updated_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :{status_symbol}"

                prediction['status'] = 'correct'
                prediction['verification_count'] = verification_offset # Stocke l'offset de succès
                prediction['final_message'] = updated_message

                logger.info(f"🔍 ✅ SUCCÈS OFFSET {verification_offset} - Costume {predicted_costume} trouvé")
                logger.info(f"🔍 🛑 ARRÊT - Vérification terminée: {status_symbol}")

                return {
                    'type': 'edit_message',
                    'predicted_game': predicted_game,
                    'new_message': updated_message,
                    'original_message': original_message
                }
            
            elif should_fail:
                # ÉCHEC - Marquer ❌ et arrêter pour cette prédiction (si offset > +3)
                original_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :⏳"
                updated_message = f"🔵{predicted_game}🔵:{predicted_costume}statut :❌"

                prediction['status'] = 'failed'
                prediction['final_message'] = updated_message

                logger.info(f"🔍 ❌ ÉCHEC FINAL - Offset {verification_offset} dépassé, prédiction marquée: ❌")

                return {
                    'type': 'edit_message',
                    'predicted_game': predicted_game,
                    'new_message': updated_message,
                    'original_message': original_message
                }
            else:
                # ÉCHEC au décalage actuel (0, +1, +2 ou +3)
                # La prédiction reste 'pending' et attend le prochain message (jeu suivant)
                logger.info(f"🔍 ❌ ÉCHEC OFFSET {verification_offset} - Costume non trouvé, attente du prochain jeu...")
                continue # Continuer la boucle pour vérifier la prochaine prédiction en attente (si elle existe)
                
        logger.info(f"🔍 ✅ VÉRIFICATION TERMINÉE - Aucune prédiction éligible/terminée pour le jeu {game_number}")
        return None

# Global instance
card_predictor = CardPredictor()
