import os
import logging
import google.generativeai as genai
from flask import Flask, request, jsonify
import telegram

# --- CONFIGURATION ---
# It's highly recommended to use environment variables for your API keys.
# On Render, you can set these in the 'Environment' section of your service.
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY')
WEBHOOK_SECRET_TOKEN = os.environ.get('WEBHOOK_SECRET_TOKEN', 'a-very-secret-string') # A secret token to verify requests

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- INITIALIZATION ---
app = Flask(__name__)

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    logger.info("Gemini AI model initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Gemini AI: {e}")
    model = None

# Configure Telegram Bot
try:
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Telegram Bot initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Telegram Bot: {e}")
    bot = None

# --- WEBHOOK HANDLER ---
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Handles incoming updates from Telegram."""
    # Verify the secret token
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret_token != WEBHOOK_SECRET_TOKEN:
        logger.warning("Invalid secret token received.")
        return 'Forbidden', 403

    if not bot or not model:
        logger.error("Bot or Gemini model not initialized. Cannot process request.")
        return jsonify(status="error", message="Internal server error"), 500

    try:
        update_data = request.get_json()
        update = telegram.Update.de_json(update_data, bot)
        
        if update.message and update.message.text:
            chat_id = update.message.chat_id
            user_message = update.message.text

            # Ignore commands for the Gemini model
            if user_message.startswith('/'):
                handle_command(chat_id, user_message)
                return jsonify(status="ok")

            logger.info(f"Received message from chat_id {chat_id}: {user_message}")

            # Send "typing..." action to the user
            bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)

            # --- Call Gemini API ---
            try:
                response = model.generate_content(user_message)
                bot_reply = response.text
            except Exception as e:
                logger.error(f"Error generating content from Gemini: {e}")
                bot_reply = "Sorry, I encountered an error while processing your request. Please try again later."
            
            # Send the response back to the user
            bot.send_message(chat_id=chat_id, text=bot_reply)
            logger.info(f"Sent reply to chat_id {chat_id}: {bot_reply[:80]}...")

    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        # Return a 200 OK to Telegram even if an error occurs,
        # to prevent it from resending the update repeatedly.
    
    return jsonify(status="ok")

def handle_command(chat_id, command):
    """Handles specific commands like /start."""
    if command.startswith('/start'):
        welcome_message = (
            "Hello! I'm a chatbot powered by Google's Gemini AI. 🚀\n\n"
            "Just send me a message, and I'll do my best to respond. "
            "You can ask me questions, ask for summaries, or just have a chat!"
        )
        bot.send_message(chat_id=chat_id, text=welcome_message)
        logger.info(f"Sent /start command response to chat_id {chat_id}")
    else:
        unknown_command_message = "Sorry, I don't recognize that command."
        bot.send_message(chat_id=chat_id, text=unknown_command_message)

# --- HEALTH CHECK ENDPOINT ---
@app.route('/')
def index():
    """A simple health check endpoint to verify the server is running."""
    return "Hello! The Gemini Telegram Bot server is running."

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # This part is for local testing. 
    # When deploying to a service like Render, it will use a Gunicorn server.
    app.run(debug=True, port=int(os.environ.get('PORT', 8080)))


