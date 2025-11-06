"""
Event handlers for the Telegram bot - webhook deployment
"""
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ✅ Canal corrigé
TARGET_CHANNEL_ID = -1002682552255
PREDICTION_CHANNEL_ID = -1002875505624

class TelegramHandlers:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        try:
            from card_predictor import card_predictor
            self.card_predictor = card_predictor
        except ImportError:
            logger.error("card_predictor not available")
            self.card_predictor = None
        self.redirected_channels = {}

    def handle_update(self, update: Dict[str, Any]) -> None:
        try:
            if 'message' in update:
                self._handle_message(update['message'])
            elif 'edited_message' in update:
                self._handle_edited_message(update['edited_message'])
            elif 'channel_post' in update:
                self._handle_message(update['channel_post'])
            elif 'edited_channel_post' in update:
                self._handle_edited_message(update['edited_channel_post'])
        except Exception as e:
            logger.error(f"Error handling update: {e}")

    def _handle_message(self, message: Dict[str, Any]) -> None:
        try:
            chat_id = message['chat']['id']
            user_id = message.get('from', {}).get('id')
            text = message.get('text', '').strip()

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
            elif text.startswith('/att'):
                self._handle_att_command(chat_id, text, user_id)
            elif text.startswith('/cos'):
                self._handle_cos_command(chat_id, text, user_id)
            elif text == '/reset':
                self._handle_reset_command(chat_id, user_id)
            elif text.startswith('/cooldown'):
                self._handle_cooldown_command(chat_id, text, user_id)
            elif text.startswith('/redirect'):
                self._handle_redirect_command(chat_id, text, user_id)
            elif text.startswith('/announce'):
                self._handle_announce_command(chat_id, text, user_id)
            else:
                if self.card_predictor:
                    self._process_card_message(message)
        except Exception as e:
            logger.error(f"Error in _handle_message: {e}")

    def _handle_edited_message(self, message: Dict[str, Any]) -> None:
        if not self.card_predictor:
            return
        
        text = message.get('text', '')
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"✏️ MESSAGE ÉDITÉ DÉTECTÉ")
        logger.info(f"📝 Texte: {text[:150]}...")
        
        if self.card_predictor.has_completion_indicators(text):
            logger.info("✅ Indicateur de complétion présent (✅/🔰)")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            result = self.card_predictor._verify_prediction_common(text, is_edited=True)
            
            if result and result['type'] == 'edit_message':
                msg_info = self.card_predictor.sent_predictions.get(result['predicted_game'])
                if msg_info:
                    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    logger.info(f"🔄 MISE À JOUR MESSAGE PRÉDICTION")
                    logger.info(f"🔹 Partie: #{result['predicted_game']}")
                    logger.info(f"🔹 Canal: {msg_info['chat_id']}")
                    logger.info(f"🔹 Message ID: {msg_info['message_id']}")
                    logger.info(f"🔹 Ancien: {result['original_message']}")
                    logger.info(f"🔹 Nouveau: {result['new_message']}")
                    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    
                    success = self.edit_message(msg_info['chat_id'], msg_info['message_id'], result['new_message'])
                    
                    if success:
                        logger.info(f"✅✅✅ MESSAGE MIS À JOUR AVEC SUCCÈS! ✅✅✅")
                    else:
                        logger.error(f"❌❌❌ ÉCHEC MISE À JOUR MESSAGE ❌❌❌")
                    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                else:
                    logger.warning(f"⚠️ Info message introuvable pour partie #{result['predicted_game']}")
        else:
            logger.debug(f"⏭️ Pas d'indicateur de complétion dans le message édité")

    def _process_card_message(self, message: Dict[str, Any]) -> None:
        text = message.get('text', '')
        sender_chat = message.get('sender_chat', {})
        sender_chat_id = sender_chat.get('id', message['chat']['id'])
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"📨 NOUVEAU MESSAGE REÇU")
        logger.info(f"🔹 Canal source: {sender_chat_id}")
        logger.info(f"🔹 Texte: {text[:100]}...")
        
        if sender_chat_id != TARGET_CHANNEL_ID:
            logger.debug(f"⏭️ Canal ignoré (attendu: {TARGET_CHANNEL_ID})")
            return
        
        logger.info(f"✅ CANAL SOURCE VALIDÉ: {TARGET_CHANNEL_ID}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        should_predict, game_number, costume = self.card_predictor.should_predict(text)
        
        if should_predict and game_number is not None and costume is not None:
            prediction = self.card_predictor.make_prediction(game_number, costume)
            target_channel = self.get_redirect_channel(sender_chat_id)
            
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info(f"🚀 ENVOI PRÉDICTION AUTOMATIQUE")
            logger.info(f"🔹 Partie source: #{game_number}")
            logger.info(f"🔹 Costume détecté: {costume}")
            logger.info(f"🔹 Partie cible: #{game_number + 2}")
            logger.info(f"🔹 Canal destination: {target_channel}")
            logger.info(f"🔹 Message: {prediction}")
            logger.info(f"🔹 Envoi en cours vers Telegram API...")
            logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            msg_result = self.send_message(target_channel, prediction)
            
            logger.info(f"📡 RÉSULTAT ENVOI API:")
            logger.info(f"🔹 Type de réponse: {type(msg_result)}")
            logger.info(f"🔹 Contenu: {msg_result}")
            
            if msg_result and isinstance(msg_result, dict) and 'message_id' in msg_result:
                target_game = game_number + 2
                self.card_predictor.sent_predictions[target_game] = {
                    'chat_id': target_channel,
                    'message_id': msg_result['message_id']
                }
                logger.info(f"✅✅✅ PRÉDICTION ENVOYÉE AVEC SUCCÈS! ✅✅✅")
                logger.info(f"🔹 Message ID: {msg_result['message_id']}")
                logger.info(f"🔹 Stockée pour partie #{target_game}")
                logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            else:
                logger.error(f"❌❌❌ ÉCHEC ENVOI PRÉDICTION ❌❌❌")
                logger.error(f"🔹 Canal: {target_channel}")
                logger.error(f"🔹 Résultat: {msg_result}")
                logger.error(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        else:
            logger.debug(f"⏭️ Pas de prédiction pour ce message")

    def _handle_start_command(self, chat_id: int, user_id: int | None = None) -> None:
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, f"🚫 Accès non autorisé. ID: {user_id}")
                return
            self.send_message(chat_id, "🎭 Bienvenue ! Bot prêt pour les prédictions.")
        except Exception as e:
            logger.error(f"Error in start command: {e}")

    def _handle_help_command(self, chat_id: int, user_id: int | None = None) -> None:
        if user_id and not self._is_authorized_user(user_id):
            self.send_message(chat_id, "🚫 Accès non autorisé.")
            return
        self.send_message(chat_id, "🎯 Commandes: /start /help /att /cos /cooldown /reset /deploy")

    def _handle_about_command(self, chat_id: int, user_id: int | None = None) -> None:
        if user_id and not self._is_authorized_user(user_id):
            self.send_message(chat_id, "🚫 Accès non autorisé.")
            return
        self.send_message(chat_id, "🤖 Bot de prédiction de cartes - Version 2025")

    def _handle_dev_command(self, chat_id: int, user_id: int | None = None) -> None:
        if user_id and not self._is_authorized_user(user_id):
            self.send_message(chat_id, "🚫 Accès non autorisé.")
            return
        self.send_message(chat_id, "👨‍💻 Développé avec Python + Flask + Telegram API")

    def _handle_deploy_command(self, chat_id: int, user_id: int | None = None) -> None:
        if user_id and not self._is_authorized_user(user_id):
            self.send_message(chat_id, "🚫 Accès non autorisé.")
            return
        
        self.send_message(chat_id, "📦 Création du package DEP20000 pour Render.com (Port 10000)...")
        
        import zipfile
        import os
        
        zip_filename = "dep20000.zip"
        files_to_include = [
            'main.py', 'bot.py', 'handlers.py', 'card_predictor.py', 
            'config.py', 'requirements.txt', 'render.yaml'
        ]
        
        try:
            # Vérifier que render.yaml utilise le port 10000
            render_ok = False
            if os.path.exists('render.yaml'):
                with open('render.yaml', 'r') as f:
                    render_content = f.read()
                    if '10000' in render_content:
                        render_ok = True
                        logger.info("✅ render.yaml configuré pour le port 10000")
                    else:
                        logger.warning("⚠️ render.yaml ne contient pas le port 10000!")
            
            # Créer le package ZIP
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                files_added = 0
                for file in files_to_include:
                    if os.path.exists(file):
                        zipf.write(file)
                        files_added += 1
                        logger.info(f"✅ Ajouté au package: {file}")
                    else:
                        logger.warning(f"⚠️ Fichier manquant: {file}")
            
            file_size = os.path.getsize(zip_filename) / 1024
            
            status_msg = f"📦 Package DEP20000 créé!\n"
            status_msg += f"📊 {files_added}/{len(files_to_include)} fichiers inclus\n"
            status_msg += f"💾 Taille: {file_size:.1f} KB\n"
            if render_ok:
                status_msg += "✅ Port 10000 configuré\n"
            status_msg += "\n📤 Envoi en cours..."
            
            self.send_message(chat_id, status_msg)
            success = self.send_document(chat_id, zip_filename)
            
            if success:
                self.send_message(chat_id, 
                    "✅ Package DEP20000 envoyé avec succès!\n\n"
                    "📋 Instructions de déploiement Render.com:\n\n"
                    "1️⃣ Extraire dep20000.zip\n"
                    "2️⃣ Créer un nouveau Web Service sur Render.com\n"
                    "3️⃣ Connecter votre dépôt Git ou uploader les fichiers\n"
                    "4️⃣ Configurer les variables d'environnement:\n"
                    "   • BOT_TOKEN = votre token bot\n"
                    "   • WEBHOOK_URL = votre URL Render\n"
                    "   • ADMIN_ID = 1190237801\n"
                    "5️⃣ Le port 10000 est déjà configuré dans render.yaml\n"
                    "6️⃣ Déployer!\n\n"
                    "🎯 Package à jour avec toutes les dernières modifications"
                )
                logger.info(f"✅ Package DEP20000 envoyé à {chat_id}")
            else:
                self.send_message(chat_id, "❌ Erreur lors de l'envoi du package")
            
            # Nettoyer le fichier ZIP après envoi
            try:
                if os.path.exists(zip_filename):
                    os.remove(zip_filename)
                    logger.info(f"🗑️ Fichier {zip_filename} nettoyé")
            except Exception as e:
                logger.warning(f"Impossible de supprimer {zip_filename}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Erreur création package: {e}")
            self.send_message(chat_id, f"❌ Erreur lors de la création du package: {str(e)}")

    def _handle_att_command(self, chat_id: int, text: str, user_id: int | None = None) -> None:
        """Handle /att command to set prediction cooldown"""
        try:
            if user_id and not self._is_authorized_user(user_id):
                self.send_message(chat_id, "🚫 Accès non autorisé.")
                return

            parts = text.strip().split()
            if len(parts) != 2:
                self.send_message(chat_id, "❌ Usage: /att [0-20]")
                return

            minutes = int(parts[1])
            if not 0 <= minutes <= 20:
                self.send_message(chat_id, "❌ Minutes entre 0 et 20")
                return

            if self.card_predictor:
                self.card_predictor.prediction_cooldown = minutes * 60
                self.send_message(chat_id, f"⏰ Délai entre prédictions réglé à {minutes} minutes.")

        except ValueError:
            self.send_message(chat_id, "❌ Nombre invalide.")
        except Exception as e:
            logger.error(f"Erreur /att : {e}")

    def _handle_cos_command(self, chat_id: int, text: str, user_id: int | None = None) -> None:
        self.send_message(chat_id, "🔧 Commande /cos - non implémentée ici")

    def _handle_reset_command(self, chat_id: int, user_id: int | None = None) -> None:
        if user_id and not self._is_authorized_user(user_id):
            return
        if self.card_predictor:
            self.card_predictor.reset_all_predictions()
            self.send_message(chat_id, "✅ Prédictions réinitialisées.")

    def _handle_cooldown_command(self, chat_id: int, text: str, user_id: int | None = None) -> None:
        self.send_message(chat_id, "🔧 Commande /cooldown - utilisez /att [0-20]")

    def _handle_redirect_command(self, chat_id: int, text: str, user_id: int | None = None) -> None:
        self.send_message(chat_id, "🔧 Commande /redirect - non implémentée ici")

    def _handle_announce_command(self, chat_id: int, text: str, user_id: int | None = None) -> None:
        self.send_message(chat_id, "🔧 Commande /announce - non implémentée ici")

    def _is_authorized_user(self, user_id: int) -> bool:
        admin_id = int(os.getenv('ADMIN_ID', '1190237801'))
        return user_id == admin_id

    def get_redirect_channel(self, source_chat_id: int) -> int:
        if self.card_predictor and hasattr(self.card_predictor, 'redirect_channels'):
            redirect_target = self.card_predictor.redirect_channels.get(source_chat_id)
            if redirect_target:
                return redirect_target
        local_redirect = self.redirected_channels.get(source_chat_id)
        if local_redirect:
            return local_redirect
        return PREDICTION_CHANNEL_ID

    def send_message(self, chat_id: int, text: str) -> Dict[str, Any] | bool:
        try:
            url = f"{self.base_url}/sendMessage"
            data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('ok'):
                return result.get('result', {})
            else:
                logger.error(f"Failed to send message: {result}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_document(self, chat_id: int, file_path: str) -> bool:
        try:
            url = f"{self.base_url}/sendDocument"
            with open(file_path, 'rb') as file:
                files = {'document': (os.path.basename(file_path), file, 'application/zip')}
                data = {'chat_id': chat_id, 'caption': '📦 Deployment Package for render.com'}
                response = requests.post(url, data=data, files=files, timeout=60)
                result = response.json()
                if result.get('ok'):
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
        try:
            url = f"{self.base_url}/editMessageText"
            data = {'chat_id': chat_id, 'message_id': message_id, 'text': new_text, 'parse_mode': 'HTML'}
            response = requests.post(url, json=data, timeout=10)
            return response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return False

            
