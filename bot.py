import os
import asyncio
import logging
import re
import json
from typing import List, Dict, Optional
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import tempfile
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class YouTubeBot:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.admin_id = int(os.getenv('ADMIN_ID', '0'))
        self.whitelist_file = 'whitelist.json'
        self.temp_dir = Path('temp_downloads')
        self.temp_dir.mkdir(exist_ok=True)
        self.max_file_size = 2 * 1024 * 1024 * 1024  # 2GB in bytes
        
        # Quality options
        self.quality_options = {
            '240p': 'worst[height<=240]',
            '360p': 'worst[height<=360]',
            '480p': 'worst[height<=480]',
            '720p': 'best[height<=720]',
            '1080p': 'best[height<=1080]',
            'audio': 'bestaudio'
        }
        
        self.load_whitelist()
        
    def load_whitelist(self):
        """Load whitelist from file"""
        try:
            if os.path.exists(self.whitelist_file):
                with open(self.whitelist_file, 'r') as f:
                    data = json.load(f)
                    self.whitelist = set(data.get('users', []))
            else:
                self.whitelist = {self.admin_id}
                self.save_whitelist()
        except Exception as e:
            logger.error(f"Error loading whitelist: {e}")
            self.whitelist = {self.admin_id}
    
    def save_whitelist(self):
        """Save whitelist to file"""
        try:
            with open(self.whitelist_file, 'w') as f:
                json.dump({'users': list(self.whitelist)}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving whitelist: {e}")
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.whitelist
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == self.admin_id
    
    def extract_youtube_urls(self, text: str) -> List[str]:
        """Extract YouTube URLs from text"""
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/playlist\?list=[\w-]+',
            r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+'
        ]
        
        urls = []
        for pattern in youtube_patterns:
            urls.extend(re.findall(pattern, text))
        
        return list(set(urls))  # Remove duplicates
    
    async def get_video_info(self, url: str) -> Optional[Dict]:
        """Get video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                return info
        except Exception as e:
            logger.error(f"Error getting video info for {url}: {e}")
            return None
    
    async def download_video(self, url: str, quality: str, output_path: str) -> Optional[str]:
        """Download video with specified quality"""
        try:
            format_selector = self.quality_options.get(quality, 'best')
            
            ydl_opts = {
                'format': format_selector,
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            
            # Add audio format for audio-only downloads
            if quality == 'audio':
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=True)
                )
                
                # Find the downloaded file
                title = info.get('title', 'video')
                ext = 'mp3' if quality == 'audio' else info.get('ext', 'mp4')
                filename = f"{title}.{ext}"
                filepath = os.path.join(output_path, filename)
                
                # Find actual file (yt-dlp might change filename)
                for file in os.listdir(output_path):
                    if file.startswith(title.replace('/', '_').replace('\\', '_')[:50]):
                        filepath = os.path.join(output_path, file)
                        break
                
                return filepath if os.path.exists(filepath) else None
                
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return None
    
    def cleanup_temp_files(self, temp_path: str):
        """Clean up temporary files"""
        try:
            if os.path.exists(temp_path):
                if os.path.isdir(temp_path):
                    shutil.rmtree(temp_path)
                else:
                    os.remove(temp_path)
        except Exception as e:
            logger.error(f"Error cleaning up {temp_path}: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        if not self.is_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        welcome_text = """
🎥 **YouTube Downloader Bot**

**Commands:**
• Send YouTube links to download videos
• Use /quality to select download quality
• Send multiple links for batch download

**Admin Commands:**
• /add_user <user_id> - Add user to whitelist
• /remove_user <user_id> - Remove user from whitelist
• /list_users - Show whitelisted users

