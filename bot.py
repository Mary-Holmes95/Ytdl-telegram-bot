#!/usr/bin/env python3
"""
Ultimate Telegram YouTube Downloader Bot
- Uses yt-dlp for downloads (ffmpeg required in environment)
- Whitelist persisted to allowed_users.json (ignored by git)
- Admin ID & Bot token read from environment variables
- Single-link and batch mode with quality selection (240..1080 + audio)
- Reports failed links at the end
"""

import os
import json
import re
import shutil
import logging
from pathlib import Path
from urllib.parse import unquote

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# --------- Config via environment variables (do NOT hardcode in repo) ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")          # required
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # set your numeric Telegram ID here on Render
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")      # optional for webhook mode (e.g. https://your-service.onrender.com)
PORT = int(os.environ.get("PORT", "8443"))

# --------- Files & folders (kept local on server) ----------
WHITELIST_FILE = "allowed_users.json"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# --------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------- Helper: whitelist persistence ----------
def load_whitelist():
    if not os.path.exists(WHITELIST_FILE):
        # start with admin only (but file not committed if .gitignore configured)
        data = {"ids": [ADMIN_ID] if ADMIN_ID else [], "usernames": {}}
        save_whitelist(data)
        return data
    with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_whitelist(data):
    with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

whitelist = load_whitelist()  # dict: {"ids": [...], "usernames": {"name": id}}

def is_allowed_user(user):
    if not user:
        return False
    uid = user.id
    uname = (user.username or "").lower()
    return (uid and uid in whitelist.get("ids", [])) or (uname and uname in whitelist.get("usernames", {})) or (uid == ADMIN_ID)

# track last-seen username->id mapping (persisted through whitelist file usernames map)
def track_username(user):
    if not user:
        return
    uname = (user.username or "").lower()
    uid = user.id
    if uname:
        whitelist.setdefault("usernames", {})[uname] = uid
        save_whitelist(whitelist)

# ---------- Utilities ----------
YOUTUBE_URL_RE = re.compile(r"(https?://\S+)")

def extract_links(text: str):
    if not text:
        return []
    return [m.group(1).strip() for m in YOUTUBE_URL_RE.finditer(text)]

def quality_keyboard(tag_prefix: str):
    # tag_prefix: "single" or "batch"
    buttons = [
        InlineKeyboardButton("240p", callback_data=f"{tag_prefix}|240"),
        InlineKeyboardButton("360p", callback_data=f"{tag_prefix}|360"),
        InlineKeyboardButton("480p", callback_data=f"{tag_prefix}|480"),
        InlineKeyboardButton("720p", callback_data=f"{tag_prefix}|720"),
        InlineKeyboardButton("1080p", callback_data=f"{tag_prefix}|1080"),
        InlineKeyboardButton("Audio (mp3)", callback_data=f"{tag_prefix}|audio"),
    ]
    # 2 per row for a compact layout
    kb = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0, len(buttons), 2)])
    return kb

# ---------- Session stores (in-memory on server). fine for small bots on Render.
# If server restarts, pending batches are lost (but whitelist persists).
pending_single = {}   # user_id -> url (when user sent one link and needs to choose quality)
pending_batch = {}    # user_id -> [urls]
# ---------- Download function ----------
def yt_download_to_file(url: str, quality: str) -> (Path, str):
    """
    Downloads a single url at the requested quality.
    Returns (Path-to-file, title).
    Raises exception on failure.
    """
    # safe outtmpl
    out_template = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")

    ydl_opts = {
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if quality == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        })
    else:
        # ask for bestvideo with exact height if available, else fallback to best below height
        # yt-dlp format selector supports height<= and equality; using <= to allow fallback
        ydl_opts["format"] = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        filename = ydl.prepare_filename(info)
        if quality == "audio":
            # yt-dlp replaced extension with original audio extension; convert filename to .mp3
            filename = os.path.splitext(filename)[0] + ".mp3"
        return Path(filename), info.get("title", "video")

