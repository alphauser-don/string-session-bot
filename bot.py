import os
import logging
import re
import sys
import time
import sqlite3
from datetime import datetime, time
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
from client import SessionManager

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize session manager
session_manager = SessionManager()

# Configuration
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))

# Conversation states
(STATE_API_ID, STATE_API_HASH, STATE_PHONE, STATE_OTP, STATE_2FA) = range(5)

# Rate limiting
user_attempts = defaultdict(int)

async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE, error_message: str):
    await update.message.reply_text(
        f"❌ Error: {error_message}\n\n"
        "If the issue persists, please contact @rishabh.zz for support."
    )
    logger.error(f"Error occurred: {error_message}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        "Use /genstring to generate your Telegram String Session."
    )

async def gen_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_attempts[user_id] >= 3:
        await update.message.reply_text("🚫 Too many attempts. Try again later.")
        return ConversationHandler.END
    
    user_attempts[user_id] += 1
    context.user_data.clear()
    await update.message.reply_text("Let's generate your string session!\nPlease send your API_ID:")
    return STATE_API_ID

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Process cancelled.")
    return ConversationHandler.END

async def handle_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not re.match(r"^\d+$", user_input):
        await update.message.reply_text("❌ Invalid API_ID. Only numbers allowed. Try again:")
        return STATE_API_ID
    
    try:
        context.user_data['api_id'] = int(user_input)
        await update.message.reply_text("✅ API_ID accepted! Send your API_HASH:")
        return STATE_API_HASH
    except ValueError:
        await handle_error(update, context, "Invalid API_ID format")
        return STATE_API_ID

async def handle_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not user_input:
        await update.message.reply_text("❌ API_HASH cannot be empty. Try again:")
        return STATE_API_HASH
    
    context.user_data['api_hash'] = user_input
    await update.message.reply_text("📱 Now send your phone number (with country code):\nExample: +14151234567")
    return STATE_PHONE

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.effective_user.id
    
    if not re.match(r"^\+?\d+$", user_input):
        await update.message.reply_text("❌ Invalid phone number. Only numbers/+ allowed. Try again:")
        return STATE_PHONE
    
    context.user_data['phone'] = user_input
    try:
        client = await session_manager.create_client(
            context.user_data['api_id'],
            context.user_data['api_hash'],
            user_id
        )
        await client.connect()
        sent_code = await client.send_code(user_input)
        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash
        await update.message.reply_text("🔢 OTP sent! Enter the code:")
        return STATE_OTP
    except Exception as e:
        await handle_error(update, context, str(e))
        return await cleanup_session(context)

async def handle_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not re.match(r"^\d+$", user_input):
        await update.message.reply_text("❌ Invalid OTP. Only numbers allowed. Try again:")
        return STATE_OTP
    
    context.user_data['otp'] = user_input
    client = context.user_data['client']
    
    try:
        await client.sign_in(
            context.user_data['phone'],
            context.user_data['phone_code_hash'],
            user_input
        )
    except SessionPasswordNeeded:
        await update.message.reply_text("🔑 Enter your 2FA password:")
        return STATE_2FA
    except Exception as e:
        await handle_error(update, context, str(e))
        return await cleanup_session(context)
    
    return await finalize_session(update, context)

async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not user_input:
        await update.message.reply_text("❌ 2FA password cannot be empty. Try again:")
        return STATE_2FA
    
    context.user_data['2fa_password'] = user_input
    try:
        await context.user_data['client'].check_password(user_input)
        return await finalize_session(update, context)
    except Exception as e:
        await handle_error(update, context, f"2FA Failed: {str(e)}")
        return await cleanup_session(context)

async def finalize_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = context.user_data['client']
    try:
        string_session = await client.export_session_string()
        await client.send_message("me", f"**String Session:**\n`{string_session}`")
        await send_session_backup(update, string_session)
        await log_usage(update.effective_user.id)
        await update.message.reply_text("✅ Success! Check Saved Messages.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Generated session:\n`{string_session}`")
    await client.disconnect()
    return ConversationHandler.END

async def send_session_backup(update: Update, session_string: str):
    try:
        with open("session.txt", "w") as f:
            f.write(session_string)
        await update.message.reply_document(
            document=InputFile("session.txt"),
            caption="🔐 Session Backup - Keep this secure!"
        )
        os.remove("session.txt")
    except Exception as e:
        await handle_error(update, context, f"Backup failed: {str(e)}")

async def log_usage(user_id: int):
    try:
        with sqlite3.connect("analytics.db") as conn:
            conn.execute("""
                INSERT INTO usage (user_id, timestamp)
                VALUES (?, ?)
            """, (user_id, int(time.time())))
    except Exception as e:
        logger.error(f"Usage logging failed: {str(e)}")

async def cleanup_session(context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = context.user_data.get('user_id')
        if user_id:
            await session_manager.revoke_session(user_id)
        if 'client' in context.user_data:
            await context.user_data['client'].disconnect()
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
    return ConversationHandler.END

async def revoke_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        await session_manager.revoke_session(user_id)
        await update.message.reply_text("✅ Session revoked successfully!")
    except Exception as e:
        await handle_error(update, context, str(e))

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔️ Unauthorized!")
        return
    
    try:
        with sqlite3.connect("analytics.db") as conn:
            cursor = conn.execute("SELECT COUNT(DISTINCT user_id) FROM usage")
            unique_users = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM usage")
            total_sessions = cursor.fetchone()[0]
            
        await update.message.reply_text(
            f"📊 Bot Statistics:\n"
            f"• Unique Users: {unique_users}\n"
            f"• Total Sessions Generated: {total_sessions}"
        )
    except Exception as e:
        await handle_error(update, context, str(e))

async def update_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔️ Unauthorized!")
        return
    
    try:
        from git import Repo
        Repo('.').remotes.origin.pull()
        await update.message.reply_text("✅ Updated! Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await handle_error(update, context, f"Update failed: {str(e)}")

async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE):
    try:
        await session_manager.cleanup_old_sessions()
        logger.info("Daily session cleanup completed")
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")

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

    # Create application
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('genstring', gen_string)],
        states={
            STATE_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_id)],
            STATE_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_hash)],
            STATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
            STATE_OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp)],
            STATE_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_2fa)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('revoke', revoke_session))
    application.add_handler(CommandHandler('stats', show_stats))
    application.add_handler(CommandHandler('updatebot', update_bot))

    # Schedule daily cleanup
    application.job_queue.run_daily(
        daily_cleanup,
        time=time(hour=3, minute=0),  # Correct time specification
        name="daily_cleanup"
    )

    application.run_polling()

if __name__ == '__main__':
    main()