**Quality Options:**
240p, 360p, 480p, 720p, 1080p, audio-only
        """
        
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def quality_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /quality command"""
        user_id = update.effective_user.id
        
        if not self.is_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        keyboard = []
        row = []
        for quality in self.quality_options.keys():
            row.append(InlineKeyboardButton(quality, callback_data=f"quality_{quality}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🎯 Select download quality:",
            reply_markup=reply_markup
        )
    
    async def handle_quality_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle quality selection callback"""
        query = update.callback_query
        await query.answer()
        
        quality = query.data.replace("quality_", "")
        user_id = query.from_user.id
        
        # Store quality preference
        context.user_data['quality'] = quality
        
        await query.edit_message_text(
            f"✅ Quality set to: **{quality}**\n\nNow send YouTube links to download!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def add_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_user command (admin only)"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Only admin can use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /add_user <user_id>")
            return
        
        try:
            new_user_id = int(context.args[0])
            self.whitelist.add(new_user_id)
            self.save_whitelist()
            await update.message.reply_text(f"✅ User {new_user_id} added to whitelist.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def remove_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove_user command (admin only)"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Only admin can use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /remove_user <user_id>")
            return
        
        try:
            remove_user_id = int(context.args[0])
            if remove_user_id == self.admin_id:
                await update.message.reply_text("❌ Cannot remove admin from whitelist.")
                return
            
            self.whitelist.discard(remove_user_id)
            self.save_whitelist()
            await update.message.reply_text(f"✅ User {remove_user_id} removed from whitelist.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")
    
    async def list_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list_users command (admin only)"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Only admin can use this command.")
            return
        
        if not self.whitelist:
            await update.message.reply_text("📝 Whitelist is empty.")
            return
        
        user_list = "\n".join([f"• {uid}" for uid in sorted(self.whitelist)])
        await update.message.reply_text(f"📝 **Whitelisted users:**\n{user_list}", parse_mode=ParseMode.MARKDOWN)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with YouTube links"""
        user_id = update.effective_user.id
        
        if not self.is_authorized(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        text = update.message.text
        urls = self.extract_youtube_urls(text)
        
        if not urls:
            await update.message.reply_text("❌ No YouTube links found in your message.")
            return
        
        quality = context.user_data.get('quality', '720p')
        
        status_message = await update.message.reply_text(
            f"🔄 Processing {len(urls)} link(s) with quality: {quality}..."
        )
        
        failed_urls = []
        success_count = 0
        
        for i, url in enumerate(urls, 1):
            try:
                await status_message.edit_text(
                    f"🔄 Processing {i}/{len(urls)}: Getting video info..."
                )
                
                # Get video info
                info = await self.get_video_info(url)
                if not info:
                    failed_urls.append((url, "Could not extract video info"))
                    continue
                
                title = info.get('title', 'Unknown')[:50]
                
                await status_message.edit_text(
                    f"🔄 Processing {i}/{len(urls)}: Downloading '{title}'..."
                )
                
                # Create temp directory for this download
                temp_download_dir = tempfile.mkdtemp(dir=self.temp_dir)
                
                # Download video
                filepath = await self.download_video(url, quality, temp_download_dir)
                
                if not filepath or not os.path.exists(filepath):
                    failed_urls.append((url, "Download failed"))
                    self.cleanup_temp_files(temp_download_dir)
                    continue
                
                # Check file size
                file_size = os.path.getsize(filepath)
                if file_size > self.max_file_size:
                    await update.message.reply_text(
                        f"📁 **{title}**\n\n"
                        f"❌ File too large for Telegram ({file_size / (1024**3):.1f} GB)\n\n"
                        f"🔗 Direct link: {url}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    self.cleanup_temp_files(temp_download_dir)
                    success_count += 1
                    continue
                
                await status_message.edit_text(
                    f"🔄 Processing {i}/{len(urls)}: Uploading '{title}'..."
                )
                
                # Send file
                with open(filepath, 'rb') as video_file:
                    if quality == 'audio':
                        await update.message.reply_audio(
                            audio=video_file,
                            title=title,
                            caption=f"🎵 **{title}**\n📊 Quality: {quality}\n🔗 Source: {url}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    else:
                        await update.message.reply_video(
                            video=video_file,
                            caption=f"🎥 **{title}**\n📊 Quality: {quality}\n🔗 Source: {url}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                
                success_count += 1
                
                # Cleanup
                self.cleanup_temp_files(temp_download_dir)
                
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                failed_urls.append((url, str(e)))
                continue
        
        # Final status
        final_text = f"✅ **Batch completed!**\n\n"
        final_text += f"📊 **Summary:**\n"
        final_text += f"• Successful: {success_count}/{len(urls)}\n"
        final_text += f"• Failed: {len(failed_urls)}/{len(urls)}\n"
        final_text += f"• Quality: {quality}"
        
        if failed_urls:
            final_text += f"\n\n❌ **Failed downloads:**\n"
            for url, error in failed_urls[:5]:  # Limit to 5 failed URLs
                final_text += f"• {url[:50]}... - {error[:30]}...\n"
            
            if len(failed_urls) > 5:
                final_text += f"• ... and {len(failed_urls) - 5} more"
        
        await status_message.edit_text(final_text, parse_mode=ParseMode.MARKDOWN)



def main():
    """Main function"""
    bot = YouTubeBot()
    
    if not bot.bot_token:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    if not bot.admin_id:
        logger.error("ADMIN_ID environment variable not set!")
        return
    
    # Create application
    application = Application.builder().token(bot.bot_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("quality", bot.quality_command))
    application.add_handler(CommandHandler("add_user", bot.add_user_command))
    application.add_handler(CommandHandler("remove_user", bot.remove_user_command))
    application.add_handler(CommandHandler("list_users", bot.list_users_command))
    application.add_handler(CallbackQueryHandler(bot.handle_quality_selection, pattern="^quality_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot
    logger.info("Starting YouTube Downloader Bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()