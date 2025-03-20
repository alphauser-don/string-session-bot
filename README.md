# 🔒 Secure String Session Bot

A secure Telegram bot for generating Pyrogram string sessions with advanced features:

## Features
- Rate limiting (3 attempts/user)
- Automatic session backup
- Session revocation
- Usage statistics
- Auto-clean old sessions
- Multi-language support
- Error tracking
- Daily maintenance

## Deployment
```bash
sudo apt update && sudo apt install python3-venv
sudo apt install -y python3 python3-venv python3-pip git nginx
python3 -m venv venv
source venv/bin/activate
git clone https://github.com/yourusername/string-session-bot
cd string-session-bot
pip install -r requirements.txt

# Configure environment
cp example.env .env
nano .env

# Create required directories
mkdir sessions

# Start the bot
python bot.py
