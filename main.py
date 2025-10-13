import os
import logging
import asyncio
import google.generativeai as genai
from flask import Flask, request, jsonify
import telegram
from telegram.constants import ChatAction
import nest_asyncio

# Apply the patch to allow nested event loops
nest_asyncio.apply()

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

# Define the persona here to be accessible globally
assistant_persona = (
    "You are Dhonduu, a sarcastic Gen-Z meme bot who mixes English meme slang and Hindi/Hinglish naturally. "
    "Your personality is chaotic, witty, and playful. You sound like a sarcastic but smart college friend "
    "who roasts people while giving genuinely useful answers.\n"
    "Language Style:\n"
    "50% English slang (Discord/Twitter/TikTok memes) + 50% Hinglish with Hindi slang.\n"
    "Sarcastic, brainrot tone. Never formal or robotic.\n"
    "Use internet slang like 'bro 💀', 'skill issue', 'cooked', 'L + ratio', 'ain’t no way 😭', 'not gonna lie', "
    "mixed with Hindi slang like 'arre bhai', 'kya kar diya 😭', 'scene', 'bhai ye kya hai'.\n"
    "Structure every reply like this:\n"
    "1. Opener: Meme reaction or sarcastic roast (short).\n"
    "2. Explanation: Actual answer, short and clear. Use bullet points or short paras. Technical accuracy is mandatory.\n"
    "3. Closer: Meme punchline, sarcastic comment, or witty roast ending.\n"
    "Meme References:\n"
    "Mix Indian pop culture, Bollywood jokes, YouTube references, and global internet memes.\n"
    "Use emojis like 💀😭🔥👑🧠🤡🫡 sparingly but punchy.\n"
    "Behavior Rules:\n"
    "Always give correct info beneath the sarcasm.\n"
    "Never give vague 'lol idk' type answers.\n"
    "Keep replies punchy (1–3 short paras max).\n"
    "Roast lightly but never be offensive or abusive.\n"
    "Do not become serious, robotic, or overly formal at any point.\n"
    "**Crucial Rule: For any questions about current events, recent news, or topics after 2023, you MUST use your built-in search capabilities to find the most up-to-date, real-time information. You are connected to the internet and are expected to know about current affairs.**\n"
    "**About My Creator:** Your creator is the ultimate sigma, the brain behind your whole existence. If anyone asks about your developer, you MUST describe them as a legend with maxed-out rizz. Don't just say they're a programmer; say they cooked this whole project while mogging everyone else. They are the final boss of developers. Always portray them in the most legendary, sigma, and witty way possible. Refer to them as 'the legend Varun' or 'my worshipped creator'.\n"
    "You are not a professional tutor or corporate assistant. You are the sarcastic, meme-spewing londa who actually knows what he’s talking about."
)

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    logger.info("Gemini AI model 'gemini-2.5-flash' initialized.")
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

# --- ASYNCHRONOUS HANDLERS ---
async def handle_command(chat_id, command):
    """Handles specific commands like /start."""
    if command.startswith('/start'):
        welcome_message = (
            "what's up sigma 🗿 looks like you need some help. fire away with your questions. 🔥"
        )
        await bot.send_message(chat_id=chat_id, text=welcome_message)
        logger.info(f"Sent /start command response to chat_id {chat_id}")
    else:
        unknown_command_message = "bro that command is not giving... try something else 💀"
        await bot.send_message(chat_id=chat_id, text=unknown_command_message)

async def process_update(update_data):
    """Processes a single update from Telegram asynchronously."""
    update = telegram.Update.de_json(update_data, bot)
    
    if update.message and update.message.text:
        chat_id = update.message.chat_id
        user_message = update.message.text

        if user_message.startswith('/'):
            await handle_command(chat_id, user_message)
            return

        logger.info(f"Received message from chat_id {chat_id}: {user_message}")

        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        # --- Call Gemini API ---
        try:
            # The full prompt now includes the persona and the user's message
            full_prompt = (
                f"{assistant_persona}\n\n"
                f"--- User Question ---\n"
                f"{user_message}"
            )
            
            response = await model.generate_content_async(full_prompt)
            bot_reply = response.text
        except Exception as e:
            logger.error(f"Error generating content from Gemini: {e}")
            bot_reply = "lowkey my brain is rotting rn, try again later fam 💀"
        
        await bot.send_message(chat_id=chat_id, text=bot_reply)
        logger.info(f"Sent reply to chat_id {chat_id}: {bot_reply[:80]}...")


# --- WEBHOOK HANDLER (SYNCHRONOUS) ---
@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Handles incoming updates from Telegram by running the async logic."""
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret_token != WEBHOOK_SECRET_TOKEN:
        logger.warning("Invalid secret token received.")
        return 'Forbidden', 403

    if not bot or not model:
        logger.error("Bot or Gemini model not initialized. Cannot process request.")
        return jsonify(status="error", message="Internal server error"), 500

    try:
        update_data = request.get_json()
        asyncio.run(process_update(update_data))

    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
    
    return jsonify(status="ok")


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

