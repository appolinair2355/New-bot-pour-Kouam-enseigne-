"""
Configuration settings for the Telegram bot
"""
import os
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration class for bot settings"""

    def __init__(self):
        # BOT_TOKEN - OBLIGATOIRE depuis variable d'environnement
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        if not self.BOT_TOKEN:
            logger.error("❌ BOT_TOKEN non trouvé dans les variables d'environnement")
            raise ValueError("BOT_TOKEN environment variable is required")

        logger.info(f"✅ BOT_TOKEN configuré: {self.BOT_TOKEN[:10]}...")

        # Validation basique du format du token
        if len(self.BOT_TOKEN.split(':')) != 2:
            logger.error("❌ Format de token invalide")
            raise ValueError("Invalid bot token format")

        # WEBHOOK_URL - OBLIGATOIRE pour Render.com
        self.WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
        if self.WEBHOOK_URL:
            logger.info(f"🔗 Webhook URL configuré: {self.WEBHOOK_URL}")
        else:
            logger.warning("⚠️ WEBHOOK_URL non configurée")

        # Port pour le serveur - utilise PORT env ou 10000 par défaut
        self.PORT = int(os.getenv('PORT', 10000))

        # Canal de destination pour les prédictions
        self.PREDICTION_CHANNEL_ID = -1002875505624
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

        # Validate configuration
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration settings"""
        if not self.BOT_TOKEN:
            raise ValueError("Bot token is required")

        if len(self.BOT_TOKEN.split(':')) != 2:
            raise ValueError("Invalid bot token format")

        if self.WEBHOOK_URL and not self.WEBHOOK_URL.startswith('https://'):
            logger.warning("Webhook URL should use HTTPS for production")

        logger.info("✅ Configuration validée avec succès")

    def get_webhook_url(self) -> str:
        """Get full webhook URL"""
        if self.WEBHOOK_URL:
            return f"{self.WEBHOOK_URL}/webhook"
        return ""

    def __str__(self) -> str:
        """String representation of config (without sensitive data)"""
        return f"Config(webhook_url={self.WEBHOOK_URL}, port={self.PORT}, debug={self.DEBUG})"
