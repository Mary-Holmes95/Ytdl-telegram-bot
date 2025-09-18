import os
import time
import telebot
from flask import Flask

# =====================
# BOT CONFIG
# =====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Add in Replit Secrets
bot = telebot.TeleBot(BOT_TOKEN)

# =====================
# BATCH SENDING SETTINGS
# =====================
BATCH_SIZE = 10   # Change if you want smaller/larger batches
DELAY_BETWEEN_BATCHES = 2  # seconds delay between batches


# =====================
# COMMAND HANDLERS
# =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "✅ Bot is online and ready!")


@bot.message_handler(commands=['send'])
def send_batch(message):
    """
    Sends a batch of dummy video links (replace with your real video list).
    """
    chat_id = message.chat.id

    # Example video links (replace with your own)
    video_links = [
        f"https://example.com/video{i}.mp4" for i in range(1, 51)
    ]

    # Send in batches
    for i in range(0, len(video_links), BATCH_SIZE):
        batch = video_links[i:i+BATCH_SIZE]
        for link in batch:
            try:
                bot.send_message(chat_id, link)
            except Exception as e:
                print(f"Error sending message: {e}")
                time.sleep(2)

        time.sleep(DELAY_BETWEEN_BATCHES)


# =====================
# KEEP-ALIVE FLASK SERVER
# =====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"


def run_flask():
    app.run(host="0.0.0.0", port=8080)


# =====================
# START BOT + KEEP ALIVE
# =====================
import threading

if __name__ == "__main__":
    # Run Flask server in a separate thread
    threading.Thread(target=run_flask).start()

    # Start polling the Telegram bot
    bot.infinity_polling(skip_pending=True)