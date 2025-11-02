"""
Telegram Bot implementation with advanced features and deployment capabilities
"""
import os
import logging
import requests
import json
from typing import Dict, Any
from handlers import TelegramHandlers
from card_predictor import card_predictor

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.deployment_file_path = "depi_render_n2_fix.zip"
        self.handlers = TelegramHandlers(token)

    def handle_update(self, update: Dict[str, Any]) -> None:
        try:
            if 'message' in update:
                logger.info("🔄 Bot traite message normal via webhook")
            elif 'edited_message' in update:
                logger.info("🔄 Bot traite message édité via webhook")
            self.handlers.handle_update(update)
            logger.info("✅ Update traité avec succès via webhook")
        except Exception as e:
            logger.error(f"❌ Error handling update via webhook: {e}")

    def send_message(self, chat_id: int, text: str) -> bool:
        try:
            url = f"{self.base_url}/sendMessage"
            data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('ok'):
                logger.info(f"Message sent to chat {chat_id}")
                return True
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
                    logger.info(f"Document sent to chat {chat_id}")
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

    def set_webhook(self, webhook_url: str) -> bool:
        try:
            url = f"{self.base_url}/setWebhook"
            data = {'url': webhook_url, 'allowed_updates': ['message', 'edited_message']}
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('ok'):
                logger.info(f"✅ Webhook set: {webhook_url}")
                return True
            else:
                logger.error(f"❌ Failed to set webhook: {result}")
                return False
        except Exception as e:
            logger.error(f"❌ Error setting webhook: {e}")
            return False

    def get_bot_info(self) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=30)
            result = response.json()
            return result.get('result', {}) if result.get('ok') else {}
        except Exception as e:
            logger.error(f"❌ Error getting bot info: {e}")
            return {}
              
