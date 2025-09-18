# YouTube Downloader Telegram Bot

A powerful Telegram bot that downloads YouTube videos with batch processing, quality selection, and whitelist system.

## 🚀 Features

- ✅ **Whitelist System**: Only authorized users can use the bot
- ✅ **Admin Controls**: Add/remove users from whitelist
- ✅ **Batch Processing**: Send multiple YouTube links at once
- ✅ **Quality Selection**: 240p → 1080p + audio-only option
- ✅ **Smart File Handling**: Handles Telegram's 2GB file limit
- ✅ **Error Reporting**: Reports failed downloads at batch end
- ✅ **Proper Cleanup**: Automatic temporary file cleanup

## 📋 Requirements

- Python 3.8+
- FFmpeg (for audio conversion)
- Telegram Bot Token
- Admin Telegram User ID

## 🛠 Installation

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd youtube-downloader-bot

# Build Docker image
docker build -t youtube-bot .

# Run with environment variables
docker run -d \
  -e BOT_TOKEN=your_bot_token_here \
  -e ADMIN_ID=your_telegram_user_id \
  --name youtube-bot \
  youtube-bot
```

### Option 2: Direct Python

```bash
# Clone the repository
git clone <your-repo-url>
cd youtube-downloader-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export BOT_TOKEN=your_bot_token_here
export ADMIN_ID=your_telegram_user_id

# Run the bot
python bot.py
```

### Option 3: Railway (Recommended for 24/7)

1. Create account at Railway.app
2. Connect your GitHub repository
3. Set environment variables:
   - `BOT_TOKEN`: Your Telegram bot token
   - `ADMIN_ID`: Your Telegram user ID
4. Deploy automatically - no keep-alive needed!

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram bot token from @BotFather | ✅ Yes |
| `ADMIN_ID` | Your Telegram user ID (admin) | ✅ Yes |

### Getting Your Bot Token

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Choose a name and username for your bot
4. Copy the bot token

### Getting Your User ID

1. Message @userinfobot on Telegram
2. Copy your user ID number

## 🎮 Usage

### User Commands

- **Send YouTube links**: Just paste YouTube URLs to download
- `/start` - Show welcome message and instructions
- `/quality` - Select download quality (240p-1080p, audio)

### Admin Commands

- `/add_user <user_id>` - Add user to whitelist
- `/remove_user <user_id>` - Remove user from whitelist  
- `/list_users` - Show all whitelisted users

### Supported Link Types

- YouTube videos: `https://youtube.com/watch?v=...`
- YouTube shorts: `https://youtube.com/shorts/...`
- Short URLs: `https://youtu.be/...`
- Playlists: `https://youtube.com/playlist?list=...`

## 📊 Quality Options

| Quality | Description |
|---------|-------------|
| 240p | Lowest video quality |
| 360p | Low video quality |
| 480p | Medium video quality |
| 720p | HD video quality (default) |
| 1080p | Full HD video quality |
| audio | Audio-only (MP3) |

## 🔧 File Structure

```
youtube-downloader-bot/
├── bot.py              # Main bot code
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
├── README.md          # This file
├── .gitignore        # Git ignore rules
├── whitelist.json    # User whitelist (auto-generated)
└── temp_downloads/   # Temporary download folder
```

## 🚨 Important Notes

### File Size Limits

- Telegram bots can upload files up to 2 GB
- Files larger than 2 GB will return a "too large" message with direct link
- The bot automatically checks file sizes before uploading

### Performance

- Downloads are processed one by one to avoid memory issues
- Temporary files are cleaned up automatically
- Failed downloads are reported at the end of each batch

### Security

- Only whitelisted users can use the bot
- Admin ID must be set via environment variable
- Whitelist is stored in `whitelist.json` file

## 🐛 Troubleshooting

### Common Issues

1. **Bot doesn't respond**
   - Check if BOT_TOKEN is correct
   - Verify bot is started with @BotFather
   - Check if your user ID is in whitelist

2. **Downloads fail**
   - Ensure FFmpeg is installed
   - Check if YouTube links are valid
   - Verify bot has write permissions

3. **Docker issues**
   - Make sure Docker has enough disk space
   - Check if ports are available
   - Verify environment variables are set

### Debug Mode

Add these environment variables for debugging:

```bash
export PYTHONUNBUFFERED=1
export LOG_LEVEL=DEBUG
```

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

If you encounter any issues:

1. Check the troubleshooting section
2. Review bot logs for error messages
3. Create an issue on GitHub with details

---

**Note**: This bot is for educational purposes. Please respect YouTube's Terms of Service and copyright laws when downloading content.