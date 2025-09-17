import os
import json
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ----- Environment variables -----
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ----- Whitelist -----
WHITELIST_FILE = "allowed_users.json"
if not os.path.exists(WHITELIST_FILE):
    with open(WHITELIST_FILE, "w") as f:
        json.dump([ADMIN_ID], f)  # Start with admin only

with open(WHITELIST_FILE, "r") as f:
    allowed_users = json.load(f)

# ----- Config -----
BATCH_LIMIT = 5  # Default batch limit


# ---------- Helpers ----------
def save_whitelist():
    with open(WHITELIST_FILE, "w") as f:
        json.dump(allowed_users, f)


def is_allowed(user_id):
    return user_id in allowed_users


# ---------- Bot Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("🚫 You are not allowed to use this bot.")
        return
    await update.message.reply_text(
        "👋 Welcome! Send me YouTube links (one or multiple separated by spaces/newlines).\n"
        "Use /quality to pick resolution before downloading.\n"
        "Default = 480p."
    )


async def set_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user pick video quality"""
    if not is_allowed(update.effective_user.id):
        return
    keyboard = [
        [InlineKeyboardButton("240p", callback_data="240"),
         InlineKeyboardButton("360p", callback_data="360")],
        [InlineKeyboardButton("480p", callback_data="480"),
         InlineKeyboardButton("720p", callback_data="720")],
        [InlineKeyboardButton("1080p", callback_data="1080"),
         InlineKeyboardButton("🎵 Audio only", callback_data="audio")]
    ]
    await update.message.reply_text(
        "🎥 Choose your preferred quality:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def quality_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quality button press"""
    query = update.callback_query
    await query.answer()
    context.user_data["quality"] = query.data
    await query.edit_message_text(f"✅ Selected quality: {query.data}")


async def download_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download one or more YouTube links"""
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("🚫 You are not allowed to use this bot.")
        return

    links = update.message.text.split()
    quality = context.user_data.get("quality", "480")  # Default to 480p
    failed = []

    # Limit batch size
    global BATCH_LIMIT
    if len(links) > BATCH_LIMIT:
        await update.message.reply_text(
            f"⚠️ Too many links! Current limit is {BATCH_LIMIT}. "
            f"Taking the first {BATCH_LIMIT} only."
        )
        links = links[:BATCH_LIMIT]

    for link in links:
        try:
            ydl_opts = {
                "outtmpl": "%(title).50s.%(ext)s",  # short filename
                "quiet": True,
                "format": "bestaudio/best" if quality == "audio" else f"best[height<={quality}]",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                file_path = ydl.prepare_filename(info)

            await update.message.reply_document(document=open(file_path, "rb"))
            os.remove(file_path)  # Cleanup ✅
        except Exception as e:
            failed.append(link)
            print(f"❌ Error with {link}: {e}")

    if failed:
        await update.message.reply_text("❌ Failed links:\n" + "\n".join(failed))
    else:
        await update.message.reply_text("✅ All downloads finished!")


# ---------- Admin Commands ----------
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        if user_id not in allowed_users:
            allowed_users.append(user_id)
            save_whitelist()
            await update.message.reply_text(f"✅ Added user {user_id}")
        else:
            await update.message.reply_text("ℹ️ User already allowed")
    except:
        await update.message.reply_text("⚠️ Usage: /adduser <user_id>")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(context.args[0])
        if user_id in allowed_users:
            allowed_users.remove(user_id)
            save_whitelist()
            await update.message.reply_text(f"❌ Removed user {user_id}")
        else:
            await update.message.reply_text("ℹ️ User not in whitelist")
    except:
        await update.message.reply_text("⚠️ Usage: /removeuser <user_id>")


async def set_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to set batch size"""
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        global BATCH_LIMIT
        new_limit = int(context.args[0])
        BATCH_LIMIT = new_limit
        await update.message.reply_text(f"✅ Batch limit set to {BATCH_LIMIT}")
    except:
        await update.message.reply_text("⚠️ Usage: /setbatch <number>")


# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Normal user commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quality", set_quality))
    app.add_handler(CallbackQueryHandler(quality_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_videos))

    # Admin commands
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("setbatch", set_batch))

    print("🚀 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()