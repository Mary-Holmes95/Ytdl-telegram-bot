#!/bin/bash

# Install system dependencies
sudo apt-get update
sudo apt-get install -y ffmpeg

# Install Python packages
pip install -r requirements.txt

# Create temp directory
mkdir -p temp_downloads

# Start the bot
python bot.py