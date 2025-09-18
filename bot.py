import os
import re
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import yt_dlp

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Whitelist
whitelist = {ADMIN_ID}

# Regex for YouTube links
YOUTUBE_REGEX = re.compile(r"(https?://[^\s]+)")

# --- Commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in whitelist:
        await update.message.reply_text("❌ You are not allowed to use this bot.")
        return
    await update.message.reply_text("✅ Send me YouTube links (one or many) and I’ll download them!")

async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.add(uid)
        await update.message.reply_text(f"✅ Added user {uid} to whitelist.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def deluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /deluser <user_id>")
        return
    try:
        uid = int(context.args[0])
        whitelist.discard(uid)
        await update.message.reply_text(f"✅ Removed user {uid} from whitelist.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in whitelist:
        await update.message.reply_text("❌ You are not allowed to use this bot.")
        return

    text = update.message.text.strip()
    links = [url for url in re.findall(YOUTUBE_REGEX, text) if "youtu" in url]

    if not links:
        await update.message.reply_text("❌ No YouTube links found!")
        return

    await update.message.reply_text(f"📥 Downloading {len(links)} videos...")

    failed = []
    for idx, url in enumerate(links, start=1):
        try:
            await update.message.reply_text(f"▶️ Processing video {idx}/{len(links)}...")

            ydl_opts = {
                "format": "best[height<=480]",  # default 480p
                "outtmpl": f"downloads/%(title)s.%(ext)s",
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            if os.path.getsize(filename) > 49 * 1024 * 1024:
                await update.message.reply_text(f"⚠️ Skipped {url} (file too large for free Telegram).")
                failed.append(url)
                os.remove(filename)
                continue

            with open(filename, "rb") as f:
                await update.message.reply_video(video=f, caption=info.get("title", "Video"))

            os.remove(filename)

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            failed.append(url)

    if failed:
        await update.message.reply_text("❌ Failed links:\n" + "\n".join(failed))
    else:
        await update.message.reply_text("✅ All videos sent!")

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adduser", adduser))
    app.add_handler(CommandHandler("deluser", deluser))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_links))
    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()