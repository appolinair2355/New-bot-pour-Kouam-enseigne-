"""
Event handlers for the Telegram bot - adapted for webhook deployment
"""

import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any
import requests 

logger = logging.getLogger(__name__)

# Rate limiting storage
user_message_counts = defaultdict(list)

# Target channel ID for Baccarat Kouamé
TARGET_CHANNEL_ID = -1002682552255

# Target channel ID for predictions and updates
PREDICTION_CHANNEL_ID = -1002875505624 # <<< CORRECTION EFFECTUÉE ICI

# Configuration constants
GREETING_MESSAGE = """
🎭 Salut ! Je suis le bot de Joker DEPLOY299999 !
Ajoutez-moi à votre canal pour que je puisse saluer tout le monde ! 👋

🔮 Je peux analyser les combinaisons de cartes et faire des prédictions !
Utilisez /help pour voir toutes mes commandes.
"""

WELCOME_MESSAGE = """
🎭 **BIENVENUE DANS LE MONDE DE JOKER DEPLOY299999 !** 🔮

🎯 **COMMANDES DISPONIBLES:**
• `/start` - Accueil
• `/help` - Aide détaillée complète
• `/about` - À propos du bot  
• `/dev` - Informations développeur
• `/deploy` - Obtenir le package de déploiement pour render.com

🔧 **CONFIGURATION AVANCÉE:**
• `/cos [1|2]` - Position de carte
• `/cooldown [secondes]` - Délai entre prédictions  
• `/redirect` - Redirection des prédictions
• `/announce [message]` - Annonce officielle
• `/reset` - Réinitialiser le système

🔮 **FONCTIONNALITÉS SPÉCIALES:**
✓ Prédictions automatiques avec cooldown configurable
✓ Analyse des combinaisons de cartes en temps réel
✓ Système de vérification séquentiel avancé
✓ Redirection multi-canaux flexible
✓ Accès sécurisé avec autorisation utilisateur

🎯 **Version DEPLOY299999 - Port 10000**
"""

HELP_MESSAGE = """
🎯 **GUIDE D'UTILISATION DU BOT JOKER** 🔮

📝 **COMMANDES DE BASE:**
• `/start` - Message d'accueil
• `/help` - Afficher cette aide
• `/about` - Informations sur le bot
• `/dev` - Contact développeur
• `/deploy` - Package de déploiement
• `/ni` - Package modifié
• `/fin` - Package final complet

🔧 **COMMANDES DE CONFIGURATION:**
• `/cos [1|2]` - Position de carte pour prédictions
• `/cooldown [secondes]` - Modifier le délai entre prédictions
• `/redirect [source] [target]` - Redirection avancée des prédictions
• `/redi` - Redirection rapide vers le chat actuel
• `/announce [message]` - Envoyer une annonce officielle
• `/reset` - Réinitialiser toutes les prédictions

🔮 Fonctionnalités avancées :
- Le bot analyse automatiquement les messages contenant des combinaisons de cartes
- Il fait des prédictions basées sur les patterns détectés
- Gestion intelligente des messages édités
- Support des canaux et groupes
- Configuration personnalisée de la position de carte

🎴 Format des cartes :
Le bot reconnaît les symboles : ♠️ ♥️ ♦️ ♣️

📊 Le bot peut traiter les messages avec format #nXXX pour identifier les jeux.

🎯 Configuration des prédictions :
• /cos 1 - Utiliser la première carte
• /cos 2 - Utiliser la deuxième carte
⚠️ Si les deux premières cartes ont le même costume, la troisième sera utilisée automatiquement.
"""

ABOUT_MESSAGE = """
🎭 Bot Joker - Prédicteur de Cartes

🤖 Version : 2.0
🛠️ Développé avec Python et l'API Telegram
🔮 Spécialisé dans l'analyse de combinaisons de cartes

✨ Fonctionnalités :
- Prédictions automatiques
- Analyse de patterns
- Support multi-canaux
- Interface intuitive

🌟 Créé pour améliorer votre expérience de jeu !
"""

DEV_MESSAGE = """
👨‍💻 Informations Développeur :

🔧 Technologies utilisées :
- Python 3.11+
- API Telegram Bot
- Flask pour les webhooks
- Déployé sur Render.com

📧 Contact : 
Pour le support technique ou les suggestions d'amélioration, 
contactez l'administrateur du bot.

🚀 Le bot est open source et peut être déployé facilement !
"""

