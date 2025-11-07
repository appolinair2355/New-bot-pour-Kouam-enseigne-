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
                admin_id = int(os.getenv('ADMIN_ID', '1190237801'))            if user_id and not self._is_authorized_user(user_id):
                admin_id = int(os.getenv('ADMIN_ID', '1190237801'))
                logger.warning(f"🚫 Tentative d'accès non autorisée: {user_id} vs {admin_id}")
                self.send_message(chat_id, f"🚫 Accès non autorisé. Votre ID: {user_id}")
                return

            logger.info(f"✅ Utilisateur autorisé, envoi du message de bienvenue")
            self.send_message(chat_id, WELCOME_MESSAGE)
        except Exception as e:
            logger.error(f"❌ Error in start command: {e}")
            self.send_message(chat_id, "❌ Une erreur s'est produite. Veuillez réessayer.")

    def _handle_help_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /help command with authorization check"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return
            self.send_message(chat_id, HELP_MESSAGE)
        except Exception as e:
            logger.error(f"Error in help command: {e}")

    def _handle_about_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /about command with authorization check"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return
            self.send_message(chat_id, ABOUT_MESSAGE)
        except Exception as e:
            logger.error(f"Error in about command: {e}")

    def _handle_dev_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /dev command with authorization check"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return
            self.send_message(chat_id, DEV_MESSAGE)
        except Exception as e:
            logger.error(f"Error in dev command: {e}")

    def _handle_deploy_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /deploy command with authorization check"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            self.send_message(
                chat_id, 
                "🚀 Préparation du package DEPI40000 avec règles corrigées (🔰 = ✅)... Veuillez patienter."
            )

            if not os.path.exists(self.deployment_file_path):
                self.send_message(chat_id, "❌ Fichier de déploiement non trouvé.")
                return

            success = self.send_document(chat_id, self.deployment_file_path)

            if success:
                self.send_message(
                    chat_id,
                    f"✅ **PACKAGE DEPI40000 ENVOYÉ !**\n\n"
                    f"📦 **Fichier :** {self.deployment_file_path}\n\n"
                    "📋 **Contenu du package DEPI40000 :**\n"
                    "1. Fichier principal du bot (main.py ou équivalent)\n"
                    "2. Fichier des règles de prédiction (card_predictor.py)\n"
                    "3. Fichier de configuration (config.py ou .env)\n"
                    "4. Dépendances (requirements.txt)\n"
                    "5. Fichier README (README.md)\n\n"
                    "📋 **Instructions de déploiement sur Render.com :**\n"
                    "1. Créez un nouveau service Web Service.\n"
                    "2. Sélectionnez 'Zip Upload' comme source.\n"
                    "3. Uploadez ce fichier zip.\n"
                    "4. Configurez les variables d'environnement : \n"
                    "   - BOT_TOKEN : Votre token Telegram\n"
                    "   - WEBHOOK_URL : L'URL de votre webhook (ex: https://votre-app.onrender.com)\n"
                    "   - PORT : 10000\n\n"
                    "🎯 Votre bot sera déployé avec le package DEPI40000 !\n\n"
                    "🔍 **NOUVELLE FONCTIONNALITÉ :** 🔰 et ✅ sont maintenant traités de manière identique pour la vérification des prédictions."
                )

        except Exception as e:
            logger.error(f"Error handling deploy command: {e}")

    def _handle_ni_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /ni command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            self.send_message(chat_id, "📦 Préparation du package...")

            if not os.path.exists(self.deployment_file_path):
                self.send_message(chat_id, "❌ Package non trouvé.")
                return

            success = self.send_document(chat_id, self.deployment_file_path)

            if success:
                self.send_message(chat_id, "✅ Package DEPI40000 envoyé avec succès !")

        except Exception as e:
            logger.error(f"Error handling ni command: {e}")

    def _handle_pred_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /pred command - sends only the corrected card_predictor.py file"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            self.send_message(chat_id, "🔧 Préparation du fichier card_predictor.py corrigé...")

            # Assuming the corrected file is packaged or directly available for this command
            pred_file_path = "pred_update.zip" # Placeholder or actual path
            if not os.path.exists(pred_file_path):
                # Fallback or specific file not found
                # For this example, we'll assume it's for demonstration purposes
                self.send_message(chat_id, "❌ Fichier de prédiction corrigé non trouvé. (Veuillez utiliser /deploy pour le package complet)")
                return
            
            # --- Code pour envoyer le document (omnis par clarté) ---
            success = self.send_document(chat_id, pred_file_path)

            if success:
                self.send_message(
                    chat_id, 
                    "✅ Fichier card_predictor.py corrigé envoyé avec succès !\n\n"
                    "🔧 Cette correction permet maintenant de reconnaître :\n"
                    "• Messages finalisés avec ✅\n"
                    "• Messages finalisés avec 🔰\n\n"
                    "📝 Remplacez votre fichier card_predictor.py existant par cette version corrigée."
                )

        except Exception as e:
            logger.error(f"Error handling pred command: {e}")

    def _handle_fin_command(self, chat_id: int, user_id: int = None) -> None:
        """Handle /fin command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            self.send_message(chat_id, "📦 Préparation du package final...")

            if not os.path.exists(self.deployment_file_path):
                self.send_message(chat_id, "❌ Package final non trouvé.")
                return

            success = self.send_document(chat_id, self.deployment_file_path)

            if success:
                self.send_message(chat_id, "✅ Package FINAL DEPI40000 envoyé !")

        except Exception as e:
            logger.error(f"Error handling fin command: {e}")

    def _handle_cooldown_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        """Handle /cooldown command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            parts = text.strip().split()
            if len(parts) == 1:
                current_cooldown = self.card_predictor.prediction_cooldown if self.card_predictor else 30
                self.send_message(chat_id, f"⏰ Cooldown actuel: {current_cooldown} secondes")
                return

            if len(parts) != 2:
                self.send_message(chat_id, "❌ Format: /cooldown [secondes]")
                return

            try:
                seconds = int(parts[1])
                if seconds < 30 or seconds > 600:
                    self.send_message(chat_id, "❌ Délai entre 30 et 600 secondes")
                    return
            except ValueError:
                self.send_message(chat_id, "❌ Nombre invalide")
                return

            if self.card_predictor:
                self.card_predictor.prediction_cooldown = seconds
                self.send_message(chat_id, f"✅ Cooldown mis à jour: {seconds}s")

        except Exception as e:
            logger.error(f"Error handling cooldown command: {e}")

    def _handle_announce_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        """Handle /announce command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            parts = text.strip().split(maxsplit=1)
            if len(parts) == 1:
                self.send_message(chat_id, "💡 Usage: /announce [message]")
                return

            announcement_text = parts[1]
            # Utilise get_redirect_channel pour trouver le canal cible actuel
            target_channel = self.get_redirect_channel(TARGET_CHANNEL_ID) 
            formatted_message = f"📢 **ANONCE OFFICIELLE** 📢\n\n{announcement_text}"

            sent_message_info = self.send_message(target_channel, formatted_message)

            if sent_message_info:
                self.send_message(chat_id, f"✅ Annonce envoyée avec succès au canal: {target_channel}")

        except Exception as e:
            logger.error(f"Error handling announce command: {e}")

    def _handle_redirect_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        """Handle /redirect command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            parts = text.strip().split()
            if len(parts) == 1:
                self.send_message(chat_id, "💡 Usage: /redirect [source_id] [target_id]")
                return

            if parts[1] == "clear":
                if self.card_predictor:
                    self.card_predictor.redirect_channels.clear()
                    self.send_message(chat_id, "✅ Redirections supprimées")
                return

            if len(parts) != 3:
                self.send_message(chat_id, "❌ Format: /redirect [source_id] [target_id]")
                return

            try:
                source_id = int(parts[1])
                target_id = int(parts[2])
            except ValueError:
                self.send_message(chat_id, "❌ IDs invalides")
                return

            if self.card_predictor:
                self.card_predictor.set_redirect_channel(source_id, target_id)
                self.send_message(chat_id, f"✅ Redirection: {source_id} → {target_id}")

        except Exception as e:
            logger.error(f"Error handling redirect command: {e}")

    def _handle_cos_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        """Handle /cos command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            parts = text.strip().split()
            if len(parts) != 2:
                self.send_message(chat_id, "❌ Format: /cos [1|2]")
                return

            try:
                position = int(parts[1])
                if position not in [1, 2]:
                    self.send_message(chat_id, "❌ Position 1 ou 2 seulement")
                    return
            except ValueError:
                self.send_message(chat_id, "❌ Position invalide")
                return

            if self.card_predictor:
                self.card_predictor.set_position_preference(position)
                self.send_message(chat_id, f"✅ Position de carte: {position}")

        except Exception as e:
            logger.error(f"Error handling cos command: {e}")

    def _handle_regular_message(self, message: Dict[str, Any]) -> None:
        """Handle regular text messages"""
        try:
            chat_id = message['chat']['id']
            chat_type = message['chat'].get('type', 'private')

            if chat_type == 'private':
                self.send_message(
                    chat_id,
                    "🎭 Salut ! Je suis le bot Joker.\n"
                    "Utilisez /help pour voir mes commandes."
                )

        except Exception as e:
            logger.error(f"Error handling regular message: {e}")

    def _handle_new_chat_members(self, message: Dict[str, Any]) -> None:
        """Handle when bot is added to a channel or group"""
        try:
            chat_id = message['chat']['id']

            for member in message['new_chat_members']:
                if member.get('is_bot', False):
                    self.send_message(chat_id, GREETING_MESSAGE)
                    break

        except Exception as e:
            logger.error(f"Error handling new chat members: {e}")

    def _handle_redi_command(self, chat_id: int, sender_chat_id: int, user_id: int = None) -> None:
        """Handle /redi command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Vous n'êtes pas autorisé à utiliser ce bot.")
                return

            # Utilise le TARGET_CHANNEL_ID comme source par défaut
            if self.card_predictor:
                 self.card_predictor.set_redirect_channel(TARGET_CHANNEL_ID, sender_chat_id)
            
            # Stockage local pour compatibilité
            self.redirected_channels[TARGET_CHANNEL_ID] = sender_chat_id

            self.send_message(chat_id, f"✅ Prédictions redirigées vers ce chat ({sender_chat_id}).")

        except Exception as e:
            logger.error(f"Error handling redi command: {e}")

    def _handle_reset_command(self, sender_chat_id: int, user_id: int = None) -> None:
        """Handle /reset command"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                # Répondre même si non autorisé pour éviter confusion dans un groupe
                self.send_message(sender_chat_id, "🚫 Vous n'êtes pas autorisé à réinitialiser le système.")
                return

            if self.card_predictor:
                self.card_predictor.reset_all_predictions()
                # Réinitialiser également la redirection locale pour la source principale
                if TARGET_CHANNEL_ID in self.redirected_channels:
                    del self.redirected_channels[TARGET_CHANNEL_ID]

                self.send_message(sender_chat_id, "✅ Système complètement réinitialisé.")

        except Exception as e:
            logger.error(f"Error handling reset command: {e}")

    def get_redirect_channel(self, source_chat_id: int) -> int:
        """Get the target channel for redirection"""
        # 1. Vérifie si une redirection est configurée dans le prédicteur
        if self.card_predictor and hasattr(self.card_predictor, 'redirect_channels'):
            redirect_target = self.card_predictor.redirect_channels.get(source_chat_id)
            if redirect_target:
                return redirect_target

        # 2. Vérifie la redirection locale (pour la compatibilité)
        local_redirect = self.redirected_channels.get(source_chat_id)
        if local_redirect:
            return local_redirect

        # 3. Retourne l'ID de canal par défaut (corrigé)
        return PREDICTION_CHANNEL_ID 

    def send_message(self, chat_id: int, text: str) -> Dict[str, Any] | bool: 
        """Send text message to user using direct API call"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown' # Utilisation de Markdown pour les messages, car WELCOME_MESSAGE utilise **
            }

            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                logger.info(f"Message sent successfully to chat {chat_id}")
                return result.get('result', {}) # Return result for message_id extraction
            else:
                # Ajout de logs pour l'erreur de canal cible
                if result.get('error_code') == 400 and 'chat not found' in result.get('description', '').lower():
                    logger.error(f"❌ Échec d'envoi: Le canal/chat ID {chat_id} est introuvable ou le bot n'y est pas/n'a pas les droits.")
                
                logger.error(f"Failed to send message: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_document(self, chat_id: int, file_path: str) -> bool:
        """Send document file to user"""
        try:
            url = f"{self.base_url}/sendDocument"

            with open(file_path, 'rb') as file:
                files = {
                    'document': (os.path.basename(file_path), file, 'application/zip')
                }
                data = {
                    'chat_id': chat_id,
                    'caption': '📦 Package de déploiement pour render.com'
                }

                response = requests.post(url, data=data, files=files, timeout=60)
                result = response.json()

                if result.get('ok'):
                    logger.info(f"Document sent successfully to chat {chat_id}")
                    return True
                else:
                    logger.error(f"Failed to send document: {result}")
                    return False

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Error sending document: {e}")
            return False

    def edit_message(self, chat_id: int, message_id: int, new_text: str) -> bool:
        """Edit an existing message using direct API call"""
        try:
            url = f"{self.base_url}/editMessageText"
            data = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': new_text,
                'parse_mode': 'Markdown' # Changé en Markdown pour la cohérence
            }

            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                logger.info(f"Message edited successfully in chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to edit message: {result}")
                return False

        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return False

