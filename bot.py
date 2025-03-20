import os
import logging
import re
import sys
import time
import sqlite3
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
from pyrogram.errors import SessionPasswordNeeded, ApiIdInvalid, PhoneNumberInvalid
from client import create_client

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))

# Conversation states
(STATE_API_ID, STATE_API_HASH, STATE_PHONE, STATE_OTP, STATE_2FA) = range(5)

# Rate limiting
user_attempts = defaultdict(int)

async def handle_error(update: Update, error_message: str):
    await update.message.reply_text(
        f"❌ Error: {error_message}\n\n"
        "If the issue persists, please contact @rishabh.zz for support."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        "Use /genstring to generate your Telegram String Session."
    )

async def gen_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if user_attempts[update.effective_user.id] >= 3:
        await update.message.reply_text("🚫 Too many attempts. Try again later.")
        return ConversationHandler.END
    user_attempts[update.effective_user.id] += 1
    context.user_data.clear()
    await update.message.reply_text("Let's generate your string session!\nPlease send your API_ID:")
    return STATE_API_ID

# ... (rest of conversation handlers from previous version)

async def send_session_backup(update: Update, session_string: str):
    with open("session.txt", "w") as f:
        f.write(session_string)
    await update.message.reply_document(
        document=InputFile("session.txt"),
        caption="🔐 Here's your session backup. Store it securely!"
    )
    os.remove("session.txt")

async def revoke_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'client' in context.user_data:
        await context.user_data['client'].terminate()
        await update.message.reply_text("✅ Session revoked successfully!")
    else:
        await update.message.reply_text("❌ No active session to revoke.")

async def show_usage_stats(update: Update):
    if update.effective_user.id == OWNER_ID:
        with sqlite3.connect("analytics.db") as conn:
            cursor = conn.execute("SELECT COUNT(DISTINCT user_id) FROM usage")
            users = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM usage")
            total = cursor.fetchone()[0]
        await update.message.reply_text(
            f"📊 Usage Statistics:\n"
            f"• Unique Users: {users}\n"
            f"• Total Sessions Generated: {total}"
        )

async def cleanup_old_sessions():
    try:
        for session_file in os.listdir("sessions"):
            file_path = os.path.join("sessions", session_file)
            if time.time() - os.path.getmtime(file_path) > 2592000:  # 30 days
                os.remove(file_path)
    except Exception as e:
        logging.error(f"Session cleanup failed: {str(e)}")

def main():
    # Initialize database
    with sqlite3.connect("analytics.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                timestamp INTEGER
            )
        """)
    
    # Setup bot
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", show_usage_stats))
    application.add_handler(CommandHandler("revoke", revoke_session))
    
    # ... (rest of handler setup from previous version)
    
    # Start cleanup scheduler
    application.job_queue.run_repeating(
        lambda _: cleanup_old_sessions(),
        interval=86400,  # Run daily
        first=10
    )
    
    application.run_polling()

if __name__ == "__main__":
    main()