MAX_MESSAGES_PER_MINUTE = 30
RATE_LIMIT_WINDOW = 60

def is_rate_limited(user_id: int) -> bool:
    """Check if user is rate limited"""
    now = datetime.now()
    user_messages = user_message_counts[user_id]

    # Remove old messages outside the window
    user_messages[:] = [msg_time for msg_time in user_messages 
                       if now - msg_time < timedelta(seconds=RATE_LIMIT_WINDOW)]

    # Check if user exceeded limit
    if len(user_messages) >= MAX_MESSAGES_PER_MINUTE:
        return True

    # Add current message time
    user_messages.append(now)
    return False

class TelegramHandlers:
    """Handlers for Telegram bot using webhook approach"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}" # Replaced TelegramBot with base_url
        # Import card_predictor locally to avoid circular imports
        try:
            from card_predictor import card_predictor
            self.card_predictor = card_predictor
        except ImportError:
            logger.error("Failed to import card_predictor")
            self.card_predictor = None

        # Store redirected channels for each source chat
        self.redirected_channels = {} # {source_chat_id: target_chat_id}
        
        # Deployment file path - use depi_render_n2_fix.zip
        self.deployment_file_path = "depi_render_n2_fix.zip"

    def handle_update(self, update: Dict[str, Any]) -> None:
        """Handle incoming Telegram update with enhanced webhook support"""
        try:
            if 'message' in update:
                message = update['message']
                logger.info(f"🔄 Handlers - Traitement message normal")
                self._handle_message(message)
            elif 'edited_message' in update:
                message = update['edited_message']
                logger.info(f"🔄 Handlers - Traitement message édité pour prédictions/vérifications")
                self._handle_edited_message(message)
            else:
                logger.info(f"⚠️ Type d'update non géré: {list(update.keys())}")

        except Exception as e:
            logger.error(f"Error handling update: {e}")

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle regular messages"""
        try:
            chat_id = message['chat']['id']
            user_id = message.get('from', {}).get('id')
            sender_chat = message.get('sender_chat', {})
            sender_chat_id = sender_chat.get('id', chat_id)

            # Rate limiting check (skip for channels/groups)
            chat_type = message['chat'].get('type', 'private')
            if user_id and chat_type == 'private' and is_rate_limited(user_id):
                self.send_message(chat_id, "⏰ Veuillez patienter avant d'envoyer une autre commande.")
                return

            # Handle commands
            if 'text' in message:
                text = message['text'].strip()

                if text == '/start':
                    self._handle_start_command(chat_id, user_id)
                elif text == '/help':
                    self._handle_help_command(chat_id, user_id)
                elif text == '/about':
                    self._handle_about_command(chat_id, user_id)
                elif text == '/dev':
                    self._handle_dev_command(chat_id, user_id)
                elif text == '/deploy':
                    self._handle_deploy_command(chat_id, user_id)
                elif text == '/ni':
                    self._handle_ni_command(chat_id, user_id)
                elif text == '/pred':
                    self._handle_pred_command(chat_id, user_id)
                elif text.startswith('/cos'):
                    self._handle_cos_command(chat_id, text, user_id)
                elif text == '/redi':
                    self._handle_redi_command(chat_id, sender_chat_id, user_id)
                elif text == '/reset':
                    self._handle_reset_command(sender_chat_id, user_id)
                elif text.startswith('/cooldown'):
                    self._handle_cooldown_command(chat_id, text, user_id)
                elif text.startswith('/redirect'):
                    self._handle_redirect_command(chat_id, text, user_id)
                elif text.startswith('/announce'):
                    self._handle_announce_command(chat_id, text, user_id)
                elif text == '/fin':
                    self._handle_fin_command(chat_id, user_id)
                else:
                    # Handle regular messages - check for card predictions even in regular messages
                    self._handle_regular_message(message)

                    # Also process for card prediction in channels/groups (for polling mode)
                    if chat_type in ['group', 'supergroup', 'channel'] and self.card_predictor:
                        self._process_card_message(message)

                        # NOUVEAU: Vérification sur messages normaux aussi
                        self._process_verification_on_normal_message(message)

            # Handle new chat members
            if 'new_chat_members' in message:
                self._handle_new_chat_members(message)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _handle_edited_message(self, message: Dict[str, Any]) -> None:
        """Handle edited messages with enhanced webhook processing for predictions and verification"""
        try:
            chat_id = message['chat']['id']
            chat_type = message['chat'].get('type', 'private')
            user_id = message.get('from', {}).get('id')
            message_id = message.get('message_id')
            sender_chat = message.get('sender_chat', {})
            sender_chat_id = sender_chat.get('id', chat_id)

            logger.info(f"✏️ WEBHOOK - Message édité reçu ID:{message_id} | Chat:{chat_id} | Sender:{sender_chat_id}")

            # Rate limiting check (skip for channels/groups)
            if user_id and chat_type == 'private' and is_rate_limited(user_id):
                return

            # Process edited messages
            if 'text' in message:
                text = message['text']
                logger.info(f"✏️ WEBHOOK - Contenu édité: {text[:100]}...")

                # Skip card prediction if card_predictor is not available
                if not self.card_predictor:
                    logger.warning("❌ Card predictor not available")
                    return

                # Vérifier que c'est du canal autorisé
                if sender_chat_id != TARGET_CHANNEL_ID:
                    logger.info(f"🚫 Message édité ignoré - Canal non autorisé: {sender_chat_id}")
                    return

                logger.info(f"✅ WEBHOOK - Message édité du canal autorisé: {TARGET_CHANNEL_ID}")

                # TRAITEMENT MESSAGES ÉDITÉS AMÉLIORÉ - Prédiction ET Vérification
                has_completion = self.card_predictor.has_completion_indicators(text)
                has_bozato = '🔰' in text
                has_checkmark = '✅' in text

                logger.info(f"🔍 ÉDITION - Finalisation: {has_completion}, 🔰: {has_bozato}, ✅: {has_checkmark}")
                logger.info(f"🔍 ÉDITION - 🔰 et ✅ sont maintenant traités de manière identique pour la vérification")

                if has_completion:
                    logger.info(f"🎯 ÉDITION FINALISÉE - Traitement prédiction ET vérification")

                    # SYSTÈME 1: PRÉDICTION AUTOMATIQUE (messages édités avec finalisation)
                    should_predict, game_number, combination = self.card_predictor.should_predict(text)

                    if should_predict and game_number is not None and combination is not None:
                        prediction = self.card_predictor.make_prediction(game_number, combination)
                        logger.info(f"🔮 PRÉDICTION depuis ÉDITION: {prediction}")

                        # Envoyer la prédiction et stocker les informations
                        target_channel = self.get_redirect_channel(sender_chat_id)
                        sent_message_info = self.send_message(target_channel, prediction)
                        if sent_message_info and isinstance(sent_message_info, dict) and 'message_id' in sent_message_info:
                            target_game = game_number + 2
                            self.card_predictor.sent_predictions[target_game] = {
                                'chat_id': target_channel,
                                'message_id': sent_message_info['message_id']
                            }
                            logger.info(f"📝 PRÉDICTION STOCKÉE pour jeu {target_game} vers canal {target_channel}")

                    # SYSTÈME 2: VÉRIFICATION UNIFIÉE (messages édités avec finalisation)
                    verification_result = self.card_predictor._verify_prediction_common(text, is_edited=True)
                    if verification_result:
                        logger.info(f"🔍 ✅ VÉRIFICATION depuis ÉDITION: {verification_result}")

                        if verification_result.get('type') == 'edit_message':
                            predicted_game = verification_result.get('predicted_game')
                            new_message = verification_result.get('new_message')

                            # Tenter d'éditer le message de prédiction existant
                            if predicted_game in self.card_predictor.sent_predictions:
                                message_info = self.card_predictor.sent_predictions[predicted_game]
                                edit_success = self.edit_message(
                                    message_info['chat_id'],
                                    message_info['message_id'],
                                    new_message
                                )

                                if edit_success:
                                    logger.info(f"🔍 ✅ MESSAGE ÉDITÉ avec succès - Prédiction {predicted_game}")
                                else:
                                    logger.error(f"🔍 ❌ ÉCHEC ÉDITION - Prédiction {predicted_game}")
                            else:
                                logger.warning(f"🔍 ⚠️ AUCUN MESSAGE STOCKÉ pour {predicted_game}")
                    else:
                        logger.info(f"🔍 ⭕ AUCUNE VÉRIFICATION depuis édition")

                # Gestion des messages temporaires
                elif self.card_predictor.has_pending_indicators(text):
                    logger.info(f"⏰ WEBHOOK - Message temporaire détecté, en attente de finalisation")
                    if message_id:
                        self.card_predictor.pending_edits[message_id] = {
                            'original_text': text,
                            'timestamp': datetime.now()
                        }

        except Exception as e:
            logger.error(f"❌ Error handling edited message via webhook: {e}")

    def _process_card_message(self, message: Dict[str, Any]) -> None:
        """Process message for card prediction (works for both regular and edited messages)"""
        try:
            chat_id = message['chat']['id']
            text = message.get('text', '')
            sender_chat = message.get('sender_chat', {})
            sender_chat_id = sender_chat.get('id', chat_id)

            # Only process messages from Baccarat Kouamé channel
            if sender_chat_id != TARGET_CHANNEL_ID:
                logger.info(f"🚫 Message ignoré - Canal non autorisé: {sender_chat_id}")
                return

            if not text or not self.card_predictor:
                return

            logger.info(f"🎯 Traitement message CANAL AUTORISÉ: {text[:50]}...")

            # Store temporary messages with pending indicators
            if self.card_predictor.has_pending_indicators(text):
                message_id = message.get('message_id')
                if message_id:
                    self.card_predictor.temporary_messages[message_id] = text
                    logger.info(f"⏰ Message temporaire stocké: {message_id}")

            # VÉRIFICATION AMÉLIORÉE - Messages normaux avec 🔰 ou ✅
            has_completion = self.card_predictor.has_completion_indicators(text)

            if has_completion:
                logger.info(f"🔍 MESSAGE NORMAL avec finalisation: {text[:50]}...")
                verification_result = self.card_predictor._verify_prediction_common(text, is_edited=False)
                if verification_result:
                    logger.info(f"🔍 ✅ VÉRIFICATION depuis MESSAGE NORMAL: {verification_result}")

                    if verification_result['type'] == 'edit_message':
                        predicted_game = verification_result['predicted_game']
                        if predicted_game in self.card_predictor.sent_predictions:
                            message_info = self.card_predictor.sent_predictions[predicted_game]
                            edit_success = self.edit_message(
                                message_info['chat_id'],
                                message_info['message_id'],
                                verification_result['new_message']
                            )
                            if edit_success:
                                logger.info(f"✅ MESSAGE ÉDITÉ depuis message normal - Prédiction {predicted_game}")

        except Exception as e:
            logger.error(f"Error processing card message: {e}")

    def _process_verification_on_normal_message(self, message: Dict[str, Any]) -> None:
        """Process verification on normal messages (not just edited ones)"""
        try:
            text = message.get('text', '')
            chat_id = message['chat']['id']
            sender_chat = message.get('sender_chat', {})
            sender_chat_id = sender_chat.get('id', chat_id)

            # Only process messages from Baccarat Kouamé channel
            if sender_chat_id != TARGET_CHANNEL_ID:
                return

            if not text or not self.card_predictor:
                return

            has_completion = self.card_predictor.has_completion_indicators(text)

            if has_completion:
                verification_result = self.card_predictor._verify_prediction_common(text, is_edited=False)
                if verification_result:
                    if verification_result['type'] == 'edit_message':
                        predicted_game = verification_result['predicted_game']

                        if predicted_game in self.card_predictor.sent_predictions:
                            message_info = self.card_predictor.sent_predictions[predicted_game]
                            edit_success = self.edit_message(
                                message_info['chat_id'],
                                message_info['message_id'],
                                verification_result['new_message']
                            )

        except Exception as e:
            logger.error(f"❌ Error processing verification on normal message: {e}")

    def _is_authorized_user(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        # Mode debug : autoriser temporairement plus d'utilisateurs pour tests
        if os.getenv('DEBUG_MODE', 'false').lower() == 'true':
            logger.info(f"🔧 MODE DEBUG - Utilisateur {user_id} autorisé temporairement")
            return True

        # Vérifier l'ID admin depuis les variables d'environnement
        admin_id = int(os.getenv('ADMIN_ID', '1190237801'))
        is_authorized = user_id == admin_id

        if is_authorized:
            logger.info(f"✅ Utilisateur autorisé: {user_id}")
        else:
            logger.warning(f"🚫 Utilisateur non autorisé: {user_id} (Admin attendu: {admin_id})")

        return is_authorized

    def _handle_start_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /start command with authorization check"""
        try:
            logger.info(f"🎯 COMMANDE /start reçue - Chat: {chat_id}, User: {user_id}")

            if user_id and not self._is_authorized_user(user_id):
                admin_id = int(os.getenv('ADMIN_ID', '1190237801'))