# ---------- Handlers ----------
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_username(update.effective_user)
    if not is_allowed_user(update.effective_user):
        await update.message.reply_text("🚫 You are not allowed to use this bot.")
        return
    await update.message.reply_text(
        "👋 Welcome! Send one or more YouTube links (one per line).\n"
        "- Single link → pick a quality (240..1080 or audio).\n"
        "- Multiple links → pick one quality for whole batch.\n"
        "Admins: /allow <id_or_username>, /deny <id_or_username>, /listallowed"
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_username(update.effective_user)
    if not is_allowed_user(update.effective_user):
        await update.message.reply_text("🚫 You are not allowed to use this bot.")
        return
    txt = (
        "How to use:\n"
        "- Send a single YouTube link → you'll get buttons for 240/360/480/720/1080/audio.\n"
        "- Send many links (one per line) → you'll be asked once for quality and the bot will download sequentially.\n"
        "- Admin commands (only for ADMIN_ID): /allow, /deny, /listallowed\n"
        "\nPrivacy note: whitelist is stored locally on the server only (file is .gitignored)."
    )
    await update.message.reply_text(txt)

async def allow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_username(update.effective_user)
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /allow <numeric_id_or_username>\nUsername may begin with @ or not.")
        return
    arg = context.args[0].lstrip("@").lower()
    # If numeric id:
    if arg.isdigit():
        uid = int(arg)
        if uid not in whitelist.get("ids", []):
            whitelist.setdefault("ids", []).append(uid)
            save_whitelist(whitelist)
        await update.message.reply_text(f"✅ Allowed user id {uid}")
    else:
        # username — if we know mapping from prior interactions, convert to id; otherwise store username mapping
        # we accept storing username mapping; full resolution to numeric id will be attempted when user interacts
        whitelist.setdefault("usernames", {})[arg] = whitelist.get("usernames", {}).get(arg) or None
        save_whitelist(whitelist)
        await update.message.reply_text(f"✅ Allowed username @{arg} (user must message the bot once for ID mapping)")

async def deny_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_username(update.effective_user)
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /deny <numeric_id_or_username>")
        return
    arg = context.args[0].lstrip("@").lower()
    removed = False
    if arg.isdigit():
        uid = int(arg)
        if uid in whitelist.get("ids", []):
            whitelist["ids"].remove(uid)
            removed = True
    else:
        if arg in whitelist.get("usernames", {}):
            whitelist["usernames"].pop(arg, None)
            removed = True
    if removed:
        save_whitelist(whitelist)
        await update.message.reply_text(f"Removed {arg} from whitelist.")
    else:
        await update.message.reply_text(f"{arg} not found in whitelist.")

async def listallowed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_username(update.effective_user)
    if update.effective_user.id != ADMIN_ID:
        return
    ids = whitelist.get("ids", [])
    usernames = whitelist.get("usernames", {})
    msg = "Whitelisted IDs:\n" + ("\n".join(map(str, ids)) if ids else "(none)") + "\n\n"
    msg += "Whitelisted usernames (may need to message bot for numeric id mapping):\n" + ("\n".join(f"@{u}" for u in usernames.keys()) if usernames else "(none)")
    await update.message.reply_text(msg)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_username(update.effective_user)
    if not is_allowed_user(update.effective_user):
        await update.message.reply_text("🚫 You are not allowed to use this bot.")
        return

    text = update.message.text or ""
    links = extract_links(text)
    if not links:
        await update.message.reply_text("Send one or more YouTube links (one per line).")
        return

    if len(links) == 1:
        # single mode: store url and ask quality
        user_id = update.effective_user.id
        pending_single[user_id] = links[0]
        kb = quality_keyboard("single")
        await update.message.reply_text("Choose quality for this video:", reply_markup=kb)
    else:
        # batch mode
        user_id = update.effective_user.id
        pending_batch[user_id] = links
        kb = quality_keyboard("batch")
        await update.message.reply_text(f"Detected {len(links)} links. Choose one quality for the whole batch:", reply_markup=kb)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    track_username(user)
    if not is_allowed_user(user):
        await query.edit_message_text("🚫 You are not allowed to use this bot.")
        return

    data = query.data  # format: "<mode>|<quality>"
    try:
        mode, quality = data.split("|", 1)
    except Exception:
        await query.edit_message_text("Invalid action.")
        return

    user_id = user.id
    if mode == "single":
        url = pending_single.pop(user_id, None)
        if not url:
            await query.edit_message_text("Session expired or no URL found.")
            return
        await query.edit_message_text(f"Downloading single video at {quality}...")
        failed = []
        try:
            filepath, title = yt_download_to_file(url, quality)
            # send
            with open(filepath, "rb") as f:
                if quality == "audio":
                    await context.bot.send_audio(user_id, f, caption=title)
                else:
                    await context.bot.send_video(user_id, f, caption=title)
            filepath.unlink(missing_ok=True)
        except Exception as e:
            logger.exception("Download/send failed")
            failed.append(url)
            await context.bot.send_message(user_id, f"⚠️ Failed to download/send: {url}\nError: {e}")

        if failed:
            await context.bot.send_message(user_id, "❌ Failed links:\n" + "\n".join(failed))
        else:
            await context.bot.send_message(user_id, "✅ Done.")

    elif mode == "batch":
        links = pending_batch.pop(user_id, [])
        if not links:
            await query.edit_message_text("No batch found (session expired).")
            return
        await query.edit_message_text(f"Starting batch download ({len(links)} videos) at {quality}...")
        failed = []
        for url in links:
            try:
                filepath, title = yt_download_to_file(url, quality)
                with open(filepath, "rb") as f:
                    if quality == "audio":
                        await context.bot.send_audio(user_id, f, caption=title)
                    else:
                        await context.bot.send_video(user_id, f, caption=title)
                filepath.unlink(missing_ok=True)
            except Exception as e:
                logger.exception("Batch item failed")
                failed.append(url)
        if failed:
            await context.bot.send_message(user_id, "❌ Batch finished with failures:\n" + "\n".join(failed))
        else:
            await context.bot.send_message(user_id, "✅ Batch finished successfully!")
    else:
        await query.edit_message_text("Unknown mode.")

# alias function for compatibility with older code paths
def yt_download_to_file(url, quality):
    return yt_download_to_file_impl(url, quality)

# Avoid name clash; implement actual downloader
def yt_download_to_file_impl(url: str, quality: str):
    return yt_download_to_file(url, quality)  # forward to main implementation

# But define the used function properly (fixing naming)
def yt_download_to_file(url: str, quality: str):
    return yt_download_to_file_core(url, quality)

def yt_download_to_file_core(url: str, quality: str):
    return __yt_download_to_file(url, quality)

def __yt_download_to_file(url: str, quality: str):
    """
    actual implementation placed at bottom to avoid forward-reference issues
    """
    # code moved here to keep above handlers concise
    return _yt_download_core(url, quality)

def _yt_download_core(url: str, quality: str):
    out_template = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    ydl_opts = {"outtmpl": out_template, "noplaylist": True, "quiet": True, "no_warnings": True}

    if quality == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        })
    else:
        ydl_opts["format"] = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if quality == "audio":
            filename = os.path.splitext(filename)[0] + ".mp3"
        return Path(filename), info.get("title", "Video")

# ---------- Main ----------
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Exiting.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("allow", allow_cmd))
    app.add_handler(CommandHandler("deny", deny_cmd))
    app.add_handler(CommandHandler("listallowed", listallowed_cmd))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # webhook if WEBHOOK_URL set, otherwise polling (good for local tests)
    if WEBHOOK_URL:
        # use token in URL path to help with security
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=BOT_TOKEN, webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
