# Telegram Invite Bot

This bot auto-generates expiring group invite links, tracks invites, awards stars, and handles withdrawals.

## Setup

1. Clone repo  
   `git clone https://github.com/yourusername/telegram-invite-bot.git`  
2. Create a virtual environment  
   `python -m venv venv && source venv/bin/activate`  
3. Install dependencies  
   `pip install -r requirements.txt`  
4. Edit `invite_bot.py` to insert your bot token  
   ```python
   BOT_TOKEN = "8201716701:AAEjfIHh4cJh1p8zWwBhYjl4B4q3HOrqvdY"
