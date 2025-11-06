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
PREDICTION_CHANNEL_ID = -1002875505624 # NOUVEAU CANAL CIBLE : -1002875505624

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
• `/reset` - Réinitialisation du système
"""

HELP_MESSAGE = """
... (contenu inchangé) ...
"""

ABOUT_MESSAGE = """
... (contenu inchangé) ...
"""

DEV_MESSAGE = """
... (contenu inchangé) ...
"""

MAX_MESSAGES_PER_MINUTE = 30
RATE_LIMIT_WINDOW = 60

def is_rate_limited(user_id: int) -> bool:
    """Check if user is rate limited"""
    now = datetime.now()
    # Clean up old timestamps
    user_message_counts[user_id] = [
        t for t in user_message_counts[user_id] 
        if t > now - timedelta(seconds=RATE_LIMIT_WINDOW)
    ]
    
    if len(user_message_counts[user_id]) >= MAX_MESSAGES_PER_MINUTE:
        logger.warning(f"RATE LIMIT: User {user_id} exceeded limit.")
        return True
    
    user_message_counts[user_id].append(now)
    return False

class TelegramHandlers:
    """Handlers for Telegram bot using webhook approach"""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}" 
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
        """Handle incoming Telegram updates"""
        if 'message' in update:
            self._handle_message(update['message'])
        elif 'edited_message' in update:
            self._handle_edited_message(update['edited_message'])

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Process standard message updates"""
        chat = message.get('chat', {})
        chat_id = chat.get('id')
        text = message.get('text', '')
        message_id = message.get('message_id')
        user_id = message.get('from', {}).get('id')
        sender_chat_id = message.get('sender_chat', {}).get('id')
        
        if not chat_id:
            logger.warning("Message without chat_id received.")
            return
        
        # Log message for debugging
        logger.info(f"Received message from chat {chat_id}: {text[:50]}...")

        # Handle system message (e.g., new members)
        if 'new_chat_members' in message:
            self._handle_new_chat_members(message)
            return
        
        if is_rate_limited(user_id):
            return

        if text.startswith('/'):
            # Handle commands
            command = text.split()[0].lower()
            if command == '/start':
                self._handle_start_command(chat_id, user_id)
            elif command == '/help':
                self._handle_help_command(chat_id, user_id)
            elif command == '/about':
                self._handle_about_command(chat_id, user_id)
            elif command == '/dev':
                self._handle_dev_command(chat_id, user_id)
            elif command == '/deploy':
                self._handle_deploy_command(chat_id, user_id)
            elif command == '/ni':
                self._handle_ni_command(chat_id, user_id)
            elif command == '/pred':
                self._handle_pred_command(chat_id, user_id)
            elif command == '/fin':
                self._handle_fin_command(chat_id, user_id)
            elif command == '/cooldown':
                self._handle_cooldown_command(chat_id, text, user_id)
            elif command == '/announce':
                self._handle_announce_command(chat_id, text, user_id)
            elif command == '/redirect':
                self._handle_redirect_command(chat_id, text, user_id)
            elif command == '/cos':
                self._handle_cos_command(chat_id, text, user_id)
            elif command == '/redi':
                 self._handle_redi_command(chat_id, sender_chat_id, user_id)
            elif command == '/reset':
                 self._handle_reset_command(sender_chat_id, user_id)
        else:
            # Handle regular message logic
            self._handle_regular_message(message)

    def _handle_edited_message(self, message: Dict[str, Any]) -> None:
        """Process edited message updates (for verification)"""
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        if chat_id == TARGET_CHANNEL_ID and self.card_predictor:
            logger.info(f"Received EDIT from TARGET_CHANNEL {chat_id}: {text[:50]}...")
            
            # 1. Process verification based on the edited message
            verification_result = self.card_predictor.verify_prediction_from_edit(text)
            
            if verification_result and verification_result.get('type') == 'edit_message':
                self._process_verification_result(verification_result, source_chat_id=TARGET_CHANNEL_ID)
                
            # 2. Check if the edited message is now final and can trigger a prediction
            # This is less likely with the new 10-card rule but kept for robustness
            self._process_card_message(text, source_chat_id=TARGET_CHANNEL_ID)

    def _process_card_message(self, text: str, source_chat_id: int) -> None:
        """Process messages that might contain card info for prediction"""
        if self.card_predictor:
            should_predict, game_number, predicted_costume = self.card_predictor.should_predict(text)
            
            if should_predict and game_number is not None and predicted_costume is not None:
                prediction_text = self.card_predictor.make_prediction(game_number, predicted_costume)
                
                # Get redirection channel (default is now -1002875505624)
                target_chat_id = self.get_redirect_channel(source_chat_id)
                
                # Send prediction
                response = self.send_message(target_chat_id, prediction_text)
                if response and response.get('ok'):
                    message_id = response.get('result', {}).get('message_id')
                    predicted_game = game_number + 2
                    if message_id:
                        # Store sent message ID for potential future edits (verification updates)
                        self.card_predictor.sent_predictions[predicted_game] = {
                            'message_id': message_id,
                            'chat_id': target_chat_id,
                            'predicted_costume': predicted_costume # Store costume for verification in handlers.py if needed
                        }
                        logger.info(f"Prediction for game {predicted_game} sent to {target_chat_id} with ID {message_id}")

    def _process_verification_on_normal_message(self, text: str, source_chat_id: int) -> None:
        """Process messages that might verify a previous prediction"""
        if self.card_predictor:
            verification_result = self.card_predictor.verify_prediction(text)
            
            if verification_result and verification_result.get('type') == 'edit_message':
                self._process_verification_result(verification_result, source_chat_id)

    def _process_verification_result(self, result: Dict, source_chat_id: int) -> None:
        """Handles the outcome of a prediction verification"""
        predicted_game = result.get('predicted_game')
        new_message = result.get('new_message')
        
        sent_info = self.card_predictor.sent_predictions.get(predicted_game)
        
        if sent_info:
            target_chat_id = sent_info['chat_id']
            message_id = sent_info['message_id']
            
            logger.info(f"Attempting to EDIT message {message_id} in chat {target_chat_id} with new status: {new_message}")
            self.edit_message(target_chat_id, message_id, new_message)

    def _is_authorized_user(self, user_id: int) -> bool:
        """Check if user is authorized to use commands"""
        # Placeholder for authorization logic
        # For now, allow all users.
        return True

    def _handle_start_command(self, chat_id: int, user_id: int = None) -> None:
        self.send_message(chat_id, GREETING_MESSAGE)

    def _handle_help_command(self, chat_id: int, user_id: int = None) -> None:
        self.send_message(chat_id, HELP_MESSAGE)

    def _handle_about_command(self, chat_id: int, user_id: int = None) -> None:
        self.send_message(chat_id, ABOUT_MESSAGE)

    def _handle_dev_command(self, chat_id: int, user_id: int = None) -> None:
        self.send_message(chat_id, DEV_MESSAGE)

    def _handle_deploy_command(self, chat_id: int, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        self.send_document(chat_id, self.deployment_file_path)

    def _handle_ni_command(self, chat_id: int, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        self.send_message(chat_id, f"🎯 Position préférée: {self.card_predictor.position_preference}")

    def _handle_pred_command(self, chat_id: int, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        predictions_status = "\n".join([
            f"🔵{game}🔵: {data['predicted_costume']} (statut: {data['status']})"
            for game, data in self.card_predictor.predictions.items()
        ])
        if not predictions_status:
            predictions_status = "Aucune prédiction en cours."
        self.send_message(chat_id, f"🔮 **Statut des Prédictions :**\n{predictions_status}")

    def _handle_fin_command(self, chat_id: int, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        self.send_message(chat_id, f"⏰ Cooldown actuel: {self.card_predictor.prediction_cooldown} secondes.")

    def _handle_cooldown_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        try:
            _, value_str = text.split()
            new_cooldown = int(value_str)
            if new_cooldown >= 10:
                self.card_predictor.prediction_cooldown = new_cooldown
                self.send_message(chat_id, f"✅ Délai de prédiction mis à jour à {new_cooldown} secondes.")
            else:
                self.send_message(chat_id, "❌ Le délai doit être d'au moins 10 secondes.")
        except ValueError:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /cooldown [secondes] (ex: /cooldown 300)")
        except Exception:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /cooldown [secondes]")

    def _handle_announce_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        try:
            message_to_send = text.split(maxsplit=1)[1]
            if not message_to_send.strip():
                self.send_message(chat_id, "❌ Le message ne peut être vide.")
                return

            self.send_message(PREDICTION_CHANNEL_ID, f"📢 ANNONCE OFFICIELLE :\n\n{message_to_send}")
            self.send_message(chat_id, "✅ Annonce envoyée au canal de prédiction.")
        except IndexError:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /announce [message]")

    def _handle_redirect_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        try:
            _, target_chat_id_str = text.split()
            target_chat_id = int(target_chat_id_str)
            if target_chat_id < -1000000000000 or target_chat_id > -1000000000:
                self.send_message(chat_id, "❌ ID de canal invalide. Doit être un ID de canal (commence par -100).")
                return

            self.card_predictor.set_redirect_channel(TARGET_CHANNEL_ID, target_chat_id)
            self.redirected_channels[TARGET_CHANNEL_ID] = target_chat_id
            self.send_message(chat_id, f"✅ Redirection des prédictions de {TARGET_CHANNEL_ID} vers {target_chat_id} configurée.")
        except ValueError:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /redirect [-ID_du_canal] (ex: /redirect -1001234567890)")
        except Exception:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /redirect [-ID_du_canal]")

    def _handle_cos_command(self, chat_id: int, text: str, user_id: int = None) -> None:
        if not self._is_authorized_user(user_id): return
        try:
            _, position_str = text.split()
            position = int(position_str)
            if position in [1, 2]:
                self.card_predictor.set_position_preference(position)
                self.send_message(chat_id, f"✅ Position de carte préférée mise à jour à {position}.")
            else:
                self.send_message(chat_id, "❌ Position invalide. Utilisez 1 ou 2.")
        except ValueError:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /cos [1|2]")
        except Exception:
            self.send_message(chat_id, "❌ Format invalide. Utilisation: /cos [1|2]")

    def _handle_regular_message(self, message: Dict[str, Any]) -> None:
        """Handle non-command messages, focusing on card messages from the target channel"""
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')

        # Process messages from the target channel
        if chat_id == TARGET_CHANNEL_ID:
            # 1. Prediction attempt (using 10 rules)
            self._process_card_message(text, source_chat_id=TARGET_CHANNEL_ID)
            
            # 2. Verification attempt (checking old predictions)
            self._process_verification_on_normal_message(text, source_chat_id=TARGET_CHANNEL_ID)

    def _handle_new_chat_members(self, message: Dict[str, Any]) -> None:
        """Send welcome message to new users"""
        chat_id = message.get('chat', {}).get('id')
        for member in message.get('new_chat_members', []):
            if member.get('is_bot') and member.get('username') == 'JokerDeploy99999_bot': # Replace with your bot's username
                self.send_message(chat_id, WELCOME_MESSAGE)
                break

    def _handle_redi_command(self, chat_id: int, sender_chat_id: int, user_id: int = None) -> None:
        """Shortcut to set redirection to the current channel's ID (useful in channels)"""
        if not self._is_authorized_user(user_id): return
        
        # Check if the command was sent from a channel (sender_chat_id is present)
        target_id = sender_chat_id if sender_chat_id else chat_id
        
        if target_id == chat_id and target_id > 0:
             self.send_message(chat_id, "❌ Cette commande doit être utilisée dans un canal ou en réponse à un message de canal pour définir la redirection.")
             return
             
        if target_id < -1000000000000 or target_id > -1000000000:
            self.send_message(chat_id, "❌ ID de canal invalide détecté. Doit être un ID de canal (commence par -100).")
            return
            
        self.card_predictor.set_redirect_channel(TARGET_CHANNEL_ID, target_id)
        self.redirected_channels[TARGET_CHANNEL_ID] = target_id
        self.send_message(chat_id, f"✅ Redirection des prédictions de {TARGET_CHANNEL_ID} vers le canal actuel ({target_id}) configurée.")

    def _handle_reset_command(self, sender_chat_id: int, user_id: int = None) -> None:
        """Reset all predictions and internal states"""
        if not self._is_authorized_user(user_id): return
        
        self.card_predictor.reset_all_predictions()
        self.redirected_channels.clear()
        
        # Send confirmation to the chat where the command was received (sender_chat_id is likely the channel)
        # Using TARGET_CHANNEL_ID if sender_chat_id is not reliable in all contexts
        target_chat = sender_chat_id if sender_chat_id else TARGET_CHANNEL_ID
        
        # Fallback in case target_chat is not valid, though it should be if called via Telegram
        if target_chat:
            self.send_message(target_chat, "🔄 Le système de prédictions, le cooldown et les redirections ont été **complètement réinitialisés**.")


    def get_redirect_channel(self, source_chat_id: int) -> int:
        """Get the target channel for redirection"""
        # 1. Check predictor instance (persistent config)
        if self.card_predictor and hasattr(self.card_predictor, 'redirect_channels'):
            redirect_target = self.card_predictor.redirect_channels.get(source_chat_id)
            if redirect_target:
                return redirect_target

        # 2. Check local handler storage (less persistent)
        local_redirect = self.redirected_channels.get(source_chat_id)
        if local_redirect:
            return local_redirect

        # 3. Default channel
        return PREDICTION_CHANNEL_ID # Utilise le nouveau canal par défaut

    def send_message(self, chat_id: int, text: str) -> Dict[str, Any] | bool:
        """Send a message using direct API call"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                logger.info(f"Message sent successfully to chat {chat_id}")
                return result
            else:
                logger.error(f"Failed to send message: {result}")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_document(self, chat_id: int, file_path: str) -> bool:
        """Send a document using direct API call (e.g., deployment package)"""
        try:
            url = f"{self.base_url}/sendDocument"
            
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {
                    'chat_id': chat_id,
                    'caption': "Voici le package de déploiement (depi_render_n2_fix.zip).",
                    'parse_mode': 'HTML'
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
                'parse_mode': 'HTML'
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
