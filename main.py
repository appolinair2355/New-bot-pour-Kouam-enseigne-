"""
Main entry point for the Telegram bot deployment on render.com
"""
import os
import logging
from flask import Flask, request
from bot import TelegramBot
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
config = Config()
bot_token = config.BOT_TOKEN
if not bot_token:
    raise ValueError("❌ BOT_TOKEN is required")
bot = TelegramBot(bot_token)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        update = request.get_json()
        if update:
            bot.handle_update(update)
        return 'OK', 200
    except Exception as e:
        logger.error(f"❌ Error handling webhook: {e}")
        return 'Error', 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for render.com"""
    return {'status': 'healthy', 'service': 'telegram-bot'}, 200

@app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return {'message': 'Telegram Bot is running', 'status': 'active'}, 200

def setup_webhook():
    """Set webhook on startup"""
    try:
        webhook_url = config.get_webhook_url()
        if webhook_url:
            success = bot.set_webhook(webhook_url)
            if success:
                logger.info(f"✅ Webhook set: {webhook_url}")
            else:
                logger.error("❌ Failed to set webhook")
        else:
            logger.warning("⚠️ WEBHOOK_URL not set")
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")

if __name__ == '__main__':
    setup_webhook()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
  
