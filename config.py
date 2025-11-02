"""
Configuration settings for the Telegram bot - Render.com ready
"""
import os
import logging

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not self.BOT_TOKEN:
            logger.error("❌ BOT_TOKEN not found in environment variables")
            raise ValueError("BOT_TOKEN environment variable is required")

        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL', f'https://{os.getenv("REPL_SLUG", "")}.{os.getenv("REPL_OWNER", "")}.repl.co')
        self.PORT = int(os.getenv('PORT') or 10000)
        self.PREDICTION_CHANNEL_ID = -1002875505624
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    def get_webhook_url(self) -> str:
        return f"{self.WEBHOOK_URL}/webhook" if self.WEBHOOK_URL else ""

    def __str__(self) -> str:
        return f"Config(webhook_url={self.WEBHOOK_URL}, port={self.PORT}, debug={self.DEBUG})"
      
